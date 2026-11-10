#!/usr/bin/env python3
"""Search PubMed and rank candidate papers by relevance, evidence type, and recency."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
REQUEST_PAUSE_SECONDS = 0.34
FETCH_BATCH_SIZE = 100


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[\u2010-\u2015\-_/,:;()\[\]{}.!?\"'`]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", normalize_name(value))


def build_journal_index(venue_quality_dir: Path | None) -> dict[str, tuple[str, Any]]:
    if not venue_quality_dir:
        return {}
    data_path = venue_quality_dir / "journal_scores.json"
    if not data_path.exists():
        raise FileNotFoundError(f"journal_scores.json not found in {venue_quality_dir}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    index: dict[str, tuple[str, Any]] = {}
    for key, value in data.items():
        names = {key}
        if isinstance(value, dict) and value.get("name"):
            names.add(str(value["name"]))
        for name in names:
            for candidate in {normalize_name(name), compact_name(name)}:
                if candidate:
                    index[candidate] = (key, value)
    return index


def lookup_journal(index: dict[str, tuple[str, Any]], name: str) -> tuple[str, Any] | None:
    variants = [name]
    no_parentheses = re.sub(r"\s*\([^)]*\)", "", str(name or "")).strip()
    if no_parentheses and no_parentheses != name:
        variants.append(no_parentheses)
    prefix = re.split(r"[.:]", no_parentheses)[0].strip()
    if prefix and len(prefix) >= 5:
        variants.append(prefix)
    for variant in variants:
        for key in (normalize_name(variant), compact_name(variant)):
            if key in index:
                return index[key]
    return None


def venue_quality(record: dict[str, Any], journal_index: dict[str, tuple[str, Any]]) -> tuple[float, str, str]:
    if not journal_index:
        return 0.0, "", ""
    journal = record.get("journal") or record.get("journal_iso") or ""
    match = lookup_journal(journal_index, str(journal))
    if not match:
        return 0.0, "No matched venue metric", "low"
    matched_name, info = match
    info = info if isinstance(info, dict) else {}
    quartile = str(info.get("quartile") or "").upper()
    impact_factor = info.get("if")
    zone = info.get("csa_zone")
    try:
        impact_value = float(impact_factor)
    except (TypeError, ValueError):
        impact_value = 0.0
    try:
        zone_value = int(zone)
    except (TypeError, ValueError):
        zone_value = 0

    evidence = []
    if impact_factor not in (None, ""):
        evidence.append(f"IF {impact_factor}")
    if quartile:
        evidence.append(f"JCR {quartile}")
    if zone not in (None, ""):
        evidence.append(f"CAS Zone {zone}")

    score = 0.0
    if zone_value == 1 or (quartile == "Q1" and impact_value >= 10):
        score = 35 + min(impact_value, 50) / 2
    elif quartile == "Q1" or zone_value == 2 or impact_value >= 5:
        score = 22 + min(impact_value, 30) / 3
    elif quartile == "Q2":
        score = 12 + min(impact_value, 20) / 4
    elif evidence:
        score = min(impact_value, 10) / 2

    label = "; ".join(evidence) if evidence else f"Matched: {matched_name}"
    return score, label, "high"


def build_queries(topic: str, current_year: int) -> list[tuple[str, str, str]]:
    base = topic.strip()
    recent_start = max(current_year - 5, 2000)
    return [
        ("base", base, "relevance"),
        (
            "review_meta",
            f"({base}) AND (systematic review[Publication Type] OR meta-analysis[Publication Type] OR review[Publication Type])",
            "relevance",
        ),
        (
            "clinical_evidence",
            f"({base}) AND (randomized controlled trial[Publication Type] OR clinical trial[Publication Type] OR cohort OR prospective OR retrospective)",
            "relevance",
        ),
        ("recent", f"({base}) AND ({recent_start}:{current_year}[Date - Publication])", "pub date"),
    ]


def search_pubmed(query: str, max_results: int, sort: str) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
        "sort": sort,
    }
    url = f"{ESEARCH_URL}?{urllib.parse.urlencode(params)}"
    time.sleep(REQUEST_PAUSE_SECONDS)
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode("utf-8"))
    return [str(pmid) for pmid in data.get("esearchresult", {}).get("idlist", [])]


def text_of(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return "".join(node.itertext()).strip()


def fetch_records(pmids: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for start in range(0, len(pmids), FETCH_BATCH_SIZE):
        batch = pmids[start : start + FETCH_BATCH_SIZE]
        params = {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"}
        url = f"{EFETCH_URL}?{urllib.parse.urlencode(params)}"
        time.sleep(REQUEST_PAUSE_SECONDS)
        with urllib.request.urlopen(url) as response:
            root = ET.fromstring(response.read().decode("utf-8"))
        for article in root.findall(".//PubmedArticle"):
            record = parse_pubmed_article(article)
            if record.get("pmid"):
                records.append(record)
    return records


def parse_pubmed_article(article: ET.Element) -> dict[str, Any]:
    medline = article.find("MedlineCitation")
    article_data = medline.find("Article") if medline is not None else None
    journal = article_data.find("Journal") if article_data is not None else None
    pubmed_data = article.find("PubmedData")

    pmid = text_of(medline.find("PMID") if medline is not None else None)
    title = text_of(article_data.find("ArticleTitle") if article_data is not None else None)
    journal_title = text_of(journal.find("Title") if journal is not None else None)
    journal_iso = text_of(journal.find("ISOAbbreviation") if journal is not None else None)

    abstract_parts: list[str] = []
    abstract = article_data.find("Abstract") if article_data is not None else None
    if abstract is not None:
        for elem in abstract.findall("AbstractText"):
            label = elem.get("Label")
            body = text_of(elem)
            if body:
                abstract_parts.append(f"{label}: {body}" if label else body)

    publication_types: list[str] = []
    pub_type_list = article_data.find("PublicationTypeList") if article_data is not None else None
    if pub_type_list is not None:
        publication_types = [text_of(item) for item in pub_type_list.findall("PublicationType") if text_of(item)]

    authors: list[str] = []
    author_list = article_data.find("AuthorList") if article_data is not None else None
    if author_list is not None:
        for author in author_list.findall("Author")[:6]:
            collective = text_of(author.find("CollectiveName"))
            last = text_of(author.find("LastName"))
            initials = text_of(author.find("Initials"))
            name = collective or " ".join(part for part in [last, initials] if part)
            if name:
                authors.append(name)

    doi = ""
    pmcid = ""
    if pubmed_data is not None:
        for article_id in pubmed_data.findall("ArticleIdList/ArticleId"):
            id_type = article_id.get("IdType")
            if id_type == "doi":
                doi = text_of(article_id)
            elif id_type == "pmc":
                pmcid = text_of(article_id)

    return {
        "pmid": pmid,
        "title": title,
        "journal": journal_title or journal_iso,
        "journal_iso": journal_iso,
        "year": extract_year(journal),
        "authors": authors,
        "publication_types": publication_types,
        "abstract": " ".join(abstract_parts),
        "doi": doi,
        "pmcid": pmcid,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
    }


def extract_year(journal: ET.Element | None) -> str:
    if journal is None:
        return ""
    year = text_of(journal.find("JournalIssue/PubDate/Year"))
    if year:
        return year
    medline_date = text_of(journal.find("JournalIssue/PubDate/MedlineDate"))
    match = re.search(r"(19|20)\d{2}", medline_date)
    return match.group(0) if match else ""


def keyword_tokens(topic: str) -> set[str]:
    stop = {
        "and", "or", "the", "of", "in", "on", "with", "for", "to", "from",
        "a", "an", "study", "studies", "review", "clinical", "trial",
        "effect", "effects", "outcome", "outcomes", "patients", "patient",
        "disease", "therapy", "treatment",
    }
    tokens = {token.lower() for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", topic)}
    return {token for token in tokens if token not in stop}


def relevance_score(record: dict[str, Any], tokens: set[str]) -> tuple[float, str]:
    if not tokens:
        return 20.0, "No topic tokens provided; retained for manual review"
    title = str(record.get("title") or "").lower()
    abstract = str(record.get("abstract") or "").lower()
    title_hits = {token for token in tokens if token in title}
    abstract_hits = {token for token in tokens if token in abstract}
    score = len(title_hits) * 8 + len(abstract_hits) * 3
    if len(title_hits) >= 2:
        score += 10
    if record.get("abstract"):
        score += 5
    matched = sorted(title_hits | abstract_hits)
    reason = "Matched topic terms: " + ", ".join(matched[:8]) if matched else "Weak keyword match; manually check relevance"
    return score, reason


def evidence_score(publication_types: list[str], title: str, abstract: str) -> tuple[float, str]:
    joined = " | ".join(publication_types).lower()
    searchable = f"{title} {abstract}".lower()
    score = 0.0
    labels: list[str] = []
    if "practice guideline" in joined or "guideline" in joined:
        score += 35
        labels.append("Guideline")
    if "meta-analysis" in joined or "meta analysis" in searchable:
        score += 35
        labels.append("Meta-analysis")
    if "systematic review" in joined or "systematic review" in searchable:
        score += 32
        labels.append("Systematic review")
    elif "review" in joined:
        score += 15
        labels.append("Review")
    if "randomized controlled trial" in joined or "randomized" in searchable or "randomised" in searchable:
        score += 30
        labels.append("RCT")
    elif "clinical trial" in joined:
        score += 22
        labels.append("Clinical trial")
    if any(word in searchable for word in ["cohort", "prospective", "retrospective", "real-world", "registry"]):
        score += 12
        labels.append("Cohort/real-world")
    if any(kind in joined for kind in ["editorial", "letter", "comment", "news"]):
        score -= 30
        labels.append("Editorial/letter/comment")
    return score, ", ".join(dict.fromkeys(labels)) or "Original/other"


def recency_score(year: str, current_year: int) -> float:
    try:
        value = int(year)
    except (TypeError, ValueError):
        return 0.0
    age = max(current_year - value, 0)
    if age <= 5:
        return 12.0
    if age <= 10:
        return 6.0
    return 0.0


def recommendation(total: float, relevance: float, evidence: float) -> str:
    if relevance < 8:
        return "Needs manual check"
    if total >= 75 and evidence >= 25:
        return "Strongly recommended"
    if total >= 45:
        return "Keep for review"
    if total >= 25:
        return "Supplementary"
    return "Needs manual check"


def run_search(topic: str, max_per_query: int, current_year: int) -> tuple[list[str], list[dict[str, Any]]]:
    seen: set[str] = set()
    pmids: list[str] = []
    query_rows: list[dict[str, Any]] = []
    for label, query, sort in build_queries(topic, current_year):
        ids = search_pubmed(query, max_per_query, sort)
        query_rows.append({"module": label, "query": query, "pmids": ids})
        for pmid in ids:
            if pmid not in seen:
                seen.add(pmid)
                pmids.append(pmid)
    return pmids, query_rows


def rank_records(
    records: list[dict[str, Any]],
    topic: str,
    current_year: int,
    journal_index: dict[str, tuple[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    tokens = keyword_tokens(topic)
    journal_index = journal_index or {}
    ranked: list[dict[str, Any]] = []
    for record in records:
        relevance, relevance_reason = relevance_score(record, tokens)
        evidence, evidence_label = evidence_score(record.get("publication_types") or [], record.get("title") or "", record.get("abstract") or "")
        recent = recency_score(record.get("year") or "", current_year)
        venue, venue_label, venue_confidence = venue_quality(record, journal_index)
        total = relevance + evidence + recent + venue
        rec = recommendation(total, relevance, evidence)
        reasons = [relevance_reason, f"Evidence type: {evidence_label}"]
        if venue_label:
            reasons.append(f"Venue evidence: {venue_label}")
        if recent:
            reasons.append("Recent paper")
        ranked.append(
            {
                **record,
                "relevance_score": round(relevance, 1),
                "evidence_score": round(evidence, 1),
                "recency_score": round(recent, 1),
                "venue_score": round(venue, 1),
                "venue_evidence": venue_label,
                "venue_confidence": venue_confidence,
                "total_score": round(total, 1),
                "evidence_type": evidence_label,
                "recommendation": rec,
                "reason": "; ".join(reasons),
            }
        )
    order = {"Strongly recommended": 0, "Keep for review": 1, "Supplementary": 2, "Needs manual check": 3}
    ranked.sort(
        key=lambda item: (
            order.get(item["recommendation"], 9),
            -float(item.get("total_score") or 0),
            -(int(item.get("year") or 0) if str(item.get("year") or "").isdigit() else 0),
        )
    )
    return ranked


def write_markdown(topic: str, ranked: list[dict[str, Any]], query_rows: list[dict[str, Any]], limit: int | None = None) -> str:
    rows = ranked[:limit] if limit else ranked
    counts = Counter(item["recommendation"] for item in ranked)
    lines = [
        "# PubMed Paper Finder Results",
        "",
        f"Topic: `{topic}`",
        "",
        f"Deduplicated PubMed records: {len(ranked)}",
        f"- Strongly recommended: {counts.get('Strongly recommended', 0)}",
        f"- Keep for review: {counts.get('Keep for review', 0)}",
        f"- Supplementary: {counts.get('Supplementary', 0)}",
        f"- Needs manual check: {counts.get('Needs manual check', 0)}",
        "",
        "## Search Modules",
        "",
        "| Module | PMID hits | Query |",
        "| --- | ---: | --- |",
    ]
    for row in query_rows:
        query = str(row["query"]).replace("|", "\\|")
        lines.append(f"| {row['module']} | {len(row['pmids'])} | `{query}` |")
    lines.extend(
        [
            "",
            "## Ranked Candidate Papers",
            "",
            "| Recommendation | Title | Year | Journal | Venue evidence | Evidence type | PMID | Reason |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in rows:
        title = str(item.get("title") or "").replace("|", "\\|")
        journal = str(item.get("journal") or "").replace("|", "\\|")
        venue_label = str(item.get("venue_evidence") or "").replace("|", "\\|")
        reason = str(item.get("reason") or "").replace("|", "\\|")
        pmid = item.get("pmid") or ""
        link = f"[{pmid}]({item.get('pubmed_url')})" if pmid and item.get("pubmed_url") else str(pmid)
        lines.append(
            f"| {item['recommendation']} | {title} | {item.get('year','')} | {journal} | {venue_label} | {item.get('evidence_type','')} | {link} | {reason} |"
        )
    if limit and len(ranked) > limit:
        lines.append("")
        lines.append(f"> Showing top {limit} records. Use JSON/CSV output for the full result set.")
    lines.extend(
        [
            "",
            "> This is a first-pass reading-priority list based on PubMed metadata, abstracts, publication type, relevance, and recency. It does not replace expert review, systematic review methods, or full-text appraisal.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, ranked: list[dict[str, Any]]) -> None:
    fields = [
        "recommendation",
        "title",
        "year",
        "journal",
        "venue_evidence",
        "venue_confidence",
        "evidence_type",
        "pmid",
        "pubmed_url",
        "doi",
        "total_score",
        "reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in ranked:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("topic", help="English PubMed topic or Boolean query")
    parser.add_argument("--max-per-query", type=int, default=40)
    parser.add_argument("--current-year", type=int, default=2026)
    parser.add_argument(
        "--venue-quality-dir",
        type=Path,
        help="Optional path to paper-quality-filter/references for journal_scores.json venue metrics",
    )
    parser.add_argument("--output", type=Path, default=Path("pubmed_results.md"))
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--csv-output", type=Path)
    parser.add_argument("--show", type=int, default=30, help="Number of rows to include in Markdown output")
    args = parser.parse_args()

    pmids, query_rows = run_search(args.topic, args.max_per_query, args.current_year)
    if not pmids:
        print("No PubMed results found.", file=sys.stderr)
        return 1

    records = fetch_records(pmids)
    journal_index = build_journal_index(args.venue_quality_dir)
    ranked = rank_records(records, args.topic, args.current_year, journal_index)

    args.output.write_text(write_markdown(args.topic, ranked, query_rows, args.show), encoding="utf-8")
    if args.json_output:
        args.json_output.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.csv_output:
        write_csv(args.csv_output, ranked)

    counts = Counter(item["recommendation"] for item in ranked)
    print(f"Fetched and ranked {len(ranked)} unique PubMed records.")
    print(f"Strongly recommended: {counts.get('Strongly recommended', 0)}")
    print(f"Keep for review: {counts.get('Keep for review', 0)}")
    print(f"Supplementary: {counts.get('Supplementary', 0)}")
    print(f"Needs manual check: {counts.get('Needs manual check', 0)}")
    print(f"Markdown output: {args.output}")
    if args.json_output:
        print(f"JSON output: {args.json_output}")
    if args.csv_output:
        print(f"CSV output: {args.csv_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

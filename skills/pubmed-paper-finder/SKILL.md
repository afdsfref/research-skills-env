---
name: pubmed-paper-finder
description: Use when users want an AI agent to search PubMed for biomedical or medical papers, expand a natural-language research topic into multiple PubMed search modules, retrieve PMID-traceable metadata and abstracts, deduplicate results, and produce a ranked candidate reading list for literature reviews, manuscript introductions/discussions, journal clubs, or research background checks.
---

# PubMed Paper Finder

## Purpose

Use this Skill to help users find more relevant PubMed papers and turn the results into a clear candidate reading list.

The Skill focuses on open PubMed retrieval signals:

- search-query expansion and multiple search modules;
- PMID, title, journal, year, DOI, publication type, abstract, and PubMed URL;
- topic relevance from title/abstract keyword matching;
- evidence type, such as systematic review, meta-analysis, randomized controlled trial, clinical trial, cohort/real-world study, review, or original article;
- recency.

It can optionally connect to the companion `paper-quality-filter` repository for venue-level evidence such as impact factor, JCR quartile, and CAS zone:

```text
https://github.com/yilaai/paper-quality-filter
```

Do not duplicate large venue datasets inside this Skill. Keep `pubmed-paper-finder` focused on PubMed retrieval and use `--venue-quality-dir` when users want venue-quality enrichment.

## When To Use

Use this Skill when the user asks:

- "Search PubMed papers about ..."
- "帮我检索 PubMed 文献"
- "找更多 PubMed 相关论文"
- "筛选适合写综述/Introduction/Discussion 的 PubMed 文献"
- "给我一个带 PMID 的候选文献列表"
- "用 Agent 帮我构建 PubMed 检索式"

Do not use this Skill to make final medical claims or decide whether a paper is clinically correct. It produces a ranked candidate list for reading and human review.

## Workflow

### 1. Understand The Research Topic

Extract:

- disease, population, or model;
- intervention, exposure, drug, biomarker, method, or mechanism;
- outcome, endpoint, or research question;
- preferred study type if the user provides one.

If the user writes in Chinese, translate the topic into precise English biomedical terms before searching PubMed.

### 2. Build Multiple PubMed Search Modules

Do not rely on one keyword query. Use the bundled script:

```bash
python scripts/pubmed_paper_finder.py "TOPIC OR BOOLEAN QUERY" --max-per-query 40 --output pubmed_results.md
```

The script runs:

- `base`: broad topic relevance search;
- `review_meta`: systematic reviews, meta-analyses, and reviews;
- `clinical_evidence`: randomized controlled trials, clinical trials, cohort and observational evidence;
- `recent`: recent publications.

This helps reduce the common problem of searching too narrowly and missing useful papers.

### 3. Retrieve And Rank

The script:

1. searches PubMed via NCBI E-utilities;
2. merges and deduplicates PMIDs;
3. fetches metadata and abstracts in batches;
4. scores each record using topic relevance, evidence type, recency, and optional venue evidence;
5. exports Markdown, JSON, and/or CSV.

Default output columns:

```text
Recommendation | Title | Year | Journal | Venue Evidence | Evidence Type | PMID | Reason
```

### 4. Explain The Result Carefully

Use reading-priority language, not absolute quality judgments:

- `Strongly recommended`: highly relevant and strong evidence type, or very relevant recent review/trial evidence.
- `Keep for review`: relevant and likely useful for background, comparison, or citation screening.
- `Supplementary`: weak-to-moderate relevance or lower evidence priority.
- `Needs manual check`: insufficient metadata or weak topic match.

Always remind users that the output is a first-pass reading list. Final citation decisions require reading abstracts/full texts and domain expert judgment.

## Useful Commands

Markdown only:

```bash
python scripts/pubmed_paper_finder.py "SGLT2 inhibitors chronic kidney disease renal outcomes" --output ranked_pubmed.md
```

Markdown + JSON + CSV:

```bash
python scripts/pubmed_paper_finder.py "SGLT2 inhibitors chronic kidney disease renal outcomes" \
  --output ranked_pubmed.md \
  --json-output ranked_pubmed.json \
  --csv-output ranked_pubmed.csv
```

With optional venue-quality evidence from `paper-quality-filter`:

```bash
python scripts/pubmed_paper_finder.py "SGLT2 inhibitors chronic kidney disease renal outcomes" \
  --venue-quality-dir ../paper-quality-filter/references \
  --output ranked_pubmed_with_quality.md
```

Smaller quick test:

```bash
python scripts/pubmed_paper_finder.py "lung cancer immunotherapy biomarkers" --max-per-query 10 --show 15
```

## Caveat

This Skill helps users search more systematically and prioritize reading. It does not replace professional medical judgment, systematic review methodology, or full-text appraisal.

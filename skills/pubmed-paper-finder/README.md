# PubMed Paper Finder

An open-source Agent Skill for finding PubMed papers more systematically.

It helps an AI agent turn a biomedical research topic into multiple PubMed search modules, retrieve PMID-traceable metadata and abstracts, deduplicate records, and generate a ranked candidate reading list for literature reviews, manuscript introductions/discussions, journal clubs, and research background checks.

## What It Solves

PubMed search is often hard for beginners because:

- PubMed query expressions are easy to write too narrowly or too broadly.
- Biomedical topics often require synonyms, abbreviations, drug names, outcomes, and study-type filters.
- A single search query may miss useful reviews, meta-analyses, trials, or recent papers.
- Search results still need to be organized into a reading-priority list.

This Skill helps an agent:

1. Search from several angles instead of one keyword query.
2. Retrieve structured PubMed metadata and abstracts.
3. Deduplicate PMIDs.
4. Rank candidate papers by topic relevance, evidence type, and recency.
5. Export Markdown, JSON, and CSV results.

## Important Scope

This repository does not duplicate journal-metric datasets. For venue-level quality evidence, it can optionally connect to the companion open-source dataset:

https://github.com/yilaai/paper-quality-filter

The default ranking uses open PubMed signals:

- title and abstract relevance;
- publication type;
- recency;
- PMID traceability.

If you provide `paper-quality-filter/references`, the script can also add venue evidence such as impact factor, JCR quartile, and CAS zone.

## Repository Structure

```text
pubmed-paper-finder/
├── SKILL.md
├── README.md
├── scripts/
│   └── pubmed_paper_finder.py
└── examples/
    ├── sglt2_results.md
    ├── sglt2_results.json
    ├── sglt2_results.csv
    ├── sglt2_results_with_quality.md
    ├── sglt2_results_with_quality.json
    └── sglt2_results_with_quality.csv
```

## Quick Start

Run a PubMed search and generate a Markdown report:

```bash
python scripts/pubmed_paper_finder.py "SGLT2 inhibitors chronic kidney disease renal outcomes" --output pubmed_results.md
```

Generate Markdown, JSON, and CSV:

```bash
python scripts/pubmed_paper_finder.py "SGLT2 inhibitors chronic kidney disease renal outcomes" \
  --output pubmed_results.md \
  --json-output pubmed_results.json \
  --csv-output pubmed_results.csv
```

Use the companion venue-quality dataset:

```bash
git clone https://github.com/yilaai/paper-quality-filter.git ../paper-quality-filter

python scripts/pubmed_paper_finder.py "SGLT2 inhibitors chronic kidney disease renal outcomes" \
  --venue-quality-dir ../paper-quality-filter/references \
  --output pubmed_results_with_quality.md
```

Run a smaller quick test:

```bash
python scripts/pubmed_paper_finder.py "lung cancer immunotherapy biomarkers" --max-per-query 10 --show 15
```

## Output Columns

The Markdown report includes:

```text
Recommendation | Title | Year | Journal | Venue evidence | Evidence type | PMID | Reason
```

Recommendation tiers are reading-priority labels. When `--venue-quality-dir` is provided, venue-level evidence can influence the priority:

- `Strongly recommended`: highly relevant and strong evidence type, or very relevant recent review/trial evidence.
- `Keep for review`: relevant and likely useful for background, comparison, or citation screening.
- `Supplementary`: weak-to-moderate relevance or lower evidence priority.
- `Needs manual check`: insufficient metadata or weak topic match.

## Example

Topic:

```text
SGLT2 inhibitors chronic kidney disease renal outcomes
```

Example result summary:

```text
Deduplicated PubMed records: 41
- Strongly recommended: 25
- Keep for review: 16
- Supplementary: 0
- Needs manual check: 0
```

See [`examples/sglt2_results.md`](examples/sglt2_results.md).

With companion venue-quality data:

```text
Deduplicated PubMed records: 41
- Strongly recommended: 27
- Keep for review: 14
- Supplementary: 0
- Needs manual check: 0
```

See [`examples/sglt2_results_with_quality.md`](examples/sglt2_results_with_quality.md).

## How The Search Works

The script runs several bounded PubMed modules:

| Module | Purpose |
| --- | --- |
| `base` | broad topic relevance search |
| `review_meta` | systematic reviews, meta-analyses, and reviews |
| `clinical_evidence` | randomized controlled trials, clinical trials, cohort and observational evidence |
| `recent` | recent publications |

It uses NCBI E-utilities and does not scrape PubMed web pages.

## Caveat

This tool creates a first-pass reading-priority list. It does not replace professional medical judgment, systematic review methodology, or full-text appraisal.

Before citing a paper, read the abstract/full text and verify that it supports your claim.

## License

MIT

#!/usr/bin/env python3
"""PubMed E-utilities CLI (Windows-portable replacement for pubmed_eutils.sh).

The upstream skill ships `pubmed_eutils.sh`, which needs bash. This host has no
bash, so this script exposes the same commands with the same stdout contract so
`parse_pubmed.py` can consume the output unchanged.

Commands
    search <query> [retmax]        esearch.fcgi JSON  -> parse_pubmed.py esearch
    fetch <pmid1,pmid2,...>        efetch.fcgi XML    -> parse_pubmed.py efetch|bibtex
    fetch_json <pmid1,...>         esummary.fcgi JSON -> parse_pubmed.py esummary
    related <pmid> [retmax]        elink neighbor_score, then esummary JSON
    cite_lookup <title>            esearch on "<title>"[Title]

Environment
    NCBI_API_KEY   optional; raises the rate limit from 3/s to 10/s
    NCBI_EMAIL     optional; contact address sent with each request
    NCBI_TOOL      optional; tool name sent with each request

Rate limiting: one request at a time, minimum spacing between calls
(0.35 s without an API key, 0.11 s with one), plus retry with backoff on
429/5xx, which is what the NCBI usage policy asks for.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DB = "pubmed"
TOOL = os.environ.get("NCBI_TOOL", "dsh-search-lit")
EMAIL = os.environ.get("NCBI_EMAIL", "noreply@example.com")
API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
MIN_INTERVAL = 0.11 if API_KEY else 0.35

_last_call = 0.0


def _sleep_if_needed() -> None:
    global _last_call
    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()


def _params(**extra: object) -> str:
    q = {"tool": TOOL, "email": EMAIL}
    if API_KEY:
        q["api_key"] = API_KEY
    q.update({k: v for k, v in extra.items() if v is not None})
    return urllib.parse.urlencode(q)


def get(path: str, **params: object) -> str:
    """GET one E-utilities endpoint and return the body as text."""
    url = f"{BASE}/{path}?{_params(**params)}"
    delay = 1.0
    last_error: Exception | None = None
    for _ in range(4):
        _sleep_if_needed()
        req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL} (python-urllib)"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504):
                raise SystemExit(json.dumps({"error": f"HTTP {exc.code}", "url": url}))
            time.sleep(delay)
            delay *= 2
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            time.sleep(delay)
            delay *= 2
    raise SystemExit(json.dumps({"error": f"request failed: {last_error}", "url": url}))


def _positive_int(value: str, name: str) -> int:
    try:
        n = int(str(value).strip())
    except ValueError:
        raise SystemExit(json.dumps({"error": f"{name} must be a whole number"}))
    if n <= 0:
        raise SystemExit(json.dumps({"error": f"{name} must be greater than zero"}))
    return n


def cmd_search(argv: list[str]) -> str:
    if not argv:
        raise SystemExit("Usage: search <query> [retmax]")
    query = argv[0]
    retmax = _positive_int(argv[1] if len(argv) > 1 else "20", "retmax")
    return get("esearch.fcgi", db=DB, term=query, retmax=retmax, retmode="json", sort="relevance")


def cmd_fetch(argv: list[str]) -> str:
    if not argv:
        raise SystemExit("Usage: fetch <pmid1,pmid2,...>")
    return get("efetch.fcgi", db=DB, id=argv[0], rettype="xml", retmode="xml")


def cmd_fetch_json(argv: list[str]) -> str:
    if not argv:
        raise SystemExit("Usage: fetch_json <pmid1,pmid2,...>")
    return get("esummary.fcgi", db=DB, id=argv[0], retmode="json")


def cmd_related(argv: list[str]) -> str:
    if not argv:
        raise SystemExit("Usage: related <pmid> [retmax]")
    pmid = argv[0]
    retmax = _positive_int(argv[1] if len(argv) > 1 else "10", "retmax")
    body = get("elink.fcgi", dbfrom=DB, db=DB, id=pmid, cmd="neighbor_score", retmode="json")
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return json.dumps({"error": "elink returned non-JSON"})
    linked: list[str] = []
    for linkset in data.get("linksets", []) or []:
        for db in linkset.get("linksetdbs", []) or []:
            if db.get("linkname") == "pubmed_pubmed":
                linked = [str(item["id"]) for item in (db.get("links") or [])][:retmax]
                break
        if linked:
            break
    if not linked:
        return json.dumps({"error": "No related articles found"})
    return cmd_fetch_json([",".join(linked)])


def cmd_cite_lookup(argv: list[str]) -> str:
    if not argv:
        raise SystemExit("Usage: cite_lookup <title>")
    return cmd_search([f"{argv[0]}[Title]", "5"])


COMMANDS = {
    "search": cmd_search,
    "fetch": cmd_fetch,
    "fetch_json": cmd_fetch_json,
    "related": cmd_related,
    "cite_lookup": cmd_cite_lookup,
}

USAGE = (
    "Usage: python pubmed_eutils.py <command> <args...>\n"
    "Commands: search, fetch, fetch_json, related, cite_lookup\n"
    "Pipe the output into parse_pubmed.py (esearch | esummary | efetch | bibtex).\n"
    "On Windows use python; on hosts with python3 use that.\n"
)


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("help", "-h", "--help"):
        sys.stdout.write(USAGE)
        return 0
    command = argv[0]
    handler = COMMANDS.get(command)
    if handler is None:
        sys.stderr.write(f"Unknown command: {command}\n{USAGE}")
        return 2
    result = handler(argv[1:])
    sys.stdout.write(result)
    if not result.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Scripts — reproduce & validate

Two scripts make the published numbers verifiable end to end.

## reproduce.py — raw → export (the reproducibility entrypoint)

Rebuilds every published dataset from the original BLS sources with one command:

    python scripts/reproduce.py                 # full run → real DB + export/
    python scripts/reproduce.py --no-download    # offline (fails if raw files missing)
    python scripts/reproduce.py --formats csv    # only the CSV (+ codebook)
    # scratch verify (does not touch the committed DB/exports):
    python scripts/reproduce.py --no-download --db /tmp/x.duckdb --export-dir /tmp/exp

Pipeline: ingest (BLS CPS API + LAUS + cpsaat07 PDF) → load to DuckDB → clean →
prepare → export. On the first run it downloads sources into data/raw/ (URLs in
SOURCES.md); after that it runs offline from the cache. Logic lives in src/
(ingest.py, clean_quality.py, prepare.py).

## validate_charts.py — pre-publish data gate

Re-derives what each published chart shows straight from DuckDB and confirms the
exports match, the headline facts hold, and structural invariants hold. Exit 0 =
safe to publish; non-zero = do not publish (it prints the failing check).

    python scripts/validate_charts.py

## Run order & interpreter

1. python scripts/reproduce.py       # build raw → export
2. python scripts/validate_charts.py # confirm exit 0

Run with Python 3.11+ and the packages in requirements.txt (duckdb, pandas,
pyarrow, requests, beautifulsoup4, lxml, pdfplumber, openpyxl, pyyaml, Pillow).

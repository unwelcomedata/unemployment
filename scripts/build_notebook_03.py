"""Build 03-prepare.ipynb for the unemployment project.

03-prepare OWNS the chart-ready datasets (built from the interim _clean tables)
AND the sellable export package. 04-viz only CONSUMES the prepared tables.
This authors the notebook via nbformat (house convention); execute it with
nbconvert on the `data_projects` conda kernel.
"""
import nbformat
from pathlib import Path

nb = nbformat.v4.new_notebook()
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.13.5"},
}

cells = []

# ── Cell 0 — title ───────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
# 03 — Prepare: build chart-ready tables + export package

This notebook is the **preparation stage**. It does the two jobs `03-prepare` owns:

1. **Build the chart-ready / analysis-ready tables** — the shaped, aggregated
   per-chart datasets that `04-viz` consumes. All aggregation runs in DuckDB,
   reusing the EXACT SQL that defines each chart (series ids, filters, the
   trailing-12-month state window, groupings). These are persisted both as
   **persistent DuckDB tables** (so `04-viz` reads them by name) and as
   **Parquet** under `data/processed/`.
2. **Package the sellable export** — three analysis-ready datasets (national
   annual demographics, state trailing-12-month LAUS, education × race) written
   to `export/` as **CSV + Excel + Parquet** each with a plain-English
   **codebook**, per the `export:` block in `config.yaml`.

`04-viz` then opens the DB **read-only** and renders the charts — it no longer
builds any `chart_*` table. DuckDB is single-writer, so this notebook is the
writer and closes its connection in the `## Cleanup` cell before `04-viz` opens.

> Chart-5's geopandas join + banding + render deliberately stay in `04-viz`
> (presentation layer); only the per-state `chart_state_map` dataset is prepared
> here. That is the clean 03/04 seam.
"""))

# ── Cell 1 — setup (writable connection) ─────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
import sys, os
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

PROJECT = Path.cwd()
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "src"))

import duckdb
import pandas as pd

from src.ingest import load_config
from src.clean_quality import get_connection, save_processed, register_source, get_sources
from src.prepare import (
    build_chart_headline,
    build_chart_u3_u6,
    build_chart_race,
    build_chart_youth,
    build_chart_state_map,
    build_chart_states_selected,
    build_chart_edu_race,
    build_export_national_annual,
    state_map_window_label,
    numeric_summary,
    package_dataset,
)

cfg = load_config("config.yaml")
con = get_connection(cfg)   # WRITABLE — 03-prepare is the writer
print("Connected (rw). Tables:", [t[0] for t in con.execute("SHOW TABLES").fetchall()])
"""))

# ── Cell 2 — build chart-ready tables (markdown) ─────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Build chart-ready tables

These are the shaped per-chart datasets `04-viz` consumes. Each is built from an
interim `_clean` table with the exact chart logic — unchanged values, filters,
windows, band thresholds, and groupings:

- **chart_headline** — headline U-3 rate, annual avg, 1948–2026 (`LNS14000000`).
- **chart_u3_u6** — U-3 vs U-6, annual avg, `year >= 1994` (`LNS14000000`, `LNS13327709`).
- **chart_race** — White / Hispanic / Black, annual avg, `year >= 1973`
  (`…003` / `…009` / `…006`).
- **chart_youth** — teens 16–19 (`LNS14000012`) vs adults 20+ (`LNS14000024`),
  annual avg, 1948–2026.
- **chart_state_map** — per-state average over the **12 most recent distinct
  monthly periods** (distinct-period window survives the missing 2025-10 gap).
- **chart_states_selected** — CA / TX / FL / NY / MI / MA, annual avg.
- **chart_edu_race** — race gap by education level, 25+, 2024 (White vs Black),
  from the annual `cpsaat07` table.

All aggregation stays in DuckDB (no pandas transforms).
"""))

# ── Cell 3 — build + confirm chart tables (code) ─────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
headline        = build_chart_headline(con)
u3_u6           = build_chart_u3_u6(con)
race            = build_chart_race(con)
youth           = build_chart_youth(con)
state_map       = build_chart_state_map(con)
states_selected = build_chart_states_selected(con)
edu_race        = build_chart_edu_race(con)

# Build confirmations (MIN/MAX/COUNT) mirroring the old 04-viz build prints.
print("chart_headline:",        con.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_headline").fetchone())
print("chart_u3_u6:",           con.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_u3_u6").fetchone())
print("chart_race:",            con.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_race").fetchone())
print("chart_youth:",           con.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_youth").fetchone())
print(f"chart_state_map: {len(state_map)} states, trailing-12 window {state_map_window_label(con)}")
print("chart_states_selected:", con.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_states_selected").fetchone())
print("chart_edu_race:",        con.execute("SELECT COUNT(*) FROM chart_edu_race").fetchone())
"""))

# ── Cell 4 — quality checks (markdown) ───────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Quality checks before persisting

Confirm the prepared tables have the expected shape and the headline facts are
intact (same values the charts show), so a drift is caught here, before export.
"""))

# ── Cell 5 — quality checks (code) ───────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# Row-count expectations for the prepared tables.
expected_rows = {
    "chart_headline": 79, "chart_u3_u6": 33, "chart_race": 54,
    "chart_youth": 79, "chart_state_map": 51, "chart_states_selected": 51,
    "chart_edu_race": 8,
}
for t, n in expected_rows.items():
    got = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    flag = "ok" if got == n else "DRIFT"
    print(f"  {t:<24} {got:>4} rows (expected {n})  [{flag}]")

# Headline-fact spot checks (must match the charts).
dc_rate = con.execute("SELECT rate FROM chart_state_map WHERE state_abbrev='DC'").fetchone()[0]
dc_top  = con.execute("SELECT state_abbrev FROM chart_state_map ORDER BY rate DESC LIMIT 1").fetchone()[0]
print(f"\\n  chart_state_map: DC = {dc_rate}% (top state = {dc_top})")

edu = {(r[0], r[1]): r[2] for r in con.execute(
    "SELECT education_level, race, unemployment_rate FROM chart_edu_race"
).fetchall()}
print("  chart_edu_race per-tier White/Black:")
for tier in ["Less than high school", "High school, no college",
             "Some college or associate degree", "Bachelor's degree and higher"]:
    print(f"    {tier:<36} White {edu[(tier,'White')]}  Black {edu[(tier,'Black')]}")

teen_breaches = con.execute(
    "SELECT COUNT(*) FROM chart_youth WHERE youth_16_19 <= adults_20plus"
).fetchone()[0]
print(f"\\n  chart_youth rows where teen <= adults 20+: {teen_breaches} (expect 0)")

ratio_lt_13 = con.execute(
    "SELECT COUNT(*) FROM chart_race WHERE black/white < 1.3"
).fetchone()[0]
print(f"  chart_race years with Black/White ratio < 1.3: {ratio_lt_13} (expect < 5)")
"""))

# ── Cell 6 — persist prepared tables (markdown) ──────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Persist prepared tables to `data/processed/`

The chart tables now live as persistent DuckDB tables (what `04-viz` reads by
name). We also write each to `data/processed/*.parquet` so the prepared data is
inspectable on disk and regenerable. (`data/processed/` is gitignored.)
"""))

# ── Cell 7 — persist prepared tables (code) ──────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
prepared = {
    "chart_headline.parquet":        headline,
    "chart_u3_u6.parquet":           u3_u6,
    "chart_race.parquet":            race,
    "chart_youth.parquet":           youth,
    "chart_state_map.parquet":       state_map,
    "chart_states_selected.parquet": states_selected,
    "chart_edu_race.parquet":        edu_race,
}
for fname, df in prepared.items():
    save_processed(df, cfg, fname)
"""))

# ── Cell 8 — package the sellable datasets (markdown) ────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Package the sellable export (3 datasets + codebook)

Three analysis-ready datasets go to `export/` as **CSV + Excel + Parquet** each
with a plain-English **codebook** (per the `export:` block in `config.yaml`;
`strip_pii_columns` is empty, so `strip_pii()` is a no-op but is still called by
`package_dataset`):

1. **`unemployment_national_annual_v1`** — the national annual panel the line
   charts (U-3, U-6, race, youth) are cut from.
2. **`unemployment_states_trailing12_v1`** — per-state trailing-12-month average
   (the choropleth dataset).
3. **`unemployment_by_education_race_2024_v1`** — race × education-level rates,
   25+, 2024 (the companion chart dataset).

All three are **BLS, public domain**. Series-break caveats come from `SOURCES.md`.
"""))

# ── Cell 9 — package the sellable datasets (code) ────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# ── 1. National annual demographics panel ────────────────────────────────────
national_annual = build_export_national_annual(con)
NATIONAL_CB = {
    "year":               "Calendar year (annual average of monthly values).",
    "u3_rate":            "Official U-3 unemployment rate (%), seasonally adjusted, 16+. BLS CPS LNS14000000.",
    "u6_rate":            "Broad U-6 rate (%): U-3 plus marginally-attached workers and involuntary part-timers. Begins 1994. BLS CPS LNS13327709.",
    "white_rate":         "U-3 unemployment rate (%) for White workers, seasonally adjusted. BLS CPS LNS14000003 (begins 1954; comparable from 1973).",
    "black_rate":         "U-3 unemployment rate (%) for Black workers, seasonally adjusted. BLS CPS LNS14000006 (begins 1972).",
    "hispanic_rate":      "U-3 unemployment rate (%) for Hispanic workers, seasonally adjusted. BLS CPS LNS14000009 (begins 1973).",
    "adults_20plus_rate": "U-3 unemployment rate (%) for workers 20 years and over, seasonally adjusted. BLS CPS LNS14000024.",
    "youth_16_19_rate":   "U-3 unemployment rate (%) for workers 16-19 years, seasonally adjusted. BLS CPS LNS14000012.",
}
NATIONAL_NOTES = \"\"\"
    Source: U.S. Bureau of Labor Statistics, Current Population Survey (CPS).
    License: Public domain (U.S. Government work).
    Measure: U-3 is the official unemployment rate (jobless, available, and
    actively looked in the last 4 weeks, as a share of the labor force); U-6
    adds discouraged/marginally-attached workers plus involuntary part-timers.
    All values are annual averages of the seasonally-adjusted monthly series.

    Methodology changes / series breaks:
      - 1994 CPS redesign introduced the U-4 through U-6 alternative measures
        (hence u6_rate begins 1994) and new job-search/duration questions.
      - 2011 raised the maximum recorded jobless-duration from ~2 to ~5 years
        (affects duration series, NOT the U-3/U-6 rate levels here).
      - Race/ethnicity series start on different dates: White 1954, Black 1972,
        Hispanic 1973; comparisons are reliable from 1973 forward.
    Retrieved 2026-09-28.
\"\"\"
paths_national = package_dataset(
    national_annual, cfg, name="unemployment_national_annual_v1",
    codebook=NATIONAL_CB, notes=NATIONAL_NOTES,
)

# ── 2. State trailing-12-month average (LAUS) ────────────────────────────────
states_export = con.execute(
    "SELECT state_name, state_abbrev, rate, n_months FROM chart_state_map ORDER BY rate DESC"
).df()
STATES_CB = {
    "state_name":   "State (or District of Columbia) name.",
    "state_abbrev": "Two-letter USPS state abbreviation (DC for the District of Columbia).",
    "rate":         "Average seasonally-adjusted U-3 unemployment rate (%) over the trailing 12 most recent distinct monthly periods (Jul 2025 - Jul 2026).",
    "n_months":     "Number of monthly observations in the average (12 for all states except Wyoming, which reports through Dec 2025 = 5 months).",
}
STATES_NOTES = \"\"\"
    Source: U.S. Bureau of Labor Statistics, Local Area Unemployment Statistics
    (LAUS). License: Public domain (U.S. Government work).
    Measure: model-based, seasonally-adjusted state unemployment rate. Each row
    is the average of the state's monthly rate over the 12 most recent distinct
    (year, month) periods present in the data (2025-10 is absent, so the 12
    periods span 13 calendar months). Wyoming reports only through Dec 2025, so
    its average covers 5 months.
    Methodology changes / series breaks: LAUS moved to a revised model-based
    estimation approach in 2021 (see SOURCES.md).
    Retrieved 2026-09-28.
\"\"\"
paths_states = package_dataset(
    states_export, cfg, name="unemployment_states_trailing12_v1",
    codebook=STATES_CB, notes=STATES_NOTES,
)

# ── 3. Education x race (2024, 25+) ──────────────────────────────────────────
edu_export = con.execute(
    "SELECT year, education_level, education_order, race, unemployment_rate "
    "FROM chart_edu_race "
    "ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END"
).df()
EDU_CB = {
    "year":              "Calendar year of the annual average (2024).",
    "education_level":   "Highest education tier: 'Less than high school', 'High school, no college', 'Some college or associate degree', or \\\"Bachelor's degree and higher\\\".",
    "education_order":   "Integer sort key for education_level (lowest to highest attainment).",
    "race":              "Race group: 'White' or 'Black'.",
    "unemployment_rate": "Annual-average unemployment rate (%), not seasonally adjusted, workers 25 and over, for the race x education cell. BLS CPS table cpsaat07.",
}
EDU_NOTES = \"\"\"
    Source: U.S. Bureau of Labor Statistics, Current Population Survey (CPS),
    annual table cpsaat07. License: Public domain (U.S. Government work).
    Measure: annual-average unemployment rate, population 25 years and over, NOT
    seasonally adjusted. This is a DIFFERENT grain from the monthly, seasonally
    adjusted, 16+ national series in the other exports; do not conflate them.
    Interpretation: the Black/White gap holds at every education level, which is
    why economists attribute the ~2:1 gap mainly to labor-market discrimination
    and occupational segregation rather than education (EPI 2015, 2019; Quillian
    et al. PNAS 2017; Fed FEDS 2017-071). Retrieved 2026-09-28.
\"\"\"
paths_edu = package_dataset(
    edu_export, cfg, name="unemployment_by_education_race_2024_v1",
    codebook=EDU_CB, notes=EDU_NOTES,
)

print("\\nExport files written:")
for grp in (paths_national, paths_states, paths_edu):
    for kind, p in grp.items():
        print(f"  {kind:<9} {p}")
"""))

# ── Cell 10 — register provenance (markdown) ─────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Register provenance for the prepared/exported datasets

Record the three export datasets in the `_sources` provenance table so the DB
documents where each prepared dataset came from (the underlying `_clean` tables
are already registered by `02-clean`).
"""))

# ── Cell 11 — register provenance (code) ─────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
register_source(
    con, table="unemployment_national_annual_v1",
    name="BLS CPS — national annual unemployment panel (prepared)",
    url="https://www.bls.gov/cps/",
    license="Public domain (U.S. Government work)",
    notes="Annual-average U-3/U-6 + race + age panel; prepared from unemployment_national_clean in 03-prepare.",
    retrieved="2026-09-28",
    methodology="Annual averages of seasonally-adjusted monthly CPS series.",
    series_breaks="U-6 begins 1994 (CPS redesign); race series start White 1954 / Black 1972 / Hispanic 1973.",
)
register_source(
    con, table="unemployment_states_trailing12_v1",
    name="BLS LAUS — state trailing-12-month average (prepared)",
    url="https://www.bls.gov/lau/",
    license="Public domain (U.S. Government work)",
    notes="Per-state average over the 12 most recent distinct monthly periods; prepared from unemployment_states_clean in 03-prepare.",
    retrieved="2026-09-28",
    methodology="Model-based seasonally-adjusted state rate; 12 most-recent distinct (year,month) periods.",
    series_breaks="LAUS revised model-based estimation in 2021; Wyoming reports through Dec 2025 (5 months).",
)
register_source(
    con, table="unemployment_by_education_race_2024_v1",
    name="BLS CPS cpsaat07 — unemployment by education x race, 25+ (prepared)",
    url="https://www.bls.gov/cps/cpsaat07.htm",
    license="Public domain (U.S. Government work)",
    notes="2024 annual-average rate by education tier x race (White/Black), 25+; prepared from unemployment_by_education_race in 03-prepare.",
    retrieved="2026-09-28",
    methodology="Annual average, NOT seasonally adjusted, population 25 and over.",
    series_breaks="Different grain from the monthly SA 16+ series; not comparable to the national annual panel.",
)
print(get_sources(con).to_string(index=False))
"""))

# ── Cell 12 — cleanup (markdown) ─────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Cleanup

Close the writable connection so the single-writer lock is released before
`04-viz` opens the DB read-only.
"""))

# ── Cell 13 — cleanup (code) ─────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/03-prepare.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")

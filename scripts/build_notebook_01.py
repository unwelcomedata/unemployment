"""Build 01-ingest.ipynb for the unemployment project."""
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

# ── Cell 0 — title ──────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""# 01 — Ingest: BLS Unemployment Data

Fetches U.S. unemployment data from the Bureau of Labor Statistics (BLS)
Public Data API v2 and lands it in `data/raw/` and `data/project.duckdb`.

**Two data pulls:**
1. **National demographic series** — monthly unemployment rate by age, sex,
   race/ethnicity, and alternative measures U-3 through U-6 (1948–2026).
   20 BLS CPS series (LNS prefix), seasonally adjusted.
2. **State-level series** — monthly unemployment rate for all 50 states + DC
   (1976–2026). 51 BLS LAUS series (LASST prefix), seasonally adjusted.

**API notes:** BLS Public Data API v2, no registration key required for these
pull sizes. Without a key: 25 series/request, 10-year windows, 25 req/day.
Both pulls fit comfortably within those limits.

**No transformation happens here** — raw observations land in DuckDB exactly
as the BLS API returns them. All cleaning is in `02-clean.ipynb`.
"""))

# ── Cell 1 — setup ──────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
import sys, os
from pathlib import Path

# Navigate to project root regardless of how the kernel was launched
PROJECT = Path.cwd()
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT / "src"))

from ingest import (
    load_config,
    ingest_bls_api,
    KEY_UNEMPLOYMENT_SERIES,
    ALTERNATIVE_MEASURES_SERIES,
    STATE_UNEMPLOYMENT_SERIES,
)
from clean_quality import get_connection, load_to_duckdb, register_source
import pandas as pd
import duckdb

cfg = load_config()
print(f"Project: {cfg['project_name']}")
print(f"DuckDB:  {cfg['settings']['duckdb_file']}")
"""))

# ── Cell 2 — section header: national series ────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## National Demographic Series (BLS CPS, LNS prefix)

Source: **BLS Current Population Survey (CPS)**, the monthly household survey
that produces the headline unemployment rate.

**Series fetched (20 total):**

| Category | Series |
|---|---|
| Overall | Total 16+, Men 16+, Women 16+ |
| By sex (adults) | Men 20+, Women 20+ |
| By age | 16–19, 20–24, 25–34, 35–44, 45–54 |
| By race/ethnicity | White, Black, Hispanic, Asian |
| Alternative measures | U-3 (official), U-4, U-5, U-6 (broadest) |

All series are **seasonally adjusted monthly rates** (unemployment %).

**Definition (U-3, the headline rate):** unemployed = without a job, available
to work, and actively looked in the last 4 weeks ÷ civilian labor force. U-6
is the broadest measure — adds marginally attached workers and people working
part-time for economic reasons. Never compare U-3 and U-6 as if they're the
same thing.

**Series breaks to note:**
- U-4/U-5/U-6 alternative measures only go back to 1994 (introduced then).
- Black series back to 1972, Hispanic to 1973, Asian to 2003.
- White series back to 1954; total/sex/most age groups back to 1948.
- Two older age-bracket series (55-64y, 65+y) returned no data on this API —
  those BLS series IDs may have been replaced; not a critical gap for the core
  story and can be filled in later.
"""))

# ── Cell 3 — load national data from parquet ────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# Load from the cached raw parquet (already fetched this session).
# The parquet was saved to data/raw/bls_api_data.parquet by ingest_bls_api().
# Re-running this cell is safe: it just reloads from cache, no API call.
df_national = pd.read_parquet("data/raw/bls_api_data.parquet")
df_national["label"] = df_national["series_id"].map(
    {**KEY_UNEMPLOYMENT_SERIES, **ALTERNATIVE_MEASURES_SERIES}
)

print(f"National series loaded: {len(df_national):,} observations")
print(f"Series present: {df_national['series_id'].nunique()} of 20 requested")
print()

# Year coverage by series
coverage = (
    df_national
    .groupby(["label", "series_id"])["year"]
    .agg(first="min", last="max", n="count")
    .reset_index()
    .sort_values("first")
)
print(coverage[["label", "first", "last", "n"]].to_string(index=False))
"""))

# ── Cell 4 — load into DuckDB ────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
con = get_connection(cfg)

# Load national data
con.execute("DROP TABLE IF EXISTS unemployment_national")
con.execute("CREATE TABLE unemployment_national AS SELECT * FROM df_national ORDER BY series_id, year, period")

n = con.execute("SELECT COUNT(*) FROM unemployment_national").fetchone()[0]
print(f"unemployment_national: {n:,} rows loaded into DuckDB")

register_source(
    con,
    "unemployment_national",
    name="BLS CPS National Unemployment (demographics)",
    url="https://api.bls.gov/publicAPI/v2/timeseries/data/",
    license="Public domain (U.S. government work)",
    notes=(
        "Seasonally adjusted monthly unemployment rates by age/sex/race + U3-U6 "
        "alternative measures. 18 of 20 requested series returned data. "
        "Missing: 55-64y (LNS14000095) and 65+y (LNS14000097) — series IDs may "
        "have changed in recent BLS catalog updates."
    ),
    methodology=(
        "BLS CPS household survey, ~60,000 households/month. U-3 = official "
        "unemployment rate (jobless + available + actively searched last 4 weeks "
        "/ civilian labor force). U-6 = U-3 + marginally attached + involuntary "
        "part-timers. All series seasonally adjusted via X-13ARIMA-SEATS."
    ),
    series_breaks=(
        "U-4/U-5/U-6 begin 1994. Black series 1972, Hispanic 1973, Asian 2003, "
        "White 1954. Biennial CPS redesigns (1994 most significant) introduced "
        "new questions affecting duration/reason categories — rates themselves "
        "are broadly comparable across the full history."
    ),
)
print("Source registered in _sources.")
"""))

# ── Cell 5 — section header: state series ───────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## State-Level Series (BLS LAUS, LASST prefix)

Source: **BLS Local Area Unemployment Statistics (LAUS)** program.

51 state-level series (50 states + DC), monthly, 1976–2026.
All seasonally adjusted unemployment rates (U-3 definition only at state level).

**Key difference from national CPS:** LAUS state estimates are **model-based**
(not direct survey reads). The state CPS sample is too small to publish alone,
so LAUS blends CPS with UI claims data and CES payroll estimates via a
signal-plus-noise time-series model. Re-estimation of the model means historical
values can be revised — treat each pull as a single vintage.
"""))

# ── Cell 6 — inspect state data ─────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# State data was fetched in a prior session and is already in DuckDB.
df_states = con.execute("SELECT * FROM unemployment_states").df()
print(f"unemployment_states: {len(df_states):,} rows")
print(f"States: {df_states['label'].nunique()}")
years = df_states["year"].agg(["min", "max"])
print(f"Year range: {int(df_states['year'].min())} – {int(df_states['year'].max())}")
print()
print(df_states.head(10).to_string(index=False))
"""))

# ── Cell 7 — quick sanity checks ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Quick inspection — plausibility checks
"""))

cells.append(nbformat.v4.new_code_cell("""\
# National: check headline U-3 total rate at well-known recession peaks
total = con.execute(\"\"\"
    SELECT year, period, value
    FROM unemployment_national
    WHERE series_id = 'LNS14000000'
      AND (
          (year = 1982 AND period = 'M11') OR  -- early-80s recession peak ~10.8
          (year = 2009 AND period = 'M10') OR  -- Great Recession peak ~10.0
          (year = 2020 AND period = 'M04') OR  -- COVID peak ~14.7
          (year = 2026 AND period = 'M07')     -- recent
      )
    ORDER BY year, period
\"\"\").df()
print("Headline U-3 at recession peaks + recent:")
print(total.to_string(index=False))

# State: check current rate for a few known states
recent_states = con.execute(\"\"\"
    SELECT label, year, period, value
    FROM unemployment_states
    WHERE year = (SELECT MAX(year) FROM unemployment_states)
    ORDER BY value DESC
    LIMIT 10
\"\"\").df()
print()
print("Top 10 states by unemployment rate (most recent year):")
print(recent_states.to_string(index=False))
"""))

# ── Cell 8 — summary ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Summary

| Table | Rows | Coverage | Notes |
|---|---|---|---|
| `unemployment_national` | 13,786 | 1948–2026, 18 series | National by age/sex/race + U3–U6 |
| `unemployment_states` | 30,950 | 1976–2026, 51 series | All states + DC, U-3 only |
| `series_catalog` | 71 | — | Series ID → label lookup |
| `state_ref` | 51 | — | State FIPS + series ID crosswalk |

Raw data saved to `data/raw/bls_api_data.parquet` (national) and
`data/raw/bls_api_states.parquet` (states).

**Next:** `02-clean.ipynb` — standardize dates, run quality checks, save
analysis-ready interim Parquet files.
"""))

# ── Cell 9 — cleanup ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("con.close()\nprint('Connection closed.')"))

nb.cells = cells

out = Path("notebooks/01-ingest.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")

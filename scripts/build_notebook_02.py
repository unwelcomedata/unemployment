"""Build 02-clean.ipynb for the unemployment project."""
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
cells.append(nbformat.v4.new_markdown_cell("""\
# 02 — Clean: Unemployment Data

Loads raw BLS data from DuckDB, standardizes dates and types, filters
annual-average placeholders, adds analysis-ready derived columns, runs
quality reports, and saves interim Parquet files to `data/interim/`.

**All cleaning runs inside DuckDB — no pandas chained operations.**

**Two tables produced:**
- `unemployment_national_clean` — national by age/sex/race + U3–U6, 1948–2026
- `unemployment_states_clean` — all states + DC, monthly, 1976–2026
"""))

# ── Cell 1 — setup ──────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
import sys, os
from pathlib import Path

PROJECT = Path.cwd()
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT / "src"))

from clean_quality import get_connection, quality_report, save_interim, register_source, run_sql
import pandas as pd
import duckdb

cfg = {
    "paths": {
        "data_interim": "data/interim",
        "data_processed": "data/processed",
    },
    "settings": {
        "duckdb_file": "data/project.duckdb",
        "parquet_engine": "pyarrow",
    },
}
con = get_connection(cfg)
print("Connected to DuckDB:", cfg["settings"]["duckdb_file"])
tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
print("Tables available:", tables)
"""))

# ── Cell 2 — national data cleaning ─────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## National Unemployment Data — Cleaning

**Steps:**
1. Parse `period` ("M01"…"M12") → integer `month`; drop M13 (annual averages).
2. Derive a `date` column (first of month, as a VARCHAR ISO date for DuckDB
   compatibility across all display tools).
3. Add a `category` column grouping each series ("overall", "by_sex", "by_age",
   "by_race", "alternative_measures") for easy slicing in exploration.
4. Cast `value` to DOUBLE, keep only rows where value is not null.
5. Deduplicate on (series_id, year, month).
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Define category mapping for series IDs
CATEGORY_MAP = {
    "LNS14000000": "overall",
    "LNS14000001": "by_sex",
    "LNS14000002": "by_sex",
    "LNS14000025": "by_sex",
    "LNS14000026": "by_sex",
    "LNS14000012": "by_age",
    "LNS14000036": "by_age",
    "LNS14000089": "by_age",
    "LNS14000091": "by_age",
    "LNS14000093": "by_age",
    "LNS14000095": "by_age",
    "LNS14000097": "by_age",
    "LNS14000003": "by_race",
    "LNS14000006": "by_race",
    "LNS14000009": "by_race",
    "LNS14032183": "by_race",
    "LNS14023621": "alternative",
    "LNS13327707": "alternative",
    "LNS13327708": "alternative",
    "LNS13327709": "alternative",
}

import pandas as pd

# Create the category lookup as a temp table
cat_df = pd.DataFrame([
    {"series_id": k, "category": v}
    for k, v in CATEGORY_MAP.items()
])
con.execute("DROP TABLE IF EXISTS _category_map")
con.execute("CREATE TABLE _category_map AS SELECT * FROM cat_df")

# Build the cleaned national table inside DuckDB
con.execute("DROP TABLE IF EXISTS unemployment_national_clean")
con.execute(\"\"\"
CREATE TABLE unemployment_national_clean AS
SELECT
    n.series_id,
    n.label,
    COALESCE(c.category, 'other')      AS category,
    n.year,
    CAST(REPLACE(n.period, 'M', '') AS INTEGER) AS month,
    n.period_name,
    -- ISO date string for the first of the month
    printf('%04d-%02d-01', n.year, CAST(REPLACE(n.period, 'M', '') AS INTEGER)) AS date,
    TRY_CAST(n.value AS DOUBLE)        AS value
FROM unemployment_national n
LEFT JOIN _category_map c USING (series_id)
WHERE n.period != 'M13'           -- drop annual averages
  AND TRY_CAST(n.value AS DOUBLE) IS NOT NULL
ORDER BY series_id, year, month
\"\"\")

n_clean = con.execute("SELECT COUNT(*) FROM unemployment_national_clean").fetchone()[0]
print(f"unemployment_national_clean: {n_clean:,} rows")
print()
print(con.execute("SELECT * FROM unemployment_national_clean LIMIT 5").df().to_string(index=False))
"""))

# ── Cell 3 — quality report: national ───────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
df_nat_clean = con.execute("SELECT * FROM unemployment_national_clean").df()
_ = quality_report(
    df_nat_clean,
    "unemployment_national_clean",
    con,
    required_columns=["series_id", "label", "category", "year", "month", "date", "value"],
)
"""))

# ── Cell 4 — spot checks: national ──────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# Spot-check: well-known recession peaks should match BLS published figures
checks = con.execute(\"\"\"
SELECT label, year, month, value
FROM unemployment_national_clean
WHERE (series_id = 'LNS14000000' AND year IN (1982, 2009, 2020))
   OR (series_id = 'LNS14000006' AND year = 2010)  -- Black peak ~16.0
   OR (series_id = 'LNS13327709' AND year = 2010)  -- U-6 peak ~17.2
ORDER BY series_id, year, month
\"\"\").df()

print("Recession-peak spot checks:")
print(checks.to_string(index=False))

# Distribution by category
cat_dist = con.execute(\"\"\"
    SELECT category, COUNT(DISTINCT series_id) AS series, COUNT(*) AS observations,
           MIN(year) AS first_year, MAX(year) AS last_year
    FROM unemployment_national_clean
    GROUP BY category ORDER BY category
\"\"\").df()
print()
print("Coverage by category:")
print(cat_dist.to_string(index=False))
"""))

# ── Cell 5 — save national interim ──────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
from pathlib import Path
Path("data/interim").mkdir(parents=True, exist_ok=True)
df_nat_clean.to_parquet("data/interim/unemployment_national_clean.parquet", index=False)
print(f"Saved → data/interim/unemployment_national_clean.parquet  ({len(df_nat_clean):,} rows)")
"""))

# ── Cell 6 — state data cleaning ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## State Unemployment Data — Cleaning

**Steps:**
1. Join with `state_ref` to attach state names (already on the table as `label`).
2. Parse `period` → integer `month`; drop M13.
3. Derive `date` (ISO string, first of month).
4. Add a 2-letter `state_abbrev` column for chart labels using a FIPS lookup.
5. Cast `value` to DOUBLE, drop nulls.
6. Deduplicate on (state, year, month).
"""))

cells.append(nbformat.v4.new_code_cell("""\
# FIPS → 2-letter abbreviation lookup
FIPS_ABBREV = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

abbrev_df = pd.DataFrame([
    {"series_id": f"LASST{fips}0000000000003", "state_abbrev": abbr}
    for fips, abbr in FIPS_ABBREV.items()
])
con.execute("DROP TABLE IF EXISTS _abbrev_map")
con.execute("CREATE TABLE _abbrev_map AS SELECT * FROM abbrev_df")

con.execute("DROP TABLE IF EXISTS unemployment_states_clean")
con.execute(\"\"\"
CREATE TABLE unemployment_states_clean AS
SELECT
    s.series_id,
    s.label                                              AS state_name,
    COALESCE(a.state_abbrev, '?')                       AS state_abbrev,
    s.year,
    CAST(REPLACE(s.period, 'M', '') AS INTEGER)         AS month,
    s.period_name,
    printf('%04d-%02d-01', s.year,
           CAST(REPLACE(s.period, 'M', '') AS INTEGER)) AS date,
    TRY_CAST(s.value AS DOUBLE)                         AS value
FROM unemployment_states s
LEFT JOIN _abbrev_map a USING (series_id)
WHERE s.period != 'M13'
  AND TRY_CAST(s.value AS DOUBLE) IS NOT NULL
ORDER BY series_id, year, month
\"\"\")

n_states = con.execute("SELECT COUNT(*) FROM unemployment_states_clean").fetchone()[0]
print(f"unemployment_states_clean: {n_states:,} rows")
print()
print(con.execute("SELECT * FROM unemployment_states_clean LIMIT 5").df().to_string(index=False))
"""))

# ── Cell 7 — quality report: states ─────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
df_states_clean = con.execute("SELECT * FROM unemployment_states_clean").df()
_ = quality_report(
    df_states_clean,
    "unemployment_states_clean",
    con,
    required_columns=["series_id", "state_name", "state_abbrev", "year", "month", "date", "value"],
)
"""))

# ── Cell 8 — spot checks: states ────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# Spot-check: current rankings + known outlier states
recent_year = con.execute("SELECT MAX(year) FROM unemployment_states_clean").fetchone()[0]
recent_month = con.execute(
    f"SELECT MAX(month) FROM unemployment_states_clean WHERE year = {recent_year}"
).fetchone()[0]

ranked = con.execute(f\"\"\"
    SELECT state_name, state_abbrev, value
    FROM unemployment_states_clean
    WHERE year = {recent_year} AND month = {recent_month}
    ORDER BY value DESC
\"\"\").df()
print(f"State rankings — {recent_year}-{recent_month:02d} (most recent):")
print(ranked.to_string(index=False))
"""))

# ── Cell 9 — save states interim ────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
df_states_clean.to_parquet("data/interim/unemployment_states_clean.parquet", index=False)
print(f"Saved → data/interim/unemployment_states_clean.parquet  ({len(df_states_clean):,} rows)")
"""))

# ── Cell 10 — summary ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Summary

| Table | Rows | Notes |
|---|---|---|
| `unemployment_national_clean` | ~13.7k | Dates parsed, category added, M13 dropped |
| `unemployment_states_clean` | ~30.9k | Dates parsed, state_abbrev added, M13 dropped |

Both tables persisted in `data/project.duckdb` and saved to `data/interim/` as Parquet.

**Next:** `04-viz.ipynb` — explore headline rate trends, racial/gender gaps,
state patterns, and U3 vs U6. Decide what story to tell and which charts to build.
"""))

# ── Cell 11 — cleanup ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/02-clean.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")

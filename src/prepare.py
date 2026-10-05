"""Sellable dataset preparation and export utilities.

Takes a processed DataFrame and packages it for sale/distribution:
  - Drops any PII columns listed in config.yaml
  - Exports to CSV, Excel, and/or Parquet
  - Generates a plain-text codebook (column descriptions)

Usage in a notebook:
    from src.prepare import package_dataset
    package_dataset(df, cfg, name="my_dataset", codebook={"col": "description"})
"""

from __future__ import annotations

import textwrap
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


# ---------------------------------------------------------------------------
# Chart-ready table builders (DuckDB-first)
# ---------------------------------------------------------------------------
#
# These build the shaped/aggregated per-chart tables that 04-viz CONSUMES.
# All aggregation runs inside DuckDB (no pandas transforms). The SQL here is
# byte-for-byte the logic that previously lived in 04-viz's build cell — moving
# "where the prep happens" into 03-prepare without changing a single value,
# filter, window, band threshold, or grouping. Each builder takes an open
# WRITABLE connection, drops+recreates its table, and returns the result frame
# (ordered) so the notebook can print/persist/export it.


def build_chart_headline(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 1 — headline U-3 rate, annual averages 1948–2026."""
    con.execute("DROP TABLE IF EXISTS chart_headline")
    con.execute("""
CREATE TABLE chart_headline AS
SELECT year, ROUND(AVG(value), 2) AS rate
FROM unemployment_national_clean
WHERE series_id = 'LNS14000000'
GROUP BY year ORDER BY year
""")
    return con.execute("SELECT * FROM chart_headline ORDER BY year").df()


def build_chart_u3_u6(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 2 — U-3 vs U-6, annual averages 1994–2026."""
    con.execute("DROP TABLE IF EXISTS chart_u3_u6")
    con.execute("""
CREATE TABLE chart_u3_u6 AS
SELECT
    year,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000000' THEN value END), 2) AS u3,
    ROUND(AVG(CASE WHEN series_id = 'LNS13327709' THEN value END), 2) AS u6
FROM unemployment_national_clean
WHERE series_id IN ('LNS14000000', 'LNS13327709')
  AND year >= 1994
GROUP BY year ORDER BY year
""")
    return con.execute("SELECT * FROM chart_u3_u6 ORDER BY year").df()


def build_chart_race(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 3 — unemployment by race/ethnicity, annual averages 1973–2026."""
    con.execute("DROP TABLE IF EXISTS chart_race")
    con.execute("""
CREATE TABLE chart_race AS
SELECT
    year,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000003' THEN value END), 2) AS white,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000009' THEN value END), 2) AS hispanic,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000006' THEN value END), 2) AS black
FROM unemployment_national_clean
WHERE series_id IN ('LNS14000003', 'LNS14000006', 'LNS14000009')
  AND year >= 1973
GROUP BY year ORDER BY year
""")
    return con.execute("SELECT * FROM chart_race ORDER BY year").df()


def build_chart_youth(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 4 — teens (16–19) vs adults 20+, annual averages 1948–2026.

    The adults line uses the real combined-sex adult total, BLS CPS series
    LNS14000024 (Unemployment Rate, 20 years & over, seasonally adjusted) — NOT
    the overall 16+ rate (which includes teens) and NOT a men/women mean.
    """
    con.execute("DROP TABLE IF EXISTS chart_youth")
    con.execute("""
CREATE TABLE chart_youth AS
SELECT
    year,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000024' THEN value END), 2) AS adults_20plus,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000012' THEN value END), 2) AS youth_16_19
FROM unemployment_national_clean
WHERE series_id IN ('LNS14000024', 'LNS14000012')
GROUP BY year ORDER BY year
""")
    return con.execute("SELECT * FROM chart_youth ORDER BY year").df()


def build_chart_state_map(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 5 — per-state trailing-12-month average rate.

    Averages each state's rate over the 12 most recent DISTINCT (year, month)
    periods available (distinct-period window survives the missing 2025-10 gap).
    The geo merge + banding + render stay in 04-viz (presentation); this is the
    chart-ready per-state dataset.
    """
    con.execute("DROP TABLE IF EXISTS chart_state_map")
    con.execute("""
CREATE TABLE chart_state_map AS
WITH top12 AS (
    SELECT DISTINCT (year*12 + month) AS idx
    FROM unemployment_states_clean
    ORDER BY idx DESC
    LIMIT 12
)
SELECT
    s.state_name,
    s.state_abbrev,
    ROUND(AVG(s.value), 2) AS rate,
    COUNT(*)              AS n_months
FROM unemployment_states_clean s
WHERE (s.year*12 + s.month) IN (SELECT idx FROM top12)
GROUP BY s.state_name, s.state_abbrev
ORDER BY rate DESC
""")
    return con.execute("SELECT * FROM chart_state_map ORDER BY rate DESC").df()


def state_map_window_label(con: duckdb.DuckDBPyConnection) -> str:
    """Return the trailing-12 window label string ('YYYY-MM .. YYYY-MM').

    Diagnostic only (does not affect any chart value) — used for a build
    confirmation print in 03-prepare.
    """
    win = con.execute("""
WITH top12 AS (
    SELECT DISTINCT (year*12 + month) AS idx
    FROM unemployment_states_clean ORDER BY idx DESC LIMIT 12
)
SELECT MIN(idx), MAX(idx) FROM top12
""").fetchone()

    def _lbl(idx: int) -> str:
        y, m = divmod(idx - 1, 12)
        return f"{y}-{m+1:02d}"

    return f"{_lbl(win[0])} .. {_lbl(win[1])}"


def build_chart_states_selected(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 6 — selected states (CA/TX/FL/NY/MI/MA) annual averages."""
    con.execute("DROP TABLE IF EXISTS chart_states_selected")
    con.execute("""
CREATE TABLE chart_states_selected AS
SELECT
    year,
    ROUND(AVG(CASE WHEN state_name = 'California'    THEN value END), 2) AS california,
    ROUND(AVG(CASE WHEN state_name = 'Texas'         THEN value END), 2) AS texas,
    ROUND(AVG(CASE WHEN state_name = 'Florida'       THEN value END), 2) AS florida,
    ROUND(AVG(CASE WHEN state_name = 'New York'      THEN value END), 2) AS new_york,
    ROUND(AVG(CASE WHEN state_name = 'Michigan'      THEN value END), 2) AS michigan,
    ROUND(AVG(CASE WHEN state_name = 'Massachusetts' THEN value END), 2) AS massachusetts
FROM unemployment_states_clean
WHERE state_name IN ('California', 'Texas', 'Florida', 'New York', 'Michigan', 'Massachusetts')
GROUP BY year ORDER BY year
""")
    return con.execute("SELECT * FROM chart_states_selected ORDER BY year").df()


def build_chart_edu_race(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Chart 7 — race gap by education level, 25+, 2024 (White vs Black)."""
    con.execute("DROP TABLE IF EXISTS chart_edu_race")
    con.execute("""
CREATE TABLE chart_edu_race AS
SELECT year, education_level, education_order, race, unemployment_rate
FROM unemployment_by_education_race
WHERE year = 2024 AND race IN ('White', 'Black')
ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END
""")
    return con.execute(
        "SELECT * FROM chart_edu_race "
        "ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END"
    ).df()


def build_export_national_annual(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Analysis-ready national annual panel — the sellable national dataset.

    Joins the per-chart national annual tables on `year` into one tidy table:
    year + u3 + u6 + white + black + hispanic + adults_20plus + youth_16_19.
    This is the dataset the national line charts (1–4) are cut from. Built from
    the already-created chart_* tables (so values are identical by construction).
    A FULL OUTER JOIN keeps every year present in any component series.
    """
    return con.execute("""
SELECT
    COALESCE(h.year, u.year, r.year, yth.year) AS year,
    h.rate            AS u3_rate,
    u.u6              AS u6_rate,
    r.white           AS white_rate,
    r.black           AS black_rate,
    r.hispanic        AS hispanic_rate,
    yth.adults_20plus AS adults_20plus_rate,
    yth.youth_16_19   AS youth_16_19_rate
FROM            chart_headline        h
FULL OUTER JOIN chart_u3_u6           u   ON u.year   = h.year
FULL OUTER JOIN chart_race            r   ON r.year   = COALESCE(h.year, u.year)
FULL OUTER JOIN chart_youth           yth ON yth.year = COALESCE(h.year, u.year, r.year)
ORDER BY year
""").df()


# ---------------------------------------------------------------------------
# PII stripping
# ---------------------------------------------------------------------------

def strip_pii(df: pd.DataFrame, cfg: dict[str, Any]) -> pd.DataFrame:
    """Drop columns listed under export.strip_pii_columns in config.yaml."""
    cols_to_drop = cfg.get("export", {}).get("strip_pii_columns", [])
    if cols_to_drop:
        existing = [c for c in cols_to_drop if c in df.columns]
        if existing:
            df = df.drop(columns=existing)
            print(f"Stripped PII columns: {existing}")
    return df


# ---------------------------------------------------------------------------
# Codebook
# ---------------------------------------------------------------------------

def build_codebook(
    df: pd.DataFrame,
    descriptions: dict[str, str] | None = None,
    project_name: str = "",
    notes: str = "",
) -> str:
    """Generate a plain-text codebook for the dataset.

    Args:
        df:           The export-ready DataFrame.
        descriptions: Dict mapping column name → human-readable description.
                      Columns not in the dict get a placeholder.
        project_name: Printed in the header.
        notes:        Free-text notes appended at the bottom (source info, license, etc.).

    Returns:
        Codebook as a string (written to a .md file by package_dataset).
    """
    descriptions = descriptions or {}
    today = date.today().isoformat()

    lines = [
        f"# {project_name} — Dataset Codebook",
        f"Generated: {today}",
        "",
        "## Columns",
        "",
    ]

    for col in df.columns:
        dtype = str(df[col].dtype)
        desc = descriptions.get(col, "_No description provided._")
        non_null = df[col].notna().sum()
        total = len(df)
        lines.append(f"### `{col}`")
        lines.append(f"- **Type**: `{dtype}`")
        lines.append(f"- **Non-null**: {non_null:,} / {total:,} ({non_null/total:.1%})")
        lines.append(f"- **Description**: {desc}")
        lines.append("")

    if notes:
        lines += ["## Notes", "", textwrap.dedent(notes).strip(), ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def package_dataset(
    df: pd.DataFrame,
    cfg: dict[str, Any],
    name: str,
    codebook: dict[str, str] | None = None,
    notes: str = "",
    formats: list[str] | None = None,
) -> dict[str, Path]:
    """Strip PII, export to configured formats, and write a codebook.

    Args:
        df:       Processed DataFrame ready for packaging.
        cfg:      Loaded config dict.
        name:     Base filename (no extension).
        codebook: Column description dict passed to build_codebook().
        notes:    Free-text appended to the codebook (source, license, etc.).
        formats:  Override config export.formats. Supported: csv, xlsx, parquet.

    Returns:
        Dict of {format: Path} for every file written.
    """
    df = strip_pii(df, cfg)

    export_dir = Path(cfg["paths"]["export"])
    export_dir.mkdir(parents=True, exist_ok=True)

    export_cfg = cfg.get("export", {})
    active_formats = formats or export_cfg.get("formats", ["csv"])
    include_codebook = export_cfg.get("include_codebook", True)
    project_name = cfg.get("project_name", name)

    written: dict[str, Path] = {}

    if "csv" in active_formats:
        p = export_dir / f"{name}.csv"
        df.to_csv(p, index=False, encoding=cfg["settings"]["encoding"])
        written["csv"] = p
        print(f"Exported CSV     → {p}")

    if "xlsx" in active_formats:
        p = export_dir / f"{name}.xlsx"
        with pd.ExcelWriter(p, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="data")
        written["xlsx"] = p
        print(f"Exported Excel   → {p}")

    if "parquet" in active_formats:
        p = export_dir / f"{name}.parquet"
        df.to_parquet(p, index=False, engine=cfg["settings"]["parquet_engine"])
        written["parquet"] = p
        print(f"Exported Parquet → {p}")

    if include_codebook:
        cb_text = build_codebook(df, descriptions=codebook, project_name=project_name, notes=notes)
        cb_path = export_dir / f"{name}_codebook.md"
        cb_path.write_text(cb_text, encoding="utf-8")
        written["codebook"] = cb_path
        print(f"Wrote codebook   → {cb_path}")

    print(f"\n✓  Package complete: {len(df):,} rows × {len(df.columns)} columns")
    return written


# ---------------------------------------------------------------------------
# Quick summary helpers (useful before packaging)
# ---------------------------------------------------------------------------

def value_counts_all(df: pd.DataFrame, top_n: int = 10) -> None:
    """Print top-N value counts for every column — quick sanity check."""
    for col in df.columns:
        print(f"\n── {col} ──")
        print(df[col].value_counts(dropna=False).head(top_n).to_string())


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Return describe() output for numeric columns only, transposed for readability."""
    return df.select_dtypes("number").describe().T.round(2)

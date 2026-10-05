#!/usr/bin/env python
"""Reproduce the unemployment published datasets from raw sources.

This is the serious-tier reproducibility entrypoint: a single command that goes
from the raw BLS files in ``data/raw/`` all the way to the three published
exports in ``export/`` — the same CSV + codebook files the release is built on.
It runs the EXACT ``src/`` logic the notebooks use, in the documented pipeline
order (ingest → clean → prepare), WITHOUT executing the notebooks.

What it does, in order:
  1. INGEST  — ensure the raw files are present in ``data/raw/``:
                 - ``bls_api_data.parquet``   (national CPS LN series, BLS API)
                 - ``bls_api_states.parquet`` (state LAUS LA series, BLS API)
                 - ``cpsaat07_2024.pdf``      (CPS annual table, education×race)
               If any is missing and downloads are allowed, it fetches it
               (national+state via the BLS Public Data API; cpsaat07 via the
               bls.gov /cps/ PDF). With ``--no-download`` it fails instead of
               hitting the network.
  2. LOAD    — load the raw parquet files into DuckDB as ``unemployment_national``
               and ``unemployment_states`` (with human labels), and register
               both in ``_sources``.
  3. CLEAN   — build the interim ``*_clean`` tables with the same DuckDB SQL as
               ``02-clean`` (national + state), and parse the cpsaat07 PDF into
               ``unemployment_by_education_race`` (via ``parse_cpsaat07``).
  4. PREPARE — build the per-chart ``chart_*`` tables with ``src/prepare.py`` in
               the same order as ``03-prepare``, then package the THREE exports
               (CSV + Excel + Parquet + codebook) with the same names/codebooks.
  5. VERIFY  — compare each regenerated export CSV to the CURRENT published
               ``export/*.csv`` value-for-value and exit non-zero on any drift.

CACHING BEHAVIOR
----------------
Ingest hits the BLS API and downloads the cpsaat07 PDF only when a raw file is
MISSING. If the three raw files already exist in ``data/raw/`` they are reused
as-is and NO network request is made — ``--no-download`` enforces this (it fails
with guidance rather than fetching). For this project's committed state all
three raw files are present, so ``--no-download`` reproduces the whole pipeline
offline.

SAFE VERIFICATION RUN
---------------------
To verify reproducibility WITHOUT touching the committed DB/exports, point the
script at a scratch DB + scratch export dir; it then compares the scratch output
against the real ``export/*.csv``:

    /opt/anaconda3/envs/data_projects/bin/python scripts/reproduce.py \\
        --no-download --db /tmp/unemp_repro.duckdb --export-dir /tmp/unemp_repro_export

Run WITHOUT ``--db``/``--export-dir`` to actually rebuild the real artifacts
(the VERIFY step is then trivially satisfied, since it rewrote the files it
compares against).

Usage:
    python scripts/reproduce.py                         # full run → real DB/export
    python scripts/reproduce.py --no-download           # offline (fail if raw missing)
    python scripts/reproduce.py --db /tmp/x.duckdb --export-dir /tmp/exp   # scratch verify
    python scripts/reproduce.py --formats csv           # only write the CSV (+ codebook)

Run interpreter: the ``data_projects`` conda env (has duckdb + pandas + pyarrow +
pdfplumber + openpyxl). The project ``.venv`` (Py3.14) is NOT suitable.

Prerequisites:
  - Python 3.11+ with the packages in ``requirements.txt`` (+ pdfplumber for the
    cpsaat07 parse).
  - Network access only on a first run with missing raw files; cached runs are
    fully offline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# --- make the project importable regardless of where this is invoked from ----
PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from src.ingest import (  # noqa: E402
    load_config,
    ingest_bls_api,
    get_all_series_ids,
    get_series_labels,
    fetch_bls_cps_table,
    parse_cpsaat07,
    raw_path,
    KEY_UNEMPLOYMENT_SERIES,
    ALTERNATIVE_MEASURES_SERIES,
    STATE_UNEMPLOYMENT_SERIES,
)
from src.clean_quality import (  # noqa: E402
    get_connection,
    register_source,
)
from src.prepare import (  # noqa: E402
    build_chart_headline,
    build_chart_u3_u6,
    build_chart_race,
    build_chart_youth,
    build_chart_state_map,
    build_chart_states_selected,
    build_chart_edu_race,
    build_export_national_annual,
    package_dataset,
)

# --- constants mirrored from the notebooks -----------------------------------
CPSAAT07_YEAR = 2024
CPSAAT07_URL = f"https://www.bls.gov/cps/data/aa{CPSAAT07_YEAR}/cpsaat07.pdf"

# 02-clean cell 1 — series_id → category.
CATEGORY_MAP = {
    "LNS14000000": "overall",
    "LNS14000024": "overall",
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

# 02-clean cell 5 — FIPS → 2-letter abbreviation (for the state series_ids).
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

# 02-clean cell 9 — education-tier ordering (least → most educated).
EDU_ORDER = [
    "Less than high school",
    "High school, no college",
    "Some college or associate degree",
    "Bachelor's degree and higher",
]

# Export identities + codebooks/notes — copied verbatim from 03-prepare so the
# regenerated package is byte-identical to the published one.
NATIONAL_NAME = "unemployment_national_annual_v1"
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
NATIONAL_NOTES = """
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
"""

STATES_NAME = "unemployment_states_trailing12_v1"
STATES_CB = {
    "state_name":   "State (or District of Columbia) name.",
    "state_abbrev": "Two-letter USPS state abbreviation (DC for the District of Columbia).",
    "rate":         "Average seasonally-adjusted U-3 unemployment rate (%) over the trailing 12 most recent distinct monthly periods (Jul 2025 - Jul 2026).",
    "n_months":     "Number of monthly observations in the average (12 for all states except Wyoming, which reports through Dec 2025 = 5 months).",
}
STATES_NOTES = """
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
"""

EDU_NAME = "unemployment_by_education_race_2024_v1"
EDU_CB = {
    "year":              "Calendar year of the annual average (2024).",
    "education_level":   "Highest education tier: 'Less than high school', 'High school, no college', 'Some college or associate degree', or \"Bachelor's degree and higher\".",
    "education_order":   "Integer sort key for education_level (lowest to highest attainment).",
    "race":              "Race group: 'White' or 'Black'.",
    "unemployment_rate": "Annual-average unemployment rate (%), not seasonally adjusted, workers 25 and over, for the race x education cell. BLS CPS table cpsaat07.",
}
EDU_NOTES = """
    Source: U.S. Bureau of Labor Statistics, Current Population Survey (CPS),
    annual table cpsaat07. License: Public domain (U.S. Government work).
    Measure: annual-average unemployment rate, population 25 years and over, NOT
    seasonally adjusted. This is a DIFFERENT grain from the monthly, seasonally
    adjusted, 16+ national series in the other exports; do not conflate them.
    Interpretation: the Black/White gap holds at every education level, which is
    why economists attribute the ~2:1 gap mainly to labor-market discrimination
    and occupational segregation rather than education (EPI 2015, 2019; Quillian
    et al. PNAS 2017; Fed FEDS 2017-071). Retrieved 2026-09-28.
"""


def _rule(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


# ---------------------------------------------------------------------------
# 1. INGEST — ensure raw files exist (cached-first)
# ---------------------------------------------------------------------------

def step_ingest(cfg: dict, allow_download: bool) -> None:
    """Ensure national + state parquet and the cpsaat07 PDF exist in data/raw/."""
    nat_pq = raw_path(cfg, "bls_api_data.parquet")
    st_pq = raw_path(cfg, "bls_api_states.parquet")
    pdf = raw_path(cfg, f"cpsaat07_{CPSAAT07_YEAR}.pdf")

    present = {p.name: p.exists() for p in (nat_pq, st_pq, pdf)}
    if all(present.values()):
        print("Raw files present (cached) — no network request:")
        for p in (nat_pq, st_pq, pdf):
            print(f"  ✓ {p.name}  ({p.stat().st_size:,} bytes)")
        return

    missing = [name for name, ok in present.items() if not ok]
    if not allow_download:
        raise SystemExit(
            "Missing raw files and --no-download was set: "
            f"{missing}. Populate data/raw/ from the BLS sources documented in "
            "SOURCES.md (bls_api_data.parquet national CPS LN series, "
            "bls_api_states.parquet state LAUS LA series, cpsaat07_"
            f"{CPSAAT07_YEAR}.pdf), or re-run without --no-download."
        )

    print(f"Downloading missing raw files: {missing} (polite rate limit applies)…")

    # The BLS API returns both LN (national) and LA (state) series; split by id
    # prefix into the two parquet files 01/02 consume.
    if not nat_pq.exists() or not st_pq.exists():
        combined = ingest_bls_api(
            cfg, get_all_series_ids(), start_year=1948, end_year=2026
        )
        is_state = combined["series_id"].str.startswith("LASST")
        if not nat_pq.exists():
            nat = (combined[~is_state]
                   .sort_values(["series_id", "year", "period"])
                   .reset_index(drop=True))
            nat.to_parquet(nat_pq, index=False)
            print(f"  wrote {nat_pq.name}: {len(nat):,} national rows")
        if not st_pq.exists():
            st = (combined[is_state]
                  .sort_values(["series_id", "year", "period"])
                  .reset_index(drop=True))
            st["label"] = st["series_id"].map(STATE_UNEMPLOYMENT_SERIES)
            st.to_parquet(st_pq, index=False)
            print(f"  wrote {st_pq.name}: {len(st):,} state rows")

    if not pdf.exists():
        fetch_bls_cps_table(CPSAAT07_URL, pdf)
        print(f"  wrote {pdf.name}: {pdf.stat().st_size:,} bytes")


# ---------------------------------------------------------------------------
# 2. LOAD — raw parquet files into DuckDB
# ---------------------------------------------------------------------------

def step_load_raw(cfg: dict, con) -> None:
    """Load national + state raw parquet into DuckDB with human labels."""
    nat_pq = raw_path(cfg, "bls_api_data.parquet")
    st_pq = raw_path(cfg, "bls_api_states.parquet")

    # National (01-ingest cells 1-3): label via KEY + ALTERNATIVE maps.
    df_national = pd.read_parquet(nat_pq)
    df_national["label"] = df_national["series_id"].map(
        {**KEY_UNEMPLOYMENT_SERIES, **ALTERNATIVE_MEASURES_SERIES}
    )
    con.register("df_national", df_national)
    con.execute("DROP TABLE IF EXISTS unemployment_national")
    con.execute(
        "CREATE TABLE unemployment_national AS "
        "SELECT * FROM df_national ORDER BY series_id, year, period"
    )
    con.unregister("df_national")
    n_nat = con.execute("SELECT COUNT(*) FROM unemployment_national").fetchone()[0]
    print(f"unemployment_national: {n_nat:,} rows loaded")
    register_source(
        con, "unemployment_national",
        name="BLS CPS National Unemployment (demographics)",
        url="https://api.bls.gov/publicAPI/v2/timeseries/data/",
        license="Public domain (U.S. government work)",
        notes=(
            "Seasonally adjusted monthly unemployment rates by age/sex/race + U3-U6 "
            "alternative measures. 18 of 20 requested series returned data."
        ),
        methodology=(
            "BLS CPS household survey, ~60,000 households/month. U-3 = official "
            "unemployment rate; U-6 = U-3 + marginally attached + involuntary "
            "part-timers. All series seasonally adjusted via X-13ARIMA-SEATS."
        ),
        series_breaks=(
            "U-4/U-5/U-6 begin 1994. Black series 1972, Hispanic 1973, Asian 2003, "
            "White 1954."
        ),
    )

    # State (01-ingest cell 5 reads it from the DB in-notebook; here we LOAD it
    # from the cached raw parquet so a fresh scratch DB has it too).
    df_states = pd.read_parquet(st_pq)
    if "label" not in df_states.columns or df_states["label"].isna().all():
        df_states["label"] = df_states["series_id"].map(STATE_UNEMPLOYMENT_SERIES)
    con.register("df_states", df_states)
    con.execute("DROP TABLE IF EXISTS unemployment_states")
    con.execute(
        "CREATE TABLE unemployment_states AS "
        "SELECT * FROM df_states ORDER BY series_id, year, period"
    )
    con.unregister("df_states")
    n_st = con.execute("SELECT COUNT(*) FROM unemployment_states").fetchone()[0]
    print(f"unemployment_states: {n_st:,} rows loaded")
    register_source(
        con, "unemployment_states",
        name="BLS LAUS State Unemployment",
        url="https://api.bls.gov/publicAPI/v2/timeseries/data/",
        license="Public domain (U.S. government work)",
        notes="Seasonally adjusted monthly state unemployment rates (LAUS LASST series).",
        methodology="BLS Local Area Unemployment Statistics, model-based seasonally-adjusted state rate.",
        series_breaks="LAUS revised model-based estimation in 2021.",
    )


# ---------------------------------------------------------------------------
# 3. CLEAN — build interim *_clean tables (same SQL as 02-clean)
# ---------------------------------------------------------------------------

def step_clean(cfg: dict, con) -> None:
    """Replicate 02-clean: national + state clean tables + education×race."""
    # National (02-clean cell 1).
    cat_df = pd.DataFrame(
        [{"series_id": k, "category": v} for k, v in CATEGORY_MAP.items()]
    )
    con.register("cat_df", cat_df)
    con.execute("DROP TABLE IF EXISTS _category_map")
    con.execute("CREATE TABLE _category_map AS SELECT * FROM cat_df")
    con.unregister("cat_df")
    con.execute("DROP TABLE IF EXISTS unemployment_national_clean")
    con.execute("""
CREATE TABLE unemployment_national_clean AS
SELECT
    n.series_id,
    n.label,
    COALESCE(c.category, 'other')      AS category,
    n.year,
    CAST(REPLACE(n.period, 'M', '') AS INTEGER) AS month,
    n.period_name,
    printf('%04d-%02d-01', n.year, CAST(REPLACE(n.period, 'M', '') AS INTEGER)) AS date,
    TRY_CAST(n.value AS DOUBLE)        AS value
FROM unemployment_national n
LEFT JOIN _category_map c USING (series_id)
WHERE n.period != 'M13'
  AND TRY_CAST(n.value AS DOUBLE) IS NOT NULL
ORDER BY series_id, year, month
""")
    n_nat = con.execute("SELECT COUNT(*) FROM unemployment_national_clean").fetchone()[0]
    print(f"unemployment_national_clean: {n_nat:,} rows")

    # State (02-clean cell 5).
    abbrev_df = pd.DataFrame([
        {"series_id": f"LASST{fips}0000000000003", "state_abbrev": abbr}
        for fips, abbr in FIPS_ABBREV.items()
    ])
    con.register("abbrev_df", abbrev_df)
    con.execute("DROP TABLE IF EXISTS _abbrev_map")
    con.execute("CREATE TABLE _abbrev_map AS SELECT * FROM abbrev_df")
    con.unregister("abbrev_df")
    con.execute("DROP TABLE IF EXISTS unemployment_states_clean")
    con.execute("""
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
""")
    n_st = con.execute("SELECT COUNT(*) FROM unemployment_states_clean").fetchone()[0]
    print(f"unemployment_states_clean: {n_st:,} rows")

    # Education×race from the cpsaat07 PDF (02-clean cell 9).
    pdf = raw_path(cfg, f"cpsaat07_{CPSAAT07_YEAR}.pdf")
    if not pdf.exists():
        raise SystemExit(f"missing raw PDF {pdf} — run ingest first")
    df_edu_race = parse_cpsaat07(pdf, CPSAAT07_YEAR)
    order_map = {lvl: i for i, lvl in enumerate(EDU_ORDER)}
    df_edu_race["education_order"] = df_edu_race["education_level"].map(order_map)
    con.register("df_edu_race", df_edu_race)
    con.execute("DROP TABLE IF EXISTS unemployment_by_education_race")
    con.execute("""
CREATE TABLE unemployment_by_education_race AS
SELECT
    CAST(year AS INTEGER)           AS year,
    race,
    education_level,
    CAST(education_order AS INTEGER) AS education_order,
    CAST(unemployment_rate AS DOUBLE) AS unemployment_rate
FROM df_edu_race
ORDER BY year, education_order, race
""")
    con.unregister("df_edu_race")
    # QC (same asserts as 02-clean cell 9).
    n_rows = con.execute("SELECT COUNT(*) FROM unemployment_by_education_race").fetchone()[0]
    n_null = con.execute(
        "SELECT COUNT(*) FROM unemployment_by_education_race WHERE unemployment_rate IS NULL"
    ).fetchone()[0]
    tiers = {r[0] for r in con.execute(
        "SELECT DISTINCT education_level FROM unemployment_by_education_race"
    ).fetchall()}
    races = {r[0] for r in con.execute(
        "SELECT DISTINCT race FROM unemployment_by_education_race"
    ).fetchall()}
    assert n_rows == 8, f"expected 8 rows (2 races × 4 tiers), got {n_rows}"
    assert n_null == 0, f"nulls in unemployment_rate: {n_null}"
    assert tiers == set(EDU_ORDER), f"unexpected education tiers: {tiers}"
    assert races == {"White", "Black"}, f"unexpected races: {races}"
    register_source(
        con, "unemployment_by_education_race",
        name="BLS CPS — Unemployment by Educational Attainment and Race (annual, 25+)",
        url=CPSAAT07_URL,
        license="Public domain (U.S. government work)",
        notes=(
            "Annual table cpsaat07, parsed from PDF with pdfplumber by word position. "
            "Race × education cross-tab of the U-3 unemployment rate; White + Black, "
            "four education tiers."
        ),
        methodology=(
            "BLS CPS household survey averaged to annual figures. U-3 unemployment "
            "rate restricted to the 25-and-over population, reported as an ANNUAL "
            "AVERAGE, NOT seasonally adjusted."
        ),
        series_breaks=(
            "DIFFERENT GRAIN from charts 1-6: annual / 25+ / NSA (cpsaat07) vs the "
            "monthly seasonally-adjusted 16+ LN series used elsewhere."
        ),
        retrieved="2026-10-05",
    )
    print(f"unemployment_by_education_race: {n_rows} rows, {n_null} nulls — QC OK")


# ---------------------------------------------------------------------------
# 4. PREPARE — build chart tables + package exports (same as 03-prepare)
# ---------------------------------------------------------------------------

def step_prepare(cfg: dict, con, formats: list[str]) -> dict[str, int]:
    """Build the chart_* tables and package the three exports."""
    build_chart_headline(con)
    build_chart_u3_u6(con)
    build_chart_race(con)
    build_chart_youth(con)
    build_chart_state_map(con)
    build_chart_states_selected(con)
    build_chart_edu_race(con)

    # 1. National annual panel.
    national_annual = build_export_national_annual(con)
    package_dataset(national_annual, cfg, name=NATIONAL_NAME,
                    codebook=NATIONAL_CB, notes=NATIONAL_NOTES, formats=formats)

    # 2. State trailing-12.
    states_export = con.execute(
        "SELECT state_name, state_abbrev, rate, n_months FROM chart_state_map ORDER BY rate DESC"
    ).df()
    package_dataset(states_export, cfg, name=STATES_NAME,
                    codebook=STATES_CB, notes=STATES_NOTES, formats=formats)

    # 3. Education × race.
    edu_export = con.execute(
        "SELECT year, education_level, education_order, race, unemployment_rate "
        "FROM chart_edu_race "
        "ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END"
    ).df()
    package_dataset(edu_export, cfg, name=EDU_NAME,
                    codebook=EDU_CB, notes=EDU_NOTES, formats=formats)

    return {
        NATIONAL_NAME: len(national_annual),
        STATES_NAME: len(states_export),
        EDU_NAME: len(edu_export),
    }


# ---------------------------------------------------------------------------
# 5. VERIFY — regenerated export == published export, value-for-value
# ---------------------------------------------------------------------------

def _normalize(df: pd.DataFrame, float_round: int = 4) -> pd.DataFrame:
    """int32/int64- and NaN-tolerant comparison frame (see validate_charts.py)."""
    out = df.copy().reset_index(drop=True)
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(float_round)
    return out.astype(object).where(out.notna(), "<NA>").astype(str)


def step_verify(cfg: dict) -> bool:
    """Compare each regenerated export CSV to the published export/*.csv."""
    regen_dir = Path(cfg["paths"]["export"])
    published_dir = PROJECT / "export"
    all_ok = True
    for name in (NATIONAL_NAME, STATES_NAME, EDU_NAME):
        regen = regen_dir / f"{name}.csv"
        published = published_dir / f"{name}.csv"
        if not regen.exists():
            print(f"  FAIL  {name}: regenerated CSV not found at {regen}")
            all_ok = False
            continue
        if not published.exists():
            print(f"  FAIL  {name}: published CSV not found at {published}")
            all_ok = False
            continue
        a = _normalize(pd.read_csv(regen))
        b = _normalize(pd.read_csv(published))
        same_cols = list(a.columns) == list(b.columns)
        same_shape = a.shape == b.shape
        # Order-insensitive content comparison: the published exports have no
        # deterministic secondary sort on tied `rate` values (e.g. GA/IN both
        # 3.44), so a fresh build may tie-break the other way. That is NOT drift
        # — the set of rows and every value is identical. Sort both frames by
        # all columns before comparing so a tie-order flip doesn't false-fail.
        if same_cols and same_shape:
            a_sorted = a.sort_values(list(a.columns)).reset_index(drop=True)
            b_sorted = b.sort_values(list(b.columns)).reset_index(drop=True)
            equal = a_sorted.equals(b_sorted)
        else:
            equal = False
        if equal:
            print(f"  PASS  {name}: regenerated == published ({len(a)} rows)")
        else:
            print(f"  FAIL  {name}: regenerated DIFFERS from published "
                  f"(regen {a.shape} vs published {b.shape})")
            all_ok = False
    return all_ok


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Reproduce the unemployment published exports from raw sources."
    )
    ap.add_argument("--no-download", action="store_true",
                    help="Do not fetch missing raw files; fail instead (reuse data/raw cache).")
    ap.add_argument("--db", default=None,
                    help="DuckDB file to build into (default: config duckdb_file).")
    ap.add_argument("--export-dir", default=None,
                    help="Directory to write the export into (default: config export path).")
    ap.add_argument("--formats", nargs="+", default=None,
                    help="Export formats to write (default: config export.formats).")
    args = ap.parse_args()

    cfg = load_config(str(PROJECT / "config.yaml"))
    if args.db:
        cfg["settings"]["duckdb_file"] = args.db
    if args.export_dir:
        cfg["paths"]["export"] = args.export_dir
    formats = args.formats or cfg.get("export", {}).get("formats", ["csv"])

    scratch = bool(args.db or args.export_dir)

    _rule("unemployment · reproduce  (raw → export)")
    print(f"DuckDB : {cfg['settings']['duckdb_file']}")
    print(f"Export : {cfg['paths']['export']}  (formats: {', '.join(formats)})")
    if scratch:
        print("Mode   : SCRATCH — VERIFY compares scratch output vs the real export/*.csv")
    else:
        print("Mode   : IN-PLACE — rebuilding the real DB/export (VERIFY re-reads them)")

    _rule("1/5  INGEST — ensure raw files present")
    step_ingest(cfg, allow_download=not args.no_download)

    con = get_connection(cfg)
    try:
        _rule("2/5  LOAD — raw parquet → DuckDB")
        step_load_raw(cfg, con)

        _rule("3/5  CLEAN — build interim *_clean tables")
        step_clean(cfg, con)

        _rule("4/5  PREPARE — chart tables + package exports")
        counts = step_prepare(cfg, con, formats)
    finally:
        con.close()

    _rule("5/5  VERIFY — regenerated export == published export")
    ok = step_verify(cfg)

    _rule("DONE")
    for name, n in counts.items():
        print(f"  reproduced {name}: {n} rows")
    if "csv" not in formats:
        print("  NOTE: --formats did not include csv; VERIFY compares the CSV, so "
              "run with csv in --formats for a meaningful parity check.")
    if ok:
        print("\nParity: all regenerated exports match the published export/*.csv.")
        return 0
    print("\nParity: FAILURE — a regenerated export drifted from the published CSV.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

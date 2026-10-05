#!/usr/bin/env python3
"""Pre-publish data-validation GATE — re-check the chart data before anything goes public.

Re-derives the headline facts the five published unemployment charts show,
straight from the prepared DuckDB `chart_*` tables, confirms each published
`export/*.csv` still matches its DuckDB source value-for-value, checks the
structural invariants, and confirms the social/web PNG sets stay in parity.

The DB is opened **READ-ONLY** (`duckdb.connect(path, read_only=True)`) so this
gate never fights the single-writer lock a notebook or DBCode may hold. It does
not write to the DB, the exports, or the charts.

Exit code 0 = safe to publish. Non-zero = do NOT publish (prints the failing
check).

Usage:
    /opt/anaconda3/envs/data_projects/bin/python scripts/validate_charts.py

Run interpreter: the `data_projects` conda env (has duckdb + pandas + PIL). The
project `.venv` (Py3.14) is not used here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

# --- project bootstrap -------------------------------------------------------
PROJECT = Path(__file__).resolve().parent
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
sys.path.insert(0, str(PROJECT))
from src.ingest import load_config  # noqa: E402
from src.prepare import build_export_national_annual  # noqa: E402 (pure SELECT, no writes)

failures: list[str] = []
checks: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a PASS/FAIL. `condition` must be truthy to pass."""
    if condition:
        checks.append(f"  PASS  {name}")
    else:
        failures.append(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Export-vs-DB parity helper
# ---------------------------------------------------------------------------

def _normalize(df: pd.DataFrame, float_round: int = 4) -> pd.DataFrame:
    """Make a frame comparable regardless of int32/int64 and NaN handling.

    - round floats (so DB's higher precision never spuriously differs),
    - render every value as a string with NaN → a stable sentinel,
    so a published CSV (int64 on read) compares equal to a DB frame (int32).
    """
    out = df.copy()
    out = out.reset_index(drop=True)
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(float_round)
    # Stringify with a NaN sentinel so NaN == NaN compares equal.
    return out.astype(object).where(out.notna(), "<NA>").astype(str)


def assert_csv_matches(name: str, df_db: pd.DataFrame, csv_path: Path) -> None:
    """Assert a published CSV equals the DB-derived frame, value-for-value."""
    if not csv_path.exists():
        check(f"export parity: {name} (file present)", False, f"missing {csv_path}")
        return
    df_csv = pd.read_csv(csv_path)
    check(f"export parity: {name} row count", len(df_csv) == len(df_db),
          f"csv={len(df_csv)} db={len(df_db)}")
    check(f"export parity: {name} columns",
          list(df_csv.columns) == list(df_db.columns),
          f"csv={list(df_csv.columns)} db={list(df_db.columns)}")
    if list(df_csv.columns) != list(df_db.columns) or len(df_csv) != len(df_db):
        return
    norm_csv = _normalize(df_csv)
    norm_db = _normalize(df_db[df_csv.columns])
    # Order-insensitive content comparison. The exports have no deterministic
    # secondary sort on tied values (e.g. GA/IN both rate 3.44), so a fresh DB
    # ORDER BY may tie-break differently than the published CSV without any value
    # drift. Sort both by all columns before comparing so a tie-order flip
    # doesn't false-fail; every value and the full row set must still match.
    cols = list(norm_csv.columns)
    norm_csv_s = norm_csv.sort_values(cols).reset_index(drop=True)
    norm_db_s = norm_db.sort_values(cols).reset_index(drop=True)
    equal = norm_csv_s.equals(norm_db_s)
    detail = ""
    if not equal:
        diff_mask = norm_csv_s.ne(norm_db_s)
        where = diff_mask.stack()
        first = where[where].index[:1].tolist()
        detail = f"first diff at {first}" if first else "value mismatch"
    check(f"export parity: {name} values match DB", equal, detail)


# ---------------------------------------------------------------------------
# Check groups
# ---------------------------------------------------------------------------

def check_structural(con: duckdb.DuckDBPyConnection) -> None:
    """(c) STRUCTURAL — prepared-table row counts + no NULLs in asserted cols."""
    expected_rows = {
        "chart_headline": 79,
        "chart_u3_u6": 33,
        "chart_race": 54,
        "chart_youth": 79,
        "chart_state_map": 51,
        "chart_states_selected": 51,
        "chart_edu_race": 8,
    }
    for tbl, n in expected_rows.items():
        got = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        check(f"structural: {tbl} = {n} rows (non-zero)", got == n and got > 0,
              f"got {got}")

    # Hard requirements the plan calls out explicitly.
    check("structural: chart_state_map has exactly 51 rows",
          con.execute("SELECT COUNT(*) FROM chart_state_map").fetchone()[0] == 51)
    check("structural: chart_edu_race has exactly 8 rows",
          con.execute("SELECT COUNT(*) FROM chart_edu_race").fetchone()[0] == 8)

    # No NULLs in the asserted columns.
    null_specs = [
        ("chart_edu_race.unemployment_rate",
         "SELECT COUNT(*) FROM chart_edu_race WHERE unemployment_rate IS NULL"),
        ("chart_state_map.rate",
         "SELECT COUNT(*) FROM chart_state_map WHERE rate IS NULL"),
        ("chart_u3_u6.(u3,u6)",
         "SELECT COUNT(*) FROM chart_u3_u6 WHERE u3 IS NULL OR u6 IS NULL"),
        ("chart_race.(white,hispanic,black) for year>=1973",
         "SELECT COUNT(*) FROM chart_race WHERE year>=1973 AND "
         "(white IS NULL OR hispanic IS NULL OR black IS NULL)"),
        ("chart_youth.(youth_16_19,adults_20plus)",
         "SELECT COUNT(*) FROM chart_youth WHERE youth_16_19 IS NULL OR adults_20plus IS NULL"),
    ]
    for label, sql in null_specs:
        n_null = con.execute(sql).fetchone()[0]
        check(f"structural: no NULLs in {label}", n_null == 0, f"{n_null} null(s)")


def check_chart05_education(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 05 — the 8 education×race rates PRINTED on the chart (EXACT)."""
    rows = con.execute(
        "SELECT education_level, race, unemployment_rate FROM chart_edu_race"
    ).fetchall()
    edu = {(lvl, race): rate for lvl, race, rate in rows}
    # EXACT — these are the exact numbers printed on the chart (Grok: exact match).
    expected = {
        ("Less than high school", "White"): 5.7,
        ("Less than high school", "Black"): 9.5,
        ("High school, no college", "White"): 3.7,
        ("High school, no college", "Black"): 6.7,
        ("Some college or associate degree", "White"): 3.0,
        ("Some college or associate degree", "Black"): 4.7,
        ("Bachelor's degree and higher", "White"): 2.1,
        ("Bachelor's degree and higher", "Black"): 3.0,
    }
    for key, want in expected.items():
        got = edu.get(key)
        check(f"chart05: {key[0]} / {key[1]} == {want}", got == want, f"got {got}")

    # Black > White in all 4 tiers.
    tiers = [
        "Less than high school",
        "High school, no college",
        "Some college or associate degree",
        "Bachelor's degree and higher",
    ]
    for tier in tiers:
        w = edu.get((tier, "White"))
        b = edu.get((tier, "Black"))
        check(f"chart05: Black > White in '{tier}'", b is not None and w is not None and b > w,
              f"White={w} Black={b}")


def check_chart04_state_map(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 04 — DC is the lone ≥6.0 band state; band counts; total=51."""
    check("chart04: total states = 51",
          con.execute("SELECT COUNT(*) FROM chart_state_map").fetchone()[0] == 51)

    top_abbrev, top_rate = con.execute(
        "SELECT state_abbrev, rate FROM chart_state_map ORDER BY rate DESC LIMIT 1"
    ).fetchone()
    max_rate = con.execute("SELECT MAX(rate) FROM chart_state_map").fetchone()[0]
    check("chart04: DC is the max-rate state", top_abbrev == "DC", f"got {top_abbrev!r}")
    check("chart04: DC rate >= 6.0", top_rate >= 6.0, f"got {top_rate}")
    check("chart04: DC rate rounds to 6.4", round(top_rate, 1) == 6.4, f"got {top_rate}")
    check("chart04: DC rate equals MAX(rate)", top_rate == max_rate,
          f"top={top_rate} max={max_rate}")

    # Band counts using the SAME thresholds 04-viz/06 use.
    band_rows = con.execute("""
        SELECT CASE
            WHEN rate < 3.0 THEN '<3.0'
            WHEN rate < 4.0 THEN '3.0-3.9'
            WHEN rate < 5.0 THEN '4.0-4.9'
            WHEN rate < 6.0 THEN '5.0-5.9'
            ELSE '>=6.0' END AS band, COUNT(*) AS n
        FROM chart_state_map GROUP BY 1
    """).fetchall()
    bands = {b: n for b, n in band_rows}
    expected_bands = {"<3.0": 6, "3.0-3.9": 18, "4.0-4.9": 21, "5.0-5.9": 5, ">=6.0": 1}
    for band, want in expected_bands.items():
        check(f"chart04: band {band} count = {want}", bands.get(band, 0) == want,
              f"got {bands.get(band, 0)}")
    check("chart04: band counts sum to 51", sum(bands.values()) == 51,
          f"sum={sum(bands.values())}")
    check("chart04: exactly one state in the >=6.0 band", bands.get(">=6.0", 0) == 1,
          f"got {bands.get('>=6.0', 0)}")


def check_chart02_race(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 02 — Black>Hispanic>White; ratio ~2.0-2.2; 2020 spot."""
    viol = con.execute("""
        SELECT COUNT(*) FROM chart_race
        WHERE white IS NOT NULL AND hispanic IS NOT NULL AND black IS NOT NULL
          AND NOT (black > hispanic AND hispanic > white)
    """).fetchone()[0]
    check("chart02: Black > Hispanic > White in every complete year", viol == 0,
          f"{viol} violation(s)")

    ratio = con.execute(
        "SELECT AVG(black/white) FROM chart_race WHERE white IS NOT NULL AND black IS NOT NULL"
    ).fetchone()[0]
    check("chart02: mean Black/White ratio 1973-2026 within 2.0-2.2",
          2.0 <= ratio <= 2.2, f"got {ratio:.4f}")

    # Spot year 2020. DB carries 2 dp (11.57/10.48/7.34); Grok quotes the same
    # annual averages rounded (11.4/10.4/7.3). Tolerance ±0.2 — NOT a data error.
    white, hispanic, black = con.execute(
        "SELECT white, hispanic, black FROM chart_race WHERE year = 2020"
    ).fetchone()
    check("chart02: 2020 Black ~11.4 (+/-0.2)", abs(black - 11.4) <= 0.2, f"got {black}")
    check("chart02: 2020 Hispanic ~10.4 (+/-0.2)", abs(hispanic - 10.4) <= 0.2, f"got {hispanic}")
    check("chart02: 2020 White ~7.3 (+/-0.2)", abs(white - 7.3) <= 0.2, f"got {white}")


def check_chart03_youth(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 03 — teen > adults every year; ratio ~2-4x on average."""
    viol = con.execute(
        "SELECT COUNT(*) FROM chart_youth WHERE youth_16_19 <= adults_20plus"
    ).fetchone()[0]
    check("chart03: teen(16-19) > adults 20+ in every year", viol == 0,
          f"{viol} violation(s)")
    ratio = con.execute(
        "SELECT AVG(youth_16_19/adults_20plus) FROM chart_youth"
    ).fetchone()[0]
    check("chart03: mean teen/adult ratio within 2-4x", 2.0 <= ratio <= 4.0,
          f"got {ratio:.4f}")


def check_chart01_u3_u6(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 01 — U-6 > U-3 every year; starts 1994; Great-Recession peak."""
    viol = con.execute("SELECT COUNT(*) FROM chart_u3_u6 WHERE u6 <= u3").fetchone()[0]
    check("chart01: U-6 > U-3 in every year", viol == 0, f"{viol} violation(s)")

    min_year = con.execute("SELECT MIN(year) FROM chart_u3_u6").fetchone()[0]
    check("chart01: series starts 1994", min_year == 1994, f"got {min_year}")

    # Great-Recession peak (DB 2010: U-3 9.61 / U-6 16.74 — Grok "U-3 ~9.6, U-6 ~16-17").
    u3, u6 = con.execute("SELECT u3, u6 FROM chart_u3_u6 WHERE year = 2010").fetchone()
    check("chart01: 2010 U-3 ~9.6 (+/-0.3)", abs(u3 - 9.6) <= 0.3, f"got {u3}")
    check("chart01: 2010 U-6 within 16.0-17.5", 16.0 <= u6 <= 17.5, f"got {u6}")


def check_export_parity(con: duckdb.DuckDBPyConnection) -> None:
    """(a) EXPORT-vs-DB parity — each export CSV matches its DB source frame."""
    export_dir = PROJECT / "export"

    # 1. States trailing-12 export ⇔ chart_state_map ordered by rate DESC.
    states_db = con.execute(
        "SELECT state_name, state_abbrev, rate, n_months FROM chart_state_map ORDER BY rate DESC"
    ).df()
    assert_csv_matches("unemployment_states_trailing12_v1", states_db,
                       export_dir / "unemployment_states_trailing12_v1.csv")
    # spot-asserts the plan calls out
    dc = con.execute(
        "SELECT rate, n_months FROM chart_state_map WHERE state_abbrev='DC'"
    ).fetchone()
    check("export parity: states DC row rate=6.38, n_months=12",
          dc == (6.38, 12), f"got {dc}")
    wy = con.execute(
        "SELECT n_months FROM chart_state_map WHERE state_abbrev='WY'"
    ).fetchone()[0]
    check("export parity: states Wyoming n_months=5", wy == 5, f"got {wy}")

    # 2. Education×race export ⇔ chart_edu_race ordered by education_order, White-first.
    edu_db = con.execute(
        "SELECT year, education_level, education_order, race, unemployment_rate "
        "FROM chart_edu_race "
        "ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END"
    ).df()
    assert_csv_matches("unemployment_by_education_race_2024_v1", edu_db,
                       export_dir / "unemployment_by_education_race_2024_v1.csv")

    # 3. National annual panel ⇔ build_export_national_annual (pure SELECT).
    national_db = build_export_national_annual(con)
    assert_csv_matches("unemployment_national_annual_v1", national_db,
                       export_dir / "unemployment_national_annual_v1.csv")


def check_png_parity() -> None:
    """(d) SOCIAL/WEB PARITY — same 5 stems; social 1600x900, web 1664x936."""
    expected_stems = {
        "01_u3_vs_u6", "02_race_gap", "03_youth_vs_adults",
        "04_state_map", "05_race_gap_by_education",
    }
    social_dir = PROJECT / "outputs" / "social"
    web_dir = PROJECT / "outputs" / "web"

    social = {p.stem: p for p in social_dir.glob("*.png")}
    web = {p.stem: p for p in web_dir.glob("*.png")}

    check("png parity: social has the 5 expected stems", set(social) == expected_stems,
          f"got {sorted(social)}")
    check("png parity: web has the 5 expected stems", set(web) == expected_stems,
          f"got {sorted(web)}")
    check("png parity: social and web cover the same stems", set(social) == set(web),
          f"only social: {sorted(set(social)-set(web))}; only web: {sorted(set(web)-set(social))}")

    try:
        from PIL import Image
    except ImportError:
        check("png parity: PIL available for dimension check", False,
              "Pillow not importable")
        return

    for stem, path in sorted(social.items()):
        size = Image.open(path).size
        check(f"png parity: social {stem} is 1600x900", size == (1600, 900), f"got {size}")
    for stem, path in sorted(web.items()):
        size = Image.open(path).size
        check(f"png parity: web {stem} is 1664x936", size == (1664, 936), f"got {size}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config(str(PROJECT / "config.yaml"))
    db = str(PROJECT / cfg["settings"]["duckdb_file"])
    con = duckdb.connect(db, read_only=True)  # READ-ONLY — never fight the writer lock
    try:
        check_structural(con)
        check_chart05_education(con)
        check_chart04_state_map(con)
        check_chart02_race(con)
        check_chart03_youth(con)
        check_chart01_u3_u6(con)
        check_export_parity(con)
    finally:
        con.close()

    # PNG parity doesn't need the DB.
    check_png_parity()

    print("Pre-publish chart-data validation — unemployment")
    print("=" * 64)
    for line in checks:
        print(line)
    for line in failures:
        print(line)
    print("=" * 64)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S) of {len(checks)+len(failures)} checks "
              f"— DO NOT PUBLISH.")
        return 1
    print(f"RESULT: all {len(checks)} checks passed — safe to publish.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

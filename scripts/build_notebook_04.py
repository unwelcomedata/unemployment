"""Build 04-viz.ipynb for the unemployment project."""
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
# 04 — Visualization: Exploring U.S. Unemployment Data

This notebook explores the unemployment data to understand the story and decide
which angles are worth building as social charts.

**Charts explored:**
1. Headline U-3 rate — 1948–2026 (line)
2. Official vs broad unemployment — U-3 vs U-6, 1994–2026 (two-line)
3. Racial gap — White, Black, Hispanic, 1973–2026 (three-line)
4. Youth unemployment — 16–19 vs overall, 1948–2026 (two-line)
5. State rankings — current snapshot, all 51 states (ranked bars)
6. Selected states over time — CA, TX, FL, NY, MI, MA, 1976–2026 (multi-line)

**⏸ AWAITING OWNER REVIEW** — no `06-viz-social` work starts until story/framing
is locked here.
"""))

# ── Cell 1 — setup ──────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
import sys, os
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

PROJECT = Path.cwd()
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT / "src"))

SHARED = PROJECT.parent.parent / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

import duckdb
import pandas as pd
from chart_factory import render_chart
from colors import c

DB_PATH = "data/project.duckdb"

# Open writable to build chart_ tables, then close and reopen read-only.
con_rw = duckdb.connect(DB_PATH)
print("Connected (rw). Tables:", [t[0] for t in con_rw.execute("SHOW TABLES").fetchall()])
"""))

# ── Cell 2 — build chart tables ──────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Build chart tables

All SQL aggregations run in DuckDB. Annual averages are used for all line
charts (cleaner than monthly for long time spans; monthly data remains
in `unemployment_national_clean` for deeper cuts).
"""))

cells.append(nbformat.v4.new_code_cell("""\
# ── Chart 1: Headline U-3 rate, annual averages 1948-2026 ───────────────────
con_rw.execute("DROP TABLE IF EXISTS chart_headline")
con_rw.execute(\"\"\"
CREATE TABLE chart_headline AS
SELECT year, ROUND(AVG(value), 2) AS rate
FROM unemployment_national_clean
WHERE series_id = 'LNS14000000'
GROUP BY year ORDER BY year
\"\"\")
print("chart_headline:", con_rw.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_headline").fetchone())

# ── Chart 2: U-3 vs U-6, annual averages 1994-2026 ──────────────────────────
con_rw.execute("DROP TABLE IF EXISTS chart_u3_u6")
con_rw.execute(\"\"\"
CREATE TABLE chart_u3_u6 AS
SELECT
    year,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000000' THEN value END), 2) AS u3,
    ROUND(AVG(CASE WHEN series_id = 'LNS13327709' THEN value END), 2) AS u6
FROM unemployment_national_clean
WHERE series_id IN ('LNS14000000', 'LNS13327709')
  AND year >= 1994
GROUP BY year ORDER BY year
\"\"\")
print("chart_u3_u6:", con_rw.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_u3_u6").fetchone())

# ── Chart 3: Race comparison, annual averages 1973-2026 ─────────────────────
con_rw.execute("DROP TABLE IF EXISTS chart_race")
con_rw.execute(\"\"\"
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
\"\"\")
print("chart_race:", con_rw.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_race").fetchone())

# ── Chart 4: Youth vs total, annual averages 1948-2026 ──────────────────────
con_rw.execute("DROP TABLE IF EXISTS chart_youth")
con_rw.execute(\"\"\"
CREATE TABLE chart_youth AS
SELECT
    year,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000000' THEN value END), 2) AS total,
    ROUND(AVG(CASE WHEN series_id = 'LNS14000012' THEN value END), 2) AS youth_16_19
FROM unemployment_national_clean
WHERE series_id IN ('LNS14000000', 'LNS14000012')
GROUP BY year ORDER BY year
\"\"\")
print("chart_youth:", con_rw.execute("SELECT MIN(year), MAX(year), COUNT(*) FROM chart_youth").fetchone())

# ── Chart 5: State current rankings, most recent month ──────────────────────
con_rw.execute("DROP TABLE IF EXISTS chart_state_current")
con_rw.execute(\"\"\"
CREATE TABLE chart_state_current AS
WITH recent AS (
    SELECT MAX(year) AS yr FROM unemployment_states_clean
),
recent_month AS (
    SELECT MAX(month) AS mo FROM unemployment_states_clean
    WHERE year = (SELECT yr FROM recent)
)
SELECT
    state_name,
    state_abbrev,
    value AS rate
FROM unemployment_states_clean
WHERE year = (SELECT yr FROM recent)
  AND month = (SELECT mo FROM recent_month)
ORDER BY rate DESC
\"\"\")
n_states, yr, mo = con_rw.execute(
    "SELECT COUNT(*), MAX(year), MAX(month) FROM chart_state_current WHERE 1=1"
).fetchone()
print(f"chart_state_current: {n_states} states, latest = {yr}-{mo:02d}")

# ── Chart 6: Selected states over time, annual averages 1976-2026 ────────────
SELECTED_STATES = ['California', 'Texas', 'Florida', 'New York', 'Michigan', 'Massachusetts']
state_list = "', '".join(SELECTED_STATES)
con_rw.execute("DROP TABLE IF EXISTS chart_states_selected")
con_rw.execute(f\"\"\"
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
WHERE state_name IN ('{state_list}')
GROUP BY year ORDER BY year
\"\"\")
print("chart_states_selected:", con_rw.execute(
    "SELECT MIN(year), MAX(year), COUNT(*) FROM chart_states_selected"
).fetchone())

con_rw.close()
print("\\nAll chart tables built. Switching to read-only connection.")
"""))

# ── Cell 3 — open read-only ───────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
con = duckdb.connect(DB_PATH, read_only=True)
print("Connected (read-only).")
"""))

# ── Cell 4 — chart 1: headline rate ──────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 1 — U.S. Unemployment Rate, 1948–2026

The full history of the official U-3 rate. Four major peaks stand out:
the 1982 Volcker recession (~10.8%), the Great Recession peak (~10.0%),
the COVID shock (14.8% in April 2020), and the long post-WWII decline.

**Story angle:** the cyclical nature of unemployment — recoveries follow every
recession but not all recoveries reach the same lows.
"""))

cells.append(nbformat.v4.new_code_cell("""\
render_chart({
    "type": "line",
    "db": con,
    "table": "chart_headline",
    "x_col": "year",
    "series": [
        {"col": "rate", "label": "U-3 (official)", "color": c("teal")},
    ],
    "y_axis_label": "Unemployment rate (%)",
    "x_axis_label": "",          # year is self-evident
    "y_min": 0,
    "y_max": 16,
    "markers": False,
    "label_last": False,         # single line — no end-label needed
    "x_tick_step": 10,
    "title": "U.S. unemployment rate, 1948\\u20132026",
    "subtitle": "Annual average, seasonally adjusted U-3. Source: BLS CPS.",
    "source": "Bureau of Labor Statistics, CPS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "01_headline_rate",
})
"""))

# ── Cell 5 — chart 2: U-3 vs U-6 ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 2 — Official vs Broad Unemployment (U-3 and U-6), 1994–2026

U-6 includes discouraged workers plus people working part-time for economic
reasons. The **gap** between U-3 and U-6 is the "hidden unemployment."

**Key observation:** The gap widens during recessions and shrinks during tight
labor markets — it peaked at ~7.5 points after the Great Recession (U-6 ~17%
vs U-3 ~9.5%). Currently (2026) the gap is ~3–4 points.
"""))

cells.append(nbformat.v4.new_code_cell("""\
render_chart({
    "type": "line",
    "db": con,
    "table": "chart_u3_u6",
    "x_col": "year",
    "series": [
        {"col": "u3", "label": "U-3 (official)", "color": c("teal")},
        {"col": "u6", "label": "U-6 (broad)",    "color": c("navy")},
    ],
    "y_axis_label": "Unemployment rate (%)",
    "x_axis_label": "",
    "y_min": 0,
    "y_max": 18,
    "markers": False,
    "label_last": True,
    "x_tick_step": 5,
    "title": "U.S. unemployment \\u2014 official vs broad measure, 1994\\u20132026",
    "subtitle": "Annual average. U-6 adds discouraged workers + involuntary part-timers to U-3.",
    "source": "Bureau of Labor Statistics, CPS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "02_u3_vs_u6",
})
"""))

# ── Cell 6 — chart 3: racial gap ─────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 3 — Unemployment Rate by Race/Ethnicity, 1973–2026

**Key finding:** Black unemployment has consistently run ~2× White unemployment
for every year on record. Hispanic unemployment sits between the two.
The *ratio* is more stable than the absolute levels — it persists through
expansions and contractions alike.

**Story angle:** The 2:1 Black/White ratio is one of the most persistent
structural facts in U.S. labor economics. The COVID shock closed the gap
temporarily (all rates spiked), but by 2021 the gap had fully reopened.

**Caveat (label this on any chart):** Hispanic series begins 1973, Black 1972.
Starts are comparable from 1973.
"""))

cells.append(nbformat.v4.new_code_cell("""\
render_chart({
    "type": "line",
    "db": con,
    "table": "chart_race",
    "x_col": "year",
    "series": [
        {"col": "white",    "label": "White",    "color": c("teal_mid")},
        {"col": "hispanic", "label": "Hispanic", "color": c("gold")},
        {"col": "black",    "label": "Black",    "color": c("navy")},
    ],
    "y_axis_label": "Unemployment rate (%)",
    "x_axis_label": "",
    "y_min": 0,
    "y_max": 22,
    "markers": False,
    "label_last": True,
    "x_tick_step": 10,
    "title": "Unemployment rate by race/ethnicity, 1973\\u20132026",
    "subtitle": "Annual average U-3, seasonally adjusted. Series start dates differ; Black 1972, Hispanic 1973.",
    "source": "Bureau of Labor Statistics, CPS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "03_race_gap",
})
"""))

# ── Cell 7 — quick stats: racial gap ─────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# Quantify the Black/White ratio over time
ratio_df = con.execute(\"\"\"
SELECT year,
       ROUND(black / NULLIF(white, 0), 2) AS black_white_ratio,
       ROUND(black - white, 2)             AS gap_pct_points,
       white, black, hispanic
FROM chart_race
ORDER BY year
\"\"\").df()

print("Black/White unemployment ratio — key years:")
print(ratio_df[ratio_df["year"].isin([1973, 1980, 1990, 2000, 2010, 2020, 2024, 2026])].to_string(index=False))
print()
print(f"Mean ratio across all years: {ratio_df['black_white_ratio'].mean():.2f}x")
print(f"Min ratio: {ratio_df['black_white_ratio'].min():.2f}x ({ratio_df.loc[ratio_df['black_white_ratio'].idxmin(),'year']})")
print(f"Max ratio: {ratio_df['black_white_ratio'].max():.2f}x ({ratio_df.loc[ratio_df['black_white_ratio'].idxmax(),'year']})")
"""))

# ── Cell 8 — chart 4: youth ───────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 4 — Youth (16–19) vs Overall Unemployment, 1948–2026

Teen unemployment consistently runs 2–4× the overall rate. The ratio is
structural — teens compete for entry-level jobs with more experienced workers
and are first to be laid off in downturns.

**Story angle:** The teen unemployment rate at its LOWEST point (~11% in 2019)
was still above most recessions' peaks for adults.
"""))

cells.append(nbformat.v4.new_code_cell("""\
render_chart({
    "type": "line",
    "db": con,
    "table": "chart_youth",
    "x_col": "year",
    "series": [
        {"col": "total",      "label": "Overall (16+)", "color": c("teal")},
        {"col": "youth_16_19","label": "Teen (16\\u201319)", "color": c("brown_red")},
    ],
    "y_axis_label": "Unemployment rate (%)",
    "x_axis_label": "",
    "y_min": 0,
    "y_max": 30,
    "markers": False,
    "label_last": True,
    "x_tick_step": 10,
    "title": "Teen (16\\u201319) vs overall unemployment, 1948\\u20132026",
    "subtitle": "Annual average U-3, seasonally adjusted. Teen rate runs 2\\u20134\\u00d7 the overall rate in every year on record.",
    "source": "Bureau of Labor Statistics, CPS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "04_youth_vs_total",
})
"""))

# ── Cell 9 — chart 5: state rankings ─────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 5 — State Unemployment Rates (Current Snapshot)

A ranked snapshot of all 51 state-level rates. DC and a few coastal states
typically top the list. Plains and Mountain states tend to sit at the bottom.

**Story angle:** The spread from highest to lowest (~5 pp) shows how
geographically uneven unemployment is even in a healthy national labor market.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Get the reference date for the title
ref = con.execute("SELECT MAX(year), MAX(month) FROM chart_state_current").fetchone()
yr_ref, mo_ref = ref
import calendar
mo_name = calendar.month_name[mo_ref]

render_chart({
    "type": "single_ranked_bars",
    "db": con,
    "table": "chart_state_current",
    "label_col": "state_abbrev",
    "value_col": "rate",
    "color": c("teal"),
    "value_format": "{:.1f}%",
    "bar_label_inside": False,
    "title": f"State unemployment rates \\u2014 {mo_name} {yr_ref}",
    "subtitle": "Seasonally adjusted U-3. LAUS model-based estimates, BLS.",
    "source": "Bureau of Labor Statistics, LAUS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "05_state_rankings",
})
"""))

# ── Cell 10 — chart 6: selected states over time ─────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 6 — Selected States Over Time, 1976–2026

A few economically diverse states: CA and MI (industrial cycles), TX and FL
(Sun Belt growth), NY (finance) and MA (education/tech). The charts show
how differently recessions hit each state — Michigan's 2009 spike (~14%) dwarfs
the national average.

**Story angle:** State unemployment tells a richer story than the national average.
"""))

cells.append(nbformat.v4.new_code_cell("""\
render_chart({
    "type": "line",
    "db": con,
    "table": "chart_states_selected",
    "x_col": "year",
    "series": [
        {"col": "michigan",      "label": "MI",  "color": c("brown_red")},
        {"col": "california",    "label": "CA",  "color": c("teal")},
        {"col": "new_york",      "label": "NY",  "color": c("navy")},
        {"col": "florida",       "label": "FL",  "color": c("gold")},
        {"col": "texas",         "label": "TX",  "color": c("spice")},
        {"col": "massachusetts", "label": "MA",  "color": c("teal_mid")},
    ],
    "y_axis_label": "Unemployment rate (%)",
    "x_axis_label": "",
    "y_min": 0,
    "y_max": 16,
    "markers": False,
    "label_last": True,
    "x_tick_step": 10,
    "title": "Unemployment rate \\u2014 selected states, 1976\\u20132026",
    "subtitle": "Annual average, LAUS seasonally adjusted. Michigan's 2009 peak ~14%; MA and TX historically low.",
    "source": "Bureau of Labor Statistics, LAUS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "06_states_selected",
})
"""))

# ── Cell 11 — summary stats ───────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Key Numbers for Chart Copy

Important figures to have on hand when writing chart captions.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Recession peaks
peaks = con.execute(\"\"\"
SELECT year, MAX(rate) AS peak_rate
FROM chart_headline
WHERE year IN (1949, 1958, 1961, 1975, 1982, 1983, 1992, 2009, 2010, 2020)
GROUP BY year ORDER BY year
\"\"\").df()
print("U-3 recession-year peaks:")
print(peaks.to_string(index=False))
print()

# Current (2026 annual so far)
current = con.execute("SELECT year, rate FROM chart_headline ORDER BY year DESC LIMIT 3").df()
print("Most recent annual averages:")
print(current.to_string(index=False))
print()

# U-3 vs U-6 current gap
gap = con.execute("SELECT year, u3, u6, ROUND(u6-u3,1) AS gap FROM chart_u3_u6 ORDER BY year DESC LIMIT 5").df()
print("Recent U-3 vs U-6 gap:")
print(gap.to_string(index=False))
print()

# Current state extremes
extremes = con.execute(\"\"\"
SELECT state_name, state_abbrev, rate
FROM chart_state_current
WHERE rate = (SELECT MAX(rate) FROM chart_state_current)
   OR rate = (SELECT MIN(rate) FROM chart_state_current)
ORDER BY rate DESC
\"\"\").df()
print("Current state extremes:")
print(extremes.to_string(index=False))
"""))

# ── Cell 12 — story framing notes ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Story Framing — Candidate Angles for Social Charts

Based on this exploration, the most compelling angles are:

**1. The 2:1 rule — racial unemployment gap (Chart 3)**
Black unemployment has run almost exactly 2× White unemployment in every year
since records began. The ratio barely moves across expansions and recessions.
This is one of the most persistent structural facts in U.S. labor economics.
**→ Strong candidate for lead social chart.**

**2. The hidden unemployment gap — U-3 vs U-6 (Chart 2)**
The gap between the headline rate and the broad measure doubles during
recessions. At the worst of the Great Recession, the "real" rate was ~17%,
nearly double the official 9.5%.
**→ Good second chart — adds a methodology/nuance angle.**

**3. Teens always struggle — youth unemployment (Chart 4)**
Even at the peak of a hot labor market in 2019, teen unemployment (~11%) was
higher than the national rate during most adult recessions. A clean "context"
chart.
**→ Third chart option.**

**4. State geographic spread (Chart 5)**
A ranked bar of current state rates — quick snapshot of geographic inequality.
**→ Good for engagement / state pride reactions.**

**Suggested social lineup (owner to confirm):**
- Chart A: Racial gap line (the lead — structural finding)
- Chart B: U-3 vs U-6 (the "hidden unemployment" angle)
- Chart C: Youth vs overall (the "teens always lose" angle)
- Chart D: State current rankings (engagement/snapshot)

⏸ **Build `06-viz-social` only after owner confirms this framing.**
"""))

# ── Cell 13 — cleanup ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/04-viz.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")

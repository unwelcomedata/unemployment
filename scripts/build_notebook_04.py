"""Build 04-viz.ipynb for the unemployment project.

04-viz is a CONSUMER: it opens the DB read-only and renders the 7 charts from the
chart-ready tables that 03-prepare built. It no longer builds any chart_* table
(that work moved to 03-prepare). The chart configs — titles, subtitles,
footnotes, colors, chart-2 vlines, chart-5 choropleth + DC callout, chart-7
grouped columns — are UNCHANGED from the exploration-confirmed notebook.
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
# 04 — Visualization: Exploring U.S. Unemployment Data

This notebook explores the unemployment data to understand the story and decide
which angles are worth building as social charts.

**It CONSUMES the chart-ready tables built in `03-prepare`** (`chart_headline`,
`chart_u3_u6`, `chart_race`, `chart_youth`, `chart_state_map`,
`chart_states_selected`, `chart_edu_race`) and renders them — it does **not**
build any chart table itself. Run `03-prepare.ipynb` first; it is the writer and
closes its connection, so this notebook opens the DB **read-only**.

**Charts explored:**
1. Headline U-3 rate — 1948–2026 (line)
2. Official vs broad unemployment — U-3 vs U-6, 1994–2026 (two-line, with methodology markers)
3. Racial gap — White, Black, Hispanic, 1973–2026 (three-line)
4. Youth unemployment — teens (16–19) vs adults 20+, 1948–2026 (two-line)
5. State unemployment — trailing 12-month average, all 51 states (choropleth)
6. Selected states over time — CA, TX, FL, NY, MI, MA, 1976–2026 (multi-line)

**⏸ AWAITING OWNER REVIEW** — no `06-viz-social` work starts until story/framing
is locked here.
"""))

# ── Cell 1 — setup (read-only) ───────────────────────────────────────────────
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

# 03-prepare is the writer; this notebook only reads. Open read-only.
con = duckdb.connect(DB_PATH, read_only=True)

# Guard: the chart-ready tables must already exist (built by 03-prepare).
_tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
_required = [
    "chart_headline", "chart_u3_u6", "chart_race", "chart_youth",
    "chart_state_map", "chart_states_selected", "chart_edu_race",
]
_missing = [t for t in _required if t not in _tables]
assert not _missing, (
    f"Prepared chart tables missing: {_missing}. "
    "Run notebooks/03-prepare.ipynb first (it builds the chart_* tables)."
)
print("Connected (read-only). Prepared chart tables present:", _required)
"""))

# ── Cell 2 — chart 1: headline rate ──────────────────────────────────────────
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

# ── Cell 3 — chart 2: U-3 vs U-6 ─────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 2 — Official vs Broad Unemployment (U-3 and U-6), 1994–2026

U-6 includes discouraged workers plus people working part-time for economic
reasons. The **gap** between U-3 and U-6 is the "hidden unemployment."

**Key observation:** The gap widens during recessions and shrinks during tight
labor markets — it peaked at ~7.5 points after the Great Recession (U-6 ~17%
vs U-3 ~9.5%). Currently (2026) the gap is ~3–4 points.

**Methodology / definition markers on this chart** (vertical dashed lines) — both
are measurement changes, not conclusions:

- **1994 — CPS redesign.** The Current Population Survey was redesigned: new
  job-search and duration questions, and the alternative U-4–U-6 measures were
  introduced (this is why the U-6 series begins in 1994).
- **2011 — unemployment-duration cap raised.** BLS raised the maximum recorded
  value of the CPS unemployment-duration variable from up to 99 weeks (~2 years)
  to up to 260 weeks (~5 years). This affects duration / long-term-unemployment
  series, **not** the U-3 or U-6 rate *levels* shown here — it is a change to a
  measurement variable, not a redefinition of who is counted as unemployed.

Both are documented under "Methodology changes / series breaks" in `SOURCES.md`.
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
    "vlines": [
        {"x": 1994, "label": "1994 CPS redesign"},
        {"x": 2011, "label": "2011 duration cap"},
    ],
    "title": "U.S. unemployment \\u2014 official vs broad measure, 1994\\u20132026",
    "subtitle": "Annual average. U-3 (official) = jobless, available, and actively looked in the last 4 weeks, as a share of the labor force. U-6 (broad) adds discouraged/marginally-attached workers plus involuntary part-timers.",
    "source": "Markers: 1994 CPS redesign introduced U-4\\u2013U-6 and new job-search/duration questions; 2011 raised the max recorded jobless-duration from ~2 to ~5 years. BLS CPS, retrieved 2026-09-28.",
    "preset": "twitter_landscape",
    "filename": "02_u3_vs_u6",
})
"""))

# ── Cell 4 — chart 3: racial gap ─────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 3 — Unemployment Rate by Race/Ethnicity, 1973–2026

**Key finding:** Black unemployment has consistently run ~2× White unemployment
for every year on record. Hispanic unemployment sits between the two.
The *ratio* is more stable than the absolute levels — it persists through
expansions and contractions alike.

**Story angle:** The 2:1 Black/White ratio is one of the most persistent
structural facts in U.S. labor economics. The COVID shock closed the gap
temporarily (all rates spiked), but by 2021 the gap had fully reopened.

**Why the gap persists (interpretation, cited):** Economists attribute the
persistent ~2:1 gap mainly to **labor-market discrimination and occupational
segregation**, not to differences in education — the gap holds at every
education level, and hiring-audit studies find no decline in discrimination
since 1989. (Sources: BLS CPS; EPI 2015, 2019; Quillian et al., PNAS 2017;
Federal Reserve FEDS 2017-071. See `SOURCES.md` → "Interpretation sources
(race gap)"; fuller writeup in `artifacts/race-gap-literature.md`.)

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
    "subtitle": "Annual average U-3, seasonally adjusted. Black series begins 1972, Hispanic 1973.",
    "source": "Gap attributed mainly to labor-market discrimination and occupational segregation, not education (holds at every education level). Sources: BLS CPS; EPI 2015, 2019; Quillian et al. PNAS 2017; Fed FEDS 2017-071. Retrieved 2026-09-28.",
    "preset": "twitter_landscape",
    "filename": "03_race_gap",
})
"""))

# ── Cell 5 — quick stats: racial gap ─────────────────────────────────────────
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

# ── Cell 6 — chart 7: race gap by education (companion to chart 3) ───────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 7 (companion to Chart 3) — Unemployment by race within education level, 25+

This is the **companion to Chart 3** (the Black/White ~2:1 unemployment gap). It
answers the obvious rebuttal — *"isn't the gap just an education gap?"* — by
showing the gap **holds at every education level**. The chart is a **clustered
vertical-column** chart: four clusters (one per education tier) along the x-axis,
and within each cluster two adjacent columns (White, then Black) rising from a
**single shared baseline** against one left value-axis, so the within-tier gap is
read directly. In every tier the Black column is taller than the White column; a
Black worker with a bachelor's degree (3.0%) has about the same unemployment rate
as a White worker with no college at all (White some-college 3.0%). Education does
not close the gap — which is what pushes the explanation toward labor-market
discrimination and occupational segregation (see `artifacts/race-gap-literature.md`).

**Grain note — this is NOT the same series as Charts 1–6.** It comes from BLS
annual table **cpsaat07**: an **annual average**, population **25 years and over**,
**not seasonally adjusted** — versus the monthly, seasonally-adjusted, 16+ series
behind the other charts. The subtitle states this so the two are never conflated.

**Footnote (option B, verbatim — shown as the caption below the chart; the
social-ready footnote baking happens later in `06-viz-social`, out of scope here):**
> Economists attribute the persistent ~2:1 gap mainly to labor-market
> discrimination and occupational segregation, not to differences in education —
> the gap holds at every education level, and hiring-audit studies find no decline
> in discrimination since 1989. Source: BLS CPS; EPI (2015, 2019); Quillian et al.,
> PNAS 2017; Federal Reserve FEDS 2017-071."""))

cells.append(nbformat.v4.new_code_cell("""\
# Companion chart: clustered VERTICAL columns, one cluster per education tier,
# two adjacent bars (White, Black) per cluster rising from ONE shared baseline
# against a single left value-axis. White = teal_mid, Black = navy (matching
# Chart 3's race palette). Legend sits at the FAR RIGHT (legend_pos="right").
from IPython.display import Markdown, display

EDU_ORDER = [
    "Less than high school",
    "High school, no college",
    "Some college or associate degree",
    "Bachelor's degree and higher",
]
RACE_COLOR = {"White": c("teal_mid"), "Black": c("navy")}

# Long/tidy: one row per (education tier, race). Natural tier order (NOT value
# sorted), White then Black. Reads the prepared chart_edu_race table (built in
# 03-prepare); values unchanged.
edu_df = con.execute(\"\"\"
    SELECT education_level AS tier, race AS series, unemployment_rate AS value
    FROM chart_edu_race
    WHERE race IN ('White', 'Black')
    ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END
\"\"\").df()

render_chart({
    "type": "grouped_column_bars",            # alias: "clustered_bars"
    "preset": "twitter_landscape",
    "table": edu_df,                           # inline DataFrame (factory accepts df)
    "category_col": "tier",
    "value_col": "value",
    "series_col": "series",
    "series": [{"key": "White", "label": "White", "color": c("teal_mid")},
               {"key": "Black", "label": "Black", "color": c("navy")}],
    "category_order": EDU_ORDER,               # natural education order, NOT value-sorted
    "legend": [{"label": "White", "color": c("teal_mid")},
               {"label": "Black", "color": c("navy")}],
    "legend_pos": "right",
    "y_axis_label": "Unemployment rate (%)",
    "value_label_fmt": lambda v: f"{v:.1f}%",
    "label_wrap": 18,
    "title": "Unemployment rate by race within education level, workers 25+",
    "subtitle": "U.S. annual-average unemployment rate, 2024 \\u00b7 people 25 and older \\u00b7 "
                "Source: BLS Current Population Survey, table cpsaat07",
    "source": "Gap attributed mainly to labor-market discrimination and occupational segregation, not education (it holds at every education level); hiring-audit studies find no decline since 1989. Sources: BLS CPS, table cpsaat07; EPI 2015, 2019; Quillian et al. PNAS 2017; Fed FEDS 2017-071.",
    "filename": "07_race_gap_by_education",
})

# Approved footnote (option B), rendered verbatim as the chart caption.
display(Markdown(
    "<span style=\\"font-size:0.85em;color:#555\\">"
    "Economists attribute the persistent ~2:1 gap mainly to labor-market "
    "discrimination and occupational segregation, not to differences in education "
    "\\u2014 the gap holds at every education level, and hiring-audit studies find no "
    "decline in discrimination since 1989. Source: BLS CPS; EPI (2015, 2019); "
    "Quillian et al., PNAS 2017; Federal Reserve FEDS 2017-071."
    "</span>"
))
"""))

# ── Cell 7 — chart 4: youth vs adults 20+ ────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 4 — Teens (16–19) vs Adults 20+ Unemployment, 1948–2026

The comparison line is **adults 20+**, deliberately **excluding teens**, so the
teen line is contrasted against adults only (not against a total that already
includes teens).

The adults line uses the **real combined-sex adult total** — BLS CPS series
`LNS14000024` (Unemployment Rate, 20 years & over, seasonally adjusted), pulled
through `01-ingest` → `02-clean`. This is a genuine BLS series with full
1948–2026 coverage (not the overall 16+ rate, and not a men/women average).
Labeled "Workers 20+" on the chart.

Teen unemployment consistently runs 2–4× the adult rate. The ratio is
structural — teens compete for entry-level jobs with more experienced workers
and are first to be laid off in downturns.

**Story angle:** The teen unemployment rate at its LOWEST point (~11% in 2019)
was still above most recessions' peaks for adults.

**What the rate counts (and does not):** the unemployment rate — for both the teen 16–19 line and the adults-20+ line — is *unemployed ÷ labor force*, where the labor force is people who are employed **or** unemployed, and "unemployed" means available for work and having **actively looked in the last 4 weeks**. People who are neither working nor looking are **not in the labor force** and are excluded from both the numerator and the denominator. This matters most for teens: the teen rate is the share of teens *in the labor force* who lack a job — the majority of teens (they're in school) are not in the labor force and don't appear at all. Because teen labor-force participation is low (~35–40%), the teen denominator is small, so the teen rate swings more and must **not** be read as "X% of all teenagers are out of work." The definition of 'unemployed' is identical for teens and adults 20+; only the age bracket differs."""))

cells.append(nbformat.v4.new_code_cell("""\
render_chart({
    "type": "line",
    "db": con,
    "table": "chart_youth",
    "x_col": "year",
    "series": [
        {"col": "adults_20plus", "label": "Workers 20+", "color": c("teal")},
        {"col": "youth_16_19",   "label": "Teen (16\\u201319)", "color": c("brown_red")},
    ],
    "y_axis_label": "Unemployment rate (%)",
    "x_axis_label": "",
    "y_min": 0,
    "y_max": 30,
    "markers": False,
    "label_last": True,
    "x_tick_step": 10,
    "title": "Teen (16\\u201319) vs adults 20+ unemployment, 1948\\u20132026",
    "subtitle": "Annual average U-3, seasonally adjusted. Adults 20+ = BLS series LNS14000024 (real combined-sex adult total). Teen rate runs 2\\u20134\\u00d7 the adult rate in every year on record.",
    "source": "Rate = unemployed as a share of the labor force (working or actively looking), not of all teens; most teens are not in the labor force. Bureau of Labor Statistics, CPS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "04_youth_vs_adults",
})
"""))

# ── Cell 8 — chart 5: state choropleth ───────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 5 — State Unemployment Rate, Trailing 12-Month Average (choropleth)

A single-month snapshot of state rates is noisy and essentially meaningless, so
this chart maps each state's **average rate over the trailing 12 months** instead.

The window is the **12 most recent distinct monthly periods** in the data
(Jul 2025 – Jul 2026; note 2025-10 is absent, so the 12 periods span 13 calendar
months). 50 of 51 states have all 12 months; **Wyoming** reports only through
Dec 2025, so its average covers 5 months — noted here and thinner than the rest.

Rendered as a choropleth with a categorical bar legend: the continuous 12-month
average is binned into five readable rate bands and shaded light→dark. The lone
top-band state (DC) is shown as a far-right callout inset under the legend bars.

**Story angle:** The spread from highest to lowest (DC ~6.4% vs South Dakota
~2.1%) shows how geographically uneven unemployment is even in a healthy national
labor market — and a 12-month average is a stable way to show it.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Build the choropleth geo in Python: read the US-states shapefile (shared with
# dui-by-state), join the per-state trailing-12-month averages (the prepared
# chart_state_map table from 03-prepare) via FIPS, and bin the rate into ordered
# bands. The geo merge + banding + render are presentation and stay in 04; the
# per-state rate dataset is prepared in 03. The choropleth template
# reprojects/splits AK-HI-CONUS internally and needs the STATEFP column retained.
import geopandas as gpd

SHAPEFILE = (
    PROJECT.parent.parent
    / "data-projects" / "dui-by-state" / "data" / "raw" / "geo"
    / "cb_2022_us_state_20m.shp"
)
geo = gpd.read_file(SHAPEFILE)
geo = geo[~geo["STATEFP"].isin({"60", "66", "69", "72", "78"})].copy()  # 50 states + DC

# Per-state trailing-12-month average + FIPS (state_ref.fips matches STATEFP).
state_avg = con.execute(\"\"\"
SELECT m.state_name, m.state_abbrev, m.rate, m.n_months, r.fips
FROM chart_state_map m
JOIN state_ref r ON r.state_name = m.state_name
\"\"\").df()

geo = geo.merge(state_avg, left_on="STATEFP", right_on="fips", how="left")

# Bin the continuous 12-month-avg rate into ordered bands (percent).
import pandas as pd
BANDS = ["< 3.0%", "3.0\\u20133.9%", "4.0\\u20134.9%", "5.0\\u20135.9%", "\\u2265 6.0%"]
BAND_COLORS = {
    "< 3.0%":        c("teal_light"),   # #a8e0e0 (lightest)
    "3.0\\u20133.9%": c("aqua"),         # #94D2BD
    "4.0\\u20134.9%": c("teal"),         # #005F73
    "5.0\\u20135.9%": c("teal_dark"),    # #003d5c (darkest teal)
    "\\u2265 6.0%":   c("spice"),        # #BB3E03 rusty spice \\u2014 contrasting color so the lone top state (DC) stands out from the teal ramp
}

def _band(v):
    if pd.isna(v):
        return None
    if v < 3.0:
        return "< 3.0%"
    if v < 4.0:
        return "3.0\\u20133.9%"
    if v < 5.0:
        return "4.0\\u20134.9%"
    if v < 6.0:
        return "5.0\\u20135.9%"
    return "\\u2265 6.0%"

geo["rate_band"] = geo["rate"].map(_band)
print("States per band:")
print(geo["rate_band"].value_counts().reindex(BANDS).fillna(0).astype(int).to_string())

render_chart({
    "type": "choropleth",
    "geo": geo,
    "category_col": "rate_band",
    "categories": BANDS,
    "colors": BAND_COLORS,
    "bar_legend_title": "States per band",
    "title": "State unemployment rate \\u2014 trailing 12-month average",
    "subtitle": "Average of monthly rates, Jul 2025 \\u2013 Jul 2026, seasonally adjusted U-3 (LAUS). Wyoming averages 5 months (reports through Dec 2025).",
    "source": "Bureau of Labor Statistics, LAUS, retrieved 2026-09-28",
    "preset": "twitter_landscape",
    "filename": "05_state_map",
})
"""))

# ── Cell 9 — chart 6: selected states over time ──────────────────────────────
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

# ── Cell 10 — summary stats ──────────────────────────────────────────────────
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

# State extremes (trailing 12-month average)
extremes = con.execute(\"\"\"
SELECT state_name, state_abbrev, rate
FROM chart_state_map
WHERE rate = (SELECT MAX(rate) FROM chart_state_map)
   OR rate = (SELECT MIN(rate) FROM chart_state_map)
ORDER BY rate DESC
\"\"\").df()
print("State extremes (trailing 12-month average):")
print(extremes.to_string(index=False))
"""))

# ── Cell 11 — story framing notes ────────────────────────────────────────────
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
A choropleth of each state's trailing 12-month-average rate — a stable map of
geographic inequality (a single-month snapshot was too noisy to mean much).
**→ Good for engagement / state pride reactions.**

**Suggested social lineup (owner to confirm):**
- Chart A: Racial gap line (the lead — structural finding)
- Chart B: U-3 vs U-6 (the "hidden unemployment" angle)
- Chart C: Youth vs overall (the "teens always lose" angle)
- Chart D: State trailing-12-month map (engagement/geographic spread)

⏸ **Build `06-viz-social` only after owner confirms this framing.**
"""))

# ── Cell 12 — cleanup ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/04-viz.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")

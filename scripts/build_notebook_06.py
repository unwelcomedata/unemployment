"""Build 06-viz-social.ipynb for the unemployment project.

06-viz-social is a read-only CONSUMER. The owner confirmed the `04-viz` framing,
so this notebook renders the owner-confirmed 5-chart social lineup
(Charts 2, 3, 4, 5, 7) as publication-ready PNGs in TWO targets from the SAME
prepared data/config:

  - SOCIAL  — `twitter_landscape` (1600x900), full chrome (title/subtitle/source/
              watermark) -> outputs/social/
  - WEB     — `web` preset (1664x936), web_mode=True (drops title/subtitle/source,
              keeps only the @unwelcomedata watermark) -> outputs/web/

It opens `data/project.duckdb` READ-ONLY and reads the chart tables that
`03-prepare` built (chart_u3_u6, chart_race, chart_youth, chart_state_map,
chart_edu_race). It does NOT CREATE TABLE chart_* and does NOT touch 03/04 logic
or the prepared data. The 5 chart configs are copied UNCHANGED in content from
`scripts/build_notebook_04.py`; the only edits are mechanical (drop "db"/"filename",
route through the dual-render helper). Charts 1 (headline) and 6 (selected states)
are NOT in the social lineup and are not rendered.

Authored via nbformat (house convention); execute with nbconvert on the anaconda
`data_projects` kernel (has geopandas 1.1.4 for the choropleth).
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
# 06 — Social (publication charts)

The owner reviewed `04-viz` and **confirmed the framing/lineup**, so this notebook
renders the publication-ready set. 06 is the stage *after* `03-prepare` (which OWNS
the chart data) and `04-viz` (exploration). It is a **read-only CONSUMER**: it opens
`data/project.duckdb` read-only and reads the chart-ready tables `03-prepare` built
(`chart_u3_u6`, `chart_race`, `chart_youth`, `chart_state_map`, `chart_edu_race`). It
does **not** build any `chart_*` table and does not touch 03/04 logic or the prepared
data. The DB is closed in the `## Cleanup` cell.

**Two-target rendering** — each chart is produced in **two targets from the same
config** so they can't drift:

- **Social** — full chrome (title, subtitle, source, `@unwelcomedata` watermark),
  `twitter_landscape` (1600×900) → `outputs/social/`. Optimized for Bluesky/X.
- **Web** — `web_mode=True` (drops title/subtitle/source, keeps only the watermark),
  `web` preset (1664×936) → `outputs/web/`. Embedded on the Pages site, which supplies
  its own headings (see the *Web page lead-in copy* section at the bottom).

**The confirmed 5-chart lineup, renumbered 1–5 for the social set** (the social sequence is
its own numbering — it does NOT inherit the exploration notebook's chart numbers; the
`04-viz` origin is noted in parentheses for traceability):

1. **U-3 vs U-6** (line, 1994–2026): official vs broad unemployment; the gap is "hidden
   unemployment." Two methodology markers (1994 CPS redesign, 2011 duration cap). *(from
   exploration chart 2)*
2. **Racial gap** (line, 1973–2026): the persistent ~2:1 Black/White ratio; Hispanic between
   the two. *(from exploration chart 3)*
3. **Teens (16–19) vs adults 20+** (line, 1948–2026): teen rate runs 2–4× adults. *(from
   exploration chart 4)*
4. **State choropleth** (trailing-12-month average): geographic spread; DC is the lone
   top-band state, shown as a far-right callout under the legend. *(from exploration chart 5)*
5. **Race gap within education level** (clustered vertical columns, workers 25+): the
   companion to social chart 2 — the gap holds at every education level. *(from exploration
   chart 7)*

Output files are numbered `01_`…`05_` accordingly. Titles are **descriptive** (house
default), not conclusion headlines — present the data and let it carry the point. Charts 1
(headline) and 6 (selected states) from exploration are **not** in the social lineup and are
not rendered here.

> **Rendering note.** The project `.venv` is Py3.14 (matplotlib RecursionError), so all
> charts render via the shared **Pillow** factory. Run this notebook on the anaconda
> **`data_projects`** kernel (has geopandas 1.1.4 for the choropleth).
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
from IPython.display import display
from chart_factory import _CHART_TYPES
from colors import c
from viz import PRESETS

DB_PATH = "data/project.duckdb"

# 03-prepare is the writer; 06 only reads. Open read-only.
con = duckdb.connect(DB_PATH, read_only=True)

# Guard: the chart-ready tables for the social lineup must exist (built by 03-prepare).
_tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
_required = ["chart_u3_u6", "chart_race", "chart_youth", "chart_state_map", "chart_edu_race"]
_missing = [t for t in _required if t not in _tables]
assert not _missing, (
    f"Prepared chart tables missing: {_missing}. "
    "Run notebooks/03-prepare.ipynb first (it builds the chart_* tables); 06 only reads them."
)

soc_w, soc_h, _ = PRESETS["twitter_landscape"]   # 1600x900
web_w, web_h, _ = PRESETS["web"]                 # 1664x936
social_out = Path("outputs/social"); social_out.mkdir(parents=True, exist_ok=True)
web_out    = Path("outputs/web");    web_out.mkdir(parents=True, exist_ok=True)
print("Connected (read-only). Prepared tables present:", _required)
print(f"social preset {soc_w}x{soc_h} -> {social_out}  |  web preset {web_w}x{web_h} -> {web_out}")
"""))

# ── Cell 2 — dual-render helper ──────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Dual-render helper

`render_targets` builds the **social** image (full chrome) and the **web** image
(`web_mode=True`, no title/subtitle/source) from **one `base` config**, saves each to its
own directory at the exact preset dimensions, and displays the social image inline.

It calls the shared factory's chart builder directly (`_CHART_TYPES[type](cfg, con)`)
rather than `render_chart`, because `render_chart` → `_export_png` only writes to
`outputs/social`; calling the builder returns the PIL image so the helper can save the
web target to `outputs/web`. Both targets come from the same config, so social and web
can't drift.
"""))
cells.append(nbformat.v4.new_code_cell("""\
def render_targets(num, name, base, *, social=True, web=True,
                   social_img_height=None, web_img_height=None):
    builder = _CHART_TYPES[base["type"]]
    stem = f"{num:02d}_{name}"
    if social:
        cfg = {**base, "preset": "twitter_landscape", "web_mode": False}
        if social_img_height is not None:
            cfg["img_height"] = social_img_height
        img = builder(cfg, con)
        p = social_out / f"{stem}.png"
        img.save(p, format="PNG", optimize=True)
        print(f"social → {p}  ({img.size[0]}x{img.size[1]})")
        display(img)
    if web:
        cfg = {**base, "preset": "web", "web_mode": True,
               "title": "", "subtitle": None, "source": None}
        if web_img_height is not None:
            cfg["img_height"] = web_img_height
        imgw = builder(cfg, con)
        pw = web_out / f"{stem}.png"
        imgw.save(pw, format="PNG", optimize=True)
        print(f"web    → {pw}  ({imgw.size[0]}x{imgw.size[1]})")

print("helper ready")
"""))

# ── Chart 2 — U-3 vs U-6 ─────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Social chart 1 — Official vs broad unemployment (U-3 vs U-6), 1994–2026
*(exploration chart 2)*

U-3 (official, teal) vs U-6 (broad, navy). The gap between them is the "hidden
unemployment" — discouraged/marginally-attached workers plus involuntary part-timers.
Two vertical markers flag **measurement changes, not conclusions**: **1994** (the CPS
redesign that introduced U-4–U-6, which is why U-6 begins in 1994) and **2011** (the
jobless-duration cap was raised from ~2 to ~5 years — a duration-variable change, not a
redefinition of who counts as unemployed). Config copied unchanged from `04-viz`.
"""))
cells.append(nbformat.v4.new_code_cell("""\
chart2 = {
    "type": "line",
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
}
render_targets(1, "u3_vs_u6", chart2)
"""))

# ── Chart 3 — racial gap ─────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Social chart 2 — Unemployment rate by race/ethnicity, 1973–2026
*(exploration chart 3)*

White (teal_mid), Hispanic (gold), Black (navy). Black unemployment has run ~2× White
unemployment in every year on record; the ratio is more stable than the absolute levels.
**Interpretation (option B, cited):** the gap is attributed mainly to labor-market
discrimination and occupational segregation, not education — it holds at every education
level, and hiring-audit studies find no decline since 1989 (BLS CPS; EPI 2015, 2019;
Quillian et al. PNAS 2017; Fed FEDS 2017-071). **Series starts differ:** Black 1972,
Hispanic 1973 (comparable from 1973).

**Methodology markers added (this stage):** two vertical dashed markers flag
measurement changes shared with social chart 1 — **1994** (CPS redesign: new
job-search/duration questions) and **2011** (jobless-duration cap raised ~2→~5 yrs).
Both fall inside the 1973–2026 range. The chart's footnote now carries BOTH the
race-gap attribution/citations AND the marker explanation.
"""))
cells.append(nbformat.v4.new_code_cell("""\
chart3 = {
    "type": "line",
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
    "vlines": [
        {"x": 1994, "label": "1994 CPS redesign"},
        {"x": 2011, "label": "2011 duration cap"},
    ],
    "title": "Unemployment rate by race/ethnicity, 1973\\u20132026",
    "subtitle": "Annual average U-3, seasonally adjusted. Black series begins 1972, Hispanic 1973.",
    "source": "Gap attributed mainly to labor-market discrimination and occupational segregation, not education (holds at every education level). Sources: BLS CPS; EPI 2015, 2019; Quillian et al. PNAS 2017; Fed FEDS 2017-071. Markers: 1994 CPS redesign introduced U-4\\u2013U-6 and new job-search/duration questions; 2011 raised the max recorded jobless-duration from ~2 to ~5 years. Retrieved 2026-09-28.",
}
render_targets(2, "race_gap", chart3)
"""))

# ── Chart 4 — teens vs adults 20+ ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Social chart 3 — Teens (16–19) vs adults 20+ unemployment, 1948–2026
*(exploration chart 4)*

Teen 16–19 (brown_red) vs **Workers 20+** (teal) — the real combined-sex adult total, BLS
series `LNS14000024`, deliberately excluding teens so the teen line is contrasted against
adults only. The teen rate runs 2–4× the adult rate in every year on record.
**Labor-force caveat:** the rate is unemployed as a share of the *labor force* (people
working or actively looking in the last 4 weeks), **not** of all teens — most teens are in
school and not in the labor force, so this is not "X% of all teenagers are out of work."

**Methodology markers added (this stage):** the identical **1994** (CPS redesign) and
**2011** (jobless-duration cap raised ~2→~5 yrs) vertical markers shared with social
charts 1 and 2. Both fall inside the 1948–2026 range. The footnote now carries BOTH the
labor-force caveat AND the marker explanation.
"""))
cells.append(nbformat.v4.new_code_cell("""\
chart4 = {
    "type": "line",
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
    "vlines": [
        {"x": 1994, "label": "1994 CPS redesign"},
        {"x": 2011, "label": "2011 duration cap"},
    ],
    "title": "Teen (16\\u201319) vs adults 20+ unemployment, 1948\\u20132026",
    "subtitle": "Annual average U-3, seasonally adjusted. Adults 20+ = BLS series LNS14000024 (real combined-sex adult total). Teen rate runs 2\\u20134\\u00d7 the adult rate in every year on record.",
    "source": "Rate = unemployed as a share of the labor force (working or actively looking), not of all teens; most teens are not in the labor force. Markers: 1994 CPS redesign introduced U-4\\u2013U-6 and new job-search/duration questions; 2011 raised the max recorded jobless-duration from ~2 to ~5 years. Bureau of Labor Statistics, CPS, retrieved 2026-09-28",
}
render_targets(3, "youth_vs_adults", chart4)
"""))

# ── Chart 5 — state choropleth ───────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Social chart 4 — State unemployment rate, trailing 12-month average (choropleth)
*(exploration chart 5)*

Each state is shaded by its **average rate over the trailing 12 months** (Jul 2025 –
Jul 2026; note 2025-10 is absent, so the 12 distinct periods span 13 calendar months).
50 of 51 states have all 12 months; **Wyoming** reports only through Dec 2025 (5 months).
The continuous average is binned into five readable rate bands shaded light→dark, with the
`≥ 6.0%` band in a contrasting **spice** color so the lone top-band state stands out from
the teal ramp. **DC** is the only `≥ 6.0%` state and is rendered by the shared template as
a far-right callout under the legend bars, connected by a leader line.

The geopandas merge + banding below is **presentation** (it stays in the consumer, same as
`04-viz`); the per-state rate dataset itself is the prepared `chart_state_map` table from
`03-prepare`. The render config is copied unchanged from `04-viz`.
"""))
cells.append(nbformat.v4.new_code_cell("""\
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

chart5 = {
    "type": "choropleth",
    "geo": geo,
    "category_col": "rate_band",
    "categories": BANDS,
    "colors": BAND_COLORS,
    "bar_legend_title": "States per band",
    "title": "State unemployment rate \\u2014 trailing 12-month average",
    "subtitle": "Average of monthly rates, Jul 2025 \\u2013 Jul 2026, seasonally adjusted U-3 (LAUS). Wyoming averages 5 months (reports through Dec 2025).",
    "source": "Bureau of Labor Statistics, LAUS, retrieved 2026-09-28",
}
render_targets(4, "state_map", chart5)
"""))

# ── Chart 7 — race gap within education ──────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Social chart 5 — Unemployment rate by race within education level, workers 25+
*(exploration chart 7)*

The **companion to Chart 3**: a clustered vertical-column chart (four education tiers, two
adjacent columns per tier — White = teal_mid, Black = navy) answering *"isn't the gap just
an education gap?"* In every tier the Black column is taller — a Black worker with a
bachelor's degree has about the same rate as a White worker with no college. Education does
not close the gap.

**Grain note:** this is **not** the monthly SA series behind the other charts. It comes from
BLS annual table **cpsaat07** — an **annual average, workers 25+, not seasonally adjusted**
(2024). The subtitle states this so the series are never conflated.

The long/tidy reshape below is read-only presentation of the prepared `chart_edu_race`
table; the chart's own `source=` line carries the gap-attribution + citations, so the PNG
is self-contained.

**Chartjunk removed + legend moved (this stage):** each column already prints its value
atop the bar, so the **left y-axis** (tick labels + rotated title) and the **horizontal
gridlines** are redundant and are now **suppressed** (`show_y_axis=False`,
`show_gridlines=False` — new backward-compatible opt-outs on `grouped_column_bars`,
defaulting to the old behavior for every other caller). The shared **baseline rule** under
the columns stays (it is the column baseline, not a gridline). The **legend** moved from a
far-right stack to a **horizontal row at the top** (`legend_pos="top"`).
"""))
cells.append(nbformat.v4.new_code_cell("""\
EDU_ORDER = [
    "Less than high school",
    "High school, no college",
    "Some college or associate degree",
    "Bachelor's degree and higher",
]

# Long/tidy: one row per (education tier, race). Natural tier order (NOT value sorted),
# White then Black. Reads the prepared chart_edu_race table (built in 03-prepare).
edu_df = con.execute(\"\"\"
    SELECT education_level AS tier, race AS series, unemployment_rate AS value
    FROM chart_edu_race
    WHERE race IN ('White', 'Black')
    ORDER BY education_order, CASE race WHEN 'White' THEN 0 ELSE 1 END
\"\"\").df()

chart7 = {
    "type": "grouped_column_bars",            # alias: "clustered_bars"
    "table": edu_df,                           # inline DataFrame (factory accepts df)
    "category_col": "tier",
    "value_col": "value",
    "series_col": "series",
    "series": [{"key": "White", "label": "White", "color": c("teal_mid")},
               {"key": "Black", "label": "Black", "color": c("navy")}],
    "category_order": EDU_ORDER,               # natural education order, NOT value-sorted
    "legend": [{"label": "White", "color": c("teal_mid")},
               {"label": "Black", "color": c("navy")}],
    "legend_pos": "top",
    "show_y_axis": False,
    "show_gridlines": False,
    "y_axis_label": "Unemployment rate (%)",
    "value_label_fmt": lambda v: f"{v:.1f}%",
    "label_wrap": 18,
    "title": "Unemployment rate by race within education level, workers 25+",
    "subtitle": "U.S. annual-average unemployment rate, 2024 \\u00b7 people 25 and older \\u00b7 "
                "Source: BLS Current Population Survey, table cpsaat07",
    "source": "Gap attributed mainly to labor-market discrimination and occupational segregation, not education (it holds at every education level); hiring-audit studies find no decline since 1989. Sources: BLS CPS, table cpsaat07; EPI 2015, 2019; Quillian et al. PNAS 2017; Fed FEDS 2017-071.",
}
render_targets(5, "race_gap_by_education", chart7)
"""))

# ── Web page lead-in copy (info preservation) ────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Web page lead-in copy

Web mode **drops the title, subtitle, and source** from each chart (it keeps only the
`@unwelcomedata` watermark). Any fact that lived *only* in that chrome must be stated in the
Pages README prose **above** the chart, or it is silently lost. Paste the per-chart copy
below next to each web chart on the Pages site. (This section is written here; it does not
build the README.)

**Social chart 1 — U-3 vs U-6** (`01_u3_vs_u6.png`)
- **U-3 (official):** jobless, available, and actively looked in the last 4 weeks, as a
  share of the labor force. **U-6 (broad):** adds discouraged/marginally-attached workers
  plus involuntary part-timers. The gap between the two lines is "hidden unemployment."
- **1994 marker = CPS redesign:** introduced U-4–U-6 and new job-search/duration questions
  (why U-6 starts in 1994). **2011 marker = duration cap:** the max recorded jobless-duration
  was raised from ~2 to ~5 years — a measurement-variable change, not a redefinition of who
  is counted as unemployed. Both are measurement changes, not conclusions.
- Annual average. Source: BLS CPS, retrieved 2026-09-28.

**Social chart 2 — Racial gap** (`02_race_gap.png`)
- Lines: White, Hispanic, Black. Annual average U-3, seasonally adjusted.
- **Series starts differ:** Black 1972, Hispanic 1973 (comparable from 1973).
- **1994 & 2011 markers:** two vertical dashed markers flag measurement changes, not
  conclusions. **1994 = CPS redesign** (introduced U-4–U-6 and new job-search/duration
  questions). **2011 = duration cap** (max recorded jobless-duration raised from ~2 to ~5
  years — a measurement-variable change, not a redefinition of who counts as unemployed).
- **Interpretation:** the persistent ~2:1 Black/White gap is attributed mainly to
  labor-market discrimination and occupational segregation, **not** education — it holds at
  every education level and hiring-audit studies find no decline since 1989. Sources: BLS
  CPS; EPI 2015, 2019; Quillian et al. PNAS 2017; Fed FEDS 2017-071.

**Social chart 3 — Teens vs adults 20+** (`03_youth_vs_adults.png`)
- Lines: Teen (16–19) and **Workers 20+**. "Workers 20+" = BLS series **`LNS14000024`** (the
  real combined-sex adult total, excluding teens). Annual average U-3, seasonally adjusted.
- **Labor-force caveat:** the rate is unemployed as a share of the **labor force** (people
  working or actively looking), **not** of all teens. Most teens are in school and not in the
  labor force, so this is not "X% of all teenagers are out of work." Teen rate runs 2–4× the
  adult rate in every year on record. Source: BLS CPS.
- **1994 & 2011 markers:** same two measurement-change markers as chart 2 — **1994 = CPS
  redesign** (new job-search/duration questions), **2011 = duration cap** (max recorded
  jobless-duration raised ~2→~5 years). Measurement changes, not conclusions.

**Social chart 4 — State choropleth** (`04_state_map.png`)
- **Trailing 12-month AVERAGE** of each state's monthly rate, window **Jul 2025 – Jul 2026**
  (12 distinct monthly periods; 2025-10 is absent so they span 13 calendar months).
- Seasonally-adjusted **U-3 (LAUS)**. **Wyoming** averages only 5 months (reports through
  Dec 2025). Shaded in five rate bands.
- **DC** is the lone **`≥ 6.0%`** state, shown as the far-right callout under the legend.
  Source: BLS LAUS, retrieved 2026-09-28.

**Social chart 5 — Race gap within education** (`05_race_gap_by_education.png`)
- Groups shown: **White vs Black**, by four education tiers, **workers 25+**.
- **Grain:** this is a **2024 ANNUAL average, not seasonally adjusted**, from BLS table
  **`cpsaat07`** — distinct from the monthly seasonally-adjusted series behind the other
  charts. Do not conflate.
- The Black column is taller in every tier — the gap holds at every education level.
  Attributed mainly to labor-market discrimination and occupational segregation, not
  education. Sources: BLS CPS cpsaat07; EPI 2015, 2019; Quillian et al. PNAS 2017; Fed FEDS
  2017-071.
"""))

# ── Cleanup ──────────────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/06-viz-social.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")

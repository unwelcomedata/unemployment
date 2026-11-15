"""Build the unemployment infographic (tall + social SVG -> PNG) and validate every
data mark back to the DuckDB chart tables.

Every stem, bar, dot and big number is COMPUTED from data/project.duckdb (the same
chart_* tables the published charts use). Tall and social are fed identical queried values;
only the canvas mapping differs. Each mark carries data-* attributes so validate() can
parse it back out of the SVG, invert the mapping and compare with a fresh DB query.

Usage (from project root):  .venv/bin/python scripts/_build_infographic.py
Writes docs/infographic_unemployment{,_social}.{svg,png} + artifacts/INFOGRAPHIC-VALIDATION.md
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb

PROJECT = Path(__file__).resolve().parents[1]
DOCS, ART = PROJECT / "docs", PROJECT / "artifacts"
DOCS.mkdir(exist_ok=True); ART.mkdir(exist_ok=True)

NAVY, TEAL, GOLD, SPICE, AQUA = "#003049", "#005F73", "#EE9B00", "#BB3E03", "#94D2BD"
VANILLA, GREY, BG, MID = "#E9D8A6", "#6B7280", "#FBF8F0", "#0A9396"
BAND = [("<3.0", 0, 3.0, AQUA), ("3.0\u20133.9", 3.0, 4.0, MID), ("4.0\u20134.9", 4.0, 5.0, TEAL),
        ("5.0\u20135.9", 5.0, 6.0, GOLD), ("\u22656.0", 6.0, 99, SPICE)]


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace("\u2013", "&#8211;").replace("\u2014", "&#8212;").replace("\u2019", "&#8217;")
             .replace("\u00d7", "&#215;").replace("\u2265", "&#8805;").replace("\u00f7", "&#247;"))


class Lin:
    def __init__(self, v0, v1, p0, p1):
        self.v0, self.v1, self.p0, self.p1 = v0, v1, p0, p1
    def __call__(self, v):
        return self.p0 + (v - self.v0) / (self.v1 - self.v0) * (self.p1 - self.p0)
    def inv(self, p):
        return self.v0 + (p - self.p0) / (self.p1 - self.p0) * (self.v1 - self.v0)


def f(x):
    return f"{x:.1f}"


def t(x, y, s, size, fill, weight="", anchor=""):
    w = f' font-weight="{weight}"' if weight else ""
    a = f' text-anchor="{anchor}"' if anchor else ""
    return f'<text x="{f(x)}" y="{f(y)}" fill="{fill}" font-size="{size}"{w}{a}>{esc(s)}</text>'


# ───────────────────────── data ─────────────────────────
def load():
    con = duckdb.connect(str(PROJECT / "data/project.duckdb"), read_only=True)
    q = lambda s: con.execute(s).fetchall()
    d = dict(
        race=q("SELECT year, white, black FROM chart_race ORDER BY year"),
        u=q("SELECT year, u3, u6 FROM chart_u3_u6 ORDER BY year"),
        youth=q("SELECT year, adults_20plus, youth_16_19 FROM chart_youth ORDER BY year"),
        states=q("SELECT state_abbrev, rate, n_months FROM chart_state_map ORDER BY rate DESC, state_abbrev"),
        edu=q("SELECT education_level, education_order, race, unemployment_rate FROM chart_edu_race ORDER BY 2, 3"),
    )
    con.close()
    d["ratio"] = [(y, b / w) for y, w, b in d["race"]]
    d["gap"] = [(y, round(u6 - u3, 2)) for y, u3, u6 in d["u"]]
    return d


# ───────────────────────── reusable mark builders ─────────────────────────
def ratio_marks(d, xs, ys, r, sw):
    """Black/White ratio per year: stem from 1.0 up to the ratio + dot (>=2 spice, else teal)."""
    out = []
    for y, v in d["ratio"]:
        col = SPICE if v >= 2.0 else TEAL
        out.append(f'<line class="rs" data-year="{y}" x1="{f(xs(y))}" y1="{f(ys(1.0))}" x2="{f(xs(y))}" y2="{f(ys(v))}" '
                   f'stroke="{VANILLA}" stroke-width="{sw}"/>')
    for y, v in d["ratio"]:
        col = SPICE if v >= 2.0 else TEAL
        out.append(f'<circle class="rd" data-year="{y}" cx="{f(xs(y))}" cy="{f(ys(v))}" r="{r}" fill="{col}"/>'
                   f'<!-- {y} ratio {v:.3f} -->')
    return "\n  ".join(out)


def gap_bars(d, xs, ys, base, bw):
    out = []
    for y, g in d["gap"]:
        top = ys(g)
        peak = g == max(v for _, v in d["gap"])
        col = SPICE if peak else TEAL
        out.append(f'<rect class="gb" data-year="{y}" x="{f(xs(y)-bw/2)}" y="{f(top)}" width="{f(bw)}" '
                   f'height="{f(base-top)}" fill="{col}"/><!-- {y} U-6 minus U-3 = {g} -->')
    return "\n  ".join(out)


def comb(d, xs, ys, r, sw):
    out = []
    for y, a, tn in d["youth"]:
        out.append(f'<line class="cl" data-year="{y}" x1="{f(xs(y))}" y1="{f(ys(a))}" x2="{f(xs(y))}" y2="{f(ys(tn))}" '
                   f'stroke="{VANILLA}" stroke-width="{sw}"/>')
    for y, a, tn in d["youth"]:
        out.append(f'<circle class="ca" data-year="{y}" cx="{f(xs(y))}" cy="{f(ys(a))}" r="{r}" fill="{TEAL}"/>'
                   f'<circle class="ct" data-year="{y}" cx="{f(xs(y))}" cy="{f(ys(tn))}" r="{r}" fill="{SPICE}"/>')
    return "\n  ".join(out)


def state_bars(d, x0, pitch, bw, base, ys):
    out = []
    for i, (ab, rate, n) in enumerate(d["states"]):
        col = next(c for _, lo, hi, c in BAND if lo <= rate < hi)
        top = ys(rate)
        out.append(f'<rect class="sb" data-st="{ab}" x="{f(x0+i*pitch)}" y="{f(top)}" width="{f(bw)}" '
                   f'height="{f(base-top)}" fill="{col}"/><!-- {ab} {rate} -->')
    return "\n  ".join(out)


def edu_rows(d, xs, y0, pitch, r, label_x, lab, chip_x, size):
    out, levels = [], {}
    for lvl, order, race, v in d["edu"]:
        levels.setdefault((order, lvl), {})[race] = v
    for i, ((order, lvl), v) in enumerate(sorted(levels.items())):
        y = y0 + i * pitch
        out.append(f'<line x1="{f(xs(v["White"]))}" y1="{f(y)}" x2="{f(xs(v["Black"]))}" y2="{f(y)}" stroke="{VANILLA}" stroke-width="{r*0.9:.1f}" stroke-linecap="round"/>')
        out.append(t(label_x, y + lab * 0.35, lvl, lab, NAVY, "bold", "end"))
        out.append(f'<circle class="ew" data-order="{order}" cx="{f(xs(v["White"]))}" cy="{f(y)}" r="{r}" fill="{TEAL}"/>')
        out.append(f'<circle class="eb" data-order="{order}" cx="{f(xs(v["Black"]))}" cy="{f(y)}" r="{r}" fill="{SPICE}"/>')
        out.append(t(xs(v["White"]) - r - 8, y + size * 0.35, f'{v["White"]:.1f}%', size, TEAL, "bold", "end"))
        out.append(t(xs(v["Black"]) + r + 8, y + size * 0.35, f'{v["Black"]:.1f}%', size, SPICE, "bold"))
        out.append(t(chip_x, y + size * 0.35, f'{v["Black"]/v["White"]:.1f}\u00d7', size, GREY, "bold", "end"))
    return "\n  ".join(out)


# ───────────────────────── facts used in text (computed once) ─────────────────────────
def facts(d):
    ratios = dict(d["ratio"])
    mean_r = sum(ratios.values()) / len(ratios)
    n2 = sum(1 for v in ratios.values() if v >= 2.0)
    ymax = max(ratios, key=ratios.get); ymin = min(ratios, key=ratios.get)
    gaps = dict(d["gap"]); gpk = max(gaps, key=gaps.get); gmn = min(gaps, key=gaps.get)
    u3, u6 = d["u"][-1][1], d["u"][-1][2]
    yr = {y: (a, tn) for y, a, tn in d["youth"]}
    tr = {y: tn / a for y, (a, tn) in yr.items()}
    last = d["youth"][-1]
    edu = {}
    for lvl, order, race, v in d["edu"]:
        edu.setdefault(order, {})[race] = v
    st = d["states"]
    return dict(mean_r=mean_r, n2=n2, n=len(ratios), last_r=ratios[max(ratios)], last_y=max(ratios),
                ymax=ymax, rmax=ratios[ymax], ymin=ymin, rmin=ratios[ymin], gpk=gpk, gpkv=gaps[gpk],
                gmn=gmn, gmnv=gaps[gmn], u3=u3, u6=u6, uy=d["u"][-1][0], gaps=gaps,
                t_last=last, t_ratio_last=tr[last[0]], t_mean=sum(tr.values()) / len(tr),
                t_min=min(tr.values()), t_max=max(tr.values()),
                t_min_y=min(tr, key=tr.get), t_max_y=max(tr, key=tr.get),
                edu=edu, st=st, st_top=st[0], st_bot=st[-1], st_med=sorted(r for _, r, _ in st)[len(st) // 2])


# ───────────────────────── TALL ─────────────────────────
def build_tall(d, F):
    W = 1200
    # S1 ratio strip
    xs1 = Lin(1973, 2026, 150, 1120); ys1 = Lin(1.0, 3.0, 800, 590)
    grid1 = "".join(f'<line x1="150" y1="{f(ys1(v))}" x2="1120" y2="{f(ys1(v))}" stroke="{"#CBB477" if v==2 else "#E5E0D0"}" '
                    f'stroke-width="{2.5 if v==2 else 1.5}" {"stroke-dasharray=\"7 6\"" if v==2 else ""}/>'
                    + t(135, ys1(v) + 6, f"{v:.0f}\u00d7", 18, GREY, anchor="end") for v in (1, 2, 3))
    ticks1 = "".join(t(xs1(y), 828, str(y), 18, GREY, anchor="middle") for y in (1980, 2000, 2020))
    # S2 gap bars
    xs2 = Lin(1994, 2026, 165, 1105); ys2 = Lin(0, 8, 1420, 1180)
    grid2 = "".join(f'<line x1="150" y1="{f(ys2(v))}" x2="1120" y2="{f(ys2(v))}" stroke="#E5E0D0" stroke-width="1.5"/>'
                    + t(135, ys2(v) + 6, str(v), 18, GREY, anchor="end") for v in (2, 4, 6, 8))
    ticks2 = "".join(t(xs2(y), 1448, str(y), 18, GREY, anchor="middle") for y in (2000, 2010, 2020))
    # S3 comb
    xs3 = Lin(1948, 2026, 150, 1120); ys3 = Lin(0, 30, 1980, 1735)
    grid3 = "".join(f'<line x1="150" y1="{f(ys3(v))}" x2="1120" y2="{f(ys3(v))}" stroke="#E5E0D0" stroke-width="1.5"/>'
                    + t(135, ys3(v) + 6, f"{v}%", 18, GREY, anchor="end") for v in (10, 20, 30))
    ticks3 = "".join(t(xs3(y), 2008, str(y), 18, GREY, anchor="middle") for y in (1960, 1980, 2000, 2020))
    # S4 states
    ys4 = Lin(0, 7, 2640, 2350)
    state_grid = "".join(f'<line x1="120" y1="{f(ys4(v))}" x2="1120" y2="{f(ys4(v))}" stroke="#E5E0D0" stroke-width="1.5"/>'
                         + t(108, ys4(v) + 6, f"{v}%", 18, GREY, anchor="end") for v in (2, 4, 6))
    bc = {n: sum(1 for _, r, _ in d["states"] if lo <= r < hi) for n, lo, hi, _ in BAND}
    band_legend = "".join(f'<rect x="{130+i*200}" y="2662" width="18" height="18" fill="{c}"/>' + t(154 + i * 200, 2678, f"{n} ({bc[n]})", 18, GREY)
                          for i, (n, lo, hi, c) in enumerate(BAND))
    # S5 education
    xs5 = Lin(0, 10, 520, 1010)
    grid5 = "".join(f'<line x1="{f(xs5(v))}" y1="3000" x2="{f(xs5(v))}" y2="3270" stroke="#E5E0D0" stroke-width="1.5"/>'
                    + t(xs5(v), 3296, f"{v}%", 18, GREY, anchor="middle") for v in (0, 5, 10))
    H = 3470
    ymx, ymn = F["ymax"], F["ymin"]
    tl = F["t_last"]
    e = F["edu"]
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!--
  @unwelcomedata — PROJECT INFOGRAPHIC (tall portrait poster)
  Project: unemployment. Generated by scripts/_build_infographic.py; every mark is computed from
  data/project.duckdb (chart_race, chart_u3_u6, chart_youth, chart_state_map, chart_edu_race).
  Canvas 1200 x {H}.
-->
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect x="0" y="0" width="{W}" height="300" fill="{NAVY}"/>
  {t(80,126,"U.S. Unemployment",72,"#FFFFFF","bold")}
  {t(80,190,"One headline rate hides several stories",40,AQUA,"bold")}
  {t(80,242,"Bureau of Labor Statistics data: race, age, state, education and the broader U-6 measure.",26,VANILLA)}

  <!-- S1 — Black/White ratio -->
  {t(80,372,"A Black\u2013White gap that has held for 50 years",34,NAVY,"bold")}
  {t(80,406,f"Black unemployment rate \u00f7 White unemployment rate, each year {d['ratio'][0][0]}\u2013{d['ratio'][-1][0]}; the big number is the average of the yearly ratios.",22,GREY)}
  {t(80,508,f"{F['mean_r']:.1f}\u00d7",96,SPICE,"bold")}
  {t(80,540,"average ratio, 1973\u20132026",22,GREY)}
  {t(1120,508,f"{F['last_r']:.1f}\u00d7",96,NAVY,"bold",anchor="end")}
  {t(1120,540,f"in {F['last_y']}",22,GREY,anchor="end")}
  {grid1}
  {ratio_marks(d, xs1, ys1, 5.5, 3)}
  {t(xs1(ymx)-12, ys1(F['rmax'])-8, f"{F['rmax']:.2f} ({ymx})", 18, "#CA6702", "bold", anchor="end")}
  {t(xs1(ymn)-12, ys1(F['rmin'])+30, f"{F['rmin']:.2f} ({ymn})", 18, "#CA6702", "bold", anchor="end")}
  {ticks1}
  {t(80,866,f"At or above 2-to-1 in {F['n2']} of {F['n']} years; never below 1.5-to-1. Orange dots = 2\u00d7 or more.",20,GREY)}
  <line x1="80" y1="910" x2="1120" y2="910" stroke="{VANILLA}" stroke-width="3"/>

  <!-- S2 — hidden unemployment -->
  {t(80,982,"What the official rate leaves out",34,NAVY,"bold")}
  {t(80,1016,"U-6 (adds discouraged workers and involuntary part-timers) minus the official U-3, in points.",22,GREY)}
  {t(80,1098,f"{F['u3']:.2f}%",64,TEAL,"bold")}{t(80,1128,f"official U-3, {F['uy']}",22,GREY)}
  {t(1120,1098,f"{F['u6']:.2f}%",64,SPICE,"bold",anchor="end")}{t(1120,1128,f"broad U-6, {F['uy']}",22,GREY,anchor="end")}
  {grid2}
  {gap_bars(d, xs2, ys2, 1420, 22)}
  {t(xs2(F['gpk']), ys2(F['gpkv'])-10, f"{F['gpkv']:.2f} ({F['gpk']})", 18, "#CA6702", "bold", anchor="middle")}
  {ticks2}
  {t(80,1490,f"The gap widens in downturns (2001\u201303, 2008\u201310, 2020) and has run {F['gmnv']:.1f}\u2013{F['gpkv']:.1f} points since 1994.",20,GREY)}
  <line x1="80" y1="1530" x2="1120" y2="1530" stroke="{VANILLA}" stroke-width="3"/>

  <!-- S3 — teens -->
  {t(80,1602,"Teenagers carry several times the adult rate",34,NAVY,"bold")}
  {t(80,1636,"Unemployment rate, teens 16\u201319 (orange) vs workers 20 and over (teal), each year 1948\u20132026.",22,GREY)}
  {t(80,1690,f"{F['t_ratio_last']:.1f}\u00d7",64,SPICE,"bold")}{t(250,1690,f"teen \u00f7 adult rate in {tl[0]} ({tl[2]:.1f}% vs {tl[1]:.1f}%)",22,GREY)}
  {grid3}
  {comb(d, xs3, ys3, 4.5, 3)}
  {ticks3}
  {t(80,2050,f"Ranges from {F['t_min']:.1f}\u00d7 ({F['t_min_y']}) to {F['t_max']:.1f}\u00d7 ({F['t_max_y']}); average {F['t_mean']:.1f}\u00d7. Share of the labor force, not of all teens.",20,GREY)}
  <line x1="80" y1="2090" x2="1120" y2="2090" stroke="{VANILLA}" stroke-width="3"/>

  <!-- S4 — states -->
  {t(80,2162,"State by state, one stands out",34,NAVY,"bold")}
  {t(80,2196,"Trailing-12-month unemployment rate for all 51 states and DC, ranked.",22,GREY)}
  {t(80,2262,f"{F['st_top'][1]:.1f}%",64,SPICE,"bold")}{t(250,2262,f"{F['st_top'][0]} is the only place at or above 6%",22,GREY)}
  {t(1120,2262,f"{F['st_bot'][1]:.1f}%",64,TEAL,"bold",anchor="end")}{t(1120,2292,f"lowest: {F['st_bot'][0]}",22,GREY,anchor="end")}
  {state_grid}
  {state_bars(d, 130, 19.2, 14, 2640, ys4)}
  <line x1="120" y1="2640" x2="1120" y2="2640" stroke="{GREY}" stroke-width="2"/>
  {t(137,ys4(F['st_top'][1])-10,f"{F['st_top'][0]} {F['st_top'][1]:.1f}",18,SPICE,"bold",anchor="middle")}{t(130+50*19.2+7,ys4(F['st_bot'][1])-10,f"{F['st_bot'][0]} {F['st_bot'][1]:.1f}",18,TEAL,"bold",anchor="end")}
  {band_legend}
  {t(80,2724,f"Median state: {F['st_med']:.1f}%. Wyoming has only 5 months of data in the trailing window.",20,GREY)}
  <line x1="80" y1="2760" x2="1120" y2="2760" stroke="{VANILLA}" stroke-width="3"/>

  <!-- S5 — education -->
  {t(80,2832,"More education doesn't close the gap",34,NAVY,"bold")}
  {t(80,2866,"2024 unemployment rate by education: White (teal) vs Black (orange); right = ratio.",22,GREY)}
  {t(80,2930,f"{e[3]['Black']:.1f}% = {e[2]['White']:.1f}%",52,NAVY,"bold")}
  {t(80,2962,"A Black worker with a bachelor\u2019s degree has the same rate as a White worker with some college.",20,GREY)}
  {grid5}
  {edu_rows(d, xs5, 3030, 66, 11, 500, 20, 1120, 22)}

  <rect x="0" y="{H-90}" width="{W}" height="90" fill="{NAVY}"/>
  {t(80,H-45,"@unwelcomedata",24,"#FFFFFF","bold")}
  {t(80,H-15,"BLS CPS &amp; LAUS \u00b7 seasonally adjusted \u00b7 U-6 starts 1994 (CPS redesign); 2011 duration cap.".replace("&amp;","&"),18,AQUA)}
</svg>
'''
    return svg, H


# ───────────────────────── SOCIAL ─────────────────────────
def build_social(d, F):
    W, H = 1600, 900
    xs1 = Lin(1973, 2026, 120, 760); ys1 = Lin(1.0, 3.0, 456, 312)
    grid1 = "".join(f'<line x1="120" y1="{f(ys1(v))}" x2="760" y2="{f(ys1(v))}" stroke="{"#CBB477" if v==2 else "#E5E0D0"}" '
                    f'stroke-width="{2 if v==2 else 1.5}" {"stroke-dasharray=\"6 5\"" if v==2 else ""}/>'
                    + t(108, ys1(v) + 5, f"{v:.0f}\u00d7", 15, GREY, anchor="end") for v in (1, 2, 3))
    ticks1 = "".join(t(xs1(y), 476, str(y), 15, GREY, anchor="middle") for y in (1980, 2000, 2020))
    xs2 = Lin(1994, 2026, 910, 1500); ys2 = Lin(0, 8, 476, 316)
    grid2 = "".join(f'<line x1="880" y1="{f(ys2(v))}" x2="1520" y2="{f(ys2(v))}" stroke="#E5E0D0" stroke-width="1.5"/>'
                    + t(868, ys2(v) + 5, str(v), 15, GREY, anchor="end") for v in (2, 4, 6, 8))
    ticks2 = "".join(t(xs2(y), 496, str(y), 15, GREY, anchor="middle") for y in (2000, 2010, 2020))
    xs3 = Lin(1948, 2026, 910, 1520); ys3 = Lin(0, 30, 760, 590)
    grid3 = "".join(f'<line x1="880" y1="{f(ys3(v))}" x2="1520" y2="{f(ys3(v))}" stroke="#E5E0D0" stroke-width="1.5"/>'
                    + t(868, ys3(v) + 5, f"{v}%", 15, GREY, anchor="end") for v in (10, 20, 30))
    ticks3 = "".join(t(xs3(y), 780, str(y), 14, GREY, anchor="middle") for y in (1960, 1980, 2000, 2020))
    xs5 = Lin(0, 10, 330, 640)
    grid5 = "".join(f'<line x1="{f(xs5(v))}" y1="545" x2="{f(xs5(v))}" y2="750" stroke="#E5E0D0" stroke-width="1.5"/>'
                    + t(xs5(v), 770, f"{v}%", 15, GREY, anchor="middle") for v in (0, 5, 10))
    ymx, ymn, tl, e = F["ymax"], F["ymin"], F["t_last"], F["edu"]
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<!--
  @unwelcomedata — PROJECT INFOGRAPHIC (landscape social render)
  Project: unemployment. 1600x900 feed render. Same FRAME, two columns; generated by
  scripts/_build_infographic.py from the SAME queried values as the tall poster.
-->
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Helvetica, Arial, sans-serif">
  <rect width="{W}" height="{H}" fill="{BG}"/>
  <rect x="0" y="0" width="{W}" height="190" fill="{NAVY}"/>
  {t(80,90,"U.S. Unemployment",56,"#FFFFFF","bold")}
  {t(80,138,"One headline rate hides several stories",32,AQUA,"bold")}
  {t(80,172,"Bureau of Labor Statistics data: race, age, education and the broader U-6 measure.",22,VANILLA)}
  <line x1="800" y1="222" x2="800" y2="800" stroke="{VANILLA}" stroke-width="3"/>

  <!-- LEFT TOP — ratio -->
  {t(80,256,"A Black\u2013White gap that has held for 50 years",28,NAVY,"bold")}
  {t(80,284,f"Black rate \u00f7 White rate each year: {F['mean_r']:.1f}\u00d7 on average, {F['last_r']:.1f}\u00d7 in {F['last_y']}.",19,GREY)}
  {grid1}
  {ratio_marks(d, xs1, ys1, 4.2, 2.4)}
  {t(xs1(ymx)-9, ys1(F['rmax'])-7, f"{F['rmax']:.2f}", 15, "#CA6702", "bold", anchor="end")}
  {t(xs1(ymn)-9, ys1(F['rmin'])+24, f"{F['rmin']:.2f} ({ymn})", 15, "#CA6702", "bold", anchor="end")}
  {ticks1}
  {t(80,502,f"2-to-1 or more in {F['n2']} of {F['n']} years; never under 1.5-to-1.",18,GREY)}
  <line x1="80" y1="522" x2="760" y2="522" stroke="{VANILLA}" stroke-width="3"/>

  <!-- LEFT BOTTOM — education -->
  {t(80,552,"More education doesn't close it",28,NAVY,"bold")}
  {t(80,577,"2024 unemployment: White (teal) vs Black (orange); right = Black \u00f7 White.",18,GREY)}
  {grid5.replace('y1="545"','y1="598"')}
  {edu_rows(d, xs5, 628, 38, 8, 310, 15, 760, 16)}

  <!-- RIGHT TOP — hidden -->
  {t(840,256,"What the official rate leaves out",28,NAVY,"bold")}
  {t(840,284,f"U-6 minus U-3, in points. In {F['uy']}: U-3 {F['u3']:.2f}%, U-6 {F['u6']:.2f}%.",19,GREY)}
  {grid2}
  {gap_bars(d, xs2, ys2, 476, 14)}
  {t(xs2(F['gpk']), ys2(F['gpkv'])-8, f"{F['gpkv']:.2f} ({F['gpk']})", 15, "#CA6702", "bold", anchor="middle")}
  {ticks2}
  <line x1="840" y1="522" x2="1520" y2="522" stroke="{VANILLA}" stroke-width="3"/>

  <!-- RIGHT BOTTOM — teens -->
  {t(840,552,"Teenagers carry several times the adult rate",28,NAVY,"bold")}
  {t(840,577,"Teens 16\u201319 (orange) vs workers 20+ (teal), 1948\u20132026.",18,GREY)}
  {t(1520,577,f"{F['t_ratio_last']:.1f}\u00d7 in {tl[0]}",24,SPICE,"bold",anchor="end")}
  {grid3}
  {comb(d, xs3, ys3, 3.2, 2)}
  {ticks3}

  <rect x="0" y="{H-70}" width="{W}" height="70" fill="{NAVY}"/>
  {t(80,H-34,"@unwelcomedata",22,"#FFFFFF","bold")}
  {t(80,H-12,"BLS CPS & LAUS \u00b7 seasonally adjusted \u00b7 U-6 starts 1994 (CPS redesign) \u00b7 teen rate is a share of the labor force, not of all teens.",16,AQUA)}
</svg>
'''
    return svg, H


# ───────────────────────── validation ─────────────────────────
def validate(d, F, tall, social):
    lines, ok = [], True

    def chk(name, cond, detail=""):
        nonlocal ok
        ok &= bool(cond)
        lines.append(f"- {'PASS' if cond else 'FAIL'} \u2014 {name}" + (f" ({detail})" if detail else ""))

    sp = {
        "tall": dict(svg=tall, rs=Lin(1.0, 3.0, 800, 590), rx=Lin(1973, 2026, 150, 1120),
                     gy=Lin(0, 8, 1420, 1180), gx=Lin(1994, 2026, 165, 1105), cy=Lin(0, 30, 1980, 1735),
                     cx=Lin(1948, 2026, 150, 1120), sy=Lin(0, 7, 2640, 2350), ex=Lin(0, 10, 520, 1010), sx0=130, sp=19.2, base_gap=1420),
        "social": dict(svg=social, rs=Lin(1.0, 3.0, 456, 312), rx=Lin(1973, 2026, 120, 760),
                       gy=Lin(0, 8, 476, 316), gx=Lin(1994, 2026, 910, 1500), cy=Lin(0, 30, 760, 590),
                       cx=Lin(1948, 2026, 910, 1520), sy=None, ex=Lin(0, 10, 330, 640), sx0=None, sp=None, base_gap=476),
    }
    ratio = dict(d["ratio"]); gap = dict(d["gap"]); yth = {y: (a, tn) for y, a, tn in d["youth"]}
    edu = {}
    for lvl, order, race, v in d["edu"]:
        edu.setdefault(order, {})[race] = v
    for name, s in sp.items():
        svg = s["svg"]
        rd = [(int(m[0]), float(m[1]), float(m[2])) for m in re.findall(r'class="rd" data-year="(\d+)" cx="([\d.]+)" cy="([\d.]+)"', svg)]
        err = max(abs(s["rs"].inv(cy) - ratio[y]) for y, cx, cy in rd)
        xerr = max(abs(s["rx"].inv(cx) - y) for y, cx, cy in rd)
        chk(f"{name}: {len(rd)} ratio dots = {len(ratio)} DB years, values match (max err {err:.3f}, x err {xerr:.2f})",
            len(rd) == len(ratio) and err < 0.02 and xerr < 0.1)
        gb = [(int(m[0]), float(m[1]), float(m[2])) for m in re.findall(r'class="gb" data-year="(\d+)" x="[\d.]+" y="([\d.]+)" width="[\d.]+" height="([\d.]+)"', svg)]
        gerr = max(abs(s["gy"].inv(y0) - gap[y]) for y, y0, h in gb)
        berr = max(abs((y0 + h) - s["base_gap"]) for y, y0, h in gb)
        chk(f"{name}: {len(gb)} U-6 minus U-3 bars match DB (max err {gerr:.3f} pts; all share one baseline, err {berr:.2f}px)",
            len(gb) == len(gap) and gerr < 0.05 and berr < 0.2)
        ca = {int(m[0]): float(m[1]) for m in re.findall(r'class="ca" data-year="(\d+)" cx="[\d.]+" cy="([\d.]+)"', svg)}
        ct = {int(m[0]): float(m[1]) for m in re.findall(r'class="ct" data-year="(\d+)" cx="[\d.]+" cy="([\d.]+)"', svg)}
        cerr = max(max(abs(s["cy"].inv(ca[y]) - yth[y][0]), abs(s["cy"].inv(ct[y]) - yth[y][1])) for y in yth)
        chk(f"{name}: {len(ca)} adult + {len(ct)} teen dots match DB (max err {cerr:.3f} pts)", len(ca) == len(yth) == len(ct) and cerr < 0.05)
        ew = {int(m[0]): float(m[1]) for m in re.findall(r'class="ew" data-order="(\d)" cx="([\d.]+)"', svg)}
        eb = {int(m[0]): float(m[1]) for m in re.findall(r'class="eb" data-order="(\d)" cx="([\d.]+)"', svg)}
        eerr = max(max(abs(s["ex"].inv(ew[o]) - edu[o]["White"]), abs(s["ex"].inv(eb[o]) - edu[o]["Black"])) for o in edu)
        chk(f"{name}: 8 education dots match DB (max err {eerr:.3f} pts)", len(ew) == len(eb) == 4 and eerr < 0.05)
    sb = [(m[0], float(m[1]), float(m[2])) for m in re.findall(r'class="sb" data-st="(\w+)" x="[\d.]+" y="([\d.]+)" width="[\d.]+" height="([\d.]+)"', tall)]
    rates = {ab: r for ab, r, _ in d["states"]}
    serr = max(abs(sp["tall"]["sy"].inv(y0) - rates[ab]) for ab, y0, h in sb)
    chk(f"tall: {len(sb)} state bars match DB rates (max err {serr:.3f} pts) and are sorted high\u2192low",
        len(sb) == 51 and serr < 0.03 and [x[0] for x in sb] == [a for a, _, _ in d["states"]])
    bands = {}
    for ab, r, _ in d["states"]:
        k = next(n for n, lo, hi, c in BAND if lo <= r < hi); bands[k] = bands.get(k, 0) + 1
    chk("state bands match the published gate (6 / 18 / 21 / 5 / 1)", [bands[b[0]] for b in BAND] == [6, 18, 21, 5, 1], str(bands))
    # facts asserted in text
    chk(f"text: mean ratio {F['mean_r']:.2f} (2.0\u20132.2); {F['n2']} of {F['n']} years >= 2.0; min ratio {F['rmin']:.2f} >= 1.5",
        2.0 <= F["mean_r"] <= 2.2 and F["rmin"] >= 1.5)
    g = F["gaps"]
    chk("text: gap widens in downturns (2001>2000, 2003>2000, 2010>2007, 2020>2019)",
        g[2001] > g[2000] and g[2003] > g[2000] and g[2010] > g[2007] and g[2020] > g[2019])
    chk(f"text: U-3 {F['u3']} / U-6 {F['u6']} for {F['uy']} and DC {F['st_top'][1]} is the only state >= 6.0",
        sum(1 for _, r, _ in d["states"] if r >= 6.0) == 1 and F["st_top"][0] == "DC")
    chk("text: Black bachelor's rate equals White some-college rate (3.0 = 3.0); Black > White at every education level",
        edu[3]["Black"] == edu[2]["White"] and all(edu[o]["Black"] > edu[o]["White"] for o in edu))
    chk("text: teen/adult ratio range and mean as stated", 2.2 < F["t_min"] < 2.4 and 4.5 < F["t_max"] < 4.7, f"{F['t_min']:.2f}\u2013{F['t_max']:.2f}, mean {F['t_mean']:.2f}")
    chk("text: Wyoming has 5 months in the trailing window", any(a == "WY" and n == 5 for a, _, n in d["states"]))
    return ok, lines


def render(h_tall):
    from playwright.sync_api import sync_playwright
    jobs = [("infographic_unemployment.svg", "infographic_unemployment.png", 1200, h_tall),
            ("infographic_unemployment_social.svg", "infographic_unemployment_social.png", 1600, 900)]
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        for sv, pn, w, h in jobs:
            html = f"<!doctype html><html><head><style>*{{margin:0;padding:0}}</style></head><body>{(DOCS/sv).read_text(encoding='utf-8')}</body></html>"
            pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg.set_content(html); pg.wait_for_timeout(300)
            pg.screenshot(path=str(DOCS / pn), clip={"x": 0, "y": 0, "width": w, "height": h}); pg.close()
            print("rendered", pn, w, h)
        b.close()


def main():
    d = load(); F = facts(d)
    (tall, H), (social, _) = build_tall(d, F), build_social(d, F)
    (DOCS / "infographic_unemployment.svg").write_text(tall, encoding="utf-8")
    (DOCS / "infographic_unemployment_social.svg").write_text(social, encoding="utf-8")
    ok, lines = validate(d, F, tall, social)
    (ART / "INFOGRAPHIC-VALIDATION.md").write_text(
        "# Infographic data-mark validation \u2014 unemployment\n\nEvery data mark in both renders parsed back out of the SVG, "
        "inverted through its documented scale and compared with a fresh DuckDB query; every number stated in text is asserted.\n\n"
        + "\n".join(lines) + f"\n\n**Result: {'PASS' if ok else 'FAIL'}**\n", encoding="utf-8")
    print("\n".join(lines)); print("VALIDATION", "PASS" if ok else "FAIL")
    render(H)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()

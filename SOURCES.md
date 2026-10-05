# Data Sources — unemployment

All data used in this project is from authoritative sources. Crowd-edited
references (Wikipedia, etc.) are not used as primary sources.

Document every data source here before ingesting it. Include enough detail
that someone else could independently locate and verify the original data.

---

## Source Template

Copy and fill in for each source. The **How the source collects the data**,
**How the source defines the data**, and **Methodology changes / series breaks**
sections are required — they are what keep our analysis honest and prevent
apples-to-oranges comparisons.

### [Source Name]
- **Publisher:** [Agency, organization, or author]
- **URL:** [Direct link to the file or page]
- **Format:** [CSV | JSON | HTML table | ZIP | PDF | hand-curated]
- **License:** [Public domain | CC0 | CC-BY | proprietary | etc.]
- **Fields used:** [Column names or description of what was extracted]
- **Coverage:** [Geographic scope, date range, or other relevant bounds]
- **How the source collects the data:** [Survey / administrative record / model estimate;
  sampling frame; universe & denominator; who is in/out]
- **How the source defines the data:** [How the counted thing is defined; judgment calls]
- **Methodology changes / series breaks:** [Dates when definitions/methods changed and
  which periods are NOT comparable; say so if the series is consistent]
- **Known controversies / debates:** [Contested measurement choices worth a caveat]
- **Notes:** [Anything else — quirks, revisions, imputation]
- **Retrieved:** [YYYY-MM-DD]

---

## Sources

### BLS LAUS — State Unemployment Rates
- **Publisher:** U.S. Bureau of Labor Statistics, Local Area Unemployment Statistics (LAUS) program
- **URL:** https://api.bls.gov/publicAPI/v2/timeseries/data/ (BLS Public Data API v2)
- **Format:** JSON (API), loaded to DuckDB table `unemployment_states`
- **License:** Public domain (U.S. government work)
- **Fields used:** series_id, state, year, month/period, unemployment rate (seasonally adjusted)
- **Coverage:** 50 states + DC, monthly, 1976–2025
- **How the source collects the data:** **Model-based estimate, not a direct survey read.**
  State labor-force figures come from the Current Population Survey (CPS), but the state CPS
  sample is small and noisy, so LAUS runs a **signal-plus-noise time-series model** per state
  (separate models for employment and unemployment levels, built on 1976→present data),
  blended with auxiliary data from state **unemployment-insurance (UI) claims** and the
  **Current Employment Statistics (CES)** payroll survey. The published rate is derived from
  those modeled levels — so it is an estimate with a model behind it, not a raw count.
- **How the source defines the data:** The headline rate is the **U-3** definition:
  unemployed = people without a job who are *available for work* and *actively looked* in the
  last 4 weeks, divided by the civilian labor force. This **excludes** discouraged workers,
  the marginally attached, and involuntary part-timers (those appear only in the broader
  U-4…U-6 measures). "Seasonally adjusted" removes predictable within-year patterns.
- **Methodology changes / series breaks:**
  - LAUS is **periodically re-estimated** and its **seasonal-adjustment / model methodology
    has changed** (documented BLS changes in **2018** and **2021**). Historical values can be
    revised when models are updated and when estimates are re-controlled to new national/
    census-division totals, so a value pulled today may differ from one pulled years ago.
  - The **U-3 definition itself is stable** over this window, but the *modeled state estimates*
    are revised — treat the series as internally consistent within a single vintage/pull and
    re-pull the whole series rather than splicing old and new extracts.
  - COVID (2020) produced genuine extreme values plus known data-collection disruptions; not a
    definition break, but flag 2020 spikes as real-but-anomalous.
- **Known controversies / debates:** U-3 is regularly criticized for understating labor-market
  slack (it omits discouraged/underemployed workers); that's a definitional choice, not an
  error — cite U-6 alongside if the story is about "hidden" unemployment.
- **Notes:** Seasonally adjusted monthly rates. Fetched via BLS API v2 (daily request limits
  apply — see TODO for the pending national-demographic series pull).
- **Retrieved:** 2026-08-27

### State FIPS Reference
- **Publisher:** Internal crosswalk (built from official Census FIPS + BLS series IDs)
- **Format:** Internal table (`state_ref`)
- **License:** Public domain (underlying codes)
- **Fields used:** FIPS codes, state abbrev/name, BLS series IDs for 50 states + DC
- **How the source collects the data:** Hand-built reference crosswalk, not statistical data.
- **How the source defines the data:** Maps states to their official FIPS codes and the
  corresponding BLS LAUS series IDs.
- **Methodology changes / series breaks:** Reference table; no time series, no break.
- **Known controversies / debates:** None.
- **Retrieved:** 2026-08-27

### BLS Series Catalog
- **Publisher:** Internal (derived from BLS series definitions)
- **Format:** Internal table (`series_catalog`)
- **License:** Public domain
- **Fields used:** series_id → human-readable label, category
- **How the source collects the data:** Lookup table mapping BLS series IDs to labels.
- **How the source defines the data:** Documentation aid for the numeric series above.
- **Methodology changes / series breaks:** Reference table; no break.
- **Known controversies / debates:** None.
- **Retrieved:** 2026-08-27

### BLS CPS — National Unemployment by Demographics
- **Publisher:** U.S. Bureau of Labor Statistics, Current Population Survey (CPS)
- **URL:** https://api.bls.gov/publicAPI/v2/timeseries/data/ (BLS Public Data API v2)
- **Format:** JSON (API), loaded to DuckDB table `unemployment_national`
- **License:** Public domain (U.S. government work)
- **Fields used:** series_id, label, category, year, month, date, value (unemployment rate %)
- **Coverage:** National, monthly, 1948–2026; breakdowns by age/sex/race begin later (see breaks).
  Includes `LNS14000024` (Unemployment Rate, 20 years & over — the combined-sex adult total,
  full 1948–2026 coverage), added so teen-vs-adult comparisons use a real 20+ total rather than
  the overall 16+ rate (which includes teens).
- **How the source collects the data:** Monthly household survey of ~60,000 U.S. households.
  Respondents are classified as employed, unemployed, or not in the labor force based on their
  reported activity during the reference week. The CPS is the gold standard for labor-force
  measurement — it captures people not receiving unemployment insurance (self-employed, gig,
  those who exhausted benefits) that administrative records miss.
- **How the source defines the data:**
  - **U-3 (official rate):** Unemployed = without a job, available to work, and actively searched
    in the past 4 weeks ÷ civilian labor force. **This is the headline rate.**
  - **U-4:** Adds discouraged workers (gave up looking because they believe no jobs available).
  - **U-5:** Adds all marginally attached workers (wanted work, available, looked in past year).
  - **U-6 (broadest):** Adds people working part-time for economic reasons (involuntary part-time).
  - **Never compare U-3 and U-6 directly** — they measure different populations by design.
  - Demographic breakdowns (by race, age, sex) all use the U-3 definition.
- **Methodology changes / series breaks:**
  - **U-4/U-5/U-6 begin January 1994** — alternative measures introduced that year.
  - **Asian series begins January 2003** (new CPS race category).
  - **Hispanic/Latino series begins January 1973.**
  - **Black series begins January 1972.**
  - **White series begins January 1954.**
  - **1994 CPS redesign** — the most significant methodological update; introduced new questions
    on job-search methods and duration, and the alternative U-4…U-6 measures. The BLS published
    bridging factors; the overall U-3 rate is broadly comparable before/after but the change
    affects some sub-series.
  - **2011 unemployment-duration cap raised** — BLS raised the maximum recorded value for the
    CPS unemployment-duration variable from up to 99 weeks (~2 years) to up to 260 weeks
    (~5 years), beginning with January 2011 data. This affects **duration / long-term-unemployment
    series** (how long jobless spells are recorded), **not** the U-3 or U-6 rate *levels* — a
    change to a measurement variable, not a redefinition of who counts as unemployed. (Backs the
    Chart-2 "2011 duration cap" marker.)
  - **2003 race-category revision** — "Asian or Pacific Islander" was split; Asian and NHOPI became
    separate categories. The Asian series only begins after this change.
  - **55-64 year and 65+ year age-bracket series** (LNS14000095, LNS14000097) returned no data
    from the API — these series IDs may have been superseded in recent BLS catalog updates. Not a
    critical gap for the core story; the 45-54 series is the oldest age group available.
- **Known controversies / debates:**
  - U-3 regularly criticized for understating slack — it excludes discouraged and underemployed
    workers (addressed by U-6). Use U-6 alongside U-3 when the story is about "hidden" unemployment.
  - Racial unemployment rates are based on self-identified race from the CPS survey, not the same
    classification scheme across all years.
- **Notes:** 18 of 20 requested series returned data. All seasonally adjusted (X-13ARIMA-SEATS).
  Raw API responses saved to `data/raw/bls_api_data.parquet`.
- **Retrieved:** 2026-09-28

### BLS CPS — Unemployment by Educational Attainment and Race (annual, 25+)
- **Publisher:** U.S. Bureau of Labor Statistics, Current Population Survey (CPS)
- **URL:** https://www.bls.gov/cps/data/aa2024/cpsaat07.pdf (annual table cpsaat07;
  prior years at `…/aa<YEAR>/cpsaat07.pdf`)
- **Format:** PDF, parsed with pdfplumber by word position → DuckDB table
  `unemployment_by_education_race`
- **License:** Public domain (U.S. government work)
- **Fields used:** year, race (White, Black), education_level (4 tiers),
  unemployment_rate
- **Coverage:** National, **annual average**, population **25 years and over**, 2024
  (prior years available via the same `aa<YEAR>` path).
- **How the source collects the data:** The CPS monthly household survey (~60,000
  households) averaged to annual figures; education and race are self-reported.
  cpsaat07 is one of the published annual household-data tables.
- **How the source defines the data:** The **U-3** unemployment rate (same
  definition as the project's other series — jobless, available, actively looked in
  the last 4 weeks ÷ civilian labor force), but restricted to the **25-and-over**
  population and reported as an **annual average, not seasonally adjusted**. The four
  standardized education tiers are: Less than high school / High school, no college /
  Some college or associate degree / Bachelor's degree and higher. cpsaat07 splits the
  top two tiers into sub-columns (some-college vs associate; bachelor's-only vs
  advanced); we use the published **TOTAL** column for each of those two tiers and
  ignore the sub-splits (no re-derivation, no rounding drift).
- **Methodology changes / series breaks:** This is a **DIFFERENT grain** from the
  data behind charts 1–6 — **annual, 25+, NSA, from cpsaat07**, versus the **monthly
  seasonally-adjusted 16+ `LN` series** used elsewhere. **The two must never be
  plotted on the same axis or implied to be the same series.** The companion chart's
  subtitle states "annual average · people 25 and older" to keep this explicit.
  Education-attainment categories are stable across recent years.
- **Known controversies / debates:** The interpretive claim this chart supports (why
  the gap persists across education levels) is cited to EPI (2015, 2019), Quillian et
  al. (PNAS 2017), and Federal Reserve FEDS 2017-071 — see "Interpretation sources
  (race gap)" below. The chart itself is the data that makes that fact visible.
- **Access note:** bls.gov `/cps/` endpoints block automated requests (Akamai 403)
  unless a full browser header set (incl. `Referer` + `Sec-Fetch-*`) is sent; the
  ingest helper (`fetch_bls_cps_table`) does so. Raw PDF cached verbatim in
  `data/raw/cpsaat07_2024.pdf`.
- **Retrieved:** 2026-10-05

### Interpretation sources (race gap)
These back the explanatory claim on **Chart 3** (why the persistent ~2:1 Black/White
unemployment gap exists). The gap is attributed mainly to **labor-market discrimination
and occupational segregation**, not to differences in education — it holds at every
education level, and hiring-audit studies find no decline in discrimination since 1989.
This is an interpretive claim layered on the BLS CPS rate data, so its sources are cited
to meet the serious-tier citation standard. (A fuller dev-only writeup lives in
`artifacts/race-gap-literature.md`, which is gitignored and not part of this file.)

- **BLS CPS** — the underlying unemployment-rate-by-race series (see source above), and
  the race × education cross-tab (cpsaat07) that shows the gap persists at every
  education level (see source above).
- **Bertrand & Mullainathan, *American Economic Review* 2004 (NBER w9873)** — the
  landmark résumé-callback field experiment: identical résumés with Black-sounding names
  received far fewer interview callbacks.
- **Economic Policy Institute (EPI), 2015 and 2019** — analyses showing the Black/White
  unemployment gap persists across education levels and over time.
- **Quillian, Pager, Hexel & Midtbøen, *PNAS* 2017** — meta-analysis of hiring-audit
  (résumé/callback) field experiments finding no decline in anti-Black hiring
  discrimination since 1989.
- **Federal Reserve, Finance and Economics Discussion Series (FEDS) 2017-071** — decomposition
  of Black/White labor-market gaps pointing to discrimination and structural factors rather
  than education.
- **Federal Reserve Bank of San Francisco (FRBSF) Economic Letter, 2021** — Black (and
  Hispanic) unemployment is a "high-beta" version of the overall labor market (falls faster
  in downturns, recovers more slowly), which keeps the *ratio* roughly stable across the
  cycle.

---

## Notes on Data Quality

- All source files are saved verbatim to `data/raw/` and never modified.
- Discrepancies between sources should be noted here and resolved explicitly.

### Series breaks worth remembering here

- **LAUS state rates are modeled and get revised** (2018 & 2021 methodology changes; ongoing
  re-estimation). Re-pull the full series rather than splicing extracts from different dates.
- **U-3 vs U-4…U-6** are different definitions of "unemployed" — never compare across them.
- **U-4/U-5/U-6 only go back to 1994** — charts using these can't show pre-1994 history.
- **Race breakdowns start at different years:** White 1954, Black 1972, Hispanic 1973, Asian 2003.
  Cross-race comparisons must start from the latest series' first year.
- **1994 CPS redesign** — job-search questions changed and U-4…U-6 were introduced. Rates are
  broadly comparable but some sub-series (duration, reason) are not. Flag this on any pre/post-1994
  trend chart.
- **2011 duration cap** — the max recorded unemployment-duration category was raised from ~2 years
  (99 weeks) to ~5 years (260 weeks). Affects duration/long-term-unemployment series only, not the
  U-3/U-6 rate levels.
- **COVID 2020** — April 2020 14.8% peak is a genuine anomaly. Not a definition break,
  but note it as anomalous on any multi-decade chart so it doesn't distort the visual range.
- **cpsaat07 race×education table is annual / 25+ / NSA** — a different grain from the
  monthly SA `LN` series behind charts 1–6; never splice or co-plot the two.

---

## Source Provenance in DuckDB

Every table in `data/project.duckdb` has a corresponding entry in the
`_sources` metadata table:

```sql
SELECT duckdb_table, source_name, methodology, series_breaks FROM _sources;
```

Alongside `source_name`, `url`, `license`, `notes`, `retrieved`, the table carries
**`methodology`** and **`series_breaks`** so provenance travels with the data.

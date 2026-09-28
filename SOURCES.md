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
- **Coverage:** National, monthly, 1948–2026; breakdowns by age/sex/race begin later (see breaks)
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
    on job-search methods and duration. The BLS published bridging factors; the overall U-3 rate
    is broadly comparable before/after but the change affects some sub-series.
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
- **1994 CPS redesign** — job-search questions changed. Rates are broadly comparable but some
  sub-series (duration, reason) are not. Flag this on any pre/post-1994 trend chart.
- **COVID 2020** — April 2020 14.8% peak is a genuine anomaly. Not a definition break,
  but note it as anomalous on any multi-decade chart so it doesn't distort the visual range.

---

## Source Provenance in DuckDB

Every table in `data/project.duckdb` has a corresponding entry in the
`_sources` metadata table:

```sql
SELECT duckdb_table, source_name, methodology, series_breaks FROM _sources;
```

Alongside `source_name`, `url`, `license`, `notes`, `retrieved`, the table carries
**`methodology`** and **`series_breaks`** so provenance travels with the data.

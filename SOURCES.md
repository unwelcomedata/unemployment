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

<!-- Pending (see workspace TODO.md): national demographic series (U3–U6 + by age/sex/race),
     to be loaded as `unemployment_national`. Document its definitions/breaks here when added —
     the U-4/U-5/U-6 measures widen the "unemployed" definition and must be labeled distinctly
     from the U-3 headline rate above. -->

---

## Notes on Data Quality

- All source files are saved verbatim to `data/raw/` and never modified.
- Discrepancies between sources should be noted here and resolved explicitly.

### Series breaks worth remembering here

- **LAUS state rates are modeled and get revised** (2018 & 2021 methodology changes; ongoing
  re-estimation). Re-pull the full series rather than splicing extracts from different dates.
- **U-3 vs U-4…U-6** are different definitions of "unemployed" — never compare across them.

---

## Source Provenance in DuckDB

Every table in `data/project.duckdb` has a corresponding entry in the
`_sources` metadata table:

```sql
SELECT duckdb_table, source_name, methodology, series_breaks FROM _sources;
```

Alongside `source_name`, `url`, `license`, `notes`, `retrieved`, the table carries
**`methodology`** and **`series_breaks`** so provenance travels with the data.

# unemployment — Dataset Codebook
Generated: 2026-10-05

## Columns

### `state_name`
- **Type**: `object`
- **Non-null**: 51 / 51 (100.0%)
- **Description**: State (or District of Columbia) name.

### `state_abbrev`
- **Type**: `object`
- **Non-null**: 51 / 51 (100.0%)
- **Description**: Two-letter USPS state abbreviation (DC for the District of Columbia).

### `rate`
- **Type**: `float64`
- **Non-null**: 51 / 51 (100.0%)
- **Description**: Average seasonally-adjusted U-3 unemployment rate (%) over the trailing 12 most recent distinct monthly periods (Jul 2025 - Jul 2026).

### `n_months`
- **Type**: `int64`
- **Non-null**: 51 / 51 (100.0%)
- **Description**: Number of monthly observations in the average (12 for all states except Wyoming, which reports through Dec 2025 = 5 months).

## Notes

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

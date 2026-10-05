# unemployment — Dataset Codebook
Generated: 2026-10-05

## Columns

### `year`
- **Type**: `int64`
- **Non-null**: 79 / 79 (100.0%)
- **Description**: Calendar year (annual average of monthly values).

### `u3_rate`
- **Type**: `float64`
- **Non-null**: 79 / 79 (100.0%)
- **Description**: Official U-3 unemployment rate (%), seasonally adjusted, 16+. BLS CPS LNS14000000.

### `u6_rate`
- **Type**: `float64`
- **Non-null**: 33 / 79 (41.8%)
- **Description**: Broad U-6 rate (%): U-3 plus marginally-attached workers and involuntary part-timers. Begins 1994. BLS CPS LNS13327709.

### `white_rate`
- **Type**: `float64`
- **Non-null**: 54 / 79 (68.4%)
- **Description**: U-3 unemployment rate (%) for White workers, seasonally adjusted. BLS CPS LNS14000003 (begins 1954; comparable from 1973).

### `black_rate`
- **Type**: `float64`
- **Non-null**: 54 / 79 (68.4%)
- **Description**: U-3 unemployment rate (%) for Black workers, seasonally adjusted. BLS CPS LNS14000006 (begins 1972).

### `hispanic_rate`
- **Type**: `float64`
- **Non-null**: 54 / 79 (68.4%)
- **Description**: U-3 unemployment rate (%) for Hispanic workers, seasonally adjusted. BLS CPS LNS14000009 (begins 1973).

### `adults_20plus_rate`
- **Type**: `float64`
- **Non-null**: 79 / 79 (100.0%)
- **Description**: U-3 unemployment rate (%) for workers 20 years and over, seasonally adjusted. BLS CPS LNS14000024.

### `youth_16_19_rate`
- **Type**: `float64`
- **Non-null**: 79 / 79 (100.0%)
- **Description**: U-3 unemployment rate (%) for workers 16-19 years, seasonally adjusted. BLS CPS LNS14000012.

## Notes

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

# unemployment — Dataset Codebook
Generated: 2026-10-05

## Columns

### `year`
- **Type**: `int32`
- **Non-null**: 8 / 8 (100.0%)
- **Description**: Calendar year of the annual average (2024).

### `education_level`
- **Type**: `object`
- **Non-null**: 8 / 8 (100.0%)
- **Description**: Highest education tier: 'Less than high school', 'High school, no college', 'Some college or associate degree', or "Bachelor's degree and higher".

### `education_order`
- **Type**: `int32`
- **Non-null**: 8 / 8 (100.0%)
- **Description**: Integer sort key for education_level (lowest to highest attainment).

### `race`
- **Type**: `object`
- **Non-null**: 8 / 8 (100.0%)
- **Description**: Race group: 'White' or 'Black'.

### `unemployment_rate`
- **Type**: `float64`
- **Non-null**: 8 / 8 (100.0%)
- **Description**: Annual-average unemployment rate (%), not seasonally adjusted, workers 25 and over, for the race x education cell. BLS CPS table cpsaat07.

## Notes

Source: U.S. Bureau of Labor Statistics, Current Population Survey (CPS),
annual table cpsaat07. License: Public domain (U.S. Government work).
Measure: annual-average unemployment rate, population 25 years and over, NOT
seasonally adjusted. This is a DIFFERENT grain from the monthly, seasonally
adjusted, 16+ national series in the other exports; do not conflate them.
Interpretation: the Black/White gap holds at every education level, which is
why economists attribute the ~2:1 gap mainly to labor-market discrimination
and occupational segregation rather than education (EPI 2015, 2019; Quillian
et al. PNAS 2017; Fed FEDS 2017-071). Retrieved 2026-09-28.

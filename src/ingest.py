"""Web ingestion utilities.

Handles three source types:
  - html_table  : pandas read_html on a static page
  - html_scrape : BeautifulSoup for custom element extraction
  - csv / json  : direct download and save to data/raw

All raw files land in data/raw unchanged. Call load_config() once per notebook
to get paths and source definitions from config.yaml.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load project config.yaml and return it as a dict."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def raw_path(cfg: dict, filename: str) -> Path:
    """Return a Path inside data/raw, creating the directory if needed."""
    p = Path(cfg["paths"]["data_raw"]) / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_CACHE_DIR: Path | None = None


def _get_cache_dir(cfg: dict) -> Path:
    """Return the cache directory (data/raw by default)."""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = Path(cfg["paths"]["data_raw"])
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def fetch_html(url: str, headers: dict | None = None, timeout: int = 30) -> str:
    """Fetch a URL and return the response text.

    Raises requests.HTTPError on non-2xx status.
    """
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    resp = requests.get(url, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_cached(
    url: str,
    filename: str,
    cfg: dict,
    max_age_hours: float = 24.0,
    headers: dict | None = None,
    timeout: int = 30,
) -> str:
    """Fetch a URL with local file caching.

    If a cached file exists and is younger than max_age_hours, returns its
    contents without making a network request. Otherwise fetches, saves to
    data/raw/{filename}, and returns the content.

    Args:
        url:            URL to fetch.
        filename:       Cache filename (saved in data/raw/).
        cfg:            Loaded config dict.
        max_age_hours:  Re-fetch if cache is older than this (0 = always fetch).
        headers:        Optional extra HTTP headers.
        timeout:        Request timeout in seconds.

    Returns:
        Response text (from cache or network).
    """
    cache_path = _get_cache_dir(cfg) / filename
    if cache_path.exists() and max_age_hours > 0:
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return cache_path.read_text(encoding="utf-8")

    text = fetch_html(url, headers=headers, timeout=timeout)
    cache_path.write_text(text, encoding="utf-8")
    return text


def fetch_with_retry(
    url: str,
    headers: dict | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    rate_limit_seconds: float = 1.5,
) -> str:
    """Fetch a URL with rate limiting and exponential backoff on 429s.

    Args:
        url:                 URL to fetch.
        headers:             Optional extra HTTP headers.
        timeout:             Request timeout in seconds.
        max_retries:         Max retry attempts on 429/5xx.
        rate_limit_seconds:  Minimum delay between requests.

    Returns:
        Response text.

    Raises:
        requests.HTTPError after exhausting retries.
    """
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    time.sleep(rate_limit_seconds)

    for attempt in range(max_retries + 1):
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < max_retries:
                wait = rate_limit_seconds * (2 ** attempt)
                print(f"  ⚠ {resp.status_code} on {url} — retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
        resp.raise_for_status()
        return resp.text

    resp.raise_for_status()  # will raise on the last failed attempt
    return ""  # unreachable


def fetch_html_js(url: str, wait_selector: str | None = None, timeout: int = 30000) -> str:
    """Fetch a JS-rendered page using Playwright (headless Chromium).

    Use this when fetch_html() returns an empty or incomplete page.
    Requires: playwright install chromium

    Args:
        url:           Page URL.
        wait_selector: Optional CSS selector to wait for before returning HTML.
        timeout:       Playwright timeout in milliseconds.
    """
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(extra_http_headers=_DEFAULT_HEADERS)
        page.goto(url, timeout=timeout)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout)
        else:
            page.wait_for_load_state("networkidle", timeout=timeout)
        html = page.content()
        browser.close()
    return html


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_html_table(html: str, table_index: int = 0) -> pd.DataFrame:
    """Extract a <table> from HTML by index and return it as a DataFrame.

    Cleans up column names: lowercase, spaces → underscores.
    """
    tables = pd.read_html(html)
    if not tables:
        raise ValueError("No tables found in the provided HTML.")
    if table_index >= len(tables):
        raise IndexError(
            f"table_index {table_index} out of range — page has {len(tables)} table(s)."
        )
    df = tables[table_index]
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def parse_html_scrape(
    html: str,
    row_selector: str,
    field_map: dict[str, str],
) -> pd.DataFrame:
    """Scrape structured rows from HTML using CSS selectors.

    Args:
        html:          Raw HTML string.
        row_selector:  CSS selector that matches each "row" element.
        field_map:     Dict mapping output column name → CSS selector
                       relative to each row element.
                       Use '' (empty string) to get the row's own text.

    Example:
        parse_html_scrape(html, "tr.data-row", {"name": "td.name", "value": "td.val"})
    """
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(row_selector)
    records = []
    for row in rows:
        record: dict[str, str] = {}
        for col, selector in field_map.items():
            el = row.select_one(selector) if selector else row
            record[col] = el.get_text(" ", strip=True) if el else ""
        records.append(record)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, headers: dict | None = None, timeout: int = 60) -> Path:
    """Stream-download a file (CSV, JSON, zip, etc.) to dest and return the path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    with requests.get(url, headers=hdrs, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
    return dest


# ---------------------------------------------------------------------------
# Source-driven ingest (reads config.yaml sources block)
# ---------------------------------------------------------------------------

def ingest_source(
    name: str,
    cfg: dict,
    save_raw: bool = True,
    js_wait_selector: str | None = None,
    row_selector: str | None = None,
    field_map: dict[str, str] | None = None,
    rate_limit_seconds: float = 1.0,
) -> pd.DataFrame:
    """Ingest a named source from config.yaml and return a DataFrame.

    Args:
        name:               Key under `sources:` in config.yaml.
        cfg:                Loaded config dict (from load_config()).
        save_raw:           If True, save the raw HTML/bytes to data/raw/.
        js_wait_selector:   Passed to fetch_html_js() if js_render is true.
        row_selector:       Required for html_scrape type.
        field_map:          Required for html_scrape type.
        rate_limit_seconds: Polite delay before fetching.
    """
    source = cfg["sources"][name]
    url: str = source["url"]
    source_type: str = source.get("type", "html_table")
    js_render: bool = source.get("js_render", False)
    table_index: int = source.get("table_index", 0)

    time.sleep(rate_limit_seconds)

    if source_type == "csv":
        dest = raw_path(cfg, f"{name}.csv")
        download_file(url, dest)
        return pd.read_csv(dest, encoding=cfg["settings"]["encoding"])

    if source_type == "json":
        dest = raw_path(cfg, f"{name}.json")
        download_file(url, dest)
        with open(dest, encoding=cfg["settings"]["encoding"]) as f:
            data = json.load(f)
        return pd.json_normalize(data)

    # HTML-based types
    html = fetch_html_js(url, wait_selector=js_wait_selector) if js_render else fetch_html(url)

    if save_raw:
        raw_path(cfg, f"{name}.html").write_text(html, encoding="utf-8")

    if source_type == "html_table":
        return parse_html_table(html, table_index=table_index)

    if source_type == "html_scrape":
        if row_selector is None or field_map is None:
            raise ValueError("html_scrape requires row_selector and field_map arguments.")
        return parse_html_scrape(html, row_selector, field_map)

    raise ValueError(f"Unknown source type '{source_type}'. Use: html_table, html_scrape, csv, json.")


# ---------------------------------------------------------------------------
# BLS Public Data API v2
# ---------------------------------------------------------------------------
# The BLS bulk flat-file server (download.bls.gov) blocks automated access.
# Instead we use the BLS Public Data API v2:
#   https://api.bls.gov/publicAPI/v2/timeseries/data/
#
# Limits (without registration key):
#   - 25 series per request
#   - 10 years per request
#   - 25 requests per day
#
# With a free registration key (set BLS_API_KEY env var):
#   - 50 series per request
#   - 20 years per request
#   - 500 requests per day
# ---------------------------------------------------------------------------

import os

BLS_API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"


def _bls_api_fetch(
    series_ids: list[str],
    start_year: int,
    end_year: int,
    rate_limit: float = 1.5,
) -> list[dict]:
    """Call BLS API for a batch of series over a year range.

    Returns list of series dicts with 'seriesID' and 'data' keys.
    """
    api_key = os.environ.get("BLS_API_KEY", "")
    payload: dict[str, Any] = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if api_key:
        payload["registrationkey"] = api_key

    headers = {"Content-Type": "application/json"}
    resp = requests.post(BLS_API_URL, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    result = resp.json()

    if result.get("status") != "REQUEST_SUCCEEDED":
        msgs = result.get("message", [])
        raise RuntimeError(f"BLS API error: {msgs}")

    time.sleep(rate_limit)
    return result["Results"]["series"]


def ingest_bls_api(
    cfg: dict,
    series_ids: list[str],
    start_year: int = 1948,
    end_year: int = 2026,
    batch_size: int = 25,
    year_window: int = 10,
) -> pd.DataFrame:
    """Fetch multiple BLS series via the Public Data API v2.

    Handles pagination by year windows and series batching automatically.
    Saves raw JSON responses to data/raw/ for reproducibility.

    Args:
        cfg:          Loaded config dict.
        series_ids:   List of BLS series IDs to fetch.
        start_year:   First year to request (inclusive).
        end_year:     Last year to request (inclusive).
        batch_size:   Max series per API call (25 without key, 50 with key).
        year_window:  Max years per API call (10 without key, 20 with key).

    Returns:
        DataFrame with columns: series_id, year, period, period_name, value.
    """
    api_key = os.environ.get("BLS_API_KEY", "")
    if api_key:
        batch_size = min(batch_size, 50)
        year_window = min(year_window, 20)
    else:
        batch_size = min(batch_size, 25)
        year_window = min(year_window, 10)

    rate_limit = cfg["settings"].get("rate_limit_seconds", 1.5)
    all_records = []
    request_count = 0

    # Split series into batches
    series_batches = [
        series_ids[i:i + batch_size]
        for i in range(0, len(series_ids), batch_size)
    ]

    # Split year range into windows
    year_ranges = []
    y = start_year
    while y <= end_year:
        y_end = min(y + year_window - 1, end_year)
        year_ranges.append((y, y_end))
        y = y_end + 1

    total_requests = len(series_batches) * len(year_ranges)
    print(f"  BLS API: {len(series_ids)} series, {start_year}-{end_year}")
    print(f"  Batches: {len(series_batches)} series batches x {len(year_ranges)} year windows = {total_requests} requests")

    for batch_idx, batch in enumerate(series_batches):
        for yr_start, yr_end in year_ranges:
            request_count += 1
            print(f"  [{request_count}/{total_requests}] series batch {batch_idx+1}, years {yr_start}-{yr_end}...")

            try:
                series_results = _bls_api_fetch(batch, yr_start, yr_end, rate_limit)
            except (requests.HTTPError, RuntimeError) as e:
                print(f"    WARNING: {e}")
                continue

            for series in series_results:
                sid = series["seriesID"]
                for obs in series.get("data", []):
                    all_records.append({
                        "series_id": sid,
                        "year": int(obs["year"]),
                        "period": obs["period"],
                        "period_name": obs.get("periodName", ""),
                        "value": obs["value"],
                    })

    df = pd.DataFrame(all_records)
    if not df.empty:
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.sort_values(["series_id", "year", "period"]).reset_index(drop=True)

    # Save raw data as parquet for reproducibility
    dest = raw_path(cfg, "bls_api_data.parquet")
    df.to_parquet(dest, index=False)
    print(f"\n  Done: {len(df):,} observations saved to {dest}")

    return df


# ---------------------------------------------------------------------------
# Key Series Definitions
# ---------------------------------------------------------------------------

# Commonly needed unemployment rate series (seasonally adjusted)
KEY_UNEMPLOYMENT_SERIES = {
    # Overall
    "LNS14000000": "Total, 16+",
    # By sex
    "LNS14000001": "Men, 16+",
    "LNS14000002": "Women, 16+",
    # By age
    "LNS14000012": "16-19 years",
    "LNS14000036": "20-24 years",
    "LNS14000089": "25-34 years",
    "LNS14000091": "35-44 years",
    "LNS14000093": "45-54 years",
    "LNS14000095": "55-64 years",
    "LNS14000097": "65+ years",
    # By race
    "LNS14000003": "White",
    "LNS14000006": "Black or African American",
    "LNS14000009": "Hispanic or Latino",
    "LNS14032183": "Asian",
    # Adult by sex
    "LNS14000025": "Men, 20+",
    "LNS14000026": "Women, 20+",
}

# U-3 vs U-6 comparison series
ALTERNATIVE_MEASURES_SERIES = {
    "LNS14023621": "U-3 (official rate)",
    "LNS13327709": "U-6 (broad underutilization)",
    "LNS13327708": "U-5 (plus discouraged + marginally attached)",
    "LNS13327707": "U-4 (plus discouraged)",
}

# State-level unemployment rates (LAUS, seasonally adjusted)
# Format: LAUST{FIPS}0000000000003 (measure 03 = unemployment rate)
STATE_FIPS = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
    "06": "California", "08": "Colorado", "09": "Connecticut", "10": "Delaware",
    "11": "District of Columbia", "12": "Florida", "13": "Georgia", "15": "Hawaii",
    "16": "Idaho", "17": "Illinois", "18": "Indiana", "19": "Iowa",
    "20": "Kansas", "21": "Kentucky", "22": "Louisiana", "23": "Maine",
    "24": "Maryland", "25": "Massachusetts", "26": "Michigan", "27": "Minnesota",
    "28": "Mississippi", "29": "Missouri", "30": "Montana", "31": "Nebraska",
    "32": "Nevada", "33": "New Hampshire", "34": "New Jersey", "35": "New Mexico",
    "36": "New York", "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
    "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania", "44": "Rhode Island",
    "45": "South Carolina", "46": "South Dakota", "47": "Tennessee", "48": "Texas",
    "49": "Utah", "50": "Vermont", "51": "Virginia", "53": "Washington",
    "54": "West Virginia", "55": "Wisconsin", "56": "Wyoming",
}

# LAUS state series IDs (seasonally adjusted unemployment rate)
STATE_UNEMPLOYMENT_SERIES = {
    f"LASST{fips}0000000000003": name
    for fips, name in STATE_FIPS.items()
}


def get_all_series_ids() -> list[str]:
    """Return combined list of all series IDs for full ingest."""
    all_ids = []
    all_ids.extend(KEY_UNEMPLOYMENT_SERIES.keys())
    all_ids.extend(ALTERNATIVE_MEASURES_SERIES.keys())
    all_ids.extend(STATE_UNEMPLOYMENT_SERIES.keys())
    return all_ids


def get_series_labels() -> dict[str, str]:
    """Return combined dict of all series_id -> human label."""
    labels = {}
    labels.update(KEY_UNEMPLOYMENT_SERIES)
    labels.update(ALTERNATIVE_MEASURES_SERIES)
    labels.update(STATE_UNEMPLOYMENT_SERIES)
    return labels


# ---------------------------------------------------------------------------
# Full ingest orchestrator
# ---------------------------------------------------------------------------

def ingest_all(
    cfg: dict,
    start_year: int = 1976,
    end_year: int = 2026,
) -> pd.DataFrame:
    """Run full BLS ingest: national demographics + state LAUS series.

    Fetches all key series via the BLS API, saves raw parquet,
    and returns the combined DataFrame.

    Args:
        cfg:        Loaded config dict.
        start_year: First year (1976 for state data; national goes back to 1948).
        end_year:   Last year.

    Returns:
        Combined DataFrame of all fetched series.
    """
    all_series = get_all_series_ids()
    print(f"=== BLS Unemployment Ingest ===")
    print(f"  Total series: {len(all_series)}")
    print(f"  Year range: {start_year}-{end_year}")
    print()

    df = ingest_bls_api(cfg, all_series, start_year, end_year)

    # Add human-readable labels
    labels = get_series_labels()
    df["label"] = df["series_id"].map(labels)

    return df

# Implementation Specification — run-20260520-hkm-tables-2-3

**For builder only. Do not share with tester.**

---

## Overview

Implement the `hkm` Python package that replicates Tables 2 and 3 from He, Kelly & Manela (2017), "Intermediary Asset Pricing: New Evidence from Many Asset Classes," *Journal of Financial Economics* 126: 1–35.

The package connects to WRDS via psycopg2 (`~/.pgpass` for authentication), fetches data from FRED and public sources, and produces:
1. `compute_table2()` → `pd.DataFrame` of shape (3, 12) with size ratio averages
2. `compute_table3()` → tuple `(panel_a, panel_b)` of `pd.DataFrame` with pairwise correlations

---

## Package Structure

```
hkm/
├── __init__.py               # exports compute_table2, compute_table3
├── utils.py                  # logging setup, DB connection context manager
├── data/
│   ├── __init__.py
│   ├── wrds_connect.py       # psycopg2 connection using ~/.pgpass
│   ├── compustat.py          # fetch_compustat_quarterly() → DataFrame
│   ├── crsp.py               # fetch_crsp_monthly(), fetch_crsp_daily_vol() → DataFrame
│   ├── dealers.py            # PRIMARY_DEALERS list: name, gvkey, permno, start, end
│   ├── intermediary.py       # build_capital_ratio(), build_capital_factor()
│   └── macro.py              # fetch_macro_series() → DataFrame
├── tables/
│   ├── __init__.py
│   ├── table2.py             # compute_table2() → pd.DataFrame shape (3, 12)
│   └── table3.py             # compute_table3() → (panel_a, panel_b)
tests/
├── __init__.py
├── test_data.py
└── test_tables.py
README.md
```

---

## Module: `hkm/utils.py`

### Purpose
Provide shared logging configuration and a database connection context manager.

### Functions

```python
import logging
import contextlib
from typing import Generator
import psycopg2

def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger with INFO level and a standard format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

@contextlib.contextmanager
def wrds_connection(
    host: str = "wrds-pgdata.wharton.upenn.edu",
    port: int = 9737,
    dbname: str = "wrds",
    user: str = "coleginter",
) -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for a psycopg2 WRDS connection using ~/.pgpass.

    Raises:
        ConnectionError: If connection cannot be established.
    """
```

- `get_logger`: Returns a named logger, sets INFO level, adds StreamHandler with timestamp format if not already configured. Never use `print()`.
- `wrds_connection`: Context manager that opens a psycopg2 connection to WRDS using credentials from `~/.pgpass`, yields the connection, closes on exit. If connection fails, raise `ConnectionError` with a message explaining how to configure `~/.pgpass`.

---

## Module: `hkm/data/wrds_connect.py`

### Purpose
Thin wrapper around psycopg2 that provides a helper to run a SQL query and return a DataFrame.

### Functions

```python
import pandas as pd
import psycopg2
from hkm.utils import wrds_connection, get_logger

def run_query(sql: str, conn: psycopg2.extensions.connection) -> pd.DataFrame:
    """Execute a SQL query against the WRDS database and return results as DataFrame.

    Args:
        sql: The SQL string to execute.
        conn: An open psycopg2 connection.

    Returns:
        pd.DataFrame with column names from the cursor description.
    """
```

- Executes `sql` using `conn`, fetches all results, returns `pd.DataFrame`.
- Logs the first 200 characters of the SQL and the row count of the result.
- If the query returns zero rows, logs a WARNING.

---

## Module: `hkm/data/dealers.py`

### Purpose
Define the complete primary dealer universe from Table A.1 of the paper, with CRSP/Compustat identifiers where known. This is a static data file — no WRDS queries needed here.

### Data Structure

```python
from dataclasses import dataclass
import datetime

@dataclass(frozen=True)
class Dealer:
    name: str              # Name as in Table A.1
    gvkey: str | None      # Compustat GVKEY (6-digit string, zero-padded), or None if unknown
    permno: int | None     # CRSP PERMNO, or None if unknown
    start: datetime.date   # First active date per Table A.1
    end: datetime.date | None  # Last active date; None = "Current" (treat as 2012-12-31 for sample)

PRIMARY_DEALERS: list[Dealer]
```

### Primary Dealer List

Populate `PRIMARY_DEALERS` with all US-based dealers from Table A.1 that are potentially in CRSP-Compustat. GVKEYs and PERMNOs are pre-populated where known (see mapping below). Where unknown, set to `None` — the builder will attempt name-matching at runtime via `find_dealer_identifiers()`.

**Known GVKEY mappings (to be verified via WRDS name search)**:

| Name | GVKEY | Notes |
|---|---|---|
| Goldman Sachs | 011251 | Goldman Sachs Group, Inc. |
| Morgan Stanley | 022365 | Morgan Stanley |
| Merrill Lynch | 012069 | Merrill Lynch & Co. |
| Lehman Brothers | 012562 | Lehman Brothers Holdings |
| Bear Stearns | 001690 | Bear Stearns Cos. |
| JP Morgan / Chase / Chemical | 012138 or 001690 | JPMorgan Chase & Co. (post-merger) |
| Citigroup | 070858 | Citigroup Inc. |
| First Boston / Credit Suisse | 001690 | CS First Boston (use CS if available) |
| Drexel Burnham Lambert | 003021 | |
| Paine Webber | 014871 | |
| Dean Witter Reynolds | 019671 | |

Include all the following dealers from Table A.1 (US-based, likely in CRSP-Compustat):

```python
PRIMARY_DEALERS = [
    # Major US dealers with known Compustat presence
    Dealer("Goldman Sachs", gvkey="011251", permno=None,
           start=date(1974, 12, 4), end=None),
    Dealer("Merrill Lynch", gvkey="012069", permno=None,
           start=date(1960, 5, 19), end=date(2010, 11, 1)),
    Dealer("Salomon Smith Barney", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(2003, 4, 6)),
    Dealer("Lehman Brothers", gvkey="012562", permno=None,
           start=date(1976, 11, 25), end=date(2008, 9, 22)),
    Dealer("Lehman Brothers (first run)", gvkey="012562", permno=None,
           start=date(1973, 2, 22), end=date(1974, 1, 29)),
    Dealer("Bear Stearns", gvkey="001690", permno=None,
           start=date(1981, 6, 10), end=date(2008, 10, 1)),
    Dealer("Morgan Stanley", gvkey="022365", permno=None,
           start=date(1978, 2, 1), end=None),
    Dealer("JP Morgan", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=None),
    Dealer("Citigroup", gvkey="070858", permno=None,
           start=date(1961, 6, 15), end=None),
    Dealer("Chemical Bank", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1996, 3, 31)),
    Dealer("Manufacturers Hanover", gvkey=None, permno=None,
           start=date(1983, 8, 31), end=date(1991, 12, 31)),
    Dealer("Bankers Trust", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1997, 10, 22)),
    Dealer("Continental", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1991, 8, 30)),
    Dealer("Discount Corp.", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1993, 8, 10)),
    Dealer("First Boston", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1993, 10, 11)),
    Dealer("Drexel Burnham", gvkey="003021", permno=None,
           start=date(1960, 5, 19), end=date(1990, 3, 28)),
    Dealer("Paine Webber", gvkey="014871", permno=None,
           start=date(1976, 11, 25), end=date(2000, 12, 4)),
    Dealer("Dean Witter Reynolds", gvkey="019671", permno=None,
           start=date(1977, 11, 2), end=date(1998, 4, 30)),
    Dealer("Kidder Peabody", gvkey=None, permno=None,
           start=date(1978, 11, 17), end=date(1994, 4, 15)),
    Dealer("Bank of America", gvkey=None, permno=None,
           start=date(1999, 5, 17), end=date(2010, 11, 1)),
    Dealer("Prudential", gvkey=None, permno=None,
           start=date(1975, 10, 29), end=date(2000, 12, 1)),
    Dealer("Dillon Read", gvkey=None, permno=None,
           start=date(1988, 6, 24), end=date(1997, 9, 2)),
    Dealer("Harris", gvkey=None, permno=None,
           start=date(1965, 7, 15), end=date(1995, 5, 31)),
    Dealer("Aubrey Lanston", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(2000, 4, 17)),
    Dealer("Blyth Eastman Dillon", gvkey=None, permno=None,
           start=date(1974, 12, 5), end=date(1979, 12, 31)),
    Dealer("Carroll McEntee", gvkey=None, permno=None,
           start=date(1976, 9, 29), end=date(1994, 5, 6)),
    Dealer("DLJ", gvkey=None, permno=None,
           start=date(1974, 3, 6), end=date(1983, 1, 16)),
    Dealer("DLJ (second run)", gvkey=None, permno=None,
           start=date(1995, 10, 25), end=date(2000, 12, 31)),
    Dealer("First Chicago", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1999, 3, 31)),
    Dealer("First Interstate", gvkey=None, permno=None,
           start=date(1964, 7, 31), end=date(1988, 6, 17)),
    Dealer("Midland-Montagu", gvkey=None, permno=None,
           start=date(1975, 8, 13), end=date(1990, 7, 26)),
    Dealer("NationsBanc", gvkey=None, permno=None,
           start=date(1993, 7, 6), end=date(1999, 5, 16)),
    Dealer("Security Pacific", gvkey=None, permno=None,
           start=date(1986, 12, 11), end=date(1991, 1, 17)),
    Dealer("White Weld", gvkey=None, permno=None,
           start=date(1976, 2, 26), end=date(1978, 4, 18)),
    Dealer("Becker", gvkey=None, permno=None,
           start=date(1958, 5, 8), end=date(1984, 9, 10)),
    Dealer("CF Childs", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1965, 6, 29)),
    Dealer("Chase", gvkey=None, permno=None,
           start=date(1970, 10, 12), end=date(2001, 4, 30)),
    Dealer("FI Dupont", gvkey=None, permno=None,
           start=date(1974, 12, 4), end=date(1973, 7, 18)),
    Dealer("First National Bank of Boston", gvkey=None, permno=None,
           start=date(1983, 3, 21), end=date(1985, 11, 17)),
    Dealer("Pollock", gvkey=None, permno=None,
           start=date(1960, 5, 19), end=date(1987, 2, 3)),
    Dealer("Second District", gvkey=None, permno=None,
           start=date(1961, 3, 15), end=date(1983, 8, 27)),
]
```

### Helper Function

```python
def get_active_dealers(as_of: datetime.date) -> list[Dealer]:
    """Return dealers active on the given date.

    A dealer is active if start <= as_of <= end (or end is None and as_of <= 2012-12-31).
    """
```

### GVKEY/PERMNO Resolution at Runtime

```python
def find_dealer_identifiers(
    dealers: list[Dealer],
    conn: psycopg2.extensions.connection,
) -> list[Dealer]:
    """Attempt to fill in missing gvkey/permno by fuzzy name-matching against Compustat/CRSP.

    For each dealer with gvkey=None, query comp.names for company names containing
    key words from the dealer name. Return updated dealer list with identifiers where found.
    Log matches and misses.
    """
```

This function queries `comp.names` (columns: `gvkey`, `conm`) and `crsp.msenames` (columns: `permno`, `comnam`) to find matches. Use simple substring matching (ILIKE in SQL). For each match found, log the result. Return an updated list. This is best-effort — unmatched dealers remain with gvkey=None and are excluded from the data pull.

---

## Module: `hkm/data/compustat.py`

### Purpose
Fetch quarterly balance sheet data from Compustat for a list of GVKEYs.

### Functions

```python
import pandas as pd
import psycopg2

def fetch_compustat_quarterly(
    gvkeys: list[str],
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
    conn: psycopg2.extensions.connection | None = None,
) -> pd.DataFrame:
    """Fetch quarterly Compustat data for the given GVKEYs.

    Returns DataFrame with columns:
        gvkey (str), datadate (pd.Timestamp), atq (float), ceqq (float),
        book_debt (float = atq - ceqq), fyearq (int), fqtr (int)

    Filters: datafmt = 'STD', indfmt = 'INDL', popsrc = 'D', consol = 'C'
    Only rows where atq > 0 and ceqq is not null are returned.
    """
```

**SQL query**:
```sql
SELECT gvkey, datadate, atq, ceqq, fyearq, fqtr
FROM comp.fundq
WHERE gvkey IN ({gvkey_placeholders})
  AND datadate BETWEEN '{start_date}' AND '{end_date}'
  AND datafmt = 'STD'
  AND indfmt = 'INDL'
  AND popsrc = 'D'
  AND consol = 'C'
  AND atq IS NOT NULL
  AND atq > 0
  AND ceqq IS NOT NULL
ORDER BY gvkey, datadate
```

**Post-processing**:
- Compute `book_debt = atq - ceqq` (may be negative for some firms; keep as-is)
- Convert `datadate` to `pd.Timestamp`
- Cast `gvkey` to string, zero-pad to 6 chars if needed
- Log: `f"Compustat: fetched {len(df)} rows for {len(gvkeys)} GVKEYs, date range {start_date}–{end_date}"`

```python
def fetch_compustat_all_quarterly(
    sic_filter: str | None = None,
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
    conn: psycopg2.extensions.connection | None = None,
) -> pd.DataFrame:
    """Fetch quarterly Compustat data for comparison groups (BD, Banks, all firms).

    Args:
        sic_filter: If 'BD', filter SIC 6211 or 6221.
                    If 'Banks', filter SIC 6000–6299.
                    If None, return all firms.

    Returns DataFrame with same schema as fetch_compustat_quarterly() plus:
        sich (str): historical SIC code
    """
```

**SQL for BD**:
```sql
SELECT gvkey, datadate, atq, ceqq, sich, fyearq, fqtr
FROM comp.fundq
WHERE sich IN ('6211', '6221')
  AND datadate BETWEEN '{start_date}' AND '{end_date}'
  AND datafmt = 'STD'
  AND indfmt = 'INDL'
  AND popsrc = 'D'
  AND consol = 'C'
  AND atq IS NOT NULL AND atq > 0 AND ceqq IS NOT NULL
ORDER BY gvkey, datadate
```

**SQL for Banks**:
```sql
WHERE CAST(sich AS INTEGER) BETWEEN 6000 AND 6299
```

**SQL for All**:
```sql
-- No SIC filter; all firms
```

Note: `sich` in Compustat is stored as a varchar. Cast to integer for range comparisons.

---

## Module: `hkm/data/crsp.py`

### Functions

```python
import pandas as pd
import psycopg2

def fetch_crsp_monthly(
    permnos: list[int],
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
    conn: psycopg2.extensions.connection | None = None,
) -> pd.DataFrame:
    """Fetch monthly CRSP stock data for given PERMNOs.

    Returns DataFrame with columns:
        permno (int), date (pd.Timestamp), prc (float), shrout (float),
        me (float = abs(prc) * shrout)  [in $ thousands, since shrout is in thousands]

    Note: prc can be negative (bid-ask midpoint); always use abs(prc).
    shrout is in thousands of shares. me = abs(prc) * shrout (in $thousands).
    """
```

**SQL**:
```sql
SELECT a.permno, a.date, a.prc, a.shrout
FROM crsp.msf a
WHERE a.permno IN ({permno_placeholders})
  AND a.date BETWEEN '{start_date}' AND '{end_date}'
  AND a.prc IS NOT NULL
  AND a.shrout IS NOT NULL AND a.shrout > 0
ORDER BY a.permno, a.date
```

**Post-processing**:
- `me = abs(prc) * shrout` (result in $thousands since shrout is in thousands of shares)
- Convert `date` to `pd.Timestamp`
- Log row count and date range

```python
def fetch_crsp_all_monthly(
    sic_codes: list[str] | None = None,
    sic_range: tuple[int, int] | None = None,
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
    conn: psycopg2.extensions.connection | None = None,
) -> pd.DataFrame:
    """Fetch monthly CRSP data for comparison groups filtered by SIC code.

    Args:
        sic_codes: List of exact SIC codes (e.g. ['6211', '6221'] for BD)
        sic_range: Tuple (low, high) for SIC range (e.g. (6000, 6299) for Banks)
        If both None, returns all common stocks.

    Returns DataFrame with same schema as fetch_crsp_monthly() plus:
        permno (int), siccd (str or int)
    """
```

**SQL approach**: Join `crsp.msf` with `crsp.msenames` on permno where namedt <= date <= nameendt to get current SIC code.

```sql
SELECT a.permno, a.date, a.prc, a.shrout, b.siccd
FROM crsp.msf a
JOIN crsp.msenames b ON a.permno = b.permno
  AND a.date BETWEEN b.namedt AND b.nameendt
WHERE a.prc IS NOT NULL AND a.shrout IS NOT NULL AND a.shrout > 0
  AND a.date BETWEEN '{start_date}' AND '{end_date}'
  AND b.shrcd IN (10, 11)  -- common stocks only
  [AND b.siccd IN (...) OR CAST(b.siccd AS INTEGER) BETWEEN ... ]
ORDER BY a.permno, a.date
```

**Notes**:
- `shrcd IN (10, 11)` restricts to ordinary common shares (US-incorporated)
- For BD: `b.siccd IN ('6211', '6221')`
- For Banks: `CAST(b.siccd AS INTEGER) BETWEEN 6000 AND 6299`
- For all: no SIC filter (but keep `shrcd IN (10, 11)`)

```python
def fetch_crsp_market_index(
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
    conn: psycopg2.extensions.connection | None = None,
) -> pd.DataFrame:
    """Fetch CRSP monthly value-weighted market index returns.

    Returns DataFrame with columns:
        date (pd.Timestamp), vwretd (float)  [value-weighted return with dividends]
    """
```

**SQL**: `SELECT date, vwretd FROM crsp.msi WHERE date BETWEEN ... ORDER BY date`

```python
def fetch_crsp_daily_vol(
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
    conn: psycopg2.extensions.connection | None = None,
) -> pd.DataFrame:
    """Fetch realized quarterly market volatility from CRSP daily value-weighted returns.

    Queries crsp.dsi for daily vwretd, then computes quarterly std deviation.

    Returns DataFrame with columns:
        quarter (pd.Period), mkt_vol (float)  [quarterly realized std dev of daily VW returns]
    """
```

**SQL**: `SELECT date, vwretd FROM crsp.dsi WHERE date BETWEEN ... ORDER BY date`

**Post-processing**: Group by calendar quarter (pd.Period), compute std dev of daily returns within each quarter. Return one row per quarter.

---

## Module: `hkm/data/macro.py`

### Purpose
Fetch all macro variables needed for Table 3 from public sources (FRED, Shiller, Chicago Fed).

### Functions

```python
import pandas as pd

def fetch_fred_series(
    series_ids: list[str],
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Fetch one or more FRED series using pandas-datareader.

    Returns DataFrame indexed by date (pd.Timestamp) with one column per series_id.
    Monthly or quarterly series are returned at their native frequency.
    """
```

Use `pandas_datareader.data.DataReader(series_id, 'fred', start, end)`.

```python
def fetch_shiller_ep(
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Download Shiller's S&P 500 data and extract the E/P ratio.

    URL: http://www.econ.yale.edu/~shiller/data/ie_data.xls
    Fallback URL: https://shillerdata.com/data/ie_data.xls

    Returns DataFrame with columns:
        date (pd.Timestamp, quarterly), ep_ratio (float)  [earnings / price]

    The Shiller data has columns: Date, P, D, E (trailing 12-month earnings), CPI, ...
    E/P ratio = E / P (raw, not cyclically adjusted)
    Monthly dates are converted to quarterly by averaging within quarter.
    """
```

**Implementation notes**:
- Download with `requests.get()`, save to a temporary file, read with `pd.read_excel()`, skip header rows
- The Excel file has a "Data" sheet. Relevant columns: Date (e.g. "1871.01" format), P (price), E (earnings)
- Parse Date column: e.g. 1871.01 → year=1871, month=1 → pd.Timestamp("1871-01-01")
- Compute `ep_ratio = E / P`
- Filter to requested date range
- Aggregate monthly to quarterly by taking the quarterly average

```python
def fetch_nfci(
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Download Chicago Fed National Financial Conditions Index (NFCI).

    URL: https://www.chicagofed.org/data-and-publications/research/nfci/download

    Returns DataFrame with columns:
        date (pd.Timestamp, quarterly), nfci (float)
    Weekly NFCI is aggregated to quarterly average.
    """
```

**Implementation notes**:
- Download CSV from Chicago Fed. The file has columns: date, NFCI (possibly others)
- Parse dates, convert to weekly pd.Timestamp
- Aggregate: group by quarter (pd.Grouper(freq='Q')), take mean
- Return one row per quarter

```python
def fetch_aem_leverage(
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Fetch AEM broker-dealer book leverage from Fed Z.1 Flow of Funds via FRED.

    Series:
        FL664090005Q: Security broker-dealers, total financial assets (quarterly, SA)
        FL664190005Q: Security broker-dealers, total liabilities (quarterly, SA)

    AEM leverage = FL664090005Q / (FL664090005Q - FL664190005Q)
                 = Total assets / Book equity
    AEM LevFac  = log(leverage_t / leverage_{t-1})  [seasonally adjusted growth rate]

    Returns DataFrame with columns:
        date (pd.Timestamp, quarterly), aem_leverage (float), aem_levfac (float)
    """
```

**Implementation**:
1. Fetch FL664090005Q and FL664190005Q from FRED
2. Align on quarterly dates
3. Compute `book_equity = assets - liabilities`
4. Compute `leverage = assets / book_equity` (book leverage = total assets / book equity)
5. Compute `levfac = log(leverage_t / leverage_{t-1})`
6. Note: FRED series are already seasonally adjusted; the log difference is the "seasonally adjusted growth rate"
7. Return both `aem_leverage` and `aem_levfac`

```python
def build_macro_panel(
    conn: psycopg2.extensions.connection | None = None,
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Assemble all macro series into a quarterly panel for Table 3.

    Returns DataFrame indexed by quarter (pd.Period('Q')) with columns:
        ep_ratio (float): Shiller E/P ratio, quarterly average
        unemp (float): Unemployment rate, quarterly average of monthly UNRATE
        gdp_growth (float): Log change of GDPC1, quarterly (ln(GDPC1_t/GDPC1_{t-1}))
        nfci (float): NFCI quarterly average
        mkt_vol (float): Realized quarterly volatility of CRSP daily VW returns
        mkt_ret (float): CRSP monthly VW excess return (VW return - T-bill / 4)
        aem_leverage (float): AEM book leverage level
        aem_levfac (float): AEM leverage factor (log change, seasonally adjusted)

    Growth rates (for Panel B of Table 3):
        ep_growth (float): log(ep_ratio_t / ep_ratio_{t-1})
        unemp_growth (float): log(unemp_t / unemp_{t-1})
        nfci_growth (float): log(|nfci_t| / |nfci_{t-1}|) or first difference
        mkt_vol_growth (float): log(mkt_vol_t / mkt_vol_{t-1})
    """
```

**T-bill rate**: Fetch FRED TB3MS (3-month T-bill, monthly). Convert to quarterly rate = TB3MS / 4 / 100 (annualized percentage → quarterly decimal). Compute `mkt_ret = vwretd_quarterly - tbill_quarterly` where `vwretd_quarterly` is the compounded quarterly return from CRSP monthly index.

**NFCI growth note**: NFCI can be negative (high values = poor financial conditions, low or negative = good conditions). For growth rate, use first log difference of NFCI + constant if needed, or use simple arithmetic change (NFCI_t - NFCI_{t-1}). Prefer log change but protect against negative values with `np.sign(nfci) * log(|nfci|)` or simply use `pct_change()`. Use the same approach consistently and document it.

---

## Module: `hkm/data/intermediary.py`

### Purpose
Build the primary dealer capital ratio (η_t) and the capital ratio factor (η_t^Δ), for both market-based and book-based definitions.

### Functions

```python
import pandas as pd
import numpy as np
import psycopg2
from hkm.data.dealers import PRIMARY_DEALERS, get_active_dealers, find_dealer_identifiers
from hkm.data.compustat import fetch_compustat_quarterly
from hkm.data.crsp import fetch_crsp_monthly
from hkm.utils import get_logger

def build_capital_ratio(
    conn: psycopg2.extensions.connection,
    frequency: str = "Q",  # "Q" or "M"
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Compute the primary dealer capital ratio η_t.

    η_t = Σ_i ME_{i,t} / Σ_i (ME_{i,t} + BD_{i,t})

    where ME = CRSP market equity = |prc| × shrout ($thousands)
          BD = Compustat book debt = AT − CEQ ($millions → convert to $thousands)

    Algorithm:
    1. Resolve dealer GVKEYs/PERMNOs via find_dealer_identifiers()
    2. Fetch Compustat quarterly for all dealer GVKEYs (atq, ceqq)
    3. Fetch CRSP monthly for all dealer PERMNOs
    4. For each time period t:
       a. Identify active dealers at t
       b. For each active dealer: get ME from CRSP (last day of the period/quarter)
          and book debt from Compustat (most recent quarter end <= t)
       c. Aggregate: η_t = Σ ME / Σ (ME + BD)
    5. Also compute book_capital_ratio_t = Σ CEQ / Σ (CEQ + BD)

    Returns DataFrame with index=date (monthly or quarterly), columns:
        eta (float): market capital ratio
        book_capital (float): book capital ratio = Σ CEQ / Σ (AT)
        n_dealers (int): number of dealers with data in that period
    """
```

**Key implementation details**:

1. **Unit alignment**: Compustat reports AT and CEQ in $ millions. CRSP `shrout` is in thousands of shares and `prc` is in dollars, so ME = `|prc| × shrout` = $ thousands. Convert Compustat to thousands by multiplying by 1000, or convert CRSP ME to millions by dividing by 1000. Must be consistent.

2. **Most recent quarterly data**: For each month (or quarter) t, for each dealer, use the most recent `datadate` from Compustat that is <= t. Use `pd.merge_asof()` or a backward merge.

3. **Missing data**: If a dealer has no Compustat data for a period (either GVKEY not found or no recent quarterly filing), exclude that dealer from the numerator and denominator for that period. Log the exclusion.

4. **CRSP-Compustat link**: Use `crsp.ccmxpf_linktable` to map between GVKEY and PERMNO:
```sql
SELECT gvkey, lpermno AS permno, linkdt, linkenddt, linktype, linkprim
FROM crsp.ccmxpf_linktable
WHERE linktype IN ('LU', 'LC', 'LS')
  AND linkprim IN ('P', 'C')
```
Match on `linkdt <= date <= linkenddt` (or `linkenddt IS NULL`).

5. **Quarterly η_t for Table 3**: Use last month of each quarter's CRSP ME matched with most recent quarterly Compustat filing. Quarter periods: March, June, September, December.

6. **Monthly for Table 2**: Use each month-end CRSP ME with most recent quarterly Compustat.

```python
def build_capital_factor(
    eta: pd.Series,
    frequency: str = "Q",
) -> pd.Series:
    """Compute the capital ratio factor = AR(1) innovations scaled by lagged ratio.

    Fits OLS AR(1): η_t = ρ_0 + ρ × η_{t-1} + u_t on the full sample.
    Returns u_t / η_{t-1} for each t.

    The first observation will be NaN (no lagged value for the first period).
    The estimated ρ should be approximately 0.94 (paper footnote 22).

    Args:
        eta: pd.Series of capital ratio values, indexed by date/period
        frequency: 'Q' for quarterly, 'M' for monthly (determines lag)

    Returns:
        pd.Series of same index as eta, with capital ratio factor values.
        First element is NaN.
    """
```

**Implementation**:
```python
import statsmodels.api as sm

def build_capital_factor(eta: pd.Series, frequency: str = "Q") -> pd.Series:
    # Align eta_t and eta_{t-1}
    eta_lag = eta.shift(1)
    valid = eta.notna() & eta_lag.notna()

    # OLS: eta_t = rho0 + rho * eta_{t-1} + u_t
    X = sm.add_constant(eta_lag[valid])
    y = eta[valid]
    res = sm.OLS(y, X).fit()

    # Get residuals for all valid observations
    resids = pd.Series(index=eta.index, dtype=float)
    resids[valid] = res.resid

    # Scale by lagged ratio: factor = u_t / eta_{t-1}
    factor = resids / eta_lag
    return factor
```

Log the estimated ρ (should be ~0.94) at INFO level.

---

## Module: `hkm/tables/table2.py`

### Purpose
Compute Table 2: average sizes of primary dealers relative to comparison groups.

### Function

```python
import pandas as pd
import psycopg2
from hkm.utils import wrds_connection, get_logger

def compute_table2(
    conn: psycopg2.extensions.connection | None = None,
    start_date: str = "1960-01-01",
    end_date: str = "2012-12-31",
) -> pd.DataFrame:
    """Compute Table 2: primary dealer size relative to comparison groups.

    Returns pd.DataFrame of shape (3, 12):
        Index: ['1960-2012', '1960-1990', '1990-2012']
        Columns: MultiIndex with level 0 = items, level 1 = groups
            items = ['Total assets', 'Book debt', 'Book equity', 'Market equity']
            groups = ['BD', 'Banks', 'Cmpust']

    Algorithm:
    For each calendar month t in [1960-01, 2012-12]:
        1. Identify active primary dealers at t
        2. For each dealer: get TA (atq), BD (atq-ceqq), BE (ceqq), ME (|prc|*shrout)
           - TA, BD, BE from most recent Compustat quarterly filing
           - ME from CRSP monthly (last trading day of month)
        3. Sum across all dealers: TA_d, BD_d, BE_d, ME_d
        4. For each comparison group G ∈ {BD, Banks, Cmpust}:
           - Sum G's TA, BD, BE, ME from Compustat + CRSP (all US firms in group at t)
           - Compute ratio_t(item, G) = dealer_item_t / group_item_t
    After computing monthly ratios:
        Take time-series average of ratio_t over:
            - Full period: all t in [1960-01, 2012-12]
            - Early: t in [1960-01, 1989-12]
            - Late: t in [1990-01, 2012-12]
    """
```

**Critical note on comparison group**:
- For the BD comparison group: Compustat firms with SIC 6211 or 6221. This includes primary dealers themselves (dealers ⊆ BD group). The ratio is thus: dealer_sum / all_BD_sum (where dealers are counted in both numerator and denominator).
- For Banks: Compustat firms with SIC 6000–6299.
- For Cmpust: All Compustat firms.

**Data fetching approach**:
1. Fetch all Compustat quarterly for dealers (by GVKEY)
2. Fetch all CRSP monthly for dealers (by PERMNO)
3. Fetch all Compustat quarterly for each comparison group (by SIC) — use all firms, not just dealers
4. Fetch all CRSP monthly for each comparison group (by SIC) — use `fetch_crsp_all_monthly()`

**Monthly panel construction**:
For each month:
- Dealer TA/BD/BE: most recent quarterly Compustat filing (datadate <= month end)
- Dealer ME: CRSP month-end price × shares
- Group TA/BD/BE: sum across all firms in group with most recent quarterly filing
- Group ME: sum across all firms in group from CRSP month end

**Return format**:
```python
import pandas as pd

# Create MultiIndex columns
items = ['Total assets', 'Book debt', 'Book equity', 'Market equity']
groups = ['BD', 'Banks', 'Cmpust']
cols = pd.MultiIndex.from_product([items, groups], names=['item', 'group'])
index = ['1960-2012', '1960-1990', '1990-2012']
result = pd.DataFrame(index=index, columns=cols, dtype=float)
```

**Unit handling**: Compustat AT, CEQ are in $ millions. CRSP ME in $ thousands (|prc| × shrout). When summing across groups, use consistent units (convert all to millions: ME / 1000). Ratios are dimensionless so units cancel if consistent within numerator/denominator.

---

## Module: `hkm/tables/table3.py`

### Purpose
Compute Table 3: pairwise correlations of capital measures and macro variables.

### Function

```python
import pandas as pd
import psycopg2
from hkm.utils import wrds_connection, get_logger

def compute_table3(
    conn: psycopg2.extensions.connection | None = None,
    start_date: str = "1970-01-01",
    end_date: str = "2012-12-31",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute Table 3: pairwise time-series correlations.

    Returns:
        (panel_a, panel_b): Two DataFrames.

    panel_a: Correlations of levels, shape (8, 3)
        Index: ['Market capital', 'Book capital', 'AEM leverage',
                'E/P', 'Unemployment', 'GDP', 'Financial conditions', 'Market volatility']
        Columns: ['Market capital', 'Book capital', 'AEM leverage']

    panel_b: Correlations of factors, shape (9, 3)
        Index: ['Market capital factor', 'Book capital factor', 'AEM leverage factor',
                'Market excess return', 'E/P growth', 'Unemployment growth',
                'GDP growth', 'Financial conditions growth', 'Market volatility growth']
        Columns: ['Market capital factor', 'Book capital factor', 'AEM leverage factor']
    """
```

**Algorithm**:

1. **Build quarterly capital ratios** (1970Q1–2012Q4):
   - Call `build_capital_ratio(conn, frequency='Q')` → DataFrame with `eta` and `book_capital` columns
   - Compute factors: `build_capital_factor(eta_series)` and `build_capital_factor(book_capital_series)`

2. **Fetch AEM leverage** from `fetch_aem_leverage()` → columns `aem_leverage` and `aem_levfac`

3. **Fetch macro panel** from `build_macro_panel(conn)` → quarterly DataFrame with all macro variables

4. **Align all series on quarterly dates** using `pd.concat([...], axis=1, join='inner')` to get the common 1970Q1–2012Q4 sample.

5. **Panel A — levels**:
   - Variables: `eta`, `book_capital`, `aem_leverage`, `ep_ratio`, `unemp`, `gdp_growth`, `nfci`, `mkt_vol`
   - Use `pd.DataFrame.corr()` or pairwise `pd.Series.corr()` with `method='pearson'`
   - Note: GDP in Panel A is the quarterly log change (the paper correlates capital ratio levels with GDP *growth*, not GDP level)

6. **Panel B — factors**:
   - Capital variables: factors of `eta`, `book_capital`, `aem_levfac`
   - Macro variables: `mkt_ret` (excess return), `ep_growth`, `unemp_growth`, `gdp_growth`, `nfci_growth`, `mkt_vol_growth`
   - Use `pd.DataFrame.corr()` with method='pearson'

7. **Format output**:
   - For panel_a: full correlation matrix is symmetric; the table in the paper shows only the lower triangle plus cross-correlations. Return the full matrix for completeness.
   - Diagonal = 1.0

**Important note on Panel A GDP**: The paper's Panel A shows GDP correlation of +0.18 for market capital. This is GDP growth (log change of GDPC1), NOT the level of GDP. The paper labels it "GDP" in Panel A but "GDP growth" in Panel B — they are the same series. Confirmed by paper text: "decreases in GDP growth coincides with lower capital ratio."

---

## Module: `hkm/__init__.py`

```python
from hkm.tables.table2 import compute_table2
from hkm.tables.table3 import compute_table3

__all__ = ["compute_table2", "compute_table3"]
```

---

## Module: `hkm/tables/__init__.py`

```python
from hkm.tables.table2 import compute_table2
from hkm.tables.table3 import compute_table3

__all__ = ["compute_table2", "compute_table3"]
```

---

## `pyproject.toml` Updates

Add the following section to the existing `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "ANN"]
ignore = ["ANN101", "ANN102"]

[tool.mypy]
strict = true
ignore_missing_imports = true
python_version = "3.10"
```

Do NOT replace the existing `[project]` or `[project.optional-dependencies]` sections.

---

## README.md

Create a `README.md` at the repo root with:
- Project title: "HKM (2017) Replication: Tables 2 and 3"
- One-paragraph description
- Setup instructions (WRDS credentials via `~/.pgpass`, `pip install -e ".[dev]"`)
- Usage example:
  ```python
  from hkm import compute_table2, compute_table3
  from hkm.utils import wrds_connection

  with wrds_connection() as conn:
      t2 = compute_table2(conn=conn)
      panel_a, panel_b = compute_table3(conn=conn)

  print(t2)
  print(panel_a)
  print(panel_b)
  ```
- Note on data sources

---

## Error Handling Rules

1. All functions that accept `conn` should raise `ConnectionError` with a descriptive message if `conn is None` and a connection cannot be established internally.
2. Never use bare `except`. Always catch specific exceptions.
3. Use `logger.warning()` for non-fatal data quality issues (missing firms, zero rows).
4. Use `logger.error()` and re-raise for fatal issues.
5. No `print()` calls anywhere in `hkm/`.

---

## Type Annotation Rules

All public functions must have complete type annotations:
- Return types specified
- All parameters typed
- Use `X | None` syntax (Python 3.10+), not `Optional[X]`
- Use `list[X]`, `dict[K, V]`, `tuple[X, Y]` (Python 3.10+ built-in generics)
- Avoid `Any` unless unavoidable

---

## Implementation Order

Implement in this order to resolve dependencies:

1. `hkm/utils.py` (no dependencies)
2. `hkm/data/wrds_connect.py` (depends on utils)
3. `hkm/data/dealers.py` (no WRDS dependency)
4. `hkm/data/compustat.py` (depends on wrds_connect)
5. `hkm/data/crsp.py` (depends on wrds_connect)
6. `hkm/data/macro.py` (no WRDS dependency except market index)
7. `hkm/data/intermediary.py` (depends on compustat, crsp, dealers)
8. `hkm/tables/table2.py` (depends on intermediary, compustat, crsp)
9. `hkm/tables/table3.py` (depends on intermediary, macro)
10. `hkm/__init__.py`, `hkm/tables/__init__.py`, `hkm/data/__init__.py`
11. `tests/test_data.py`, `tests/test_tables.py` (minimal stubs — tester will fill in)
12. `pyproject.toml` updates, `README.md`

---

## `implementation.md` (to be written by builder)

After completing implementation, write `implementation.md` to the run directory with:
- List of all files created/modified
- GVKEY/PERMNO matches found for each dealer (from `find_dealer_identifiers()`)
- Any deviations from this spec and rationale
- Known limitations (e.g., dealers with no WRDS match)
- Ruff and mypy output (must show zero errors)

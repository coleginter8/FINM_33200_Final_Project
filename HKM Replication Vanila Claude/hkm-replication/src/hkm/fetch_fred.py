"""Fetch FRED series for HKM Tables 2 & 3 (no API key — pandas-datareader + CSV fallback)."""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import requests

from .io import get_logger, raw

LOG = get_logger("fetch_fred")

# series_id -> label
SERIES: dict[str, str] = {
    "BOGZ1FL664090005Q": "z1_bd_financial_assets",
    "BOGZ1FL664190005Q": "z1_bd_total_liabilities",
    "NFCI": "nfci",
    "UNRATE": "unrate",
    "GDPC1": "gdpc1",
}


def _read_pdr(series_id: str, start: datetime, end: datetime) -> pd.Series:
    from pandas_datareader import data as pdr  # local import → avoids cold-start cost
    df = pdr.DataReader(series_id, "fred", start, end)
    return df[series_id]


def _read_csv_fallback(series_id: str, start: datetime, end: datetime) -> pd.Series:
    """fredgraph.csv endpoint requires no key."""
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    LOG.info("CSV fallback: %s", url)
    r = requests.get(url, timeout=60, headers={"User-Agent": "hkm-replication/0.1"})
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    date_col = df.columns[0]
    val_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).loc[start:end]
    s = pd.to_numeric(df[val_col], errors="coerce").dropna()
    s.name = series_id
    return s


def fetch_one(series_id: str, *, start="1945-01-01", end="2012-12-31") -> pd.Series:
    s_dt = pd.Timestamp(start).to_pydatetime()
    e_dt = pd.Timestamp(end).to_pydatetime()
    try:
        s = _read_pdr(series_id, s_dt, e_dt)
        if s.empty:
            raise RuntimeError("pandas-datareader returned empty")
        LOG.info("FRED via pdr ok: %s rows=%d", series_id, len(s))
    except Exception as e:  # noqa: BLE001
        LOG.warning("pdr failed for %s (%s) — trying CSV", series_id, e)
        s = _read_csv_fallback(series_id, s_dt, e_dt)
        LOG.info("FRED via CSV ok: %s rows=%d", series_id, len(s))
    return s


def fetch_all() -> dict[str, pd.Series]:
    out_dir = raw("fred")
    series_dict: dict[str, pd.Series] = {}
    # Choose start dates: Z.1 starts 1945Q4 (paper uses ~1960+), GDPC1 1947Q1, NFCI 1971-01
    for sid in SERIES:
        s = fetch_one(sid)
        series_dict[sid] = s
        s.to_frame().to_csv(out_dir / f"{sid}.csv")
    LOG.info("FRED pull complete — %d series", len(series_dict))
    return series_dict


if __name__ == "__main__":
    d = fetch_all()
    for k, v in d.items():
        print(f"{k}: rows={len(v)} range={v.index.min().date()}..{v.index.max().date()}")

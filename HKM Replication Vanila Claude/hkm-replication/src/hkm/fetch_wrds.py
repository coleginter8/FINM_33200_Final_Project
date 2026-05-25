"""WRDS CRSP-Compustat pulls.

Pulls and caches:
  * crsp.msenames (company name history, for the PD name search)
  * crsp.msf joined with msenames (monthly: PRC, SHROUT, EXCHCD, SICCD, NAMECO)
  * crsp.dsf (daily VW returns, for realized market vol)
  * comp.fundq (quarterly fundamentals: atq, ceqq)
  * crsp.ccmxpf_linktable (PERMNO ↔ GVKEY)

Each function caches its output as a parquet under data/raw/wrds/.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import get_logger, raw, wrds_connect

LOG = get_logger("fetch_wrds")


def _conn():
    LOG.info("Opening WRDS connection")
    return wrds_connect()


def pull_msenames(force: bool = False) -> pd.DataFrame:
    out = raw("wrds") / "msenames.parquet"
    if out.exists() and not force:
        LOG.info("Cached %s", out)
        return pd.read_parquet(out)
    sql = """
        SELECT permno, permco, namedt, nameendt, comnam, ticker,
               shrcd, exchcd, siccd, ncusip
        FROM crsp.msenames
        WHERE namedt IS NOT NULL
    """
    with _conn() as c:
        df = c.raw_sql(sql, date_cols=["namedt", "nameendt"])
    df.to_parquet(out)
    LOG.info("Wrote %s rows=%d", out, len(df))
    return df


def pull_msf(start: str = "1959-01-01", end: str = "2013-12-31", force: bool = False) -> pd.DataFrame:
    """Monthly stock file × names — every US common stock.

    SHRCD ∈ {10, 11} keeps US common; EXCHCD ∈ {1,2,3} keeps NYSE/AMEX/NASDAQ.
    """
    out = raw("wrds") / f"msf_{start[:4]}_{end[:4]}.parquet"
    if out.exists() and not force:
        LOG.info("Cached %s", out)
        return pd.read_parquet(out)
    sql = f"""
        SELECT a.permno, a.permco, a.date,
               a.prc, a.shrout, a.ret, a.retx,
               b.shrcd, b.exchcd, b.siccd, b.comnam
        FROM crsp.msf a
        LEFT JOIN crsp.msenames b
          ON a.permno = b.permno
         AND a.date BETWEEN b.namedt AND b.nameendt
        WHERE a.date BETWEEN '{start}' AND '{end}'
          AND b.shrcd IN (10, 11)
          AND b.exchcd BETWEEN 1 AND 3
    """
    with _conn() as c:
        df = c.raw_sql(sql, date_cols=["date"])
    df["prc"] = df["prc"].abs()
    df["market_equity"] = df["prc"] * df["shrout"] / 1000.0  # $M
    df.to_parquet(out)
    LOG.info("Wrote %s rows=%d", out, len(df))
    return df


def pull_dsf_vw(start: str = "1962-01-01", end: str = "2013-12-31", force: bool = False) -> pd.DataFrame:
    out = raw("wrds") / f"dsfvw_{start[:4]}_{end[:4]}.parquet"
    if out.exists() and not force:
        LOG.info("Cached %s", out)
        return pd.read_parquet(out)
    sql = f"""
        SELECT date AS caldt, vwretd, vwretx, ewretd, sprtrn
        FROM crsp.dsi
        WHERE date BETWEEN '{start}' AND '{end}'
    """
    with _conn() as c:
        df = c.raw_sql(sql, date_cols=["caldt"])
    df.to_parquet(out)
    LOG.info("Wrote %s rows=%d", out, len(df))
    return df


def pull_fundq(start: str = "1959-01-01", end: str = "2013-12-31", force: bool = False) -> pd.DataFrame:
    out = raw("wrds") / f"fundq_{start[:4]}_{end[:4]}.parquet"
    if out.exists() and not force:
        LOG.info("Cached %s", out)
        return pd.read_parquet(out)
    sql = f"""
        SELECT gvkey, datadate, fyearq, fqtr,
               atq, ceqq, ltq, dlcq, dlttq,
               cshoq, prccq
        FROM comp.fundq
        WHERE datadate BETWEEN '{start}' AND '{end}'
          AND indfmt = 'INDL' AND datafmt = 'STD' AND popsrc = 'D' AND consol = 'C'
          AND curcdq = 'USD'
    """
    with _conn() as c:
        df = c.raw_sql(sql, date_cols=["datadate"])
    df.to_parquet(out)
    LOG.info("Wrote %s rows=%d", out, len(df))
    return df


def pull_ccm(force: bool = False) -> pd.DataFrame:
    out = raw("wrds") / "ccmxpf_linktable.parquet"
    if out.exists() and not force:
        LOG.info("Cached %s", out)
        return pd.read_parquet(out)
    sql = """
        SELECT gvkey, lpermno AS permno, lpermco AS permco,
               linkdt, linkenddt, linktype, linkprim, liid
        FROM crsp.ccmxpf_linktable
        WHERE linktype IN ('LC','LU','LS')
          AND linkprim IN ('P','C')
    """
    with _conn() as c:
        df = c.raw_sql(sql, date_cols=["linkdt", "linkenddt"])
    df["linkenddt"] = df["linkenddt"].fillna(pd.Timestamp("2099-12-31"))
    df.to_parquet(out)
    LOG.info("Wrote %s rows=%d", out, len(df))
    return df


def pull_all(force: bool = False) -> dict:
    return {
        "msenames": pull_msenames(force=force),
        "msf": pull_msf(force=force),
        "dsf_vw": pull_dsf_vw(force=force),
        "fundq": pull_fundq(force=force),
        "ccm": pull_ccm(force=force),
    }


if __name__ == "__main__":
    d = pull_all()
    for k, v in d.items():
        print(f"{k}: rows={len(v)}")

"""Fetch Ken French research factors (monthly): Mkt-RF, RF."""
from __future__ import annotations

import io
import zipfile

import pandas as pd
import requests

from .io import get_logger, raw

LOG = get_logger("fetch_ff")

URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_Factors_CSV.zip"
)


def _first_token(line: str) -> str:
    return line.split(",", 1)[0].strip()


def fetch() -> pd.DataFrame:
    LOG.info("Downloading FF research factors from %s", URL)
    r = requests.get(URL, timeout=60, headers={"User-Agent": "hkm-replication/0.1"})
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(name) as fh:
            raw_txt = fh.read().decode("latin-1")

    # FF CSV has metadata header; keep only rows starting with a 6-digit YYYYMM.
    lines = raw_txt.splitlines()
    monthly_rows = [ln for ln in lines if _first_token(ln).isdigit() and len(_first_token(ln)) == 6]
    if not monthly_rows:
        raise RuntimeError("Could not find monthly block in FF CSV")
    # Header is the last line before any data that begins with a comma (skip metadata)
    data_start = lines.index(monthly_rows[0])
    header_line = next(
        ln for ln in reversed(lines[:data_start]) if ln.strip().startswith(",")
    )
    cols = ["yyyymm"] + [c.strip() for c in header_line.split(",")[1:]]
    block = "\n".join(monthly_rows)
    df = pd.read_csv(io.StringIO(block), header=None, names=cols)
    df["yyyymm"] = df["yyyymm"].astype(int)
    df["date"] = pd.to_datetime(df["yyyymm"].astype(str), format="%Y%m") + pd.offsets.MonthEnd(0)
    df = df.drop(columns=["yyyymm"]).set_index("date")
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce") / 100.0  # percent → decimal
    out = raw("ff") / "ff_research_factors_monthly.csv"
    df.to_csv(out)
    LOG.info("Wrote %s rows=%d range=%s..%s", out, len(df), df.index.min().date(), df.index.max().date())
    return df


if __name__ == "__main__":
    df = fetch()
    print(df.head())

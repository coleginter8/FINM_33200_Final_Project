"""Fetch Zhiguo He's bundled HKM factor (intermediary_capital_ratio + risk factor).

Used only for validation cross-checks (validation.py).
"""
from __future__ import annotations

import re

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .io import get_logger, raw

LOG = get_logger("fetch_zhiguohe")

PAGE = (
    "https://zhiguohe.net/data-and-empirical-patterns/"
    "intermediary-capital-ratio-and-risk-factor/"
)


def _discover_links() -> dict[str, str]:
    """Scrape the page for monthly + quarterly CSV links."""
    r = requests.get(PAGE, timeout=60, headers={"User-Agent": "hkm-replication/0.1"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    monthly = quarterly = None
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.endswith(".csv") and "He_Kelly_Manela" in href:
            if "monthly" in href.lower():
                monthly = href
            elif "quarterly" in href.lower():
                quarterly = href
    return {"monthly": monthly, "quarterly": quarterly}


def fetch() -> dict[str, pd.DataFrame]:
    out_dir = raw("zhiguo_he")
    links = _discover_links()
    LOG.info("Discovered: %s", links)
    out = {}
    for key, url in links.items():
        if not url:
            LOG.warning("No %s URL found on page", key)
            continue
        local = out_dir / url.rsplit("/", 1)[-1]
        LOG.info("Downloading %s → %s", url, local)
        r = requests.get(url, timeout=60, headers={"User-Agent": "hkm-replication/0.1"})
        r.raise_for_status()
        local.write_bytes(r.content)
        df = pd.read_csv(local)
        # Normalize the date column → quarterly index.
        df.columns = [c.strip() for c in df.columns]
        # Common columns: 'yyyymm' or 'yyyyq' or 'date' or 'Date'
        date_col = next(
            (c for c in df.columns if c.lower() in {"date", "yyyymm", "yyyyq", "yq", "yyyy_q"}),
            df.columns[0],
        )
        out[key] = df.rename(columns={date_col: "date_raw"})
        out[key].to_csv(local.with_suffix(".normalized.csv"), index=False)
    return out


if __name__ == "__main__":
    d = fetch()
    for k, v in d.items():
        print(k, list(v.columns), v.shape)

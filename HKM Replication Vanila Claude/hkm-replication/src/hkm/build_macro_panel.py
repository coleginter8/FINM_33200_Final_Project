"""Quarterly macro panel: levels (Panel A) and log changes (Panel B)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .io import get_logger, processed, raw

LOG = get_logger("build_macro_panel")


def _load_fred(series_id: str) -> pd.Series:
    df = pd.read_csv(raw("fred") / f"{series_id}.csv", index_col=0, parse_dates=True)
    return df.iloc[:, 0].rename(series_id).astype(float)


def _ff_mkt_xret_q() -> pd.Series:
    ff = pd.read_csv(raw("ff") / "ff_research_factors_monthly.csv", index_col=0, parse_dates=True)
    mkt = ff["Mkt-RF"]
    # Compound monthly to quarterly: (1+r1)(1+r2)(1+r3) - 1
    g = (1.0 + mkt).resample("QE").prod() - 1.0
    g.name = "mkt_xret_q"
    return g


def _mkt_vol_q() -> pd.Series:
    """Realized vol within quarter from daily VW returns (rough proxy for AB market vol).

    Uses CRSP daily VW total return when available; otherwise falls back to FF
    monthly approximation = sqrt(sum of squared monthly excess returns within Q).
    """
    dsf_path = raw("wrds") / "dsfvw_1962_2013.parquet"
    if dsf_path.exists():
        d = pd.read_parquet(dsf_path).dropna(subset=["vwretd"])
        d["q"] = d["caldt"] + pd.offsets.QuarterEnd(0)
        # subtract within-quarter mean for "demeaned" RV
        g = d.groupby("q")["vwretd"].apply(
            lambda x: float(np.sqrt(((x - x.mean()) ** 2).sum()))
        )
        g.name = "mkt_vol_q"
        return g
    LOG.warning("Daily CRSP not found — using FF monthly approx for realized vol")
    ff = pd.read_csv(raw("ff") / "ff_research_factors_monthly.csv", index_col=0, parse_dates=True)
    mkt = ff["Mkt-RF"]
    g = mkt.resample("QE").apply(lambda x: float(np.sqrt(((x - x.mean()) ** 2).sum())))
    g.name = "mkt_vol_q"
    return g


def _shiller_ep() -> pd.Series:
    sh = pd.read_csv(raw("shiller") / "shiller_monthly.csv", index_col=0, parse_dates=True)
    # End-of-quarter E/P
    g = sh["E_P_TTM"].resample("QE").last()
    g.name = "ep_q"
    return g


def build() -> pd.DataFrame:
    nfci = _load_fred("NFCI").resample("QE").last().rename("nfci_q")
    unrate = _load_fred("UNRATE").resample("QE").mean().rename("unemp_q")
    gdp = _load_fred("GDPC1").resample("QE").last().rename("gdp_q")
    mkt_xret = _ff_mkt_xret_q()
    mkt_vol = _mkt_vol_q()
    ep = _shiller_ep()

    df = pd.concat([nfci, unrate, gdp, mkt_xret, mkt_vol, ep], axis=1).sort_index()
    df.index.name = "date_q"

    # Growth versions (log changes), with NFCI as simple diff because it goes negative
    df["nfci_growth_q"] = df["nfci_q"].diff()
    for col in ["unemp_q", "gdp_q", "mkt_vol_q", "ep_q"]:
        df[col.replace("_q", "_growth_q")] = np.log(df[col]).diff()
    out = df.reset_index()
    out_path = processed() / "macro_panel_quarterly.parquet"
    out.to_parquet(out_path)
    LOG.info("Wrote %s rows=%d", out_path, len(out))
    return out


if __name__ == "__main__":
    print(build().tail(8))

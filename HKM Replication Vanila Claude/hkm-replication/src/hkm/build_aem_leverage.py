"""Build AEM (Adrian-Etula-Muir) broker-dealer leverage series from Z.1.

Outputs data/processed/aem_quarterly.parquet with columns:
  date_q, aem_leverage, aem_implied_capital, aem_factor
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .io import get_logger, processed, raw

LOG = get_logger("build_aem_leverage")


def _load_fred(series_id: str) -> pd.Series:
    p = raw("fred") / f"{series_id}.csv"
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    return df.iloc[:, 0].rename(series_id)


def build() -> pd.DataFrame:
    assets = _load_fred("BOGZ1FL664090005Q")
    liab = _load_fred("BOGZ1FL664190005Q")
    df = pd.concat([assets, liab], axis=1).dropna()
    df.columns = ["assets", "liabilities"]
    df["equity"] = df["assets"] - df["liabilities"]
    df["aem_leverage"] = df["assets"] / df["equity"]
    df["aem_implied_capital"] = df["equity"] / df["assets"]
    # Filter to valid (positive) equity
    df = df[df["equity"] > 0].copy()
    df.index = df.index + pd.offsets.QuarterEnd(0)
    df.index.name = "date_q"

    # AEM factor: SA log growth of leverage via quarter-dummy residuals
    lev = np.log(df["aem_leverage"]).astype(float)
    q = df.index.quarter
    dummies = pd.get_dummies(q, prefix="q", drop_first=True).astype(float)
    dummies.index = df.index
    X = sm.add_constant(dummies).astype(float)
    y = np.asarray(lev.values, dtype=float)
    Xv = np.asarray(X.values, dtype=float)
    model = sm.OLS(y, Xv, missing="drop").fit()
    resid = pd.Series(y - model.predict(Xv), index=df.index, name="lev_sa")
    df["aem_factor"] = resid.diff()
    out = (
        df.reset_index()[["date_q", "aem_leverage", "aem_implied_capital", "aem_factor"]]
    )
    out_path = processed() / "aem_quarterly.parquet"
    out.to_parquet(out_path)
    LOG.info("Wrote %s rows=%d range=%s..%s", out_path, len(out), out["date_q"].min(), out["date_q"].max())
    return out


if __name__ == "__main__":
    print(build().tail(8))

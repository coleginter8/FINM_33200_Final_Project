"""Capital ratio innovation factors: ε_t / X_{t-1} where ε_t is AR(1) residual."""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .io import get_logger, processed

LOG = get_logger("build_factors")


def _ar1_factor(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(float)
    y = np.asarray(s.iloc[1:].values, dtype=float)
    x = np.asarray(s.iloc[:-1].values, dtype=float)
    X = sm.add_constant(x)
    mod = sm.OLS(y, X).fit()
    resid = pd.Series(y - mod.predict(X), index=s.iloc[1:].index)
    factor = resid / np.asarray(s.iloc[:-1].values, dtype=float)
    return factor


def build() -> pd.DataFrame:
    cr = pd.read_parquet(processed() / "capital_ratios_quarterly.parquet")
    cr = cr.sort_values("date_q").reset_index(drop=True)
    out = pd.DataFrame({"date_q": cr["date_q"]})
    out["market_capital_factor"] = _ar1_factor(cr.set_index("date_q")["mkt_cap_ratio"]).reindex(cr["date_q"]).values
    out["book_capital_factor"] = _ar1_factor(cr.set_index("date_q")["book_cap_ratio"]).reindex(cr["date_q"]).values
    out_path = processed() / "factors_quarterly.parquet"
    out.to_parquet(out_path)
    LOG.info("Wrote %s rows=%d", out_path, len(out))
    return out


if __name__ == "__main__":
    print(build().tail(8))

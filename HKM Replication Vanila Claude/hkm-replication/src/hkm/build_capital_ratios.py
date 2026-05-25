"""Market and book capital ratios for the PD aggregate, quarterly end-of-period."""
from __future__ import annotations

import pandas as pd

from .io import get_logger, processed

LOG = get_logger("build_capital_ratios")


def build() -> pd.DataFrame:
    g = pd.read_parquet(processed() / "group_aggregates_monthly.parquet")
    pd_g = g[g["group"] == "pd"].copy().sort_values("month_end")
    # Require at least one firm with Compustat data; otherwise ratios are
    # spurious (e.g., book_debt=0 → mkt_cap_ratio=1).
    mask = (pd_g["n_with_compustat"].fillna(0) >= 1) & pd_g["book_debt"].fillna(0).gt(0)
    pd_g["mkt_cap_ratio"] = (pd_g["market_equity"] / (pd_g["market_equity"] + pd_g["book_debt"])).where(mask)
    pd_g["book_cap_ratio"] = (pd_g["book_equity"] / (pd_g["book_equity"] + pd_g["book_debt"])).where(mask)
    # End-of-quarter values
    pd_g["q_end"] = pd_g["month_end"] + pd.offsets.QuarterEnd(0)
    q = (
        pd_g[pd_g["month_end"] == pd_g["q_end"]][
            ["q_end", "mkt_cap_ratio", "book_cap_ratio", "market_equity", "book_equity", "book_debt"]
        ]
        .rename(columns={"q_end": "date_q"})
        .reset_index(drop=True)
    )
    out = processed() / "capital_ratios_quarterly.parquet"
    q.to_parquet(out)
    LOG.info("Wrote %s rows=%d range=%s..%s", out, len(q), q["date_q"].min(), q["date_q"].max())
    return q


if __name__ == "__main__":
    print(build().tail(10))

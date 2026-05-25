"""Build the firm-level monthly panel of primary-dealer parents and comparison groups.

Outputs:
  data/processed/firm_panel_monthly.parquet     — one row per (permco, month_end)
  data/processed/group_aggregates_monthly.parquet — one row per (group, month_end)

The 6 group rows per month are:
  pd, bd_only, bd_union_pd, banks_only, banks_union_pd, cmpust_union_pd
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .fetch_wrds import pull_ccm, pull_fundq, pull_msf
from .io import PROJECT_ROOT, get_logger, processed

LOG = get_logger("build_pd_panel")


BD_SIC = {6211}
# Depository institutions broadly: 6000-6199 captures national/state commercial
# banks, savings institutions, federal savings banks, credit unions, etc. PLAN.md
# initially specified 6020-6029 + 6712, but that excluded firms HKM includes in
# Table 2 (savings institutions like Washington Mutual, etc.) — widened here so
# the Banks denominator matches published magnitudes more closely.
BANK_SIC = set(range(6000, 6200)) | {6712}


def _load_pd_map() -> pd.DataFrame:
    path = PROJECT_ROOT / "data" / "pd_to_permno_map.csv"
    df = pd.read_csv(path, parse_dates=["start_date", "end_date"])
    df = df[df["permno"].notna() & df["confidence"].isin(["high", "medium"])].copy()
    df["permno"] = df["permno"].astype(int)
    df["permco"] = df["permco"].astype("Int64")
    return df


def _calendar_align_fundq(fundq: pd.DataFrame, ccm: pd.DataFrame) -> pd.DataFrame:
    """Quarterly fundamentals → monthly, indexed by PERMCO at calendar quarter-end."""
    # Map GVKEY → PERMCO via the link table (no time restriction needed at this level
    # — multiple permnos per gvkey collapse to the same permco for share-class agg).
    link = ccm.drop_duplicates(subset=["gvkey", "permco"])[["gvkey", "permco", "linkdt", "linkenddt"]]
    fq = fundq.merge(link, on="gvkey", how="inner")
    fq = fq[(fq["datadate"] >= fq["linkdt"]) & (fq["datadate"] <= fq["linkenddt"])]

    fq["q_end"] = fq["datadate"] + pd.offsets.QuarterEnd(0)
    # Aggregate to PERMCO × q_end (some GVKEYs share a PERMCO during the panel)
    agg = (
        fq.groupby(["permco", "q_end"])
        .agg(atq=("atq", "sum"), ceqq=("ceqq", "sum"))
        .reset_index()
    )
    agg["book_debt"] = agg["atq"] - agg["ceqq"]
    agg["book_equity"] = agg["ceqq"]
    agg["total_assets"] = agg["atq"]
    return agg[["permco", "q_end", "total_assets", "book_equity", "book_debt"]]


def _monthly_panel(msf: pd.DataFrame, fundq_pcq: pd.DataFrame) -> pd.DataFrame:
    """Combine monthly MSF with quarter-end Compustat, forward-fill within quarter."""
    m = msf.copy()
    m["month_end"] = m["date"] + pd.offsets.MonthEnd(0)
    # Aggregate market_equity within (permco, month) (sum across share classes)
    m_agg = (
        m.groupby(["permco", "month_end"])
        .agg(
            market_equity=("market_equity", "sum"),
            siccd=("siccd", "first"),
            comnam=("comnam", "first"),
        )
        .reset_index()
    )
    # Now expand fundq_pcq from quarter to month: assign datadate to its quarter,
    # then forward-fill within the quarter via merge_asof.
    fundq_pcq = fundq_pcq.rename(columns={"q_end": "month_end"})
    out = m_agg.merge(fundq_pcq, on=["permco", "month_end"], how="left")
    out = out.sort_values(["permco", "month_end"])
    # ffill within each permco for total_assets/book_debt/book_equity (carry quarter-end
    # value across the 3 months of the quarter)
    fcols = ["total_assets", "book_equity", "book_debt"]
    out[fcols] = out.groupby("permco")[fcols].ffill(limit=3)
    return out


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    LOG.info("Loading WRDS data")
    msf = pull_msf()
    fundq = pull_fundq()
    ccm = pull_ccm()

    LOG.info("Calendar-aligning Compustat fundamentals to quarter-end")
    fundq_pcq = _calendar_align_fundq(fundq, ccm)

    LOG.info("Building monthly firm panel")
    panel = _monthly_panel(msf, fundq_pcq)

    # === PD parent assignment per month ===
    pd_map = _load_pd_map()
    pd_map_long = []
    for _, r in pd_map.iterrows():
        months = pd.date_range(r["start_date"], r["end_date"], freq="ME")
        for m_end in months:
            pd_map_long.append(
                {
                    "permno": r["permno"],
                    "permco": r["permco"],
                    "parent_holdco": r["parent_holdco_name"],
                    "month_end": m_end,
                }
            )
    pd_long = pd.DataFrame(pd_map_long)

    # Join PD parent ↔ PERMCO ↔ month
    pd_panel = panel.merge(
        pd_long[["permco", "month_end", "parent_holdco"]].drop_duplicates(),
        on=["permco", "month_end"],
        how="inner",
    )

    LOG.info("PD panel rows: %d (over %d permcos)", len(pd_panel), pd_panel["permco"].nunique())

    # === Group flags on the full panel ===
    panel["is_pd"] = panel["permco"].isin(pd_panel["permco"].unique())
    panel["is_bd_only"] = panel["siccd"].isin(BD_SIC) & ~panel["is_pd"]
    panel["is_bank_only"] = panel["siccd"].isin(BANK_SIC) & ~panel["is_pd"]
    panel["is_bd_union_pd"] = panel["is_pd"] | panel["is_bd_only"]
    panel["is_bank_union_pd"] = panel["is_pd"] | panel["is_bank_only"]
    panel["is_cmpust_union_pd"] = (
        panel["total_assets"].notna()
        | panel["is_pd"]
    )

    # Persist firm-level panel
    out_firm = processed() / "firm_panel_monthly.parquet"
    panel.to_parquet(out_firm)
    LOG.info("Wrote %s rows=%d", out_firm, len(panel))

    # === Group aggregates ===
    # Use min_count=1 so a fully-NaN month returns NaN (not 0) — important pre-1962
    # when Compustat coverage is missing.
    def _agg_for(mask_col: str, label: str) -> pd.DataFrame:
        sub = panel[panel[mask_col]]
        g = (
            sub.groupby("month_end")
            .agg(
                total_assets=("total_assets", lambda s: s.sum(min_count=1)),
                book_equity=("book_equity", lambda s: s.sum(min_count=1)),
                book_debt=("book_debt", lambda s: s.sum(min_count=1)),
                market_equity=("market_equity", lambda s: s.sum(min_count=1)),
                n_firms=("permco", "nunique"),
                n_with_compustat=("total_assets", lambda s: int(s.notna().sum())),
            )
            .reset_index()
        )
        g["group"] = label
        return g

    parts = [
        _agg_for("is_pd", "pd"),
        _agg_for("is_bd_only", "bd_only"),
        _agg_for("is_bank_only", "banks_only"),
        _agg_for("is_bd_union_pd", "bd_union_pd"),
        _agg_for("is_bank_union_pd", "banks_union_pd"),
        _agg_for("is_cmpust_union_pd", "cmpust_union_pd"),
    ]
    groups = pd.concat(parts, ignore_index=True)
    out_grp = processed() / "group_aggregates_monthly.parquet"
    groups.to_parquet(out_grp)
    LOG.info("Wrote %s rows=%d", out_grp, len(groups))
    return panel, groups


if __name__ == "__main__":
    p, g = build()
    print("Firm panel:", p.shape)
    print("Group aggs:", g.shape)
    print(g.groupby("group")["n_firms"].mean().round(1))

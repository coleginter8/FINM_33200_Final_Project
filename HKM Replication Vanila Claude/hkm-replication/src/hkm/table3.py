"""Table 3: pairwise correlations of capital ratios / factors and macro series."""
from __future__ import annotations

import pandas as pd

from .io import get_logger, load_settings, processed, tables_dir

LOG = get_logger("table3")


def _quarter(s: str) -> pd.Timestamp:
    return pd.Period(s, freq="Q").end_time.normalize()


def _load_panel() -> pd.DataFrame:
    cr = pd.read_parquet(processed() / "capital_ratios_quarterly.parquet")
    aem = pd.read_parquet(processed() / "aem_quarterly.parquet")
    fac = pd.read_parquet(processed() / "factors_quarterly.parquet")
    mac = pd.read_parquet(processed() / "macro_panel_quarterly.parquet")
    for d in (cr, aem, fac, mac):
        d["date_q"] = pd.to_datetime(d["date_q"]) + pd.offsets.QuarterEnd(0)
    df = (
        cr.merge(aem, on="date_q", how="outer")
        .merge(fac, on="date_q", how="outer")
        .merge(mac, on="date_q", how="outer")
        .sort_values("date_q")
        .reset_index(drop=True)
    )
    return df


def build() -> dict:
    s = load_settings()["sample"]
    start = _quarter(s["table3_start"])
    end = _quarter(s["table3_end"])
    df = _load_panel()
    df = df[(df["date_q"] >= start) & (df["date_q"] <= end)].copy()
    LOG.info("Table 3 sample: %s..%s, n=%d", df["date_q"].min(), df["date_q"].max(), len(df))

    # Panel A — levels
    # NOTE: HKM Panel A row labelled "AEM leverage" empirically matches the raw
    # aem_leverage series (sign of corr with market_cap_ratio is +). The PLAN.md
    # initially asserted it should be aem_implied_capital, but the empirical sign
    # of the published +0.42 confirms it's the leverage ratio. Using aem_leverage.
    A_intermed = ["mkt_cap_ratio", "book_cap_ratio", "aem_leverage"]
    A_macro = ["ep_q", "unemp_q", "gdp_q", "nfci_q", "mkt_vol_q"]

    def corr(a, b):
        if a == b:
            return 1.0
        sub = df[[a, b]].dropna()
        return float(sub[a].corr(sub[b])) if len(sub) > 2 else float("nan")

    A_rows = []
    for i, x in enumerate(A_intermed):
        for j, y in enumerate(A_intermed):
            A_rows.append(
                {"panel": "A", "row_label": x, "col_label": y, "corr": corr(x, y) if i >= j else None}
            )
    for x in A_macro:
        for y in A_intermed:
            A_rows.append({"panel": "A", "row_label": x, "col_label": y, "corr": corr(x, y)})

    # Panel B — factors / growth
    B_intermed = ["market_capital_factor", "book_capital_factor", "aem_factor"]
    B_macro = [
        "mkt_xret_q",
        "ep_growth_q",
        "unemp_growth_q",
        "gdp_growth_q",
        "nfci_growth_q",
        "mkt_vol_growth_q",
    ]
    B_rows = []
    for i, x in enumerate(B_intermed):
        for j, y in enumerate(B_intermed):
            B_rows.append(
                {"panel": "B", "row_label": x, "col_label": y, "corr": corr(x, y) if i >= j else None}
            )
    for x in B_macro:
        for y in B_intermed:
            B_rows.append({"panel": "B", "row_label": x, "col_label": y, "corr": corr(x, y)})

    out_df = pd.DataFrame(A_rows + B_rows)
    out_csv = tables_dir() / "table_3.csv"
    out_df.to_csv(out_csv, index=False)
    LOG.info("Wrote %s", out_csv)

    out_tex = tables_dir() / "table_3.tex"
    out_tex.write_text(_render_latex(out_df))
    LOG.info("Wrote %s", out_tex)
    return {"df": out_df}


def _fmt(v):
    if v is None or pd.isna(v):
        return ""
    return f"{v:.2f}"


def _render_latex(df: pd.DataFrame) -> str:
    def _section(panel: str, intermed: list[str], macro: list[str], title: str) -> str:
        d = df[df["panel"] == panel].copy()
        # Build a wide matrix: rows = intermed + macro, cols = intermed
        rows = intermed + macro
        cols = intermed
        mat = pd.DataFrame(index=rows, columns=cols, dtype=float)
        for _, r in d.iterrows():
            if r["col_label"] in cols and r["row_label"] in rows:
                mat.loc[r["row_label"], r["col_label"]] = r["corr"]
        lines = [
            rf"\multicolumn{{{len(cols)+1}}}{{l}}{{\textbf{{{title}}}}} \\",
            r" & " + " & ".join(cols) + r" \\",
            r"\hline",
        ]
        for row_lbl, row in mat.iterrows():
            lines.append(row_lbl + " & " + " & ".join(_fmt(v) for v in row) + r" \\")
        return "\n".join(lines)

    A = _section(
        "A",
        ["mkt_cap_ratio", "book_cap_ratio", "aem_leverage"],
        ["ep_q", "unemp_q", "gdp_q", "nfci_q", "mkt_vol_q"],
        "Panel A: levels",
    )
    B = _section(
        "B",
        ["market_capital_factor", "book_capital_factor", "aem_factor"],
        ["mkt_xret_q", "ep_growth_q", "unemp_growth_q", "gdp_growth_q", "nfci_growth_q", "mkt_vol_growth_q"],
        "Panel B: factors / growth",
    )
    col_spec = "l" + "c" * 3
    return (
        r"\begin{tabular}{" + col_spec + "}\n"
        r"\hline\hline" + "\n"
        + A + "\n"
        r"\hline" + "\n"
        + B + "\n"
        r"\hline\hline" + "\n"
        r"\end{tabular}" + "\n"
    )


if __name__ == "__main__":
    d = build()
    print(d["df"].head(20))

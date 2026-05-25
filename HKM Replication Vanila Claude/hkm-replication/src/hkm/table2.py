"""Table 2: time-series average size ratios of PDs vs comparison groups."""
from __future__ import annotations

import pandas as pd

from .io import PROJECT_ROOT, get_logger, processed, tables_dir

LOG = get_logger("table2")


PERIODS = [(1960, 2012), (1960, 1990), (1990, 2012)]
NUMERATORS = ["total_assets", "book_debt", "book_equity", "market_equity"]
# Denominator groups in the order they appear in the paper
DENOM_GROUPS = [("bd_union_pd", "BD"), ("banks_union_pd", "Banks"), ("cmpust_union_pd", "Cmpust")]


def build() -> pd.DataFrame:
    g = pd.read_parquet(processed() / "group_aggregates_monthly.parquet")
    wide = g.pivot_table(index="month_end", columns="group", values=NUMERATORS)
    # wide has MultiIndex columns: (metric, group)
    rows = []
    for (y0, y1) in PERIODS:
        sub = wide.loc[
            (wide.index >= pd.Timestamp(f"{y0}-01-01"))
            & (wide.index <= pd.Timestamp(f"{y1}-12-31"))
        ]
        row = {"period": f"{y0}-{y1}"}
        for metric in NUMERATORS:
            for grp, grp_lbl in DENOM_GROUPS:
                num = sub[(metric, "pd")]
                denom = sub[(metric, grp)]
                ratio = (num / denom).where(denom > 0)
                row[f"{metric}__{grp_lbl}"] = float(ratio.mean(skipna=True))
        rows.append(row)
    out = pd.DataFrame(rows)
    out_csv = tables_dir() / "table_2.csv"
    out.to_csv(out_csv, index=False)
    LOG.info("Wrote %s", out_csv)

    # LaTeX
    latex = _render_latex(out)
    out_tex = tables_dir() / "table_2.tex"
    out_tex.write_text(latex)
    LOG.info("Wrote %s", out_tex)
    return out


def _render_latex(df: pd.DataFrame) -> str:
    headers = ["Total assets", "Book debt", "Book equity", "Market equity"]
    sub_headers = ["BD", "Banks", "Cmpust"]
    metric_order = NUMERATORS
    body_lines = []
    for _, r in df.iterrows():
        cells = [r["period"]]
        for m in metric_order:
            for grp_lbl in sub_headers:
                cells.append(f"{r[f'{m}__{grp_lbl}']:.3f}")
        body_lines.append(" & ".join(cells) + r" \\")
    col_spec = "l" + "c" * (4 * 3)
    multi = " & ".join(rf"\multicolumn{{3}}{{c}}{{{h}}}" for h in headers)
    subhd = " & ".join(sub_headers * 4)
    return (
        r"\begin{tabular}{" + col_spec + "}\n"
        r"\hline\hline" + "\n"
        r"Period & " + multi + r" \\" + "\n"
        r" & " + subhd + r" \\" + "\n"
        r"\hline" + "\n"
        + "\n".join(body_lines) + "\n"
        r"\hline\hline" + "\n"
        r"\end{tabular}" + "\n"
    )


if __name__ == "__main__":
    print(build())

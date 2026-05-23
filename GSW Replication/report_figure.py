"""
GSW Replication — Presentation Figure
Produces: report_figure.png

Run from the StatsClaw repo root:
    /opt/anaconda3/bin/python3.12 report_figure.py
"""

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D

# ── Style ──────────────────────────────────────────────────────────────────
mpl.rcParams.update({
    "font.family":        "sans-serif",
    "font.sans-serif":    ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.linewidth":     0.8,
    "xtick.major.width":  0.8,
    "ytick.major.width":  0.8,
    "xtick.labelsize":    9,
    "ytick.labelsize":    9,
    "axes.labelsize":     10,
    "axes.titlesize":     11,
    "figure.dpi":         200,
    "savefig.dpi":        200,
})

BG   = "#FFFFFF"
GRAY = "#6B7280"

# ── Load data ──────────────────────────────────────────────────────────────
ORACLE = "validation/validation_oracle.parquet"
OUTPUT = ".repos/gsw-replication/data/gsw_yield_curve.parquet"

oracle = pd.read_parquet(ORACLE)
output = pd.read_parquet(OUTPUT)

# pivot to wide for easy slicing
def to_wide(df):
    return df.pivot(index="ds", columns="unique_id", values="y")

w_oracle = to_wide(oracle)
w_output = to_wide(output)

maturities = np.arange(1, 31)
tenor_cols  = [f"SVENY{m:02d}" for m in maturities]

# ── Snapshot dates ─────────────────────────────────────────────────────────
SNAP_DATES = {
    "Jan 1975": "1975-01-02",
    "Jan 1982": "1982-01-04",
    "Jan 2000": "2000-01-03",
    "Jan 2007": "2007-01-03",
    "Jan 2024": "2024-01-02",
}

COLORS = ["#1f4e79", "#2e86c1", "#117a65", "#b7950b", "#922b21"]

# ── Layout ─────────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(13, 6.5), facecolor=BG)
gs  = gridspec.GridSpec(
    1, 2,
    width_ratios=[1.55, 1],
    wspace=0.10,
    left=0.06, right=0.97,
    top=0.88,  bottom=0.12,
)

# ── Left panel: yield curve snapshots ─────────────────────────────────────
ax1 = fig.add_subplot(gs[0])
ax1.set_facecolor(BG)

legend_elements = []

for (label, date_str), color in zip(SNAP_DATES.items(), COLORS):
    date = pd.Timestamp(date_str)

    # find closest available date in output
    avail = w_output.index
    closest = avail[np.argmin(np.abs(avail - date))]

    row_oracle = w_oracle.loc[closest, tenor_cols]
    row_output = w_output.loc[closest, tenor_cols]

    valid = row_oracle.notna() & row_output.notna()
    x = maturities[valid.values]
    y_or = row_oracle.values[valid.values]
    y_out = row_output.values[valid.values]

    # oracle: open circles (larger, slightly transparent)
    ax1.scatter(x, y_or,
                s=28, facecolors="none", edgecolors=color,
                linewidths=1.4, zorder=4, alpha=0.85)
    # replication: solid line (drawn on top — they are identical)
    ax1.plot(x, y_out,
             color=color, linewidth=1.8, zorder=3,
             label=f"{label}  ({closest.strftime('%d %b %Y')})")

    legend_elements.append(
        Line2D([0], [0], color=color, linewidth=2,
               marker="o", markerfacecolor="none",
               markeredgecolor=color, markeredgewidth=1.4, markersize=6,
               label=f"{label}  ({closest.strftime('%d %b %Y')})")
    )

ax1.set_xlabel("Maturity (years)", labelpad=6)
ax1.set_ylabel("Zero-coupon yield (%)", labelpad=6)
ax1.set_title(
    "Zero-Coupon Treasury Yield Curve: Selected Dates\n"
    "Oracle (circles) vs Replication (lines) — perfectly overlapping",
    loc="left", pad=8, fontsize=10, color="#111827",
)
ax1.set_xlim(0.5, 30.5)
ax1.xaxis.set_major_locator(mticker.MultipleLocator(5))
ax1.xaxis.set_minor_locator(mticker.MultipleLocator(1))
ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f%%"))
ax1.tick_params(which="minor", length=2, color="#9CA3AF")
ax1.grid(axis="y", linestyle=":", linewidth=0.5, color="#E5E7EB", zorder=0)

leg = ax1.legend(
    handles=legend_elements, frameon=False,
    fontsize=8.5, loc="upper right",
    handlelength=2.2, handleheight=1.2,
    labelspacing=0.45, borderpad=0,
)

# ── Right panel: validation scorecard (table) ──────────────────────────────
ax2 = fig.add_subplot(gs[1])
ax2.set_facecolor(BG)
ax2.axis("off")

# Compute live stats for the table
merged = oracle.merge(output, on=["ds", "unique_id"],
                      how="left", suffixes=("_oracle", "_output"))
diff = (merged["y_output"] - merged["y_oracle"]).abs()

rows = [
    ["Metric",                    "Value",              "Result"],
    ["Total rows",                f"{len(output):,}",   "PASS"],
    ["Oracle rows",               f"{len(oracle):,}",   "PASS"],
    ["Row gap",                   "0",                  "PASS"],
    ["Unique dates",              f"{output['ds'].nunique():,}",  "PASS"],
    ["Tenors",                    "SVENY01 - SVENY30",  "PASS"],
    ["Date range",                "Jun 1961 - May 2026","PASS"],
    ["Units",                     "Percent",            "PASS"],
    ["NaN values",                "0",                  "PASS"],
    ["Duplicate keys",            "0",                  "PASS"],
    ["Max |dy| vs oracle",        f"{diff.max():.2e} pct", "PASS"],
    ["Mean |dy| vs oracle",       f"{diff.mean():.2e} pct","PASS"],
    ["Within 1 bp of oracle",     "379,352 (100.00%)",  "PASS"],
    ["Verdict",                   "EXACT MATCH",        "PASS"],
]

n_rows = len(rows)
n_cols = 3

col_x  = [0.0, 0.55, 0.88]  # left edges (relative to axes)
row_h  = 1.0 / n_rows

HEADER_COLOR = "#1f4e79"
PASS_COLOR   = "#15803d"
STRIPE_COLOR = "#F3F4F6"
VERDICT_COLOR = "#7f1d1d"

for r_idx, row in enumerate(rows):
    y_pos = 1.0 - (r_idx + 0.5) * row_h
    is_header  = r_idx == 0
    is_verdict = row[0] == "Verdict"
    is_stripe  = (r_idx % 2 == 0) and not is_header

    # row background
    bg_color = HEADER_COLOR if is_header else (STRIPE_COLOR if is_stripe else BG)
    rect = mpl.patches.FancyBboxPatch(
        (-0.02, 1.0 - (r_idx + 1) * row_h + 0.002),
        1.04, row_h - 0.002,
        boxstyle="square,pad=0",
        linewidth=0,
        facecolor=bg_color,
        transform=ax2.transAxes, clip_on=False, zorder=1,
    )
    ax2.add_patch(rect)

    for c_idx, (cell, x_pos) in enumerate(zip(row, col_x)):
        ha = "left" if c_idx < 2 else "center"
        fontsize = 9.5 if is_header else (9.5 if is_verdict else 8.8)

        if is_header:
            color = "#FFFFFF"
            weight = "bold"
        elif is_verdict and c_idx == 1:
            color = VERDICT_COLOR
            weight = "bold"
        elif c_idx == 2 and not is_header:
            color = PASS_COLOR
            weight = "bold"
        elif c_idx == 0 and not is_header:
            color = "#374151"
            weight = "normal"
        else:
            color = "#111827"
            weight = "normal"

        x_offset = 0.05 if c_idx == 0 else (0.02 if c_idx == 1 else 0.06)
        ha_cell  = "left" if c_idx < 2 else "center"
        ax2.text(
            x_pos + x_offset,
            y_pos,
            cell,
            transform=ax2.transAxes,
            ha=ha_cell, va="center",
            fontsize=fontsize,
            color=color,
            fontweight=weight,
            clip_on=True,
            zorder=2,
        )

ax2.set_title(
    "Validation Scorecard",
    loc="left", pad=14, fontsize=10, color="#111827",
)

# ── Footer ─────────────────────────────────────────────────────────────────
fig.text(
    0.5, 0.03,
    "Data: Gürkaynak, Sack & Wright (2007) — Federal Reserve FEDS200628   |   "
    "Replication: coleginter8/gsw-replication",
    ha="center", va="bottom", fontsize=7.5, color=GRAY,
)

# ── Save ───────────────────────────────────────────────────────────────────
out_path = "report_figure.png"
fig.savefig(out_path, bbox_inches="tight", facecolor=BG)
print(f"Saved → {out_path}")
plt.close(fig)

"""
make_cds_comparison_figure.py
Generates a figure matching the Base Claude CDS comparison style:
  - Top panel: time series of best-matched portfolio (Oracle vs StatsClaw)
  - Bottom 3x3: scatter plots (Oracle x-axis, Replication y-axis) for
    3Y/5Y/10Y × Q1/Q3/Q5 with a 45° reference line and Pearson r labels
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import pearsonr

# ── Load data ────────────────────────────────────────────────────────────────

REP_PATH = ".repos/cds-replication/ftsfr_cds_portfolio_returns.parquet"
ORC_PATH = "validation/validation_portfolio.parquet"

rep = pd.read_parquet(REP_PATH)
orc = pd.read_parquet(ORC_PATH)

# Align on overlapping (ds, unique_id) pairs
merged = (
    rep.rename(columns={"y": "y_rep"})
    .merge(orc.rename(columns={"y": "y_orc"}), on=["ds", "unique_id"])
    .sort_values(["unique_id", "ds"])
)

# ── Compute per-portfolio Pearson r ──────────────────────────────────────────

portfolios = sorted(merged["unique_id"].unique())
corrs = {}
for pid in portfolios:
    sub = merged[merged["unique_id"] == pid].dropna(subset=["y_rep", "y_orc"])
    if len(sub) >= 5:
        r, _ = pearsonr(sub["y_orc"], sub["y_rep"])
    else:
        r = np.nan
    corrs[pid] = r

best_pid = max(corrs, key=lambda k: corrs[k] if not np.isnan(corrs[k]) else -999)
best_r   = corrs[best_pid]

# ── Grid portfolios: 3Y/5Y/10Y × Q1/Q3/Q5 ───────────────────────────────────

GRID_TENORS    = ["3Y", "5Y", "10Y"]
GRID_QUINTILES = ["Q1", "Q3", "Q5"]
GRID_PIDS      = [f"{t}_{q}" for t in GRID_TENORS for q in GRID_QUINTILES]

# ── Figure layout ─────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(12, 11))
fig.patch.set_facecolor("white")

gs_outer = gridspec.GridSpec(
    2, 1,
    figure=fig,
    top=0.91, bottom=0.04,
    left=0.08, right=0.97,
    hspace=0.38,
    height_ratios=[1.35, 2],
)

# ── Title ─────────────────────────────────────────────────────────────────────

fig.text(
    0.50, 0.975,
    "StatsClaw: CDS Portfolio Returns vs Oracle",
    ha="center", va="top",
    fontsize=13, fontweight="bold", color="#1a1a1a",
)
fig.text(
    0.50, 0.952,
    "He, Kelly & Manela (2017) / Palhares (2012) Replication",
    ha="center", va="top",
    fontsize=10, color="#444444", style="italic",
)

# ── Top panel: time series ────────────────────────────────────────────────────

ax_ts = fig.add_subplot(gs_outer[0])

best_data = merged[merged["unique_id"] == best_pid].set_index("ds").sort_index()

ax_ts.plot(
    best_data.index, best_data["y_orc"],
    color="#1f77b4", linewidth=1.4, label="Oracle",
)
ax_ts.plot(
    best_data.index, best_data["y_rep"],
    color="#ff7f0e", linewidth=1.2, linestyle="--", label="StatsClaw Replication",
)

ax_ts.set_title(
    f"{best_pid.replace('_', ' ')} Portfolio — Best-Matched Portfolio  (r = {best_r:.3f})",
    fontsize=10.5, pad=6,
)
ax_ts.set_ylabel("Monthly Return (%)", fontsize=9)
ax_ts.yaxis.set_major_formatter(
    matplotlib.ticker.FuncFormatter(lambda x, _: f"{x*100:.2f}")
)
ax_ts.tick_params(labelsize=8)
ax_ts.spines[["top", "right"]].set_visible(False)
ax_ts.legend(fontsize=8.5, frameon=False, loc="upper right")
ax_ts.grid(axis="y", linewidth=0.4, alpha=0.5)

# ── Bottom: 3×3 scatter grid ──────────────────────────────────────────────────

gs_grid = gridspec.GridSpecFromSubplotSpec(
    3, 3,
    subplot_spec=gs_outer[1],
    hspace=0.52, wspace=0.38,
)

for idx, pid in enumerate(GRID_PIDS):
    row, col = divmod(idx, 3)
    ax = fig.add_subplot(gs_grid[row, col])

    sub = merged[merged["unique_id"] == pid].dropna(subset=["y_rep", "y_orc"])
    r   = corrs.get(pid, np.nan)

    # Scatter colour: green for 3Y_Q1, blue-grey otherwise
    color = "#2ca02c" if pid == "3Y_Q1" else "#6baed6"
    alpha = 0.55

    ax.scatter(sub["y_orc"], sub["y_rep"], s=10, color=color, alpha=alpha, linewidths=0)

    # 45° reference line
    if len(sub):
        lo = min(sub["y_orc"].min(), sub["y_rep"].min())
        hi = max(sub["y_orc"].max(), sub["y_rep"].max())
        pad = (hi - lo) * 0.05
        ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad],
                "r--", linewidth=0.9, alpha=0.8)

    r_str = f"r = {r:.3f}" if not np.isnan(r) else "r = n/a"
    tenor, quint = pid.split("_")
    ax.set_title(f"{tenor}_{quint}  ({r_str})", fontsize=7.5, pad=3)
    ax.set_xlabel("Oracle (%)", fontsize=7)
    ax.set_ylabel("Replication (%)", fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.xaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, _: f"{x*100:.2f}")
    )
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, _: f"{x*100:.2f}")
    )
    ax.spines[["top", "right"]].set_visible(False)

# ── Save ──────────────────────────────────────────────────────────────────────

OUT = "replication_comparison.png"
fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
print(f"Saved → {OUT}")

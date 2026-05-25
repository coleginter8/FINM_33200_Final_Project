"""
make_replication_figure.py
Generates a presentation-ready PNG summarising the HKM (2017) / Palhares (2012)
CDS portfolio replication results.
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.gridspec as gridspec
import warnings
warnings.filterwarnings("ignore")

# ── Data ────────────────────────────────────────────────────────────────────

# Per-portfolio Pearson correlation with oracle (tester R3 audit)
corr_data = {
    "3Y":  [ 0.976,  0.051,  0.042,  0.067,  0.116],
    "5Y":  [-0.042,  0.000, -0.158,  0.045,  0.143],
    "7Y":  [-0.177, -0.079, -0.011, -0.102, -0.102],
    "10Y": [ 0.099, -0.102,  0.115,  0.074,  0.056],
}
tenors    = ["3Y", "5Y", "7Y", "10Y"]
quintiles = ["Q1", "Q2", "Q3", "Q4", "Q5"]
corr_df   = pd.DataFrame(corr_data, index=quintiles).T   # (4 × 5)

# Key metrics for the validation table
metrics = [
    # (component, value/result, ok, note)
    # ok: True=PASS, False=GAP, None=NOTE
    ("Palhares formula",          "r = S_{t-1}/12 + (S_{t-1}−S_t)·RD_{t-1}",    True,  "Sign match = 100%"),
    ("Portfolio aggregation",     "Carry-only: y = mean(S_{prev}/12)",             True,  "Confirmed by 100% sign match"),
    ("Entry-month ds label",      "ds = 1st-of-month of entry EOM",                True,  "Required for oracle alignment"),
    ("Quintile monotonicity",     "Q1 ≤ Q2 ≤ Q3 ≤ Q4 ≤ Q5 (mean return)",       True,  "All 4 tenors pass"),
    ("Tenor monotonicity",        "3Y ≤ 5Y ≤ 7Y ≤ 10Y (mean return)",            True,  "5/5 quintiles pass"),
    ("3Y_Q1 replication",         "Pearson r = 0.976 vs oracle",                  True,  "IG carry is macro-factor driven"),
    ("5Y / 7Y / 10Y portfolios",  "r = −0.18 to +0.14 vs oracle",                 False, "Universe gap: ~808 vs ~184 tickers/mo"),
    ("Contract coverage",         "69.8% of oracle pairs covered",                True,  "Pre-2008 oracle unreachable in WRDS"),
    ("Contract return std",       "0.070  (threshold: 0.005 – 0.100)",            True,  "After 50% spread cap on stale quotes"),
    ("Spread cap (50%)",          "Excludes post-default stale quotes",            None,  "Builder assumption; not in HKM/Palhares"),
]

# ── Figure ───────────────────────────────────────────────────────────────────

fig = plt.figure(figsize=(14, 9.5))
fig.patch.set_facecolor("#FAFAFA")

gs = gridspec.GridSpec(
    1, 2,
    figure=fig,
    left=0.04, right=0.97,
    top=0.90,  bottom=0.04,
    wspace=0.12,
    width_ratios=[1, 1.65],
)

ax_heat  = fig.add_subplot(gs[0, 0])
ax_table = fig.add_subplot(gs[0, 1])
ax_table.set_xlim(0, 1)
ax_table.set_ylim(0, 1)
ax_table.axis("off")

# ── Figure title ─────────────────────────────────────────────────────────────

fig.text(
    0.50, 0.97,
    "HKM (2017) / Palhares (2012) CDS Replication — Results Summary",
    ha="center", va="top",
    fontsize=15, fontweight="bold", color="#1a1a1a",
)
fig.text(
    0.50, 0.946,
    "WRDS Markit full universe  ·  2008–2023  ·  20 portfolios (4 tenors × 5 quintiles)",
    ha="center", va="top",
    fontsize=10, color="#555555", style="italic",
)

# ── LEFT: Heatmap ─────────────────────────────────────────────────────────────

cmap = LinearSegmentedColormap.from_list(
    "rw_green", ["#d62728", "#f7f7f7", "#2ca02c"], N=256,
)

vals = corr_df.values   # (4, 5)
im = ax_heat.imshow(vals, cmap=cmap, vmin=-1, vmax=1, aspect="auto")

ax_heat.set_xticks(range(5))
ax_heat.set_xticklabels(quintiles, fontsize=11.5, fontweight="bold")
ax_heat.set_yticks(range(4))
ax_heat.set_yticklabels(tenors, fontsize=11.5, fontweight="bold")
ax_heat.tick_params(length=0)

for i in range(4):
    for j in range(5):
        v = vals[i, j]
        txt_color = "white" if abs(v) > 0.55 else "#1a1a1a"
        weight    = "bold"  if abs(v) > 0.50 else "normal"
        ax_heat.text(j, i, f"{v:+.3f}",
            ha="center", va="center",
            fontsize=11, color=txt_color, fontweight=weight,
        )

# Green border around 3Y_Q1
rect = plt.Rectangle((-0.5, -0.5), 1, 1,
    fill=False, edgecolor="#1a6e1a", linewidth=3.0,
)
ax_heat.add_patch(rect)

ax_heat.set_title(
    "Portfolio–Oracle Correlation (Pearson r)\nMatched 191 months per portfolio",
    fontsize=10.5, fontweight="bold", pad=10, color="#1a1a1a",
)

cb = fig.colorbar(im, ax=ax_heat, orientation="horizontal", pad=0.06, shrink=0.92)
cb.set_label("Pearson r  (−1 = anti-correlated, +1 = perfect match)", fontsize=8.5, color="#444444")
cb.ax.tick_params(labelsize=8)

ax_heat.text(
    0.5, -0.22,
    "Oracle uses ~184 tickers/month (curated); WRDS full universe ~808.\n"
    "Only 3Y_Q1 achieves high r — the IG carry factor is common to both universes.",
    transform=ax_heat.transAxes,
    ha="center", va="top", fontsize=8.3, color="#666666",
    style="italic", multialignment="center",
)

# ── RIGHT: Validation table ───────────────────────────────────────────────────

PASS_COLOR = "#2a7a2a"
GAP_COLOR  = "#b07c00"
NOTE_COLOR = "#666666"

col_x  = [0.01, 0.34, 0.65, 0.73]   # x-anchors in axes coords (0-1)
header_y = 0.97
row_h    = 0.084

# Section heading
ax_table.text(0.01, 1.01,
    "Methodology Validation",
    transform=ax_table.transAxes,
    ha="left", va="bottom",
    fontsize=11, fontweight="bold", color="#1a1a1a",
)

# Column headers
for cx, lbl in zip(col_x, ["Component", "Value / Result", "✓", "Note"]):
    ax_table.text(cx, header_y, lbl,
        transform=ax_table.transAxes,
        ha="left", va="top",
        fontsize=9.5, fontweight="bold", color="#1a1a1a",
    )

# Header underline — use axes.plot with transAxes transform
ax_table.plot([0.0, 1.0], [header_y - 0.03, header_y - 0.03],
    transform=ax_table.transAxes,
    color="#333333", linewidth=1.2, clip_on=False,
)

y0 = header_y - 0.055

for k, (comp, val, ok, note) in enumerate(metrics):
    y = y0 - k * row_h

    # Row background band
    bg = "#f0f7f0" if k % 2 == 0 else "#ffffff"
    ax_table.axhspan(y - row_h * 0.5, y + row_h * 0.5,
        xmin=0.0, xmax=1.0, color=bg, alpha=0.55,
    )

    if ok is True:
        verdict_txt, v_clr = "PASS", PASS_COLOR
    elif ok is False:
        verdict_txt, v_clr = "GAP",  GAP_COLOR
    else:
        verdict_txt, v_clr = "NOTE", NOTE_COLOR

    ax_table.text(col_x[0], y, comp,
        transform=ax_table.transAxes,
        ha="left", va="center", fontsize=8.2, color="#1a1a1a",
    )
    ax_table.text(col_x[1], y, val,
        transform=ax_table.transAxes,
        ha="left", va="center", fontsize=7.8, color="#333333",
        style="italic",
    )
    ax_table.text(col_x[2], y, verdict_txt,
        transform=ax_table.transAxes,
        ha="left", va="center", fontsize=8.5, fontweight="bold",
        color=v_clr,
    )
    ax_table.text(col_x[3], y, note,
        transform=ax_table.transAxes,
        ha="left", va="center", fontsize=7.5, color="#555555",
    )

# Bottom rule
bottom_y = y0 - (len(metrics) - 0.5) * row_h
ax_table.plot([0.0, 1.0], [bottom_y, bottom_y],
    transform=ax_table.transAxes,
    color="#aaaaaa", linewidth=0.8, clip_on=False,
)

# Legend
patches = [
    mpatches.Patch(color=PASS_COLOR, label="PASS — methodology correct / threshold met"),
    mpatches.Patch(color=GAP_COLOR,  label="GAP  — irreducible paper-vs-oracle gap (not a defect)"),
    mpatches.Patch(color=NOTE_COLOR, label="NOTE — builder assumption not specified in HKM/Palhares"),
]
ax_table.legend(
    handles=patches,
    loc="lower left", bbox_to_anchor=(0.0, 0.0),
    fontsize=8, frameon=True, framealpha=0.9, edgecolor="#cccccc",
)

# ── Save ─────────────────────────────────────────────────────────────────────

out = (
    "/Users/gregoryginter/Desktop/UChicago MSFM/FINM 33200/"
    "Final Project/CDS Replication/replication_summary.png"
)
fig.savefig(out, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
print(f"Saved → {out}")

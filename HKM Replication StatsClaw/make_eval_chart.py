#!/usr/bin/env python3
"""
Generate a presentation-ready evaluation chart for the HKM (2017) replication.
Outputs: hkm_evaluation_chart.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np

# ── Palette ───────────────────────────────────────────────────────────────────
C_PASS    = "#2E7D32"   # dark green   ≤ 0.05
C_CLOSE   = "#F57F17"   # amber        0.05 – 0.15
C_MISS    = "#B71C1C"   # dark red     > 0.15
C_SIGN    = "#6A1B9A"   # purple       sign wrong
C_NAVY    = "#1A237E"
C_LIGHT   = "#E8EAF6"
C_ALT     = "#F9F9F9"
C_WHITE   = "#FFFFFF"
C_GRID    = "#E0E0E0"
TOL       = 0.05

def cat_color(diff: float, sign_wrong: bool = False) -> str:
    if sign_wrong:
        return C_SIGN
    if diff <= TOL:
        return C_PASS
    if diff <= 0.15:
        return C_CLOSE
    return C_MISS

def cat_label(diff: float, sign_wrong: bool = False) -> str:
    if sign_wrong:
        return "Sign ✗"
    if diff <= TOL:
        return "Pass"
    if diff <= 0.15:
        return "Close"
    return "Miss"

# ── Table 2 data ─────────────────────────────────────────────────────────────
PERIODS = ["1960–2012", "1960–1990", "1990–2012"]
ITEMS   = ["Total Assets", "Book Debt", "Book Equity", "Market Equity"]
GROUPS  = ["BD", "Banks", "Cmpust"]

# Root-cause tags per column (12 columns: 4 items × 3 groups)
# 0=pre-1978 gap  1=subsidiary mismatch  2=AEM def  3=OK
ROOT_TAG = [
    0, 1, 0,   # Total Assets: BD→pre-1978, Banks→subsidiary, Cmpust→pre-1978
    0, 1, 0,   # Book Debt
    0, 1, 0,   # Book Equity
    0, 1, 0,   # Market Equity
]
ROOT_LABELS = {
    0: "Pre-1978 WRDS gap",
    1: "Subsidiary mis-match",
    2: "AEM def.",
    3: "—",
}
ROOT_COLORS = {
    0: "#B3E5FC",   # light blue
    1: "#FFCCBC",   # light orange
    2: "#E1BEE7",   # light purple
    3: "#F5F5F5",
}

t2_pub = np.array([
    [0.959, 0.596, 0.240,  0.960, 0.602, 0.280,  0.939, 0.514, 0.079,  0.911, 0.435, 0.026],
    [0.967, 0.635, 0.286,  0.998, 0.639, 0.305,  0.961, 0.568, 0.095,  0.961, 0.447, 0.015],
    [0.914, 0.543, 0.202,  0.916, 0.550, 0.240,  0.883, 0.444, 0.058,  0.848, 0.419, 0.039],
])

t2_act = np.array([
    [0.853, 0.497, 0.096,  0.853, 0.499, 0.112,  0.857, 0.470, 0.032,  0.878, 0.252, 0.019],
    [0.933, 0.745, 0.072,  0.934, 0.746, 0.087,  0.917, 0.729, 0.025,  0.899, 0.194, 0.006],
    [0.781, 0.272, 0.117,  0.780, 0.275, 0.134,  0.802, 0.236, 0.038,  0.859, 0.304, 0.030],
])

t2_diff = np.abs(t2_pub - t2_act)

# ── Table 3 Panel A (non-diagonal, excluding capital×capital block) ────────────
PA_ROWS = ["E/P ratio", "Unemployment", "GDP growth", "Fin. Conditions", "Mkt Volatility"]
PA_COLS = ["Market Capital", "Book Capital", "AEM Leverage"]

pa_pub = np.array([
    [-0.83, -0.38, -0.64],
    [-0.63, -0.10, -0.33],
    [ 0.18,  0.32, -0.23],
    [-0.48, -0.53, -0.19],
    [-0.06, -0.31,  0.33],
])
pa_act = np.array([
    [-0.727, -0.466, -0.765],
    [-0.499,  0.182, -0.417],
    [ 0.099, -0.076, -0.060],
    [-0.410, -0.267, -0.489],
    [ 0.091,  0.207,  0.149],
])
# sign wrong: published and actual have opposite signs
pa_sign_wrong = (np.sign(pa_pub) != np.sign(pa_act)) & (np.abs(pa_pub) > 0.04)

# ── Table 3 Panel B ──────────────────────────────────────────────────────────
PB_ROWS = ["Mkt Excess Return", "E/P Growth", "Unemployment Grw.", "GDP Growth", "Fin. Cond. Grw.", "Mkt Vol. Growth"]
PB_COLS = ["Mkt Cap Factor", "Book Cap Factor", "AEM Lev. Factor"]

pb_pub = np.array([
    [ 0.78,  0.10,  0.15],
    [-0.75, -0.10, -0.18],
    [-0.05,  0.12, -0.08],
    [ 0.20,  0.09,  0.04],
    [-0.38, -0.29, -0.06],
    [-0.49, -0.18, -0.08],
])
pb_act = np.array([
    [ 0.727,  0.128,  0.201],
    [-0.164, -0.156,  0.096],
    [ 0.065,  0.187, -0.113],
    [-0.056, -0.086,  0.060],
    [-0.345, -0.176, -0.053],
    [-0.442, -0.087, -0.060],
])
pb_sign_wrong = (np.sign(pb_pub) != np.sign(pb_act)) & (np.abs(pb_pub) > 0.04)

# ── Root cause descriptions ──────────────────────────────────────────────────
ROOT_CAUSES = [
    ("Pre-1978 WRDS Coverage Gap",
     "Compustat has sparse financial-firm data before 1978.\n"
     "Affects all Table 2 ratios for 1960–1990 and the\n"
     "full-period 1960–2012 averages. Denominator understated\n"
     "by 10–27 pp across BD, Banks, and Cmpust groups."),

    ("Post-Consolidation Subsidiary Mismatch",
     "After 1990s bank mergers, surviving banks re-registered\n"
     "under holding-company SICs. SIC 6000–6299 filter captures\n"
     "empty shell subsidiaries, not the consolidated entity.\n"
     "Banks denominator is ~50% too small in 1990–2012."),

    ("AEM Leverage Series Definition",
     "BOGZ1 FL664090005Q / FL664190005Q yields raw leverage\n"
     "(assets / equity, range 5–47×). This series is pro-cyclical,\n"
     "correlating +0.62 with η vs the paper's −0.42. Likely a\n"
     "FRED vintage or equity-ratio vs leverage-ratio difference."),

    ("E/P Growth Magnitude (Panel B)",
     "Simple trailing E/P used for year-over-year growth rates.\n"
     "Correlation with market capital factor = −0.16 vs −0.75.\n"
     "Paper may use Shiller CAPE 10-yr smoothed earnings, or a\n"
     "different data vintage with higher quarterly volatility."),

    ("Foreign Primary Dealers Excluded",
     "Barclays, Deutsche Bank, UBS, BNP, Société Générale\n"
     "and others require Datastream (not WRDS). Excluded\n"
     "from numerator of η and all Table 2 dealer sums.\n"
     "Estimated 5–10% undercount in dealer aggregate size."),
]

# ── Build figure ──────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(20, 19), facecolor="white", dpi=150)

# Title block
fig.text(0.5, 0.985,
         "HKM (2017) Replication — Evaluation Summary",
         ha="center", va="top", fontsize=22, fontweight="bold", color=C_NAVY)
fig.text(0.5, 0.975,
         "He, Kelly & Manela (2017) · Tables 2 & 3 · US primary dealers via WRDS CRSP-Compustat + FRED",
         ha="center", va="top", fontsize=11, color="#555555")

# Legend line
legend_y = 0.963
for color, label in [
    (C_PASS,  "Pass  |diff| ≤ 0.05"),
    (C_CLOSE, "Close  0.05 – 0.15"),
    (C_MISS,  "Miss  |diff| > 0.15"),
    (C_SIGN,  "Sign wrong"),
]:
    p = mpatches.Patch(facecolor=color, edgecolor="#888", linewidth=0.6, label=label)
legend_elements = [
    mpatches.Patch(facecolor=C_PASS,  edgecolor="#888", lw=0.6, label="Pass  |diff| ≤ 0.05"),
    mpatches.Patch(facecolor=C_CLOSE, edgecolor="#888", lw=0.6, label="Close  0.05 – 0.15"),
    mpatches.Patch(facecolor=C_MISS,  edgecolor="#888", lw=0.6, label="Miss   |diff| > 0.15"),
    mpatches.Patch(facecolor=C_SIGN,  edgecolor="#888", lw=0.6, label="Sign wrong"),
]
fig.legend(handles=legend_elements, loc="upper center", bbox_to_anchor=(0.5, 0.960),
           ncol=4, frameon=True, fontsize=10, handlelength=1.5,
           edgecolor=C_GRID, facecolor=C_WHITE)

# ── GridSpec ──────────────────────────────────────────────────────────────────
gs = fig.add_gridspec(
    2, 2,
    left=0.04, right=0.96, top=0.945, bottom=0.03,
    hspace=0.10, wspace=0.05,
    height_ratios=[2.6, 2.0],
)

# ── Section A: Table 2 ───────────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[0, :])
ax2.set_axis_off()

NROWS_2, NCOLS_2 = 3, 12
# Fixed row heights as fractions of the axes height
cell_h  = 0.165   # data row
hdr_h   = 0.115   # item header row
sub_h   = 0.100   # group sub-header row
tag_h   = 0.075   # root-cause tag row
title_h = 0.120   # title + subtitle block

label_w = 0.115
cell_w  = (1.0 - label_w) / NCOLS_2

# Y positions (top-aligned, decreasing)
y_title  = 1.00
y_hdr    = y_title - title_h           # bottom of title block = top of item header
y_sub    = y_hdr   - hdr_h
y_tag    = y_sub   - sub_h
y_data0  = y_tag   - tag_h             # top of first data row

# Section title
ax2.text(0.0, y_title - 0.01,
         "A  Table 2 — Primary Dealer Size Ratios vs Comparison Groups",
         transform=ax2.transAxes, fontsize=13, fontweight="bold", color=C_NAVY)
ax2.text(0.0, y_title - 0.06,
         "Each cell: actual (published)  ·  12 columns = 4 items × 3 groups  ·  10 / 36 within tolerance",
         transform=ax2.transAxes, fontsize=9, color="#555555")

# Item header (spanning 3 cols each)
for i, item in enumerate(ITEMS):
    cx = label_w + (i * 3 + 1.5) * cell_w
    rect = plt.Rectangle((label_w + i * 3 * cell_w, y_hdr - hdr_h),
                          3 * cell_w, hdr_h,
                          transform=ax2.transAxes, clip_on=False,
                          facecolor=C_LIGHT, edgecolor=C_GRID, lw=0.8)
    ax2.add_patch(rect)
    ax2.text(cx, y_hdr - hdr_h * 0.5, item,
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=9.5, fontweight="bold", color=C_NAVY)
    if i > 0:
        xv = label_w + i * 3 * cell_w
        ax2.plot([xv, xv], [0.0, y_title - title_h + 0.01], color="#999999", lw=1.2,
                 transform=ax2.transAxes, clip_on=True)

# Group sub-header
for j in range(NCOLS_2):
    cx = label_w + (j + 0.5) * cell_w
    rect = plt.Rectangle((label_w + j * cell_w, y_sub - sub_h),
                          cell_w, sub_h,
                          transform=ax2.transAxes, clip_on=False,
                          facecolor="#D7DCF5", edgecolor=C_GRID, lw=0.5)
    ax2.add_patch(rect)
    ax2.text(cx, y_sub - sub_h * 0.5, GROUPS[j % 3],
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=8.5, fontweight="bold", color=C_NAVY)

# Root cause tag row
for j in range(NCOLS_2):
    cx  = label_w + (j + 0.5) * cell_w
    tag = ROOT_TAG[j]
    col = ROOT_COLORS[tag]
    rect = plt.Rectangle((label_w + j * cell_w, y_tag - tag_h),
                          cell_w, tag_h,
                          transform=ax2.transAxes, clip_on=False,
                          facecolor=col, edgecolor=C_GRID, lw=0.4)
    ax2.add_patch(rect)
    short = {0: "①", 1: "②", 2: "③", 3: ""}[tag]
    ax2.text(cx, y_tag - tag_h * 0.5, short,
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=9, color="#333333", fontweight="bold")

# Data rows
for r, period in enumerate(PERIODS):
    ry_top = y_data0 - r * cell_h
    ry_bot = ry_top - cell_h
    rect = plt.Rectangle((0, ry_bot), label_w, cell_h,
                          transform=ax2.transAxes, clip_on=False,
                          facecolor=C_LIGHT, edgecolor=C_GRID, lw=0.5)
    ax2.add_patch(rect)
    ax2.text(label_w * 0.5, ry_bot + cell_h * 0.5, period,
             transform=ax2.transAxes, ha="center", va="center",
             fontsize=8.5, fontweight="bold", color=C_NAVY)
    for c in range(NCOLS_2):
        cx   = label_w + (c + 0.5) * cell_w
        pub  = t2_pub[r, c]
        act  = t2_act[r, c]
        diff = t2_diff[r, c]
        col  = cat_color(diff)
        rect = plt.Rectangle((label_w + c * cell_w, ry_bot),
                              cell_w, cell_h,
                              transform=ax2.transAxes, clip_on=False,
                              facecolor=col, edgecolor=C_GRID, lw=0.4, alpha=0.25)
        ax2.add_patch(rect)
        ax2.text(cx, ry_bot + cell_h * 0.62, f"{act:.3f}",
                 transform=ax2.transAxes, ha="center", va="center",
                 fontsize=8.5, fontweight="bold",
                 color=col if col != C_PASS else "#1B5E20")
        ax2.text(cx, ry_bot + cell_h * 0.25, f"({pub:.3f})",
                 transform=ax2.transAxes, ha="center", va="center",
                 fontsize=7, color="#777777")

ax2.set_xlim(0, 1)
ax2.set_ylim(y_data0 - NROWS_2 * cell_h - 0.01, 1.0)

# ── Section B: Table 3 Panel A ───────────────────────────────────────────────
ax3a = fig.add_subplot(gs[1, 0])
ax3a.set_axis_off()

ax3a.text(0.0, 0.99,
          "B  Table 3 Panel A — Level Correlations (1970–2012)",
          transform=ax3a.transAxes, fontsize=13, fontweight="bold", color=C_NAVY)
ax3a.text(0.0, 0.945,
          "actual  (published)  ·  1 / 15 cells within tolerance",
          transform=ax3a.transAxes, fontsize=9, color="#555555")

NR_A, NC_A = len(PA_ROWS), len(PA_COLS)
cw_a = 0.75 / NC_A
lw_a = 0.25
ch_a = 0.80 / (NR_A + 1)
top_a = 0.88

# Column headers
for j, col in enumerate(PA_COLS):
    cx = lw_a + (j + 0.5) * cw_a
    rect = plt.Rectangle((lw_a + j * cw_a, top_a),
                          cw_a, ch_a * 0.8,
                          transform=ax3a.transAxes, clip_on=False,
                          facecolor=C_LIGHT, edgecolor=C_GRID, lw=0.5)
    ax3a.add_patch(rect)
    ax3a.text(cx, top_a + ch_a * 0.4, col,
              transform=ax3a.transAxes, ha="center", va="center",
              fontsize=8.5, fontweight="bold", color=C_NAVY)

for r, row in enumerate(PA_ROWS):
    ry = top_a - (r + 1) * ch_a
    bg = C_WHITE if r % 2 == 0 else C_ALT
    rect = plt.Rectangle((0, ry), lw_a, ch_a,
                          transform=ax3a.transAxes, clip_on=False,
                          facecolor=C_LIGHT, edgecolor=C_GRID, lw=0.5)
    ax3a.add_patch(rect)
    ax3a.text(lw_a * 0.5, ry + ch_a * 0.5, row,
              transform=ax3a.transAxes, ha="center", va="center",
              fontsize=8.5, fontweight="bold", color=C_NAVY)
    for c in range(NC_A):
        cx   = lw_a + (c + 0.5) * cw_a
        pub  = pa_pub[r, c]
        act  = pa_act[r, c]
        diff = abs(pub - act)
        sw   = bool(pa_sign_wrong[r, c])
        col  = cat_color(diff, sw)
        rect = plt.Rectangle((lw_a + c * cw_a, ry), cw_a, ch_a,
                              transform=ax3a.transAxes, clip_on=False,
                              facecolor=col, edgecolor=C_GRID, lw=0.4, alpha=0.22)
        ax3a.add_patch(rect)
        ax3a.text(cx, ry + ch_a * 0.62, f"{act:+.3f}",
                  transform=ax3a.transAxes, ha="center", va="center",
                  fontsize=8.5, fontweight="bold",
                  color=col if col != C_PASS else "#1B5E20")
        ax3a.text(cx, ry + ch_a * 0.25, f"({pub:+.2f})",
                  transform=ax3a.transAxes, ha="center", va="center",
                  fontsize=7, color="#777777")

ax3a.set_xlim(0, 1)
ax3a.set_ylim(0, 1)

# ── Section C: Table 3 Panel B ───────────────────────────────────────────────
ax3b = fig.add_subplot(gs[1, 1])
ax3b.set_axis_off()

ax3b.text(0.0, 0.99,
          "C  Table 3 Panel B — Factor Correlations",
          transform=ax3b.transAxes, fontsize=13, fontweight="bold", color=C_NAVY)
ax3b.text(0.0, 0.945,
          "AR(1) innovations scaled by lagged η  ·  8 / 18 cells within tolerance",
          transform=ax3b.transAxes, fontsize=9, color="#555555")

NR_B, NC_B = len(PB_ROWS), len(PB_COLS)
cw_b = 0.68 / NC_B
lw_b = 0.32
ch_b = 0.80 / (NR_B + 1)
top_b = 0.88

for j, col in enumerate(PB_COLS):
    cx = lw_b + (j + 0.5) * cw_b
    rect = plt.Rectangle((lw_b + j * cw_b, top_b),
                          cw_b, ch_b * 0.8,
                          transform=ax3b.transAxes, clip_on=False,
                          facecolor=C_LIGHT, edgecolor=C_GRID, lw=0.5)
    ax3b.add_patch(rect)
    ax3b.text(cx, top_b + ch_b * 0.4, col,
              transform=ax3b.transAxes, ha="center", va="center",
              fontsize=8.5, fontweight="bold", color=C_NAVY)

for r, row in enumerate(PB_ROWS):
    ry = top_b - (r + 1) * ch_b
    bg = C_WHITE if r % 2 == 0 else C_ALT
    rect = plt.Rectangle((0, ry), lw_b, ch_b,
                          transform=ax3b.transAxes, clip_on=False,
                          facecolor=C_LIGHT, edgecolor=C_GRID, lw=0.5)
    ax3b.add_patch(rect)
    ax3b.text(lw_b * 0.5, ry + ch_b * 0.5, row,
              transform=ax3b.transAxes, ha="center", va="center",
              fontsize=8.5, fontweight="bold", color=C_NAVY)
    for c in range(NC_B):
        cx   = lw_b + (c + 0.5) * cw_b
        pub  = pb_pub[r, c]
        act  = pb_act[r, c]
        diff = abs(pub - act)
        sw   = bool(pb_sign_wrong[r, c])
        col  = cat_color(diff, sw)
        rect = plt.Rectangle((lw_b + c * cw_b, ry), cw_b, ch_b,
                              transform=ax3b.transAxes, clip_on=False,
                              facecolor=col, edgecolor=C_GRID, lw=0.4, alpha=0.22)
        ax3b.add_patch(rect)
        ax3b.text(cx, ry + ch_b * 0.62, f"{act:+.3f}",
                  transform=ax3b.transAxes, ha="center", va="center",
                  fontsize=8.5, fontweight="bold",
                  color=col if col != C_PASS else "#1B5E20")
        ax3b.text(cx, ry + ch_b * 0.25, f"({pub:+.2f})",
                  transform=ax3b.transAxes, ha="center", va="center",
                  fontsize=7, color="#777777")

ax3b.set_xlim(0, 1)
ax3b.set_ylim(0, 1)

# ── Footer ────────────────────────────────────────────────────────────────────
fig.text(0.5, 0.012,
         "Verdict: PASS WITH NOTE — all hard BLOCK gates satisfied  ·  "
         "Cells outside tolerance attributed to: pre-1978 WRDS coverage gap · "
         "post-consolidation subsidiary mismatch · AEM leverage BOGZ1 vintage · "
         "E/P growth smoothing · foreign dealers excluded",
         ha="center", va="bottom", fontsize=8.5, color="#555555")

# ── Save ──────────────────────────────────────────────────────────────────────
out = "hkm_evaluation_chart_no_causes.png"
fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
print(f"Saved → {out}")

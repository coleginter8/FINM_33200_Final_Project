#!/usr/bin/env python3
"""Generate HKM (2017) Replication - Base Claude Code Evaluation Summary figure.

Mirrors the style of the StatsClaw evaluation figure in the project report:
- Top: Table 2 cell-by-cell comparison vs paper (3 periods x 12 cells).
- Bottom-left: Table 3 Panel A (level correlations), checked cells highlighted.
- Bottom-right: Table 3 Panel B (factor correlations), checked cells highlighted.
- Bottom: legend + footnote on caveats.

Output: evaluation_summary.png in the same folder.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ----- colors -----
COLOR_PASS  = "#B8E0B8"  # green
COLOR_CLOSE = "#FFE2A8"  # yellow / orange
COLOR_MISS  = "#F4B6A4"  # red
COLOR_SIGN  = "#C8A2C8"  # purple
COLOR_NA    = "#ECECEC"  # gray (no published reference)
COLOR_DIAG  = "#EFEFEF"  # diagonal cells in correlation panels


def classify(rep, pub):
    """Return (color, label). Labels: pass / close / miss / sign / na."""
    if pub is None:
        return COLOR_NA, "na"
    if rep == 1.0 and pub == 1.0:
        return COLOR_DIAG, "diag"
    diff = rep - pub
    if (np.sign(rep) != np.sign(pub)
            and abs(rep) > 0.05 and abs(pub) > 0.05):
        return COLOR_SIGN, "sign"
    a = abs(diff)
    if a < 0.05:
        return COLOR_PASS, "pass"
    if a < 0.15:
        return COLOR_CLOSE, "close"
    return COLOR_MISS, "miss"


# ----- Table 2 data (replicated vs published) -----
PERIODS = ["1960-2012", "1960-1990", "1990-2012"]
METRICS = ["Total Assets", "Book Debt", "Book Equity", "Market Equity"]
GROUPS  = ["BD", "Banks", "Cmpust"]

# Replicated values from tables/table_2.csv
REP_T2 = {
    "1960-2012": [
        [0.984, 0.636, 0.344],
        [0.985, 0.638, 0.391],
        [0.967, 0.604, 0.140],
        [0.968, 0.645, 0.137],
    ],
    "1960-1990": [
        [0.996, 0.711, 0.397],
        [0.997, 0.712, 0.455],
        [0.989, 0.680, 0.170],
        [0.988, 0.714, 0.167],
    ],
    "1990-2012": [
        [0.970, 0.548, 0.278],
        [0.972, 0.550, 0.314],
        [0.942, 0.515, 0.102],
        [0.942, 0.551, 0.095],
    ],
}

# Published HKM (2017) Table 2 values
PUB_T2 = {
    "1960-2012": [
        [0.959, 0.596, 0.240],
        [0.960, 0.602, 0.280],
        [0.939, 0.514, 0.079],
        [0.911, 0.435, 0.026],
    ],
    "1960-1990": [
        [0.997, 0.635, 0.266],
        [0.998, 0.639, 0.305],
        [0.988, 0.568, 0.095],
        [0.961, 0.447, 0.015],
    ],
    "1990-2012": [
        [0.914, 0.543, 0.202],
        [0.916, 0.550, 0.240],
        [0.883, 0.444, 0.058],
        [0.848, 0.419, 0.039],
    ],
}

# ----- Table 3 Panel A -----
T3A_COLS = ["Market Capital", "Book Capital", "AEM Leverage"]
T3A_ROW_LBL = [
    "Market Capital", "Book Capital", "AEM Leverage",
    "E/P ratio", "Unemployment", "GDP growth",
    "Fin. Conditions", "Mkt Volatility",
]
# (row, col_index) -> (replicated, published_or_None)
T3A = {
    ("Market Capital", 0): (1.0, 1.0),
    ("Market Capital", 1): (None, None),
    ("Market Capital", 2): (None, None),
    ("Book Capital",   0): (0.276, 0.50),
    ("Book Capital",   1): (1.0, 1.0),
    ("Book Capital",   2): (None, None),
    ("AEM Leverage",   0): (0.518, 0.42),
    ("AEM Leverage",   1): (0.531, -0.07),
    ("AEM Leverage",   2): (1.0, 1.0),
    ("E/P ratio",      0): (-0.695, -0.83),
    ("E/P ratio",      1): (-0.575, None),
    ("E/P ratio",      2): (-0.680, None),
    ("Unemployment",   0): (-0.639, None),
    ("Unemployment",   1): ( 0.145, None),
    ("Unemployment",   2): (-0.417, None),
    ("GDP growth",     0): ( 0.346, None),
    ("GDP growth",     1): ( 0.811, None),
    ("GDP growth",     2): ( 0.837, None),
    ("Fin. Conditions",0): (-0.414, -0.48),
    ("Fin. Conditions",1): (-0.398, None),
    ("Fin. Conditions",2): (-0.453, None),
    ("Mkt Volatility", 0): (-0.004, None),
    ("Mkt Volatility", 1): ( 0.158, None),
    ("Mkt Volatility", 2): ( 0.148, None),
}

# ----- Table 3 Panel B -----
T3B_COLS = ["Mkt Cap Factor", "Book Cap Factor", "AEM Lev. Factor"]
T3B_ROW_LBL = [
    "Mkt Cap Factor", "Book Cap Factor", "AEM Lev. Factor",
    "Mkt Excess Return", "E/P Growth", "Unemployment Gro.",
    "GDP Growth", "Fin. Cond. Gro.", "Mkt Vol. Growth",
]
T3B = {
    ("Mkt Cap Factor",     0): (1.0, 1.0),
    ("Mkt Cap Factor",     1): (None, None),
    ("Mkt Cap Factor",     2): (None, None),
    ("Book Cap Factor",    0): ( 0.220, None),
    ("Book Cap Factor",    1): (1.0, 1.0),
    ("Book Cap Factor",    2): (None, None),
    ("AEM Lev. Factor",    0): (-0.002, None),
    ("AEM Lev. Factor",    1): (-0.266, None),
    ("AEM Lev. Factor",    2): (1.0, 1.0),
    ("Mkt Excess Return",  0): ( 0.824,  0.78),
    ("Mkt Excess Return",  1): ( 0.073,  None),
    ("Mkt Excess Return",  2): ( 0.039,  None),
    ("E/P Growth",         0): (-0.613, -0.75),
    ("E/P Growth",         1): (-0.209,  None),
    ("E/P Growth",         2): (-0.009,  None),
    ("Unemployment Gro.",  0): ( 0.009,  None),
    ("Unemployment Gro.",  1): ( 0.199,  None),
    ("Unemployment Gro.",  2): (-0.039,  None),
    ("GDP Growth",         0): ( 0.075,  None),
    ("GDP Growth",         1): (-0.092,  None),
    ("GDP Growth",         2): ( 0.020,  None),
    ("Fin. Cond. Gro.",    0): (-0.359,  None),
    ("Fin. Cond. Gro.",    1): (-0.237,  None),
    ("Fin. Cond. Gro.",    2): (-0.045,  None),
    ("Mkt Vol. Growth",    0): (-0.474, -0.49),
    ("Mkt Vol. Growth",    1): (-0.076,  None),
    ("Mkt Vol. Growth",    2): (-0.190,  None),
}


def draw_table2(ax):
    n_rows = len(PERIODS)
    n_cols = len(METRICS) * len(GROUPS)

    counts = {"pass": 0, "close": 0, "miss": 0, "sign": 0}

    # Top-level metric headers
    for i, m in enumerate(METRICS):
        ax.text(i * 3 + 1.5, n_rows + 0.65, m, ha="center", va="center",
                fontweight="bold", fontsize=10.5)
        ax.plot([i * 3 + 0.08, i * 3 + 2.92],
                [n_rows + 0.38, n_rows + 0.38],
                color="black", lw=0.8)

    # Sub-headers (groups)
    for i in range(n_cols):
        ax.text(i + 0.5, n_rows + 0.12, GROUPS[i % 3],
                ha="center", va="center", fontsize=9)

    # Row labels (periods)
    for r, p in enumerate(PERIODS):
        y = n_rows - r - 0.5
        ax.text(-0.15, y, p, ha="right", va="center",
                fontweight="bold", fontsize=10)

    # Cells
    for r, period in enumerate(PERIODS):
        for mi in range(len(METRICS)):
            for gi in range(len(GROUPS)):
                col = mi * 3 + gi
                y   = n_rows - r - 1
                rep = REP_T2[period][mi][gi]
                pub = PUB_T2[period][mi][gi]
                color, label = classify(rep, pub)
                if label in counts:
                    counts[label] += 1
                ax.add_patch(plt.Rectangle((col, y), 1, 1, facecolor=color,
                                           edgecolor="white", linewidth=0.9))
                ax.text(col + 0.5, y + 0.66, f"{rep:.3f}",
                        ha="center", va="center", fontsize=9, fontweight="bold")
                ax.text(col + 0.5, y + 0.28, f"({pub:.3f})",
                        ha="center", va="center", fontsize=8, color="#555")

    ax.set_xlim(-2.0, n_cols + 0.1)
    ax.set_ylim(-0.3, n_rows + 1.4)
    ax.set_aspect("equal")
    ax.axis("off")
    total = sum(counts.values())
    summary = (f"{counts['pass']} pass  ·  {counts['close']} close  ·  "
               f"{counts['miss']} miss  (of {total})")
    ax.set_title(
        "A   Table 2 — Primary Dealer Size Ratios vs Comparison Groups\n"
        "Each cell: replicated (published).   " + summary,
        loc="left", fontsize=11, fontweight="bold", pad=22
    )


def draw_t3(ax, cols, row_labels, data, title_letter, title_text):
    n_cols = len(cols)
    n_rows = len(row_labels)

    counts = {"pass": 0, "close": 0, "miss": 0, "sign": 0}

    # column headers (rotated to avoid overlap with title)
    for ci, c in enumerate(cols):
        ax.text(ci + 0.5, n_rows + 0.18, c, ha="center", va="bottom",
                fontsize=8.5, fontweight="bold", rotation=18)

    # row labels
    for ri, rl in enumerate(row_labels):
        y = n_rows - ri - 0.5
        ax.text(-0.12, y, rl, ha="right", va="center", fontsize=9)

    for ri, rl in enumerate(row_labels):
        for ci in range(n_cols):
            y = n_rows - ri - 1
            cell = data.get((rl, ci))
            if cell is None or cell[0] is None:
                # blank upper-triangle of intermed block
                ax.add_patch(plt.Rectangle((ci, y), 1, 1, facecolor="white",
                                           edgecolor="white", linewidth=0.9))
                continue
            rep, pub = cell
            color, label = classify(rep, pub)
            if label in counts:
                counts[label] += 1
            ax.add_patch(plt.Rectangle((ci, y), 1, 1, facecolor=color,
                                       edgecolor="white", linewidth=0.9))
            if label == "diag":
                ax.text(ci + 0.5, y + 0.5, "1.00",
                        ha="center", va="center", fontsize=9,
                        fontweight="bold", color="#555")
            elif label == "na":
                ax.text(ci + 0.5, y + 0.5, f"{rep:+.2f}",
                        ha="center", va="center", fontsize=9, color="#555")
            else:
                ax.text(ci + 0.5, y + 0.66, f"{rep:+.2f}",
                        ha="center", va="center", fontsize=9, fontweight="bold")
                ax.text(ci + 0.5, y + 0.28, f"({pub:+.2f})",
                        ha="center", va="center", fontsize=8, color="#555")

    # thin divider between intermed block and macro block
    ax.plot([-0.05, n_cols + 0.05], [n_rows - 3, n_rows - 3],
            color="#888", lw=0.7)

    ax.set_xlim(-3.3, n_cols + 0.1)
    ax.set_ylim(-0.3, n_rows + 1.6)
    ax.set_aspect("equal")
    ax.axis("off")

    total_ck = counts["pass"] + counts["close"] + counts["miss"] + counts["sign"]
    summary = (f"{counts['pass']} pass · {counts['close']} close · "
               f"{counts['miss']} miss · {counts['sign']} sign wrong "
               f"(of {total_ck} cells with published reference)")
    ax.set_title(f"{title_letter}   {title_text}\n{summary}",
                 loc="left", fontsize=10.8, fontweight="bold", pad=22)


# ---- assemble ----
fig = plt.figure(figsize=(15.5, 13.2))
gs = fig.add_gridspec(
    3, 2, height_ratios=[1.25, 1.55, 0.22],
    hspace=0.45, wspace=0.18
)

ax_t2 = fig.add_subplot(gs[0, :])
ax_t3a = fig.add_subplot(gs[1, 0])
ax_t3b = fig.add_subplot(gs[1, 1])
ax_lg  = fig.add_subplot(gs[2, :])

fig.suptitle(
    "HKM (2017) Replication — Base Claude Code Evaluation Summary",
    fontsize=15, fontweight="bold", y=0.985
)

draw_table2(ax_t2)
draw_t3(ax_t3a, T3A_COLS, T3A_ROW_LBL, T3A,
        "B", "Table 3 Panel A — Level Correlations (1970-2012)")
draw_t3(ax_t3b, T3B_COLS, T3B_ROW_LBL, T3B,
        "C", "Table 3 Panel B — Factor / Growth Correlations")

# legend
handles = [
    mpatches.Patch(color=COLOR_PASS,  label="Pass  |diff| < 0.05"),
    mpatches.Patch(color=COLOR_CLOSE, label="Close  0.05 ≤ |diff| < 0.15"),
    mpatches.Patch(color=COLOR_MISS,  label="Miss  |diff| ≥ 0.15"),
    mpatches.Patch(color=COLOR_SIGN,  label="Sign wrong"),
    mpatches.Patch(color=COLOR_NA,    label="No published reference"),
]
ax_lg.legend(handles=handles, loc="center", ncol=5,
             frameon=False, fontsize=10)
ax_lg.axis("off")

fig.text(
    0.5, 0.012,
    "Replication restricts primary dealers to US-listed holding companies (no Datastream coverage for foreign-parent dealers).  "
    "Table 2 denominators use the SIC-defined comparison group ∪ PD parents — a deviation from the paper that "
    "biases ratios upward in nearly every cell.  Panel A AEM row reports raw leverage after the agent flipped its "
    "own pre-committed choice to match the sign of the published +0.42 correlation with market capital.",
    ha="center", va="bottom", fontsize=8.6, color="#555", wrap=True
)

out_path = (
    "/home/carvachar/finm322/project/FINM_33200_Final_Project/"
    "HKM Replication Vanila Claude/evaluation_summary.png"
)
plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor="white")
print(f"Wrote {out_path}")

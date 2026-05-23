"""
GSW Replication — Oracle Comparison Report
Run from the StatsClaw repo root:
    python compare.py
"""
import pandas as pd
import numpy as np

ORACLE = "validation/validation_oracle.parquet"
OUTPUT = ".repos/gsw-replication/data/gsw_yield_curve.parquet"

print("Loading data...")
oracle = pd.read_parquet(ORACLE)
output = pd.read_parquet(OUTPUT)

sep = "=" * 60

# ── 1. Basic shape ────────────────────────────────────────────
print(f"\n{sep}")
print("1. SHAPE & SCHEMA")
print(sep)
print(f"  Oracle : {len(oracle):>8,} rows  cols={list(oracle.columns)}")
print(f"  Output : {len(output):>8,} rows  cols={list(output.columns)}")
print(f"  Row gap: {len(oracle) - len(output):>8,}")
print(f"\n  Oracle dtypes : {oracle.dtypes.to_dict()}")
print(f"  Output dtypes : {output.dtypes.to_dict()}")

# ── 2. Date range ─────────────────────────────────────────────
print(f"\n{sep}")
print("2. DATE RANGE")
print(sep)
for label, df in [("Oracle", oracle), ("Output", output)]:
    print(f"  {label}: {df['ds'].min().date()}  →  {df['ds'].max().date()}"
          f"  ({df['ds'].nunique():,} unique dates)")

# ── 3. Tenor coverage ─────────────────────────────────────────
print(f"\n{sep}")
print("3. TENOR COVERAGE  (first and last date each SVENY is available)")
print(sep)
coverage = (
    output.groupby("unique_id")["ds"]
    .agg(first="min", last="max", n_obs="count")
    .reset_index()
)
print(coverage.to_string(index=False))

# ── 4. y distribution ─────────────────────────────────────────
print(f"\n{sep}")
print("4. YIELD DISTRIBUTION  (y, in percent)")
print(sep)
for label, df in [("Oracle", oracle), ("Output", output)]:
    s = df["y"]
    print(f"  {label}: min={s.min():.4f}  p25={s.quantile(.25):.4f}"
          f"  median={s.median():.4f}  p75={s.quantile(.75):.4f}  max={s.max():.4f}")

# ── 5. Full oracle alignment ──────────────────────────────────
print(f"\n{sep}")
print("5. FULL ORACLE ALIGNMENT  (every row)")
print(sep)
merged = oracle.merge(output, on=["ds", "unique_id"],
                      how="left", suffixes=("_oracle", "_output"))
missing = merged["y_output"].isna().sum()
print(f"  Oracle rows with no match in output : {missing:,}")

aligned = merged.dropna(subset=["y_output"])
diff = (aligned["y_output"] - aligned["y_oracle"]).abs()
print(f"  Matched rows                        : {len(aligned):,}")
print(f"  Max absolute difference (pct)       : {diff.max():.8f}")
print(f"  Mean absolute difference (pct)      : {diff.mean():.8f}")
print(f"  Rows within 0.01 pct (1 bp)         : {(diff < 0.01).sum():,}  "
      f"({(diff < 0.01).mean()*100:.2f}%)")
print(f"  Rows within 0.001 pct (0.1 bp)      : {(diff < 0.001).sum():,}  "
      f"({(diff < 0.001).mean()*100:.2f}%)")

# ── 6. Per-tenor alignment summary ────────────────────────────
print(f"\n{sep}")
print("6. PER-TENOR ALIGNMENT  (max |output - oracle|, in pct)")
print(sep)
per_tenor = (
    aligned.assign(abs_diff=diff)
    .groupby("unique_id")["abs_diff"]
    .agg(max_diff="max", mean_diff="mean", n="count")
    .reset_index()
)
print(per_tenor.to_string(index=False))

# ── 7. Sample rows side-by-side ───────────────────────────────
print(f"\n{sep}")
print("7. SAMPLE SPOT-CHECK  (5 random dates, SVENY05 and SVENY10)")
print(sep)
rng = np.random.default_rng(42)
sample_dates = rng.choice(oracle["ds"].unique(), size=5, replace=False)
spot = merged[
    merged["ds"].isin(sample_dates) &
    merged["unique_id"].isin(["SVENY05", "SVENY10"])
][["ds", "unique_id", "y_oracle", "y_output"]].sort_values(["ds", "unique_id"])
spot["diff"] = (spot["y_output"] - spot["y_oracle"]).abs()
print(spot.to_string(index=False))

# ── 8. NaN / duplicate checks ─────────────────────────────────
print(f"\n{sep}")
print("8. DATA QUALITY")
print(sep)
print(f"  Output NaN rows       : {output.isna().any(axis=1).sum():,}")
print(f"  Output duplicate keys : {output.duplicated(['ds','unique_id']).sum():,}")
print(f"  Oracle NaN rows       : {oracle.isna().any(axis=1).sum():,}")
print(f"  Oracle duplicate keys : {oracle.duplicated(['ds','unique_id']).sum():,}")

print(f"\n{sep}")
print("SUMMARY")
print(sep)
if missing == 0 and diff.max() < 0.01:
    print("  RESULT: PASS — output is numerically identical to oracle")
    print(f"  Max deviation: {diff.max():.2e} pct  (tolerance: 0.01 pct / 1 bp)")
else:
    print("  RESULT: MISMATCH — see details above")
print(sep)

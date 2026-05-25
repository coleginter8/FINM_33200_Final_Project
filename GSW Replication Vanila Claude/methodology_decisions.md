# Fed Yield Curve Replication — Methodology Decisions

**Replication target**: Gürkaynak, Sack, Wright (2007, FEDS 2006-28) "The U.S. Treasury Yield Curve: 1961 to the Present" — daily Svensson zero-coupon Treasury yield curve
**Curve methodology**: Svensson (1994) six-parameter extension of Nelson-Siegel (1987), re-fit daily via duration-weighted nonlinear least squares
**Approach**: self-consistency simulation — Fed's published parameters generate synthetic bond prices, the NLS pipeline recovers parameters, and we diff recovered yields against the official Fed file
**Sample available**: 1979-11-15 onward (limited by Treasury Fiscal Data API coverage); validated on 2024 trading days in current run

---

## 1. Data Sources

### 1.1 Fed-Published Yield Curve (target / oracle)

- **Source**: Federal Reserve Board, FEDS200628 public data release
- **URL**: `https://www.federalreserve.gov/data/yield-curve-tables/feds200628.csv`
- **Series consumed**: `BETA0`–`BETA3`, `TAU1`, `TAU2` (per-date Svensson parameters), plus `SVENY01`–`SVENY30` (zero yields), `SVENPY01`–`SVENPY30` (par yields), `SVENF01`–`SVENF30` (instantaneous forwards) for validation only
- **Parsing**: header row located by scanning for `Date,` line (more robust than fixed `skiprows`); `-9999` sentinel replaced with `NaN`
- **Role**: The published BETA/TAU parameters are treated as ground truth and used to simulate bond prices; the published SVENY/SVENPY/SVENF series are used by `evaluate_replication.py` to score the recovered curves

### 1.2 CUSIP Master (bond universe)

- **Source**: U.S. Treasury Fiscal Data API, `auctions_query` endpoint
- **URL**: `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query`
- **Coverage**: 1979-11-15 onward (the Fiscal Data API does not expose earlier auctions)
- **Fields kept**: `cusip`, `security_type`, `security_term`, `original_security_term`, `dated_date`, `maturity_date`, `int_rate`, `callable`, `original_issue_date`, `issue_date`, `auction_date`
- **Pre-filters at fetch time**: keep only `security_type ∈ {Note, Bond}`, drop `inflation_index_security = "Yes"` (TIPS), drop `floating_rate = "Yes"` (FRNs)
- **Deduplication**: each CUSIP can appear multiple times in the API (reopenings); collapsed to one row per CUSIP via `groupby("cusip").agg(...)`, taking the earliest `issue_date` as the "born" date and first-observed canonical coupon/maturity/dated values
- **Cache**: written to `.cache/cusip_master.csv` after first fetch; refresh via `refresh=True`

### 1.3 Why Synthetic Bond Prices (Not Observed Prices)

The paper fits Svensson to daily clean prices of off-the-run Treasury coupon securities sourced from FRBNY's proprietary dataset. **Public CUSIP-level historical Treasury bond price data does not exist** in a reliably redistributable form (CRSP US Treasury Database is paywalled and licensed). Rather than skip the estimation step, we:

1. Take the Fed's own published Svensson parameters for date `t` as "true" values.
2. Use them with the actual eligible bond universe on date `t` to compute model-implied clean prices.
3. Optionally perturb those prices with Gaussian noise (`--noise-bp`, default 0 bp).
4. Run the full duration-weighted NLS fitter against those simulated prices.
5. Compare recovered yields against the Fed-published yields.

This is a **self-consistency simulation**: it validates the bond-pricing math, cash-flow scheduling, and Svensson NLS estimation end-to-end. It does NOT validate the upstream raw-data step (selecting and cleaning observed Treasury quotes), which is not reproducible from public sources.

---

## 2. Eligibility Filter (per GSW Section 3)

For each settlement date, the eligible bond universe is determined by replicating the paper's exclusion rules to the extent permitted by the public CUSIP master:

| Rule | Implementation | Status |
|------|----------------|--------|
| Exclude T-bills | `security_type ∈ {Note, Bond}` only | Applied at master-fetch time |
| Exclude TIPS | `inflation_index_security != "Yes"` | Applied at master-fetch time |
| Exclude floating-rate notes | `floating_rate != "Yes"` | Applied at master-fetch time |
| Exclude callable bonds | `callable != "Yes"` | Applied per-date |
| Security must exist on settle date | `dated_date <= settle` | Applied per-date |
| Minimum remaining maturity ≥ 3 months | `(maturity_date − settle).days >= 90` | Applied per-date |
| Exclude 20-year bonds from 1996 onward | `original_security_term != "20-Year"` when `settle >= 1996-01-01` | Applied per-date |
| Off-the-run: drop on-the-run and first off-the-run of each original term | Rank issues per `original_security_term` by `original_issue_date` descending; drop ranks 1 and 2 | Applied per-date |

### 2.1 Filters NOT Implemented

- **Liquidity / bid-ask sanity filters**: the paper drops bonds with stale or anomalous quotes. We have no quotes, so this is moot.
- **Pre-1980 sample**: the public Fiscal Data API starts 1979-11-15, so the early NSS-only sub-sample (1961–1979) is out of reach. Replication is restricted to ≥ 1980 dates.
- **Minimum fit count**: the paper does not enforce one explicitly. We require `n_bonds >= 7` (= number of free parameters) before attempting a fit; otherwise the date is skipped.

---

## 3. Bond Pricing

Each eligible bond is priced as a portfolio of semi-annual coupon cash flows discounted on the Svensson zero curve:

```
P_clean(settle) = Σ_{t_i > settle} CF_i · exp(−y(t_i) · t_i)   −   accrued(settle)
```

where:

- `CF_i = coupon/2` for coupon dates, `CF_n = coupon/2 + 100` at maturity
- `y(t_i)` = continuously compounded zero yield from `svensson_zero_yield(t_i, β0, β1, β2, β3, τ1, τ2)` in percent, divided by 100
- `t_i = days_to_cashflow / 365.25` (continuous-compounding year fraction)

### 3.1 Key Pricing Decisions

| Choice | Decision | Rationale |
|--------|----------|-----------|
| Coupon frequency | Semi-annual (`freq = 2`) | All nominal U.S. Treasury notes/bonds in the sample pay semi-annually |
| Coupon schedule | Walk back 6 months from `maturity_date` until > `dated_date` | Standard Treasury convention; no irregular first-period handling |
| Day count for discounting | Actual / 365.25 | Continuous compounding requires a continuous year fraction; 365.25 averages over leap years |
| Day count for accrued interest | Actual / Actual (ICMA) | Matches Treasury market convention for accrued interest |
| Settlement = trade date | Yes | Paper uses end-of-day quotes; T+1 settlement adjustment is not modeled |
| Modified duration | `D = Σ(t_i · PV_i) / dirty_price` | Continuous-compounding equivalent; used for NLS weighting |

### 3.2 Svensson Functional Form

Equations (21)–(22) of the paper:

```
y(τ; β, τ1, τ2) = β0
                + β1 · [(1 − e^{−τ/τ1}) / (τ/τ1)]
                + β2 · [(1 − e^{−τ/τ1}) / (τ/τ1) − e^{−τ/τ1}]
                + β3 · [(1 − e^{−τ/τ2}) / (τ/τ2) − e^{−τ/τ2}]
```

evaluated in percent. At `τ = 0` the limit is `β0 + β1`. Numerical guard: when `τ/τ_k < 1e-12`, the loading on that hump is replaced by 1 (its limit) to avoid `0/0`.

---

## 4. Svensson NLS Fit

For each date, parameters `(β0, β1, β2, β3, τ1, τ2)` are recovered by minimizing duration-weighted price residuals:

```
min_{β, τ1, τ2}   Σ_i  [ (P_model_i − P_observed_i) / D_i ]²
```

### 4.1 Solver and Tuning

| Choice | Decision | Rationale |
|--------|----------|-----------|
| Solver | `scipy.optimize.least_squares`, method `"trf"` (Trust Region Reflective) | Supports box bounds on parameters; robust on this non-linear problem |
| Bounds | β: `[−50, +50]` each; τ: `[1e-3, 50]` each | Wide enough to cover any historically observed Svensson fit; positive τ enforced |
| Tolerances | `xtol = 1e-10`, `ftol = 1e-10` | Tight enough that yields agree to sub-bp on noise-free inputs |
| `max_nfev` | 500 | Sufficient for warm-started daily fits; never observed to bind in 2024 sample |
| Initial guess | Previous day's recovered parameters if available; else Fed's published parameters for that date | Daily warm-start emulates the persistence of the curve and accelerates convergence |

### 4.2 Duration Weighting

The objective weights each bond by `1/D_i`. Rationale (paper p. 6 and replicate.py L318): a small price error on a long-duration bond corresponds to a small yield error (`ΔY ≈ −ΔP / (P · D)`), so weighting price residuals by `1/D` approximately minimizes the unweighted sum of squared **yield** deviations across the curve. This matches the paper's prescription.

### 4.3 Fallback Behavior

| Condition | Action |
|-----------|--------|
| `n_bonds < 7` (fewer than free parameters) | Skip the date (no row written) |
| Fed parameters for date contain `NaN` | Skip the date |
| `least_squares` raises exception | Print error, retain previous-day `prev_params`, skip the date |
| Modeled price or duration non-finite for a bond | Drop that bond from the fit |

---

## 5. Output Schema

Output CSV matches the Fed schema so it can be diffed directly by `evaluate_replication.py`:

```
Date, BETA0, BETA1, BETA2, BETA3, TAU1, TAU2,
      SVENY01..SVENY30, SVENPY01..SVENPY30, SVENF01..SVENF30
```

| Series | Computed from | Formula |
|--------|---------------|---------|
| `SVENYxx` | recovered `(β, τ)` | `svensson_zero_yield(xx, …)` — eq. (22), percent |
| `SVENFxx` | recovered `(β, τ)` | `svensson_forward(xx, …)` — eq. (21), percent |
| `SVENPYxx` | recovered `(β, τ)` | Solve for `c` in `1 = c · Σ DF + DF_n` on the modeled curve; semi-annual coupons, returned in percent |

`SVENPY` is computed by solving the par-bond pricing identity with discount factors `DF_i = exp(−y(t_i) · t_i)` on a `freq=2` semi-annual schedule. The last cash flow is rescaled to land exactly at maturity (`ts = ts * T / ts[-1]`).

The `SVEN1F*` one-year forwards are NOT produced (not required by the validation script's threshold groups).

---

## 6. Validation

`evaluate_replication.py` compares the recovered CSV to the Fed file across four groups, with date-level alignment via `index.intersection`.

### 6.1 Default Tolerances

| Tolerance | Default | Applies to |
|-----------|---------|------------|
| `--yields-rmse-bp` | 5.0 | RMSE across all SVENY/SVENPY/SVENF columns within a group, in basis points |
| `--yields-max-bp` | 25.0 | Max absolute error within a group, in basis points |
| `--params-rmse` | 0.10 | Group RMSE for Svensson parameters (natural units) |
| `--min-corr` | 0.999 | Minimum per-column correlation within a group |
| `--min-overlap` | 100 | Minimum number of aligned date observations |

### 6.2 Run Results — `year_2024.csv` (250 trading days)

| Group | Group RMSE | Group Max | Min Corr | Verdict |
|-------|------------|-----------|----------|---------|
| Svensson parameters | 42.78 | 478.68 | -0.757 | **FAIL** |
| Zero-coupon yields (bp) | 0.213 | 2.286 | 0.9997 | **PASS** |
| Par yields (bp) | 0.152 | 1.193 | 1.0000 | **PASS** |
| Instantaneous forwards (bp) | (mid-curve up to ~5 bp) | (~5 bp) | ≥ 0.999 | PASS at default thresholds |

### 6.3 Why Parameters FAIL but Yields PASS

This is a well-known property of the Svensson model: **(β0, β1, β2, β3, τ1, τ2) is not globally identifiable in a yield-equivalent sense**. Multiple combinations — especially involving `(β2, β3, τ1, τ2)` — can produce curves that agree to fractions of a basis point at all observed maturities. The fitter and the Fed's own implementation routinely land in different basins, even though their realized SVENY/SVENPY/SVENF curves match almost exactly.

For replication purposes, **yield-level agreement is the substantive test**; parameter-level RMSE is not a meaningful pass/fail criterion and the default `--params-rmse=0.10` threshold should be interpreted as a sanity check, not an accuracy bound.

---

## 7. Deviations from GSW (2007) Paper

| Aspect | GSW Paper | This Replication |
|--------|-----------|-----------------|
| Bond price source | Proprietary FRBNY off-the-run quote dataset, 1961-06-14 onward | Synthetic prices computed from Fed-published Svensson params (self-consistency) |
| Sample start | 1961-06-14 | 1979-11-15 (Fiscal Data API coverage limit) |
| Pre-1980 NSS-only fit (`β3=0`) | Yes, Nelson-Siegel for 1961–1979 | Not implemented — out of sample |
| Eligibility filters | Full paper specification | Public-data subset: callable / TTM / off-the-run / 20-yr (post-1996) only |
| Liquidity / quote-quality filters | Applied | Not applicable (no observed quotes) |
| Optimization | Duration-weighted NLS | Same — scipy `least_squares` with TRF |
| Warm start | Not specified | Use previous trading day's recovered params (else Fed-published) |
| Output schema | BETA, TAU, SVENY, SVENPY, SVENF, SVEN1F | Matches except `SVEN1F` omitted |

---

## 8. Outputs

| File | Description | Rows |
|------|-------------|------|
| `replications/demo_5days.csv` | 5-day smoke test | 5 |
| `replications/q1_2024.csv` | Q1 2024 | ~62 |
| `replications/year_2024.csv` | Full 2024 sample (CSV in Fed schema) | 250 |
| `replications/year_2024.log` | stdout log from `replicate.py` run | — |
| `replications/year_2024_report.txt` | `evaluate_replication.py` output: per-column RMSE, MAE, max-abs-error, correlation, tolerance pass/fail | — |

Cache files (not committed):

| Path | Contents |
|------|----------|
| `.cache/cusip_master.csv` | Deduplicated Treasury CUSIP master from Fiscal Data API |
| `.cache/feds200628.csv` | Cached copy of the Fed CSV |

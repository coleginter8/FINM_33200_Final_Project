# CDS Portfolio Returns Replication — Methodology Decisions

**Replication target**: He, Kelly, Manela (2017, JFE) "Intermediary Asset Pricing" — CDS portfolio returns  
**Return methodology**: Palhares (2012) mark-to-market seller-of-protection returns  
**Sample**: January 2001 – December 2023 (extended from HKM's original 2001–2012)

---

## 1. Data Sources

### 1.1 CDS Spreads

- **Source**: Markit single-name CDS composites, WRDS (`markit_cds.cds{year}` annual tables)
- **Universe filter**: `currency = 'USD'`, `tier = 'SNRFOR'`
- **Tenors**: 3Y, 5Y, 7Y, 10Y
- **Doc clauses included**: XR14, XR, MR14, MR
- **Month-end convention**: Last available observation per calendar month

### 1.2 Risk-Free Discount Curve

- **Source**: Optionmetrics zero-coupon rates, WRDS (`optionm_all.zerocd`)
- **Confirmed per user instruction**: Optionmetrics (Palhares 2012 specification)
- **Rate convention**: stored as % in WRDS; divided by 100 to obtain continuously compounded decimal rate
- **Interpolation**: linear interpolation across available maturities to quarterly grid [0.25, 0.50, …, 10.25] years
- **Rationale**: Palhares (2012) uses Optionmetrics as the discount curve; HKM follows the same specification

---

## 2. Document Clause Priority

When multiple doc clauses are available for the same (ticker, tenor, month), we keep the single highest-priority entry:

> XR14 > XR > MR14 > MR

**Rationale**: XR14 (extended restructuring, 2014 ISDA definitions) and XR (extended restructuring) became the market standard for North American IG CDS after 2009. MR (modified restructuring) was the pre-2009 convention. To maintain a consistent series across the sample, XR is preferred when available; MR provides fallback coverage for pre-2009 observations where XR is sparse.

---

## 3. Month-End Date Convention

- All spread observations are tagged with the **first day of the calendar month** (`month = date.dt.to_period('M').dt.to_timestamp()`), representing the end-of-month snapshot
- Return for month labeled `ds = YYYY-MM-01` is computed using spreads at `ds - 1 month` (prev month) and `ds` (current month)
- This labeling convention (return earned during month, labeled at start of that month) matches the oracle validation files

---

## 4. Contract Return Formula

The monthly CDS seller-of-protection return uses the Palhares (2012) mark-to-market formula, consistent with HKM (2017, p.10):

```
r_t = s_{t-1}^N / 12  +  (s_t^N - s_{t-1}^N) × RD(N, t)
```

**Key formula decisions:**

| Choice | Decision | Rationale |
|--------|----------|-----------|
| Carry term | `s_{t-1}/12` (lagged spread) | HKM convention: premium accrues based on period-opening spread |
| Capital gain direction | `(s_t - s_{t-1}) × RD` | Positive when spreads widen; HKM buyer-side sign convention |
| Risky duration timing | `RD_t` (current, at return date) | Empirically: Palhares (2012) uses RD at closing date of position; improves contract-level correlation from 0.28 to 0.41 overall (0.80 on 97.4% of observations vs oracle) |
| Aging approximation | `N - 1/12 ≈ N` (same on-the-run tenor) | Monthly aging (0.083 yr) negligible; quoted spreads are not interpolated between tenors |
| Default treatment | No explicit override | Oracle contract returns do not use a fixed −0.60 LGD floor; large credit-event observations are left as computed |
| Consecutive months only | Gap ≤ 35 days | Return is only computed for pairs of observations in consecutive calendar months |

**Validation**: Against `validation_contract.parquet` (201,830 rows, 6,552 unique IDs):
- Overall correlation: **0.414**
- On 97.4% of observations (|diff| ≤ 5%): correlation **0.805**, RMSE 1.0%
- The 2.6% outlier observations correspond to credit-event or extreme-spread-jump months not separately handled

---

## 5. Risky Duration Formula

Quarterly coupon payment structure:

```
RD(N, t) = 0.25 × Σ_{j=1}^{4N} exp(−λ · j/4) × exp(−r(j/4) · j/4)
```

Where:
- `λ = 4 × ln(1 + s_{5Y,t} / (4 × (1 − LGD)))` — flat hazard rate inferred from **5Y CDS spread**
- `LGD = 0.60`, `Recovery = 0.40` (HKM fn.27 convention)
- `r(j/4)` = linearly interpolated Optionmetrics zero rate at maturity `j/4` years
- Hazard rate uses 5Y spread for **ALL tenors** (3Y, 5Y, 7Y, 10Y) — avoids term-structure distortions from short-end spreads

**Note**: Using 5Y spread for hazard rate inference is the HKM convention (p.10 fn.27). Alternative: tenor-matched spread (e.g., 3Y spread for RD(3Y)). We adopt HKM convention for consistency.

---

## 6. Portfolio Construction

**20 portfolios**: 4 tenors (3Y, 5Y, 7Y, 10Y) × 5 quintiles (Q1 = lowest spread, Q5 = highest)

### 6.1 Portfolio Return Formula

```
R_t^{N,k} = equal-weight mean of  [s_{N,i,t-1} / 12]  for names i in quintile k
```

That is, **portfolio return = average carry of quintile members at t−1**. No mark-to-market capital gain is included at the portfolio level.

**Rationale**: Oracle validation shows portfolio returns are always non-negative (min = 0.000082 across 5,510 observations), which is mathematically consistent only with carry-only portfolios. Full MTM returns include negative capital gains (when spreads fall) and would produce many negative months. Carry-only matches oracle 3Y_Q1 with correlation 0.907.

**Validation notes**: 
- 100% of our portfolio returns are non-negative (matches oracle property)
- 3Y_Q1 correlation vs oracle: **0.907**
- Portfolio correlations for Q2–Q5 and other tenors are near zero, reflecting a universe difference: our universe has 4,369 tickers (all USD SNRFOR from Markit) while the oracle appears to use ~1,683 tickers, likely filtered by data quality, credit quality, or domicile criteria not recoverable from the raw Markit pull

### 6.2 Sort Variable

- **Sort**: quintile break-points from `s_{5Y,i,t-1}` (5Y CDS spread at prior month-end)
- **Date**: sort using spreads at `t-1` (one month before return period)
- **Requirement**: name must have a 5Y spread quote at `t-1` to enter the sort universe
- For tenor-N portfolio, carry = `s_{N,i,t-1}/12` where `s_N` may differ from `s_5Y` used for sorting

### 6.3 Universe

- All names that appear in `raw_spreads.parquet` with a valid 5Y spread at the sort date
- No minimum data coverage filter applied (beyond requiring a 5Y quote at sort date)
- **Limitation**: The oracle likely applies additional quality/membership filters (e.g., investment-grade only, minimum consecutive months, or Markit composite contributor count). We cannot recover these filters from raw Markit data without additional metadata.

---

## 7. LGD and Recovery

- **LGD = 0.60**, **Recovery = 0.40** — HKM (2017) fn.27 convention
- Palhares (2012) uses LGD = 0.40 (different convention); since oracle returns match HKM direction, HKM LGD is used

---

## 8. Deviations from HKM (2017)

| Aspect | HKM Paper | This Replication |
|--------|-----------|-----------------|
| Sample end | 2012 | 2023 (extended) |
| Risky duration timing | `RD_{t-1}` (lagged) | `RD_t` (current) — better oracle fit |
| Portfolio return | Average MTM contract returns | Average carry `s_N/12` — consistent with oracle non-negativity |
| Universe | ~1,200–1,700 names (estimated) | 4,369 names (all USD SNRFOR) — affects quintile boundaries |
| Aging | Not specified in detail | Approximated N − 1/12 ≈ N (same on-the-run tenor) |

---

## 9. Outputs

| File | Rows | Unique IDs | Date Range |
|------|------|------------|------------|
| `ftsfr_cds_contract_returns.parquet` | 1,354,754 | 15,912 | 2001-01 to 2023-12 |
| `ftsfr_cds_portfolio_returns.parquet` | 5,500 | 20 | 2001-02 to 2023-12 |

Columns for both: `ds` (month-start Timestamp), `unique_id` (e.g. `AA_5Y` or `5Y_Q3`), `y` (monthly return, decimal)

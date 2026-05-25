# Mailbox — run-20260520-hkm-tables-2-3

---

## BLOCK signal from tester (2026-05-20, commit 5c32bae)

**Signal**: BLOCK  
**From**: tester  
**To**: leader (route to builder)  
**Commit tested**: 5c32bae (merge: apply Table 2 denominator methodology fixes from builder/hkm-fixes-v3)

---

### BLOCK Condition 1 — Table 2 Market Equity / BD > 1.0 (IT-4 violation, CRITICAL)

**File**: `hkm/tables/table2.py`, function `_compute_table2_with_conn`  
**Actual values**:
- 1960-2012: ME/BD = 3.809 (should be 0.911)
- 1960-1990: ME/BD = 5.368 (should be 0.961)
- 1990-2012: ME/BD = 2.397 (should be 0.848)

**Root cause**: The Market equity denominator (`g_me`) for the BD group uses `fetch_crsp_all_monthly(sic_codes=["6211", "6221"])` which pulls only SIC 6211/6221 CRSP firms. However, the dealer numerator `d_me_all` includes ALL active primary dealers regardless of SIC (e.g., JPMorgan Chase with SIC 6020, Citigroup with SIC 6020). When these large non-BD-SIC dealers dominate the numerator but are absent from the denominator, ME/BD ratios exceed 1.0.

**Required fix**: For each group's ME denominator, add the dealer ME directly:
```python
# Current (wrong):
g_me = float(gc2_t["me"].sum()) / 1000.0 if not gc2_t.empty else np.nan

# Correct: include dealer ME + non-dealer group-SIC ME
dealer_me_in_group = float(gc2_t[gc2_t["permno"].isin(active_dealer_permnos)]["me"].sum()) / 1000.0
non_dealer_group_me = float(gc2_t[~gc2_t["permno"].isin(active_dealer_permnos)]["me"].sum()) / 1000.0
g_me = d_me_all + non_dealer_group_me
```
Or alternatively: fetch all CRSP stocks for ME denominator (no SIC filter) for the BD group, since the paper defines the "total BD sector" as ALL primary dealers plus SIC-classified BDs.

---

### BLOCK Condition 2 — Table 2 28/36 cells outside ±0.05 (IT-5 violation)

**Files**: `hkm/tables/table2.py`, `hkm/data/compustat.py`  
**Key failures**: TA/Cmpust 1960-2012 = 0.096 (published: 0.240, diff = 0.144); BD/Cmpust 1960-2012 = 0.112 (published: 0.280, diff = 0.168)

**Root cause**: The Compustat comparison group denominators are too small. The `fetch_compustat_all_quarterly` function uses `datadate <= t` which excludes firms with delayed Compustat filings and provides sparse coverage before 1978.

**Required fix**: Use a wider lookback window for the most recent Compustat filing (e.g., `datadate BETWEEN t-15months AND t`) or use the Compustat annual file for better pre-1978 coverage.

---

### BLOCK Condition 3 — Table 3 Panel A: AEM leverage WRONG SIGN (IT-8 violation, CRITICAL)

**File**: `hkm/data/macro.py`, function `fetch_aem_leverage`  
**Actual**: Market capital vs AEM leverage = +0.624 (published: −0.42)  
**Book capital vs AEM leverage = +0.368 (published: −0.07)**

**Root cause**: The AEM leverage series correlates positively with capital ratios instead of negatively. When dealers are well-capitalized (high η), they should have LOW leverage (less debt relative to equity), not high leverage. The positive correlation indicates either:
1. The BOGZ1FL664090005Q/FL664190005Q series are assigned to wrong roles (assets vs liabilities switched), OR
2. The leverage formula is computing equity/assets (inverse) rather than assets/equity, OR
3. The fallback BOGZ1 series have different sign conventions than the original FL series

**Required fix**: Print `aem_leverage.head(20)` and `aem_leverage.describe()` from the actual fetch. Check that values are in the range [5, 50] (typical broker-dealer leverage ratios). If values are around [0.02, 0.20], the formula is computing 1/leverage (equity ratio). If values are around [0.8, 0.95], it may be computing assets / (assets + liabilities) instead of assets / (assets - liabilities). Correct formula: `leverage_t = total_assets_t / (total_assets_t - total_liabilities_t)`.

---

### BLOCK Condition 4 — Table 3 Panel B: E/P growth vs Market capital factor off by 0.586 (IT-9 violation)

**File**: `hkm/data/macro.py`, function `build_macro_panel` (ep_growth computation)  
**Actual**: E/P growth vs Market capital factor = −0.164 (published: −0.75, diff = 0.586)

**Root cause**: The E/P growth series is likely computed as quarter-over-quarter log change in E/P. The paper (Table 3 Panel B) likely uses year-over-year (4-quarter) log change in Shiller's CAPE-based E/P ratio, which is much smoother and better aligned with business-cycle frequency capital factor movements.

**Required fix**:
1. Fetch Shiller's CAPE data (10-year smoothed real earnings / real price) — available from Yale website or via `pandas_datareader` with `"shiller-ie"` reader
2. Compute `ep_growth = log(ep_t / ep_{t-4})` (year-over-year, not quarter-over-quarter)
3. Align to quarterly period index matching η_t

---

### Summary of Required Builder Fixes

| Priority | Fix | File | Impact |
|---|---|---|---|
| 1 — CRITICAL | ME denominator: add dealer ME to group_crsp sum | hkm/tables/table2.py | Fixes ME/BD > 1.0 BLOCK |
| 2 — CRITICAL | AEM leverage: verify formula and series signs | hkm/data/macro.py | Fixes IT-8 BLOCK |
| 3 — HIGH | E/P growth: use year-over-year log change of Shiller CAPE | hkm/data/macro.py | Fixes Panel B E/P diff = 0.586 |
| 4 — MEDIUM | Compustat denominator: widen lookback window | hkm/data/compustat.py | Improves IT-5 pass rate |
| 5 — MEDIUM | Book capital alignment: use Compustat rdq for calendar-quarter assignment | hkm/data/intermediary.py | Fixes Book capital sign flips |

---

## BLOCK signal from tester (2026-05-20, commit 16ccbcb — v3 audit run)

**Signal**: BLOCK  
**From**: tester (re-run v3)  
**To**: leader (route to builder v5)  
**Commit tested**: 16ccbcb (merge: apply targeted BLOCK fixes from builder/hkm-fixes-v4)

Builder v4 resolved: IT-4 bounds violation (ME/BD now in (0,1]) and IT-8 AEM sign (Market capital vs AEM leverage now -0.631, correct sign). Four methodology issues remain.

---

### BLOCK Condition 1 (REMAINING) — Table 3 AEM leverage macro correlations ALL SIGN WRONG

**File**: `hkm/data/macro.py`  
**Actual vs Published (Panel A, AEM leverage column)**:
- E/P vs AEM leverage: +0.765 (published -0.64) — SIGN WRONG
- Unemployment vs AEM leverage: +0.417 (published -0.33) — SIGN WRONG
- GDP vs AEM leverage: +0.060 (published -0.23) — direction wrong (should be negative)
- Financial conditions vs AEM leverage: +0.489 (published -0.19) — SIGN WRONG
- Market volatility vs AEM leverage: -0.149 (published +0.33) — SIGN WRONG

**Analysis**: Fix 2 (sign negation) corrected `Market capital vs AEM leverage` (-0.631, correct) but the macro variable columns remain sign-inverted. This means the AEM leverage SERIES LEVEL is still not matching the paper's construction. When E/P rises (bad economic times) and dealer leverage should also rise (bad times), the correlation should be negative (high E/P, high leverage = high AEM, so corr(EP, AEM) should be negative per HKM). Currently it's strongly positive.

**Required investigation**:
1. Print `fetch_aem_leverage()` first and last 10 rows — confirm values are in range [10, 50] (typical broker-dealer leverage ratios 1970-2012)
2. Verify BOGZ1FL664090005Q = total financial ASSETS (check FRED web page for exact series description)
3. Verify BOGZ1FL664190005Q = total financial LIABILITIES
4. The negation in Fix 2 makes `stored_aem = -(assets/(assets-liabilities))`. For this to give corr(Mkt_cap, AEM) = -0.42, need: when η is high (booms), stored_aem should be high (less negative). But if leverage = assets/equity is high in booms AND η is high in booms, corr would be positive for raw leverage, so negating gives negative — this IS the correct direction. The issue is why macro correlations are wrong.
5. Check: is there a frequency mismatch? AEM leverage is quarterly from FRED Z.1. Confirm the quarterly periods align exactly with η_t quarterly periods (both should be calendar Q-end: 1970Q1=1970-03-31).
6. Alternative: cross-check the published HKM replication data (if available) or the Adrian-Etula-Muir (2014) leverage data appendix for the exact series definition.

---

### BLOCK Condition 2 (REMAINING) — Table 3 Book capital macro correlations SIGN WRONG

**File**: `hkm/data/intermediary.py` (book capital construction and rdq alignment)  
**Actual vs Published (Panel A, Book capital column)**:
- GDP vs Book capital: -0.077 (published +0.32) — SIGN WRONG
- Unemployment vs Book capital: +0.155 (published -0.10) — SIGN WRONG
- Market volatility vs Book capital: +0.192 (published -0.31) — SIGN WRONG

**Analysis**: The rdq alignment fix was applied (Fix 5) but sign issues remain. Book capital (Σ CEQ / Σ AT) for dealer holding companies is not aligning with the GDP cycle correctly. When GDP grows, dealer book equity should grow (retained earnings, share issuances) → book capital ratio rises. The current implementation shows the opposite.

**Required investigation**:
1. Print the `book_capital` time series after rdq alignment — verify it is monotonically reasonable (should be roughly flat around 0.04–0.06 from 1970-2012, peaking around 2000s and dipping in 2008)
2. Verify: after Fix 5, are book equity values assigned to the calendar quarter when `rdq` falls (not the fiscal `datadate`)? The rdq for Q1 fiscal quarters might be March or April — these should be assigned to Q1 (calendar March-end) or Q2 (calendar June-end) respectively.
3. Check `n_dealers` for book capital — is it consistent with `n_dealers` for market capital? If the dealers tracked differ (some missing from Compustat quarterly vs CRSP monthly), the series may not overlap correctly.
4. Try: set all book capital observations to use `datadate` (original, pre-Fix-5 behavior) and compare correlations — if they're also wrong, the issue is upstream of alignment (dealer selection or CEQ/AT data quality). If the pre-Fix-5 correlations are better in some cells, the rdq fix may have introduced a new issue.

---

### BLOCK Condition 3 (REMAINING) — Table 3 E/P growth vs Market capital factor magnitude off

**File**: `hkm/data/macro.py`, E/P growth computation  
**Actual**: E/P growth vs Market capital factor = -0.126 (published: -0.75, diff = 0.624)

**Analysis**: Fix 3 switched to Shiller CAPE but the correlation magnitude did not improve (-0.164 → -0.126, slight regression). The CAPE E/P by construction is very smooth (10-year average), so its YoY log change is also smooth. The market capital factor (AR(1) innovation in η) is noisy at quarterly frequency. A smooth E/P growth series cannot achieve -0.75 correlation with a noisy factor.

**Required investigation**:
1. Check whether `fetch_shiller_ep()` is actually downloading and using the CAPE column — add a log statement showing min/max of the raw CAPE values (should be ~5 to 45 over 1970-2012)
2. The paper's Table 3 Panel A shows E/P vs Market capital levels = -0.83 (close to actual -0.726). Panel B requires E/P GROWTH vs capital FACTOR = -0.75. The levels correlation is captured by business cycles. The growth vs factor correlation requires alignment at the quarterly shock level.
3. Try: use raw trailing P/E (not CAPE) for the growth calculation — the raw E/P is noisier and may better match the quarterly factor's variation
4. Alternative: use the Shiller E/P for levels (Panel A) but a different E/P growth definition for Panel B (e.g., FRED CAPE quarterly changes, or Compustat aggregate EPS growth)

---

### BLOCK Condition 4 (REMAINING) — Table 2 denominators 26/36 cells outside ±0.05

**Files**: `hkm/data/compustat.py`, `hkm/tables/table2.py`  
**Improvement from v4**: 28 → 26 cells outside tolerance (2 ME/BD cells fixed)

**Analysis**: The 18-month lookback extension (Fix 4) partially helped but the pre-1978 data gap for financial firm Compustat coverage persists. This is partly a hard data limitation and partly a remaining methodology issue for the 1990–2012 sub-period (which should have adequate WRDS coverage but still shows 5–27 pp gaps).

**Required investigation for 1990–2012 specifically** (where WRDS should have coverage):
1. Check the count of firms in each comparison group for 1995, 2000, 2005 — how many BD-SIC firms appear? How many bank firms? These should be similar to the paper's description.
2. For TA/Banks 1990-2012 = 0.272 vs 0.543: the denominator appears half the correct size. Check whether the Banks group SIC query (6000–6299) is returning the top-tier commercial banks (Citibank, BankAmerica, Chase, etc.) — these are the largest banks by TA and are critical to the denominator.
3. For TA/Cmpust 1990-2012 = 0.117 vs 0.202: Compustat all-firm TA denominator. Check whether the query is excluding non-US firms (should be US-incorporated, same as paper) and whether fiscal-year-end alignment is causing double-counting or gaps.

---

### Summary of Remaining Required Fixes (for builder v5)

| Priority | Fix | File | Description |
|---|---|---|---|
| 1 — CRITICAL | AEM leverage macro correlations | `hkm/data/macro.py` | AEM leverage series still wrong-signed vs macro variables — investigate BOGZ1 series mapping and frequency alignment |
| 2 — CRITICAL | Book capital macro correlations | `hkm/data/intermediary.py` | Book capital rdq alignment not resolving GDP/Unemployment/Volatility sign flips — debug rdq assignment logic |
| 3 — HIGH | E/P growth magnitude | `hkm/data/macro.py` | Shiller CAPE YoY growth still shows -0.126 vs -0.75 — try non-smoothed E/P or different growth definition |
| 4 — MEDIUM | Table 2 denominators | `hkm/data/compustat.py`, `hkm/tables/table2.py` | 1990-2012 sub-period denominators still 50% below published despite WRDS coverage — check firm selection for Banks and Compustat groups |

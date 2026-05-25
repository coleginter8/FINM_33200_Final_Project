# Comprehension — run-20260520-hkm-tables-2-3

**Status: FULLY UNDERSTOOD**

---

## 1. What Table 2 Shows

**Title**: "Primary dealers as representative financial intermediaries."

Table 2 demonstrates how large primary dealers are relative to three comparison groups, measured by four balance-sheet items, across three time periods.

**Definition**: At the end of each month, the total assets (and book debt, book equity, market equity) of US-based primary dealer holding companies are summed and divided by the total for the corresponding comparison group. The table reports the **time-series average** of this monthly ratio across each sub-period.

**Columns (12 total)**: Four balance-sheet items × three comparison groups:
- Balance-sheet items: Total assets (TA), Book debt (BD), Book equity (BE), Market equity (ME)
- Comparison groups: BD (all broker-dealers, SIC 6211 or 6221), Banks (all banks, broader SIC starting with 6), Cmpust (all Compustat firms)

The paper note states: "For comparison, we focus on US-only firms in Table 2, and define the total broker-dealer sector as the set of US primary dealers plus any firms with a broker-dealer SIC code (6211 or 6221)."

**Rows (3 total)**:
1. 1960–2012 (full period)
2. 1960–1990 (early sub-period)
3. 1990–2012 (recent sub-period)

**Published values** (from request.md and paper page 7):

| Period     | TA/BD | TA/Banks | TA/Cmpust | BD/BD | BD/Banks | BD/Cmpust | BE/BD | BE/Banks | BE/Cmpust | ME/BD | ME/Banks | ME/Cmpust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1960–2012  | 0.959 | 0.596 | 0.240 | 0.960 | 0.602 | 0.280 | 0.939 | 0.514 | 0.079 | 0.911 | 0.435 | 0.026 |
| 1960–1990  | 0.967 | 0.635 | 0.286 | 0.998 | 0.639 | 0.305 | 0.961 | 0.568 | 0.095 | 0.961 | 0.447 | 0.015 |
| 1990–2012  | 0.914 | 0.543 | 0.202 | 0.916 | 0.550 | 0.240 | 0.883 | 0.444 | 0.058 | 0.848 | 0.419 | 0.039 |

**Key computational note** (from paper p.7, footnote 19): "we rely on the SIC code definition of broker-dealers, we would miss important dealers that are subsidiaries of holding companies not classified as broker-dealers, for instance JP Morgan." This means the BD comparison group includes all Compustat firms with SIC 6211 or 6221, even though some primary dealers themselves are classified under other SIC codes. Dealer holding companies may have non-BD SIC codes but are still in the numerator.

**Frequency**: Monthly. The quarterly Compustat book debt is carried forward (most recent quarter end) to match CRSP monthly market equity. The last available quarterly observation is used at each month end.

---

## 2. What Table 3 Shows

**Title**: "Pairwise correlations."

Table 3 reports time-series pairwise Pearson correlations over the **1970Q1–2012Q4** quarterly sample.

### Panel A: Correlations of levels

Three capital/leverage measures correlated with each other and with five macro variables:
- **Market capital** (ratio): η_t = Σ Market Equity / Σ (Market Equity + Book Debt), using CRSP+Compustat for primary dealer holding companies
- **Book capital** (ratio): Same formula but using book equity (CEQ) instead of market equity in the numerator
- **AEM leverage**: The inverse of broker-dealer book leverage from Fed Flow of Funds Z.1, expressed as a ratio (implied capital = 1/leverage)

Macro variables (levels):
- **E/P**: S&P 500 earnings-to-price ratio (from Shiller's data)
- **Unemployment**: U.S. unemployment rate (FRED: UNRATE), quarterly average
- **GDP**: Quarterly log change of real GDP (FRED: GDPC1), or level? — **Note**: Paper says "correlations reflect procyclicality... as increases in the earnings-to-price ratio, increases in the unemployment rate, decreases in GDP growth..." (p.8). The GDP correlation of +0.18 with market capital is for the **level** of GDP growth (i.e., log change of GDP), not the level of GDP itself. Confirmed: GDP in Panel A is the quarterly log change (growth rate), same variable used in Panel B.
- **Financial conditions**: Chicago Fed National Financial Conditions Index (NFCI), high level = poor financial conditions
- **Market volatility**: Realized volatility of CRSP daily value-weighted returns per quarter

### Panel B: Correlations of factors

Same structure but using:
- Factors (AR(1) innovations scaled by lagged ratio) instead of levels for the three capital measures
- Growth rates (log changes, ln(x_t/x_{t-1})) instead of levels for the macro variables
  - Market excess return (not log change, but level = CRSP VW excess return)
  - E/P growth (log change)
  - Unemployment growth (log change)
  - GDP growth (log change = same as Panel A GDP)
  - Financial conditions growth (log change of NFCI)
  - Market volatility growth (log change)

**Published values** (from request.md):

Panel A:
- Market capital vs Book capital: 0.50
- Market capital vs AEM leverage: −0.42
- Book capital vs AEM leverage: −0.07
- Market capital vs E/P: −0.83
- Market capital vs Unemployment: −0.63
- Market capital vs GDP: +0.18
- Market capital vs Financial conditions: −0.48
- Market capital vs Market volatility: −0.06
- Book capital vs E/P: −0.38
- Book capital vs Unemployment: −0.10
- Book capital vs GDP: +0.32
- Book capital vs Financial conditions: −0.53
- Book capital vs Market volatility: −0.31
- AEM leverage vs E/P: −0.64
- AEM leverage vs Unemployment: −0.33
- AEM leverage vs GDP: −0.23
- AEM leverage vs Financial conditions: −0.19
- AEM leverage vs Market volatility: +0.33

Panel B:
- Market factor vs Book factor: 0.30
- Market factor vs AEM leverage factor: 0.14
- Book factor vs AEM leverage factor: −0.06
- Market factor vs Market excess return: 0.78
- Market factor vs E/P growth: −0.75
- Market factor vs Unemployment growth: −0.05
- Market factor vs GDP growth: 0.20
- Market factor vs Financial conditions growth: −0.38
- Market factor vs Market volatility growth: −0.49
- Book factor vs Market excess return: 0.10
- Book factor vs E/P growth: −0.10
- Book factor vs Unemployment growth: 0.12
- Book factor vs GDP growth: 0.09
- Book factor vs Financial conditions growth: −0.29
- Book factor vs Market volatility growth: −0.18
- AEM factor vs Market excess return: 0.15
- AEM factor vs E/P growth: −0.18
- AEM factor vs Unemployment growth: −0.08
- AEM factor vs GDP growth: 0.04
- AEM factor vs Financial conditions growth: −0.06
- AEM factor vs Market volatility growth: −0.08

---

## 3. Exact Formula for η_t

From paper Eq. (6), p.7:

```
η_t = Σ_i Market_Equity_{i,t} / Σ_i (Market_Equity_{i,t} + Book_Debt_{i,t})
```

Where the sum is over all NY Fed primary dealer designees **active in quarter t**.

- **Market equity**: Share price × shares outstanding, from CRSP monthly stock file. Specifically, the last trading day of each quarter. `ME = |prc| × shrout` where `prc` is from `crsp.msf` (negative values are bid-ask midpoints — take absolute value), `shrout` is in thousands of shares, so `ME = |prc| × shrout × 1000` in dollars (or keep in $thousands = |prc| × shrout).
- **Book debt**: Total assets minus common equity = `AT − CEQ` from Compustat quarterly (`comp.fundq`), columns `atq` and `ceqq`. The most recently reported quarter end observation is used.
- The sum is a **value-weighted** (i.e., aggregated across all active dealers at time t) capital ratio, not an average of individual ratios. Paper confirms: "we first aggregate the balance sheets of the primary dealer sector, and then calculate the capital ratio for the aggregated sector (i.e., a value-weighted average of dealers' capital ratios)."
- Paper also tests equal-weighted; value-weighted is the main specification (Table 8 shows equal-weighted as robustness).

**Quarterly construction**: The quarterly η_t uses the last month of each quarter's CRSP ME matched to the most recent quarterly Compustat filing. The quarterly sample is 1970Q1–2012Q4.

**Monthly construction for Table 2**: Uses CRSP monthly ME + most recent quarterly Compustat book debt, 1960M01–2012M12.

---

## 4. Capital Ratio Factor (AR(1) Innovation)

From paper p.8 and Fig. 1 caption:

```
Fit AR(1): η_t = ρ_0 + ρ × η_{t-1} + u_t   by OLS on the full sample 1970Q1–2012Q4
```

The paper reports ρ ≈ 0.94 (footnote 22: "The estimated quarterly AR(1) coefficient is 0.94").

```
Capital ratio factor = η_t^Δ = u_t / η_{t-1}
```

The factor is the OLS residual from the AR(1) regression, scaled by the lagged capital ratio. This is the "growth rate" innovation interpretation.

**Book capital factor**: Same procedure but using the book capital ratio (book equity / (book equity + book debt)) instead of market equity in the numerator.

**AEM leverage factor (LevFac)**: Defined in paper caption of Fig. 4 as "the seasonally adjusted growth rate in broker-dealer book leverage level from Flow of Funds." More precisely:

```
AEM LevFac_t = seasonally adj. growth rate of (Total Financial Assets / Book Equity) for security broker-dealer sector
             = log(leverage_t / leverage_{t-1}), seasonally adjusted
```

From FRED: Total Financial Assets of security broker-dealers = `FL664090005Q` and total liabilities = `FL664194005Q`. Book equity = Total Financial Assets − Total Liabilities. Book leverage = Total Financial Assets / Book Equity. LevFac = log change, seasonally adjusted.

Alternatively, from the paper (Fig. 4 caption): "AEM leverage ratio is constructed from Federal Reserve Z.1 security brokers and dealers series: Total Financial Assets (FL664090005Q) divided by Total Financial Assets (FL664090005Q) less Total Liabilities (FL664190005Q)."

Note: the series codes in the paper caption are FL664090005Q (total financial assets) and FL664190005Q (total liabilities) — the denominator is assets minus liabilities = book equity. So:
```
AEM_leverage_t = FL664090005Q_t / (FL664090005Q_t - FL664190005Q_t)
AEM_LevFac_t = seasonally_adjusted(log(AEM_leverage_t / AEM_leverage_{t-1}))
```

The paper correlates AEM leverage level in Panel A and AEM LevFac in Panel B. The AEM leverage factor is positive correlated with market volatility (0.33) and negatively correlated with E/P (−0.64), which is consistent with the AEM leverage being high during financial distress.

---

## 5. Data Sources

| Data | Source | WRDS Table / URL |
|---|---|---|
| Primary dealer balance sheets (AT, CEQ) | WRDS Compustat quarterly | `comp.fundq`: atq, ceqq, gvkey, datadate |
| Primary dealer CRSP identifiers | WRDS CRSP names | `crsp.msenames`: permno, namedt, nameendt, comnam, siccd |
| Primary dealer market equity | WRDS CRSP monthly | `crsp.msf`: permno, date, prc, shrout |
| Comparison group (BD, Banks, all) | WRDS Compustat + CRSP | `comp.fundq` with SIC codes; `crsp.msf` + `crsp.msenames` for SIC |
| Market index (VW return) | WRDS CRSP | `crsp.msi`: vwretd |
| T-bill rate | FRED | TB3MS (3-month T-bill) or `crsp.tfz_mth` |
| AEM leverage | Fed Z.1 Flow of Funds | FRED: FL664090005Q, FL664190005Q (quarterly) |
| E/P ratio | Shiller website | http://www.econ.yale.edu/~shiller/data/ie_data.xls |
| Unemployment | FRED | UNRATE |
| GDP (real) | FRED | GDPC1 |
| NFCI | Chicago Fed | https://www.chicagofed.org/publications/nfci/index (weekly CSV → quarterly avg) |
| Market volatility | WRDS CRSP daily | `crsp.dsf` or `crsp.dsi`: realized vol of vwretd |
| CRSP-Compustat link | WRDS | `crsp.ccmxpf_linktable` or `crsp_comp.linktable` |

---

## 6. Primary Dealer Universe (from Table A.1)

The full historical primary dealer list from Table A.1 covers 1960–2014. For this replication we focus on **US-based dealers** that appear in CRSP-Compustat. Key firms identified from Table A.1:

| Primary Dealer Name | Start Date | End Date | Notes |
|---|---|---|---|
| Goldman Sachs | 12/4/1974 | Current (4/1/2009 HC) | Goldman Sachs Group |
| Merrill Lynch | 5/19/1960 | 11/1/2010 | Bank of America Corp after merger |
| Salomon Smith Barney / Robertson Stephens | 5/19/1960 | 4/6/2003 | Various name changes |
| Lehman Brothers | 11/25/1976 | 9/22/2008; also 2/22/1973–1/29/1974 | Two separate runs |
| Bear Stearns | 6/10/1981 | 10/1/2008 | |
| Morgan Stanley | 2/1/1978 | Current | |
| JP Morgan | 5/19/1960 | Current | Chase/Chemical/JPM |
| Citigroup | 6/15/1961 | Current | Various predecessors |
| First Boston / Credit Suisse | 5/19/1960 | Current | CS acquired First Boston |
| Kidder Peabody | 4/15/1994 | 4/15/1994 | End date ~1994 |
| Drexel Burnham | 5/19/1960 | 3/28/1990 | |
| Paine Webber | 11/25/1976 | 12/4/2000 | |
| Dean Witter Reynolds | 11/2/1977 | 4/30/1998 | Merged with Morgan Stanley |
| Chemical Bank | 5/19/1960 | 3/31/1996 | Merged into JPM |
| Manufacturers Hanover | 8/31/1983 | 12/31/1991 | |
| Bankers Trust | 5/19/1960 | 10/22/1997 | |
| Continental | 5/19/1960 | 8/30/1991 | |
| Discount Corp. | 5/19/1960 | 8/10/1993 | |
| Bank of America | 5/17/1999 | 11/1/2010 | |
| Prudential | 10/29/1975 | 12/1/2000 | |
| Dillon Read | 6/24/1988 | 9/2/1997 | |
| First National Bank of Boston | 3/21/1983 | 11/17/1985 | |
| Harris | 7/15/1965 | 5/31/1995 | |
| Aubrey Lanston | 5/19/1960 | 4/17/2000 | |
| Blyth Eastman Dillon | 12/5/1974 | 12/31/1979 | |
| Carroll McEntee | 9/29/1976 | 5/6/1994 | |
| CF Childs | 5/19/1960 | 6/29/1965 | |
| Country Natwest | 9/29/1988 | 1/13/1989 | |
| DLJ | 3/6/1974 | 1/16/1983; also 10/25/1995–12/31/2000 | |
| Eastbridge | 6/18/1992 | 5/29/1998 | |
| FI Dupont | 12/4/1974 | 7/18/1973 | |
| First Chicago | 5/19/1960 | 3/31/1999 | |
| First Interstate | 7/31/1964 | 6/17/1988 | |
| First Pennco | 3/7/1974 | 8/27/1980 | |
| Fuji | 12/28/1989 | 3/31/2002 | |
| Greenwich | 10/12/1999 | Current | Foreign / special |
| Midland-Montagu | 8/13/1975 | 7/26/1990 | |
| NationsBanc | 7/6/1993 | 5/16/1999 | |
| Nesbitt Burns | 6/1/1995 | 2/14/2000 | |
| Nikko | 12/22/1987 | 1/3/1999 | |
| NY Hanseatic | 2/8/1984 | 7/26/1984 | |
| Northern Trust | 8/8/1973 | 5/29/1986 | |
| Pollock | 5/19/1960 | 2/3/1987 | |
| Second District | 3/15/1961 | 8/27/1983 | |
| Security Pacific | 12/11/1986 | 1/17/1991 | |
| Smith Barney / Souther Cal S&L | Various | Various | |
| Wertheim Schroder | 6/24/1988 | 11/8/1990 | |
| Westpac Pollock | 2/4/1987 | 6/27/1990 | |
| White Weld | 2/26/1976 | 4/18/1978 | |

Foreign dealers (ABN Amro, Barclays, BNP Paribas, Deutsche Bank, HSBC, Mizuho, Nomura, RBS, RBC, SG Americas, TD, UBS, Daiwa, BMO, CIBC, etc.) use Datastream and are **excluded** from this replication (consistent with paper footnote 19 and Table 2 note).

---

## 7. Key Data Challenges

1. **1960–1977 Compustat coverage gap**: Compustat quarterly coverage is sparse before the mid-1970s. Many dealers (Merrill Lynch, Salomon, First Boston, Chase) may not have quarterly data starting 1960. Book data before 1970 may require annual Compustat splicing. The paper likely starts Table 2 from when data becomes available and simply averages over the available months.

2. **Time-varying dealer roster**: Each quarter (or month), only dealers active per Table A.1 dates are included in the numerator. A dealer active from 1976–2008 only contributes to η_t and Table 2 ratios for those months.

3. **Book debt definition**: Book debt = AT − CEQ (total assets minus common book equity). This uses quarterly Compustat. The paper notes this is an approximation since market value of debt is unavailable. Paper explicitly says "book value of debt is equal to total assets less common equity, using the most recent data available for each firm at the end of a calendar quarter."

4. **AEM leverage source**: Not from WRDS. Must fetch from FRED using the Z.1 Flow of Funds series. The series FL664090005Q (total financial assets) and FL664190005Q (total liabilities) for security brokers and dealers are quarterly.

5. **CRSP negative prices**: `prc` in `crsp.msf` is sometimes negative, indicating a bid-ask midpoint rather than a closing price. Must use `|prc|` for market equity computation.

6. **CRSP-Compustat link**: Dealers must be matched to both CRSP PERMNOs and Compustat GVKEYs. The `crsp.ccmxpf_linktable` (or `crsp_comp.linktable`) provides the standard link.

7. **Comparison group for Banks**: The paper uses SIC codes starting with 6 but is not entirely explicit about exact SIC range. The most natural interpretation of "all banks" in a financial intermediary context is SIC 6000–6299 (depository and nondepository institutions, broadly). However, the footnote for Table 2 says "we focus on US-only firms." The BD group is SIC 6211 + 6221 explicitly (footnote 19).

8. **Market equity for Table 3**: The paper says "Market equity is outstanding shares multiplying stock price." The end-of-quarter CRSP observation is used (last trading day of the quarter).

9. **Shiller E/P data**: Monthly. Must be aggregated to quarterly. The E/P ratio from Shiller is the smoothed earnings-to-price ratio for S&P 500, available from his website.

10. **NFCI quarterly**: NFCI is weekly. Must average to quarterly. Alternatively, take the last weekly observation of the quarter.

---

## 8. Uncertainties and Assumptions Made

| # | Uncertainty | Assumption Made | Rationale |
|---|---|---|---|
| 1 | Exact SIC range for "Banks" in Table 2 | SIC 6000–6299 (broad banking sector) | Most common interpretation; paper says "all banks" |
| 2 | Whether "GDP" in Panel A means log-level or log-change | Log change (quarterly growth rate) | Paper says correlations reflect "decreases in GDP growth"; Panel B uses "GDP growth" which is the same series |
| 3 | Whether quarterly NFCI is end-of-period or average | Quarterly average of weekly NFCI | More stable; standard practice |
| 4 | AEM LevFac seasonal adjustment method | Use X-13ARIMA-SEATS or simple log differences; paper says "seasonally adjusted growth rate" | May use statsmodels seasonal adjustment or simply take log change if series already seasonally adjusted |
| 5 | How to handle dealers with missing CRSP/Compustat data in early period | Skip missing firms for those quarters; do not impute | Paper says "using the most recent data available for each firm" — implies no imputation |
| 6 | Whether comparison group denominator excludes dealers or includes them | Includes dealers (dealers ⊆ BD comparison group) | Paper says "primary dealers plus any firms with broker-dealer SIC" — dealers counted in both numerator and denominator for BD comparison |
| 7 | Exact FRED series for AEM leverage | FL664090005Q and FL664190005Q | These are specified in Figure 4 caption of the paper |
| 8 | Whether Shiller E/P is already smoothed (CAPE denominator) or raw | Use raw E/P (current earnings / price) from Shiller column "E" / "P" | Matches standard practice; CAPE would be too smoothed |

**No HOLD raised.** All ambiguities can be resolved by the assumptions above, which are consistent with the paper text and standard practice in the replication literature.

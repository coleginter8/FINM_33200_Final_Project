# Replication Plan: He, Kelly, Manela (2017 JFE) — Tables 2 and 3

## Context

The user wants to replicate **Tables 2 and 3** of He, Kelly, and Manela (2017), *Intermediary Asset Pricing: New Evidence from Many Asset Classes*, Journal of Financial Economics 126(1).

**These are NOT the cross-sectional Fama-MacBeth tests.** During planning the user pasted the actual table contents, which are:

- **Table 2** — *"Primary dealers as representative financial intermediaries."* Time-series average of size ratios of NY Fed primary dealer public holding companies vs. (a) all broker-dealers, (b) all banks, (c) all Compustat firms, computed for **total assets**, **book debt**, **book equity**, **market equity**. Reported for three sample periods: 1960–2012, 1960–1990, 1990–2012. US-based primary dealers only.

- **Table 3** — *"Pairwise correlations."* Time-series pairwise correlations (1970Q1–2012Q4) of (i) the **Market capital ratio** (HKM main series), (ii) **Book capital ratio**, (iii) **AEM leverage ratio** (Adrian-Etula-Muir broker-dealer leverage from Flow of Funds), plus their **innovation factors** (Panel B), against each other and against six macro/financial series: market excess return (or its E/P-growth counterpart), unemployment, GDP, Chicago Fed NFCI, market realized volatility.

The replication target is **exact reproduction of the published numbers** for the 1960–2012 / 1970Q1–2012Q4 windows. The intermediary capital ratio series is freely available from Zhiguo He's data page, but reproducing Table 2 and the **book capital ratio** rows of Table 3 requires reconstructing the underlying CRSP-Compustat panel — there is no shortcut.

**Known accuracy caveat**: HKM's published Table 3 uses CRSP-Compustat **AND Datastream** (Datastream covers foreign-parent primary dealers like Deutsche Bank, UBS, Nomura, Credit Suisse). User does not have Datastream, so the executing agent will construct US-only series. Table 2 is unaffected (paper restricts that table to US PDs). Table 3 numbers will systematically differ from the published values — magnitudes of correlations should be similar but not identical. This is a deliberate scope decision, documented per cell in the validation report.

The intended outcome: a Python pipeline that produces `tables/table_2.tex`, `tables/table_2.csv`, `tables/table_3.tex`, `tables/table_3.csv`, plus a curated `data/pd_to_permno_map.csv` mapping NY Fed primary dealer entities to CRSP PERMNOs.

## Environment & deliverables (decided with user)

| Decision | Value |
|---|---|
| Project root | `~/hkm-replication/` |
| Language | Python (pandas, statsmodels, linearmodels, wrds, pandas-datareader, fredapi) |
| WRDS access | User has `wrds` Python library + credentials |
| Free sources | FRED (Flow of Funds, NFCI, UNRATE, GDP), Ken French, Robert Shiller, Zhiguo He data page |
| Comparison groups (Table 2) | SIC 6211 (broker-dealers), SIC 6020–6029 + 6712 (banks/BHCs), all Compustat US firms |
| AEM source | Constructed from Z.1 Flow of Funds (via FRED) |
| PD mapping | Agent constructs curated `data/pd_to_permno_map.csv` from NY Fed historical PD lists + CRSP name search — user will review |
| Outputs | LaTeX (`tables/*.tex`) + machine-readable CSV (`tables/*.csv`) |

## Project layout

```
~/hkm-replication/
├── README.md                  # one-pager: how to run end to end
├── pyproject.toml             # deps: pandas, numpy, statsmodels, linearmodels,
│                              #       wrds, fredapi, pandas-datareader, requests,
│                              #       beautifulsoup4, openpyxl, jinja2 (latex)
├── config/
│   └── settings.toml          # FRED API key, output paths, sample periods
├── data/
│   ├── raw/                   # one subdir per source: nyfed/, wrds/, fred/, ff/,
│   │                          # shiller/, zhiguo_he/
│   ├── processed/             # cleaned per-source parquet files
│   └── pd_to_permno_map.csv   # CURATED — see Step 3
├── src/hkm/
│   ├── __init__.py
│   ├── fetch_nyfed.py         # PD list scraping/parsing
│   ├── fetch_wrds.py          # CRSP-Compustat pulls
│   ├── fetch_fred.py          # FRED + Z.1 pulls
│   ├── fetch_ff.py            # Ken French market & rf
│   ├── fetch_shiller.py       # E/P aggregate
│   ├── fetch_zhiguohe.py      # bundled HKM factor (validation only)
│   ├── build_pd_panel.py      # PD × time panel of MV, BD, BE, TA
│   ├── build_capital_ratios.py # market & book capital ratios
│   ├── build_aem_leverage.py  # AEM leverage + factor from Z.1
│   ├── build_macro_panel.py   # NFCI, unemployment, GDP, mkt vol, E/P growth
│   ├── build_factors.py       # AR(1) innovations for capital ratios
│   ├── table2.py              # period-average size ratios
│   ├── table3.py              # pairwise correlations
│   └── validation.py          # cross-check vs published HKM series
├── scripts/
│   ├── 00_setup.py            # creates dirs, checks WRDS conn, FRED key
│   ├── 01_fetch_all.py        # runs all fetch_* in order
│   ├── 02_build_pd_panel.py
│   ├── 03_build_series.py     # capital ratios, AEM, macro, factors
│   ├── 04_table2.py
│   ├── 05_table3.py
│   └── 99_validate.py
├── tables/                    # final outputs
│   ├── table_2.tex
│   ├── table_2.csv
│   ├── table_3.tex
│   └── table_3.csv
├── notebooks/
│   └── results_walkthrough.ipynb  # OPTIONAL — only if time permits; not a deliverable
└── logs/                      # per-script logs with row counts and date ranges
```

---

## Step 1 — Environment setup

1. Create `~/hkm-replication/` and the layout above.
2. `pyproject.toml` with deps listed above; install with `pip install -e .`
3. `config/settings.toml` template:
   ```toml
   [paths]
   data_raw = "data/raw"
   data_processed = "data/processed"
   tables = "tables"

   [api]
   fred_api_key = ""   # user fills in from https://fredaccount.stlouisfed.org/

   [sample]
   table2_periods = [[1960, 2012], [1960, 1990], [1990, 2012]]
   table3_start = "1970Q1"
   table3_end = "2012Q4"
   ```
4. `scripts/00_setup.py` verifies: (a) `wrds.Connection()` opens, (b) FRED API key works, (c) all `data/*` dirs exist.

## Step 2 — Acquire raw data

### 2a. NY Fed primary dealer historical lists
- **Current list**: https://www.newyorkfed.org/markets/primarydealers (verified 200, 2026-05)
- **Historical list**: https://www.newyorkfed.org/medialibrary/media/markets/pridealers_historical.xls (verified 200, 2026-05 — direct download)
- Parse into `data/raw/nyfed/primary_dealers.csv` with columns: `dealer_name`, `start_date`, `end_date`.

### 2b. CRSP-Compustat via WRDS (the wrds Python library)
For each PERMNO appearing in the mapping (Step 3) and for each comparison universe:

- **CRSP monthly** (`crsp.msf` joined to `crsp.msenames`): PERMNO, date, PRC, SHROUT, EXCHCD, SICCD, NAMECO. Filter to US common stocks (SHRCD ∈ {10, 11}).
- **CRSP daily** (`crsp.dsf`) for VW index returns 1962–2012 — used for realized market volatility in Table 3.
- **Compustat quarterly fundamentals** (`comp.fundq`): GVKEY, datadate, atq (total assets), ceqq (common equity), dlcq + dlttq (debt — or compute as `atq - ceqq` per the paper's `AT - CEQ` definition of book debt).
- **CRSP-Compustat link** (`crsp.ccmxpf_linktable`): map PERMNO ↔ GVKEY with valid linkdt/linkenddt and linktype ∈ {'LC','LU','LS'}, linkprim ∈ {'P','C'}.

Save as parquet under `data/raw/wrds/`. Cache by PERMNO list so reruns are cheap.

### 2c. FRED series (via `fredapi`)
| Purpose | FRED series ID | Status |
|---|---|---|
| Z.1 broker-dealer financial assets (level, $M, NSA, quarterly, 1945Q4+) | `BOGZ1FL664090005Q` | Verified 2026-05 |
| Z.1 broker-dealer total liabilities (level, $M, NSA, quarterly) | `BOGZ1FL664190005Q` | Verified 2026-05 |
| Chicago Fed NFCI (weekly → quarter-end value) | `NFCI` | Verified |
| Civilian unemployment rate (monthly → quarterly avg) | `UNRATE` | Verified |
| Real GDP, chained $ (quarterly) | `GDPC1` | Verified |

Fallback if any FRED series returns empty: direct CSV download from federalreserve.gov/datadownload (Z.1) and bls.gov (UNRATE).

### 2d. Ken French data library
- **F-F Research Factors** (Mkt-RF and RF, monthly): https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip
- Build quarterly market excess return as compounded monthly Mkt-RF.

### 2e. Robert Shiller aggregate E/P
- **URL** (HTTP, not HTTPS — HTTPS times out): http://www.econ.yale.edu/~shiller/data/ie_data.xls (verified 200, 2026-05)
- Use the **12-month trailing earnings yield** = 1 / (column "P/E", which is trailing-12-mo S&P 500 P/E). Do **NOT** use 1/CAPE.
- Quarter-end value of E/P → Panel A level for "E/P" row.
- Log change of quarterly E/P → Panel B "E/P growth" row.
- If shillerdata.com migration breaks the Yale URL, fall back to scraping the current download link from https://shillerdata.com/ landing page.

### 2f. Zhiguo He bundled HKM data (validation reference)
- https://zhiguohe.net/data-and-empirical-patterns/intermediary-capital-ratio-and-risk-factor/ (verified 200, 2026-05)
- Files: `He_Kelly_Manela_Factors_monthly_YYMMDD.csv`, `He_Kelly_Manela_Factors_quarterly_YYMMDD.csv` (suffix = update date, e.g. `_250627` as of June 2025). Agent should scrape the page for the latest filename rather than hardcoding.
- Used ONLY in `validation.py` to compare our reconstructed series against the published series.
- **Expected correlations** (US-only reconstruction vs published all-PD series — adjusted downward because Datastream not available):
  - `market_cap_ratio` (US-only) vs bundled `intermediary_capital_ratio`: expect ~0.85–0.95 (foreign PDs contribute substantial market cap, so correlation will be lower than the 0.98 a perfect reconstruction would hit).
  - `market_capital_factor` (US-only) vs bundled `intermediary_capital_risk_factor`: expect ~0.80–0.90.
  - If correlation < 0.75, mapping is probably broken — surface to user.

## Step 3 — Primary-dealer-to-PERMNO entity map (the hard part)

This is the central engineering risk. The agent must produce `data/pd_to_permno_map.csv` with columns:

```
dealer_name, parent_holdco_name, permno, gvkey,
start_date, end_date, confidence, notes
```

**Procedure**:
1. Take each unique `dealer_name` from `data/raw/nyfed/primary_dealers.csv`.
2. For each, identify the publicly traded **US** holding company that owned the dealer at the time. Examples: "Salomon Brothers" → "Salomon Inc." → (1997) "Travelers Group" → (1998) "Citigroup"; "Bear Stearns & Co." → "Bear Stearns Companies" → (Mar 2008) JPMorgan Chase.
3. Search CRSP by company name (`crsp.msenames.NAMECO`) for matching PERMNOs over the relevant date range.
4. For each PERMNO, confirm it has a valid Compustat link.
5. For dealers that were subsidiaries of foreign banks (Deutsche Bank, UBS, Nomura, etc.), mark `confidence = "foreign_excluded"` — Table 2 restricts to US-based holding companies.
6. For dealers that went private/bankrupt (Lehman post-2008), set `end_date` accordingly.
7. For periods when a dealer's holding company is itself a primary dealer (e.g., post-merger consolidation), avoid double-counting by setting `parent_holdco_name` and aggregating at the parent level.

**Confidence levels**:
- `high` — unambiguous CRSP name match with continuous coverage
- `medium` — name match required manual disambiguation across mergers
- `low` — best guess, no clean CRSP match (e.g., dealer was a non-listed subsidiary)
- `foreign_excluded` — non-US parent

**Deliverable**: agent commits the file with all rows populated, flagging `low` rows in the script logs so the user can review and edit. Do not silently drop unmatched dealers.

## Step 4 — Build the firm panel

`src/hkm/build_pd_panel.py`:
- For each PERMNO in the mapping (excluding `foreign_excluded` and `low`-confidence rows that user hasn't approved), build a monthly panel of:
  - `market_equity = |PRC| × SHROUT / 1000` (in $M)
  - `book_equity = ceqq` — **point-in-time, NOT lagged** (paper uses calendar-aligned book values). Assign `datadate` to the calendar quarter containing it, then ffill within quarter to fill non-end-of-quarter months.
  - `total_assets = atq`
  - `book_debt = atq - ceqq` (paper's definition: `AT - CEQ`)
- **Multi-share-class firms**: aggregate to PERMCO before summing — sum `market_equity` across PERMNOs that share a PERMCO, then use one row per PERMCO-month.
- Aggregate to the **parent holdco** level by `parent_holdco_name` per month (sum across PERMCOs owned by the same parent at that time).
- Build parallel monthly panels for comparison universes (CRSP-Compustat US firms only):
  - **Broker-dealers**: `SICCD == 6211`
  - **Banks**: `SICCD ∈ [6020, 6029] ∪ {6712}`
  - **Compustat-all**: all US CRSP-Compustat firms with non-missing `atq`, `ceqq`
- **Denominator handling for Table 2** (user-decided): The denominator for each comparison group is `(SIC-defined comparison group) ∪ (PD parents)`. That is, primary dealer parent firms are added to the denominator even when their SIC is not in the comparison group (e.g., Citigroup as a bank-holdco is added to the broker-dealer denominator). This ensures ratios ≤ 1 and matches the published table magnitudes.
- Save as `data/processed/firm_panel_monthly.parquet` (one row per PERMCO-month) and aggregated `data/processed/group_aggregates_monthly.parquet` (one row per group-month with summed assets / debt / equity / market_eq). The aggregated file has **6 group rows per month**: `pd`, `bd_only`, `bd_union_pd`, `banks_only`, `banks_union_pd`, `cmpust_union_pd`.

## Step 5 — Construct headline series

`src/hkm/build_capital_ratios.py`:
- `market_capital_ratio_t = Σ market_equity_t / (Σ market_equity_t + Σ book_debt_t)` summed across PD holding companies
- `book_capital_ratio_t = Σ book_equity_t / (Σ book_equity_t + Σ book_debt_t)` summed across PD holding companies
- Aggregate to quarter using end-of-quarter values (the paper uses end-of-period).
- Output: `data/processed/capital_ratios_quarterly.parquet` with columns `date_q, market_cap_ratio, book_cap_ratio`.

`src/hkm/build_aem_leverage.py`:
- Pull `BOGZ1FL664090005Q` (assets) and `BOGZ1FL664190005Q` (liabilities) from FRED, quarterly.
- `aem_leverage_t = financial_assets_t / (financial_assets_t - total_liabilities_t)` — this is the **leverage ratio** (assets-to-equity).
- `aem_implied_capital_t = 1 / aem_leverage_t = (financial_assets_t - total_liabilities_t) / financial_assets_t` — this is the **capital ratio** (equity-to-assets). **This is the series HKM uses in Table 3 Panel A as the row labelled "AEM leverage".** The paper's wording ("AEM implied capital is the inverse of broker-dealer book leverage") together with the +0.42 sign of corr(Market cap, AEM) in your pasted Table 3 confirm that the Panel A row is the capital ratio, NOT the leverage ratio. Earlier draft of this plan had this backwards.
- **AEM factor** (Panel B row "AEM leverage factor"): seasonally-adjusted log growth of `aem_leverage_t` (NOT of `aem_implied_capital_t` — Panel B uses the original AEM 2014 leverage factor). Seasonal adjustment per user decision: **quarter-dummy residuals**. Procedure:
  1. Compute `lev_t = log(aem_leverage_t)`.
  2. Regress `lev_t` on quarter dummies (Q1–Q4) over the full sample.
  3. Take residuals → seasonally-adjusted log leverage.
  4. First-difference → `aem_factor_t`.
- Output: `data/processed/aem_quarterly.parquet` with columns `date_q, aem_leverage, aem_implied_capital, aem_factor`.

`src/hkm/build_factors.py`:
- `market_capital_factor_t = ε_t / market_cap_ratio_{t-1}`, where ε_t is the AR(1) residual of `market_cap_ratio_t`.
- Same construction for `book_capital_factor`.
- Output: `data/processed/factors_quarterly.parquet`.

`src/hkm/build_macro_panel.py` — build BOTH level and growth versions of every macro series (Panel A uses levels, Panel B uses log changes):

| Variable | Level (Panel A) | Growth (Panel B) | Source |
|---|---|---|---|
| Market excess return | — | `mkt_xret_q` = compounded monthly Mkt-RF | Ken French |
| E/P | `ep_q` = quarter-end 1/(Shiller 12-mo trailing P/E) | `ep_growth_q` = log change of `ep_q` | Shiller ie_data.xls |
| Unemployment | `unemp_q` = quarterly average UNRATE | `unemp_growth_q` = log change of `unemp_q` | FRED `UNRATE` |
| GDP | `gdp_q` = `GDPC1` level | `gdp_growth_q` = log change of `gdp_q` | FRED `GDPC1` |
| Financial conditions | `nfci_q` = quarter-end NFCI | `nfci_growth_q` = log change of `nfci_q` | FRED `NFCI` |
| Market volatility | `mkt_vol_q` = realized vol of CRSP VW daily within quarter | `mkt_vol_growth_q` = log change of `mkt_vol_q` | CRSP `dsf` |

- Realized vol formula: `mkt_vol_q = sqrt( Σ_d (r_d - r̄)^2 )` over the quarter's daily CRSP VW excess returns; NOT annualized (correlations are scale-invariant).
- NFCI growth: NFCI is mean-zero by construction so `log` is undefined for negative values — for Panel B's "Financial conditions growth" row, use **simple first difference** of NFCI instead of log change. Document this deviation in the validation report.
- Output: `data/processed/macro_panel_quarterly.parquet` with both `*_q` and `*_growth_q` columns.

## Step 6 — Table 2

`src/hkm/table2.py`:
1. Load `group_aggregates_monthly.parquet`.
2. For each month, for each of {total_assets, book_debt, book_equity, market_equity}:
   - `ratio_BD_t = pd_sum_t / bd_union_pd_sum_t`
   - `ratio_Banks_t = pd_sum_t / banks_union_pd_sum_t`
   - `ratio_Cmpust_t = pd_sum_t / cmpust_union_pd_sum_t`
   - (Denominators are union groups per Step 4's decision.)
3. For each of the three periods (1960–2012, 1960–1990, 1990–2012), compute the time-series average of each ratio across all months in the period.
4. Emit a 3-row × 12-column table matching the paper's layout.
5. Write `tables/table_2.csv` and `tables/table_2.tex` (use `jinja2` template that matches HKM's column grouping with `\multicolumn{3}{c}{Total assets}` etc.).

**Validation**: compare to user-pasted values:
```
1960-2012 row: 0.959 0.596 0.240 | 0.960 0.602 0.280 | 0.939 0.514 0.079 | 0.911 0.435 0.026
1960-1990 row: 0.997 0.635 0.266 | 0.998 0.639 0.305 | 0.988 0.568 0.095 | 0.961 0.447 0.015
1990-2012 row: 0.914 0.543 0.202 | 0.916 0.550 0.240 | 0.883 0.444 0.058 | 0.848 0.419 0.039
```
Log abs-difference per cell; flag any cell with |diff| > 0.02 as a probable mapping issue.

## Step 7 — Table 3

`src/hkm/table3.py`:
1. Load `capital_ratios_quarterly`, `aem_quarterly`, `factors_quarterly`, `macro_panel_quarterly`. Restrict to 1970Q1–2012Q4.

2. **Panel A — Correlations of levels**: 3×3 lower triangle of (Market capital, Book capital, AEM **implied capital**), plus 5×3 of (E/P, Unemployment, GDP, Financial conditions, Market volatility) × (the three ratios). Use raw levels.
   - NOTE: Panel A's "AEM leverage" row uses `aem_implied_capital` (1/leverage), NOT `aem_leverage`. See Step 5's AEM section.

3. **Panel B — Correlations of factors**: 3×3 lower triangle of (Market capital factor, Book capital factor, AEM **leverage factor**), plus 6×3 of (Market excess return, E/P growth, Unemployment growth, GDP growth, Financial conditions growth, Market volatility growth) × (the three factors).
   - NOTE: Panel B's "AEM leverage factor" uses `aem_factor` (SA log growth of leverage), NOT 1/leverage growth.

4. Emit `tables/table_3.csv` (one row per cell with `panel`, `row_label`, `col_label`, `corr`) and `tables/table_3.tex` (formatted Panel A + Panel B).

**Expected divergence from published Table 3**: Because the reconstruction uses US-only PDs (no Datastream), Market capital and Book capital correlations will differ from the published values. Direction and rough magnitude of divergence:
- Diagonal correlations (which-vs-self) will be 1.00 trivially.
- Off-diagonals involving Market capital — expected within ±0.10 of paper (foreign PDs shift the magnitudes but not signs).
- Macro vs Market capital — likely within ±0.10. The −0.83 target for corr(Market cap, E/P) may come in as −0.70 to −0.85.
- Book capital row — least confident; foreign PDs (esp. Deutsche Bank, UBS) have very different book/market ratios than US PDs.

**Validation targets** (from user-pasted content) — use these to gate the pipeline:
- Panel A: corr(Market cap, Book cap) = 0.50; corr(Market cap, AEM) = 0.42; corr(Book cap, AEM) = −0.07
- Panel A: corr(Market cap, E/P) = −0.83; corr(Market cap, NFCI) = −0.48
- Panel B: corr(Market cap factor, Market excess return) = 0.78; corr(Market cap factor, E/P growth) = −0.75; corr(Market cap factor, mkt vol growth) = −0.49

Log abs-difference per cell; flag any cell with |diff| > 0.05 as a probable construction issue.

## Step 8 — Validation (`scripts/99_validate.py`)

1. **Mapping coverage**: print count of PD entities with `confidence ∈ {high, medium}` per decade. Expect ≥ 10 in every decade after 1970.
2. **Capital ratio cross-check vs published**: load Zhiguo He's bundled `He_Kelly_Manela_Factors_quarterly_YYMMDD.csv`, align on `date_q`, compute correlation of our `market_cap_ratio` (US-only) vs bundled `intermediary_capital_ratio` (all-PD). Expected range 0.85–0.95 because of US-only restriction (no Datastream). If correlation < 0.75, mapping is probably broken — surface to user.
3. **Factor cross-check vs published**: same for `market_capital_factor` vs bundled `intermediary_capital_risk_factor`. Expected range 0.80–0.90.
4. **Table 2 cell-by-cell** vs the user-pasted target values (Step 6). Flag |diff| > 0.02 — Table 2 should match closely because it's US-only by construction in both our work and the paper.
5. **Table 3 cell-by-cell** vs the user-pasted target values (Step 7). Tolerance is wider: flag |diff| > 0.10 (expected divergence due to no-Datastream caveat). For each cell, log the absolute difference and the published value side-by-side.
6. Emit `logs/validation_report.md` summarizing all checks with pass/fail bucket: GREEN (within tolerance), YELLOW (within 2× tolerance), RED (outside).

## Step 9 — Verification (how user can confirm it worked)

Run end-to-end:
```bash
cd ~/hkm-replication
python scripts/00_setup.py            # WRDS conn, FRED key, dirs OK
python scripts/01_fetch_all.py        # ~10-30 min depending on WRDS
python scripts/02_build_pd_panel.py   # ~2-5 min
python scripts/03_build_series.py     # <1 min
python scripts/04_table2.py           # produces tables/table_2.{csv,tex}
python scripts/05_table3.py           # produces tables/table_3.{csv,tex}
python scripts/99_validate.py         # prints PASS/FAIL summary
```

Visual checks:
- Open `tables/table_2.csv` — confirm 3 rows × 12 cols, numbers within ±0.02 of user-pasted targets.
- Open `tables/table_3.csv` — confirm Panel A and Panel B blocks, target cells listed in Step 7 match within ±0.05.
- Open `logs/validation_report.md` — all checks should be PASS.
- Render `tables/table_2.tex` and `tables/table_3.tex` with `pdflatex` and compare visually to the paper PDF.

## Key risks & mitigations

| Risk | Mitigation |
|---|---|
| PD-to-PERMNO mapping diverges from HKM's choices | Validate against Zhiguo He's bundled `intermediary_capital_ratio` series; correlation < 0.98 means rerun mapping with user review |
| FRED Z.1 series IDs may have changed | Cross-check series description; fall back to federalreserve.gov/datadownload direct CSV |
| NY Fed historical PD list URL may break | Wayback Machine fallback; HKM Online Appendix Table A.1 lists the dealer set explicitly (extract from paper if available) |
| Treatment of foreign-owned dealers (Deutsche Bank, UBS, Nomura, Credit Suisse) | Paper restricts to US-based holdcos in Table 2; exclude in `confidence = "foreign_excluded"`. For Table 3 ratios HKM does include foreign in the market_capital_ratio construction per the paper — confirm in the paper text and split the panel into two sets if needed |
| Compustat book debt definition | Paper explicitly defines `book_debt = AT - CEQ`. Use that. Do NOT use `dlcq + dlttq` even though it's the textbook book-debt measure |
| AR(1) innovation construction differences | Paper's factor formula: ε_t / X_{t-1}. Confirm sign convention against bundled series |
| Seasonal adjustment of AEM growth rate | Use X-13ARIMA-SEATS via `statsmodels.tsa.x13`; if not installed, fall back to seasonal-mean-removal and document deviation |
| `notebooks/results_walkthrough.ipynb` is OPTIONAL | Skip if running over budget; CSV + LaTeX are the contractual deliverables |

## Reference URLs

- Paper PDF (JFE version): https://bfi.uchicago.edu/wp-content/uploads/jfepublishedversion.pdf
- Paper PDF (MFM version, user's link): https://mfm.uchicago.edu/wp-content/uploads/2020/07/He-et-al_Intermediary-asset-pricing-New-evidence-from-many-asset-classes.pdf
- NBER WP w21920: https://www.nber.org/papers/w21920
- Zhiguo He data page: https://zhiguohe.net/data-and-empirical-patterns/intermediary-capital-ratio-and-risk-factor/
- Asaf Manela data page (may 403 from non-browser clients): https://asaf.manela.org/data/
- Existing Julia replication (asset pricing tests, not Tables 2/3): https://github.com/inkydragon/He-Kelly-Manela-2017-JFE
- NY Fed primary dealers: https://www.newyorkfed.org/markets/primarydealers
- FRED: https://fred.stlouisfed.org/
- Ken French data library: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- Shiller data: http://www.econ.yale.edu/~shiller/data.htm

## Open questions for executing agent

If during execution any of the following come up, **pause and surface to user** rather than guess:

1. PD mapping rows with `confidence = "low"` — show the user the list and ask for guidance.
2. If Z.1 FRED series return unexpectedly short ranges or zeros — confirm series ID before falling back to federalreserve.gov direct download.
3. If correlation with bundled HKM `intermediary_capital_ratio` < 0.75 — surface; do NOT silently patch mapping.
4. If Table 2 row-1 cell deviations > 0.05 from targets — this implies a denominator-definition issue (Step 4), surface before computing the other panels.

## Decisions already locked in (do not re-litigate)

These were resolved during planning — agent should follow without re-asking:

- **Foreign PDs**: US-only reconstruction; accept Table 3 divergence from published values. Datastream not in scope.
- **Table 2 denominators**: comparison group ∪ PD parents (so ratios ≤ 1).
- **Compustat reporting lag**: point-in-time, no lag.
- **E/P series**: 1 / (Shiller 12-month trailing P/E). Not CAPE.
- **AEM seasonal adjustment**: quarter-dummy residuals, then first difference.
- **AEM Panel A row**: implied capital (1/leverage), NOT leverage. Panel B row: leverage factor (SA log growth of leverage).
- **Output**: LaTeX + CSV. Notebook optional.
- **Cross-check FF25/Treasuries via WRDS**: dropped from scope (Tables 2/3 don't use those portfolios).

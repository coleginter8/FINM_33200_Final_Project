# Request — run-20260520-hkm-tables-2-3

## Request Summary

Replicate Tables 2 and 3 only from He, Kelly & Manela (2017), "Intermediary Asset Pricing: New Evidence from Many Asset Classes," *Journal of Financial Economics* 126: 1–35.

## Source Material

- Paper PDF: `/Users/gregoryginter/Desktop/UChicago MSFM/FINM 33200/Final Project/HKM Replication/hkm-paper.pdf`
- Target repo: coleginter8/hkm-replication
- Workspace repo: coleginter8/workspace
- WRDS credentials: `~/.pgpass` (username: coleginter)

## Scope

Implement a Python package (`hkm/`) that produces:

1. **Table 2** — Average sizes of primary dealers relative to three comparison groups (all broker-dealers [BD], all banks [Banks], all Compustat firms [Cmpust]), across four balance-sheet items (Total assets, Book debt, Book equity, Market equity) and three time periods (1960–2012, 1960–1990, 1990–2012). Monthly data; US-based primary dealers only; holding companies in CRSP-Compustat.

2. **Table 3** — Pairwise time-series correlations (1970Q1–2012Q4):
   - Panel A: Levels of Market capital ratio, Book capital ratio, AEM leverage vs macro variables (E/P, Unemployment, GDP, Financial conditions, Market volatility)
   - Panel B: Factors (AR(1) innovations scaled by lagged ratio) of the same three series vs macro variables in growth rates

## Published Target Values

### Table 2

| Period     | TA/BD | TA/Banks | TA/Cmpust | BD/BD | BD/Banks | BD/Cmpust | BE/BD | BE/Banks | BE/Cmpust | ME/BD | ME/Banks | ME/Cmpust |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1960–2012  | 0.959 | 0.596 | 0.240 | 0.960 | 0.602 | 0.280 | 0.939 | 0.514 | 0.079 | 0.911 | 0.435 | 0.026 |
| 1960–1990  | 0.967 | 0.635 | 0.286 | 0.998 | 0.639 | 0.305 | 0.961 | 0.568 | 0.095 | 0.961 | 0.447 | 0.015 |
| 1990–2012  | 0.914 | 0.543 | 0.202 | 0.916 | 0.550 | 0.240 | 0.883 | 0.444 | 0.058 | 0.848 | 0.419 | 0.039 |

### Table 3 — Panel A (Correlations of levels)

|  | Market capital | Book capital | AEM leverage |
|---|---|---|---|
| Market capital | 1.00 | 0.50 | −0.42 |
| Book capital | — | 1.00 | −0.07 |
| AEM leverage | — | — | 1.00 |
| E/P | −0.83 | −0.38 | −0.64 |
| Unemployment | −0.63 | −0.10 | −0.33 |
| GDP | 0.18 | 0.32 | −0.23 |
| Financial conditions | −0.48 | −0.53 | −0.19 |
| Market volatility | −0.06 | −0.31 | 0.33 |

### Table 3 — Panel B (Correlations of factors)

|  | Mkt capital factor | Book capital factor | AEM leverage factor |
|---|---|---|---|
| Mkt capital factor | 1.00 | 0.30 | 0.14 |
| Book capital factor | — | 1.00 | −0.06 |
| AEM leverage factor | — | — | 1.00 |
| Market excess return | 0.78 | 0.10 | 0.15 |
| E/P growth | −0.75 | −0.10 | −0.18 |
| Unemployment growth | −0.05 | 0.12 | −0.08 |
| GDP growth | 0.20 | 0.09 | 0.04 |
| Financial conditions growth | −0.38 | −0.29 | −0.06 |
| Market volatility growth | −0.49 | −0.18 | −0.08 |

## Acceptance Criteria

1. `compute_table2()` returns a DataFrame matching shape (3, 12) with values within ±0.05 of published numbers for cells derivable from WRDS+CRSP (1960–2012 coverage may be partial)
2. `compute_table3()` returns (panel_a, panel_b) with correlation values within ±0.05 of published numbers for the 1970Q1–2012Q4 period
3. All tests pass: `pytest --tb=short`
4. Zero ruff errors: `ruff check hkm/`
5. Zero mypy errors: `mypy hkm/ --strict`

## Workflow

Workflow 2 (Code + Ship): planner → builder → tester → scriber → reviewer → shipper

## Context Notes

- Previous run (run-20260515-124030): PASS WITH NOTE — 71 tests skipped due to WRDS 1978Q1 start gap vs paper's 1970Q1
- Fresh replication: repo reset to scaffold (9871b28), workspace cleared
- evaluation.md (untracked in repo) tracks cell-by-cell comparison; update it with actual vs published values
- For Table 3, AEM leverage comes from the Fed Flow of Funds (public data), not WRDS
- Book debt = AT − CEQ (total assets minus common equity)
- Market equity = shares outstanding × price (from CRSP, monthly)
- η_t = Σ_i ME_{i,t} / Σ_i (ME_{i,t} + BD_{i,t}) using quarterly Compustat debt + CRSP equity
- Capital ratio factor = AR(1) innovations in η_t, scaled by lagged η_t (AR(1) ρ ≈ 0.94)
- Comparison groups for Table 2: BD = SIC 6211+6221, Banks = SIC 6000–6299, Cmpust = all Compustat

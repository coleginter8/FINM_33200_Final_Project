# Impact — run-20260520-hkm-tables-2-3

## Target Repository State

- Repo: coleginter8/hkm-replication
- Current commit: 9871b28 (Initial scaffold — bare package for HKM replication)
- Scaffold contents: `.gitignore`, `pyproject.toml`, `.env.example`
- Status: greenfield — no source files exist yet

## What Must Be Built

The entire Python package `hkm/` must be created from scratch on top of the scaffold.

### Write Surface (all new files)

```
hkm/
├── __init__.py
├── utils.py                      # shared helpers (logging, db connection)
├── data/
│   ├── __init__.py
│   ├── wrds_connect.py           # psycopg2 connection via ~/.pgpass
│   ├── compustat.py              # quarterly balance sheet: AT, CEQ (book debt = AT - CEQ)
│   ├── crsp.py                   # monthly CRSP: ME = prc × shrout; SIC codes
│   ├── dealers.py                # primary dealer name→GVKEY/PERMNO mapping (Table A.1)
│   ├── intermediary.py           # η_t = Σ ME / Σ (ME + BD); AR(1) factor
│   └── macro.py                  # FRED: UNRATE, GDPC1, NFCI; Shiller E/P; CRSP vol
├── tables/
│   ├── __init__.py
│   ├── table2.py                 # compute_table2() → (3, 12) DataFrame
│   └── table3.py                 # compute_table3() → (panel_a, panel_b) DataFrames
tests/
├── __init__.py
├── test_data.py                  # unit tests for data modules
└── test_tables.py                # unit + integration tests for table outputs
README.md
ARCHITECTURE.md
```

## Key Algorithms

### η_t (primary dealer capital ratio)
```
η_t = Σ_i Market_Equity_{i,t} / Σ_i (Market_Equity_{i,t} + Book_Debt_{i,t})
Book_Debt = AT - CEQ  (Compustat quarterly: at − ceq)
Market_Equity = prc × shrout  (CRSP monthly, last day of quarter)
```

### Capital ratio factor (for Table 3)
```
Fit AR(1): η_t = ρ₀ + ρ η_{t-1} + u_t   (ρ ≈ 0.94 per paper)
Factor = u_t / η_{t-1}   (innovation scaled by lagged ratio)
```

### Table 2 ratio
```
For each quarter t, each balance-sheet item X, each comparison group G:
  ratio_t = Σ_{i ∈ dealers} X_{i,t} / Σ_{j ∈ G} X_{j,t}
Time-series mean of ratio_t over each sub-period
```

## Data Sources

| Data | Source | Access |
|---|---|---|
| Primary dealer balance sheets | WRDS Compustat (comp.fundq: at, ceq) | psycopg2 |
| Primary dealer market equity | WRDS CRSP (crsp.msf: prc, shrout) | psycopg2 |
| Comparison group (BD, Banks, all) | WRDS Compustat/CRSP (SIC codes) | psycopg2 |
| AEM leverage | Fed Flow of Funds Z.1 (public) | pandas-datareader or FRED API |
| E/P ratio | Shiller data (public CSV) | requests |
| Unemployment, GDP | FRED | pandas-datareader |
| NFCI | Federal Reserve Bank of Chicago (public CSV) | requests |
| Market excess return | CRSP value-weighted index + T-bill | WRDS CRSP |
| Market volatility | CRSP realized vol (daily) | WRDS CRSP |

## Primary Dealer Universe (for η_t and Table 2)

From Table A.1 of the paper. US-based firms only that appear in CRSP-Compustat. Key firms:
- Goldman Sachs (GVKEY: 011251), Bear Stearns, Lehman Brothers, Merrill Lynch
- Morgan Stanley, Salomon Brothers, First Boston, Kidder Peabody
- JP Morgan, Citigroup, Bank of America, Chemical Bank, Manufacturers Hanover
- Drexel Burnham, Paine Webber, Dean Witter Reynolds, Prudential-Bache
- All with start/end dates from Table A.1 for time-varying dealer composition

Foreign dealers (Barclays, Deutsche Bank, UBS, BNP, etc.) use Datastream — for this replication focus on US dealers from CRSP-Compustat only (consistent with paper's Table 2 note).

## Sample Periods

| Table | Period | Frequency | Source |
|---|---|---|---|
| Table 2 | 1960M01–2012M12 | Monthly (Compustat annual/quarterly spliced) | CRSP + Compustat |
| Table 3 η levels | 1970Q1–2012Q4 | Quarterly | CRSP + Compustat |
| Table 3 macro | 1970Q1–2012Q4 | Quarterly | FRED + Shiller + CRSP |

## Risk Areas

1. **Data availability 1960–1977**: Compustat quarterly goes back to ~1960 but coverage is sparse; CRSP goes to 1926. Match by GVKEY/PERMNO from Table A.1 names. If WRDS coverage starts later, document gap.
2. **Book debt definition**: Paper says `AT − CEQ` (total assets minus common equity). Must use quarterly Compustat, not annual.
3. **AEM leverage**: From Fed Z.1 Flow of Funds, not WRDS. Must fetch from public source.
4. **Time-varying dealer composition**: Dealers enter/exit per Table A.1 dates. Must filter by quarter.
5. **Comparison group SIC codes**: BD = 6211 or 6221. Banks: exact definition (6000–6299 is broad; may need narrower per paper).
6. **AR(1) estimation**: OLS on full sample 1970Q1–2012Q4 for factor construction.
7. **Macro correlations**: Log changes for growth rates (ln(x_t) - ln(x_{t-1})). Market excess return = CRSP value-weighted return - T-bill rate.

## Profile

`python-package`

## Teammate Plan

| Teammate | Task |
|---|---|
| planner | Deeply read paper PDF; produce spec.md (algorithms, data pipeline, exact formulas), test-spec.md (acceptance tests with published target values), comprehension.md |
| builder | Implement hkm/ package from spec.md; connect to WRDS; produce implementation.md |
| tester | Run pytest, ruff, mypy from test-spec.md; produce audit.md |
| scriber | Write ARCHITECTURE.md, log-entry.md, docs.md |
| reviewer | Cross-check all artifacts; produce review.md |
| shipper | git commit, git push to coleginter8/hkm-replication; sync workspace |

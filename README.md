# Comparative Effectiveness of StatsClaw and Base Claude Code on Financial Research Replications

**Authors:** Charlie Carvajal, Cole Ginter, Jonathon Nie, Alex Nikolaev  
**Course:** FINM 33200 — Generative and Agentic AI for Finance, University of Chicago

---

## Overview

This project evaluates two AI-driven replication approaches — the StatsClaw multi-agent framework and base Claude Code in plan mode — on three financial research replication tasks of increasing difficulty. Contrary to expectations, StatsClaw outperformed base Claude on the easy case but underperformed on both the medium and hard cases, suggesting its value may be conditional on task complexity.

---

## Key Findings

| Case | Difficulty | Papers | StatsClaw | Base Claude | Winner |
|---|---|---|---|---|---|
| GSW Federal Yield Curve | Easy | Gürkaynak, Sack & Wright (2007) | Exact match — all 9 tests pass, 379,352 rows, max diff = 0.000000, ~33 min, ~432K tokens | Correct yields via full Svensson re-estimation; 1–2 bp irreducible error vs Fed file | **StatsClaw** |
| CDS Portfolio Returns | Medium | He, Kelly & Manela (2017); Palhares (2013) | Correct formula; 3Y_Q1 r = 0.976; violated HOLD on discount curve; missed Fed/FRED data sources | Surfaced discount curve ambiguity; 97.4% contracts within 5% of oracle; identified all 3 data sources | **Base Claude** |
| HKM Tables 2 & 3 | Hard | He, Kelly & Manela (2017) | Wrong GVKEYs (subsidiary instead of holding company); no documentation; hallucinated codes — complete failure | 86-row dealer map with confidence flags; market_capital_ratio r = 0.96 vs published He series | **Base Claude** |

---

## Repository Structure

```
FINM_33200_Final_Project/
├── GSW Replication StatsClaw/      StatsClaw run — exact match (9/9 tests, 379,352 rows)
├── GSW Replication Vanila Claude/  Base Claude run — full Svensson re-estimation approach
├── CDS Replication StatsClaw/      StatsClaw run — correct formula, violated HOLD instruction
├── CDS Replication Vanila Claude/  Base Claude run — better methodology, 97.4% contract match
├── HKM Replication StatsClaw/      StatsClaw run — complete failure (wrong GVKEYs)
├── HKM Replication Vanila Claude/  Base Claude run — 86-row dealer map, r=0.96 capital ratio
├── statsclaw/                      StatsClaw framework source (agents, skills, profiles, templates)
├── FINM 33200 Final Project Report (1).pdf   Full 18-page report
└── requirements.txt
```

---

## StatsClaw Overview

StatsClaw is a workflow framework for Claude Code distributed as a public GitHub repository. Rather than a separate model or API, it configures Claude Code to operate as a coordinated team of specialized agents: a leader, planner, builder, tester, scriber, reviewer, and shipper. The central mechanism is adversarial verification — the builder produces results that must pass tests independently created by the tester. The planner reads source papers and produces `spec.md` (the builder's implementation spec) and `test-spec.md` (the tester's validation spec), which are kept strictly isolated from each other. For these financial replications, real data replaced simulated data, reducing the adversarial verification loop from three independent checks to two.

---

## Methodology

Both StatsClaw and base Claude replications were run on **separate Claude accounts** to prevent data contamination via conversation memory, past-chat search, or user-preference features. Base Claude used plan mode, forcing a complete methodology document before any code was generated. Each framework operated independently with no user guidance during execution. The evaluation combined a quantitative check (how closely do numbers match the oracle?) with a qualitative audit (what assumptions and decisions were made silently versus transparently?).

---

## Case Details

### Case 1 — GSW Federal Yield Curve (Easy)

**Papers:** Gürkaynak, Sack & Wright (2007)  
**Target:** Reproduce the zero-coupon Treasury yield curve dataset from the [`ftsfr/fed_yield_curve`](https://github.com/ftsfr/fed_yield_curve) repository.  
**Key test:** Would the framework recognize that the Federal Reserve already publishes the fitted curve as a downloadable CSV (FEDS200628) rather than re-estimating the Svensson model from bond prices?

- **StatsClaw:** Identified FEDS200628 immediately, downloaded and reshaped the data — exact match against oracle on all 9 validation tests. Delivered less code, no synthetic bond dependency, and an irreducible error of 0.000000.
- **Base Claude:** Reimplemented the full Svensson estimation pipeline from Treasury Fiscal Data API bond prices. Produced yields within 1–2 bp of the Fed file on the zero curve and up to ~13 bp on the 30-year forward — substantively correct but with irreducible error relative to the published series.

---

### Case 2 — CDS Portfolio Returns (Medium)

**Papers:** He, Kelly & Manela (2017); Palhares (2013)  
**Target:** Reproduce two monthly parquet files from [`ftsfr/cds_returns`](https://github.com/ftsfr/cds_returns): 20 sorted portfolios (4 tenors × 5 spread quintiles) and individual contract returns.  
**Data sources required:** WRDS Markit CDS, Federal Reserve zero-coupon yields, FRED short-term Treasury yields.  
**Return formula:** r_t = S_{t-1}/12 + (S_{t-1} − S_t) × RD_{t-1}

**StatsClaw:**
- Correctly identified the Palhares (2013) protection-seller formula and achieved 100% sign match
- 3Y_Q1 portfolio reached r = 0.976 with the oracle — the only portfolio to surpass the 0.90 threshold
- **Failed** to raise a HOLD on the discount curve as instructed, silently assuming zero risk-free rate pre-2008 and Markit's riskypv01 post-2008
- Missed the Federal Reserve and FRED data sources entirely; used only WRDS Markit CDS
- Required 4 builder iterations with relaxed validation thresholds

**Base Claude:**
- Correctly surfaced the discount curve ambiguity as an explicit user decision point before writing any code
- Identified all three required data sources (WRDS Markit CDS, Optionmetrics zero-coupon rates, FRED)
- 97.4% of contract observations fell within 5% of the oracle (r = 0.805 on that subset)
- Failed at portfolio level due to universe mismatch: pulled 4,369 tickers vs oracle's ~1,683, making quintile boundaries unrecoverable without knowing the oracle's membership filter

---

### Case 3 — HKM Tables 2 & 3 (Hard)

**Papers:** He, Kelly & Manela (2017)  
**Target:** Replicate Tables 2 and 3 — primary dealer size ratios vs broker-dealers, banks, and Compustat firms (Table 2); correlations of intermediary capital ratios with macro factors (Table 3).  
**Data sources:** WRDS CRSP, Compustat, Datastream.  
**Key trap:** The NY Fed's primary dealer list names trading subsidiaries (e.g., "Bear, Stearns & Co., Inc."), while the tables require the publicly traded U.S. holding companies that owned them. An exact replication is also impossible due to Compustat data-vintage backfills.

**StatsClaw:**
- Used primary dealer GVKEYs directly instead of holding company GVKEYs, with no documentation of this choice
- Hallucinated GVKEY codes; several errors including end dates preceding start dates
- The way these errors were discovered was through direct inspection of the GVKEYs used — not through any audit document
- **Classified as a complete failure**

**Base Claude:**
- Produced a curated 86-row `pd_to_permno_map.csv` with dealer name, parent holding company, CRSP PERMNO/PERMCO, GVKEY, effective date window, and a confidence flag (high / medium / low / foreign_excluded)
- Cross-checked the reconstructed intermediary capital series against the version published on Zhiguo He's data page: market_capital_ratio r = +0.96 over 176 quarters of overlap
- Table 2 runs systematically high due to a SIC denominator construction flaw locked in during planning
- Table 3 book capital row has a sign reversal, traced to using CEQQ as book equity without adjusting for preferred stock

---

## Conclusion

The results were the opposite of expectations. StatsClaw's adversarial verification loop excels when the hard part of a replication is finding and cleaning already-published data — the planner identifies the right source, the builder fetches it, and independent tester verification catches data errors. For methodologically ambiguous replications, where success depends on sustained transparency about intermediate decisions, base Claude's plan-first approach proved more reliable.

The leading hypothesis for StatsClaw's underperformance on complex tasks is context window overflow: the CDS `spec.md` was approximately 3× and the HKM `spec.md` approximately 6× larger than the GSW one, likely overloading the planner's context window and causing it to miss prompt instructions and hallucinate identifiers. These results suggest that the value of StatsClaw in financial replications is conditional rather than monotonic.

---

## Full Report

See [FINM 33200 Final Project Report (1).pdf](FINM%2033200%20Final%20Project%20Report%20(1).pdf) for the complete 18-page writeup including validation scorecards, methodology comparisons, and per-cell table evaluations.

---

## References

- Gürkaynak, Refet S., Brian Sack, and Jonathan H. Wright. 2007. "The U.S. Treasury Yield Curve: 1961 to the Present." *Journal of Monetary Economics* 54(8): 2291–2304.
- He, Zhiguo, Bryan Kelly, and Asaf Manela. 2017. "Intermediary Asset Pricing: New Evidence from Many Asset Classes." *Journal of Financial Economics* 126(1): 1–35.
- Palhares, Diogo. 2013. "Cash-Flow Maturity and Risk Premia in CDS Markets." PhD diss., University of Chicago. Working paper via AQR Capital Management.
- FTSFR. n.d. *cds_returns*. GitHub repository. https://github.com/ftsfr/cds_returns
- FTSFR. n.d. *fed_yield_curve*. GitHub repository. https://github.com/ftsfr/fed_yield_curve

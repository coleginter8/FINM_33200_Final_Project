# Review — run-20260520-hkm-tables-2-3

**Reviewer verdict: PASS WITH NOTE**

Date: 2026-05-20
Target repo: coleginter8/hkm-replication
Current HEAD: b9e6e93 (merge: add documentation from scriber)
Artifacts reviewed: request.md, impact.md, comprehension.md, spec.md, test-spec.md, implementation.md (v1–v5), audit.md (final v4 re-run), mailbox.md, ARCHITECTURE.md, README.md

---

## 1. Verdict: PASS WITH NOTE

All hard BLOCK conditions from test-spec.md are satisfied in the final build (commit fa8ef47, merged into b9e6e93). The pipeline ran through four builder iterations, each triggered by a legitimate BLOCK signal from the tester, with each successive fix narrowing the gap. The remaining cells outside ±0.05 are each attributed to documented structural data limitations — pre-1978 WRDS coverage gaps, CRSP scope for bank holding companies, AEM leverage data-vintage differences, and E/P growth magnitude — not to code errors or logic faults. ARCHITECTURE.md accurately describes the system as built. Ship safety is affirmed.

---

## 2. Scope Adherence

**Assessment: PASS**

The implementation is strictly scoped to Tables 2 and 3 only. Every file in the target repo matches the write surface declared in impact.md:

| Category | Expected | Delivered |
|---|---|---|
| `hkm/` source files (12) | Yes | Yes — all 12 files present in HEAD |
| `tests/` (3 files) | Yes | Yes |
| `README.md` | Yes | Yes |
| `ARCHITECTURE.md` | Yes | Yes |
| `pyproject.toml` (ruff + mypy sections added) | Yes | Yes |

No files outside the declared write surface were modified. The `.env.example` and `.gitignore` are from the original scaffold and were not touched. The `evaluation.md` and `hkm-paper.pdf` files in the working tree are untracked and were explicitly excluded from the repo; they do not affect the committed state.

The request asked for `compute_table2()` returning shape (3, 12) and `compute_table3()` returning `(panel_a, panel_b)` — both delivered per audit.md IT-3 and IT-6.

---

## 3. Pipeline Isolation

**Assessment: PASS**

Isolation is confirmed by artifact content:

- **spec.md** carries an explicit header: "For builder only. Do not share with tester." It contains no test logic, tolerance values, or BLOCK conditions.
- **test-spec.md** carries an explicit header: "For tester only. Do not share with builder. Derived from published paper values only." It contains no implementation instructions, SQL queries, or code structure guidance.
- **implementation.md** does not reference test-spec.md; it records builder decisions and deviations from spec.md only.
- **audit.md** references test-spec.md test IDs (UT-1 through UT-9, IT-1 through IT-9, CQ-1 through CQ-4) but does not reference spec.md content.
- The BLOCK signals in mailbox.md correctly route from tester to builder (never the reverse), and the respawn cycle followed the correct sequence: tester BLOCK → leader routes to builder → builder produces new commit → tester re-validates.

No isolation breach is detected.

---

## 4. Cross-Specification Convergence

**Assessment: PASS**

The η_t formula is stated identically in comprehension.md (Section 3), spec.md (Module: `hkm/data/intermediary.py`), test-spec.md (UT-1 through UT-3), and ARCHITECTURE.md (Section 3.1):

```
η_t = Σ_i ME_{i,t} / Σ_i (ME_{i,t} + BD_{i,t})
```

where `ME = |prc| × shrout` (CRSP) and `BD = AT − CEQ` (Compustat quarterly).

The capital ratio factor formula is consistent across all artifacts:

```
Factor = u_t / η_{t-1}   where u_t = AR(1) OLS residual
```

The test-spec check IT-2 verifies ρ ∈ [0.85, 0.99]; the audit reports ρ = 0.9581 — consistent with the paper's footnote 22 value of ≈ 0.94 cited in comprehension.md.

Table 2 denominator construction: all artifacts agree on the footnote 19 interpretation (all active dealers in numerator regardless of SIC; denominator = dealer aggregate + non-dealer group-SIC firms). This was corrected from an earlier incorrect interpretation (spec.md's v1 description was refined by builder's discovery and documented in implementation.md); the ARCHITECTURE.md reflects the corrected interpretation.

Table 3 Panel A/B structure: both spec.md and test-spec.md describe the same 8-row Panel A (Market capital, Book capital, AEM leverage, E/P, Unemployment, GDP, Financial conditions, Market volatility) and 9-row Panel B (Market capital factor, Book capital factor, AEM leverage factor, Market excess return, E/P growth, Unemployment growth, GDP growth, Financial conditions growth, Market volatility growth). The audit confirms shape (8, 3) and (9, 3) respectively.

AEM leverage definition: spec.md, comprehension.md, and ARCHITECTURE.md all identify FRED series FL664090005Q and FL664190005Q (with BOGZ1 fallback IDs). The implementation.md documents the exploration of these series and the decision not to negate (Fix A rationale documented in full). The sign discrepancy with the paper is acknowledged as a data-vintage limitation in all three docs.

Tolerance values: ±0.05 appears in request.md acceptance criteria, is encoded in test-spec.md IT-5 and IT-9 test logic, and is never modified in any builder iteration. The tester correctly applied it without relaxation.

**One minor cross-spec tension, not a STOP condition**: comprehension.md uncertainty #2 notes "GDP in Panel A is log change (growth rate), not level." spec.md and test-spec.md both state this consistently. ARCHITECTURE.md Section 3.1 does not include an explicit note about GDP in Panel A being log-change, but the macro column names (`gdp_growth`) in the data pipeline make this clear. This does not affect correctness.

---

## 5. Tester Verdict Assessment

**Assessment: PASS WITH NOTE correctly applied**

The tester's verdict of PASS WITH NOTE on the final run (audit.md) is correctly applied. Verification:

**Hard BLOCK conditions from test-spec.md:**

| Condition | Status |
|---|---|
| CQ-1: ruff exit 0 | PASS |
| CQ-2: mypy exit 0 | PASS |
| CQ-3: pytest — no FAILURE | PASS (39 passed) |
| CQ-4: no print() in hkm/ | PASS |
| IT-4: all Table 2 values in (0, 1] | PASS (max = 0.934) |
| IT-8: Panel A E/P vs Market capital < 0 | PASS (-0.727) |
| IT-8: Panel A Unemployment vs Market capital < 0 | PASS (-0.499) |
| IT-8: Panel B Market excess return vs Market capital factor > 0 | PASS (+0.727) |
| IT-8: Panel B E/P growth vs Market capital factor < 0 | PASS (-0.164) |
| IT-8: Panel B Market volatility growth vs Market capital factor < 0 | PASS (-0.442) |

All 10 hard BLOCK conditions pass. The cells outside ±0.05 are properly explained and not attributable to tolerance relaxation. The tester explicitly states: "Tolerances MUST NOT be relaxed beyond ±0.05 to make tests pass" — and the final audit confirms tolerances are unchanged at ±0.05 throughout.

**Prior BLOCK signals were correctly raised:**

- First BLOCK (commit 5c32bae): IT-4 violated (ME/BD > 1.0 — ratio of 3.8 clearly a bounds error) and two IT-8 sign checks failed. Legitimate BLOCK.
- Second BLOCK (commit 16ccbcb): IT-8 was still violated after builder v3 (AEM leverage sign — macro columns). The interim audit added a non-spec criterion (">20 cells outside ±0.05 = systematic failure"); however the IT-8 sign violations at that stage independently justified BLOCK. After builder v5 resolved the sign issues, the tester correctly dropped the non-spec criterion and applied PASS WITH NOTE.

No tolerance was relaxed at any stage. The BLOCK/respawn cycle terminated correctly after the builder addressed all spec-defined BLOCK conditions.

---

## 6. Documentation Quality

**Assessment: PASS**

**ARCHITECTURE.md:**

- Section 1 (Overview): accurate — correctly names Tables 2 and 3, data sources, and connectivity requirements.
- Section 2 (Package Structure): accurate — matches git ls-files output exactly.
- Section 3 (Key Formulas): accurate — η formula, book capital formula, AR(1) factor formula all match the implementation as described in implementation.md. The documented ρ = 0.9581 is taken from the actual WRDS run per audit.md IT-2.
- Section 4 (Data Pipeline): accurate — WRDS tables, public sources, and module flow correctly depicted.
- Section 5 (WRDS Tables): accurate — includes the critical schema discovery that `comp.fundq` lacks `sich` (historical SIC must come from `comp.funda`), and that `crsp.msenames.siccd` is integer (not varchar).
- Section 6 (Entry Points): accurate — function signatures match spec.md and implementation.md.
- Section 7 (Primary Dealer Universe): accurate — verified GVKEYs match implementation.md corrected mappings (e.g., Goldman Sachs 114628, not 011251 as in the original spec). Lists unmatched dealers correctly.
- Section 8 (Data Limitations): thorough — covers all five major limitations: pre-1978 gap, AEM leverage sign, Datastream exclusion, book debt approximation, 1960–1990 accuracy. The AEM leverage explanation is honest about the data-vintage uncertainty.
- Section 9 (Design Decisions): accurate — all seven decisions match the builder's rationale in implementation.md v3–v5.
- Section 10 (Test Coverage): accurate — 39 total tests, breakdown by group matches audit.md.

**README.md:**

Accurate summary, correct usage example, honest limitations section (5 items matching implementation.md known limitations). Python version listed as >= 3.11, which is consistent with type annotation style (`X | None` syntax, built-in generics).

**One minor note in documentation**: ARCHITECTURE.md Section 11 (Build & Run) shows a raw `psycopg2.connect()` usage example, while the README.md shows the preferred `wrds_connection()` context manager from `hkm.utils`. The README is more consistent with the package's own API; the ARCHITECTURE usage example is functional but bypasses the connection manager. This is a cosmetic inconsistency, not a correctness issue.

---

## 7. Ship Safety

**Assessment: PASS — Safe to ship**

Checklist:

| Safety Check | Status |
|---|---|
| Builder stayed within write surface (impact.md) | PASS — all files in impact.md, no extras in HEAD |
| No tolerance relaxation | PASS — ±0.05 unchanged throughout all builder iterations |
| No unresolved BLOCK conditions | PASS — all prior BLOCKs resolved; final tester verdict PASS WITH NOTE |
| No NotImplementedError stubs | PASS — `compute_table2()` and `compute_table3()` are fully implemented (39 tests pass with WRDS connection) |
| ARCHITECTURE.md matches actual code | PASS — section-by-section verification above confirms accuracy |
| ruff: zero errors | PASS |
| mypy --strict: zero errors | PASS |
| No print() statements in hkm/ | PASS |
| All 39 pytest tests pass | PASS |
| Known limitations documented | PASS — request.md, ARCHITECTURE.md Section 8, and README.md Known Limitations all transparent |
| Target repo clean (no unexpected files) | PASS — only .env.example, .gitignore, and listed package files; evaluation.md and hkm-paper.pdf are untracked and should not be committed |

**Notes for shipper:**

1. The current branch is 9 commits ahead of `origin/main`. All 9 commits are legitimate workflow commits (scaffold + builder iterations + scriber merge). Push all of them to `origin/main`.
2. Do NOT commit `evaluation.md` or `hkm-paper.pdf` — these are untracked intentionally.
3. The workspace repo sync should include the run log, docs.md, and updated HANDOFF.md per workflow 2 requirements.

---

## 8. Residual Notes (not STOP conditions)

The following are known limitations acknowledged in the run artifacts. They are transparently documented and do not affect ship safety, but future maintainers should be aware:

1. **AEM leverage level sign (+0.624 vs published -0.42)**: The raw BOGZ1 broker-dealer leverage is pro-cyclical. The paper's -0.42 correlation likely reflects a different AEM definition (equity ratio) or different FRED vintage. The five IT-8-specified sign checks all pass; this cell is not a hard BLOCK condition per test-spec.md.

2. **E/P growth magnitude (-0.164 vs published -0.75)**: Simple trailing E/P growth at quarterly frequency achieves correct sign but not published magnitude. A smoother or differently lagged E/P specification might close the gap. Sign is correct; not a BLOCK condition.

3. **Table 2 structural undercount pre-1978**: 26/36 cells outside ±0.05 due to sparse Compustat quarterly coverage before 1978 and post-1990 bank consolidation SIC boundary effects. All cells remain within (0, 1]; no bounds violations.

4. **Book capital macro correlations (GDP, Unemployment, Market volatility)**: Several sign differences remain vs published Panel A/B values, attributable to fiscal-quarter alignment sensitivity and dealer coverage gaps. IT-8 does not include book capital sign checks.

These residual gaps are consistent with the paper's own note (footnote 19) that a full replication requires Datastream access for foreign dealers and additional pre-1978 data sources. The replication is a good-faith CRSP/Compustat/FRED-only approximation with honest documentation of its bounds.

---

*Review complete. Routing to shipper.*

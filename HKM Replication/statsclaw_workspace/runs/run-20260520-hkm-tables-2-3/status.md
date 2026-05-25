# Status — run-20260520-hkm-tables-2-3

Current state: DONE

## History

| Timestamp | State | Notes |
|---|---|---|
| 2026-05-20 | NEW | Run created |
| 2026-05-20 | CREDENTIALS_VERIFIED | GitHub PASS, WRDS file present |
| 2026-05-20 | PLANNED | impact.md written; greenfield package build planned |
| 2026-05-20 | SPEC_READY | planner produced comprehension.md (FULLY UNDERSTOOD), spec.md (1001 lines), test-spec.md (737 lines) |
| 2026-05-20 | PIPELINES_COMPLETE (builder) | builder commit 49ae53d on builder/hkm-replication-v2; merged to main; 39/39 tests passed in builder env; dispatching tester |
| 2026-05-20 | BLOCKED | tester issued BLOCK: 32/36 Table 2 cells fail ±0.05; AEM leverage sign inverted (Panel A); E/P growth magnitude wrong (Panel B). See audit.md. |
| 2026-05-20 | BUILDER_COMPLETE_V3 | builder/hkm-fixes-v3 commit 159baa6 merged to main (5c32bae). Fixes: (1) compustat.py — fetch_compustat_all_quarterly now uses comp.funda.sich joined via fyearq=fyear (historical annual SIC, not comp.fundq.sich which doesn't exist) + CRSP shrcd IN (10,11) US-only filter via CCM link; (2) dealers.py — Salomon Smith Barney gvkey='008537' (SIC 6211, $212-448B assets); Chase truncated to 1995-12-31 to prevent stale carry-forward; (3) macro.py — E/P growth shift(4) YoY; (4) table2.py — removed _dealer_in_group/SIC filtering; ALL dealers in numerator for ALL groups; denominator = dealer TA + non-dealer group TA with GVKEY dedup. 39/39 unit tests pass. Dispatching tester v2. |

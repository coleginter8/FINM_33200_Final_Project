# Evaluation Rubric: StatsClaw vs Vanilla Claude Code

Applied to three test cases: HKM intermediary factor, GSW yield curve, CDS portfolio returns.

## Dimensions

| Dimension | Description |
|---|---|
| Clarification questions | Number of ambiguous decisions surfaced vs silently assumed |
| Wall-clock time | Total time from start to validated output |
| Validation pass rate | Fraction of oracle spot checks within tolerance |
| Pipeline isolation | Builder never read oracle; confirmed by audit trail |
| Token cost | Approximate input + output tokens per stage |
| Autonomy | Stages completed without user intervention |

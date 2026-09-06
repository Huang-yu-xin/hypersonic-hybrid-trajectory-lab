# M3-S2S Budget Audit

Exact integer budgets (no placeholders; taskbook Sec. 9/34):

| stream | budget |
|---|---|
| Truth discovery (240 candidates x 3 x 100k) | 72,000,000 |
| Truth confirmation (240 x 3 x 500k) | 360,000,000 |
| Truth P_ref (config-level reuse) | 0 |
| **TRUTH_BUDGET_MAX** | **436,000,000** |
| **ARM_A_GRADIENT_BUDGET** (120 x 8 x 20k) | **19,200,000** |
| ARM_B_MAX_BUDGET (120 x 8 x 2 x 20k; separate gate) | 38,400,000 |
| Online maximum if Arm B activates (excludes truth) | 57,600,000 |

Top-up is forbidden in every stream; planned/actual/difference accounting
is mandatory in the final report.

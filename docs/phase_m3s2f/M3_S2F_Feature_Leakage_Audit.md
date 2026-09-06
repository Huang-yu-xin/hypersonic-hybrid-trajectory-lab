# M3-S2F Feature Leakage Audit

Status: **PASS** (vacuously: no model was trained; no feature entered any X).

- Family A: not recoverable => never constructed.
- Family B (M_delta): constructible but not evaluated standalone in this
  stage; delta-quantile candidates would be inner-CV-only per the frozen
  rule when evaluated in a future recoverable stage.
- Family C: PI1VNR-only probe data (different budget/definition; absent on
  S1C) is INCOMPATIBLE for primary use — mixing it would constitute a
  protocol leak, and it was not used.
- No truth/reference/panel-identity field entered any computation beyond
  the membership-only protected-reserve audit.
- Parent dataset hash re-verified: True (f5f684fdb693123c...).
- Local-shape ruling: NOT_AVAILABLE_FOR_PRIMARY (MECHANISM_ONLY at most; PI1VNR-only probe cannot be mixed with S1C no-probe trials, taskbook Sec. 8.1).

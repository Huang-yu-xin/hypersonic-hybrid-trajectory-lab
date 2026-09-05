# M3-PI1V Robustness Diagnostics

Diagnostic only; no tuning was derived from LOSO/LOCO/state audits.

- State-level policy audit: `m3pi1v_state_level_policy_audit.csv` (48 rows, both families).
- LOSO: 48 held-out-state evaluations (threshold reselection on the remaining 23 states).
- LOCO: 28 held-out-config evaluations.
- Truth-subtype metrics reported separately (`m3pi1v_truth_stratified_metrics.json`); no subtype-specific thresholds.
- All outputs are labelled reference-stratified development metrics; no natural-prevalence claim.

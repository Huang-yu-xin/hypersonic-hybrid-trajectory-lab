# M3-ML0 Final Report

Verdict: **M3-ML0-C** (2026-09-06T10:58:20+0800).  No safety-compliant candidate; the current online feature family is insufficient for ML confirmation.

Development stage only: nothing here is "confirmed"; any successor requires
a new untouched stage.  Zero new simulator calls; the 18 protected reserve
states were untouched.

## 1-10 required answers

1. Tier-A strictly 48 states / 384 trials: **48 states / 384 trials**; dataset sha256 `f5f684fdb693123c...`.
2. Protected-18 zero touch: **YES** (overlap = 0; membership-only CSV in preflight).
3. Frozen S1 on the combined exposed dataset: coverage 0.8594, ND unsafe 0.2109, wrong 0.0000, HOLD unsafe 0.0000, AMBIGUOUS unsafe 0.3750.
4. S1C AMBIGUOUS failure reproduced on combined data: **YES** (AMBIGUOUS unsafe 0.3750 vs HOLD 0.0000).
5. Features most helpful for AMBIGUOUS separation (univariate AUC vs DEPLOYABLE): ESS_grad (AMB 0.370, HOLD 0.681); S1 (AMB 0.836, HOLD 0.981); SE_g (AMB 0.572, HOLD 0.741); abs_g_hat (AMB 0.850, HOLD 0.966); curvature_c (AMB 0.500, HOLD 0.500); s2 (AMB 0.418, HOLD 0.353).
6. Is logistic enough: B1 (S1-only) coverage 0.7852, ND unsafe 0.2344, wrong 0.0000, HOLD unsafe 0.0000, AMBIGUOUS unsafe 0.4167; B2 (F0 logistic) coverage 0.8477, ND unsafe 0.2188, wrong 0.0000, HOLD unsafe 0.0714, AMBIGUOUS unsafe 0.3333.
7. Does GBDT add stable gain: B3 coverage 0.7422, ND unsafe 0.1406, wrong 0.0000, HOLD unsafe 0.0000, AMBIGUOUS unsafe 0.2500.
8. All results from config-grouped OOF: **YES** (GroupKFold(5) outer on config_id, GroupKFold(4) inner; audit `D:\Users\huangyx\Desktop\hypersonic-hybrid-trajectory-lab\results\phase_m3ml0\preflight\m3ml0_groupsplit_audit.json`).
9. Safety-compliant candidate with coverage gain >= 5pp: **False**.
10. Next stage: feature redesign / S2 theory work; ML confirmation is not reachable with the current online features.

## Mechanism analysis (Q1-Q3, descriptive / non-causal)

- Group medians (S1 / SE_g / s2 / curvature_c): DEPLOYABLE S1 11.58, HOLD S1 1.96, AMBIGUOUS S1 4.57; SE_g DEPLOYABLE 0.00330 vs AMBIGUOUS 0.00327; s2 DEPLOYABLE 3.200 vs AMBIGUOUS 4.472.
- Standardized B2 logistic coefficients: S1=+2.526, SE_g=+2.345, curvature_c=-0.000, g_hat=-1.437, s2=-0.284.
- B2 permutation importance: S1=0.2870, SE_g=0.0284, curvature_c=0.0000, g_hat=0.0203, s2=0.0045.
- HOLD is easy for S1 because its gradient CIs are wide relative to |g_hat| (low S1); AMBIGUOUS trials often reach DEPLOYABLE-like S1, so S1 alone cannot separate them -- the quantitative AUC table above shows how far each available descriptor goes.

## Claim boundary

No safety-compliant candidate; the current online feature family is insufficient for ML confirmation.  Not allowed: "ML controller confirmed", "deployment safe",
"generalizes to the untouched population".  VALUE / RARITY / M3-Q remain
BLOCKED.

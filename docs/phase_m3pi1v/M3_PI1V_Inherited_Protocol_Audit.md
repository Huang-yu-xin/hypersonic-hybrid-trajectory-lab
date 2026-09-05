# M3-PI1V Inherited Protocol Audit

Status: **COMPLETE** (no ambiguous constants; no PI1V-PREREG-X).

- Gradient estimator: `hyptraj.m3d.adaptation.gradient_decision` (frozen M3-v0; sha256 `7a2251af2c39d54b...`).
- Sign convention: g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK (PI1 preregistration authoritative; the G2 CI-sign rule is not inherited).
- Invalid rule: estimator problems OR non-finite g_hat/CI/ESS OR ESS_grad < 20 => invalid; policy action ABSTAIN; no opposite direction inferred.
- R = 8 reps/state; B_grad = 20000 samples/trial; 20 batches; alpha_p = 0.5.
- Seed semantics: sha256(namespace|state_id|replicate); pilot rng [seed,101]; bootstrap [seed,424243].
- S1: abs(gradient_estimate) / ((ci_high-ci_low)/(2*1.959963984540054)) (UC3 S1_gradient_z).
- Metrics: UC3 wrong/coverage/unsafe semantics, Wilson 95% CIs.
- V1 SE estimator: paired-batch SE over 20 paired CRN batches (PI1 preregistration, hash-locked).

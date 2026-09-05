# M3-PI1VN Frozen Protocol Inheritance

Status: **COMPLETE**.

- PI1V committed implementation hash: `c7332b9e91ce8c28...`.
- Gradient estimator: hyptraj.m3d.adaptation.gradient_decision.
- Sign convention: g_hat < 0 => WIDEN; g_hat > 0 => SHRINK; R=8, B_grad=20000.
- Probe: 10000/10000, 20 paired CRN batches; opposite action never probed; no adaptive probe.
- V1 = V1 = (-0.01 - r_hat) / SE(r_hat); S1 = abs(g_hat) / ((ci_high-ci_low)/(2*1.959963984540054)) on the same gradient data.
- Metrics/thresholds/gates/5pp criterion imported verbatim from the committed PI1V machinery; no invalid-PI1V threshold reused.

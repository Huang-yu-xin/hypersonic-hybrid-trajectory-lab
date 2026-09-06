# M3-ML0 Reserve Firewall Audit

Status: **PASS** (2026-09-06T10:53:23+0800).

- Remaining protected reserve rebuilt live from source artifacts:
  **18 states** (42 reserve - 24 S1C panel).
- Used by ML-0: **0**.  Membership-only CSV:
  `results/phase_m3ml0/preflight/m3ml0_protected_reserve_18.csv`
  (state_id / config_id / membership / source hash).
- Forbidden uses enforced: gradient, V1 probe, S1, features, splits, error
  analysis, threshold selection, theory descriptors, plots.

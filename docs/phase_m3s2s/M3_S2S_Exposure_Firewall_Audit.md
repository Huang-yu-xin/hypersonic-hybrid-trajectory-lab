# M3-S2S Exposure Firewall Audit

Status: **PASS** (2026-09-06T12:53:48+0800).

- Exclusion manifest is content-based (comparator-field detection with
  namespace inheritance; filename-only classification forbidden).
- Excluded sets: PI1V attempts, PI1VN retired, PI1VNR development panel,
  S1C confirmation panel, ML0 Tier-A states, all gradient pilots, all V1
  probes, all S1 threshold-search/diagnostic panels, all prior controller
  confirmation panels, and the 18 protected reserve.
- Truth-reference-only characterization remains allowed under frozen
  semantics (no g_hat/S1/V1/r_hat/deploy-abstain comparator output).
- Candidate pool: 240 truth-UNLABELED states (freshness is
  structural: new s2 points excluding all characterized values).
- Unknown candidate-bearing artifacts: none at prereg time; any UNRESOLVED
  at execution => candidate ineligible => STOP if quota unmet.

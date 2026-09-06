# M3-S2S Truth Source Audit

Status: **PASS (T1: new truth sampling required; canonical CF1N three-phase protocol frozen verbatim)** (2026-09-06T12:24:43+0800).

- Existing corrected truth inventory (94 states, event semantics v2) is
  fully consumed: controller-exposed + protected covers 94/94; fresh
  truth-labeled pool = **0** => T0 infeasible.
- TRUTH_SAMPLING_REQUIRED = **YES** (T1).
- Canonical truth contract frozen verbatim: the CF1N three-phase corrected
  protocol (pref 500k/config reusable; discovery 3 arms x 100k with
  direction_margin 0.05 / hold_band 0.03 / improvement_threshold -0.01 /
  min arm ESS 20; confirmation 3 arms x 500k, paired CRN 20; namespaces
  M3-CF1N-PREF / M3-CF1N-DISCOVERY / M3-CF1N-CONFIRM; event semantics v2).
- Truth-contract phase config hashes are recorded in
  `configs/phase_m3s2s/m3s2s_truth_contract.json`.
- Retirement: every truth-sampled state enters
  `m3s2s_truth_exposed_inventory` and is retired from future untouched
  confirmation use, selected or not.

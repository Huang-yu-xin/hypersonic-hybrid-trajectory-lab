# M3-S25-R1 Candidate Support Audit

Status: mechanics **PASS**, structural support invariants (M3-S25-R1.2,
bounds derived from the frozen generator constants) **PASS**
(2026-09-06T23:09:41+0800).

- Mechanism: u in [0.15, 1.00] split into 8 frozen strata; per config x
  stratum exactly one fresh state chosen as the FIRST legal+fresh anchor
  in SHA256 anchor-hash ascending order over L=65 deterministic interior
  anchors (taskbook Sec. 6/7).  Selection is independent of truth labels,
  discovery results, SHRINK/HOLD counts and candidate numeric ordering.
- 240 candidates / 30 configs / 8 strata each; duplicate state_id = 0;
  freshness violations = 0; legality violations = 0; truth labels
  consulted = 0; candidate substitution = 0.
- Realized u range over the universe: [0.1548, 0.9984].
- M3-S25-R1.2 STRUCTURAL invariants (bounds derived from the frozen
  generator constants; tol = 1e-12): A stratum occupancy 8/8 =
  True; B min(u) <= u0_max + tol =
  True; C max(u) >= u7_min - tol =
  True; D span >= (u7_min-u0_max) - tol =
  True.
- Superseded chain: R1.0 span >= 0.70 (FAIL c000 0.6971 / cf1n_new_002
  0.6649) and R1.1 fixed thresholds 0.25/0.85/0.65 (FAIL m3s2s_cfg_005
  min u 0.251420 > 0.25) -- both resolved by the structural bounds.
- Per-config report:
  `results/phase_m3s25r1/preflight/m3s25r1_preflight.json`
  (`per_config_support`); historical records:
  `M3_S25_R1_Support_Invariant_Conflict.md` (R1.0),
  `M3_S25_R1_1_Amendment_Record.md` (R1.1, BLOCKED evidence preserved),
  `M3_S25_R1_2_Amendment_Record.md` (R1.2).

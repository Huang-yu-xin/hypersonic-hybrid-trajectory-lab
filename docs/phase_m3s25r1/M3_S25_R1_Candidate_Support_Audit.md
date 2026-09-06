# M3-S25-R1 Candidate Support Audit

Status: mechanics **PASS**, support-span invariant **FAIL**
(2026-09-06T20:14:34+0800).

- Mechanism: u in [0.15, 1.00] split into 8 frozen strata; per config x
  stratum exactly one fresh state chosen as the FIRST legal+fresh anchor
  in SHA256 anchor-hash ascending order over L=65 deterministic interior
  anchors (taskbook Sec. 6/7).  Selection is independent of truth labels,
  discovery results, SHRINK/HOLD counts and candidate numeric ordering.
- 240 candidates / 30 configs / 8 strata each; duplicate state_id = 0;
  freshness violations = 0; legality violations = 0; truth labels
  consulted = 0; candidate substitution = 0.
- Realized u range over the universe: [0.1548, 0.9984].
- Per-config span report: see
  `results/phase_m3s25r1/preflight/m3s25r1_preflight.json`
  (`per_config_support`) and
  `M3_S25_R1_Support_Invariant_Conflict.md` for the realized conflict.

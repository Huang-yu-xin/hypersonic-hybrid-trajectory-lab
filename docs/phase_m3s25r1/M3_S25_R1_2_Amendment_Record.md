# M3-S25-R1.2 Amendment Record (zero sampling)

Amendment document:
`docs/phase_m3s25r1/M3_S25_R1_2_Amendment_Taskbook.md` (sha256
`dcb2e1b7ee432da835b5d968c5e9f336836b49a1608e1e180d7356cfdf810790`).  Parent: M3-S25-R1.1 at commit
`37553a207d96b2edcc827595f0b711e392c4358f`.

## What changed (and what did not)

- REPLACED: the M3-S25-R1.1 fixed decimal support thresholds
  (B min(u) <= 0.25; C max(u) >= 0.85; D span >= 0.65) with
  GENERATOR-DERIVED STRUCTURAL invariants computed from the frozen
  constants U_LO = 0.15, U_HI = 1.00, N_STRATA = 8, L_ANCHORS = 65:
  `w = (U_HI-U_LO)/N_STRATA`; `u0_max = U_LO + L_ANCHORS/(L_ANCHORS+1)*w`;
  `u7_min = U_LO + (N_STRATA-1)*w + 1/(L_ANCHORS+1)*w`; frozen numerical
  tolerance tol = 1e-12.  The implementation
  (`hyptraj.m3s25r1.candidates.structural_bounds`) computes the bounds
  from the constants and takes no data input, so realized candidate
  values cannot tune the thresholds.
- UNCHANGED: the frozen candidate universe and its byte SHA256
  (`9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`),
  candidate generation, hash ranking, freshness rules, legality, seeds,
  truth semantics, budget (432,000,000), runtime ordering, panel rules,
  and every authorization gate.
- PRESERVED: the R1.1 preflight BLOCKED report as historical evidence --
  `results/phase_m3s25r1/preflight/m3s25r1_1_preflight_R1_1_historical.json`
  (sha256 `5cdf399fd9ab7b8a76840ef10e1a6b12744bfbc656e816f55e473160fc2e54aa`, verdict FAIL,
  failed check invariant_B_min_reach_le_0.25 for m3s2s_cfg_005).

## Zero-sampling validation outcome

- Universe byte SHA unchanged: PASS.  240 states / 30 configs /
  8 strata per config: PASS.  Freshness: 0 collisions, 0 substitutions:
  PASS.  Truth-semantics hash, seed manifests, budget 432,000,000:
  PASS.  Simulator calls = 0; samples = 0.
- Structural invariants (all PASS):
  - A (stratum occupancy 8/8): PASS for all 30 configs.
  - B min(u) <= u0_max + tol, u0_max = 0.2546401515151515: PASS
    (worst realized min u = 0.251420).
  - C max(u) >= u7_min - tol, u7_min = 0.8953598484848485: PASS
    (worst realized max u = 0.898580).
  - D span >= (u7_min - u0_max) - tol = 0.6407196969696970: PASS
    (worst realized span = 0.664867).
- Realized conflicts: 0/30.

| config | failed | min u | max u | span |
|---|---|---|---|---|
| (none) | | | | |

## Disposition

- Preflight verdict: **PASS** --
  EXECUTION-READY.
- Per amendment: M3_S25_R1_TRUTH_AUTHORIZED remains NO pending the human
  execution-readiness audit; ARM_A / ARM_B remain NO; VALUE / RARITY /
  M3-Q BLOCKED; simulator calls = 0; samples = 0.
- Amendment history preserved without squashing: R1.0 (commit e244a06)
  and R1.1 (commit 37553a2) remain in history; this amendment is the
  next commit.
- STOP for human audit.

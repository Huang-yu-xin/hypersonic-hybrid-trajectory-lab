# M3-S25-R1 Truth Stage Report

Outcome: **M3-S25-R1-PANEL-FROZEN**.  Recorded 2026-09-06 under the
M3-S25-R1.2 T1 authorization (TRUTH Gate ONLY, Human 2026-09-06, commit
`56c7588`; execution-readiness audit PASS).  **ARM_A_AUTHORIZED = NO;
ARM_B_AUTHORIZED = NO; VALUE / RARITY / M3-Q = BLOCKED.**

## Execution integrity (clean)

- 480/480 truth units durable COMPLETE: 240 discovery + 240
  confirmation.  **CONSUMED_INVALID = 0.**  0 duplicates; every COMPLETE
  record's `record_file_hash` re-verified against its durable file
  (0 mismatches across both streams).
- Exact sample accounting (planned == actual, topup = 0, difference = 0):
  discovery 240 x 3 x 100,000 = **72,000,000**; confirmation 240 x 3 x
  500,000 = **360,000,000**; P_ref sampling = **0** (30-entry reuse
  registry, hash-verified).  Total actual = **432,000,000** =
  TRUTH_BUDGET_MAX.

## Frozen truth (240 R1 states, ALL_240_R1_CANDIDATES)

| truth | n | (parent M3-S2S reference) |
|---|---|---|
| WIDEN | 116 | 171 |
| SHRINK | **61** | **0** |
| HOLD | 25 | 16 |
| AMBIGUOUS | 38 | 53 |

The support completion worked exactly as designed: the corrected
benchmark's SHRINK region lives at high s2, and R1's stratified coverage
of u in [0.15, 1.00] produced 61 SHRINK states where the parent's
low-end-only placement produced zero.

## Truth-exposed inventory / development union

- All 240 R1 states recorded in
  `results/phase_m3s25r1/summary/m3s25r1_truth_exposed_inventory.json`
  (development_eligible = YES; untouched_confirmation_eligible = NO).
- Development union D_union = D_old (M3-S2S 240) u D_new (M3-S25-R1 240)
  = **480 states**, 0 duplicates.

## Frozen panel (union pool, M3-S25-R1-PANEL-V1)

- **M3-S25-R1-PANEL-FROZEN**: 120 unique states / 30 distinct configs
  (>= 24 required), truth composition exactly **30 WIDEN / 30 SHRINK /
  30 HOLD / 30 AMBIGUOUS**; no quota relaxation, no panel shrinkage.
- Source mix: 83 states from M3-S25-R1, 37 from M3-S2S.  **All 30
  SHRINK states come from M3-S25-R1** (the repaired support); M3-S2S
  contributed WIDEN 14 / HOLD 9 / AMBIGUOUS 14.
- Panel sha256: `2bdb9a91562cc44c...` (frozen in
  `configs/phase_m3s25r1/m3s25r1_panel.json`; per-state records in
  `results/phase_m3s25r1/summary/m3s25r1_panel.csv` with truth artifact
  hashes and ranking hashes under the frozen namespace
  `M3-S25-R1-PANEL-V1|`).

## Gates / terminal state

```text
M3-S25-R1 truth stage terminus: M3-S25-R1-PANEL-FROZEN
M3_S25_R1_TRUTH_AUTHORIZED  = YES (exercised; truth stage complete)
M3_S25_R1_ARM_A_AUTHORIZED  = NO
M3_S25_R1_ARM_B_AUTHORIZED  = NO
VALUE / RARITY / M3-Q       = BLOCKED
```

STOP executed after the panel freeze.  No Arm A or Arm B activity.  The
next step is the independent post-truth / post-panel human audit; only a
new explicit human authorization can enable Arm A.

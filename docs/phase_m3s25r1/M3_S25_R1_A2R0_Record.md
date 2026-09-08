# M3-S25-R1-A2R0 — Inherited-269 Completion Preregistration

Recorded 2026-09-07.  Zero-sampling preregistration stage authorized by
the post-A1R human adjudication: A1R is validly and permanently terminal
`M3-S25-R1-A1R-X` at HEAD `e955c49`; the 269 durable COMPLETE A1R
trials are inherited together; 691 entirely new trials complete the
frozen 960-trial panel.

```
M3-S25-R1-A2R0 PREREG STATUS:
ROUND 0 COMPLETE (zero sampling)

A1R (sealed terminal):
M3-S25-R1-A1R-X at HEAD e955c49 (PERMANENT; NO REPLAY)
269 durable COMPLETE / 1 CONSUMED_INVALID / 690 never-started
A1R ledger SHA 0ad71e8b620cfda98ee1811a26d517a398d00d72513c98453281327059d528f7

INHERITANCE:
269 inherited A1R records (hash-pinned in place; never copied)
691 missing logical slots (includes 1 CONSUMED_INVALID + 690 FRESH)
invalid unit c020_s25r1_3.8634000847|rep5 EXPOSED / CONSUMED_INVALID / EXCLUDED
ALL-269-or-none; no truth labels in the manifest

SEEDS:
691 new seeds under M3-S25-R1-A2R-GRAD
zero overlap with: old A1R 960, old Arm-A 960, truth/S2S/CF1N/historical

BUDGET:
inherited samples 5,380,000 (269 x 20,000)
new planned = max 13,820,000 (691 x 20,000)
effective final dataset 19,200,000
cumulative if A2R completes 19,240,000
top-up = 0; substitution = 0

FROZEN DESIGN (unchanged):
same 120-state panel; same truth manifest; same estimator; same S1
threshold 5.4417199447782; same features/CV/model grids/safety gates

BOUNDED DIR FSYNC RETRY (A2R-only; §8):
max 5 attempts; deterministic backoff [0.0, 0.01, 0.05, 0.15, 0.30]s
retries ONLY the directory durability operation on the SAME artifact
NEVER reruns the simulator; all fail => CONSUMED_INVALID => A2R-X => STOP

PERSISTENCE:
results/phase_m3s25r1/arm_a2r/ (completely separate from A1R)
A2R ledger covers only the 691 new trials
A1R ledger and 269 inherited artifacts are never modified

EVALUATION GATE:
truth sealed until 269 inherited verified + 691 new COMPLETE = 960
then frozen B0/B1/A1-A4; terminal names A2R-A / A2R-B-GATE / A2R-X

GATES (all NO):
M3_S25_R1_A2R_ARM_A_AUTHORIZED: NO
M3_S25_R1_A2R_ARM_B_AUTHORIZED: NO
(all previous gates remain NO/CLOSED; VALUE/RARITY/M3-Q BLOCKED)

simulator calls = 0; samples = 0
```

## Frozen artifact SHAs

- A2R inheritance manifest: `d1efd276fa8b38ff...`
- A2R retired stream: `6d02e2112901754a...`
- A2R contract: `958cd0aa6cde3e42...`
- A2R seed manifest: `edb038a6e69a2e61...`
- A1R contract (updated `code_sha256` for A2R arm_a.py changes): `784f3f5db6e1d44f...`

## Preflight

23/23 checks PASS.  Simulator calls = 0, samples = 0.

# M3-S25-R1-A2R0 — Inherited-269 Completion Preregistration

Recorded 2026-09-07.  Amended 2026-09-08 (A2R0.1).  Zero-sampling
preregistration stage authorized by the post-A1R human adjudication:
A1R is validly and permanently terminal `M3-S25-R1-A1R-X` at HEAD
`e955c49`; the 269 durable COMPLETE A1R trials are inherited together;
691 entirely new trials complete the frozen 960-trial panel.

## A2R0.1 Amendment (2026-09-08, zero sampling)

1. **Restored the historical A1R contract** to its exact terminal bytes
   at HEAD `e955c49` (SHA `fdf0c42d...`).  A terminal historical contract
   is NOT updated to match current A2R source code.  The current A2R
   scientific-code SHA lives only in the A2R contract's
   `corrected_instrumentation.code_sha256` and the hash manifest.
   A1R regression tests compare against the historical frozen contract,
   not the current working-tree `arm_a.py`.

2. **Corrected A2R new-seed manifest semantics**: the manifest describes
   ONLY the NEW sampling stream:
   - `n_units = 691`, `n_trials = 691`, `budget = 13,820,000`
   - Optional: `inherited_trials = 269`, `total_effective_trials = 960`,
     `effective_final_dataset = 19,200,000`
   - No seed value or unit ID was altered.

3. **seed_collision_audit** returns `units = expected_count` (691 for
   A2R), not the global `N_TRIALS`.

### Unchanged in A2R0.1

- 269 inherited unit IDs and all their hashes
- 691 new unit IDs and all seed values
- panel, truth manifest, A0 contract
- old A1R seed manifest, A1R ledger
- fsync retry constants/policy
- all scientific budgets

### Changed in A2R0.1

- A2R seed-manifest SHA (metadata only)
- A2R retired-stream SHA (historical contract SHA correction)
- A2R contract SHA
- runner/hash-manifest SHA

## Frozen design summary

```
M3-S25-R1-A2R0 PREREG STATUS:
ROUND 0 COMPLETE (amended by A2R0.1; zero sampling)

A1R (sealed terminal):
M3-S25-R1-A1R-X at HEAD e955c49 (PERMANENT; NO REPLAY)
269 durable COMPLETE / 1 CONSUMED_INVALID / 690 never-started
A1R ledger SHA 0ad71e8b620cfda98ee1811a26d517a398d00d72513c98453281327059d528f7
A1R contract SHA fdf0c42d4922890a6c17b004278253ec4a4797e76373ece6292c7512b2863985 (HISTORICAL, RESTORED)

INHERITANCE:
269 inherited A1R records (hash-pinned in place; never copied)
691 missing logical slots (includes 1 CONSUMED_INVALID + 690 FRESH)
invalid unit c020_s25r1_3.8634000847|rep5 EXPOSED / CONSUMED_INVALID / EXCLUDED
ALL-269-or-none; no truth labels in the manifest

SEEDS:
691 new seeds under M3-S25-R1-A2R-GRAD
n_units = 691; n_trials = 691; budget = 13,820,000
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

BOUNDED DIR FSYNC RETRY (A2R-only):
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

## Frozen artifact SHAs (after A2R0.1)

- A2R inheritance manifest: `d1efd276fa8b38ff...` (unchanged)
- A2R retired stream: `90c274b47da28173...` (corrected: historical contract SHA)
- A2R contract: `b87f0dfcf6d76ed9...` (corrected)
- A2R seed manifest: `9d41eecb8d2ed81c...` (metadata correction)
- A1R contract: `fdf0c42d4922890a...` (HISTORICAL, RESTORED to terminal bytes)

## Preflight

23/23 checks PASS.  Simulator calls = 0, samples = 0.

## Broad M3-lineage regression

2369 passed, 0 failed, 46 deselected (route), 3 warnings (deprecation).
A2R0 + A1R0 (historical-freeze) + A0 + R1 + parent + all M3-lineage.

# M3-S25-R1-A2R-B0 Record — ±Delta Local-Shape Arm-B Preregistration

ZERO scientific sampling in this stage.  All artifacts are mechanical
preflight; no simulator calls.

## What this stage is

B0 is the preregistration of Arm-B's ±Delta local-shape evaluation.
The human scientific choice `Delta = 0.10` in `u = log(s^2)` is frozen.
All 960 center trials and their seeds are immutable CRN anchors.

## Parent acceptance

Parent terminal `M3-S25-R1-A2R-B-GATE` at `5d7eb7b234cedb0069adf7043234047a34028288`
accepted as **VALID SCIENTIFIC NEGATIVE**.

Arm-A was exercised once: 691/691 new durable COMPLETE with 0
CONSUMED_INVALID + 269 inherited = 960 effective / 19.2M samples.
No A-model met the frozen success criterion.  Arm-B proceeds as the
separate local-shape arm.

## Frozen center dataset

- 120 states × 8 replicates = 960 center logical units
- 269 inherited A1R COMPLETE + 691 A2R COMPLETE = 960 center trials
- Same truth/panel: `m3s25r1_panel.json` (SHA256: `2bdb9a91...`)
- Same center estimator: `hyptraj.m3d.adaptation.gradient_decision`
- Same GroupKFold(5) / GroupKFold(4), groups = config_id
- Same safety gates: coverage ≥ 0.75, ND unsafe ≤ 0.20, wrong ≤ 0.05, AMBIGUOUS unsafe < 0.25

## Human scientific choice frozen

```
Delta = 0.10
coordinate: u = log(s^2)
```

- Do not compare Delta values after Arm-B data
- Do not fall back to 0.05/0.20 automatically
- If ±0.10 infeasible for any frozen state → STOP

## Feasibility proof

For all 120 panel states, `s2_side = s2 * exp(+-0.10)` ranges from
0.495 to 8.803.  All values > 0 and within valid numerical range.
**120/120 states feasible for Delta=0.10.**

## Arm-B scientific sampling specification

| Quantity | Value |
|----------|-------|
| Center logical units | 960 |
| Side trials per center | 2 (one L, one R) |
| Total side trials | 1,920 |
| Samples per side trial | 20,000 |
| Total side budget | 38,400,000 |
| Top-up | 0 |
| Substitution | 0 |

Side evaluations:
- Left: `u - 0.10` → `s2_left = s2 * exp(-0.10)`
- Right: `u + 0.10` → `s2_right = s2 * exp(+0.10)`

## CRN semantics (audited and frozen)

**Audit document**: `M3_S25_R1_A2R_B0_CRN_Audit.md`

The center seed is the CRN anchor.  For each center trial:

1. Recompute center pilot: `z, logp, logr_c, strata = draw_online_pilot(st_center, seed_center)`
2. Compute `a_vec_c, resp_c, sq_c` using center proposal `q_c`
3. Evaluate gradient at `s2_c`, `s2_l`, `s2_r` using SAME `z`, recomputed importance weights per side proposal
4. Frozen `scalar_gradient_estimate(a_vec, resp, sq, s2=side_s2, dim=dim)`
5. Frozen `stratified_bootstrap_gradient_ci(a_vec, resp, sq, strata, s2=side_s2, ...)`

**Key insight**: Same seed at different s2 gives DIFFERENT z (because s2 enters the proposal Cholesky).  CRN is achieved by drawing ONCE at center and reusing z for all three evaluations with recomputed logr.

- Never rerun a center trial
- Never replace a center record
- Never count a center seed reuse as a new center realization
- No silent switch to independent RNG

## Frozen local-shape feature family

1. `local_sign_persistence`
2. `left_sign_match`
3. `right_sign_match`
4. `three_point_sign_pattern`
5. `gradient_slope`
6. `left_slope`
7. `right_slope`
8. `slope_asymmetry`
9. `relative_gradient_slope`
10. `local_gradient_range`
11. `local_S1_range`
12. `g_double_prime_descriptive`

No new feature discovery after Arm-B sampling.

## Frozen model machinery

- Reuse only frozen Logistic / GBDT grids
- No MLP, Optuna, new hyperparameter sweep, or new threshold search
- Best Arm-A comparator: B1 aggregate GBDT baseline

## Arm-B success gates

Coverage ≥ 0.75, ND unsafe ≤ 0.20, wrong ≤ 0.05, AMBIGUOUS unsafe < 0.25

And relative to frozen best Arm-A comparator (B1):
- coverage gain ≥ 0.03
- OR: ND unsafe reduction ≥ 0.05 with coverage ≥ 0.75

## Terminal mapping

| Verdict | Meaning |
|---------|---------|
| `M3-S25-R1-A2R-C` | Arm-B local-shape development success |
| `M3-S25-R1-A2R-D` | Valid negative after Arm B |
| `M3-S25-R1-A2R-X` | Integrity invalid |

## Persistence

- Separate path: `results/phase_m3s25r1/arm_b/`
- Separate ledger: `trial_ledger.jsonl`
- Separate left/right records
- Hardened bounded directory-fsync retry (5 attempts, deterministic backoff)
- Any consumed side trial without durable COMPLETE → CONSUMED_INVALID → X → STOP → NO REPLAY

## Gates during B0

```
M3_S25_R1_A2R_ARM_B_AUTHORIZED = NO
M3_S25_R1_A2R_TRUTH = BLOCKED
M3_S25_R1_VALUE_RARITY_M3Q = BLOCKED
```

Truth / VALUE / RARITY / M3-Q remain blocked for execution.

## B0 readiness proof (25/25 tests PASS)

- [x] Parent B-GATE exact at `5d7eb7b`
- [x] Delta=0.10 feasible for all 120 states
- [x] Exact CRN semantics proven and documented
- [x] 960 center anchors fixed (269 inherited + 691 A2R)
- [x] 1,920 side units frozen (960 L + 960 R)
- [x] Exact 38.4M budget
- [x] Persistence path created (`results/phase_m3s25r1/arm_b/`)
- [x] Seed manifest written with SHA256 binding
- [x] B0 contract written with all gates NO/BLOCKED
- [x] Mock test proves zero scientific simulator calls
- [x] CRN audit document complete

## Artifacts

| Artifact | Path | SHA256 |
|----------|------|--------|
| B0 contract | `configs/phase_m3s25r1/m3s25r1_b0_contract.json` | See contract |
| B0 seed manifest | `configs/phase_m3s25r1/m3s25r1_b0_seed_manifest.json` | `b9e5d124...` |
| CRN audit | `docs/phase_m3s25r1/M3_S25_R1_A2R_B0_CRN_Audit.md` | — |
| B0 prereg tests | `tests/test_m3s25r1_b0_prereg.py` | — |
| Arm-B persistence | `results/phase_m3s25r1/arm_b/` | — |

## STOP

B0 preregistration complete.  STOP for immediate Arm-B authorization audit.
Do NOT run arm_b_execute.

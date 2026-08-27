# M3-BV2 Validity Audit — benchmark-construction integrity

> **Completed at:** 2026-08-28 ｜ **Branch:** `feature/phase-m3bv2-dual-axis-benchmark`
> **Audit scope:** BV2-D0 (decision) and BV2-V0 (value) validity items plus the shared construction integrity chain. Audit reads only preregistered construction outputs; no controller output is read anywhere.

---

## 1. Parent-tag and preregistration chain

| Check | Evidence | Result |
|---|---|---|
| `RareTopo-M3-BV-v0` tag exists | `git tag -l` | **PASS** |
| Tag points at the correction commit | `git rev-list -n 1 RareTopo-M3-BV-v0` = `1eea183` ("Correct M3-BV headroom interpretation and finalize negative result") | **PASS** |
| M3-G-v1 parent unchanged | `git rev-parse RareTopo-M3-G-v1^{}` = `4505a36` | **PASS** |
| M3-D-v0 parent recorded | lock `parent_tags.m3d_v0` = `7bd58c59` | recorded |
| BV2 task + construction lock committed before science | commit `37d17bc` ("M3-BV2 task + construction lock committed (PREREGISTERED…)") is an ancestor of every BV2 analysis `git_commit` | **PASS** |
| M3-D freeze reference intact | `docs/phase_m3d/M3_D_Benchmark_Freeze.json` body sha256 `b613f45d…` self-recorded and reproducible by stripping `freeze_sha256_of_body_above` (json.dumps indent=1) | **PASS** |

## 2. Candidate-source byte identity (task Sec. 5)

| Check | Evidence | Result |
|---|---|---|
| reuse recorded as prior data | `results/phase_m3bv2/reuse_record.json`: `conclusion = REUSE_OK`, `reuse_condition` names the task Sec. 5 contract | **PASS** |
| pool task anchor matches | `pool.task_sha256` = sha256(BV-v0 task doc) | **PASS** |
| pool lock anchor matches | `pool.construction_lock_sha256` = sha256(BV-v0 construction lock) | **PASS** |
| config family matches | `pool.frozen_configs` == `m3d_candidate_state_grid.json` `frozen_configs` (8 configs) | **PASS** |
| s2 grid matches | `pool.s2_grid_bv` == locked 11-value grid | **PASS** |
| state keys = 8 × 11 grid | 88 keys, no extras, no gaps | **PASS** |
| source hashes recorded | pool `7fe30650…`, headline `9d1822e7…` (sha256 in reuse record) | **PASS** |

## 3. Legality (task Sec. 6)

- 88 / 88 candidate states legal; `all_three_arms_legal = true` for every state (BASE / WIDEN / SHRINK at delta_theta = 0.20); 0 `ILLEGAL_PRE_FREEZE`; 0 assembly stops.
- Every state selected into either benchmark is drawn from this legal pool (asserted per state by `test_m3bv2_three_arm_legality`).

## 4. Reference-budget and CRN semantics (task Sec. 7)

- Every reference record: N_ref = 500,000/arm, 20 batches, `delta_theta = 0.20`, single state RNG anchor 701001 + candidate index.
- CRN rule (locked): one shared Generator per state across base/shrink/widen within each batch; only the selected component's Cholesky differs.
- **M2 = Σ_j L_j verified on all 264 arm records** (1e-9-level diffs; `pass = true` on all).
- Label distribution over the 88 states: WIDEN 42, SHRINK 27, HOLD 12, REFERENCE_AMBIGUOUS 7.

## 5. Headline-budget semantics (task Sec. 8)

- 100,000/arm × 10 batches × **8 matched replicates** per state (the frozen final evaluation budget).
- Replicate RNG rule `[701001 + candidate_idx, 10000 + replicate]` re-verified **exact on all 704 replicate records**.
- Matched within replicate (CRN), independent across replicates.

## 6. No-controller-leakage scan

- Recursive key scan of `decision_analysis.json` and `value_analysis.json` for controller-family terms (`controller`, `m3g`, `gradient`, `ga1`, `rho`, `offline`, `ess`, `m3-d`): **zero hits**.
- `source` fields of both analyses reference only the two prior-characterization files + the reuse record.
- Selection uses only reference label / margin / stability / legality / config coverage — no controller performance (construction lock `firewall`).

## 7. Determinism of selection

- Axis A: the locked BV-v0 algorithm replayed at BV2 produces a selection **bit-identical** to the BV-v0 recorded 8/8/8 (cross-check `bv0_replay_crosscheck_identical = true`).
- Axis B: deterministic replay (same inputs, same rule) reproduces the stored 12/12 selection exactly (`test_m3bv2_selection_deterministic`).
- No manual state picking; Oracle feasibility was checked **after** deterministic selection.

## 8. Unified-objective self-consistency

- `J(π) = median_state [median_replicate log(M2(π)/M2(BASE))]` recomputed from raw per-replicate M2 by an independent implementation in the test suite: matches the stored J for Oracle and all three fixed policies to 1e-9.
- BestFixed re-derived from the same stored per-state tables equals the recorded BestFixed; `G_Oracle` recomputed from the same table matches to 1e-9.
- J(ALWAYS_HOLD) = 0 exactly, as implied by the functional (BASE/BASE per replicate).

## 9. Freeze-artifact integrity

- Both freeze JSONs satisfy the schema (13 required keys incl. `controller_runs_on_bv2 = 0`, `online_trials_run_before_this_freeze = 0`, seal declaration).
- `freeze_sha256_of_body_above` is reproducible from the file content (field stripped, `json.dumps(indent=1)`): Decision `bd10a094…` → regenerated `54c3da78…`; Value `ba0aae02…` → `de2e00b3…` (body hash changes when the `frozen_at_utc` timestamp is regenerated; self-consistency holds at each generation).
- Benchmark consumption configs match the freeze state sets exactly.
- Freeze files committed at `2e814a5` *after* the full test suite passed (1213 passed).

## 10. Test-suite evidence

```
python -m pytest -q
→ 1213 passed, 0 failed (includes the 18 task-required test_m3bv2_* tests)
```

## 11. Verdict

> **All BV2-D0 / BV2-V0 validity items PASS. Both benchmarks are constructed from byte-identical prior characterization, all gates are recorded, and controller runs on BV2 remain 0.**
# M3-S25-R1-A0 Record (Arm-A Rebind & Execution Readiness; zero sampling)

Parent truth terminal HEAD `089c6a48c73831fbd95e2caa5b21137b485080aa`
(M3-S25-R1-PANEL-FROZEN).  A0 added NO simulator calls and NO samples.

## Frozen artifacts (hash-pinned)

| artifact | sha256 |
|---|---|
| panel truth manifest (evaluation-only, SEALED) | `75f5993bc6a251220e5e533f0b96de153bcef313d95706e6e0b7294db57af880` |
| Arm-A rebind contract | `234c651654ffaaca32f32036befd4b4ea6038174dca7b80e78356f488d0f3570` |
| Arm-A seed manifest (960 units) | `20cbe999286df7c4664a53067a1796b7b1ce9da37eb5c42939e07a456b8bf30d` |

- Panel truth manifest: 120 states, 30/30/30/30, 30 configs, source mix
  R1 83 / S2S 37, all 30 SHRINK from M3-S25-R1; bound to panel body SHA
  `2bdb9a91...` and the exact `m3s25r1_panel.json` file SHA.  Mechanical
  verification PASS.  SEALED: never read during Arm-A sampling; unsealed
  only after 960/960 durable COMPLETE.
- Rebind (no scientific retuning): estimator
  `hyptraj.m3d.adaptation.gradient_decision` unmodified with a BIT-EXACT
  crosscheck enforced on every trial; alpha_p 0.5; S1 threshold
  5.4417199447782; 120 x 8 x 20,000 = 960 trials = 19,200,000 (no
  top-up); instrumentation m3s2s_instr_v1 (N_BOOTSTRAP 500; a_vec / resp
  / sq / strata / bootstrap_g sidecars); parent feature family, grouped
  nested-CV (outer GroupKFold(5) / inner GroupKFold(4), groups =
  config_id; no test-fold threshold/delta tuning), model family
  (B0 frozen S1, B1 aggregate GBDT, A1/A2 stability logistic/GBDT,
  A3/A4 stability+margin logistic/GBDT), parent safety gates
  (coverage >= 0.75, ND unsafe <= 0.20, wrong <= 0.05, AMBIGUOUS unsafe
  < 0.25) + frozen improvement criterion.  All 9 inherited parent
  contracts recorded by exact SHA256 inside the rebind contract.
- Seeds: new namespace `M3-S25-R1-A-GRAD`, 960 unique units, 0 duplicate
  seeds, 0 historical collision, 0 truth-stream collision.

## Preflight (arm_a_preflight): PASS 17/17

parent/truth-terminal HEAD ancestry, PANEL-FROZEN, frozen panel SHA,
manifest SHA + identity, 30 configs / 30-30-30-30, protected reserve 18
untouched, 960 seeds, zero collisions, destination empty, path/disk PASS
(exact production layout), GroupKFold(5)/(4) class/config feasibility
(24/6 configs per fold, all classes present), all inherited contract
hashes, ARM_A = NO, ARM_B = NO, truth gate CLOSED.

## Persistence + route (tested with mocked trials; real simulator calls 0)

Per trial: STARTED durable -> 20k sampling -> aggregate gradient record
(ONLINE fields only; truth-label leakage rejected by the validator) ->
instrumentation sidecar -> sidecar SHA verify -> record SHA verify ->
COMPLETE.  Restart requires exactly one STARTED + one COMPLETE + both
artifact hashes; any other state => M3-S25-R1-X => STOP => NO REPLAY.
Mocked full route green: 960/960 durable COMPLETE, consumption
19,200,000, restart-safe skip, truth unseal ONLY after completeness,
grouped evaluation, synthetic M3-S25-R1-A / B-GATE / X verdicts.

## Gates

```text
M3_S25_R1_TRUTH_AUTHORIZED = NO   (CLOSED / EXERCISED at truth terminal
                                   HEAD 089c6a48c73831fbd95e2caa5b21137b485080aa)
M3_S25_R1_ARM_A_AUTHORIZED = NO
M3_S25_R1_ARM_B_AUTHORIZED = NO
VALUE / RARITY / M3-Q      = BLOCKED
```

STOP.  Awaiting the Arm-A execution-readiness audit; only an explicit
human `M3_S25_R1_ARM_A_AUTHORIZED: YES` commit enables
`python scripts/run_m3s25r1.py arm_a_execute`.


## A0.1 amendment (conditional-PASS fixes; zero sampling)

Applied per the human's A0.1 instruction (scientific rebind CONDITIONALLY
PASS):

1. Scientific-code hash lock completed: `scientific_code_hashes` now
   covers `m3s25r1/arm_a.py`, `m3s25r1/arm_a_eval.py`,
   `m3ml0/evaluation.py`, `m3ml0/threshold.py`, `m3ml0/features.py`,
   `m3ml0/models.py`, `m3pi1vr0/persistence.py` (plus the existing
   estimator/persistence chain); a test proves the entries exist and
   match current bytes.
2. Frozen panel FILE SHA enforced at runtime: `EXPECTED_PANEL_FILE_SHA`
   = `136830a2bdd5291882564e6bba922161ae519139573921161c50f7dfa20950ff`
   AND the rebind contract's `panel.panel_file_sha256`; the stored
   `panel_sha256` field alone is not trusted.  Tamper test: modifying an
   s2 field while keeping `panel_sha256` unchanged hard-fails
   `arm_a_execute` before STARTED/simulator.
3. Sidecar durability made genuinely transactional: temp -> write ->
   flush -> fsync(file) -> atomic rename -> fsync(parent dir) -> SHA256
   verify, before the JSON record may reach durable COMPLETE; injected
   tests for BEFORE_FSYNC / AFTER_FSYNC_BEFORE_RENAME / AFTER_VERIFY all
   yield CONSUMED_INVALID with no false COMPLETE.
4. B1 comparator restored to the EXACT ML0 B3 aggregate GBDT feature set
   (`S1, g_hat, abs_g_hat, SE_g, CI_width, s2, curvature_c, ESS_grad,
   gradient_valid`) with the frozen ML0 HistGradientBoosting grid;
   `curvature_c` is online frozen config metadata persisted in every
   trial record (truth-free route); the ML0 feature-contract and
   model-grid SHAs are recorded in the rebind contract.
5. Success eligibility restricted: B0/B1 are comparators only; only
   A1-A4 may trigger `M3-S25-R1-A`; a B1-only-compliant scenario
   deterministically yields `M3-S25-R1-B-GATE` (synthetic regression
   test).
6. Seed-audit proof repaired: explicit `len(vals) == 960 and
   len(set(vals)) == 960` conditions; type-consistent per-stream pools
   (integer seed VALUES vs integer pools, seed_key TUPLES vs tuple
   pools) with explicit zero-collision proof against M3-S2S Arm-A
   candidate seeds, M3-S2S truth seeds, M3-S25-R1 truth seeds, all
   recorded historical scientific seed pools and the CF1N manifests.
   The 960-unit seed manifest stayed BYTE-IDENTICAL
   (`20cbe999...`).
7. Secondary-metrics contract completed: OOF probabilities are preserved
   from the nested CV and ROC-AUC / PR-AUC / Brier / ECE are reported on
   scored OOF rows; report-only, never affecting the primary verdict.

Updated rebind contract sha: `f02fc399834e5d950d46f29d8e609f1b8df3697097
a705db6de8d5474c6085d6` (pin updated in the runner; the panel truth
manifest and the 960-unit seed manifest are unchanged byte-for-byte).

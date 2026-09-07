# M3-S25-R1-A0 Taskbook -- Arm-A Rebind & Execution Readiness

> **Provenance.** Frozen from the human-issued instruction text received
> 2026-09-06 (post-truth / post-panel scientific audit PASS).  Parent
> terminal HEAD `089c6a48c73831fbd95e2caa5b21137b485080aa`.  ZERO-SAMPLING
> stage: no simulator call is allowed in A0.

## Gates (unchanged through A0)

```text
M3_S25_R1_ARM_A_AUTHORIZED = NO
M3_S25_R1_ARM_B_AUTHORIZED = NO
VALUE / RARITY / M3-Q      = BLOCKED
```

## 1. Frozen panel preserved

The 120 panel state IDs, ranking, source-stage composition, panel
selection and panel SHA
`2bdb9a91562cc44c6dd9e1d1c0d49f8950e531c3108ea61b6d03eb0c153ce2b8`
are not modified.

## 2. Tracked panel truth manifest (evaluation-only, sealed)

`configs/phase_m3s25r1/m3s25r1_panel_truth_manifest.json` records for all
120 states: state_id, truth, config_id, source_stage, s2, u, rank,
truth_artifact_hash; bound to the panel body SHA and the exact
`m3s25r1_panel.json` file SHA.  Mechanical verification: 120 unique
states, exact state-ID equality, 30/30/30/30, 30 configs, source mix
R1 83 / S2S 37, all 30 SHRINK from M3-S25-R1.  NOT used during Arm-A
scientific sampling; sealed until all 960 Arm-A trials are durable
COMPLETE.

## 3. Rebind of the frozen M3-S2S Arm-A contracts (no retuning)

estimator `hyptraj.m3d.adaptation.gradient_decision`; alpha_p = 0.5; S1
threshold 5.4417199447782; 120 states x 8 replicates x 20,000 samples =
960 trials = 19,200,000 (no top-up); instrumentation m3s2s_instr_v1
(N_BOOTSTRAP = 500; a_vec/resp/sq/strata lossless sidecars); parent
feature family, grouped nested-CV (outer GroupKFold(5) / inner
GroupKFold(4), groups = config_id), model family, safety gates and Arm-A
success criterion.  Every inherited parent contract is recorded by exact
SHA256.  New namespace `M3-S25-R1-A-GRAD`; 960-unit seed manifest with
zero duplicate seeds, zero historical collision, zero truth-stream
collision.

## 4-5. Arm-A execution + persistence implemented BEFORE authorization

Stages `arm_a_preflight` / `arm_a_execute` / `arm_a_evaluate`.  Per trial:
STARTED durable -> 20k simulator sampling -> aggregate gradient record ->
instrumentation sidecar -> sidecar SHA verification -> record SHA
verification -> COMPLETE.  Sampling without durable COMPLETE =>
CONSUMED_INVALID => M3-S25-R1-X => STOP => NO REPLAY.  Restart requires
exactly one STARTED + one COMPLETE + both artifact hashes.  The sampling
execution view carries online-required fields only -- never truth labels.

## 6-8. Preflight, evaluation, scientific gates

Preflight verifies (zero sampling): parent/truth terminal HEADs, PANEL-
FROZEN, panel SHA, manifest SHA, 120-state identity, 30 configs,
30/30/30/30, protected reserve 18 untouched, 960 seeds, zero historical
seed collision, destination empty, path/disk PASS, GroupKFold(5)/(4)
class/config feasibility, all inherited contract hashes, ARM_A = NO,
ARM_B = NO.  Evaluation unseals the truth manifest ONLY after 960/960
durable COMPLETE and runs the frozen parent development comparison
(frozen S1; aggregate-feature GBDT baseline; stability logistic/GBDT;
stability + practical-margin logistic/GBDT) with no test-fold threshold
or delta tuning.  Parent gates: coverage >= 0.75, ND unsafe <= 0.20,
wrong <= 0.05, AMBIGUOUS unsafe < 0.25 + the frozen improvement criterion.

R1-local terminal names (scientific gate unchanged):
`M3-S25-R1-A` (Arm-A development success; Arm B NOT RUN),
`M3-S25-R1-B-GATE` (valid completion, no compliant candidate; STOP for
separate Arm-B review), `M3-S25-R1-X` (integrity failure).

## 9. Truth gate closure (closure-only)

`M3_S25_R1_TRUTH_AUTHORIZED = NO`, status CLOSED / EXERCISED, truth
terminal HEAD `089c6a48c73831fbd95e2caa5b21137b485080aa` -- prevents
accidental truth re-entry.

## 10-11. Tests, regression, commit

Mocked full-route tests (preflight -> 960 mocked trials -> sidecar
durability -> truth unseal after completeness -> grouped evaluation ->
synthetic A / B-GATE verdicts) with real simulator calls = 0; A0 tests +
relevant S2S/R1 parent tests + broad regression + hash lock; commit and
push without squashing; STOP for the Arm-A execution-readiness audit.

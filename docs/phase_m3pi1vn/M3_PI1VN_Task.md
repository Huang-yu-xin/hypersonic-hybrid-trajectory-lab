# RareTopo M3-PI1VN — Independent Fresh-Panel Finite-Action Information Validation

## First Valid Clean Test of the Frozen <=2x V1 Hypothesis After WCF1-A

Current corrected frontier:

```text
M3-CF1N    CF1N-A
M3-CF2     CF2-A
M3-PI1V    PI1V-X
M3-PI1VR0  PI1VR0-CAP-B
M3-WA1     WA1-X
M3-WA1R    WA1R-B
M3-WCF1    WCF1-A
```

WCF1-A restored fresh W diversity:

```text
WCF1 new physical configs = 6
NEW_W_CONFIG = 6/6
ROBUST_NEW_W_CONFIG = 5/6

WCF1 labels:
WIDEN = 11
AMBIGUOUS = 1

combined fresh W pool:
W states = 26
distinct W configs = 11

fresh 8W/8S/8ND development panel:
frozen = YES
pilot exposure = 0
probe exposure = 0
```

The exact fresh-panel hash must be read from:

```text
results/phase_m3wcf1/summary/
m3wcf1_fresh_development_panel_hash.json
```

PI1VN reruns the original frozen scientific hypothesis unchanged:

```text
gradient sign chooses direction
+
low-budget paired finite-action V1 chooses DEPLOY / ABSTAIN
```

Frozen protocol:

```text
R = 8 repetitions/state
B_grad = 20,000 samples/trial
BASE probe = 10,000
selected-action probe = 10,000
probe total = 20,000 <= B_grad
total online information <= 2 * B_grad
20 paired CRN batches

V1 = (-0.01 - r_hat) / SE(r_hat)

gates:
wrong-direction <= 5%
deployable coverage >= 75%
ND unsafe <= 20%

unique-information rule:
S1 does not full-pass
OR
V1 best-safe coverage - S1 best-safe coverage >= 5 percentage points
```

No scientific choice may be altered because of PI1V Attempt-2 diagnostic results.

---

## 1. Parent requirements

Before any simulator call verify:

```text
WCF1 = WCF1-A

WCF1 P_ref:
6/6 COMPLETE
consumed-invalid = 0

WCF1 reference:
12/12 COMPLETE
consumed-invalid = 0

fresh panel:
24 states
8 W
8 S
8 ND
pilot exposure = 0
probe exposure = 0

PI1V valid verdict = PI1V-X
PI1V Attempt-2 = DIAGNOSTIC_ONLY

WA1 = WA1-X
WA1R = WA1R-B

all retired states/seeds remain retired
```

Any mismatch:

```text
PI1VN-X
STOP
```

---

## 2. Fresh panel is immutable

Use exactly:

```text
results/phase_m3wcf1/summary/
m3wcf1_fresh_development_panel.csv
```

and the committed hash from:

```text
m3wcf1_fresh_development_panel_hash.json
```

Recompute before any pilot and require exact match.

No panel regeneration, replacement, or rebalancing.

---

## 3. Frozen panel composition

Require exactly:

```text
W = 8
S = 8
ND = 8
TOTAL = 24
```

ND truth remains:

```text
HOLD + AMBIGUOUS
```

Report subtype counts only; do not change them.

---

## 4. Freshness firewall

Every panel state must satisfy:

```text
pilot exposure before PI1VN = 0
probe exposure before PI1VN = 0
threshold replay exposure = 0
```

Create:

```text
m3pi1vn_panel_freshness_audit.csv
```

Any exposure:

```text
PI1VN-X
STOP
```

---

## 5. Protected reserve firewall

All WCF1 unselected valid states remain:

```text
PILOT_PROTECTED_RESERVE
```

PI1VN must not run on them:

```text
gradient pilot
S1 feature
V1 probe
threshold replay
```

Create:

```text
m3pi1vn_reserve_firewall_audit.json
```

Also protect UC2R confirmation and all other untouched reserves.

---

## 6. Retired/invalid data firewall

Explicitly exclude:

```text
original CF2 24-state pilot-exposed panel
PI1V Attempt-1 trials
PI1V Attempt-2 replay trials
WA1 consumed-invalid candidate
all retired PI1V seeds
all retired WA1 seeds
```

The following Attempt-2 diagnostics are forbidden as design input:

```text
V1 best-safe coverage
S1 best-safe coverage
AMBIGUOUS unsafe behavior
gradient wrong-direction result
selected thresholds
V1/S1 score distributions
LOSO/LOCO results
```

---

## 7. Scientific protocol must be identical

PI1VN is not a revised method.

It inherits exactly:

```text
gradient estimator
gradient sign convention
R
B_grad
probe allocation
probe pairing
V1 estimator
V1 SE estimator
S1 definition
metric denominators
threshold enumeration
threshold tie-break
5% / 75% / 20% gates
5pp unique-information rule
```

---

## 8. Frozen repetition and gradient protocol

Use:

```text
R = 8
B_grad = 20,000
```

Total trials:

```text
24 × 8 = 192
```

Use committed sign rule:

```text
g_hat < 0 => WIDEN
g_hat > 0 => SHRINK
```

Use exact historical zero/invalid handling.

If gradient invalid:

```text
ABSTAIN
```

Finite-action information may never flip direction.

---

## 9. Direction sanity gate

Evaluate Sign-No-Abstain on 16 deployable states:

```text
8 W
8 S
```

Frozen gate:

```text
wrong-direction <= 5%
```

If fail:

```text
PI1VN-D
```

No threshold may rescue direction failure.

---

## 10. Fresh seeds

Use new namespaces:

```text
M3-PI1VN-GRAD
M3-PI1VN-PROBE
```

Freeze all exact seeds for 192 trials before first simulator call.

Require zero collision with all prior stages.

Create:

```text
m3pi1vn_seed_manifest.json
m3pi1vn_seed_manifest_hash.json
```

---

## 11. Frozen finite-action probe

For each valid gradient-selected action probe only:

```text
BASE = 10,000
selected action = 10,000
```

Total probe:

```text
20,000 = B_grad
```

Hence total online information per valid trial:

```text
20,000 gradient + 20,000 probe = 40,000 = 2×B_grad
```

Use 20 paired CRN batches.

Never probe the opposite action.

Forbidden:

```text
budget ladder
second probe
larger probe near threshold
state-specific budget
adaptive retry
```

---

## 12. Relative change and V1

Use:

```text
r_hat = M2_hat(selected) / M2_hat(BASE) - 1
```

Frozen improvement margin:

```text
-0.01
```

Frozen V1:

```text
V1 = (-0.01 - r_hat) / SE(r_hat)
```

The exact SE estimator must match the committed original PI1 protocol hash.

Any estimator mismatch:

```text
PI1VN-PREREG-X
STOP
```

---

## 13. Invalid probe rule

If finite-action estimate, SE, or V1 is invalid:

```text
ABSTAIN
```

No imputation, replay, or larger sample.

---

## 14. V1 policy

For threshold tau:

```text
if gradient invalid:
    ABSTAIN
elif probe invalid:
    ABSTAIN
elif V1 >= tau:
    DEPLOY gradient-selected action
else:
    ABSTAIN
```

V1 never changes direction.

---

## 15. S1 comparator

Use exact inherited S1 from the same fresh gradient trial.

No extra samples.

No new feature engineering.

No threshold imported from invalid PI1V.

---

## 16. Same-data comparison

V1 and S1 use:

```text
same 24 fresh states
same 192 trials
same gradient realizations
same corrected truth
```

Only V1 receives the extra paired finite-action probe.

---

## 17. Frozen metric contract

Use exact G2/UC3 semantics for:

```text
wrong-direction rate
deployable coverage
ND unsafe deployment rate
```

Do not redefine denominators.

Freeze metric implementation hash before pilot.

---

## 18. Primary gates

Unchanged:

```text
wrong-direction <= 5%
deployable coverage >= 75%
ND unsafe <= 20%
```

---

## 19. Deterministic threshold rule

Use the frozen PI1V rule:

```text
deploy-all-valid sentinel
all midpoints between sorted unique finite scores
abstain-all sentinel
```

or exact equivalent committed implementation.

No threshold value from invalid PI1V may be reused.

---

## 20. Threshold selection objective

For V1 and S1 separately:

```text
1. enumerate all deterministic threshold candidates
2. compute wrong / coverage / unsafe
3. retain wrong <=5% and unsafe <=20%
4. maximize deployable coverage
5. tie-break:
   lower unsafe
   lower wrong
   more conservative threshold
   canonical numeric order
```

No manual threshold selection.

---

## 21. Full-pass definitions

```text
V1_FULL_PASS
= exists threshold with:
  wrong <=5%
  coverage >=75%
  unsafe <=20%

S1_FULL_PASS
= same three gates
```

---

## 22. Best safety-compliant coverage

For each score family:

```text
BEST_SAFE_COVERAGE
= max coverage over thresholds satisfying:
  wrong <=5%
  unsafe <=20%
```

---

## 23. Unique-information criterion

V1 is uniquely justified iff:

```text
V1_FULL_PASS = YES
```

and either:

```text
A. S1_FULL_PASS = NO
```

or:

```text
B.
V1_BEST_SAFE_COVERAGE
-
S1_BEST_SAFE_COVERAGE
>= 0.05
```

No change to 5 percentage points.

---

## 24. Verdicts

### PI1VN-A — VALID INDEPENDENT SUPPORT FOR V1

Require:

```text
direction sanity PASS
V1_FULL_PASS = YES
unique-information criterion = YES
```

Next:

```text
M3-PI2
untouched confirmation-panel preregistration
```

### PI1VN-B — V1 PASSES BUT IS NOT UNIQUELY JUSTIFIED

Require:

```text
direction sanity PASS
V1_FULL_PASS = YES
unique-information criterion = NO
```

No automatic confirmation.

If S1_FULL_PASS is validly observed, a separate S1-route decision may follow.

### PI1VN-C — VALID NEGATIVE RESULT AT <=2x

Require:

```text
direction sanity PASS
V1_FULL_PASS = NO
```

This is the first valid negative result for the frozen <=2x V1 hypothesis.

If additionally:

```text
S1_FULL_PASS = YES
```

then a separately preregistered S1 confirmation route may be considered.

### PI1VN-D — DIRECTION FAILURE

If Sign-No-Abstain wrong-direction exceeds 5%.

### PI1VN-X — INVALID

For panel, freshness, seed, budget, protocol, metric, threshold, persistence, or post-outcome adaptation violations.

Verdict priority:

```text
INVALID -> PI1VN-X
direction fail -> PI1VN-D
V1 full-pass false -> PI1VN-C
unique-information false -> PI1VN-B
otherwise -> PI1VN-A
```

---

## 25. Hardened persistence

For each trial:

```text
1. validate filesystem-safe path
2. durable STARTED ledger
3. execute gradient calculation
4. execute finite-action probe if applicable
5. build canonical non-circular payload
6. validate schema
7. compute hashes
8. temp write
9. flush + fsync
10. atomic rename
11. fsync parent directory
12. verify final durable record/hash
13. ledger COMPLETE
```

If scientific calculation begins but durable COMPLETE fails:

```text
trial = CONSUMED_INVALID
PI1VN-X
STOP
```

No replay.

---

## 26. Trial canonical record

Path:

```text
results/phase_m3pi1vn/trials/<safe_state_id>/<rep_id>.json
```

Required fields:

```text
state_id
rep_id
truth
config_id
gradient seed
gradient estimate/features
gradient valid
selected action
probe seed
BASE probe stats
selected-action probe stats
probe valid
r_hat
SE_r_hat
V1
S1
sample counts
opposite_action_probe_samples = 0
panel hash
protocol hashes
canonical payload hash
file hash
```

---

## 27. Exact sample accounting

Maximum gradient samples:

```text
192 × 20,000 = 3,840,000
```

Maximum probe samples:

```text
192 × 20,000 = 3,840,000
```

Maximum total:

```text
7,680,000 samples
```

If invalid gradients skip probes, actual cost may be lower.

---

## 28. Required analysis

Create:

```text
m3pi1vn_direction_sanity.json
m3pi1vn_v1_trials.csv
m3pi1vn_s1_trials.csv
m3pi1vn_v1_threshold_frontier.csv
m3pi1vn_s1_threshold_frontier.csv
m3pi1vn_selected_thresholds.json
m3pi1vn_primary_metrics.json
m3pi1vn_information_gain.json
m3pi1vn_state_level_policy_audit.csv
m3pi1vn_truth_stratified_metrics.json
m3pi1vn_family_stratified_metrics.json
m3pi1vn_loso_diagnostic.csv
m3pi1vn_loco_diagnostic.csv
m3pi1vn_persistence_audit.json
m3pi1vn_final_verdict.json
```

---

## 29. Diagnostics

Report separately:

```text
W coverage/wrong
S coverage/wrong
HOLD unsafe
AMBIGUOUS unsafe
```

Also report by physical-source family when represented:

```text
legacy/current corrected
CF1N replacement
WCF1 new
```

LOSO and LOCO are diagnostic only.

They may not alter threshold, formula, or verdict.

---

## 30. No natural-prevalence claim

The panel is engineered as 8W/8S/8ND.

Do not interpret overall deployment fraction or class frequency as natural prevalence.

Use wording:

```text
reference-stratified development metrics
```

---

## 31. No confirmation in PI1VN

Regardless of verdict:

```text
protected reserve pilot = 0
confirmation trials = 0
```

PI1VN ends at development evidence.

VALUE, RARITY, and M3-Q remain BLOCKED.

---

## 32. Required pre-pilot outputs

```text
results/phase_m3pi1vn/summary/
m3pi1vn_source_manifest.json
m3pi1vn_parent_audit.json
m3pi1vn_panel_hash_audit.json
m3pi1vn_panel_freshness_audit.csv
m3pi1vn_reserve_firewall_audit.json
m3pi1vn_retired_data_firewall.json
m3pi1vn_protocol_inheritance_audit.json
m3pi1vn_gradient_contract.json
m3pi1vn_probe_contract.json
m3pi1vn_v1_estimator_contract.json
m3pi1vn_s1_contract.json
m3pi1vn_metric_contract.json
m3pi1vn_threshold_contract.json
m3pi1vn_seed_manifest.json
m3pi1vn_seed_manifest_hash.json
m3pi1vn_persistence_contract.json
m3pi1vn_prereg_hashes.json
```

---

## 33. Required trial outputs

```text
results/phase_m3pi1vn/trials/
<safe_state_id>/<rep_id>.json

trial_ledger.jsonl
trial_manifest.json
```

Exactly 192 durable trial records if the stage completes validly.

---

## 34. Required figures

At minimum:

```text
PI1VN-1 V1 distribution by W/S/ND
PI1VN-2 S1 distribution by W/S/ND
PI1VN-3 V1 risk-coverage frontier
PI1VN-4 S1 risk-coverage frontier
PI1VN-5 V1 vs S1 best-safe coverage
PI1VN-6 per-state deployment/unsafe heatmap
PI1VN-7 directional wrong rate by state
PI1VN-8 LOSO threshold stability
PI1VN-9 HOLD vs AMBIGUOUS unsafe behavior
PI1VN-10 metrics by physical-family source
```

No figure-driven retuning.

---

## 35. Required docs

```text
docs/phase_m3pi1vn/
M3_PI1VN_Task.md
M3_PI1VN_Parent_WCF1_Audit.md
M3_PI1VN_Fresh_Panel_Audit.md
M3_PI1VN_Frozen_Protocol_Inheritance.md
M3_PI1VN_Pregistration.md
M3_PI1VN_Human_Approval.md
M3_PI1VN_Pilot_Execution_Audit.md
M3_PI1VN_V1_Analysis.md
M3_PI1VN_S1_Comparator.md
M3_PI1VN_Robustness_Diagnostics.md
M3_PI1VN_Reserve_Firewall_Audit.md
M3_PI1VN_Final_Report.md
```

---

## 36. Required configs

```text
configs/phase_m3pi1vn/
m3pi1vn_panel.json
m3pi1vn_gradient_protocol.json
m3pi1vn_probe_protocol.json
m3pi1vn_v1_estimator.json
m3pi1vn_s1_contract.json
m3pi1vn_metric_contract.json
m3pi1vn_threshold_contract.json
m3pi1vn_seeds.json
m3pi1vn_persistence.json
m3pi1vn_gates.json
```

---

## 37. Required tests

Parent/freshness:

```text
test_m3pi1vn_parent_wcf1a
test_m3pi1vn_panel_hash_matches_wcf1
test_m3pi1vn_panel_exact24
test_m3pi1vn_panel_exact8w8s8nd
test_m3pi1vn_panel_pilot_zero_pretrial
test_m3pi1vn_panel_probe_zero_pretrial
test_m3pi1vn_no_panel_replacement
test_m3pi1vn_reserve_overlap_zero
test_m3pi1vn_reserve_pilot_zero
```

Retired/invalid data:

```text
test_m3pi1vn_pi1v_primary_x
test_m3pi1vn_no_attempt2_v1_input
test_m3pi1vn_no_attempt2_s1_input
test_m3pi1vn_no_old_cf2_panel
test_m3pi1vn_no_wa1_consumed_state
test_m3pi1vn_no_retired_seed_reuse
```

Gradient:

```text
test_m3pi1vn_R_exact8
test_m3pi1vn_Bgrad_exact20000
test_m3pi1vn_gradient_estimator_hash
test_m3pi1vn_gradient_sign_rule
test_m3pi1vn_gradient_invalid_rule
test_m3pi1vn_no_direction_redefinition
```

Probe:

```text
test_m3pi1vn_base_probe_10000
test_m3pi1vn_selected_probe_10000
test_m3pi1vn_probe_total_20000
test_m3pi1vn_total_cost_le2x
test_m3pi1vn_paired_crn20
test_m3pi1vn_selected_action_only
test_m3pi1vn_opposite_probe_zero
test_m3pi1vn_no_adaptive_probe
```

V1/S1:

```text
test_m3pi1vn_rhat_definition
test_m3pi1vn_margin_minus1pct
test_m3pi1vn_v1_formula_exact
test_m3pi1vn_se_estimator_hash
test_m3pi1vn_invalid_probe_abstains
test_m3pi1vn_v1_controls_deploy_only
test_m3pi1vn_v1_never_changes_direction
test_m3pi1vn_s1_definition_hash
test_m3pi1vn_s1_same_gradient_data
test_m3pi1vn_s1_no_probe_data
test_m3pi1vn_no_invalid_s1_threshold_reuse
```

Metrics/thresholds:

```text
test_m3pi1vn_wrong_gate_5pct
test_m3pi1vn_coverage_gate_75pct
test_m3pi1vn_unsafe_gate_20pct
test_m3pi1vn_threshold_candidate_rule
test_m3pi1vn_threshold_tiebreak
test_m3pi1vn_best_safe_coverage
test_m3pi1vn_unique_gain_5pp
test_m3pi1vn_verdict_priority
```

Persistence/boundaries:

```text
test_m3pi1vn_safe_path
test_m3pi1vn_started_before_simulator
test_m3pi1vn_non_circular_hash
test_m3pi1vn_atomic_persistence
test_m3pi1vn_final_hash_verify
test_m3pi1vn_consumed_invalid_no_replay
test_m3pi1vn_no_frozen_overwrite
test_m3pi1vn_all192_complete_or_invalid
test_m3pi1vn_no_confirmation
test_m3pi1vn_reserve_unexposed
test_m3pi1vn_value_blocked
test_m3pi1vn_rarity_blocked
test_m3pi1vn_m3q_blocked
```

Full regression:

```text
all collected tests covered
zero failures
```

---

## 38. Suggested commit sequence

```text
1. PI1VN task + WCF1 parent audit
2. fresh-panel hash audit
3. panel/reserve freshness firewall
4. retired/invalid-data firewall
5. protocol inheritance audit
6. freeze exact R/B_grad/probe contract
7. freeze V1/S1/metric/threshold hashes
8. fresh seed manifest
9. hardened persistence prereg
10. pre-run full regression
11. human approval
12. transactional 192-trial execution
13. persistence audit
14. direction sanity
15. V1/S1 score tables
16. deterministic threshold frontiers
17. freeze selected thresholds
18. information-gain verdict
19. state/truth/family diagnostics
20. LOSO/LOCO diagnostics
21. reserve firewall re-audit
22. final verdict
23. full regression
```

---

## 39. Mandatory pre-pilot STOP report

```text
M3-PI1VN PREREG STATUS:
COMPLETE / BLOCKED

PARENT:
WCF1 = WCF1-A
PI1V valid verdict = PI1V-X

FRESH DEVELOPMENT PANEL:
states = 24
W = 8
S = 8
ND = 8
hash =
hash matches WCF1 = YES
pilot exposure = 0
probe exposure = 0

PROTECTED RESERVE:
states =
pilot exposure = 0

INVALID / RETIRED DATA:
PI1V Attempt-2 used = NO
original CF2 panel used = NO
WA1 consumed state used = NO
retired seeds used = NO

GRADIENT:
R = 8
B_grad = 20000
sign rule = g_hat<0 WIDEN / g_hat>0 SHRINK
protocol hash =

PROBE:
BASE = 10000
selected action = 10000
total = 20000
paired CRN batches = 20
opposite action = 0
adaptive probe = NO

ONLINE COST:
per valid trial max = 40000
<=2x B_grad = YES

V1:
formula = (-0.01-r_hat)/SE(r_hat)
margin = -0.01
estimator hash =
SE estimator hash =

S1:
definition hash =
same gradient data = YES
probe information used = NO

METRICS:
wrong semantics frozen = YES
coverage semantics frozen = YES
unsafe semantics frozen = YES

GATES:
wrong <=5%
coverage >=75%
unsafe <=20%

UNIQUE INFORMATION:
S1 full-pass absent
OR
V1 best-safe coverage - S1 best-safe coverage >=5pp

THRESHOLD RULE:
deterministic = YES
invalid PI1V threshold reused = NO

SEEDS:
gradient namespace = M3-PI1VN-GRAD
probe namespace = M3-PI1VN-PROBE
planned trials = 192
collisions = 0
hash-locked = YES

PERSISTENCE:
hardened = ENABLED
STARTED-before-simulator = YES
non-circular hash = YES
consumed-invalid replay = FORBIDDEN

MAX SAMPLES:
gradient = 3840000
probe = 3840000
total = 7680000

CONFIRMATION:
authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN PI1VN
```

Then STOP.

---

## 40. Mandatory final report

```text
M3-PI1VN STATUS:
COMPLETE / INVALID

PARENT:
WCF1 = WCF1-A

FRESH PANEL:
states = 24
hash verified = YES
panel changed = NO

TRIALS:
expected = 192
complete =
consumed-invalid =

SAMPLES:
gradient =
probe =
total =
<=2x = PASS/FAIL

DIRECTION:
deployable trials = 128
valid gradient =
wrong =
wrong rate =
gate <=5% = PASS/FAIL

V1:
valid scores =
selected threshold =
wrong =
coverage =
unsafe =
V1_FULL_PASS =
best safety-compliant coverage =

S1:
selected threshold =
wrong =
coverage =
unsafe =
S1_FULL_PASS =
best safety-compliant coverage =

COMPARISON:
coverage gain =
gain >=5pp =
unique-information criterion = PASS/FAIL

TRUTH STRATA:
W coverage/wrong =
S coverage/wrong =
HOLD unsafe =
AMBIGUOUS unsafe =

ROBUSTNESS:
state-level audit = COMPLETE
LOSO = COMPLETE
LOCO = COMPLETE
family-stratified = COMPLETE

PERSISTENCE:
hashes = PASS/FAIL
ledger = PASS/FAIL
manifest = PASS/FAIL

INVALID / RETIRED DATA:
PI1V Attempt-2 used = NO
retired states used = NO
retired seeds used = NO

PROTECTED RESERVE:
pilot exposure = 0

CONFIRMATION:
trials = 0
authorized = NO

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

FINAL VERDICT:
PI1VN-A /
PI1VN-B /
PI1VN-C /
PI1VN-D /
PI1VN-X

SECONDARY ROUTE SIGNAL:
if PI1VN-C:
  S1_FULL_PASS = YES/NO

NEXT:
M3-PI2 /
S1 confirmation preregistration decision /
method redesign /
direction rethink /
stop

FULL REGRESSION:
...
```

---

## 41. Route logic after valid PI1VN

```text
PI1VN-A
→ M3-PI2 untouched confirmation for frozen V1 threshold

PI1VN-B
→ no V1 confirmation;
  consider S1 route only if valid S1_FULL_PASS

PI1VN-C + S1_FULL_PASS
→ V1 <=2x hypothesis validly rejected;
  separately preregister S1 untouched confirmation

PI1VN-C + S1 not full-pass
→ abstention-information method redesign

PI1VN-D
→ direction estimator rethink

PI1VN-X
→ incident recovery; no scientific route choice
```

---

## 42. Final principle

The repair chain has completed its purpose:

```text
PI1V-X
→ remove contaminated development evidence
→ rebuild fresh reference supply
→ restore W count
→ restore W config diversity
→ freeze a new untouched 8W/8S/8ND panel
```

WCF1-A means there is no remaining reference-supply justification for changing
the experiment.

PI1VN must answer the original question exactly once:

```text
fresh panel
+
fresh seeds
+
same gradient
+
same 10k/10k finite-action probe
+
same V1
+
same S1
+
same 5% / 75% / 20% gates
+
same 5pp information criterion
=
first valid clean verdict on the <=2x V1 hypothesis
```

No further reference augmentation is justified before this test.

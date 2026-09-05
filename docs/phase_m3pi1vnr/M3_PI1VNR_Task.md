# RareTopo M3-PI1VNR — Independent Recovery on a Second Fresh Development Panel

## Zero-New-Reference Recovery + Clean Re-Test of the Frozen <=2x V1 Hypothesis After PI1VN-X

Current corrected frontier:

```text
M3-CF1N     CF1N-A
M3-CF2      CF2-A
M3-PI1V     PI1V-X
M3-PI1VR0   PI1VR0-CAP-B
M3-WA1      WA1-X
M3-WA1R     WA1R-B
M3-WCF1     WCF1-A
M3-PI1VN    PI1VN-X
```

PI1VN invalid incident:

```text
planned trials = 192
durable COMPLETE before incident = 136
failing trial index = 137 / 192
failing state = cf1n_new_005_wa1_w_s2_1p4142135624
rep = 0
scientific sampling completed = YES
durable COMPLETE = NO
status = CONSUMED_INVALID
trials 138–192 = NEVER STARTED
```

Root cause:

```text
run_uuid embedded an encoded long state ID
+
temp filename embedded that information again
->
full Windows path ~265 chars
->
path write failure beyond effective MAX_PATH
```

Frozen rule applied correctly:

```text
CONSUMED_INVALID
-> PI1VN-X
-> STOP
-> NO REPLAY
```

The 136 durable trial records and the failed trial are diagnostic only. They
do not support V1/S1 thresholds, verdicts, or route selection.

M3-PI1VNR performs a clean recovery with **zero new reference samples**.

Recovery principle:

```text
quarantine PI1VN
-> retire the entire PI1VN 24-state development panel
-> retire all PI1VN seeds
-> use only still-unexposed corrected high-budget reserve
-> zero-sim freeze a SECOND fresh 8W/8S/8ND panel
-> exhaustively preflight all 192 real paths
-> use entirely new seeds
-> rerun the ORIGINAL frozen <=2x V1 hypothesis unchanged
```

---

## 1. Scientific status of PI1VN

Freeze:

```text
PI1VN valid verdict = PI1VN-X
PI1VN primary V1 result = UNAVAILABLE
PI1VN primary S1 result = UNAVAILABLE
PI1VN direction result = UNAVAILABLE
136 durable completed trials = DIAGNOSTIC_ONLY
failed trial = CONSUMED_INVALID
```

No numerical diagnostic result from PI1VN may enter PI1VNR design.

---

## 2. Retire the full PI1VN panel

Retire all 24 states from future:

```text
primary development
threshold selection
confirmation
```

Create:

```text
results/phase_m3pi1vnr/summary/m3pi1vnr_retired_pi1vn_panel.csv
```

All 24 receive:

```text
status = PILOT_EXPOSED_RETIRED
future development use = NO
future confirmation use = NO
```

This is the conservative no-optionality rule and is consistent with PI1VR0.

---

## 3. Retire all PI1VN seeds

Retire every seed under:

```text
M3-PI1VN-GRAD
M3-PI1VN-PROBE
```

including seeds for trials never started.

Create:

```text
m3pi1vnr_retired_pi1vn_seed_manifest.json
```

No PI1VNR seed may collide.

---

## 4. Quarantine PI1VN outputs

Create:

```text
m3pi1vnr_pi1vn_quarantine_manifest.json
```

Quarantine as diagnostic-only:

```text
136 durable trial records
failed-trial incident record
trial ledger
trial manifest
any partial score tables
any V1/S1 outputs
any figures/logs
```

Do not delete them and do not use them scientifically.

---

## 5. Incident forensics

Create:

```text
m3pi1vnr_incident_forensics.json
```

Record:

```text
root cause class = PATH_LENGTH
failed state
failed rep
full failing path length
temp basename length
run_uuid representation
STARTED-before-simulator = YES
scientific sampling completed = YES
durable COMPLETE = NO
CONSUMED_INVALID durable ledger = YES
replay performed = NO
```

---

## 6. Hard scientific firewall

Forbidden throughout PI1VNR:

```text
use PI1V Attempt-2 metrics
use PI1VN partial metrics
use any partial V1/S1 score from 136 completed trials
use PI1VN threshold/frontier
reuse PI1VN 24-state panel
reuse retired PI1V/PI1VN seeds
reuse WA1 consumed-invalid state
modify V1 formula
modify S1 definition
modify R
modify B_grad
modify 10k/10k probe allocation
modify paired-CRN count
modify 5% / 75% / 20% gates
modify 5pp unique-information rule
add probe budget ladder
add adaptive probe
add new high-budget reference
run confirmation
run VALUE
run RARITY
run M3-Q
```

---

## 7. Zero-new-reference principle

Require:

```text
new P_ref samples = 0
new finite-action reference samples = 0
```

If a second fresh panel cannot be built from untouched reserve:

```text
PI1VNR-CAP-B
STOP
```

No automatic new reference stage inside PI1VNR.

---

## 8. Candidate reference universe

A state is eligible for the second fresh panel iff:

```text
corrected event semantics
full-event probability domain
durable COMPLETE
hash-valid
pilot exposure = 0
probe exposure = 0
threshold replay exposure = 0
not in original CF2 retired panel
not in PI1VN retired panel
not WA1 consumed-invalid
not CF1 invalid
not pre-ER1 contaminated
not separately protected UC2R confirmation if still reserved
```

---

## 9. Fresh reserve exposure audit

Create:

```text
m3pi1vnr_fresh_reserve_audit.csv
```

Fields:

```text
state_id
truth
config_id
physical_family
s2
source_stage
source_region
high_budget_valid
pilot_exposure
probe_exposure
threshold_replay_exposure
retired_reason
eligible_second_panel
```

No online score fields.

---

## 10. Redacted selection view

Create:

```text
m3pi1vnr_selection_view.csv
```

Allowed only:

```text
state_id
truth
config_id
physical_family
s2
source_stage
source_region
stable_config_flag
canonical_bank_order
```

Forbidden:

```text
V1
S1
gradient confidence
gradient error
r_hat
SE
M2 effect magnitude
threshold distance
PI1VN completion status
PI1V/PI1VN diagnostic metrics
```

Freeze hash before panel selection.

---

## 11. Second fresh panel target

Exact target:

```text
8 WIDEN
8 SHRINK
8 NON-DEPLOYABLE
= 24 states
```

where:

```text
ND = HOLD + AMBIGUOUS
```

---

## 12. Diversity gates

W:

```text
8 W
distinct configs >= 6
max 2/config
```

S:

```text
8 S
distinct configs >= 6
max 2/config
```

Prefer 8 distinct stable configs if untouched reserve permits.

ND:

```text
8 ND
distinct configs >= 6 OR source regions >= 6
max 2/config
```

Whole panel:

```text
24 unique state IDs
pilot exposure = 0
probe exposure = 0
threshold replay exposure = 0
```

---

## 13. Deterministic selector

Use only:

```text
truth
config diversity
physical-family diversity
source-region diversity
s2 spacing
canonical order
```

Priority:

```text
1. maximize distinct config count
2. maximize family/region coverage
3. enforce max2/config
4. maximize log-s2 spacing
5. lower canonical bank order
6. lexical state_id
```

No manual post-selector state swap.

---

## 14. Panel capacity gate

Define:

```text
M3PI1VNR-PANEL-1
```

PASS iff exact 8W/8S/8ND and all diversity/freshness gates pass.

If fail:

```text
PI1VNR-CAP-B
STOP
```

No simulator.

---

## 15. Freeze second fresh panel

If capacity passes create:

```text
m3pi1vnr_fresh_development_panel.csv
m3pi1vnr_fresh_development_panel_hash.json
```

This becomes the only development panel for PI1VNR.

All unselected valid states remain:

```text
PILOT_PROTECTED_RESERVE
```

---

## 16. Path hardening: fixed-length run_uuid

For every PI1VNR trial:

```text
run_uuid
```

must be bounded and must not contain state ID.

Preferred:

```text
uuid4().hex
```

Freeze a maximum run_uuid length.

---

## 17. Bounded state slug and temp basename

Final path may use:

```text
<short-readable-prefix>-<fixed-digest>
```

for the state directory.

Full original state ID stays inside the JSON payload.

Recommended limits:

```text
state slug <= 64 chars
temp basename <= 80 chars
```

The persistence module, not only the caller, must enforce these bounds.

---

## 18. Conservative full-path limit

Before simulator, compute every actual path under the real working directory.

Default recovery gate:

```text
full path length <= 220 chars
```

for:

```text
final record path
temp record path
ledger/lock path if applicable
```

unless an explicitly tested Windows long-path API contract is used instead.

---

## 19. Exhaustive 192-trial path preflight

For:

```text
24 states × 8 reps = 192 trials
```

materialize every future path string without simulator calls.

Create:

```text
m3pi1vnr_path_preflight.csv
```

Fields:

```text
state_id
rep_id
safe_state_slug
run_uuid_template_length
final_path
final_path_length
temp_path_example
temp_path_length
limit
PASS
```

Require:

```text
192/192 PASS
```

---

## 20. Worst-case synthetic path tests

Test synthetic state IDs longer than every actual panel state.

Also test:

```text
state ID lengths 40 / 80 / 160 / 320
run_uuid lengths 32 / 64 / 256
deep work directory
near-limit final path
near-limit temp path
over-limit path
```

Over-limit cases must fail **before simulator mock invocation**.

---

## 21. Module-level safety requirement

If caller supplies an overlong run_uuid, the persistence layer must:

```text
truncate/hash into bounded token
```

or reject before scientific execution.

Path-length errors must become pre-scientific validation failures, never
post-sampling persistence failures.

---

## 22. Hardened transaction order

For every trial:

```text
1. construct bounded paths
2. validate full path lengths
3. verify destination path preconditions
4. durable STARTED ledger
5. scientific gradient calculation
6. scientific finite-action probe if applicable
7. build canonical non-circular payload
8. schema validate
9. compute hashes
10. temp write
11. flush + fsync
12. atomic rename
13. fsync parent directory
14. verify final durable record/hash
15. ledger COMPLETE
```

---

## 23. Persistence gate

Define:

```text
M3PI1VNR-PERSIST-1
```

PASS iff:

```text
fixed-length run_uuid PASS
bounded state slug PASS
bounded temp basename PASS
actual 192-path preflight 192/192 PASS
worst-case path PASS
over-limit fails before simulator PASS
STARTED-before-simulator PASS
non-circular hash PASS
atomic persistence PASS
CONSUMED_INVALID no-replay PASS
frozen-artifact overwrite guard PASS
synthetic E2E PASS
pre-run regression PASS
```

If fail:

```text
PI1VNR-INFRA-B
STOP
```

No simulator.

---

## 24. Frozen scientific protocol

If preflight passes, use exactly:

```text
R = 8
B_grad = 20,000
sign rule = inherited UC3
BASE probe = 10,000
selected-action probe = 10,000
20 paired CRN batches
V1 frozen formula
S1 frozen definition
frozen metric semantics
frozen threshold rule
5% / 75% / 20% gates
5pp unique-information criterion
```

No scientific change from PI1VN.

---

## 25. Gradient rule

Use:

```text
g_hat < 0 => WIDEN
g_hat > 0 => SHRINK
```

with exact committed invalid/zero handling.

If gradient invalid:

```text
ABSTAIN
```

Finite-action information never changes direction.

---

## 26. Direction sanity gate

Evaluate Sign-No-Abstain on:

```text
8 W + 8 S = 16 deployable states
```

Frozen gate:

```text
wrong-direction <= 5%
```

If fail:

```text
PI1VNR-D
```

---

## 27. Fresh seed namespaces

Use:

```text
M3-PI1VNR-GRAD
M3-PI1VNR-PROBE
```

Freeze all 192 exact trial seeds before simulator.

Require zero collision with every prior namespace.

---

## 28. Frozen probe protocol

For valid selected action:

```text
BASE = 10,000
selected action = 10,000
```

Total probe:

```text
20,000 = B_grad
```

Total online information:

```text
40,000 = 2 × B_grad
```

Use 20 paired CRN batches.

Opposite-action probe:

```text
0
```

No adaptive probe or budget ladder.

---

## 29. Frozen V1 and S1

Use:

```text
r_hat = M2_hat(selected) / M2_hat(BASE) - 1
margin = -0.01
V1 = (-0.01 - r_hat) / SE(r_hat)
```

Use exact inherited SE estimator hash.

Use exact inherited S1 from the same gradient data.

No previous threshold may be reused.

---

## 30. Same-data comparison

V1 and S1 use:

```text
same second fresh 24-state panel
same 192 trial identities
same gradient realizations
same corrected truth
```

Only V1 gets the paired finite-action probe.

---

## 31. Frozen gates

```text
wrong <= 5%
coverage >= 75%
unsafe <= 20%
```

---

## 32. Deterministic threshold rule

Use exact frozen enumeration:

```text
deploy-all-valid sentinel
midpoints between sorted unique finite scores
abstain-all sentinel
```

or the exact committed equivalent.

For each score family:

```text
retain wrong<=5% and unsafe<=20%
maximize coverage
tie-break:
  lower unsafe
  lower wrong
  more conservative threshold
  canonical numeric order
```

---

## 33. Full-pass and unique-information rule

```text
V1_FULL_PASS
S1_FULL_PASS
```

require all three gates.

Define best-safe coverage as max coverage over thresholds with:

```text
wrong<=5%
unsafe<=20%
```

V1 is uniquely justified iff:

```text
V1_FULL_PASS = YES
```

and:

```text
S1_FULL_PASS = NO
```

or:

```text
V1 best-safe coverage - S1 best-safe coverage >= 5pp
```

---

## 34. Verdicts

### PI1VNR-A

```text
direction PASS
V1_FULL_PASS = YES
unique-information criterion = PASS
```

Meaning:

```text
VALID INDEPENDENT SUPPORT FOR V1 AT <=2x COST
```

Next: untouched confirmation preregistration.

### PI1VNR-B

```text
direction PASS
V1_FULL_PASS = YES
unique-information criterion = FAIL
```

V1 can pass but extra finite-action information is not justified.

### PI1VNR-C

```text
direction PASS
V1_FULL_PASS = NO
```

Meaning:

```text
VALID INDEPENDENT NEGATIVE RESULT:
V1 INSUFFICIENT AT FROZEN <=2x COST
```

If S1_FULL_PASS=YES, a separate S1 confirmation route may then be considered.

### PI1VNR-D

Direction sanity fails.

### PI1VNR-CAP-B

Second fresh panel cannot be built.

### PI1VNR-INFRA-B

Preflight persistence/path gate fails before sampling.

### PI1VNR-X

Any scientific-run integrity failure after execution begins.

Verdict priority:

```text
scientific invalid -> PI1VNR-X
infrastructure preflight fail -> PI1VNR-INFRA-B
panel capacity fail -> PI1VNR-CAP-B
direction fail -> PI1VNR-D
V1 full-pass false -> PI1VNR-C
unique-information fail -> PI1VNR-B
otherwise -> PI1VNR-A
```

---

## 35. Exact trial/sample count

If scientific execution is authorized:

```text
24 × 8 = 192 trials
```

Maximum gradient samples:

```text
192 × 20,000 = 3,840,000
```

Maximum probe samples:

```text
192 × 20,000 = 3,840,000
```

Maximum online total:

```text
7,680,000
```

New high-budget reference samples:

```text
0
```

---

## 36. Trial canonical record

Use bounded paths:

```text
results/phase_m3pi1vnr/trials/<bounded_state_slug>/<rep_id>.json
```

Payload includes full state ID and:

```text
rep_id
truth
config_id
gradient seed
gradient estimate
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
second-panel hash
protocol hashes
payload hash
file hash
```

---

## 37. Required analysis

Create:

```text
m3pi1vnr_persistence_audit.json
m3pi1vnr_direction_sanity.json
m3pi1vnr_v1_trials.csv
m3pi1vnr_s1_trials.csv
m3pi1vnr_v1_threshold_frontier.csv
m3pi1vnr_s1_threshold_frontier.csv
m3pi1vnr_selected_thresholds.json
m3pi1vnr_primary_metrics.json
m3pi1vnr_information_gain.json
m3pi1vnr_state_level_policy_audit.csv
m3pi1vnr_truth_stratified_metrics.json
m3pi1vnr_family_stratified_metrics.json
m3pi1vnr_loso_diagnostic.csv
m3pi1vnr_loco_diagnostic.csv
m3pi1vnr_reserve_firewall_postrun.json
m3pi1vnr_final_verdict.json
```

Diagnostics may not retune anything.

---

## 38. Required docs

```text
docs/phase_m3pi1vnr/
M3_PI1VNR_Task.md
M3_PI1VNR_PI1VN_Incident_Forensics.md
M3_PI1VNR_Scientific_Quarantine.md
M3_PI1VNR_Fresh_Panel_Recovery.md
M3_PI1VNR_Path_Hardening.md
M3_PI1VNR_Frozen_Protocol_Inheritance.md
M3_PI1VNR_Pregistration.md
M3_PI1VNR_Human_Approval.md
M3_PI1VNR_Pilot_Execution_Audit.md
M3_PI1VNR_V1_Analysis.md
M3_PI1VNR_S1_Comparator.md
M3_PI1VNR_Robustness_Diagnostics.md
M3_PI1VNR_Final_Report.md
```

---

## 39. Required tests

Retirement/quarantine:

```text
test_m3pi1vnr_parent_pi1vn_x
test_m3pi1vnr_pi1vn_primary_unavailable
test_m3pi1vnr_all24_pi1vn_panel_retired
test_m3pi1vnr_no_pi1vn_panel_reuse
test_m3pi1vnr_all_pi1vn_seeds_retired
test_m3pi1vnr_no_partial_pi1vn_metrics_used
test_m3pi1vnr_no_invalid_pi1v_metrics_used
```

Fresh panel:

```text
test_m3pi1vnr_zero_new_reference
test_m3pi1vnr_selection_view_redacted
test_m3pi1vnr_exact8w8s8nd
test_m3pi1vnr_w_configs_ge6
test_m3pi1vnr_w_max2_per_config
test_m3pi1vnr_s_configs_ge6
test_m3pi1vnr_s_max2_per_config
test_m3pi1vnr_nd_diversity
test_m3pi1vnr_panel_unique
test_m3pi1vnr_panel_pilot_zero
test_m3pi1vnr_panel_probe_zero
test_m3pi1vnr_panel_hash
test_m3pi1vnr_remaining_reserve_protected
```

Path hardening:

```text
test_m3pi1vnr_run_uuid_bounded
test_m3pi1vnr_run_uuid_no_state_id
test_m3pi1vnr_state_slug_bounded
test_m3pi1vnr_temp_basename_bounded
test_m3pi1vnr_actual_192_paths_preflight
test_m3pi1vnr_all_actual_paths_le220
test_m3pi1vnr_worst_case_long_state
test_m3pi1vnr_overlimit_fails_before_simulator
test_m3pi1vnr_caller_long_uuid_safened_module_level
```

Persistence:

```text
test_m3pi1vnr_started_before_simulator
test_m3pi1vnr_non_circular_hash
test_m3pi1vnr_atomic_persistence
test_m3pi1vnr_final_hash_verify
test_m3pi1vnr_consumed_invalid_no_replay
test_m3pi1vnr_frozen_overwrite_guard
test_m3pi1vnr_synthetic_e2e
```

Scientific protocol:

```text
test_m3pi1vnr_R_exact8
test_m3pi1vnr_Bgrad_exact20000
test_m3pi1vnr_gradient_sign_rule
test_m3pi1vnr_base_probe_10000
test_m3pi1vnr_selected_probe_10000
test_m3pi1vnr_probe_total_20000
test_m3pi1vnr_paired_crn20
test_m3pi1vnr_opposite_probe_zero
test_m3pi1vnr_v1_formula_exact
test_m3pi1vnr_s1_definition_hash
test_m3pi1vnr_metric_contract_hash
test_m3pi1vnr_threshold_contract_hash
```

Gates/boundaries:

```text
test_m3pi1vnr_wrong_gate_5pct
test_m3pi1vnr_coverage_gate_75pct
test_m3pi1vnr_unsafe_gate_20pct
test_m3pi1vnr_best_safe_coverage
test_m3pi1vnr_unique_gain_5pp
test_m3pi1vnr_verdict_priority
test_m3pi1vnr_no_confirmation
test_m3pi1vnr_reserve_unexposed
test_m3pi1vnr_value_blocked
test_m3pi1vnr_rarity_blocked
test_m3pi1vnr_m3q_blocked
```

Full regression:

```text
all collected tests covered
zero failures
```

---

## 40. Suggested commit sequence

```text
1. PI1VNR task + PI1VN-X audit
2. quarantine PI1VN outputs
3. retire full PI1VN panel + seeds
4. untouched high-budget reserve audit
5. redacted second-panel selection view
6. second-panel capacity gate
7. freeze second 8W/8S/8ND panel + hash
8. protect remaining reserve
9. bounded path contract
10. exhaustive 192-path preflight
11. worst-case path/failure injection
12. persistence gate
13. frozen protocol inheritance audit
14. new PI1VNR seed freeze
15. pre-run regression
16. human approval
17. transactional 192-trial execution
18. persistence audit
19. direction sanity
20. V1/S1 frontiers
21. freeze selected thresholds
22. information-gain verdict
23. robustness diagnostics
24. reserve firewall re-audit
25. final verdict
26. full regression
```

---

## 41. Mandatory pre-run STOP report

```text
M3-PI1VNR PREREG STATUS:
COMPLETE / BLOCKED

PARENT:
PI1VN = PI1VN-X
WCF1 = WCF1-A
PI1V = PI1V-X

PI1VN INCIDENT:
planned trials = 192
durable complete = 136
consumed-invalid = 1
never started = 55
replay performed = NO

PI1VN PANEL:
states = 24
retired = 24
reused in PI1VNR = 0

PI1VN SEEDS:
retired = YES
reused = 0

INVALID DIAGNOSTICS:
PI1V Attempt-2 used = NO
PI1VN partial metrics used = NO

REFERENCE:
new P_ref samples = 0
new high-budget reference samples = 0

FRESH RESERVE:
eligible W =
eligible S =
eligible HOLD =
eligible AMB =
eligible ND =

SECOND FRESH PANEL:
states = 24
W = 8
S = 8
ND = 8
W configs =
S configs =
ND configs =
ND regions =
hash =
pilot exposure = 0
probe exposure = 0

M3PI1VNR-PANEL-1:
PASS

REMAINING PROTECTED RESERVE:
states =
pilot exposure = 0

PATH CONTRACT:
run_uuid max length =
state slug max length =
temp basename max length =
full path limit = 220

ACTUAL PATH PREFLIGHT:
trials = 192
PASS = 192
FAIL = 0
max observed final path length =
max observed temp path length =

WORST-CASE PATH TEST:
PASS

OVER-LIMIT FAILURE:
before simulator = YES

PERSISTENCE:
STARTED-before-simulator = PASS
atomic = PASS
non-circular hash = PASS
no replay = PASS
synthetic E2E = PASS

M3PI1VNR-PERSIST-1:
PASS

SCIENTIFIC PROTOCOL:
R = 8
B_grad = 20000
BASE probe = 10000
selected probe = 10000
paired CRN = 20
V1 unchanged = YES
S1 unchanged = YES
metrics unchanged = YES
threshold rule unchanged = YES

GATES:
wrong <=5%
coverage >=75%
unsafe <=20%
unique gain >=5pp or S1 no-full-pass

SEEDS:
gradient namespace = M3-PI1VNR-GRAD
probe namespace = M3-PI1VNR-PROBE
planned trials = 192
collisions = 0
hash locked = YES

MAX ONLINE SAMPLES:
gradient = 3840000
probe = 3840000
total = 7680000

CONFIRMATION:
authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN PI1VNR
```

Then STOP.

---

## 42. Mandatory final report

```text
M3-PI1VNR STATUS:
COMPLETE / INVALID

SECOND FRESH PANEL:
states = 24
W = 8
S = 8
ND = 8
hash verified = YES
panel changed = NO

RETIRED DATA:
PI1VN panel reused = NO
PI1VN seeds reused = NO
PI1VN diagnostics used = NO
PI1V diagnostics used = NO

TRIALS:
expected = 192
complete =
consumed-invalid =

PATH SAFETY:
preflight 192/192 = PASS
runtime path failures = 0

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

TRUTH:
W coverage/wrong =
S coverage/wrong =
HOLD unsafe =
AMB unsafe =

ROBUSTNESS:
state audit = COMPLETE
LOSO = COMPLETE
LOCO = COMPLETE
family = COMPLETE

PERSISTENCE:
hashes = PASS/FAIL
ledger = PASS/FAIL
manifest = PASS/FAIL

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
PI1VNR-A /
PI1VNR-B /
PI1VNR-C /
PI1VNR-D /
PI1VNR-CAP-B /
PI1VNR-INFRA-B /
PI1VNR-X

SECONDARY ROUTE SIGNAL:
if PI1VNR-C:
  S1_FULL_PASS = YES/NO

NEXT:
M3-PI2 /
S1 confirmation preregistration /
method redesign /
direction rethink /
fresh-reference decision /
infrastructure repair /
stop

FULL REGRESSION:
...
```

---

## 43. Final principle

The third infrastructure incident must not weaken the scientific standard.

The correct recovery is:

```text
PI1VN-X
-> quarantine partial outputs
-> retire full PI1VN panel + all PI1VN seeds
-> zero new reference samples
-> construct a second fresh 8W/8S/8ND panel
-> exhaustively preflight all 192 real paths
-> fixed-length UUID / bounded state slug / bounded temp name
-> fresh PI1VNR seeds
-> exact unchanged <=2x V1/S1 experiment
-> complete 192/192 or invalidate
```

The objective is not to make the code eventually finish. The objective is to
obtain the first scientifically valid verdict while preserving every frozen
failure boundary.

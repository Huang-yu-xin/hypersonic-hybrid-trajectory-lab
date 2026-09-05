# RareTopo M3-WA1 — Fresh WIDEN Reference Augmentation

## Reference-First Recovery of Fresh 8W/8S/8ND Development Capacity After PI1VR0-CAP-B

Current corrected frontier:

```text
M3-CF1N    CF1N-A
M3-CF2     CF2-A
M3-PI1V    PI1V-X
M3-PI1VR0  PI1VR0-CAP-B
```

PI1VR0 audited the untouched reserve:

```text
WIDEN = 7
SHRINK = 29
HOLD = 13
AMBIGUOUS = 21
ND = 34
```

Therefore the only count bottleneck is:

```text
WIDEN shortage = 1 state
```

M3-WA1 is a narrowly scoped, reference-first WIDEN augmentation.

It does not test V1, S1, controller safety, value, rarity, or M3-Q.

It may not use any numerical result from invalid PI1V Attempt 1/2.

---

## 1. Stage invariants

```text
gradient pilot = 0
finite-action probe = 0
V1 threshold = null
S1 threshold = null
protected confirmation pilot = 0

VALUE = BLOCKED
RARITY = BLOCKED
M3-Q = BLOCKED
```

---

## 2. Hard firewall

Forbidden:

```text
use PI1V Attempt-2 V1/S1 scores
use invalid-run gradient confidence
use invalid-run r_hat/SE/frontiers
reuse original 24 CF2 development states
reuse retired PI1V seeds
pilot any of the 70 protected reserve states
target SHRINK or ND augmentation
change 8W/8S/8ND target
lower W diversity gate after outcomes
adaptive candidate addition after outcomes
replace failed candidates after outcomes
run discovery then refine around success
run gradient/V1 pilot
run S1 confirmation
run value/rarity/M3-Q
```

---

## 3. Parent audit

Must verify:

```text
PI1VR0 final verdict = PI1VR0-CAP-B

valid PI1V verdict = PI1V-X
PI1V Attempt-2 metrics = DIAGNOSTIC_ONLY

original 24 CF2 states = retired
old PI1V seeds = retired

70 reserve states = verified untouched
fresh reserve W = 7
fresh reserve S = 29
fresh reserve ND = 34

M3PI1VR0-PERSIST-1 = PASS
```

Any mismatch:

```text
WA1-X
STOP
```

---

## 4. Hardened persistence

Inherit PI1VR0 contract:

```text
filesystem-safe IDs
durable STARTED ledger before simulator
temp write
flush + fsync
schema validation
sha256
atomic rename
parent-directory fsync
final hash verification
ledger COMPLETE
no same-stage replay after CONSUMED_INVALID
```

---

## 5. Re-audit current W reserve diversity

Create:

```text
results/phase_m3wa1/summary/m3wa1_existing_w_reserve_audit.csv
```

Report:

```text
7 untouched W states
distinct W configs
max W/config
physical families represented
s2 values
```

The eventual fresh panel still requires:

```text
W = 8
W distinct configs >= 6
W max/config <= 2
```

WA1 success is not merely “new W >=1”.

---

## 6. Build valid historical W-support inventory

Create:

```text
m3wa1_w_support_inventory.csv
```

from corrected high-budget durable states only.

Fields:

```text
state_id
config_id
physical_family
s2
truth
source_stage
grid_or_interval_index
pilot_exposed
probe_exposed
P_ref_hash
canonical_hash
```

Exclude:

```text
CF1 invalid data
pre-ER1 contaminated data
CONSUMED_INVALID records
```

Pilot-exposed states may only serve as historical support-location evidence if
their high-budget truth was validly established before exposure; they can
never enter the fresh panel.

---

## 7. W-support config eligibility

A config may generate WA1 candidates only if corrected high-budget truth has:

```text
>=2 adjacent confirmed WIDEN states
```

on an ordered s2 grid/interval.

Single isolated W states are not enough.

---

## 8. Candidate generation

For each adjacent confirmed W pair:

```text
(s2_i, s2_j)
```

generate at most one fresh log-midpoint:

\[
s2_{\rm mid}
=
\exp\left(\frac{\log s2_i+\log s2_j}{2}\right).
\]

Requirements:

```text
strictly inside the confirmed-W interval
fresh full-state identity
no previous sampling at same identity
```

If collision occurs, that pair yields no candidate.

Do not perturb the midpoint.

---

## 9. Candidate pool

Create:

```text
m3wa1_candidate_pool.csv
```

Fields:

```text
candidate_id
config_id
physical_family
left_W_state
right_W_state
left_s2
right_s2
candidate_s2
fresh_identity
P_ref_source
canonical_order
```

No outcome-strength or invalid PI1V fields.

---

## 10. P_ref dependency audit

Create:

```text
m3wa1_pref_dependency_audit.json
```

Determine from code whether P_ref is:

```text
CONFIG_SPECIFIC
or
FULL_STATE_SPECIFIC
```

If config-specific and corrected/durable:

```text
reuse the valid config P_ref
```

If state-specific:

```text
generate new P_ref for every WA1 candidate
```

Do not guess.

---

## 11. Freeze exactly 8 WA1 candidates

Before any outcome, select exactly:

```text
8 candidate states
```

Rationale:

```text
only one additional W is required,
but candidate labels are uncertain;
8 fixed candidates provide redundancy without adaptive extension.
```

No ninth candidate may be added after outcomes.

---

## 12. Candidate diversity selector

Deterministic priority:

```text
1. maximize distinct physical config count
2. prioritize configs that improve feasibility of final W >=6-config gate
3. max 2 WA1 candidates/config
4. maximize physical-family coverage
5. maximize s2 spacing
6. canonical order
```

No effect size and no invalid PI1V score.

Pre-run hard gate:

```text
candidate count = 8
distinct configs >= 4
max candidates/config <= 2
```

Prefer >=6 configs if available.

If even 4 configs are impossible:

```text
WA1-PRE-B
STOP
```

---

## 13. Freeze candidate manifest

Create:

```text
m3wa1_candidate_manifest.csv
m3wa1_candidate_manifest_hash.json
```

Freeze before simulation.

No substitutions after hash lock.

---

## 14. Reference protocol

Use one-shot high-budget reference:

```text
500,000 samples / arm
3 arms:
BASE
WIDEN
SHRINK
20 paired CRN batches
```

No 100k discovery stage.

Per candidate:

```text
1,500,000 samples
```

Eight candidates:

```text
12,000,000 finite-action samples
```

P_ref cost is additional only if dependency audit requires new P_ref.

---

## 15. Corrected semantics

Use:

```text
event = topology != S0
full-event probability domain
BASE/WIDEN/SHRINK unchanged
-1% improvement threshold
±3% HOLD band
5% direction margin
ESS >=20
invalid rules unchanged
```

---

## 16. Seeds

Use:

```text
M3-WA1-REF
```

If new P_ref is needed:

```text
M3-WA1-PREF
```

All seeds:

```text
fresh
hash-locked
disjoint from all prior stages
```

---

## 17. Transactional persistence

For each candidate:

```text
validate safe path
durable STARTED
simulate
temp serialize
flush
fsync
schema validate
sha256
atomic rename
parent fsync
verify final hash
ledger COMPLETE
```

If sampling starts and persistence fails:

```text
CONSUMED_INVALID
WA1-X
STOP
```

No replay.

---

## 18. WA1 labels

Each durable candidate receives:

```text
WIDEN
SHRINK
HOLD
AMBIGUOUS
INVALID
```

Define:

```text
K_WA1_W
K_WA1_S
K_WA1_H
K_WA1_AMB
K_WA1_INVALID
```

Only W contributes to the WA1 primary supply target, but all valid non-W
records may remain protected reference evidence.

---

## 19. Combined fresh W pool

After WA1:

```text
existing untouched reserve W (7)
+
new WA1 W states
```

Create:

```text
m3wa1_combined_fresh_w_pool.csv
```

Do not include retired original CF2 states.

---

## 20. W feasibility test

The combined fresh W pool must contain a deterministic selectable subset with:

```text
exactly 8 W
distinct configs >=6
max 2/config
```

This is the actual WA1 success condition.

---

## 21. Full fresh-panel capacity recheck

If W feasibility passes, combine with untouched reserve:

```text
S = 29
ND = 34
```

plus any new valid WA1 non-W references.

Re-run the PI1VR0 fresh-panel selector under the same frozen rules:

```text
8 W
8 S
8 ND
```

No pilot information may enter.

---

## 22. Freeze fresh panel if feasible

Create:

```text
m3wa1_fresh_development_panel.csv
m3wa1_fresh_development_panel_hash.json
```

Require:

```text
24 states
8 W
8 S
8 ND
all unique
pilot exposure = 0
probe exposure = 0
```

Allowed selector inputs:

```text
truth
config_id
physical family
s2
source region
canonical order
pilot exposure
```

Forbidden:

```text
PI1V Attempt-2 V1/S1
gradient confidence
r_hat
SE
effect magnitude
threshold results
```

---

## 23. Protect all unselected states

All valid high-budget states not selected into the new panel remain:

```text
PILOT_PROTECTED_RESERVE
```

Create:

```text
m3wa1_remaining_protected_reserve.csv
m3wa1_remaining_reserve_summary.json
```

---

## 24. Verdicts

### WA1-A — FRESH DEVELOPMENT CAPACITY RESTORED

Require:

```text
reference execution valid
combined W exact-8 feasibility PASS
full 8W/8S/8ND capacity PASS
fresh panel frozen
```

Next:

```text
M3-PI1VN
Independent Fresh-Panel Finite-Action Information Validation
```

### WA1-B — W AUGMENTATION INSUFFICIENT

If valid execution completes but W feasibility still fails.

No adaptive second batch inside WA1.

### WA1-PRE-B — CANDIDATE FAMILY TOO NARROW

If the pre-run 8-candidate / >=4-config gate cannot be met.

### WA1-X — INVALID

For provenance/hash/seed/persistence/leakage/post-outcome adaptation failure.

Verdict priority:

```text
INVALID -> WA1-X
pre-run candidate gate fail -> WA1-PRE-B
valid execution but W feasibility fail -> WA1-B
otherwise -> WA1-A
```

---

## 25. No V1/S1 route decision

WA1 does not decide between V1 and S1.

Even if new references resemble the invalid Attempt-2 diagnostics, those
diagnostics remain non-primary.

If WA1-A, PI1VN must rerun the original frozen <=2x PI1V hypothesis unchanged.

---

## 26. Required outputs

Pre-run:

```text
results/phase_m3wa1/summary/
m3wa1_source_manifest.json
m3wa1_parent_audit.json
m3wa1_existing_w_reserve_audit.csv
m3wa1_w_support_inventory.csv
m3wa1_candidate_pool.csv
m3wa1_pref_dependency_audit.json
m3wa1_selector_contract.json
m3wa1_candidate_manifest.csv
m3wa1_candidate_manifest_hash.json
m3wa1_seed_manifest.json
m3wa1_persistence_contract.json
m3wa1_prereg_hashes.json
```

Execution:

```text
results/phase_m3wa1/reference/<candidate_id>.json
reference_ledger.jsonl
reference_manifest.json
```

Final capacity:

```text
m3wa1_reference_summary.json
m3wa1_persistence_audit.json
m3wa1_combined_fresh_w_pool.csv
m3wa1_w_feasibility.json
m3wa1_full_panel_capacity.json
m3wa1_fresh_development_panel.csv
m3wa1_fresh_development_panel_hash.json
m3wa1_remaining_protected_reserve.csv
m3wa1_remaining_reserve_summary.json
m3wa1_final_verdict.json
```

---

## 27. Required docs

```text
docs/phase_m3wa1/
M3_WA1_Task.md
M3_WA1_Parent_Audit.md
M3_WA1_W_Support_Design.md
M3_WA1_Pregistration.md
M3_WA1_Human_Approval.md
M3_WA1_Reference_Execution_Audit.md
M3_WA1_Fresh_Panel_Capacity.md
M3_WA1_Final_Report.md
```

---

## 28. Required tests

Parent/leakage:

```text
test_m3wa1_parent_pi1vr0capb
test_m3wa1_pi1v_primary_x
test_m3wa1_no_invalid_pi1v_scores
test_m3wa1_old24_not_candidates
test_m3wa1_reserve_not_piloted
test_m3wa1_no_s1_confirmation
test_m3wa1_no_v1_pilot
```

Candidate design:

```text
test_m3wa1_adjacent_confirmed_w_support_only
test_m3wa1_log_midpoint_definition
test_m3wa1_midpoint_strictly_interior
test_m3wa1_candidate_identity_fresh
test_m3wa1_candidate_exact8
test_m3wa1_candidate_configs_ge4
test_m3wa1_candidate_max2_per_config
test_m3wa1_selector_deterministic
test_m3wa1_no_effect_strength_selection
test_m3wa1_no_adaptive_candidate_extension
```

P_ref/reference:

```text
test_m3wa1_pref_dependency_audited
test_m3wa1_pref_reuse_only_if_config_specific
test_m3wa1_new_pref_if_state_dependent
test_m3wa1_ref_budget_500k
test_m3wa1_ref_three_arms
test_m3wa1_ref_crn20
test_m3wa1_ref_corrected_semantics
test_m3wa1_ref_seed_disjoint
```

Persistence:

```text
test_m3wa1_safe_path
test_m3wa1_started_before_simulator
test_m3wa1_atomic_persistence
test_m3wa1_hash_verify
test_m3wa1_consumed_invalid_no_replay
test_m3wa1_no_frozen_overwrite
```

Capacity:

```text
test_m3wa1_combined_w_pool
test_m3wa1_w_exact8_feasibility
test_m3wa1_w_configs_ge6
test_m3wa1_w_max2_per_config
test_m3wa1_full_panel_8w8s8nd
test_m3wa1_fresh_panel_unique
test_m3wa1_fresh_panel_pilot_zero
test_m3wa1_fresh_panel_probe_zero
test_m3wa1_fresh_panel_hash
test_m3wa1_remaining_reserve_protected
```

Boundaries:

```text
test_m3wa1_gradient_zero
test_m3wa1_probe_zero
test_m3wa1_threshold_null
test_m3wa1_confirmation_zero
test_m3wa1_value_blocked
test_m3wa1_rarity_blocked
test_m3wa1_m3q_blocked
```

Full regression:

```text
all collected tests covered
zero failures
```

---

## 29. Mandatory pre-run STOP report

```text
M3-WA1 PREREG STATUS:
COMPLETE / BLOCKED

PARENT:
PI1VR0 = PI1VR0-CAP-B
PI1V valid verdict = PI1V-X

INVALID PI1V DATA:
used in candidate design = NO
used in selector = NO

EXISTING FRESH RESERVE:
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34

EXISTING FRESH W:
distinct configs =
max/config =

W SUPPORT INVENTORY:
eligible adjacent-W configs =
eligible adjacent-W pairs =

P_REF:
dependency = CONFIG_SPECIFIC / STATE_SPECIFIC
reuse/new rule frozen = YES

WA1 CANDIDATES:
count = 8
distinct configs =
max/config =
IDs =
manifest hash =

CANDIDATE RULE:
adjacent confirmed W only = YES
log midpoint = YES
fresh identities = YES
adaptive extension = FORBIDDEN

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
finite-action samples = 12000000

SEEDS:
namespace = M3-WA1-REF
collision = 0
hash-locked = YES

PERSISTENCE:
PI1VR0 hardened contract = ENABLED
STARTED before simulator = YES
consumed-invalid replay = FORBIDDEN

SUCCESS TARGET:
combined fresh W subset:
  exact W = 8
  configs >=6
  max/config <=2

full fresh panel:
  8W / 8S / 8ND

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation = NOT AUTHORIZED

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN WA1 REFERENCE
```

---

## 30. Mandatory final report

```text
M3-WA1 STATUS:
COMPLETE / INVALID

REFERENCE:
candidates = 8
complete =
consumed-invalid =
finite-action samples =

LABELS:
new W =
new S =
new HOLD =
new AMB =
new INVALID =

PERSISTENCE:
hashes = PASS/FAIL
ledger = PASS/FAIL
manifest = PASS/FAIL

COMBINED FRESH W:
old untouched W = 7
new W =
total W =
distinct configs =

W FEASIBILITY:
exact 8 selectable = YES/NO
configs >=6 = PASS/FAIL
max2/config = PASS/FAIL

FULL FRESH PANEL:
feasible = YES/NO
W = 8/NA
S = 8/NA
ND = 8/NA
hash =

INVALID PI1V RESULTS:
used = NO

REMAINING PROTECTED RESERVE:
states =
pilot exposure = 0

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation authorized = NO

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

FINAL VERDICT:
WA1-A /
WA1-B /
WA1-PRE-B /
WA1-X

NEXT:
M3-PI1VN /
broader W-reference expansion /
redesign /
stop

FULL REGRESSION:
...
```

---

## 31. Final principle

PI1VR0 showed an extremely specific fresh-development shortage:

```text
W = 7
S = 29
ND = 34
```

The minimal scientific response is:

```text
do not touch S
do not touch ND
do not use invalid PI1V scores
do not alter V1/S1

find valid adjacent corrected W-support intervals
→ freeze 8 fresh interior midpoint candidates
→ one-shot 500k/arm reference
→ recheck W diversity
→ freeze a fresh 8W/8S/8ND panel
→ only then run independent PI1VN
```

This repairs reference capacity without converting the invalid PI1V replay
into a hidden route-selection signal.

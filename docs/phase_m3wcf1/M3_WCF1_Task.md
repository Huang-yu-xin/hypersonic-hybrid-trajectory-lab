# RareTopo M3-WCF1 — Prospective Fresh Physical-Configuration WIDEN Expansion
## Broader W-Reference Family Expansion After WA1R-B

Current corrected frontier:

```text
M3-CF1N    CF1N-A
M3-CF2     CF2-A
M3-PI1V    PI1V-X
M3-PI1VR0  PI1VR0-CAP-B
M3-WA1     WA1-X
M3-WA1R    WA1R-B
```

WA1R completed validly:

```text
recovery reference = 8/8 COMPLETE
consumed-invalid = 0

labels:
WIDEN = 8
SHRINK = 0
HOLD = 0
AMBIGUOUS = 0
INVALID = 0
```

However the combined fresh W pool still fails the frozen development-panel
diversity gate:

```text
exact W = 8 selectable      FAIL
distinct W configs >= 6     FAIL
max 2 W/config              FAIL

structural ceiling:
fresh W support spans only 5 configs
```

Therefore the remaining bottleneck is no longer W state count. It is:

```text
fresh corrected WIDEN support on at least one additional physical config
```

M3-WCF1 expands the physical-configuration family, not the local s2 midpoint
family.

---

## 1. Primary objective

Establish at least one entirely new physical config with at least one durable
corrected high-budget WIDEN state, so that the combined fresh W pool can satisfy:

```text
exactly 8 W
distinct configs >= 6
max 2/config
```

and thereby restore a fresh:

```text
8W / 8S / 8ND
```

development panel.

---

## 2. Stage invariants

Before and during WCF1:

```text
gradient pilot = 0
finite-action V1 probe = 0
V1 threshold = null
S1 threshold = null
protected confirmation pilot = 0

VALUE = BLOCKED
RARITY = BLOCKED
M3-Q = BLOCKED
```

No invalid PI1V result may influence WCF1 design.

---

## 3. Hard scientific firewall

Forbidden:

```text
reuse WA1 CONSUMED_INVALID candidate
reuse retired PI1V state
reuse retired PI1V/WA1 seeds
use PI1V Attempt-2 V1 scores
use PI1V Attempt-2 S1 scores
use invalid-run gradient confidence
add more midpoint states in the existing 5 W configs
relax W configs>=6
relax max2/config
change 8W/8S/8ND target
adaptively add a seventh physical config
adaptively add new s2 values after outcomes
replace a failed config after outcomes
run discovery then refine successes
run gradient pilot
run V1 probe
run S1 confirmation
run value
run rarity
run M3-Q
```

---

## 4. Parent audit

Must verify:

```text
PI1V valid verdict = PI1V-X
PI1VR0 = PI1VR0-CAP-B
WA1 = WA1-X
WA1R = WA1R-B

WA1 consumed candidate reused = NO

WA1R:
8/8 reference records COMPLETE
8/8 labels = WIDEN
consumed-invalid = 0

fresh W config ceiling = 5

70 original protected reserve states remain scientifically valid according to
the latest reserve audit

all valid WA1R reference states remain pilot-unexposed
```

Any mismatch:

```text
WCF1-X
STOP
```

---

## 5. Valid evidence allowed for design

WCF1 may use only valid scientific evidence:

```text
corrected high-budget WIDEN labels
durable CF1N/WA1R reference records
valid corrected old-family reference states
physical config coordinates
s2 coordinates
CF0/CF1R0 legal physical candidate lattice
```

Forbidden:

```text
invalid PI1V Attempt-1/2 online scores
invalid WA1 candidate truth
```

---

## 6. Entirely fresh physical configs

A WCF1 physical config must never have been used as a scientific physical config
in any prior corrected reference or pilot stage.

Exclude at least:

```text
all old/current family configs
all CF1 configs
all CF1N replacement configs
all WA1/WA1R configs
all retired development configs
all previously referenced physical configs
```

Create:

```text
m3wcf1_used_physical_config_manifest.json
```

---

## 7. Legal physical candidate lattice

Recover the outcome-independent legal physical candidate lattice from CF0/CF1R0.

Keep field classification:

```text
PHYSICAL_CONFIG_AXIS
ACTION_STATE_AXIS
NUMERICAL_ONLY
BOOKKEEPING
```

`s2` is not a physical-config expansion axis.

---

## 8. Physical capacity gate

Before selection, count legal fresh physical configs after exclusions.

Require:

```text
>= 6
```

If fewer:

```text
WCF1-PRE-B
STOP
```

No simulator.

---

## 9. Freeze exactly six new physical configs

Select exactly:

```text
6 fresh physical configs
```

before any WCF1 reference outcome.

Reason:

```text
only one new W config is required,
but six fixed configs give prospective redundancy without adaptive extension.
```

No seventh config may be added after outcomes.

---

## 10. Outcome-blind config selector

Use sequential maximin physical diversity.

Base distance set:

```text
all previously used physical configs
+
already selected WCF1 configs
```

At each step select the legal fresh candidate maximizing minimum normalized
physical distance to the base set.

Tie-break:

```text
1. larger distance to prior-config centroid
2. distinct discrete physical mode if applicable
3. canonical candidate ID
```

No W outcome may enter selection.

---

## 11. Freeze config manifest

Create:

```text
m3wcf1_physical_config_manifest.csv
m3wcf1_physical_config_manifest_hash.json
```

Suggested IDs:

```text
wcf1_new_000
wcf1_new_001
wcf1_new_002
wcf1_new_003
wcf1_new_004
wcf1_new_005
```

Fields:

```text
wcf1_config_id
raw candidate ID
physical coordinates
normalized coordinates
min distance to prior set
selection rank
tie-break fields
```

---

## 12. Freeze exactly two W-target s2 values

Each new config receives exactly:

```text
2 W-target s2 values
```

Total states:

```text
6 configs × 2 s2 = 12 states
```

No later s2 additions.

---

## 13. Valid W-by-s2 support audit

Before simulator, construct a zero-sim table from corrected durable high-budget
reference states only:

```text
common-grid s2
distinct valid configs observed
distinct configs labeled WIDEN
W-support fraction
```

Exclude:

```text
invalid PI1V scores
WA1 consumed-invalid state
pre-ER1 contaminated evidence
```

Create:

```text
m3wcf1_valid_w_by_s2_audit.csv
```

---

## 14. Deterministic W-target s2 selector

From the already-frozen CF0 common grid, choose exactly two distinct s2 values:

```text
1. highest number of distinct valid configs labeled WIDEN
2. then highest WIDEN fraction among valid observed configs
3. then lower s2
4. then canonical grid index
```

Freeze the selected values before any WCF1 P_ref or reference run.

The rule is authoritative; do not manually force `1.25` or `1.6`.

---

## 15. Why valid historical W evidence may guide s2 placement

WCF1 is explicitly a new targeted reference-supply study.

Prior valid reference truth may guide placement. Independence comes from:

```text
new physical configs
new config-specific P_ref
new state identities
new seeds
prospective frozen selector
```

not from pretending valid historical evidence is unknown.

---

## 16. Freeze 12-state manifest

Create:

```text
m3wcf1_reference_state_manifest.csv
m3wcf1_reference_state_manifest_hash.json
```

Exactly:

```text
6 fresh configs × 2 frozen W-target s2 = 12 fresh states
```

Fields:

```text
state_id
config_id
s2
grid_index
physical fields
config_manifest_hash
s2_selector_hash
```

---

## 17. State freshness audit

Check every full-state identity against all prior stages, including:

```text
CF1
CF1N
CF2
PI1V retired panel
PI1VR0 reserve
WA1 candidate pool
WA1 consumed state
WA1R states
```

Require:

```text
12/12 identities fresh
```

If collision:

```text
WCF1-PRE-B
STOP
```

Do not perturb config or s2.

---

## 18. New config-specific P_ref

Because all six physical configs are new, generate:

```text
6 new corrected config-specific P_ref streams
```

Namespace:

```text
M3-WCF1-PREF
```

No cross-config P_ref reuse.

---

## 19. P_ref budget

```text
500,000 full-event samples/config
```

Total:

```text
3,000,000 P_ref samples
```

Use corrected:

```text
event = topology != S0
full-event probability domain
```

---

## 20. Reference protocol

For each of 12 states:

```text
500,000 samples / arm
3 arms:
BASE
WIDEN
SHRINK
20 paired CRN batches
```

No 100k discovery stage.

Finite-action cost:

```text
12 × 3 × 500,000
= 18,000,000 samples
```

Total WCF1 cost:

```text
P_ref = 3,000,000
reference = 18,000,000
total = 21,000,000 samples
```

---

## 21. Corrected classifier semantics

Use unchanged:

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

## 22. Fresh seed namespaces

Use:

```text
M3-WCF1-PREF
M3-WCF1-REF
```

All exact seeds:

```text
fresh
hash-locked before simulator
disjoint from all prior stages
```

---

## 23. Hardened persistence

Inherit repaired PI1VR0/WA1R persistence:

```text
safe path
durable STARTED before simulator
scientific calculation
non-circular payload/hash contract
temp write
flush + fsync
schema validation
sha256
atomic rename
parent-directory fsync
final durable verification
ledger COMPLETE
```

If sampling starts but durable COMPLETE fails:

```text
record = CONSUMED_INVALID
WCF1-X
STOP
```

No replay and no replacement.

---

## 24. P_ref completion gate

Before reference execution:

```text
expected = 6
COMPLETE = 6
CONSUMED_INVALID = 0
hashes PASS
ledger PASS
manifest PASS
```

Otherwise:

```text
WCF1-X
```

---

## 25. Reference completion gate

Before capacity analysis:

```text
expected = 12
COMPLETE = 12
CONSUMED_INVALID = 0
hashes PASS
ledger PASS
manifest PASS
```

Otherwise:

```text
WCF1-X
```

---

## 26. High-budget state labels

Each state receives:

```text
WIDEN
SHRINK
HOLD
AMBIGUOUS
INVALID
```

No provisional labels.

---

## 27. NEW_W_CONFIG

A new WCF1 physical config is:

```text
NEW_W_CONFIG
```

iff at least one of its two frozen high-budget states is WIDEN.

No adjacency requirement is needed because WCF1 is creating reference supply,
not claiming a stable W regime.

Also report diagnostic:

```text
ROBUST_NEW_W_CONFIG
```

iff both states are WIDEN.

---

## 28. Primary target

Define:

```text
K_NEW_W_CONFIG
```

Target:

```text
K_NEW_W_CONFIG >= 1
```

---

## 29. Combined fresh W pool

Combine valid pilot-unexposed W evidence from:

```text
PI1VR0 untouched reserve
WA1R valid references
WCF1 valid references
```

Exclude:

```text
retired original CF2 panel
WA1 consumed-invalid candidate
all invalid PI1V evidence
```

Create:

```text
m3wcf1_combined_fresh_w_pool.csv
```

---

## 30. W diversity feasibility gate

Require existence of a deterministic redacted subset:

```text
exactly 8 W
distinct configs >=6
max 2/config
```

Define:

```text
W_DIVERSITY_FEASIBLE = YES/NO
```

---

## 31. Full fresh development panel

If W diversity passes, combine with valid untouched S and ND supply and construct:

```text
8 W
8 S
8 ND
```

using the same PI1VR0 diversity rules.

Allowed selector inputs:

```text
truth
config ID
physical family
s2
source region
canonical order
pilot/probe exposure
```

Forbidden:

```text
invalid PI1V V1/S1
gradient confidence
r_hat
SE
effect magnitude
threshold results
```

---

## 32. Freeze fresh panel

If feasible create:

```text
m3wcf1_fresh_development_panel.csv
m3wcf1_fresh_development_panel_hash.json
```

Require:

```text
24 unique states
8 W
8 S
8 ND
pilot exposure = 0
probe exposure = 0
```

All unselected valid states remain:

```text
PILOT_PROTECTED_RESERVE
```

---

## 33. Verdicts

### WCF1-A — PHYSICAL W DIVERSITY RESTORED

Require:

```text
K_NEW_W_CONFIG >=1
W_DIVERSITY_FEASIBLE = YES
full fresh 8W/8S/8ND panel feasible = YES
fresh panel hash frozen
```

Next:

```text
M3-PI1VN
Independent Fresh-Panel Finite-Action Information Validation
```

### WCF1-B — NO NEW W PHYSICAL CONFIG

Valid execution but:

```text
K_NEW_W_CONFIG = 0
```

No adaptive seventh config.

### WCF1-C — NEW W EXISTS BUT PANEL GATE STILL FAILS

At least one new W config exists, but frozen exact-W/panel diversity remains
infeasible.

### WCF1-PRE-B — PROSPECTIVE EXPANSION CANNOT BE FROZEN

If:

```text
fresh legal physical configs <6
12-state manifest cannot be fresh
W-target s2 selector invalid
```

No simulator.

### WCF1-X — INVALID

For provenance, leakage, seed, persistence, semantic, or post-outcome adaptation
failure.

Verdict priority:

```text
INVALID -> WCF1-X
pre-run freeze fail -> WCF1-PRE-B
K_NEW_W_CONFIG == 0 -> WCF1-B
panel diversity fail -> WCF1-C
otherwise -> WCF1-A
```

---

## 34. No V1/S1 route decision

WCF1 is only a reference-supply stage.

It may not conclude that V1 works/fails or S1 is superior.

If WCF1-A, PI1VN reruns the original frozen <=2x information test unchanged.

---

## 35. Required outputs

Pre-run:

```text
results/phase_m3wcf1/summary/
m3wcf1_source_manifest.json
m3wcf1_parent_audit.json
m3wcf1_used_physical_config_manifest.json
m3wcf1_legal_physical_capacity.json
m3wcf1_physical_selector_contract.json
m3wcf1_physical_config_manifest.csv
m3wcf1_physical_config_manifest_hash.json
m3wcf1_valid_w_by_s2_audit.csv
m3wcf1_s2_selector_contract.json
m3wcf1_w_target_s2.json
m3wcf1_reference_state_manifest.csv
m3wcf1_reference_state_manifest_hash.json
m3wcf1_state_freshness_audit.json
m3wcf1_pref_protocol.json
m3wcf1_reference_protocol.json
m3wcf1_seed_manifest.json
m3wcf1_persistence_contract.json
m3wcf1_prereg_hashes.json
```

Execution:

```text
results/phase_m3wcf1/pref/<config_id>.json
pref_ledger.jsonl
pref_manifest.json

results/phase_m3wcf1/reference/<state_id>.json
reference_ledger.jsonl
reference_manifest.json
```

Final capacity:

```text
m3wcf1_pref_summary.json
m3wcf1_pref_persistence_audit.json
m3wcf1_reference_summary.json
m3wcf1_reference_by_config.json
m3wcf1_reference_persistence_audit.json
m3wcf1_new_w_config_summary.json
m3wcf1_combined_fresh_w_pool.csv
m3wcf1_w_diversity_feasibility.json
m3wcf1_full_panel_capacity.json
m3wcf1_fresh_development_panel.csv
m3wcf1_fresh_development_panel_hash.json
m3wcf1_remaining_protected_reserve.csv
m3wcf1_remaining_reserve_summary.json
m3wcf1_final_verdict.json
```

---

## 36. Required docs

```text
docs/phase_m3wcf1/
M3_WCF1_Task.md
M3_WCF1_Parent_Audit.md
M3_WCF1_Physical_Config_Expansion.md
M3_WCF1_W_Target_s2_Design.md
M3_WCF1_Pregistration.md
M3_WCF1_Human_Approval.md
M3_WCF1_Pref_Execution_Audit.md
M3_WCF1_Reference_Execution_Audit.md
M3_WCF1_Fresh_Panel_Capacity.md
M3_WCF1_Final_Report.md
```

---

## 37. Required tests

Parent/leakage:

```text
test_m3wcf1_parent_wa1rb
test_m3wcf1_pi1v_primary_x
test_m3wcf1_no_invalid_pi1v_scores
test_m3wcf1_no_wa1_consumed_state
test_m3wcf1_no_retired_state_reuse
test_m3wcf1_reserve_unpiloted
```

Physical expansion:

```text
test_m3wcf1_s2_not_physical_axis
test_m3wcf1_legal_candidate_lattice
test_m3wcf1_fresh_config_capacity_ge6
test_m3wcf1_exact6_new_configs
test_m3wcf1_no_prior_config_reuse
test_m3wcf1_maximin_selector
test_m3wcf1_config_selector_outcome_blind
test_m3wcf1_config_manifest_hash
```

W-target s2:

```text
test_m3wcf1_valid_w_support_only
test_m3wcf1_no_invalid_pi1v_in_s2_audit
test_m3wcf1_s2_selector_deterministic
test_m3wcf1_exact2_target_s2
test_m3wcf1_target_s2_from_frozen_grid
test_m3wcf1_s2_selector_frozen_preoutcome
```

State manifest:

```text
test_m3wcf1_exact12_states
test_m3wcf1_two_states_per_config
test_m3wcf1_all_state_identities_fresh
test_m3wcf1_no_adaptive_state_extension
test_m3wcf1_manifest_hash
```

P_ref/reference:

```text
test_m3wcf1_new_pref_per_config
test_m3wcf1_pref_count6
test_m3wcf1_pref_budget500k
test_m3wcf1_pref_event_v2
test_m3wcf1_pref_seed_disjoint
test_m3wcf1_pref_all_complete_before_reference
test_m3wcf1_ref_count12
test_m3wcf1_ref_budget500k
test_m3wcf1_ref_three_arms
test_m3wcf1_ref_crn20
test_m3wcf1_ref_corrected_semantics
test_m3wcf1_ref_seed_disjoint
test_m3wcf1_no_discovery_stage
```

Persistence:

```text
test_m3wcf1_safe_path
test_m3wcf1_started_before_simulator
test_m3wcf1_non_circular_hash_contract
test_m3wcf1_atomic_persistence
test_m3wcf1_hash_verify
test_m3wcf1_consumed_invalid_no_replay
test_m3wcf1_no_frozen_overwrite
```

Capacity:

```text
test_m3wcf1_new_w_config_definition
test_m3wcf1_combined_fresh_w_pool
test_m3wcf1_exact8_w_feasibility
test_m3wcf1_w_configs_ge6
test_m3wcf1_w_max2_per_config
test_m3wcf1_full_panel_8w8s8nd
test_m3wcf1_fresh_panel_unique
test_m3wcf1_fresh_panel_pilot_zero
test_m3wcf1_fresh_panel_probe_zero
test_m3wcf1_fresh_panel_hash
test_m3wcf1_remaining_reserve_protected
```

Boundaries:

```text
test_m3wcf1_gradient_zero
test_m3wcf1_probe_zero
test_m3wcf1_threshold_null
test_m3wcf1_confirmation_zero
test_m3wcf1_value_blocked
test_m3wcf1_rarity_blocked
test_m3wcf1_m3q_blocked
```

Full regression:

```text
all collected tests covered
zero failures
```

---

## 38. Mandatory pre-run STOP report

```text
M3-WCF1 PREREG STATUS:
COMPLETE / BLOCKED

PARENT:
WA1R = WA1R-B
WA1 = WA1-X
PI1V valid verdict = PI1V-X

CURRENT FRESH W:
state count =
distinct configs = 5
exact8/config>=6 feasible = NO

INVALID PI1V DATA:
used in config selection = NO
used in s2 selection = NO
used in panel selection = NO

PHYSICAL CONFIG SPACE:
legal fresh capacity =
selector = sequential maximin
outcome-blind = YES

NEW CONFIGS:
count = 6
IDs =
manifest hash =
prior config collisions = 0

VALID W-BY-s2 AUDIT:
source = corrected durable high-budget only
invalid evidence used = NO

W-TARGET s2:
count = 2
values =
selector rule frozen = YES
common-grid values = YES

REFERENCE STATES:
count = 12
fresh identities = 12/12
manifest hash =

P_REF:
new streams = 6
samples/config = 500000
namespace = M3-WCF1-PREF

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
states = 12
namespace = M3-WCF1-REF

EXPECTED COST:
P_ref = 3000000
finite-action reference = 18000000
total = 21000000

PERSISTENCE:
hardened contract = ENABLED
STARTED-before-simulator = YES
non-circular hash = YES
consumed-invalid replay = FORBIDDEN

PRIMARY TARGET:
K_NEW_W_CONFIG >=1

FINAL W GATE:
exact W = 8
configs >=6
max2/config

FULL PANEL TARGET:
8W / 8S / 8ND

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN WCF1
```

Then STOP.

---

## 39. Mandatory final report

```text
M3-WCF1 STATUS:
COMPLETE / INVALID

P_REF:
expected = 6
complete =
consumed-invalid =
samples =

REFERENCE:
expected states = 12
complete =
consumed-invalid =
samples =

BY NEW CONFIG:
<wcf1_config_id>:
  s2 values =
  labels =
  NEW_W_CONFIG = YES/NO
  ROBUST_NEW_W_CONFIG = YES/NO
...

COUNTS:
K_NEW_W_CONFIG =
K_ROBUST_NEW_W_CONFIG =

PERSISTENCE:
P_ref hashes = PASS/FAIL
P_ref ledger = PASS/FAIL
reference hashes = PASS/FAIL
reference ledger = PASS/FAIL
manifests = PASS/FAIL

COMBINED FRESH W:
states =
distinct configs =

W DIVERSITY:
exact 8 selectable = YES/NO
configs >=6 = PASS/FAIL
max2/config = PASS/FAIL

FULL FRESH PANEL:
feasible = YES/NO
W = 8/NA
S = 8/NA
ND = 8/NA
hash =

INVALID PI1V DATA:
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
WCF1-A /
WCF1-B /
WCF1-C /
WCF1-PRE-B /
WCF1-X

NEXT:
M3-PI1VN /
broader physical W expansion /
diversity-objective rethink /
stop

FULL REGRESSION:
...
```

---

## 40. Final principle

WA1R-B shows that local W state supply is no longer the issue:

```text
8/8 WA1R states = WIDEN
```

The failure is geometric/configurational:

```text
fresh W support spans only 5 configs
```

Therefore the minimal meaningful next move is:

```text
stop adding s2 points in those 5 configs
→ select 6 entirely new physical configs outcome-blind
→ freeze 2 W-target common-grid s2 values from valid historical evidence
→ generate new config-specific P_ref
→ one-shot 500k/arm reference on 12 states
→ require >=1 genuinely new W config
→ restore exact8 W across >=6 configs
→ freeze fresh 8W/8S/8ND panel
→ only then rerun PI1VN
```

This changes the dimension that actually failed while preserving every frozen
scientific boundary from the invalid PI1V lineage.

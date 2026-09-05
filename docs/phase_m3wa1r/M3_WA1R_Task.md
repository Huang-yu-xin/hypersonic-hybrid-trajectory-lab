# RareTopo M3-WA1R — WA1 Recovery with Consumed-Candidate Retirement
## Fresh-Seed One-Shot WIDEN Reference Recovery After WA1-X

> 项目：`hypersonic-hybrid-trajectory-lab`
>
> 当前 corrected frontier：
>
> ```text
> M3-CF1N    CF1N-A
> M3-CF2     CF2-A
> M3-PI1V    PI1V-X
> M3-PI1VR0  PI1VR0-CAP-B
> M3-WA1     WA1-X
> ```
>
> WA1 invalid incident：
>
> ```text
> candidate 1:
> cf1n_new_000_wa1_w_s2_1p788854382
>
> finite-action samples consumed:
> 1,500,000
>
> durable COMPLETE record:
> NO
>
> reason:
> schema validator required record_sha256 before the frozen persistence
> sequence had written that field
>
> status:
> CONSUMED_INVALID
> ```
>
> Candidate 2–8：
>
> ```text
> never started
> simulator samples = 0
> pilot exposure = 0
> reference exposure = 0
> ```
>
> WA1 candidate source before any WA1 outcome：
>
> ```text
> 9 adjacent-confirmed-W log-midpoint candidates
> 6 physical configs
> zero identity collisions
> ```
>
> WA1 selected 8 of those 9 before simulation.
>
> The recovery principle is：
>
> ```text
> retire the consumed candidate identity and its seed permanently
> preserve the 7 never-started frozen candidates
> use only the one pre-existing, outcome-blind unused pool candidate as the
> possible replacement
> freeze a new recovery manifest before any simulator call
> use entirely fresh seeds
> ```
>
> WA1R may not regenerate or perturb midpoint candidates after seeing WA1-X.

---

# 0. Stage Name

```text
M3-WA1R
WA1 Recovery with Consumed-Candidate Retirement
```

Primary objective：

```text
restore the original reference-only WIDEN augmentation experiment
without reusing the consumed WA1 candidate or any WA1 seed.
```

---

# 1. Scientific Status of WA1

Freeze：

```text
WA1 valid verdict = WA1-X
WA1 primary augmentation result = UNAVAILABLE
WA1 candidate-1 truth = UNAVAILABLE
WA1 candidate-1 reference record = INVALID / NON-DURABLE
```

Do not infer candidate-1 W/S/H/AMB truth from logs, stdout, memory dumps, or
temporary payload fragments.

---

# 2. Hard Retirement

Permanently retire：

```text
state identity:
cf1n_new_000_wa1_w_s2_1p788854382

its WA1 reference seed

any temporary/noncanonical record associated with that run
```

Status：

```text
CONSUMED_INVALID_RETIRED
```

It may never enter：

```text
fresh W pool
fresh development panel
future confirmation panel
future reference selector
```

---

# 3. Seven Never-Started Candidates

The other 7 WA1 selected candidates may remain scientifically fresh only if
the audit proves：

```text
simulator invocation count = 0
reference samples = 0
ledger STARTED absent
no pilot/probe exposure
no threshold replay
```

Create：

```text
m3wa1r_never_started_candidate_audit.csv
```

Any candidate with uncertain exposure is retired.

---

# 4. Unused Ninth Candidate

Recover the exact candidate that existed in the **pre-outcome WA1 candidate
pool** but was not selected in the WA1 8-candidate manifest.

It may be used as the sole replacement candidate only if：

```text
it was generated before any WA1 outcome
its identity is fresh
it was never sampled
it was never pilot/probe exposed
its source adjacent-W pair remains valid
its P_ref dependency remains valid
```

No newly generated candidate is allowed in WA1R.

---

# 5. Why No New Midpoint Generation

WA1 already saw an infrastructure failure after sampling candidate 1.

Generating a new midpoint now would create post-incident design freedom.

Therefore WA1R is restricted to：

```text
7 never-started selected candidates
+
the 1 already-existing unused pre-outcome pool candidate
```

If this set cannot satisfy the recovery diversity gate：

```text
WA1R-PRE-B
STOP
```

---

# 6. Stage Invariants

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

Invalid PI1V Attempt-2 diagnostics remain：

```text
DIAGNOSTIC_ONLY
```

---

# 7. Hard Firewall

Forbidden：

```text
1. rerun the consumed WA1 candidate
2. reuse its seed
3. reuse any WA1 reference seed
4. reconstruct candidate-1 truth
5. generate a tenth WA1-family midpoint
6. perturb an existing midpoint
7. add adaptive candidates after outcomes
8. change the 8W/8S/8ND target
9. change W diversity gates
10. use PI1V Attempt-2 V1/S1/gradient scores
11. pilot the 70 protected reserve states
12. run V1
13. run S1 confirmation
14. VALUE
15. RARITY
16. M3-Q
```

---

# 8. Parent Audit

Before any simulator call confirm：

```text
PI1VR0 = PI1VR0-CAP-B
WA1 = WA1-X

PI1V valid verdict = PI1V-X

WA1 consumed-invalid candidates = 1
WA1 never-started selected candidates = 7

original WA1 candidate pool = 9
unused pre-outcome candidates = 1

70 protected reserve states remain pilot-unexposed

M3PI1VR0-PERSIST-1 = PASS
WA1 persistence bug fix exists
```

Any mismatch：

```text
WA1R-X
STOP
```

---

# 9. Incident Fix Audit

The WA1 validator/payload-order bug must be fixed before recovery.

The fixed canonical sequence must be internally consistent：

```text
1. safe path validation
2. durable STARTED ledger
3. simulator
4. build payload without circular hash requirement
5. serialize temp
6. schema validation on pre-hash schema
7. compute canonical sha256
8. persist hash metadata according to frozen non-circular contract
9. atomic rename
10. parent-directory fsync
11. verify durable final record/hash
12. ledger COMPLETE
```

The implementation must avoid a schema in which：

```text
record_sha256 is required before record_sha256 can be computed.
```

---

# 10. Hash Contract Must Be Non-Circular

Freeze one explicit convention before simulator.

Preferred：

```text
scientific_payload_hash
= sha256(canonical scientific payload excluding self-hash field)

record_file_hash
= sha256(final serialized record bytes)
```

If the record contains a hash field, define exactly which bytes are hashed.

Never require the final file to contain its own full-file SHA-256 as part of
the bytes being hashed.

Create：

```text
m3wa1r_hash_contract.json
```

---

# 11. Synthetic Regression for the Exact WA1 Bug

Before scientific sampling, run mock records through：

```text
payload construction
schema validation
hash generation
atomic persistence
ledger COMPLETE
```

Test specifically that：

```text
schema validation does not require an unavailable self-hash
```

Add failure injection around the repaired step.

No simulator sampling.

---

# 12. Recovery Persistence Gate

Define：

```text
M3WA1R-PERSIST-1
```

PASS only if：

```text
safe path PASS
STARTED-before-simulator PASS
non-circular hash contract PASS
schema validation PASS
atomic persistence PASS
consumed-invalid no-replay PASS
frozen-artifact overwrite guard PASS
synthetic WA1 bug regression PASS
full regression PASS
```

If fail：

```text
WA1R-INFRA-B
STOP
```

---

# 13. P_ref Dependency

WA1 already established：

```text
P_ref dependency = CONFIG_SPECIFIC
```

WA1R must re-verify from committed source code and durable artifacts.

Allowed P_ref source：

```text
results/phase_m3cf1n/pref/<config_id>.json
```

Require：

```text
durable COMPLETE
corrected full-event semantics
hash valid
config ID match
```

No new P_ref is required if all checks pass.

---

# 14. Recovery Candidate Manifest Construction

Candidate universe is fixed to：

```text
7 audited never-started WA1 selected candidates
+
1 audited unused ninth WA1 pool candidate
```

No other candidate can enter.

Create：

```text
m3wa1r_candidate_universe.csv
```

---

# 15. Recovery Diversity Gate

The new 8-candidate recovery manifest must satisfy：

```text
candidate count = 8
distinct configs >= 4
max candidates/config <= 2
```

Prefer：

```text
distinct configs >= 6
```

if the fixed universe provides it.

This is checked before simulator.

---

# 16. Final Fresh-W Feasibility Awareness

The eventual fresh-panel W gate remains：

```text
exact W = 8
distinct W configs >= 6
max 2/config
```

Candidate selection may use config identity to support that structural gate.

It may not use any numerical WA1 or invalid PI1V outcome.

---

# 17. Deterministic Recovery Selector

Because the candidate universe has exactly 8 members after retirement and
replacement, the expected selector is：

```text
select all 8
```

If exposure audit retires another candidate and fewer than 8 remain：

```text
WA1R-PRE-B
```

Do not generate replacements.

---

# 18. Freeze Recovery Manifest

Create：

```text
m3wa1r_candidate_manifest.csv
m3wa1r_candidate_manifest_hash.json
```

Fields：

```text
candidate_id
config_id
s2
source_pair
origin:
  WA1_NEVER_STARTED
  or
  WA1_UNUSED_PREOUTCOME
P_ref_hash
canonical_order
```

Freeze before any scientific call.

---

# 19. Fresh Seed Namespace

Use entirely new namespace：

```text
M3-WA1R-REF
```

Requirements：

```text
8 fresh exact seeds
zero collision with M3-WA1-REF
zero collision with all prior corrected stages
hash-locked before simulator
```

Old WA1 seeds remain retired.

---

# 20. Reference Protocol Is Unchanged

Use exactly the WA1 scientific protocol：

```text
500,000 samples / arm

arms:
BASE
WIDEN
SHRINK

20 paired CRN batches
```

No discovery stage.

No budget changes.

---

# 21. WA1R Finite-Action Cost

If all 8 recovery candidates run：

```text
8 × 3 × 500,000
= 12,000,000 finite-action samples
```

The invalid WA1 1.5M samples are reported separately as retired incident cost.

They do not count as WA1R scientific evidence.

---

# 22. Corrected Reference Semantics

Use unchanged：

```text
event = topology != S0
full-event probability domain
BASE/WIDEN/SHRINK definitions
-1% improvement threshold
±3% HOLD band
5% direction margin
ESS >=20
invalid rules unchanged
```

---

# 23. Transactional Execution

For each recovery candidate：

```text
safe path
durable STARTED
simulate
build canonical payload
validate pre-hash schema
compute frozen hash fields
temp write
flush/fsync
atomic rename
parent fsync
verify final durable hashes
ledger COMPLETE
```

Exact code order must match the frozen repaired contract.

---

# 24. Persistence Failure Policy

If any WA1R scientific sampling begins and durable COMPLETE persistence fails：

```text
candidate = CONSUMED_INVALID
WA1R-X
STOP
```

No replay.

No second recovery attempt inside WA1R.

---

# 25. Reference Labels

Each valid durable candidate receives one corrected high-budget label：

```text
WIDEN
SHRINK
HOLD
AMBIGUOUS
INVALID
```

Define：

```text
K_WA1R_W
K_WA1R_S
K_WA1R_H
K_WA1R_AMB
K_WA1R_INVALID
```

---

# 26. Existing Fresh Reserve

Start from the PI1VR0 untouched reserve：

```text
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34
```

The retired original CF2 panel is excluded.

The WA1 consumed candidate is excluded.

---

# 27. Combined Fresh Reference Pool

After valid WA1R execution, add all durable WA1R references to the untouched
reference inventory.

Create：

```text
m3wa1r_combined_fresh_reference_pool.csv
```

---

# 28. W Feasibility Gate

The combined fresh W pool must contain a subset satisfying：

```text
exactly 8 W states
distinct configs >= 6
max 2/config
```

Use deterministic redacted selection only.

This is the primary capacity gate.

---

# 29. Full Fresh Panel Capacity

If W feasibility passes, attempt exact：

```text
8 W
8 S
8 ND
```

under the PI1VR0 frozen diversity rules.

No invalid PI1V scores may enter.

No retired state may enter.

---

# 30. Fresh Panel Selector

Allowed inputs：

```text
truth
config_id
physical family
s2
source region
canonical order
pilot/probe exposure
```

Forbidden：

```text
PI1V Attempt-2 V1
PI1V Attempt-2 S1
gradient confidence
r_hat
SE
effect magnitude
threshold results
WA1 candidate-1 non-durable outcome
```

---

# 31. Freeze Fresh Development Panel

If feasible：

```text
m3wa1r_fresh_development_panel.csv
```

Require：

```text
24 states
8 W
8 S
8 ND
all unique
pilot exposure = 0
probe exposure = 0
```

Freeze：

```text
m3wa1r_fresh_development_panel_hash.json
```

---

# 32. Protect Remaining Reference States

All unselected valid states become/remain：

```text
PILOT_PROTECTED_RESERVE
```

Create：

```text
m3wa1r_remaining_protected_reserve.csv
m3wa1r_remaining_reserve_summary.json
```

---

# 33. WA1R-A — Recovery Successful

Require：

```text
WA1 remains WA1-X
consumed WA1 candidate not reused
all old WA1 seeds retired
M3WA1R-PERSIST-1 PASS
8 fresh recovery candidates frozen
8/8 reference records COMPLETE
CONSUMED_INVALID = 0
W feasibility PASS
full fresh 8W/8S/8ND panel PASS
fresh panel hash frozen
```

Verdict：

```text
WA1R-A
FRESH DEVELOPMENT CAPACITY RESTORED
```

Next：

```text
M3-PI1VN
Independent Fresh-Panel Finite-Action Information Validation
```

---

# 34. WA1R-B — Reference Augmentation Insufficient

If execution is valid but：

```text
combined W pool cannot satisfy
exact W=8, configs>=6, max2/config
```

then：

```text
WA1R-B
```

No adaptive third augmentation inside WA1R.

Next：broader separately preregistered W-reference expansion.

---

# 35. WA1R-PRE-B — Recovery Candidate Capacity Fails

If after retiring consumed/uncertain candidates：

```text
candidate count <8
or
distinct configs <4
or
max/config >2 with no deterministic valid universe
```

then：

```text
WA1R-PRE-B
```

No simulator.

---

# 36. WA1R-INFRA-B — Persistence Repair Fails

If `M3WA1R-PERSIST-1` fails：

```text
WA1R-INFRA-B
```

No scientific sampling.

---

# 37. WA1R-X — Invalid Recovery

Any：

```text
consumed candidate reuse
old seed reuse
post-outcome candidate generation
invalid-run score leakage
candidate-manifest mutation
reference persistence failure
semantic deviation
protected-reserve pilot exposure
```

causes：

```text
WA1R-X
```

---

# 38. Verdict Priority

```text
if invalid:
    WA1R-X
elif persistence gate fails:
    WA1R-INFRA-B
elif pre-run candidate gate fails:
    WA1R-PRE-B
elif W/full-panel capacity fails:
    WA1R-B
else:
    WA1R-A
```

---

# 39. No V1/S1 Decision in WA1R

WA1R does not decide：

```text
V1 vs S1
```

Invalid PI1V Attempt-2 remains diagnostic only.

If WA1R-A, PI1VN must rerun the original frozen <=2x PI1V hypothesis unchanged.

---

# 40. Required Pre-Run Outputs

```text
results/phase_m3wa1r/summary/
m3wa1r_source_manifest.json
m3wa1r_parent_audit.json
m3wa1r_wa1_incident_status.json
m3wa1r_retired_candidate_seed_manifest.json
m3wa1r_never_started_candidate_audit.csv
m3wa1r_unused_candidate_audit.json
m3wa1r_hash_contract.json
m3wa1r_persistence_contract.json
m3wa1r_synthetic_bug_regression.json
m3wa1r_persistence_gate.json
m3wa1r_pref_dependency_audit.json
m3wa1r_candidate_universe.csv
m3wa1r_candidate_manifest.csv
m3wa1r_candidate_manifest_hash.json
m3wa1r_seed_manifest.json
m3wa1r_prereg_hashes.json
```

---

# 41. Required Execution Outputs

```text
results/phase_m3wa1r/reference/
<candidate_id>.json
reference_ledger.jsonl
reference_manifest.json
```

Exactly 8 durable canonical reference records if validly complete.

---

# 42. Required Capacity Outputs

```text
results/phase_m3wa1r/summary/
m3wa1r_reference_summary.json
m3wa1r_persistence_audit.json
m3wa1r_combined_fresh_reference_pool.csv
m3wa1r_w_feasibility.json
m3wa1r_full_panel_capacity.json
m3wa1r_fresh_development_panel.csv
m3wa1r_fresh_development_panel_hash.json
m3wa1r_remaining_protected_reserve.csv
m3wa1r_remaining_reserve_summary.json
m3wa1r_final_verdict.json
```

---

# 43. Required Docs

```text
docs/phase_m3wa1r/
M3_WA1R_Task.md
M3_WA1R_WA1_Incident_Audit.md
M3_WA1R_Persistence_Repair.md
M3_WA1R_Candidate_Recovery.md
M3_WA1R_Pregistration.md
M3_WA1R_Human_Approval.md
M3_WA1R_Reference_Execution_Audit.md
M3_WA1R_Fresh_Panel_Capacity.md
M3_WA1R_Final_Report.md
```

---

# 44. Required Tests — Incident / Retirement

```text
test_m3wa1r_parent_wa1x
test_m3wa1r_consumed_candidate_retired
test_m3wa1r_consumed_candidate_not_reused
test_m3wa1r_old_wa1_seeds_retired
test_m3wa1r_seven_never_started_verified
test_m3wa1r_unused_ninth_preoutcome_only
test_m3wa1r_no_new_midpoint_generation
```

---

# 45. Required Tests — Persistence Repair

```text
test_m3wa1r_safe_path
test_m3wa1r_started_before_simulator
test_m3wa1r_non_circular_hash_contract
test_m3wa1r_schema_before_hash_contract_valid
test_m3wa1r_atomic_persistence
test_m3wa1r_bug_regression
test_m3wa1r_consumed_invalid_no_replay
test_m3wa1r_frozen_overwrite_guard
```

---

# 46. Required Tests — Candidate Recovery

```text
test_m3wa1r_candidate_universe_only_preoutcome
test_m3wa1r_candidate_exact8
test_m3wa1r_candidate_configs_ge4
test_m3wa1r_candidate_max2_per_config
test_m3wa1r_candidate_manifest_frozen
test_m3wa1r_no_invalid_pi1v_scores
test_m3wa1r_no_wa1_outcome_selection
```

---

# 47. Required Tests — P_ref / Reference

```text
test_m3wa1r_pref_config_specific
test_m3wa1r_pref_durable_hash_valid
test_m3wa1r_reference_budget_500k
test_m3wa1r_reference_three_arms
test_m3wa1r_reference_crn20
test_m3wa1r_reference_semantics_v2
test_m3wa1r_seed_namespace_new
test_m3wa1r_seed_collision_zero
test_m3wa1r_all8_complete
```

---

# 48. Required Tests — Fresh Capacity

```text
test_m3wa1r_combined_fresh_pool
test_m3wa1r_w_exact8_feasibility
test_m3wa1r_w_configs_ge6
test_m3wa1r_w_max2_per_config
test_m3wa1r_full_panel_8w8s8nd
test_m3wa1r_fresh_panel_unique
test_m3wa1r_fresh_panel_pilot_zero
test_m3wa1r_fresh_panel_probe_zero
test_m3wa1r_fresh_panel_hash
test_m3wa1r_remaining_reserve_protected
```

---

# 49. Boundary Tests

```text
test_m3wa1r_gradient_zero
test_m3wa1r_probe_zero
test_m3wa1r_threshold_null
test_m3wa1r_confirmation_zero
test_m3wa1r_value_blocked
test_m3wa1r_rarity_blocked
test_m3wa1r_m3q_blocked
```

Full regression：

```text
all collected tests covered
zero failures
```

---

# 50. Suggested Commit Sequence

```text
1. WA1R task + WA1-X incident status
2. retire consumed candidate and all WA1 seeds
3. audit 7 never-started candidates
4. audit unused ninth pre-outcome candidate
5. freeze non-circular hash contract
6. synthetic reproduction/regression of WA1 schema bug
7. persistence gate
8. reverify config-specific P_ref
9. freeze recovery candidate universe
10. freeze exact 8-candidate manifest
11. freeze fresh seed namespace
12. pre-run full regression
13. human approval
14. transactional 8-candidate reference execution
15. persistence audit
16. combined fresh reference pool
17. W feasibility check
18. fresh 8W/8S/8ND panel construction
19. freeze panel hash
20. protect remaining reserve
21. final verdict
22. full regression
```

---

# 51. Mandatory Pre-Run STOP Report

```text
M3-WA1R PREREG STATUS:
COMPLETE / BLOCKED

PARENT:
WA1 = WA1-X
PI1VR0 = PI1VR0-CAP-B
PI1V valid verdict = PI1V-X

WA1 INCIDENT:
consumed-invalid candidates = 1
consumed candidate ID =
retired = YES
reused = NO

WA1 NEVER-STARTED:
audited count = 7
all simulator samples = 0
all exposure = 0

UNUSED PRE-OUTCOME CANDIDATE:
count = 1
ID =
generated before WA1 outcome = YES
sampled = NO

RECOVERY CANDIDATES:
count = 8
distinct configs =
max/config =
manifest hash =
new midpoint generated after WA1-X = NO

P_REF:
dependency = CONFIG_SPECIFIC
new P_ref samples = 0
all reused records durable = YES

PERSISTENCE:
safe paths = PASS
STARTED before simulator = PASS
non-circular hash contract = PASS
WA1 bug regression = PASS
atomic persistence = PASS
consumed-invalid replay = FORBIDDEN

M3WA1R-PERSIST-1:
PASS

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
expected finite-action samples = 12000000

SEEDS:
namespace = M3-WA1R-REF
count = 8
collision with WA1 = 0
all prior collision = 0
hash-locked = YES

EXISTING FRESH RESERVE:
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34

SUCCESS TARGET:
combined fresh W:
  exact 8 selectable
  configs >=6
  max2/config

full fresh panel:
  8W / 8S / 8ND

INVALID PI1V DATA:
used = NO

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
HUMAN APPROVAL TO RUN WA1R REFERENCE
```

Then STOP.

---

# 52. Mandatory Final Report

```text
M3-WA1R STATUS:
COMPLETE / INVALID

WA1:
valid verdict = WA1-X
consumed candidate reused = NO

RECOVERY REFERENCE:
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
hash contract = PASS/FAIL
canonical hashes = PASS/FAIL
ledger = PASS/FAIL
manifest = PASS/FAIL

COMBINED FRESH W:
old untouched W = 7
new WA1R W =
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

SIMULATOR:
WA1R finite-action samples =
new P_ref samples = 0

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
WA1R-A /
WA1R-B /
WA1R-PRE-B /
WA1R-INFRA-B /
WA1R-X

NEXT:
M3-PI1VN /
broader W-reference expansion /
infrastructure repair /
stop

FULL REGRESSION:
...
```

---

# 53. Scientific Claim If WA1R-A

Allowed：

> A separately preregistered recovery stage retired the consumed WA1
> candidate, reused only never-started pre-outcome candidate identities,
> executed them with fresh seeds under the repaired persistence contract, and
> restored enough fresh corrected high-budget WIDEN supply to freeze an
> untouched 8W/8S/8ND development panel.

Not allowed：

```text
V1 works
V1 fails
S1 is superior
controller is safe
value improved
```

---

# 54. Final Principle

WA1R should repair only the infrastructure-contaminated augmentation.

The clean recovery is：

```text
WA1-X remains invalid
→ retire consumed candidate + old WA1 seeds
→ keep only 7 never-started candidates
→ use only the already-existing unused ninth pre-outcome candidate
→ freeze exactly 8 recovery candidates
→ fresh seeds
→ one-shot 500k/arm reference
→ recheck W diversity
→ freeze fresh 8W/8S/8ND panel
→ then return to PI1VN
```

No new midpoint is invented after the failure, and no invalid PI1V result
influences the recovery design.

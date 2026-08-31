# RareTopo M3-D2 — Corrected Sign-Diverse Benchmark Reconstruction
## 完整实验任务书 / Codex Execution Specification

> 项目：`hypersonic-hybrid-trajectory-lab`  
> 当前有效科学前沿：`RareTopo-M3-v2` + corrected `RareTopo-M3-D-v1` reference-gate negative result  
> 当前阶段：**M3-D2 — Corrected Sign-Diverse Benchmark Reconstruction**  
> 性质：**重新建立 schema-2 事件语义下合法、独立、可冻结的 WIDEN / HOLD / SHRINK benchmark**  
> 本阶段不执行 controller online comparison，不恢复 M3-G，不进入 BV/BV2/CA/PF。
>
> ER-1 已确认：
>
> ```text
> frozen topology domain = S0–S4
> nominal topology = S0
> corrected event = topology != S0 = S1–S4
> last clean frozen empirical parent = RareTopo-M2-v0
> first contaminated empirical stage = M3-v0
> corrected M3-v0 tag = RareTopo-M3-v2
> corrected M3-D tag = RareTopo-M3-D-v1
> ```
>
> corrected M3-D reference gate on the historical 24-state benchmark gives：
>
> ```text
> WIDEN    = 6
> SHRINK   = 7
> HOLD     = 3
> AMBIGUOUS= 8
> ```
>
> 因此原先 `8/8/8` benchmark composition 不再存在，`M3D-1` reference gate FAIL，旧 online 192-trial controller comparison 不再合法。
>
> 本阶段唯一科学目标：
>
> \[
> \boxed{
> \text{Construct and freeze a new corrected sign-diverse benchmark}
> }
> \]
>
> 必须满足：
>
> ```text
> correct schema-2 event semantics
> full-event probability domain S1–S4
> independent benchmark-construction data
> preregistered state-candidate generation
> preregistered ambiguity handling
> preregistered deterministic balancing rule
> benchmark frozen before any controller evaluation
> ```

---

# 0. Codex 总执行指令

严格按以下顺序：

```text
D2-0  Live Git / corrected-parent audit
 ↓
D2-1  Semantic + probability-domain lock
 ↓
D2-2  Candidate-family preregistration
 ↓
D2-3  Discovery characterization
 ↓
D2-4  Deterministic shortlist freeze
 ↓
D2-5  Independent reference confirmation
 ↓
D2-6  Final balanced benchmark construction
 ↓
D2-7  Benchmark-only freeze
 ↓
STOP
```

本任务书结束时：

```text
NO controller online evaluation
NO M3-G-v2
NO BV/BV2
NO M3-CA
NO PF stages
NO M3-Q
```

这些必须在新的 benchmark freeze 后另行 preregister。

---

# 1. Hard Scientific Firewall

禁止：

```text
reuse old contaminated event semantics
use NOMINAL as an event literal
use S0/proposal-arm strings as event predicates
use missing-mode p_ref(S2–S4) as full-event reference
retune M3 scalar gradient
retune action thresholds after seeing D2 results
retune finite-step magnitude after seeing D2 results
change controller parameters
run controller online trials
select states manually because they look balanced
remove ugly/ambiguous states without the preregistered rule
change candidate grid after discovery results
change class target after confirmation results
```

允许：

```text
new benchmark-construction simulation under a frozen protocol
independent discovery and confirmation streams
corrected full-event reference characterization
pure arithmetic / bootstrap / CI analysis
state balancing using a preregistered deterministic rule
```

---

# 2. Parent Evidence That Must Be Preserved

Historical tags remain immutable.

Do not move/delete：

```text
RareTopo-M2-v0
RareTopo-M3-v2
RareTopo-M3-D-v1
RareTopo-ER1-v0   (if present)
```

Also preserve all superseded historical tags from the old lineage.

M3-D2 is a **new scientific benchmark-construction stage**, not a rewrite of M3-D-v1.

Recommended new tag：

```text
RareTopo-M3-D2-v0
```

---

# 3. D2-0 — Live Git Audit

First run：

```bash
git branch --show-current
git status --short
git log -25 --oneline
git tag --list
pytest -q
```

Verify：

```text
RareTopo-M2-v0
RareTopo-M3-v2
RareTopo-M3-D-v1
ER-1 final corrected lineage report
ER-1 supersession ledger
```

Record：

```text
branch
HEAD
working-tree status
parent tags / peeled commits
full regression
```

Historical closing regression from ER-1：

```text
1363 passed, 3 warnings
```

Treat this only as an expectation；live `pytest -q` is authoritative.

---

# 4. New Branch

After parent audit create：

```text
feature/phase-m3d2-corrected-sign-diverse-benchmark
```

Do not continue scientific work on the evidence-repair branch.

---

# 5. D2-1 — Freeze the Corrected Event Contract

The only valid event domain for D2 is：

```text
topology labels = S0, S1, S2, S3, S4
nominal          = S0
event            = topology != S0
                 = S1 | S2 | S3 | S4
```

Explicit IDs should be saved：

```text
event_semantics_schema_version = 2
event_definition_id = FULL_TOPOLOGY_EVENT_S1_S4
nominal_topology = S0
```

Never compare against：

```text
"NOMINAL"
```

inside event membership logic.

---

# 6. Probability-Domain Repair Is Binding

ER-1 established two distinct probability domains：

```text
corrected P_hat:
full event S1–S4

historical p_ref:
missing modes S2–S4 only
```

Therefore the historical `p_ref` is invalid for corrected full-event VRF / Strong evidence.

M3-D2 must create or identify a **new full-event reference probability**：

\[
\boxed{
 p_{ref}^{full}=P(S1\cup S2\cup S3\cup S4)
}
\]

under the exact frozen state/event semantics.

---

# 7. Full-Event Probability Reference Contract

Before discovery data, freeze exactly how `p_ref_full` is obtained.

Preferred order：

```text
1. Reuse a clean existing raw reference stream only if it was generated under
   topology S0–S4 and contains enough information to recompute S1–S4.

2. Otherwise generate a dedicated independent full-event reference stream
   using the repository's clean/reference characterization machinery.
```

Do not derive `p_ref_full` by rescaling the old S2–S4 reference.

Do not infer S1 mass from downstream contaminated outputs.

---

# 8. Probability Reference Outputs

For every candidate/reference state, save：

```text
p_ref_full
p_ref_full_SE
p_ref_full_CI
sample_count
seed
source proposal / sampling law
event_definition_id
schema_version
```

If one state-level reference is shared across arms, document why.

All arms in a state must estimate the **same S1–S4 probability**.

---

# 9. Probability-Domain Sanity Gate

For the same state and same corrected event, action-arm IS probability estimates：

```text
BASE
WIDEN
SHRINK
```

must be statistically compatible with one another and with `p_ref_full`.

Use the preregistered uncertainty rule from repository conventions.

If arm probability estimates disagree beyond the locked sanity gate：

```text
REFERENCE_INVALID
```

and the state cannot enter the benchmark.

Do not repair it by swapping probability references.

---

# 10. Authoritative Action Classifier

M3-D2 must not invent a new WIDEN/HOLD/SHRINK definition.

Extract the corrected classifier from：

```text
RareTopo-M3-D-v1
```

and freeze：

```text
finite-step size
M2 comparison formula
bootstrap / CI method
HOLD tolerance
WIDEN rule
SHRINK rule
AMBIGUOUS rule
tie handling
minimum ESS / numerical validity
```

Create：

```text
configs/phase_m3d2/m3d2_classifier_contract.json
```

The hash of this contract must be committed before discovery simulation.

---

# 11. Why Ambiguous Is a First-Class Class

The corrected old benchmark produced：

```text
8 ambiguous / 24
```

M3-D2 must not force ambiguous states into WIDEN/HOLD/SHRINK.

`AMBIGUOUS` means：

```text
the corrected reference data do not support a unique preregistered finite-step class
```

Ambiguous states may：

```text
remain in the discovery pool
be reported scientifically
be excluded from the final balanced benchmark by the preregistered rule
```

They must never be relabeled by hand.

---

# 12. Scientific Goal of the New Benchmark

The new benchmark must provide enough clean states for：

```text
WIDEN
HOLD
SHRINK
```

under corrected schema-2 semantics.

Preferred final composition：

```text
8 WIDEN
8 HOLD
8 SHRINK
```

for continuity with the original M3-D design.

But exact `8/8/8` is allowed only if the preregistered candidate pool produces it legitimately.

---

# 13. Benchmark Feasibility Gate

Before any controller can be authorized, final confirmation must yield at least：

```text
WIDEN >= 8
HOLD   >= 8
SHRINK >= 8
```

with non-ambiguous corrected classes.

If any class has fewer than 8 confirmed states：

```text
M3D2-BENCHMARK-FAIL
```

Do not lower the target after seeing results.

Do not run controller trials.

---

# 14. Candidate-Family Construction Principle

Candidate states must come from the **same scientific state-generation family** as the corrected M3/M3-D problem.

Do not invent a new event family.

Use repository-frozen state parameterization and parameter bounds.

The candidate set must be generated deterministically before simulation.

---

# 15. Candidate Pool Must Be Larger Than 24

Because the corrected historical 24-state set contains only：

```text
6 W
7 S
3 H
8 ambiguous
```

a larger pool is required.

Recommended target candidate count：

```text
48–72 deterministic candidate states
```

Exact count must be chosen before results based on compute budget and frozen parameter grid structure.

Do not choose pool size after observing class balance.

---

# 16. Candidate Grid Generation

Preferred construction：

```text
start from the frozen corrected state parameter bounds
preserve the same event/topology family
preserve the same scalar-action semantics
expand the grid deterministically around underrepresented transition regions
```

Important：

```text
"around underrepresented transition regions"
```

must be defined from **pre-existing corrected M3-v2 / M3-D-v1 geometry or scalar-gradient information**, not from new D2 outcomes.

Candidate generation cannot use controller performance.

---

# 17. Use Corrected Gradient Only as a Candidate Generator

If corrected M3-v2 scalar gradient can predict likely action sign：

```text
negative → likely WIDEN
positive → likely SHRINK
near zero → likely HOLD/transition
```

it may be used to stratify candidate generation.

But final class is determined only by the confirmed finite-step reference classifier.

Therefore：

```text
gradient = candidate-generation prior
finite-step confirmed M2 = benchmark class ground truth
```

---

# 18. Pre-Stratified Candidate Pool

Recommended deterministic strata：

```text
G-W: predicted negative-gradient region
G-H: near-zero-gradient region
G-S: predicted positive-gradient region
```

Generate enough candidates in each stratum so that HOLD is not starved.

Because the corrected old pool had only 3 HOLD states, intentionally allocate more **candidate density** near the corrected sign-transition region.

This is allowed only if the transition-region rule is frozen before D2 simulation.

---

# 19. No Outcome-Adaptive Grid Expansion

After discovery starts, forbidden：

```text
"we need more HOLD, so add a few more points here"
```

Instead preregister one of：

```text
A. one fixed candidate pool only

or

B. deterministic two-wave pool where Wave 2 is fully specified from Wave 1
   using a prewritten algorithm independent of manual judgement
```

Option A is preferred for simplicity.

---

# 20. D2-2 Preregistration Files

Before any new simulator calls create：

```text
configs/phase_m3d2/
    m3d2_protocol.json
    m3d2_candidate_states.json
    m3d2_discovery_seeds.json
    m3d2_confirmation_seeds.json
    m3d2_classifier_contract.json
    m3d2_probability_contract.json
    m3d2_balancing_rule.json
```

Commit all files.

Record SHA-256 hashes.

No benchmark simulation before this commit.

---

# 21. Discovery vs Confirmation Separation

Use two independent stages.

## Discovery

Purpose：

```text
estimate provisional corrected class
identify valid candidates
apply preregistered shortlist rule
```

## Confirmation

Purpose：

```text
independently establish final reference class
```

Discovery data do not become final benchmark reference data.

---

# 22. Discovery Sample Budget

Recommended discovery budget：

```text
100k samples per arm per candidate
```

for：

```text
BASE
WIDEN
SHRINK
```

Use enough reference probability samples to apply the probability-domain sanity gate.

If repository experience supports a different fixed discovery count, freeze it before simulation.

---

# 23. Discovery Seeds

Must be：

```text
new
frozen before data
disjoint from confirmation seeds
disjoint from any future controller online seeds
```

CRN pairing across BASE/WIDEN/SHRINK is recommended if it matches the corrected M3-D methodology.

---

# 24. Discovery Outputs

For every candidate：

```text
config_id
candidate stratum
state parameters
corrected event probability
BASE M2
WIDEN M2
SHRINK M2
ESS
probability sanity status
provisional class
ambiguity metric / CI
effect margin
numerical validity
```

Save all candidates, not only selected ones.

---

# 25. Preregistered Shortlist Rule

The shortlist rule must be frozen before discovery outcomes.

Recommended class-conditional rule：

1. discard only protocol-invalid candidates：

```text
probability-domain fail
numerical invalidity
ESS below frozen minimum
```

2. separate provisional classes：

```text
WIDEN
HOLD
SHRINK
AMBIGUOUS
```

3. within W/H/S, rank by **reference certainty**, not effect size alone：

```text
primary: distance from ambiguity boundary / CI confidence
secondary: state-space diversity criterion
tertiary: deterministic config_id order
```

4. select more than 8 per class for confirmation.

Recommended：

```text
12 confirmed candidates per target class
```

if available.

This gives room for confirmation class changes.

---

# 26. State-Space Diversity Rule

The final benchmark should not contain eight near-duplicate states from a tiny parameter neighborhood.

Before discovery, define a deterministic diversity rule, e.g.：

```text
bin by frozen scalar state parameter(s)
maximum N per bin
or
farthest-point selection in normalized frozen state coordinates
```

Do not invent a diversity metric after seeing class outcomes.

---

# 27. Ambiguous Discovery States

Discovery-ambiguous states normally do not enter the main confirmation shortlist.

However, if HOLD candidates are scarce, do NOT manually promote ambiguous states.

The benchmark gate should fail rather than redefine HOLD.

---

# 28. D2-4 Shortlist Freeze

After discovery analysis and deterministic selection：

```text
commit the shortlist
commit discovery summary
commit all source hashes
```

Create：

```text
results/phase_m3d2/summary/
    m3d2_discovery_summary.csv
    m3d2_shortlist.json
```

No confirmation data before shortlist commit.

---

# 29. Confirmation Sample Budget

Use the corrected M3-D reference standard unless live repository protocol shows otherwise.

Recommended：

```text
500,000 samples per arm per shortlisted state
```

for：

```text
BASE
WIDEN
SHRINK
```

This mirrors the corrected M3-D repair reference characterization.

---

# 30. Confirmation Probability Reference

Every confirmation state must have corrected full-event probability reference：

```text
S1–S4
```

Do not use：

```text
historical missing-mode S2–S4 p_ref
```

Persist：

```text
p_ref_full
uncertainty
reference stream provenance
```

---

# 31. Confirmation Class Is Authoritative

The final class is computed only from independent confirmation data.

Possible outcomes：

```text
WIDEN
HOLD
SHRINK
AMBIGUOUS
INVALID
```

Discovery class is not carried over.

---

# 32. Confirmation Class-Stability Report

Report the matrix：

```text
Discovery → Confirmation
```

including：

```text
W→W
W→H
W→S
W→A
H→...
S→...
```

This is an important measure of benchmark reliability.

Do not remove class-switching records from the audit.

---

# 33. Final 8/8/8 Construction

Only after confirmation.

If at least：

```text
8 WIDEN
8 HOLD
8 SHRINK
```

exist, apply a preregistered deterministic selection rule within each confirmed class.

Recommended priority：

```text
1. strongest class-certainty margin
2. frozen diversity criterion
3. deterministic config_id tie-break
```

Do not optimize benchmark states for future controller success.

---

# 34. Final Benchmark Composition

Target：

```text
24 states
8 WIDEN
8 HOLD
8 SHRINK
```

Save excluded confirmed states too.

Output：

```text
m3d2_final_benchmark.json
m3d2_final_benchmark.csv
m3d2_excluded_confirmed_states.csv
```

---

# 35. Final Benchmark Must Be Controller-Blind

Before benchmark freeze：

```text
NO M3-G controller
NO GA1 evaluation
NO HOLD classifier evaluation
NO online pilot
NO controller seed
```

The benchmark may depend only on：

```text
corrected event semantics
finite-step reference M2
probability-domain validity
prewritten diversity/balancing rule
```

---

# 36. Corrected Benchmark Reference Fields

Each final state must persist：

```text
config_id
state parameters
corrected class
p_ref_full
BASE P_hat
WIDEN P_hat
SHRINK P_hat
BASE M2
WIDEN M2
SHRINK M2
ESS per arm
class confidence / CI
action margins
schema version
event definition id
reference seeds
sample counts
```

---

# 37. Separate Probability Evidence from Action Evidence

M3-D2 must not conflate：

```text
event probability correctness
```

with：

```text
which finite-step arm minimizes M2
```

Therefore save two gates per state：

```text
probability_semantics_valid
reference_action_class_valid
```

A state enters the benchmark only if both are true.

---

# 38. Benchmark-Level Primary Gate

Define：

```text
M3D2-1
```

PASS iff：

```text
WIDEN >= 8 confirmed valid states
HOLD   >= 8 confirmed valid states
SHRINK >= 8 confirmed valid states
```

and the deterministic final selector produces exactly 8/8/8.

If FAIL：

```text
M3-D2 final verdict = BENCHMARK NOT CONSTRUCTIBLE UNDER CURRENT CANDIDATE FAMILY
```

No controller trial is authorized.

---

# 39. Secondary Benchmark Quality Gates

Recommended：

```text
class stability discovery→confirmation
probability sanity across arms
minimum ESS
state-space diversity
no duplicated configs
source/hash integrity
```

These cannot replace M3D2-1.

---

# 40. Do Not Optimize for Action Margin Too Aggressively

Very large-margin WIDEN/SHRINK states may be easy but unrepresentative.

HOLD states near a finite-step indifference region are intrinsically more fragile.

Therefore final selection should report：

```text
margin distribution by class
```

and avoid selecting only extreme tails if the preregistered diversity rule prevents this.

---

# 41. Required Discovery Figures

At least：

```text
D2-1 candidate class map
D2-2 corrected gradient vs provisional finite-step class
D2-3 ambiguity / CI margin distribution
D2-4 corrected event probability by candidate
D2-5 discovery class counts
D2-6 state-space coverage by provisional class
```

---

# 42. Required Confirmation Figures

At least：

```text
D2-7 discovery→confirmation transition matrix
D2-8 confirmed class counts
D2-9 action M2 ratios by confirmed class
D2-10 probability estimates across BASE/WIDEN/SHRINK
D2-11 final 8/8/8 benchmark map
D2-12 final benchmark class margins
```

---

# 43. Required Docs

Create：

```text
docs/phase_m3d2/
    M3_D2_Corrected_Sign_Diverse_Benchmark_Task.md
    M3_D2_Protocol_and_Pregistration.md
    M3_D2_Discovery_Audit.md
    M3_D2_Confirmation_Audit.md
    M3_D2_Final_Benchmark_Freeze.md
```

---

# 44. Required Summary Files

```text
results/phase_m3d2/summary/
    m3d2_source_manifest.json
    m3d2_probability_reference.csv
    m3d2_discovery_summary.csv
    m3d2_shortlist.json
    m3d2_confirmation_summary.csv
    m3d2_class_transition.csv
    m3d2_final_benchmark.json
    m3d2_final_benchmark.csv
    m3d2_excluded_confirmed_states.csv
    m3d2_final_verdict.json
```

---

# 45. Source Manifest

Lock：

```text
RareTopo-M2-v0 relevant artifacts
RareTopo-M3-v2 corrected artifacts
RareTopo-M3-D-v1 corrected reference audit
ER-1 semantic contract
ER-1 supersession ledger
candidate configs
protocol configs
seed locks
classifier contract
probability contract
```

Every entry：

```text
path
sha256
source tag/commit
role
read_only
```

---

# 46. New Simulator Accounting

M3-D2 is a new benchmark-construction experiment, so new simulator calls are allowed after preregistration.

Track separately：

```text
discovery simulator samples
confirmation simulator samples
full-event reference samples
```

Do not label these as deployable controller cost.

They are benchmark-construction scientific cost.

---

# 47. Seed Discipline

Maintain distinct namespaces：

```text
D2 discovery seeds
D2 confirmation seeds
future controller online seeds
```

Future controller seeds must not be generated/consumed during M3-D2 if repository policy treats seed lists as hidden evaluation resources.

At minimum do not reuse discovery/confirmation seeds for controller evaluation.

---

# 48. Required Semantic Tests

At least：

```text
test_m3d2_event_schema_v2
test_m3d2_event_topology_not_s0
test_m3d2_nominal_literal_not_event
test_m3d2_probability_domain_full_s1_s4
test_m3d2_missing_mode_pref_not_used
test_m3d2_arm_probability_same_event
test_m3d2_variance_mass_zero_for_non_event
```

---

# 49. Required Protocol Tests

At least：

```text
test_m3d2_parent_tags
test_m3d2_classifier_contract_hash
test_m3d2_candidate_pool_frozen
test_m3d2_discovery_seed_lock
test_m3d2_confirmation_seed_lock
test_m3d2_seed_disjointness
test_m3d2_no_controller_evaluation
test_m3d2_no_posthoc_grid_change
test_m3d2_no_posthoc_threshold_change
```

---

# 50. Required Benchmark Tests

At least：

```text
test_m3d2_probability_sanity_gate
test_m3d2_discovery_classifier
test_m3d2_shortlist_deterministic
test_m3d2_confirmation_classifier
test_m3d2_ambiguous_not_forced
test_m3d2_class_transition_schema
test_m3d2_final_class_counts
test_m3d2_final_8_8_8
test_m3d2_final_unique_configs
test_m3d2_state_diversity_rule
test_m3d2_output_schema
```

Final：

```bash
pytest -q
```

must exit 0.

---

# 51. D2 Final Verdicts

Only：

```text
D2-A
CORRECTED SIGN-DIVERSE BENCHMARK FROZEN

D2-B
CORRECTED BENCHMARK NOT CONSTRUCTIBLE UNDER CURRENT CANDIDATE FAMILY

D2-C
PROBABILITY / SEMANTIC REFERENCE INVALID

D2-D
PROTOCOL / NUMERICAL INVALIDITY
```

---

# 52. D2-A — Benchmark Frozen

Conditions：

```text
corrected event semantics valid
full-event probability domain valid
confirmation produces >=8 W/H/S
final deterministic selector produces exact 8/8/8
all benchmark tests pass
full regression passes
```

Then freeze：

```text
RareTopo-M3-D2-v0
```

This tag freezes **reference benchmark only**.

It does not freeze any controller result.

---

# 53. What D2-A Authorizes

Only after D2-A may the project write a separate taskbook for：

```text
M3-G2 / M3-G-v2
Corrected Controller Confirmation
```

That future stage must：

```text
use the new frozen D2 benchmark
use independent controller seeds
re-derive any pilot probability semantics under schema 2
revalidate GA1/rho/delta-theta inheritance before use
```

Do not assume historical M3-G-v1 parameters remain scientifically justified merely because benchmark structure is restored.

They may be used as frozen candidates only if a separate inheritance audit authorizes them.

---

# 54. D2-B — Benchmark Not Constructible

If any target class has fewer than 8 confirmed states：

```text
D2-B
```

Do not reduce：

```text
8 → 6
```

after seeing results.

Do not add more candidate states ad hoc.

Next action must be a separate scientific decision：

```text
expand state family?
change finite-step action family?
accept that HOLD is rare under corrected semantics?
```

Those are new scientific questions.

---

# 55. D2-C — Probability / Semantic Invalid

Trigger：

```text
full-event p_ref cannot be established
arm P_hat disagree under same event beyond locked gate
variance_mass semantic tests fail
schema-2 event mismatch reappears
```

Action：

```text
STOP
return to evidence/estimator repair
```

No benchmark claim.

---

# 56. D2-D — Protocol / Numerical Invalidity

Trigger：

```text
seed contamination
post-hoc candidate modification
confirmation draw-order mismatch
unexplained numerical failure
source hash mutation
full regression failure
```

Action：

```text
STOP
no scientific benchmark freeze
```

---

# 57. Historical Benchmark Comparison

The final audit should compare：

```text
historical contaminated 8/8/8
corrected historical 24-state result = 6/7/3/8A
new corrected D2 benchmark
```

But do not describe the new D2 benchmark as “recovering the original truth”.

It is a new benchmark constructed under corrected semantics.

---

# 58. Claim Boundaries

M3-D2 may claim only：

```text
A corrected sign-diverse finite-step benchmark can/cannot be constructed
within the preregistered candidate state family under schema-2 event semantics.
```

It cannot claim：

```text
controller works
GA1 works
HOLD recovery works
adaptive value exists
BV2 headroom exists
absolute VRF result
proposal-family bottleneck
PF1/PF2/PF3 results survive
M5-AR routing
```

---

# 59. M5-AR Status

Throughout D2：

```text
M5-AR = BLOCKED
```

Even D2-A does not directly authorize M5-AR.

The corrected lineage must rebuild scientifically from the new benchmark.

---

# 60. M3-Q Status

Throughout D2：

```text
M3-Q = BLOCKED
```

No corrected evidence currently supports curvature as the dominant issue.

---

# 61. Recommended Commit Sequence

## Commit 0

```text
live parent audit / D2 branch
```

## Commit 1

```text
schema-2 + full-event probability contract
```

## Commit 2

```text
classifier / candidate / balancing preregistration
```

No simulation before Commit 2.

## Commit 3

```text
discovery raw results
```

## Commit 4

```text
discovery audit + deterministic shortlist freeze
```

## Commit 5

```text
confirmation raw results
```

## Commit 6

```text
confirmation audit + class transition
```

## Commit 7

```text
final benchmark selection + figures + tests
```

## Commit 8

```text
final freeze report
```

Then if D2-A：

```text
RareTopo-M3-D2-v0
```

---

# 62. Codex Final Report Format

```text
M3-D2 STATUS:
COMPLETE / BLOCKED

LIVE GIT:
branch =
HEAD =
M3-v2 tag =
M3-D-v1 tag =
pytest =

EVENT SEMANTICS:
schema = 2
event = S1-S4
nominal = S0
full-event probability reference =

CANDIDATE POOL:
count =
predicted W/H/S strata =
discovery samples/arm =

DISCOVERY:
valid candidates =
WIDEN =
HOLD =
SHRINK =
AMBIGUOUS =
INVALID =

SHORTLIST:
WIDEN =
HOLD =
SHRINK =
rule =

CONFIRMATION:
samples/arm =
WIDEN =
HOLD =
SHRINK =
AMBIGUOUS =
INVALID =

CLASS STABILITY:
discovery→confirmation agreement =
transition matrix =

PROBABILITY SANITY:
arm consistency =
p_ref_full consistency =
failed states =

FINAL BENCHMARK:
WIDEN =
HOLD =
SHRINK =
unique states =
diversity gate =

M3D2-1:
PASS / FAIL

FINAL VERDICT:
D2-A / D2-B / D2-C / D2-D

CONTROLLER ONLINE TRIALS:
0

NEW SIMULATOR SAMPLES:
discovery =
confirmation =
reference =
total =

NEXT AUTHORIZED ACTION:
...

FILES:
...

COMMITS:
...

TAG:
...

REGRESSION:
...
```

---

# 63. Final Scientific Principle

ER-1 has changed the scientific frontier.

The project must not ask：

```text
Does the old controller still work?
```

before first answering：

\[
\boxed{
\text{Does a corrected sign-diverse benchmark actually exist?}
}
\]

The historical 24-state benchmark no longer provides that foundation.

M3-D2 therefore rebuilds the **measurement instrument** before testing the
controller.

The key discipline is：

\[
\boxed{
\text{benchmark construction}
\perp
\text{controller evaluation}
}
\]

in terms of data, seeds and decision logic.

Only after an independently confirmed corrected `8/8/8` benchmark is frozen
should the project decide whether to launch a new corrected controller study.

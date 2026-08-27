# M3-BV — Adaptive-Value Benchmark Redesign Task

> **Project:** RareTopo  
> **Stage:** M3-BV — Adaptive-Value Benchmark Redesign  
> **Primary objective:** Redesign the scalar covariance-action benchmark so that action labels, headline evaluation budget, and adaptive-value headroom are mutually consistent **before** any adaptive controller is evaluated.  
> **Scientific firewall:** This stage is a benchmark-design stage, not a controller-design stage.  
> **Mandatory first action:** **Freeze M3-G-v1 before starting any M3-BV scientific work.**

---

# 0. FIRST: Freeze M3-G-v1

Before creating or running M3-BV, finalize and freeze M3-G-v1.

Current intended frozen conclusion:

> **Exact first-order gain gating generalizes HOLD recovery across unseen Monte-Carlo trials on the frozen proposal states, but adaptive superiority over the best fixed action remains unsupported.**

The claim remains limited to:

```text
out-of-sample over Monte-Carlo / pilot randomness
NOT
out-of-sample over proposal states / event geometries
```

The M3-VA result must also be preserved:

```text
Oracle itself cannot pass the current V1-5 adaptive-value gate:
Oracle / BestFixed median ratio = 1.000
Oracle wins = 10 / 24
```

Therefore V1-5 is benchmark-headroom-limited and must not be interpreted primarily as controller failure.

## 0.1 Freeze audit

Before tagging:

```bash
git branch --show-current
git status --short
git rev-parse HEAD
git rev-parse RareTopo-M3-D-v0^{}
python -m pytest -q
```

Verify:

```text
M3-G-v1 prereg commit unchanged
M3-G-v1 implementation commit unchanged
M3-G-v1 confirmatory result commit unchanged
M3-VA audit commit unchanged
24-state benchmark hash unchanged
confirmatory seeds unchanged
raw scientific result hashes unchanged
full pytest exit 0
working tree has no unexpected tracked modifications
```

## 0.2 Freeze documentation

Ensure the final M3-G-v1 report explicitly records:

```text
V1-1..V1-4 PASS
V1-5 FAIL
Strong PASS
M3-VA verdict = benchmark adaptive headroom insufficient
M3-Q remains blocked
```

Do not modify scientific results.

## 0.3 Tag

If audit passes:

```bash
git add <freeze-audit / final-report corrections if any>
git commit -m "Finalize M3-G-v1 confirmatory freeze"

python -m pytest -q

git tag -a RareTopo-M3-G-v1 -m "Freeze RareTopo M3-G-v1: exact first-order gain gating replicates HOLD recovery on unseen seeds; adaptive-value superiority remains unsupported due to benchmark headroom limits"

git push origin RareTopo-M3-G-v1
```

Confirm:

```text
tag peeled commit == final HEAD
parent tags unchanged
working tree clean
```

Only after this tag exists may M3-BV begin.

---

# 1. Create M3-BV Branch

Create:

```bash
git switch -c feature/phase-m3bv-adaptive-value-benchmark
```

Create and commit this task before any new benchmark characterization run.

Suggested document path:

```text
docs/phase_m3bv/M3_BV_Adaptive_Value_Benchmark_Redesign_Task.md
```

Status at commit:

```text
PREREGISTERED — BENCHMARK CONSTRUCTION NOT STARTED
```

---

# 2. Scientific Motivation

M3-G-v1 established that the exact first-order gain gate can recover HOLD decisions across unseen Monte-Carlo trials.

However, M3-VA showed:

\[
\operatorname{median}_{state}
\operatorname{median}_{seed}
\frac{M_2(\mathrm{Oracle})}
{M_2(\mathrm{BestFixed})}
=1.000
\]

and:

```text
Oracle wins = 10 / 24
```

Therefore the old benchmark does not contain enough measurable adaptive-value headroom for the original V1-5 gate.

The key mismatch is:

```text
reference action label
≠
headline-budget realized action value
```

especially for HOLD states.

M3-BV asks:

> Can we construct a preregistered, sign-diverse scalar covariance-action benchmark where the reference action is stable at the headline evaluation budget and where an Oracle policy has measurable value advantage over every fixed action rule?

---

# 3. Scientific Firewall

M3-BV may change only benchmark construction.

M3-BV may NOT change:

```text
M3-D gradient estimator
M3-G-v1 GA1/rho=0.02 controller
delta_theta = 0.20
ESS_grad = 20
bootstrap direction rule
fixed-weight Layer A semantics
CRN semantics
M2 estimator definition
leakage decomposition
VRF definitions
legality checker
```

No controller may be evaluated until the benchmark itself passes all benchmark-only gates.

Do not use controller performance to choose states.

---

# 4. Benchmark Unit

A candidate benchmark state remains:

```text
frozen event config
+
frozen mixture means
+
frozen mixture weights
+
selected component
+
scalar covariance state s2
```

The only benchmark-design variable is proposal state / approved benchmark state construction.

No joint optimization.

No controller-informed state search.

No oracle field enters online controller APIs.

---

# 5. Candidate Family

Start from the existing frozen event family, but do NOT automatically reuse the old 24-state benchmark.

Construct a fresh candidate pool from legal proposal states.

The state grid must be preregistered before characterization.

Recommended starting scalar grid:

```text
s2_grid_bv =
[0.65, 0.85, 1.10, 1.40, 1.80, 2.30, 3.00, 4.00, 5.00, 6.40, 8.00]
```

Before any run:

- verify BASE, WIDEN, and SHRINK arms are all legal;
- any state with any illegal required arm is `ILLEGAL_PRE_FREEZE`;
- illegal states are never replaced post hoc.

If the existing legality floor requires another minimum, compute it from the frozen legality checker and lock the resulting grid before characterization.

No grid amendment after controller outcomes are observed.

---

# 6. Reference Characterization

For every legal candidate state evaluate:

```text
SHRINK
BASE
WIDEN
```

under high-budget CRN reference evaluation.

Freeze an exact reference budget before running.

Recommended:

```text
N_ref = 500,000 per arm
```

Use the same estimator semantics as the frozen pipeline.

Store:

```text
M2
mode-wise L_j
paired batch estimates
paired uncertainty
arm legality
state metadata
```

Verify:

\[
M_2=\sum_jL_j
\]

to numerical tolerance.

---

# 7. Reference Action Definition

For each candidate state determine the reference best action among:

```text
WIDEN
HOLD = BASE
SHRINK
```

Reference WIDEN / SHRINK requires a meaningful value margin.

Define:

\[
\Delta_{\mathrm{best}}
=
\frac{
M_2(\mathrm{second\ best})-M_2(\mathrm{best})
}{
M_2(\mathrm{best})
}.
\]

For active WIDEN / SHRINK candidate eligibility require:

```text
reference best action statistically supported
AND
Delta_best >= 0.05
```

Thus active-action states must have at least 5% value separation from the second-best arm.

No threshold relaxation after characterization.

---

# 8. HOLD Definition

Do NOT define HOLD only as “reference difference within 1%”.

A HOLD candidate must satisfy both:

## 8.1 Reference indifference

At high reference budget:

```text
BASE is effectively tied with WIDEN
AND
BASE is effectively tied with SHRINK
```

within the frozen HOLD tolerance.

Recommended reference tolerance:

```text
±1%
```

## 8.2 Headline-budget stability

At the actual headline evaluation budget, HOLD must remain value-indifferent with high probability / high replicate stability.

This requirement is mandatory.

The exact stability criterion must be committed before characterization.

Recommended operational criterion:

```text
Across matched headline-budget reference replicates:
>= 80% of replicate blocks place both perturbation arms within ±5% of BASE
```

Alternative statistically equivalent criterion is allowed only if locked before running.

The key principle is:

\[
\boxed{
\text{label resolution}
\gtrsim
\text{headline evaluation noise resolution}
}
\]

A HOLD label that is stable only at 500k but unstable at the deployed evaluation budget is ineligible.

---

# 9. Headline-Budget Stability Characterization

Before selecting benchmark states, characterize each candidate under the same sample budget used in later controller evaluation.

Use frozen headline evaluation semantics.

For each candidate estimate:

```text
probability / fraction that reference-best action remains best
realized action-value margin distribution
rank stability of WIDEN / BASE / SHRINK
```

This stage is still benchmark-only.

No controller is run.

---

# 10. Benchmark Gate BV-0 — Validity

Require:

```text
M3-G-v1 tag exists
M3-BV task committed before candidate characterization
parent tags unchanged
grid locked before characterization
all required arms legal
reference estimator frozen
headline-budget estimator frozen
CRN frozen
M2=sum L verified
no controller outputs used for state selection
full pytest pass
```

Failure => STOP.

---

# 11. Benchmark Gate BV-1 — Sign Diversity

Candidate pool must contain at least:

```text
8 stable WIDEN states
8 stable SHRINK states
8 stable HOLD states
```

All must satisfy class-specific stability rules.

If not:

```text
STOP benchmark construction
```

Do not relax thresholds.

Any amendment must be written and committed before additional characterization.

---

# 12. Benchmark Gate BV-2 — Evaluation-Budget Action Stability

For selected benchmark candidates require that the reference action remains stable at the headline evaluation budget.

For WIDEN / SHRINK:

```text
reference action is realized best action in >=80% of matched headline-budget replicates
```

For HOLD:

```text
headline-budget indifference criterion from Sec.8.2 is satisfied
```

Report exact stability fraction per state.

States failing stability are ineligible.

---

# 13. Benchmark Gate BV-3 — Oracle Headroom

This is the central new benchmark gate.

Construct the benchmark-only Oracle:

```text
for each state:
take the frozen reference action
```

Compare Oracle to every fixed policy:

```text
Always-Widen
Always-Shrink
Always-Hold
```

Define globally best fixed policy using the same frozen aggregation used later.

Require:

\[
\operatorname{median}_{state}
\left[
\operatorname{median}_{replicate}
\frac{
M_2(\mathrm{Oracle})
}{
M_2(\mathrm{BestFixed})
}
\right]
\le0.95
\]

and:

```text
Oracle beats BestFixed on >=16 / 24 selected states
```

Both required.

If Oracle fails:

```text
benchmark = VALUE-INFEASIBLE
STOP before controller evaluation
```

No controller may be blamed for failing a gate that Oracle itself cannot pass.

---

# 14. Optional Strong Oracle Headroom

Report, but do not require:

```text
Oracle / BestFixed <= 0.90
```

This is a stronger benchmark-quality target.

---

# 15. Benchmark Selection Rule

Only after BV-0..BV-3 candidate eligibility information exists.

Select exactly:

```text
8 WIDEN
8 SHRINK
8 HOLD
```

The selection rule itself must be preregistered.

Recommended deterministic selection hierarchy:

1. eligible only;
2. maximize config coverage;
3. within equal coverage prefer larger headline-budget stability;
4. then larger reference value margin;
5. final deterministic tie-break `(config_id, s2)` ascending.

IMPORTANT:

Do not manually pick states because they make a controller look better.

Selection depends only on:

```text
reference action
reference margin
headline-budget stability
event/config coverage
legality
```

No adaptive controller performance.

---

# 16. Config-Coverage Constraint

Avoid the old benchmark concentration problem.

Require at minimum:

```text
each action class spans >=4 distinct event configs
```

and preferably:

```text
no event config contributes >2 states to the same action class
```

If the candidate pool cannot satisfy this:

```text
report limitation
and STOP unless a preregistered amendment is made before controller runs
```

Do not silently relax coverage after seeing results.

---

# 17. Freeze Artifacts

Before any controller evaluation create:

```text
docs/phase_m3bv/M3_BV_Benchmark_Freeze.md
docs/phase_m3bv/M3_BV_Benchmark_Freeze.json
configs/phase_m3bv/m3bv_benchmark_v0.json
```

Record:

```text
parent tags
task commit
candidate grid
reference budget
headline budget
legality rule
W/S margin threshold
HOLD reference tolerance
headline stability rule
Oracle headroom metrics
selected 24 states
class balance
config coverage
all source hashes
selection rule
freeze timestamp
```

Commit benchmark freeze before any controller run.

After freeze:

```text
NO state replacement
NO label changes
NO margin changes
NO headroom threshold changes
NO benchmark amendment based on controller performance
```

---

# 18. Required Benchmark-Only Tests

At minimum:

```text
test_m3bv_parent_tags
test_m3bv_grid_locked
test_m3bv_all_three_arms_legal
test_m3bv_reference_crn
test_m3bv_m2_equals_sum_leakage
test_m3bv_active_margin_threshold
test_m3bv_hold_reference_indifference
test_m3bv_hold_headline_stability
test_m3bv_action_stability
test_m3bv_oracle_best_fixed_definition
test_m3bv_oracle_headroom_gate
test_m3bv_class_balance
test_m3bv_config_coverage
test_m3bv_selection_deterministic
test_m3bv_no_controller_selection_leakage
test_m3bv_freeze_schema
```

Then:

```bash
python -m pytest -q
```

Full suite must exit 0 before benchmark freeze is considered valid.

---

# 19. Benchmark Diagnostics

Before controller evaluation, produce:

```text
per-state reference M2 for W/B/S
per-state reference margin
headline-budget action stability
HOLD indifference stability
Oracle vs each fixed policy
Oracle headroom by action class
config coverage
proposal-state distribution
```

---

# 20. Required Figures

Create:

1. **BV-1** — W/B/S reference M2 curves over proposal scale  
2. **BV-2** — action class map over `(config, s2)`  
3. **BV-3** — reference margin distribution  
4. **BV-4** — headline-budget action stability  
5. **BV-5** — HOLD indifference stability  
6. **BV-6** — Oracle vs fixed per-state M2 ratio  
7. **BV-7** — Oracle adaptive headroom by class  
8. **BV-8** — selected 24-state class/config coverage  

---

# 21. Controller Evaluation Firewall

No adaptive controller may run until:

```text
BV-0 PASS
BV-1 PASS
BV-2 PASS
BV-3 PASS
benchmark freeze committed
full pytest PASS
```

If any fail:

```text
STOP
```

The benchmark-design result itself is reportable.

---

# 22. Controller Evaluation Order After Freeze

Only after benchmark validity is established:

First evaluate the already-frozen scalar controllers without modification:

```text
M3-D gradient controller
M3-G-v1 GA1/rho=0.02
Always-Widen
Always-Shrink
Always-Hold
Oracle
```

Do NOT introduce M3-Q yet.

The first question is:

> Does the already validated M3-G-v1 controller capture meaningful Oracle headroom on a benchmark where such headroom actually exists?

---

# 23. Controller Value Metrics

For M3-G-v1 report:

```text
WIDEN recall
SHRINK recall
HOLD recall
balanced accuracy
macro-F1
M2(v1)/M2(M3-D)
M2(v1)/M2(BestFixed)
M2(v1)/M2(Oracle)
wins/losses/ties vs BestFixed
VRF_budget
mode-wise leakage
```

Use exactly the same aggregation used by the Oracle headroom gate.

---

# 24. Adaptive-Value Controller Gate BV-C1

Only meaningful because Oracle feasibility was already established.

Require:

\[
\operatorname{median}_{state}
\operatorname{median}_{seed}
\frac{M_2(M3Gv1)}
{M_2(BestFixed)}
\le0.95
\]

and:

```text
M3-G-v1 beats BestFixed on >=16/24 states
```

If FAIL while Oracle passes BV-3:

```text
controller fails to capture available adaptive-value headroom
```

This is then legitimate evidence for controller improvement.

---

# 25. Oracle Capture Metric

Define:

\[
\mathrm{Capture}
=
\frac{
M_2(BestFixed)-M_2(M3Gv1)
}{
M_2(BestFixed)-M_2(Oracle)
}.
\]

Compute carefully under the frozen aggregation hierarchy.

Report:

```text
median Oracle-headroom capture
per-class capture
per-state capture
```

Do not use states where denominator is numerically zero without an explicit tie rule.

This metric answers:

> Of the adaptive value theoretically available in the benchmark, how much does M3-G-v1 actually capture?

---

# 26. Decision Logic After Controller Evaluation

## Case A — Oracle headroom gate fails
Benchmark redesign unsuccessful.

```text
STOP
Do not run controller
Do not start M3-Q
```

## Case B — Oracle headroom passes and M3-G-v1 also passes
The scalar first-order controller demonstrates meaningful adaptive value.

```text
Do not rush into M3-Q.
First freeze the positive scalar result.
```

## Case C — Oracle headroom passes, M3-G-v1 fails, and action classification is still high
This is the cleanest justification for:

```text
M3-Q — Curvature-Aware Finite-Step Action Value
```

because the benchmark now proves that value headroom exists but the first-order controller fails to capture it.

## Case D — Oracle headroom passes, but M3-G-v1 action classification collapses
Problem is benchmark/state generalization rather than purely value modeling.

Do not immediately attribute failure to missing curvature.

---

# 27. Claim Boundaries

If benchmark gates pass:

> We constructed a preregistered sign-diverse scalar covariance-action benchmark in which reference action labels are stable at the headline evaluation budget and an Oracle adaptive policy has measurable advantage over every fixed scalar action rule.

Do NOT claim:

```text
controller superiority
real-system generalization
universal adaptive advantage
full-matrix validity
```

until controller evaluation separately supports it.

If the benchmark fails:

> The tested candidate family does not provide sufficient stable adaptive-value headroom under the frozen evaluation protocol.

That is a valid negative benchmark result.

---

# 28. Negative-Result Discipline

Do not manipulate the benchmark until Oracle wins.

Forbidden after outcome inspection:

```text
lower Oracle ratio threshold
lower win threshold
drop difficult HOLD states
change evaluation budget
change label tolerance
change stability criterion
replace states
change config coverage rule
```

Any benchmark amendment must:

```text
state old rule
state new rule
state observed result motivating amendment
state what remains untouched
be committed before additional characterization
```

No amendment after controller outcomes are observed.

---

# 29. Recommended Execution Order

```text
F0  freeze M3-G-v1
 ↓
B0  create M3-BV branch
 ↓
B1  commit M3-BV task + configs
 ↓
B2  construct legal candidate pool
 ↓
B3  high-budget reference characterization
 ↓
B4  headline-budget stability characterization
 ↓
B5  classify eligible W/S/H states
 ↓
B6  Oracle headroom audit
 ↓
B7  enforce config coverage + deterministic 8/8/8 selection
 ↓
B8  freeze 24-state benchmark
 ↓
B9  targeted tests + full pytest
 ↓
STOP AND REPORT
 ↓
only after approval:
controller evaluation
```

---

# 30. First Mandatory Checkpoint

Do not run M3-G-v1 on the new benchmark yet.

Stop after the benchmark freeze and report:

| Item | Result |
|---|---|
| M3-G-v1 final HEAD | |
| `RareTopo-M3-G-v1` tag | |
| M3-BV branch | |
| M3-BV task commit | |
| candidate states total | |
| legal states | |
| eligible WIDEN | |
| eligible SHRINK | |
| eligible HOLD | |
| selected benchmark | 8/8/8 |
| config coverage per class | |
| headline-budget stability | |
| Oracle / BestFixed ratio | |
| Oracle wins / losses / ties | |
| BV-0 | |
| BV-1 | |
| BV-2 | |
| BV-3 | |
| benchmark freeze commit | |
| full pytest | |
| controller runs on M3-BV | **0** |

Only if:

```text
BV-0 PASS
BV-1 PASS
BV-2 PASS
BV-3 PASS
```

should M3-G-v1 be evaluated on the redesigned benchmark.

---

# 31. Core Principle

The entire M3-BV stage exists to enforce:

\[
\boxed{
\text{Oracle feasibility}
\rightarrow
\text{benchmark freeze}
\rightarrow
\text{controller evaluation}
}
\]

Never again require a controller to pass an adaptive-value gate that the benchmark Oracle itself cannot pass.

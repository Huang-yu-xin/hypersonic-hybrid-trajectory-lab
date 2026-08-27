# M3-BV2 — Dual-Axis Decision / Adaptive-Value Benchmark Task

> **Project:** RareTopo  
> **Stage:** M3-BV2 — Dual-Axis Decision / Adaptive-Value Benchmark  
> **Status:** PREREGISTRATION — NO BV2 SCIENTIFIC RUNS YET  
> **Mandatory first action:** Correct and freeze the negative M3-BV-v0 result before starting BV2.  
> **Core design principle:** Separate **decision correctness** from **adaptive economic value**.  
> **Scientific firewall:** BV2 is still a benchmark-design stage first. No controller may be evaluated until the Value benchmark proves Oracle feasibility.

---

# 0. FIRST: Correct and Freeze M3-BV-v0 Negative Result

M3-BV-v0 already produced a valid negative benchmark-design result:

```text
BV-0 PASS
BV-1 PASS
BV-2 PASS
BV-3 FAIL
benchmark = VALUE-INFEASIBLE
controller runs = 0
```

The negative result remains valid.

However, one interpretation in the current BV report must be corrected before freeze.

## 0.1 Correct the SHRINK interpretation

Current wording incorrectly implies:

> SHRINK headroom contributes no adaptive value because a fixed SHRINK policy can capture it.

This is not correct under the frozen definition of:

```text
BestFixed = one globally selected fixed rule
```

because the actual globally best fixed policy is:

```text
ALWAYS_WIDEN
```

Therefore SHRINK states **do provide genuine adaptive headroom relative to BestFixed**.

Replace the interpretation with:

> **SHRINK states provide genuine and decisive headroom relative to the globally best fixed policy, ALWAYS_WIDEN, but that headroom is concentrated in only one-third of the balanced benchmark and is therefore insufficient to move the current median-of-state-ratios adaptive-value metric below the frozen 0.95 threshold.**

Do not change:

```text
BV-3 FAIL
Oracle / BestFixed = 0.9946
wins / losses / ties = 14 / 2 / 8
BestFixed = ALWAYS_WIDEN
```

## 0.2 Add the structural-gate diagnosis

The final BV-v0 report should explicitly state:

```text
In an 8W/8H/8S benchmark where BestFixed=ALWAYS_WIDEN:

- all 8 WIDEN states are constructive Oracle/BestFixed ties;
- HOLD states are intentionally near-indifferent and therefore tend to have ratios near 1;
- decisive Oracle headroom is concentrated mainly in SHRINK states.

Therefore the frozen median-ratio <=0.95 gate is close to structurally unattainable for this balanced decision benchmark, even when the benchmark has valid sign diversity and stable labels.
```

Also state that:

```text
wins >=16/24
```

is knife-edge because the 8 WIDEN ties cap strict Oracle wins at 16 even in the best possible case.

This is a benchmark-metric architecture issue, not a controller result.

## 0.3 Freeze M3-BV-v0 as a negative design result

Run:

```bash
python -m pytest -q
```

Confirm:

```text
M3-G-v1 tag unchanged
BV prereg commit unchanged
raw BV results unchanged
controller runs remain 0
no benchmark freeze artifact was retroactively created
working tree clean except intended report correction
```

Commit:

```bash
git add docs/phase_m3bv/M3_BV_Benchmark_Report.md <any matching audit correction>
git commit -m "Correct M3-BV headroom interpretation and finalize negative result"
```

Then tag:

```bash
git tag -a RareTopo-M3-BV-v0 -m "Freeze RareTopo M3-BV-v0 negative benchmark-design result: stable sign-diverse candidate family remains value-infeasible under the frozen Oracle headroom gate"
git push origin RareTopo-M3-BV-v0
```

Important:

```text
RareTopo-M3-BV-v0
=
frozen negative benchmark-design experiment
NOT
a controller-evaluation benchmark freeze
```

Only after this is complete may BV2 begin.

---

# 1. Create BV2 Branch

Create:

```bash
git switch -c feature/phase-m3bv2-dual-axis-benchmark
```

Create and commit before any BV2 characterization:

```text
docs/phase_m3bv2/M3_BV2_Dual_Axis_Benchmark_Task.md
configs/phase_m3bv2/m3bv2_construction_lock.json
```

Status:

```text
PREREGISTERED — NO SCIENTIFIC RUNS
```

---

# 2. Scientific Motivation

Previous stages established:

```text
M3-G-v1:
exact GA1/rho=0.02 reproduces HOLD recovery on unseen Monte-Carlo seeds.

M3-VA:
the old 8W/8H/8S benchmark has insufficient Oracle adaptive-value headroom.

M3-BV-v0:
even after redesigning for stability and margins, the balanced 8W/8H/8S benchmark remains VALUE-INFEASIBLE under the median-ratio adaptive-value gate.
```

The central problem is that two different scientific questions were forced into one benchmark:

```text
Question A:
Did the controller choose the correct WIDEN / HOLD / SHRINK action?

Question B:
Did adaptive switching create measurable estimator value over the best globally fixed policy?
```

These are not the same question.

BV2 separates them.

---

# 3. Dual-Axis Benchmark Architecture

BV2 contains two separately frozen benchmarks.

## Axis A — Decision Benchmark

Purpose:

```text
test WIDEN / HOLD / SHRINK action correctness
```

Target structure:

```text
8 WIDEN
8 HOLD
8 SHRINK
=
24 decision states
```

Headline metrics:

```text
W/S/H recall
balanced accuracy
macro-F1
confusion matrix
HOLD_GAIN behavior
```

This benchmark is allowed to include HOLD states with low economic margins because HOLD is scientifically necessary for action correctness.

No adaptive-value superiority claim is based on Axis A.

## Axis B — Adaptive-Value Benchmark

Purpose:

```text
test whether state-dependent WIDEN/SHRINK switching has measurable economic value over one globally best fixed scalar rule
```

Primary recommended structure:

```text
12 WIDEN
12 SHRINK
=
24 value states
```

No HOLD class is required in the Value benchmark.

Reason:

```text
HOLD states are near-indifferent by definition and dilute an economic-value benchmark.
```

The Value benchmark should contain states where the best action has meaningful value separation.

---

# 4. Scientific Firewall

BV2 may redesign benchmark construction only.

Do NOT change:

```text
M3-D gradient estimator
M3-G-v1 GA1/rho=0.02
delta_theta = 0.20
ESS_grad = 20
bootstrap direction rule
fixed-weight Layer A
CRN semantics
M2 estimator
leakage decomposition
VRF definitions
legality checker
```

No M3-Q.

No controller tuning.

No rho tuning.

No use of controller performance during benchmark selection.

---

# 5. Candidate State Family

A state remains:

```text
frozen event config
+
frozen means
+
frozen weights
+
selected component
+
scalar covariance s2
```

The candidate family must be locked before characterization.

BV2 may reuse the legal proposal-state pool from BV-v0 only if:

```text
raw state definitions are byte-identical
and
reuse is explicitly recorded as prior characterization data
```

If a broader grid is required, it must be preregistered before new characterization.

Do not expand the grid after seeing controller outcomes.

---

# 6. Three-Arm Legality

Every candidate state used by either benchmark must satisfy legality for all three:

```text
SHRINK
BASE
WIDEN
```

No state with an illegal required arm may enter either benchmark.

No illegal state replacement after freeze.

---

# 7. Reference Characterization

Use the frozen high-budget semantics.

Recommended if not reusing valid prior reference records:

```text
N_ref = 500,000 / arm
20 CRN batches
```

For every candidate:

```text
M2(WIDEN)
M2(BASE)
M2(SHRINK)
L_j for every arm
paired uncertainty
reference action
reference margin
```

Verify:

\[
M_2=\sum_j L_j.
\]

---

# 8. Headline-Budget Characterization

Use the exact later controller evaluation budget.

For benchmark construction only, estimate per state:

```text
action-rank stability
value-margin stability
effective indifference probability
realized M2 ratio distribution
```

No controller outputs are allowed.

---

# 9. Unified Value Functional

BV2 must use the **same mathematical functional** to:

```text
select BestFixed
and
measure Oracle adaptive value.
```

Do not select BestFixed with one aggregation and evaluate headroom with another.

Recommended functional:

\[
J(\pi)
=
\operatorname{median}_{state}
\left[
\operatorname{median}_{replicate}
\log\frac{M_2(\pi)}{M_2(BASE)}
\right].
\]

Then define:

\[
BestFixed
=
\arg\min_{f\in\{WIDEN,HOLD,SHRINK\}}
J(f).
\]

For Axis B, HOLD may still be included as a fixed comparator even though HOLD states are absent.

Define adaptive-value gain:

\[
G_{\mathrm{Oracle}}
=
J(BestFixed)-J(Oracle).
\]

If the project prefers a normalized ratio functional instead, it must be fully specified and committed before characterization.

One functional only.

---

# 10. Axis A Eligibility — Decision Benchmark

Decision benchmark states must have stable labels.

## WIDEN / SHRINK

Require:

```text
reference action statistically supported
headline-budget action stability >= 0.80
```

Reference margin should remain meaningful but need not satisfy the stricter Value benchmark margin if decision stability is already strong.

Recommended minimum:

```text
reference margin >= 0.05
```

## HOLD

Require both:

```text
reference indifference rule
AND
headline-budget HOLD stability >= 0.80
```

Reuse the corrected BV-v0 stability semantics unless amended before science.

---

# 11. Axis A Selection

Select exactly:

```text
8 WIDEN
8 HOLD
8 SHRINK
```

Deterministic selection only.

Priority:

1. eligibility;
2. maximize config coverage;
3. maximize headline-budget stability;
4. maximize reference margin for W/S;
5. deterministic `(config_id, s2)` tie-break.

Require:

```text
>=4 configs per class
prefer <=2 states/config/class
```

Axis A exists only for action correctness.

No Oracle-vs-fixed feasibility gate is required for Axis A.

---

# 12. Axis B Eligibility — Value Benchmark

Axis B should contain only states with meaningful economic separation.

Use only:

```text
WIDEN
SHRINK
```

by default.

Each state must satisfy:

```text
reference best action statistically supported
headline-budget best-action stability >=0.80
reference value margin >=0.05
```

Preferred stronger diagnostic:

```text
margin >=0.10
```

but 0.05 is the hard default unless preregistration locks another value.

No HOLD states unless a future amendment defines a distinct measurable-value HOLD concept before any controller run.

---

# 13. Axis B Class Balance

Primary structure:

```text
12 WIDEN
12 SHRINK
```

The reason is structural:

```text
any one fixed action rule should be strong on only one side,
while an adaptive Oracle can switch between sides.
```

Require:

```text
>=4 distinct configs in WIDEN
>=4 distinct configs in SHRINK
```

Prefer:

```text
<=3 states/config/class
```

Selection must not use M3-G-v1 outputs.

---

# 14. Axis B Selection Rule

Within each class select states deterministically:

1. eligible only;
2. maximize config coverage;
3. larger headline-budget action stability;
4. larger economic margin;
5. deterministic `(config_id, s2)` order.

Do not manually select states because Oracle headroom improves.

Oracle feasibility is checked **after** deterministic selection.

---

# 15. BV2-D Gates — Decision Benchmark

## BV2-D0 Validity

Require:

```text
BV-v0 negative tag exists
BV2 task/config committed before science
all parent tags unchanged
candidate source hashes recorded
all three arms legal
no controller leakage
M2=sum L
full pytest pass
```

## BV2-D1 Diversity

Require:

```text
8 WIDEN
8 HOLD
8 SHRINK
```

## BV2-D2 Stability

Require every selected state:

```text
headline-budget stability >=0.80
```

and all HOLD states satisfy the frozen indifference-stability rule.

If D0–D2 pass:

```text
Decision benchmark may be frozen.
```

---

# 16. BV2-V Gates — Value Benchmark

## BV2-V0 Validity

Require:

```text
12 WIDEN + 12 SHRINK selected deterministically
all states legal
all states stable
all states satisfy value-margin threshold
config coverage constraints pass
no controller outputs used
```

## BV2-V1 Fixed-Rule Tradeoff

Before Oracle feasibility, verify that no single fixed W/S action dominates both classes.

Report:

```text
J(ALWAYS_WIDEN)
J(ALWAYS_SHRINK)
J(ALWAYS_HOLD)
```

and class-conditional performance.

If one fixed rule is simultaneously near-optimal on both W and S classes, mark benchmark weak.

---

# 17. BV2-V2 Oracle Feasibility

This is the central Value benchmark gate.

Using the unified functional:

\[
G_{\mathrm{Oracle}}
=
J(BestFixed)-J(Oracle).
\]

Require a meaningful adaptive advantage.

Recommended hard criterion:

```text
equivalent normalized Oracle/BestFixed ratio <= 0.95
```

or, if using log-functional directly:

```text
G_Oracle >= -log(0.95)
```

Use one mathematically equivalent form only.

Optional strong criterion:

```text
Oracle equivalent ratio <=0.90
```

---

# 18. BV2-V3 Symmetric Headroom

Do NOT require Oracle to strictly beat BestFixed on states where:

```text
Oracle action == BestFixed action
```

Those ties are structurally correct.

Instead require meaningful **opposite-class regret**.

Define:

\[
R_{opp,W}
=
\operatorname{median}_{W\ states}
\frac{M_2(ALWAYS\_SHRINK)}{M_2(ALWAYS\_WIDEN)}
\]

\[
R_{opp,S}
=
\operatorname{median}_{S\ states}
\frac{M_2(ALWAYS\_WIDEN)}{M_2(ALWAYS\_SHRINK)}
\]

Require both:

```text
R_opp,W >=1.05
R_opp,S >=1.05
```

This proves that one fixed direction cannot serve both classes well.

Also report class-specific Oracle headroom.

This replaces the old constructive-tie-sensitive strict-win logic.

---

# 19. IMPORTANT: Remove the Old Structural Tie Error

Do NOT use:

```text
Oracle strict wins against BestFixed on same-action states
```

as a required signal of adaptive value.

If Oracle and BestFixed execute the same arm, equality is expected.

Adaptive value must be measured through:

```text
unified aggregate objective improvement
+
opposite-class regret
```

not by demanding impossible strict wins on same-action states.

This is the central metric correction from BV-v0.

---

# 20. Axis B Freeze Condition

Value benchmark can freeze only if:

```text
BV2-V0 PASS
BV2-V1 PASS
BV2-V2 PASS
BV2-V3 PASS
full pytest PASS
```

If Oracle feasibility fails:

```text
VALUE benchmark = infeasible
STOP before controller evaluation
```

No threshold relaxation.

---

# 21. Freeze Artifacts

If the corresponding axis passes, create separately:

```text
docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.md
docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.json

docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.md
docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.json

configs/phase_m3bv2/m3bv2_decision_benchmark.json
configs/phase_m3bv2/m3bv2_value_benchmark.json
```

Commit before controller runs.

After freeze:

```text
NO state replacement
NO metric change
NO functional change
NO margin change
NO controller-informed amendment
```

---

# 22. Controller Evaluation Firewall

No controller may run on Axis B until the Value benchmark passes Oracle feasibility and is frozen.

After freeze, first evaluate only existing frozen controllers:

```text
M3-D
M3-G-v1 GA1/rho=0.02
Always-Widen
Always-Shrink
Always-Hold
Oracle
```

Do NOT start M3-Q yet.

---

# 23. Controller Evaluation — Axis A

Axis A asks only:

```text
Does M3-G-v1 preserve strong W/H/S decision correctness?
```

Report:

```text
W recall
H recall
S recall
balanced accuracy
macro-F1
confusion matrix
```

No adaptive-value superiority claim from Axis A.

---

# 24. Controller Evaluation — Axis B

Axis B asks:

> How much of the available Oracle adaptive-value headroom does M3-G-v1 capture?

Use the same unified functional \(J\).

Report:

\[
G_{v1}
=
J(BestFixed)-J(M3Gv1).
\]

Define Oracle capture:

\[
Capture
=
\frac{G_{v1}}{G_{\mathrm{Oracle}}}.
\]

Headline:

```text
J(M3-G-v1)
J(BestFixed)
J(Oracle)
Oracle headroom
v1 captured headroom
per-class action quality
VRF_budget
```

---

# 25. Controller Gate BV2-C1 — Value Capture

Only meaningful after Oracle feasibility passes.

Recommended hard gate:

```text
M3-G-v1 captures >=50% of Oracle headroom
```

and:

```text
J(M3-G-v1) < J(BestFixed)
```

Optional stronger target:

```text
capture >=75%
```

Do not require impossible strict wins on states where v1 and BestFixed execute the same arm.

---

# 26. Decision Logic

## Case A — Decision benchmark fails
Action-label stability remains unresolved.

Do not interpret value results.

## Case B — Decision passes, Value benchmark Oracle feasibility fails
Benchmark family still lacks usable adaptive economic value.

```text
STOP
No M3-Q
```

## Case C — Both benchmarks pass, M3-G-v1 captures large headroom
Scalar first-order policy has real adaptive value.

Freeze the positive result before any M3-Q.

## Case D — Both benchmarks pass, M3-G-v1 decision accuracy high but value capture low
This is the cleanest justification for:

```text
M3-Q — Curvature-Aware Finite-Step Action Value
```

## Case E — Value benchmark passes but M3-G-v1 decision accuracy collapses
Problem is state/config generalization, not automatically curvature.

---

# 27. Required Tests

At minimum:

```text
test_m3bv2_parent_tags
test_m3bv2_candidate_source_lock
test_m3bv2_three_arm_legality
test_m3bv2_reference_crn
test_m3bv2_m2_equals_sum_leakage
test_m3bv2_decision_class_balance
test_m3bv2_decision_hold_stability
test_m3bv2_decision_config_coverage
test_m3bv2_value_12w12s
test_m3bv2_value_margin
test_m3bv2_value_stability
test_m3bv2_unified_objective
test_m3bv2_bestfixed_same_objective
test_m3bv2_oracle_feasibility
test_m3bv2_opposite_class_regret
test_m3bv2_selection_deterministic
test_m3bv2_no_controller_selection_leakage
test_m3bv2_freeze_schema
```

Then:

```bash
python -m pytest -q
```

---

# 28. Required Figures

Decision benchmark:

1. D1 — W/H/S state map  
2. D2 — reference margin/stability  
3. D3 — config coverage  
4. D4 — later controller confusion matrix  

Value benchmark:

5. V1 — W/S reference M2 curves  
6. V2 — fixed-rule tradeoff by class  
7. V3 — Oracle vs BestFixed unified objective  
8. V4 — opposite-class regret  
9. V5 — Oracle headroom distribution  
10. V6 — after approval: M3-G-v1 captured headroom  

---

# 29. Required Reports

Create:

```text
docs/phase_m3bv2/
├── M3_BV2_Dual_Axis_Benchmark_Task.md
├── M3_BV2_Methodology.md
├── M3_BV2_Validity_Audit.md
├── M3_BV2_Benchmark_Report.md
└── M3_BV2_Final_Report.md
```

Before controller evaluation, Final Report should contain benchmark-only results only.

---

# 30. Claim Boundaries

If both benchmarks freeze:

> We constructed separate preregistered decision and adaptive-value benchmarks: the decision benchmark tests stable WIDEN/HOLD/SHRINK action correctness, while the value benchmark tests measurable WIDEN/SHRINK switching advantage over one globally fixed scalar action rule under a unified objective.

Do NOT claim controller superiority until controller evaluation.

If Value benchmark fails:

> The tested candidate family still does not provide sufficient symmetric adaptive-value headroom under the frozen value functional.

---

# 31. Negative-Result Discipline

Forbidden after outcome inspection:

```text
change 12W/12S balance
reintroduce HOLD to rescue Oracle metric
change unified objective
change Oracle threshold
change opposite-class regret threshold
change config coverage
drop difficult states
change evaluation budget
change margin threshold
```

Any amendment must be committed before additional characterization and must explicitly state observed outcomes.

No amendment after controller results exist.

---

# 32. Recommended Execution Order

```text
F0  correct BV-v0 wording
 ↓
F1  full pytest
 ↓
F2  tag RareTopo-M3-BV-v0 negative result
 ↓
B0  create BV2 branch
 ↓
B1  commit BV2 task + construction lock
 ↓
B2  build/reuse candidate characterization
 ↓
B3  construct Decision benchmark candidates
 ↓
B4  construct Value benchmark candidates
 ↓
B5  unified-objective BestFixed audit
 ↓
B6  Oracle feasibility + opposite-class regret
 ↓
B7  deterministic freeze selection
 ↓
B8  benchmark-only tests + full pytest
 ↓
B9  freeze Decision and Value benchmarks
 ↓
STOP AND REPORT
 ↓
only after approval:
evaluate M3-G-v1
```

---

# 33. First Mandatory Checkpoint

Do not run M3-G-v1 on BV2 yet.

Stop after benchmark freeze / benchmark infeasibility decision and report:

| Item | Result |
|---|---|
| M3-BV-v0 correction commit | |
| `RareTopo-M3-BV-v0` tag | |
| BV2 branch | |
| BV2 task commit | |
| candidate source | |
| Decision eligible W/H/S | |
| Decision selected | 8/8/8 |
| Decision config coverage | |
| BV2-D0/D1/D2 | |
| Value eligible W/S | |
| Value selected | 12/12 |
| Value config coverage | |
| unified functional | |
| BestFixed | |
| J(BestFixed) | |
| J(Oracle) | |
| Oracle headroom | |
| opposite-class regret W | |
| opposite-class regret S | |
| BV2-V0/V1/V2/V3 | |
| Decision freeze commit | |
| Value freeze commit | |
| full pytest | |
| controller runs on BV2 | **0** |

---

# 34. Core Principle

BV2 must permanently separate:

\[
\boxed{\text{Decision correctness}}
\]

from:

\[
\boxed{\text{Adaptive economic value}}
\]

The Decision benchmark asks:

```text
Did the controller choose WIDEN / HOLD / SHRINK correctly?
```

The Value benchmark asks:

```text
Does switching between WIDEN and SHRINK create measurable value over one globally fixed policy?
```

Do not force HOLD states to carry an adaptive-value signal they were never designed to provide.
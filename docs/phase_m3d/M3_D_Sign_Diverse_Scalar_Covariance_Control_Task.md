# M3-D Sign-Diverse Scalar Covariance-Control Benchmark — Preregistered Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems  
> **Method Track:** M3-D — Sign-Diverse Scalar Covariance-Control Benchmark  
> **Status:** **PREREGISTERED — NOT STARTED**  
> **Parent frozen tags:** `RareTopo-H3-v1.0`, `RareTopo-M1-v0`, `RareTopo-M1-D-v1.0`, `RareTopo-M2-v0`  
> **Immediate predecessor:** M3-v0 — Second-Moment Gradient Covariance Control  
> **M3-v0 requirement:** FREEZE/TAG FIRST  
> **Date:** 2026-08-27

---

# 0. FIRST ACTION — Freeze M3-v0

M3-D scientific runs are forbidden until M3-v0 is formally frozen.

Target tag:

```text
RareTopo-M3-v0
```

Before tagging:

```bash
git branch --show-current
git status --short
git rev-parse HEAD
python -m pytest -q
```

Confirm:

- M3 freeze-audit corrections are committed;
- local dominated-envelope assumption replaces the invalid global `q >= c > 0` argument;
- `M2 = sum_j L_j` decomposition is closed;
- Gate M3-3 is recorded as **FAIL**;
- the frozen conclusion says:
  - local second-moment gradient direction supported;
  - predicted widening beats the opposite perturbation;
  - no adaptive advantage over Always-Widen established;
  - full-matrix escalation remains blocked;
- H3 / M1-v0 / M1-D / M2 frozen tags are unchanged;
- full pytest exits 0.

Then:

```bash
git tag -a RareTopo-M3-v0 -m "Freeze RareTopo M3-v0: local second-moment covariance-gradient direction validated; adaptive advantage over Always-Widen not established"
git push origin RareTopo-M3-v0
```

If the tag exists and points elsewhere, STOP. Do not force-tag.

---

# 1. Motivation

M3-v0 validated the frozen scalar covariance-gradient controller:

```text
g < 0            -> WIDEN
g > 0            -> SHRINK
95% CI crosses 0 -> HOLD
ESS_grad < 20    -> HOLD_LOW_ESS
```

and showed that the predicted widening direction reduces independent-evaluation \(M_2\) and beats the opposite perturbation.

However, the frozen M1-D/M3-v0 benchmark is overwhelmingly widening-dominant:

```text
Gradient Acc_dir ≈ Always-Widen Acc_dir
adaptive advantage ≈ 0 pp
```

Therefore M3-v0 establishes a local descent mechanism but not adaptive controller value.

M3-D exists to answer exactly this missing question.

---

# 2. Scientific Firewall

M3-D freezes the M3-v0 controller.

The following are IMMUTABLE:

```text
covariance-gradient formula
responsibility r_k = pi_k q_k / q
fixed-weight Layer A
ESS_grad threshold = 20
fixed-stratified bootstrap
95% CI sign rule
delta_theta_main = 0.20
step sensitivity = [0.10, 0.20, 0.40]
relative tie tolerance = 0.01
Always-Widen / Always-Shrink / Always-Hold comparators
CRN discipline
probability / variance estimators
VRF definitions
legality checker
```

M3-D may NOT:

- alter the gradient formula;
- tune the main step after results;
- change CI action logic;
- add full-matrix covariance control;
- jointly optimize means / covariance / weights in Layer A;
- use oracle direction online;
- delete difficult benchmark states after adaptive runs;
- reinterpret M3-v0 as adaptive-success.

M3-D is a **benchmark-extension + adaptive-value test**, not a controller redesign.

---

# 3. Primary Research Question

Can the frozen M3 scalar gradient controller provide measurable adaptive value when the proposal-state benchmark genuinely contains:

```text
WIDEN-optimal
SHRINK-optimal
HOLD-near-optimal
```

states?

The desired evidence is not merely correct gradient sign. It is:

\[
\text{Gradient policy}
>
\max(
\text{Always-Widen},
\text{Always-Shrink},
\text{Always-Hold}
)
\]

under matched sampling and evaluation budgets.

---

# 4. Benchmark Unit

A benchmark state consists of:

```text
frozen event/topology config
+
frozen mixture means and weights
+
selected controlled component
+
base scalar covariance s_k^2
```

This intentionally varies the **proposal state**, not the controller.

The same event geometry may require different covariance actions at different proposal scales because the second-moment gradient is proposal-dependent.

---

# 5. Event Family

Reuse the frozen M1-D event configs:

```text
c000
c001
c004
c006
c007
c010
c017
c020
```

Do not regenerate event geometry.

Only diversify the current scalar covariance of the selected component.

---

# 6. Candidate Scalar-Covariance Grid

For each frozen config construct legal states:

\[
\Sigma_k=s^2I.
\]

Preregister:

```text
s2_grid = [0.55, 0.70, 0.85, 1.00, 1.25, 1.60, 2.00]
```

Every state must pass the frozen legality checker.

If illegal:

```text
ILLEGAL_PRE_FREEZE
```

Do not replace the value post hoc.

This grid is a benchmark-state generator, not a gradient hyperparameter search.

---

# 7. Offline Reference Characterization

Before any adaptive M3-D runs, characterize every legal `(config, s2_state)` offline.

At each state evaluate with matched CRN:

\[
M_2(\theta-\delta),\qquad
M_2(\theta),\qquad
M_2(\theta+\delta),
\]

where:

```text
delta = 0.20
```

Recommended fixed reference budget:

```text
N_ref = 500,000 per arm
```

If an analytic/deterministic reference method already exists, it may replace stochastic reference only if its use is fixed before characterization and applied uniformly.

Save all reference values and uncertainty.

---

# 8. Offline Oracle Action Label

Use frozen tie tolerance:

```text
tau = 0.01
```

### WIDEN

if WIDEN improves BASE by more than 1% and is better than SHRINK.

### SHRINK

if SHRINK improves BASE by more than 1% and is better than WIDEN.

### HOLD

if neither perturbation improves BASE by more than 1%.

Reference uncertainty must support the label. Otherwise:

```text
REFERENCE_AMBIGUOUS
```

and the state is ineligible.

---

# 9. Direction-Margin Gate

For WIDEN/SHRINK states define:

\[
\Delta_{dir}
=
\frac{
M_2(\text{second-best})-M_2(\text{best})
}{
M_2(\text{best})
}.
\]

Require:

```text
Delta_dir >= 0.05
```

For HOLD require both perturbations to lie within a preregistered ±3% neighborhood of BASE:

```text
abs(M2(widen)/M2(base)-1) <= 0.03
abs(M2(shrink)/M2(base)-1) <= 0.03
```

Do not relax thresholds after adaptive results.

---

# 10. Sign-Diversity Construction Gate

The candidate pool must contain at least:

```text
>= 8 stable WIDEN states
>= 8 stable SHRINK states
>= 8 stable HOLD states
```

distributed across multiple frozen configs.

If not:

```text
STOP
```

Do not proceed to adaptive trials.

Any redesign requires a preregistration amendment before online runs.

---

# 11. Candidate Pool

Maximum pool:

```text
8 configs × 7 covariance states = 56
```

For each state record:

```text
config_id
s2
legality
M2_shrink_ref
M2_base_ref
M2_widen_ref
reference uncertainty
oracle action
direction margin
```

Output:

```text
results/phase_m3d/reference/m3d_candidate_pool.json
```

---

# 12. Frozen Headline Benchmark

Within each action class sort eligible states by:

```text
(config_id, s2)
```

Select the first:

```text
8 WIDEN
8 SHRINK
8 HOLD
```

for exactly:

\[
24
\]

frozen proposal states.

No adaptive-result-driven substitutions.

Create BEFORE online runs:

```text
docs/phase_m3d/M3_D_Benchmark_Freeze.md
docs/phase_m3d/M3_D_Benchmark_Freeze.json
```

Record:

```text
task commit
candidate pool
reference protocol
all labels/margins
selected 24 states
freeze timestamp
hash
```

Commit the benchmark freeze before any adaptive run.

---

# 13. No Oracle Leakage

Offline reference fields must never enter the online controller.

Online controller may access only:

```text
pilot samples
sample source densities
current proposal q
selected component metadata
current covariance
```

It may NOT access:

```text
oracle action
reference M2 values
direction margin
action class
```

Add structural no-oracle-leakage tests.

---

# 14. Online Trials

For every frozen state:

```text
pilot_n = 20,000
alpha_p = 0.5
seeds = [2026..2033]
```

Total headline trials:

\[
24\times8=192.
\]

Use the unchanged M3-v0 gradient estimator and bootstrap.

---

# 15. Frozen Gradient Action

Use exactly:

```text
ESS_grad < 20 -> HOLD_LOW_ESS
95% CI upper < 0 -> WIDEN
95% CI lower > 0 -> SHRINK
otherwise -> HOLD_UNCERTAIN
```

Deployment action maps both HOLD reasons to:

```text
HOLD
```

while preserving reason codes.

---

# 16. Headline Layer A Comparators

Each trial evaluates with matched CRN:

```text
GRADIENT
ALWAYS_WIDEN
ALWAYS_SHRINK
ALWAYS_HOLD
```

All share:

```text
same pilot
same current proposal
same selected component
same means
same mixture weights
same other covariances
same final evaluation random base
same delta_theta = 0.20
```

Only the scalar covariance action differs.

Layer A is the headline adaptive-value experiment.

---

# 17. Oracle Comparator

Secondary offline comparator:

```text
ORACLE_ACTION
```

uses the frozen reference action label.

It must never enter online action logic.

Purpose: quantify Gradient-to-Oracle action regret.

---

# 18. Primary Metric — Three-Class Accuracy

\[
Acc_3
=
P(A_{gradient}=A_{oracle}).
\]

Because the benchmark is balanced, also report:

```text
per-class recall
macro-F1
balanced accuracy
confusion matrix
```

Do not report only raw accuracy.

---

# 19. Adaptive Regret

For each trial:

\[
R_{M2}
=
\frac{
M_2(GRADIENT)-M_2(ORACLE)
}{
M_2(ORACLE)
}.
\]

Report:

```text
global median
per-class median
paired bootstrap CI
```

---

# 20. Best Fixed-Rule Comparison

Compare Gradient against:

```text
Always-Widen
Always-Shrink
Always-Hold
```

under the preregistered aggregate:

```text
median of per-state seed medians
```

Define the globally best fixed rule by that aggregate.

Headline ratio:

\[
R_{fixed}
=
\frac{
M_2(GRADIENT)
}{
M_2(BEST\ FIXED)
}.
\]

This is the central adaptive-value metric.

---

# 21. Class-Conditional Performance

For true:

```text
WIDEN
SHRINK
HOLD
```

classes separately report:

\[
M_2(GRADIENT)/M_2(BASE)
\]

and Gradient versus each fixed rule.

Adaptive success must not be driven by one class only.

---

# 22. Gate M3D-0 — Validity

Require:

- `RareTopo-M3-v0` frozen first;
- task committed before reference characterization;
- benchmark freeze committed before online runs;
- parent tags unchanged;
- no oracle leakage;
- 24-state balanced benchmark complete;
- no missing cells;
- valid source-density accounting;
- CRN pairing valid;
- full `python -m pytest -q` pass.

Failure => INVALID.

---

# 23. Gate M3D-1 — Sign Diversity

Frozen benchmark must contain exactly:

```text
8 WIDEN
8 SHRINK
8 HOLD
```

with:

```text
reference ambiguous = 0
illegal = 0
```

Hard gate.

---

# 24. Gate M3D-2 — Adaptive Action Accuracy

Require:

\[
Acc_3\ge0.75.
\]

Per-class recall:

```text
WIDEN >= 0.70
SHRINK >= 0.70
HOLD >= 0.60
```

---

# 25. Gate M3D-3 — Beat the Best Fixed Rule

This is the main novelty gate.

Require:

\[
\boxed{
\operatorname{median}_{state}
\left[
\operatorname{median}_{seed}
\frac{M_2(GRADIENT)}{M_2(BEST\ FIXED)}
\right]
\le0.90
}
\]

and Gradient must beat each fixed rule on at least:

```text
16 / 24 states
```

by per-state seed median.

---

# 26. Gate M3D-4 — Near Oracle

Require:

\[
\boxed{
\operatorname{median}
\frac{M_2(GRADIENT)}{M_2(ORACLE)}
\le1.10
}
\]

over all frozen states.

---

# 27. Gate M3D-5 — Cross-Class Robustness

Require Gradient vs BASE:

```text
WIDEN class median ratio <= 0.95
SHRINK class median ratio <= 0.95
HOLD class median ratio <= 1.02
```

This prevents a controller from winning globally while failing one action regime.

---

# 28. Gate M3D-6 — Leakage Safety

For at least:

```text
22 / 24 states
```

require:

\[
\operatorname{median}_{seed}
\max_j
\frac{L_j(GRADIENT)}{L_j(BASE)}
\le2.
\]

Also verify:

\[
M_2=\sum_jL_j
\]

for every evaluated arm within numerical tolerance.

---

# 29. Strong Gate — Budget Efficiency

Strong result:

\[
\operatorname{median}
VRF_{\mathrm{budget}}(GRADIENT)>1
\]

under deployable call accounting.

This is not required for core adaptive-value success.

---

# 30. Mandatory Always-Widen Test

M3-v0 could not beat Always-Widen because almost every active state wanted widening.

Therefore M3-D must explicitly test:

\[
Gradient
\quad vs\quad
Always\text{-}Widen.
\]

If Gradient still does not beat Always-Widen despite a balanced benchmark:

> adaptive value remains unsupported.

Do not soften this conclusion.

---

# 31. M3-v0 Replay Control

Replay the original unit-scale M3-v0 proposal states as a secondary control.

Expected behavior:

```text
mostly WIDEN
Gradient ≈ Always-Widen
```

Purpose:

> show that any M3-D adaptive advantage comes from sign-diverse states, not controller changes.

This replay does not enter headline gates.

---

# 32. Proposal-State Transition Analysis

For a fixed event config, record offline action across scale:

```text
small s2 -> ?
mid s2   -> ?
large s2 -> ?
```

A particularly useful pattern is:

```text
WIDEN -> HOLD -> SHRINK
```

as proposal width increases.

Do not preregister monotonicity as a required gate unless it is guaranteed before online runs.

---

# 33. Required Ablations

## D-A
Gradient vs all fixed rules.

## D-B
ESS_grad stratification.

## D-C
Frozen step sensitivity:

```text
0.10
0.20
0.40
```

Main remains 0.20.

## D-D
Point-sign vs CI-sign diagnostic.

Main remains CI-sign.

## D-E
Oracle-action regret.

## D-F
M3-v0 replay.

---

# 34. Layer B — Frozen Weight Reoptimization

Only after Layer A is fully audited.

Run frozen M1-v0 SLSQP weight reoptimization after each scalar action.

Layer B is secondary:

```text
headline adaptive-value gate = Layer A
Layer B = deployment interaction
```

Layer B cannot rescue a failed Layer A M3D-3.

---

# 35. Statistical Hierarchy

Paired unit:

```text
(state, seed)
```

Hierarchy:

1. within state: 8 seeds;
2. within action class: 8 states;
3. global: 24 states.

Headline:

```text
median of per-state seed medians
```

Also report:

```text
paired bootstrap 95% CI
state win count
seed win count
per-class results
```

Do not treat all 192 rows as IID.

---

# 36. Required Tests

At minimum:

```text
test_m3d_candidate_state_legality
test_m3d_reference_widen_label
test_m3d_reference_shrink_label
test_m3d_reference_hold_label
test_m3d_direction_margin
test_m3d_balanced_benchmark_freeze
test_m3d_no_oracle_leakage
test_m3d_controller_parity_with_m3
test_m3d_same_pilot
test_m3d_fixed_weights_layer_a
test_m3d_crn_counterfactuals
test_m3d_three_class_accuracy
test_m3d_best_fixed_rule_metric
test_m3d_oracle_regret
test_m3d_modewise_decomposition
test_m3d_result_schema
```

Run:

```bash
python -m pytest -q
```

before final gate audit.

---

# 37. Required Outputs

```text
docs/phase_m3d/
├── M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md
├── M3_D_Benchmark_Freeze.md
├── M3_D_Methodology.md
├── M3_D_Validity_Audit.md
└── M3_D_Final_Report.md

configs/phase_m3d/
├── m3d_candidate_state_grid.json
├── m3d_reference_characterization.json
└── m3d_online_v0.json

src/hyptraj/m3d/
├── benchmark_states.py
├── reference_direction.py
├── adaptation.py
└── metrics.py

scripts/
├── run_m3d_reference_pool.py
├── freeze_m3d_benchmark.py
├── run_m3d_layer_a.py
├── run_m3d_layer_b.py
├── run_m3d_gate_audit.py
└── run_m3d_figures.py

results/phase_m3d/
├── reference/
├── layer_a/
├── layer_b/
├── ablations/
└── summary/

figures/phase_m3d/
└── figure_M3D_*.png
```

---

# 38. Required Figures

1. **M3D-1 Action-State Map** — \(s^2\) vs WIDEN/HOLD/SHRINK reference action  
2. **M3D-2 Gradient CI vs Oracle Action**  
3. **M3D-3 Three-Class Confusion Matrix**  
4. **M3D-4 Gradient vs Fixed Rules \(M_2\)**  
5. **M3D-5 Gradient / Oracle Regret**  
6. **M3D-6 Per-Class Performance**  
7. **M3D-7 ESS_grad vs Correctness**  
8. **M3D-8 Budget VRF**, MC boundary = 1  

---

# 39. Machine-Readable Trial Schema

```json
{
  "schema_version": "raretopo-m3d-v0",
  "config_id": "c000",
  "state_id": "c000_s2_055",
  "seed": 2026,
  "base_s2": 0.55,
  "oracle_action": "WIDEN",
  "oracle_direction_margin": 0.0,
  "gradient": {
    "g_hat": 0.0,
    "g_ci_low": 0.0,
    "g_ci_high": 0.0,
    "ESS_grad": 0.0,
    "action": "WIDEN"
  },
  "arms": {
    "hold": {"M2": 0.0, "mode_L": {}},
    "widen": {"M2": 0.0, "mode_L": {}},
    "shrink": {"M2": 0.0, "mode_L": {}},
    "gradient": {"M2": 0.0, "mode_L": {}},
    "oracle": {"M2": 0.0, "mode_L": {}}
  },
  "metrics": {
    "action_correct": true,
    "regret_M2": 0.0,
    "VRF_proposal": 0.0,
    "VRF_budget": 0.0
  },
  "validity": {}
}
```

---

# 40. Claim Boundary

If M3D-0..6 pass:

> **On a preregistered sign-diverse proposal-state benchmark containing widening-, shrinking-, and hold-optimal states, the frozen second-moment gradient controller adapts its scalar covariance action to the current proposal state and outperforms every fixed widening/shrinking/holding rule under matched sampling and evaluation budgets.**

If action accuracy passes but M3D-3 fails:

> **The gradient identifies proposal-state-dependent covariance directions, but the measured action-selection advantage is insufficient to outperform the best fixed rule under the preregistered benchmark and step size.**

If Always-Widen remains competitive/better:

> **Sign diversity exists, but the current finite-sample gradient policy does not convert it into robust adaptive value.**

Do not claim:

```text
universal optimality
global convergence
full-matrix success
high-dimensional transfer
real-system cost efficiency
```

---

# 41. Negative Result Policy

## A — Balanced sign diversity cannot be built
STOP before adaptive runs.

## B — Sign-diverse benchmark exists, action accuracy low
Finite-sample gradient is not robust across direction regimes.

## C — Accuracy high, best-fixed advantage absent
Correct classification does not translate into enough \(M_2\) value.

## D — Gradient beats fixed rules but not Oracle
Adaptive controller works; action-selection uncertainty remains.

## E — Gradient near Oracle, VRF<1
Adaptive control works but remains below crude-MC cost efficiency.

## F — Gradient near Oracle, VRF>1
Strong M3-D success.

No threshold relaxation or result-driven state deletion.

---

# 42. Stop / Go Rules

```text
M3-v0 not frozen -> STOP
M3-D task not committed before reference pool -> INVALID
candidate pool lacks 8/8/8 sign diversity -> STOP
benchmark freeze not committed before online run -> INVALID
oracle leakage detected -> INVALID
full pytest failure -> STOP
```

Full-matrix covariance control remains blocked until M3-D establishes real adaptive value.

---

# 43. Preregistration Lock

After task commit freeze:

```text
parent tags
s2_grid
offline reference protocol
tau = 0.01
direction margin = 0.05
HOLD ±3% rule
8/8/8 benchmark composition
benchmark selection ordering
pilot_n = 20,000
alpha = 0.5
seed set
delta_theta = 0.20
ESS_grad = 20
95% CI policy
fixed-weight Layer A
comparators
M3D-0..6
Strong Gate
```

Any change requires:

```text
M3_D_PREREG_AMENDMENT_<date>.md
```

before adaptive runs.

---

# 44. Execution Order

```text
Step 0  Freeze M3-v0 -> RareTopo-M3-v0
   ↓
D0      Commit this M3-D task
   ↓
D1      Build legal proposal-state candidate pool
   ↓
D2      Offline WIDEN/HOLD/SHRINK reference characterization
   ↓
D3      Verify 8/8/8 sign diversity
   ↓
D4      Freeze 24-state benchmark + hash + commit
   ↓
D5      No-oracle/parity tests
   ↓
D6      Run Layer A 24 × 8 trials
   ↓
D7      Gate adaptive accuracy + best-fixed advantage
   ↓
D8      Only then Layer B / sensitivity
   ↓
D9      Final report / freeze decision
```

---

# 45. One-Line State

```text
H3      = frozen
M1-v0   = frozen
M1-D    = frozen
M2-v0   = frozen negative result
M3-v0   = freeze before M3-D
M3-D    = preregistered sign-diverse adaptive-value benchmark
next    = freeze M3-v0, then construct offline WIDEN/HOLD/SHRINK proposal-state pool
```

# M3 Second-Moment Gradient Covariance Control — Preregistered Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems  
> **Method Track:** M3 — Second-Moment Gradient Covariance Control  
> **Document type:** Freeze instruction + preregistered theory / method / experiment task  
> **Status:** **M2 MUST BE FROZEN FIRST; M3 PREREGISTERED — NOT STARTED**  
> **Parent frozen science:** `RareTopo-H3-v1.0`  
> **Parent frozen adaptive method:** `RareTopo-M1-v0`  
> **Parent frozen multi-mode benchmark:** `RareTopo-M1-D-v1.0`  
> **Immediate predecessor:** M2 — Variance-Geometry Covariance Adaptation, executed with a clean negative result  
> **Date:** 2026-08-27  

---

# 0. FIRST ACTION — Freeze M2 Before Any M3 Work

M2 produced a scientifically useful negative result and must be frozen before any M3 scientific work begins.

Frozen M2 conclusion:

> **Local variance-HDR covariance matching is not supported as a proposal covariance control rule on the frozen M1-D benchmark. Descriptive variance geometry and a valid second-moment descent control target are not the same object.**

M2 must not be overwritten, repaired in place, or silently reinterpreted as a successful covariance-adaptation method.

## Required M2 freeze procedure

Target tag:

```text
RareTopo-M2-v0
```

Determine the exact M2 final HEAD from the repository at execution time. Do not invent it.

Before tagging:

```bash
git branch --show-current
git status --short
git rev-parse HEAD
pytest -q
```

Confirm:

- full pytest exit code = 0;
- `RareTopo-H3-v1.0`, `RareTopo-M1-v0`, `RareTopo-M1-D-v1.0` remain unchanged;
- M2 Task / Methodology / Legality Audit / Final Report are present;
- M2 gate audit records M2-0 PASS, M2-1 PASS, M2-2 FAIL, M2-3 FAIL, M2-4 PASS, M2-5 FAIL, Strong NOT PASSED;
- no positive covariance-control claim is made.

Create:

```bash
git tag -a RareTopo-M2-v0 -m "Freeze RareTopo M2-v0 negative result: local variance-HDR covariance matching is not a valid covariance control rule on the frozen M1-D benchmark"
git push origin RareTopo-M2-v0
```

If the tag already exists but points elsewhere, stop. Do not force-tag.

Create/update:

```text
docs/phase_m2/M2_Freeze_Summary.md
```

recording final HEAD, pytest, gate verdicts, negative conclusion, limitations, parent tags, and tag commit.

Only after M2 is frozen may M3 begin.

---

# 1. M3 Motivation

M2 tested:

\[
\widehat C_{\eta,k}^{V} \rightarrow \Sigma_k^{new}
\]

and failed systematically.

The lesson is:

\[
\boxed{\text{descriptive variance geometry} \neq \text{descent control law}}
\]

M3 instead derives covariance control directly from:

\[
M_2(q)=\int_A \frac{p(x)^2}{q(x)}dx.
\]

The objective is a genuine local control signal:

\[
\boxed{\nabla_{\Sigma_k} M_2}
\]

rather than a descriptive covariance-matching heuristic.

---

# 2. Scientific Firewall

The following remain frozen:

```text
RareTopo-H3-v1.0
RareTopo-M1-v0
RareTopo-M1-D-v1.0
RareTopo-M2-v0
M1-D benchmark set
event / topology definitions
variance selector
selected-mode logic
exploration alpha = 0.5
pilot_n = 20,000
final_eval_n = 100,000
seed set = [2026..2033]
probability / variance estimators
stratified bootstrap
component means
birth logic
VRF definitions
```

M3-v0 must not:

- tune M2's lambda;
- change frozen benchmark configs;
- learn a policy;
- jointly optimize mean/covariance/weights/components;
- add component deletion;
- claim global covariance optimality;
- start full-matrix control before scalar directional control is validated.

---

# 3. Primary Research Question

Can a finite-sample estimate of the derivative of the IS second moment with respect to covariance correctly predict whether a selected Gaussian proposal component should **WIDEN, SHRINK, or HOLD**, and does a preregistered small step in the predicted direction reduce independent-evaluation \(M_2\)?

M3-v0 starts with scalar isotropic control only:

\[
\Sigma_k=s_k^2 I.
\]

---

# 4. Mathematical Setup

Let:

\[
q(x)=\sum_j \pi_j q_j(x),
\qquad
q_k(x)=\mathcal N(x;m_k,\Sigma_k).
\]

Second moment:

\[
M_2(q)=\int_A \frac{p(x)^2}{q(x)}dx.
\]

Normalized variance measure:

\[
\nu_V^{(q)}(dx)
=
\frac{\mathbf1_A(x)p(x)^2/q(x)}{M_2(q)}dx.
\]

Mixture responsibility:

\[
\boxed{
r_k(x)=\frac{\pi_k q_k(x)}{q(x)}
}
\]

with \(0\le r_k\le1\) and \(\sum_k r_k=1\).

---

# 5. Candidate Matrix Gradient Theorem

M3 must formally derive and proof-audit:

\[
\boxed{
\nabla_{\Sigma_k}M_2
=
\frac{M_2}{2}
\Sigma_k^{-1}
\left[
\mathbb E_{\nu_V}[r_k]\Sigma_k
-
\mathbb E_{\nu_V}
\left[
r_k(X-m_k)(X-m_k)^\top
\right]
\right]
\Sigma_k^{-1}
}
\]

for fixed means, weights, and other covariances under the required support, differentiability, and integrability assumptions.

Equivalent form:

\[
\nabla_{\Sigma_k}M_2
=
\frac{M_2}{2}
\mathbb E_{\nu_V}
\left[
r_k
\left(
\Sigma_k^{-1}
-
\Sigma_k^{-1}\delta\delta^\top\Sigma_k^{-1}
\right)
\right],
\]

where \(\delta=X-m_k\).

This is a candidate theorem until the derivation, assumptions audit, and finite-difference validation all pass.

---

# 6. Responsibility-Weighted Stationary Target

Define:

\[
\boxed{
T_k
=
\frac{
\mathbb E_{\nu_V}
[
r_k(X-m_k)(X-m_k)^\top
]
}{
\mathbb E_{\nu_V}[r_k]
}
}
\]

when the denominator is positive.

A fixed-\((m,\pi)\) stationary condition is:

\[
\boxed{\Sigma_k=T_k}
\]

if the gradient identity is valid.

Important distinction from failed M2:

| M2 descriptive object | M3 control object |
|---|---|
| top-eta HDR only | full \(
u_V^{(q)}\) |
| mode-conditioned | responsibility-weighted |
| centered at HDR centroid | centered at frozen proposal mean |
| descriptive local shape | derived from \(M_2\) derivative |

---

# 7. Isotropic Scalar Derivative

Set:

\[
\Sigma_k=s_k^2I,
\qquad
\theta_k=\log s_k^2.
\]

Use implementation names:

```text
dim   = state dimension
delta = X - m_k
```

Candidate derivative:

\[
\boxed{
g_k
=
\frac{\partial M_2}{\partial\theta_k}
=
\frac{M_2}{2}
\mathbb E_{\nu_V}
\left[
r_k
\left(
\mathrm{dim}
-
\frac{\|\delta\|^2}{s_k^2}
\right)
\right]
}
\]

Define:

\[
D_k
=
\frac{
\mathbb E_{\nu_V}
[
r_k\|\delta\|^2
]
}{
\mathbb E_{\nu_V}[r_k]
}.
\]

Then:

\[
g_k \propto \mathrm{dim}-D_k/s_k^2.
\]

Interpretation:

```text
g_k < 0  -> WIDEN
g_k > 0  -> SHRINK
g_k ~ 0  -> HOLD
```

This directional rule is the central M3-v0 hypothesis.

---

# 8. Finite-Sample Estimator

For pilot samples \(x_i\sim r_i\), reuse frozen variance-mass importance values:

\[
a_i
=
\mathbf1_A(x_i)
\frac{p(x_i)^2}{q(x_i)r_i(x_i)}.
\]

Then:

\[
\widehat M_2=\frac1N\sum_i a_i,
\qquad
\bar a_i=\frac{a_i}{\sum_j a_j}.
\]

Responsibility:

\[
\widehat r_{k,i}
=
\frac{\pi_kq_k(x_i)}{q(x_i)}.
\]

Estimate:

\[
\widehat\mu_{r,k}
=
\sum_i \bar a_i\widehat r_{k,i},
\]

\[
\widehat D_k
=
\frac{
\sum_i
\bar a_i\widehat r_{k,i}
\|x_i-m_k\|^2
}{
\widehat\mu_{r,k}
},
\]

and:

\[
\boxed{
\widehat g_k
=
\frac{\widehat M_2}{2}
\widehat\mu_{r,k}
\left(
\mathrm{dim}
-
\frac{\widehat D_k}{s_k^2}
\right)
}
\]

when validity conditions pass.

---

# 9. Gradient ESS

Define normalized control weights:

\[
c_i
=
\frac{
\bar a_i r_{k,i}
}{
\sum_j\bar a_jr_{k,j}
}.
\]

Then:

\[
\boxed{
ESS_{grad}=\frac1{\sum_i c_i^2}
}
\]

Main safeguard:

```text
ESS_grad >= 20
```

Otherwise:

```text
HOLD_LOW_ESS
```

---

# 10. Gradient Bootstrap and Decision Rule

Use the frozen fixed-stratified bootstrap:

- resample within p-source stratum;
- resample within q-source stratum;
- preserve stratum sizes;
- recompute \(\widehat g_k\).

Store:

```text
g_hat
g_ci_low
g_ci_high
ESS_grad
decision
```

Decision:

### WIDEN
if upper 95% CI < 0.

### SHRINK
if lower 95% CI > 0.

### HOLD_UNCERTAIN
if CI contains 0.

### HOLD_LOW_ESS
if ESS < 20.

### HOLD_INVALID
if validity / legality fails.

Do not use point-sign alone in headline experiments.

---

# 11. Preregistered Scalar Step

Main:

```text
delta_theta_main = 0.20
```

Thus:

\[
s_{new}^2=s_{old}^2e^{\pm0.20}.
\]

Interpretation:

```text
WIDEN -> +0.20
SHRINK -> -0.20
HOLD -> 0
```

Sensitivity only:

```text
[0.10, 0.20, 0.40]
```

Main remains 0.20.

---

# 12. Mandatory Fixed-Weight Layer

The gradient is derived for fixed mixture weights.

Therefore Layer A must lock:

```text
selected mode
all component means
all mixture weights
all other covariances
component count
```

Only the scalar covariance of the selected component changes.

Layer B may later run the frozen M1-v0 SLSQP weight optimizer, but Layer B cannot rescue a failed Layer A directional hypothesis.

---

# 13. Counterfactual Direction Test

For each non-HOLD trial evaluate with matched CRN:

```text
BASE
WIDEN
SHRINK
GRADIENT-PREDICTED
```

If gradient predicts WIDEN:

\[
\Sigma_{pred}=e^{+0.20}\Sigma_0,
\qquad
\Sigma_{opp}=e^{-0.20}\Sigma_0.
\]

If gradient predicts SHRINK, reverse.

Primary directional evidence:

\[
M_2(pred)<M_2(base)
\]

and:

\[
M_2(pred)<M_2(opposite).
\]

---

# 14. Evaluation-Best Direction

Using independent final evaluation:

```text
WIDEN if M2(widen) < both base and shrink
SHRINK if M2(shrink) < both base and widen
HOLD if neither perturbation improves base by >1%
```

Preregister:

```text
relative_tie_tolerance = 0.01
```

Direction accuracy:

\[
\boxed{
Acc_{dir}
=
P(\text{predicted direction}=\text{evaluation-best direction})
}
\]

---

# 15. Primary Benchmark

Reuse the 8 frozen M1-D configs:

```text
c000 c001 c004 c006 c007 c010 c017 c020
```

Seeds:

```text
2026 2027 2028 2029 2030 2031 2032 2033
```

64 paired trials.

No config removal or replacement.

---

# 16. Proposal State at Which Gradient Is Evaluated

Primary M3-v0 derivative point:

> frozen M1-D variance-policy proposal immediately after the variance-critical component has been added and the frozen M1-v0 mixture weights have been established, before any M3 covariance change.

Record:

```text
selected_mode
component_index
component_mean
component_weight
base_covariance
full mixture state
```

Do not differentiate one proposal and evaluate a different one.

---

# 17. Explicit M2 Diagnostic

For each M3 trial also compute the failed M2 descriptive HDR covariance \(C_{\eta,k}^{V}\), but never use it for control.

Report cases where:

```text
M2 descriptive covariance suggests narrowing
M3 second-moment gradient predicts widening
```

This directly tests the M2 lesson:

\[
\text{descriptive spread}\neq\text{descent direction}.
\]

---

# 18. Theory Audit

Before scientific runs create:

```text
docs/phase_m3/M3_Covariance_Gradient_Derivation.md
```

Include:

1. Gaussian log-density covariance derivative;
2. mixture derivative;
3. differentiation-under-integral assumptions;
4. responsibility identity;
5. matrix gradient;
6. isotropic derivative;
7. stationary condition;
8. theorem scope;
9. nonclaims.

---

# 19. Finite-Difference Validation

For deterministic toy / high-accuracy sanity cases:

\[
g_{FD}
=
\frac{
M_2(\theta+h)-M_2(\theta-h)
}{
2h
}.
\]

Main sanity:

```text
h = 1e-3
```

Require:

```text
gradient sign agreement = 100%
relative gradient error <= 5e-3
```

If this fails, STOP.

---

# 20. Sanity Cases

## S1 — Single Gaussian half-space
Validate isotropic derivative sign and finite differences.

## S2 — Two-component Gaussian mixture
Validate responsibility weighting.

## S3 — M2-style narrow HDR case
If supported, demonstrate:
```text
HDR covariance narrow
gradient says WIDEN
widen lowers M2
```

S3 is explanatory, not a hard gate.

---

# 21. Comparators

Main scalar comparators:

| Method | Rule |
|---|---|
| HOLD | no covariance change |
| SHRINK | fixed \(-0.20\) |
| WIDEN | fixed \(+0.20\) |
| GRADIENT | CI-sign rule; otherwise HOLD |

All share selected mode, mean, weights in Layer A, pilot, and matched evaluation randomness.

Always-Widen is mandatory because M2 may imply a simple widening heuristic.

If Gradient ≈ Always-Widen, the gradient may add little adaptive value on this benchmark.

---

# 22. Simulator-Call Accounting

Gradient estimation reuses the pilot:

```text
pilot_n = 20,000
alpha_p = 0.5
```

Each proposal evaluation uses:

```text
final_eval_n = 100,000
```

Scientific counterfactual calls for BASE/WIDEN/SHRINK must be reported separately.

For deployable VRF, count only the chosen GRADIENT action path, not the opposite-direction scientific diagnostic.

Report both:

```text
scientific_audit_calls
deployable_method_calls
```

---

# 23. Primary Metrics

- gradient sign and CI;
- ESS_grad;
- WIDEN / SHRINK / HOLD frequency;
- directional accuracy;
- predicted-step success rate;
- \(M_2(pred)/M_2(base)\);
- \(M_2(pred)/M_2(opposite)\);
- selected-mode leakage;
- off-target leakage;
- proposal-level VRF;
- deployable budget-adjusted VRF.

---

# 24. Core Gates

## M3-0 Validity
Require M2 frozen, parent tags unchanged, task committed before runs, derivation present, no oracle leakage, fixed-weight Layer A, full pytest pass.

## M3-1 Numerical Gradient Validity
Toy/FD:
```text
100% sign agreement
relative error <= 5e-3
```

## M3-2 Direction Identifiability
At least:
```text
>= 50% of 64 trials
```
yield confident non-HOLD direction.

## M3-3 Direction Accuracy
Among active trials:
\[
Acc_{dir}\ge0.75.
\]
Also require at least +25 percentage points over the preregistered nonadaptive direction comparator.

## M3-4 Predicted Step M2 Gain
Among active trials:
```text
>=75%
```
must satisfy:
\[
M_2(pred)<M_2(base).
\]
And:
\[
\boxed{
\operatorname{median}
\frac{M_2(pred)}{M_2(base)}
\le0.90
}
\]

## M3-5 Counterfactual Ordering
\[
\boxed{
\operatorname{median}
\frac{M_2(pred)}{M_2(opposite)}
\le0.85
}
\]

## M3-6 No Catastrophic Leakage Redistribution
At least 7/8 configs:
\[
\operatorname{median}_{seed}
\max_{j\neq k}
\frac{L_j(pred)}{L_j(base)}
\le2.
\]

---

# 25. Strong Gate

Strong M3 result:

\[
\boxed{
\operatorname{median}
VRF_{budget}^{gradient}>1
}
\]

under deployable call accounting.

This is not required for core directional validity.

---

# 26. Interpretation Matrix

| FD valid | Direction accurate | Pred step lowers M2 | Beats opposite | Interpretation |
|---|---|---|---|---|
| No | — | — | — | theory/implementation invalid |
| Yes | No | No | No | finite-sample gradient not predictive |
| Yes | Yes | No | No | sign informative but action ineffective |
| Yes | Yes | Yes | weak | local descent works, contrast noisy |
| Yes | Yes | Yes | strong | core M3 success |
| Yes | Yes | Yes | strong + VRF>1 | strong M3 success |

---

# 27. Negative Result Policy

Preserve all outcomes:

- mostly HOLD → finite-sample gradient too uncertain;
- Gradient ≈ Always-Widen → gradient adds limited value beyond coarse widening;
- wrong sign → estimator/theory assumptions inadequate;
- right sign but harmful step → first-order direction needs trust region / curvature;
- scalar success does not imply full-matrix success.

Do not retune step size post hoc.

---

# 28. Full Matrix Control Deferred

Do not implement full matrix M3-v1 until scalar M3-v0 passes all core gates.

A later candidate may use:

\[
\Sigma_{t+1}
=
\mathcal R_\gamma(\Sigma_t,T_k)
\]

with an SPD trust region.

That is outside this task.

---

# 29. Required Tests

At minimum:

```text
test_m3_gaussian_covariance_loggrad
test_m3_mixture_responsibility
test_m3_matrix_gradient_toy
test_m3_isotropic_gradient_toy
test_m3_gradient_finite_difference
test_m3_stratified_gradient_estimator
test_m3_gradient_bootstrap
test_m3_gradient_ess
test_m3_direction_rule_widen
test_m3_direction_rule_shrink
test_m3_direction_rule_hold
test_m3_fixed_weight_layer
test_m3_counterfactual_crn
test_m3_no_final_eval_leakage
test_m3_result_schema
```

Run full:

```bash
pytest -q
```

before final gate audit.

---

# 30. Repository Layout

```text
docs/phase_m3/
├── M3_Second_Moment_Gradient_Covariance_Control_Task.md
├── M3_Covariance_Gradient_Derivation.md
├── M3_Methodology.md
├── M3_Gradient_Validity_Audit.md
└── M3_Final_Report.md

configs/phase_m3/
├── m3_scalar_gradient_v0.json
└── m3_step_sensitivity.json

src/hyptraj/m3/
├── covariance_gradient.py
├── gradient_estimator.py
├── direction_policy.py
└── metrics.py

scripts/
├── run_m3_theory_checks.py
├── run_m3_sanity.py
├── run_m3_scalar_experiments.py
├── run_m3_gate_audit.py
└── run_m3_figures.py

tests/
└── test_m3_*.py

results/phase_m3/
├── theory_checks/
├── sanity/
├── scalar_layer_a/
├── scalar_layer_b/
├── sensitivity/
└── summary/

figures/phase_m3/
└── figure_M3_*.png
```

---

# 31. Machine-Readable Record

Each trial should record at least:

```json
{
  "schema_version": "raretopo-m3-v0",
  "h3_tag": "RareTopo-H3-v1.0",
  "m1_tag": "RareTopo-M1-v0",
  "m1d_tag": "RareTopo-M1-D-v1.0",
  "m2_tag": "RareTopo-M2-v0",
  "config_id": "c000",
  "seed": 2026,
  "selected_mode": "Sx",
  "component_index": 1,
  "layer": "fixed_weights",
  "gradient": {
    "M2_hat": 0.0,
    "responsibility_mass": 0.0,
    "D_hat": 0.0,
    "g_hat": 0.0,
    "g_ci_low": 0.0,
    "g_ci_high": 0.0,
    "ESS_grad": 0.0,
    "decision": "WIDEN|SHRINK|HOLD_UNCERTAIN|HOLD_LOW_ESS"
  },
  "counterfactual": {
    "delta_theta": 0.2,
    "M2_base": 0.0,
    "M2_widen": 0.0,
    "M2_shrink": 0.0,
    "M2_pred": 0.0,
    "M2_opposite": 0.0,
    "evaluation_best_direction": "WIDEN|SHRINK|HOLD"
  },
  "m2_diagnostic": {
    "hdr_covariance": [],
    "hdr_trace": 0.0
  },
  "evaluation": {
    "P_hat": 0.0,
    "VRF_proposal": 0.0,
    "VRF_budget": 0.0,
    "mode_L": {}
  },
  "validity": {}
}
```

---

# 32. Required Figures

1. M3-1 — M2 descriptive covariance vs M3 gradient direction  
2. M3-2 — analytic gradient vs finite difference  
3. M3-3 — gradient CI and WIDEN/HOLD/SHRINK distribution  
4. M3-4 — paired SHRINK / BASE / WIDEN / GRADIENT \(M_2\)  
5. M3-5 — \(M_2(pred)/M_2(opposite)\)  
6. M3-6 — direction accuracy  
7. M3-7 — ESS_grad vs directional reliability  
8. M3-8 — deployable budget VRF with MC boundary = 1  

---

# 33. Run Order

```text
Step 0  Freeze M2 -> RareTopo-M2-v0
   ↓
M3-0   Commit M3 preregistration
   ↓
M3-1   Covariance-gradient derivation
   ↓
M3-2   Finite-difference + toy validation
   ↓
M3-3   Stratified gradient estimator + bootstrap
   ↓
M3-4   Scalar Layer A counterfactual benchmark
   ↓
M3-5   Gate directional accuracy / M2 reduction
   ↓
M3-6   Always-Widen / Always-Shrink audit
   ↓
M3-7   Layer B frozen reweight
   ↓
M3-8   Step sensitivity
   ↓
M3-9   Final report / freeze decision
```

---

# 34. Stop / Go Rules

- If M2 is not frozen: STOP.
- If gradient theorem or FD validation fails: STOP.
- If <50% trials yield identifiable direction: STOP scientific escalation.
- If directional accuracy <75%: do not enter full-matrix control.
- If predicted step does not lower \(M_2\): do not claim gradient control success.
- Full-matrix M3-v1 is allowed only after M3-0 through M3-6 all PASS.

---

# 35. Strongest Allowed Claim

If core gates pass:

> **On the frozen multi-missing-mode RareTopo benchmark, a finite-sample estimate of the second-moment covariance derivative predicts a local Gaussian scale direction that reduces estimator second moment more reliably than the opposite covariance perturbation under matched proposal state and evaluation budgets.**

If Gradient ≈ Always-Widen:

> **The second-moment derivative correctly predicts widening on this benchmark, but provides limited measurable value beyond a fixed widening rule.**

If Strong Gate passes, only then add a cost-efficiency claim versus crude MC.

---

# 36. Preregistration Lock

After task commit, lock:

```text
parent tags
M2 freeze requirement
8 frozen configs
seed set
pilot_n = 20,000
alpha = 0.5
final_eval_n = 100,000
fixed-weight Layer A
gradient formula
responsibility definition
ESS_grad threshold = 20
95% bootstrap sign rule
delta_theta_main = 0.20
sensitivity = [0.10, 0.20, 0.40]
tie tolerance = 0.01
Always-Widen comparator
Always-Shrink comparator
Gate M3-0..M3-6
Strong Gate
```

Any change requires:

```text
M3_PREREG_AMENDMENT_<date>.md
```

with old/new/reason/outcome-inspection/untouched-rerun fields.

---

# 37. Completion Checklist

## M2 freeze
- [ ] M2 Final Report complete
- [ ] M2 full pytest pass
- [ ] M2 negative claim explicit
- [ ] `RareTopo-M2-v0` annotated tag created
- [ ] tag pushed
- [ ] M2 freeze summary recorded

## M3 theory
- [ ] matrix gradient derivation
- [ ] isotropic derivation
- [ ] assumptions audit
- [ ] stationarity audit
- [ ] no theorem overclaim

## M3 implementation
- [ ] responsibility estimator
- [ ] stratified gradient estimator
- [ ] ESS_grad
- [ ] stratified bootstrap
- [ ] WIDEN/SHRINK/HOLD rule
- [ ] fixed-weight layer
- [ ] counterfactual evaluation

## Validation
- [ ] S1
- [ ] S2
- [ ] finite-difference checks
- [ ] full pytest

## Benchmark
- [ ] 8 configs × 8 seeds
- [ ] HOLD / WIDEN / SHRINK / GRADIENT
- [ ] Layer A complete
- [ ] Layer B only after Layer A audit
- [ ] sensitivity retained

## Gates
- [ ] M3-0
- [ ] M3-1
- [ ] M3-2
- [ ] M3-3
- [ ] M3-4
- [ ] M3-5
- [ ] M3-6
- [ ] Strong separately reported

---

# 38. Immediate Instruction to Execution Agent

Do not begin M3 code before M2 freeze.

Execute:

```text
1. Freeze M2 as RareTopo-M2-v0.
2. Record exact M2 final HEAD and full pytest result.
3. Confirm H3 / M1-v0 / M1-D parent tags are unchanged.
4. Commit this M3 task before generating any M3 scientific result.
5. Perform only M3-1 theory derivation + finite-difference/toy validation first.
```

Do not launch the 64-trial benchmark until M3-1/M3-2 pass.

---

# 39. One-Line State

```text
H3 = frozen
M1-v0 = frozen
M1-D = frozen
M2 = executed negative result -> FREEZE FIRST
M3 = preregistered
M3 scientific runs = NOT STARTED
next action = freeze M2, then validate the second-moment covariance gradient
```

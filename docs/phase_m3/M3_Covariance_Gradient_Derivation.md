# M3 Covariance Gradient Derivation — Second-Moment Gradient Covariance Control

> **Schema:** `raretopo-m3-v0` ｜ **Date:** 2026-08-27 ｜ **Status:** candidate theorem + audit (task Sec. 18)
> **Parent frozen science:** `RareTopo-H3-v1.0` ／ frozen methods: `RareTopo-M1-v0`, `RareTopo-M1-D-v1.0`, `RareTopo-M2-v0`
> **Task file:** `M3_Second_Moment_Gradient_Covariance_Control_Task.md` (Sec. 4–7, 18)
> **Validation:** `results/phase_m3/theory_checks/` (`run_m3_theory_checks.py`) must show 100% finite-difference sign agreement and relative error <= 5e-3 BEFORE any benchmark run (Stop/Go, task Sec. 19/34).

---

## Scope of this document

Required contents per task Sec. 18:

1. Gaussian log-density covariance derivative;
2. mixture derivative;
3. differentiation-under-integral assumptions;
4. responsibility identity;
5. matrix gradient;
6. isotropic derivative;
7. stationary condition;
8. theorem scope;
9. nonclaims.

Everything here is POPULATION-level analysis of differentiable densities; no
finite-sample estimator appears before Sec. 9-note, and estimator error bounds
are out of scope (they are what bootstrap CI + gates measure empirically).

Notation: dimension ``dim = d``; ``A`` is the frozen event region (union of
missing-mode supports) with positive measure; all densities are measurable,
strictly positive on the interior of ``A`` where required, and ``p`` is square
integrable against ``1/q`` on ``A`` (assumption A3 below makes this precise).

---

## 0. Setting

```text
q(x)      = sum_j pi_j q_j(x),        pi_j > 0, sum_j pi_j = 1
q_j(x)    = N(x; m_j, Sigma_j),       each Sigma_j in SPD(d)  (symmetric pos.def.)
Selected component k is the ONLY object differentiated; the map
Sigma_k -> M2(q) keeps m_j, pi, Sigma_{j!=k} FIXED.
M2(q)     = integral_A p(x)^2 / q(x) dx          (IS second moment)
nu_V^q(dx)= 1_A(x) p(x)^2/q(x)/M2(q) dx           (normalized variance measure)
delta(x)  = X - m_k                                (implementation name delta)
```

The task preregisters the ISOTROPIC sub-family ``Sigma_k = s_k^2 I`` with
``theta_k = log s_k^2`` for control; the general statement is proved first.

---

## 1. Gaussian log-density covariance derivative

For one component,

```text
log q_k(x) = -(d/2) log(2*pi) - (1/2) log|Sigma| - (1/2) tr(Sigma^-1 Delta(x)),
Delta(x) = (x - m)(x - m)'       (= delta delta')
```

Entrywise derivative with respect to ``Sigma_ab`` (interior of SPD):

```text
d/dSigma_ab log|Sigma|            = (Sigma^-1)_ba                       [= Sigma^-1 entries, sym]
d/dSigma_ab tr(Sigma^-1 Delta)    = -(Sigma^-1 Delta Sigma^-1)_ba
=>  d log q_k / dSigma
    = -(1/2) Sigma^-1 + (1/2) Sigma^-1 Delta Sigma^-1
    = -(1/2) ( Sigma^-1 - Sigma^-1 Delta Sigma^-1 )                    (1)
```

i.e. **the opposite sign** of the commonly mis-stated ``+(1/2)(...)`` form; the
sign flip comes from the negative log-determinant term. This is the constant
most likely to be silently wrong in code, which is why FD validation (Sec. 12)
is a hard Stop/Go gate.

A useful invariant check: contracting (1) with ``dSigma = Sigma``
(direction ``theta = log s^2``, see Sec. 6) reproduces the classic quadratic-form
score ``-d/2 + tr(Sigma^-1 Delta)/2``.

## 2. Mixture derivative

Only the k-th term depends on ``Sigma_k``:

```text
dq/dSigma_k = pi_k dq_k/dSigma_k = pi_k q_k * (d log q_k/dSigma_k)
```

Substituting into the parameter-dependent integral,

```text
dM2/dSigma_k = integral_A p^2 * d(q^-1)/dSigma_k
             = - integral_A (p^2 / q^2) dq/dSigma_k
             = - integral_A (p^2/q) * r_k(x) * (d log q_k/dSigma_k)  dx      (2)
```

where the last line uses the **responsibility identity** (Sec. 4):
``pi_k q_k / q = r_k(x)``.

## 3. Differentiation-under-integral assumptions (audit)

(A1) *SPD interior*: ``Sigma_k`` ranges over the open SPD cone; log-det and the
inverse are C-infinity there, so (1) is valid.

(A2) *Zero-set safety*: all identities below are taken over ``A`` intersect
``{q > 0}``. Assumption: ``(1-A) subset {q > 0}`` up to Lebesgue-null sets, and
``q`` is locally bounded away from 0 wherever needed. Violation surfaces as
non-finite weights in the estimator and fires HOLD_INVALID (never silently
repaired).

(A3) *Integrability*: ``M2(q) < infinity``. Under (A2)+(A3) the integrand
``g(Sigma, x) = 1_A p^2/q_Sigma`` is dominated on any compact SPD-neighbourhood
``U`` of ``Sigma_k`` by an integrable bound: on ``U``, ``q_Sigma >= c_U > 0``
pointwise-minimum argument over the compact set (continuous q, closed level
set), giving ``|p^2/q| <= p^2/c_U`` integrable by (A3); derivatives behave the
same way after applying (1), because ``|d log q_k/dSigma|`` grows at most
polynomially in ``||x||`` while ``p^2`` carries the decay. Differentiation under
the integral sign (dominated convergence on the difference quotient) is thus
licensed on ``U``.

(A4) *Fixed-parameter discipline*: the derivative is taken holding
``m_j, pi, Sigma_{j != k}`` fixed. Any joint move (means, weights, adding or
deleting components) voids every formula in this document. This is exactly the
Layer A lock (prereg config `gradient_point_locked.layer_A_locks`).

(A5) *Event indicator*: ``A`` is fixed and independent of ``Sigma_k``; its
boundary is carried through unchanged because integration-by-parts/chain-rule
steps never differentiate ``1_A``.

## 4. Responsibility identity

```text
r_k(x) = pi_k q_k(x) / q(x),    0 <= r_k <= 1,  sum_j r_j(x) = 1       (3)
```

(Positivity/bounds are immediate; the partition of unity follows from summing
over j.) Two structural consequences used repeatedly:

```text
sum_k r_k(x) = 1                         => gradients of DIFFERENT components interact
p^2/q^2 * pi_k q_k = p^2/q * r_k         => responsibility enters line (2)
```

Crucial contrast with M2 (frozen failure, recorded verbatim in
`RareTopo-M2-v0`): M2's descriptive region object was top-eta HDR conditioned,
mode-centered, NOT responsibility-weighted, and never differentiated anything.
Here every factor comes from differentiating ``M2`` itself.

## 5. Matrix gradient (candidate theorem)

Inserting (1) into (2):

```text
grad_{Sigma_k} M2
  = - integral_A (p^2/q) r_k * [-(1/2)(Sigma^-1 - Sigma^-1 Delta Sigma^-1)]
  = +(1/2) E_nuV[ r_k ( Sigma^-1 - Sigma^-1 Delta Sigma^-1 ) ] '
```

with expectation factors splitting because ``Sigma^-1`` is constant in x:

```text
boxed:
grad_{Sigma_k} M2
  = (M2/2) * Sigma_k^-1 [ E_nuV[r_k] Sigma_k - E_nuV[ r_k (X-m_k)(X-m_k)' ] ] Sigma_k^-1   (4)
```

Equivalently ``= (M2/2) E_nuV[ r_k (Sigma^-1 - Sigma^-1 delta delta' Sigma^-1) ]``.
PROOF-CHECK of the factoring step: left-multiplying constant matrices past the
x-expectation is linear algebra (expectation is elementwise); symmetric entrywise
form is recovered by taking ``ab`` entries of (4). QED-as-audit; numerical proof
obligation discharged by the finite-difference gate.

Sign sanity: if the responsibility-scaled scatter ``E[r_k delta delta']`` exceeds
``E[r_k] Sigma_k`` "on average" (component too NARROW for the variance mass it
carries), the bracket is negative-definite-leaning and the gradient pulls
toward widening -- matching intuition and the scalar form next.

## 6. Isotropic derivative

Set ``Sigma_k = s_k^2 I``, ``theta = log s_k^2`` (so ``dSigma/dtheta = Sigma``).
Taking the Frobenius inner product of (4) with ``Sigma``:

```text
g_k = dM2/dtheta = tr(grad' Sigma)
    = (M2/2) tr( Sigma^-1(E[r]Sigma - E[r Delta]) )
    = (M2/2) ( dim * E[r] - tr(Sigma^-1 E[r Delta]) )
    = (M2/2) E[r] ( dim - D_k / s_k^2 ),                                 (5)

D_k = E_nuV[ r_k ||X - m_k||^2 ] / E_nuV[ r_k ]
```

(the last equality uses ``tr(Sigma^-1 E[r Delta]) = E[r ||delta||^2]/s_k^2`` on
the isotropic slice and factorizes the constant ``E[r]``). Implementation names
locked by the task: ``dim``, ``delta = X - m_k``.

Interpretation (the central M3-v0 hypothesis):

```text
g_k < 0 -> WIDEN   (responsibility-scaled squared radius exceeds dim*s_k^2)
g_k > 0 -> SHRINK
g_k ~ 0 -> HOLD
```

## 7. Stationary condition (responsibility-weighted target)

With ``mu_r = E[r_k] > 0`` define

```text
T_k = E_nuV[ r_k (X-m_k)(X-m_k)' ] / E_nuV[ r_k ]                            (6)
```

Then the matrix gradient (4) vanishes iff ``T_k = Sigma_k`` (left/right multiply
by ``Sigma``: bracket ``= mu_r Sigma - mu_r T_k``). On the isotropic slice the
stationary point is ``s_k^2 = tr(T_k)/dim``.

AUDIT of status: ``grad = 0`` is a FIRST-ORDER NECESSARY condition for a local
extremum of ``M2`` over the SPD interior at fixed (m, pi); it is NOT a global
minimum certificate, and nothing here claims that iterating any relaxation
toward ``T_k`` converges to a minimizer (full-matrix iteration is EXPLICITLY OUT
of scope for M3-v0, task Sec. 28). Comparison table versus failed M2 is in task
Sec. 6 and is reproduced in the Final Report only as narrative contrast.

## 8. Finite-sample readout note (bridge to Sec. 8 of the task)

For pilot samples ``x_i ~ r_i`` (recorded source density), the frozen
variance-mass importance values

```text
a_i = 1_A(x_i) p(x_i)^2 / (q(x_i) r_i(x_i))
```

are reused VERBATIM from the M1/H3 pipeline; with normalized ``ab_i = a_i /
sum_j a_j`` the plugin estimates are

```text
M2_hat = mean(a);  mu_r_hat = sum ab_i rhat_ki;
D_hat  = sum ab_i rhat_ki ||x_i - m_k||^2 / mu_r_hat;
g_hat  = (M2_hat/2) mu_r_hat (dim - D_hat/s_k^2);
c_i    = ab_i rhat_ki / sum_j ab_j rhat_kj,   ESS_grad = 1 / sum c_i^2.
```

Uncertainty: frozen fixed-stratified bootstrap (resample WITHIN each source
stratum, sizes preserved), 95% percentile CI on ``g_hat``; decision precedence
HOLD_INVALID > HOLD_LOW_ESS (ESS_grad < 20) > CI-sign rule.

## 9. Validity conditions coded as gates (estimator side)

An estimate is USED only when all pass, else HOLD_INVALID / HOLD_LOW_ESS:

```text
V1 finiteness:      M2_hat, mu_r_hat, D_hat, g_hat all finite
V2 mass:            mu_r_hat > 0 (denominator of T_k/D_k strictly positive)
V3 support support: sum a_i > 0 on A (variance mass present)
V4 legality:        s_new^2 = s_old^2 exp(+-delta_theta) passes FROZEN checker
                    min-eig( Sigma_new ) >= LEGALITY_MIN_EIG = 0.5 (metadata-
                    certified unit base makes e^{+-0.40} >= 0.670 legal always)
V5 gradient ESS:    ESS_grad >= 20
V6 CRN pairing:     pred/opposite arms evaluated on matched generator streams
```

## 10. Theorem scope (what is claimed)

- Identity (4)/(5) holds for the frozen mixture family at ANY interior SPD
  ``Sigma_k`` with means, weights, other covariances fixed, under A1–A5.
- The scalar direction rule ``sign(g_k)`` WIDEN/SHRINK/HOLD is the FIRST-ORDER
  action implied by the derivative at the CURRENT scale ``s_k^2``.
- Finite-sample deployment validity is empirical and gated (Sec. 11 gates
  M3-1..M3-6); the theorem itself makes NO finite-sample claim.

## 11. Nonclaims

- NO claim of global covariance optimality of ``T_k`` or of any iterate.
- NO claim about simultaneous moves of means, weights, component count.
- NO claim that a WIDEN/SHRINK step reduces ``M2`` for LARGE steps (first-order
  locality; trust-region/curvature is future work and out of scope).
- NO claim of transfer beyond the frozen M1-D benchmark without re-validation.
- NO claim that scalar success implies full-matrix success (task Sec. 28 gating).
- The theorem does not repair or reinterpret M2; the M2 negative result stays
  verbatim frozen (`RareTopo-M2-v0`).

## 12. Numerical proof obligation (hard gate)

`scripts/run_m3_theory_checks.py` validates (4)-(5) against central finite
differences on deterministic quadrature-computed toy cases (half-space events,
one/two-component mixtures, narrow-HDR explanatory case):

```text
h = 1e-3 ;  requirement: 100% sign agreement AND max relative error <= 5e-3
failure => STOP (no benchmark run may start)
```

Output lands in `results/phase_m3/theory_checks/theory_checks_v1.json`.

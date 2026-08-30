# M4-PF Structured Objective-Gradient Proposal — Task Lock

> Parent freeze: `RareTopo-M3-CA-v0`  
> Starting commit: `6b1ce6e1e99acc176df6b787e9cd5566fccc29bf`  
> PF0 status at lock: not started  
> PF0 simulator calls authorized: **zero**

## 1. Motivation and question

M3-CA reproduced 97.1% capture of scalar-family Oracle adaptive headroom but
found `VRF_budget_free_oracle = 0.01005324 << 1`. M4-PF tests whether the
isotropic scalar covariance family is too restrictive and whether the same
objective-gradient principle exposes useful low-rank directional structure.

The governing distinction is:

```text
correct control inside a restricted family
is not sufficient proposal-family expressiveness
```

M4-PF does not revive descriptive covariance matching from M2.

## 2. PF0 mathematical target

For a symmetric log-covariance direction `B`, the locked target is

\[
\Sigma_k(\epsilon)=\Sigma_k^{1/2}\exp(\epsilon B)\Sigma_k^{1/2},
\]

\[
g_{k,B}=\frac{M_2}{2}E_{\nu_V}
\left[r_k\{\operatorname{tr}(B)-z_k^TBz_k\}\right],
\]

with matrix representation

\[
G_k=\frac{M_2}{2}E_{\nu_V}\left[r_k(I-z_kz_k^T)\right],
\qquad g_{k,B}=\langle G_k,B\rangle_F.
\]

Required special cases are

\[
g_{scalar}=\operatorname{tr}(G_k),
\qquad g_{k,v}=v^TG_kv\quad(B=vv^T).
\]

No manual scale factor may be introduced to force scalar recovery.

## 3. PF0 scientific firewall

The invariant is

```text
extra_simulator_calls = 0
```

PF0 may read existing artifacts, derive and implement pure matrix arithmetic,
run deterministic Gaussian fixtures, decompose matrices, hash sources, make
tables/plots and run tests. It may not generate pilots, seeds, trajectories,
benchmark states or final evaluations, and may not tune controllers, rho,
GA gates, pilot size, means, mixture allocation, covariance rank or M3-Q.

## 4. Source and identifiability gate

Before a real-state matrix reconstruction, PF0 must prove that frozen records
contain or can exactly reconstruct all of:

- per-sample locations/displacements or whitened coordinates;
- per-sample variance-mass weights or their exact inputs;
- component responsibilities;
- component means/covariances;
- event indicators and source strata where required by the M3 estimator.

Missing sample-level inputs produce

```text
NOT IDENTIFIABLE FROM EXISTING ARTIFACTS
```

and never authorize a PF0 simulation. Theory, API, deterministic algebra tests
and the identifiability audit still complete.

## 5. PF0 diagnostics and gate

If real-state reconstruction is identifiable, compute per state/component:
eigenvalues/eigenvectors, trace, spectral and Frobenius norms, positive and
negative spectral mass, anisotropy, sign-cancellation, and top-1/top-2 absolute
spectral fractions. Associations with M3-CA FreeOracle VRF are descriptive
only.

PF0 ends in exactly one state:

- `GO`: theory passes and frozen data show meaningful low-rank directional
  structure;
- `GO-WITHOUT-FROZEN-RECONSTRUCTION`: theory passes but frozen sample records
  are insufficient; PF1 may preregister a new data pipeline;
- `NO-GO`: trace captures the useful structure or low-rank directional mass is
  negligible; covariance-rank experiments are not run.

## 6. Conditional PF1 scope

PF1 is allowed only after PF0 is committed and frozen and after a separate PF1
protocol/config/seed/state lock is committed. PF1 compares only:

- S0: frozen scalar isotropic family;
- S1: rank-1 objective-gradient log-covariance update;
- S2: rank-2 objective-gradient log-covariance update.

The update is

\[
\Sigma'=\Sigma^{1/2}\exp(-\eta\widetilde G_r)\Sigma^{1/2}.
\]

Rank is selected by descending absolute eigenvalue. Step normalization, eta,
eigenvalue clipping, log-step clipping, condition-number ceiling, states,
seeds, budgets, metrics and gates must be frozen before simulator use. PF1 may
not tune a controller, mean, mixture allocation, pilot budget, rank or eta from
evaluation outcomes and may not escalate directly to a free full matrix.

## 7. PF1 endpoint and verdicts

The primary endpoint is proposal-family feasibility under free action/config
selection:

\[
VRF_{budget}^{FreeOracle,family}.
\]

Only the selected final evaluation enters deployable cost; gradient/reference
construction, Oracle search, unselected families and diagnostics are
audit-only.

The locked verdicts are:

- PF1-A: best S1/S2 median FreeOracle VRF > 1;
- PF1-B: 0.1 < median <= 1;
- PF1-C: median <= 0.1;
- PF1-D: scalar baseline, protocol, numerical safety or accounting is invalid.

PF1-C prohibits mechanical rank-4/rank-8/full-matrix escalation and routes to
a separately preregistered joint mean-plus-covariance study.

## 8. Global claim boundary

Neither PF0 nor PF1 may claim universal optimality, deployable controller
efficiency, real-system speedup, causal anisotropy effects, or that M3 was
incorrect. M3-Q remains blocked throughout M4-PF.

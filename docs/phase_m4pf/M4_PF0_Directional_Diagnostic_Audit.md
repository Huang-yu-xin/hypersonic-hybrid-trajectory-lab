# M4-PF0 Directional Objective-Gradient Audit

## 1. Executive verdict

**PF0 verdict: `GO-WITHOUT-FROZEN-RECONSTRUCTION`.**

The structured log-covariance objective gradient is derived, implemented and
validated without a trajectory-simulator call. Its trace exactly recovers the
frozen M3 scalar gradient convention, rank-1 directions reduce to `v^T G v`,
and the matrix-exponential update preserves positive definiteness. However,
the frozen M3--M3-CA artifacts do not retain the per-sample numeric arrays
needed to reconstruct real-state matrix gradients. No empirical claim about
directional structure is therefore made in PF0.

This verdict permits a separately preregistered PF1 data pipeline. It does not
itself establish that rank-1 or rank-2 proposals improve efficiency.

## 2. Freeze and opening regression

- Parent tag: `RareTopo-M3-CA-v0`.
- Parent commit: `6b1ce6e1e99acc176df6b787e9cd5566fccc29bf`.
- Working branch: `feature/phase-m4pf-structured-objective-gradient`.
- Opening full regression: 1,234 tests passed with three pre-existing pytest
  fixture deprecation warnings.
- Closing full regression: 1,247 tests passed with the same three pre-existing
  warnings (`331.12 s`).
- PF0 simulator-call invariant: `extra_simulator_calls = 0`.
- Frozen-input manifest: 11 read-only artifacts; all post-analysis SHA-256
  checks match their pre-analysis values.

The machine-readable source manifest is
`results/phase_m4pf0/summary/m4pf0_source_manifest.json`. Generated result
artifacts remain under the repository's ignored `results/` tree, consistent
with prior phases.

## 3. Identifiability audit

An exact real-state reconstruction requires numeric per-sample records for:

1. sample locations/displacements or whitened coordinates;
2. variance-mass weights, or every exact input needed to recompute them;
3. component responsibilities;
4. component means and covariances; and
5. event indicators and source strata required by the estimator.

The frozen JSON files contain aggregate fields such as `g_hat`, `ESS_grad`,
`M2_hat` and `responsibility_mass`, but contain no qualifying numeric sample
arrays. Strings such as `a_i` and `responsibility` occur only in metadata or
formula descriptions and are not observations. Aggregate scalar summaries do
not identify the scatter term

\[
E_{\nu_V}[r_k z_k z_k^T].
\]

The formal result is therefore:

```text
NOT IDENTIFIABLE FROM EXISTING ARTIFACTS
```

In accordance with the task lock, this result did not trigger data generation,
pilot replay or any other simulator use. Real-state eigenvalue, eigenvector,
anisotropy and cancellation plots are intentionally absent.

## 4. Theory and implementation checks

For a symmetric log-covariance direction `B`, the implemented matrix gradient
is

\[
G_k=\frac{M_2}{2}E_{\nu_V}[r_k(I-z_kz_k^T)],
\qquad g_{k,B}=\langle G_k,B\rangle_F.
\]

The following checks passed:

- symmetric matrix construction and input-shape validation;
- exact scalar recovery `g_scalar = trace(G)` with no fitted scale factor;
- exact directional recovery `g_v = v^T G v` for `B=vv^T`;
- eigenpair ordering by descending absolute eigenvalue for rank truncation;
- well-defined top-1/top-2 spectral fractions, anisotropy and cancellation
  diagnostics, including the zero-matrix edge case;
- SPD preservation under
  `Sigma^(1/2) exp(-eta G_rank) Sigma^(1/2)`;
- rejection of unsafe updates exceeding a locked condition-number ceiling;
- source-manifest re-hashing and sample-level identifiability classification.

Thirteen focused PF0 tests passed; the closing full suite passed all 1,247
tests.

## 5. Deterministic finite-difference validation

The validation fixture uses a closed-form Gaussian second moment on all of
`R^2`, not random samples or trajectories. Central differences were evaluated
for identity, rank-1 and mixed symmetric directions at step sizes `1e-2`,
`1e-3` and `1e-4`.

- Maximum relative error at `epsilon = 1e-4`: `1.5072265e-7`.
- Fixture matrix symmetry error: `0`.
- Scalar trace: `-0.17452360761434976`.
- Identity directional derivative: `-0.17452360761434976`.

The error decreases at the expected second-order central-difference rate. The
two theory-only figures are:

- `figures/phase_m4pf0/PF0-T1_directional_fd_convergence.png`;
- `figures/phase_m4pf0/PF0-T2_scalar_trace_recovery.png`.

These figures validate the algebra and scalar embedding only; they are not
evidence about any M3-CA benchmark state.

## 6. State-table handling

The 24 frozen M3-CA states were carried into
`results/phase_m4pf0/summary/m4pf0_state_gradient_table.csv` for provenance.
Every row is explicitly marked non-identifiable for matrix reconstruction.
No eigenvalue, direction or association with FreeOracle VRF is imputed.

## 7. Claim boundary and next stage

PF0 establishes mathematical and software readiness for a structured
objective-gradient experiment. It does not establish useful anisotropy,
causality, deployable efficiency, universal optimality or a defect in M3.
M3-Q remains blocked.

Before any PF1 simulator call, PF1 must separately freeze and commit its state
set, disjoint seeds, budgets, sample-level data schema, S0/S1/S2 construction,
rank rule, normalization, step size, clipping, condition-number ceiling,
FreeOracle evaluation, cost accounting and A/B/C/D verdict gates. No PF1
choice may be tuned from final evaluation outcomes.

# M4-PF2-0 Mean-Gradient and Anchor Audit

## Executive verdict

PF2-0 is complete with:

```text
NOT IDENTIFIABLE FROM EXISTING ARTIFACTS
FRESH GRADIENT CONSTRUCTION REQUIRED
```

The mean-gradient theory and deterministic implementation pass, but the PF1
records contain only aggregate gradient matrices and diagnostics, not aligned
numeric sample arrays. In addition, the PF1 gradients were constructed at the
base state proposal while the preferred PF2 anchor is the per-state S0
FreeOracle-selected widen/shrink proposal. All 24 states have this mismatch.

No PF2 simulator call was made. Fresh audit-only gradient construction is
permitted only after a separate PF2 protocol and seed lock is committed.

## Live freeze audit

- Parent tag: `RareTopo-M4-PF1-v0`.
- Peeled parent commit: `e6885bb59a8437cd5834a3a60ccf07c9c89624fe`.
- Branch: `feature/phase-m4pf2-joint-mean-covariance`.
- PF1 verdict reproduced: `PF1-C`, 24 states.
- PF1 protocol, state and seed hashes match the final summary.
- M3-BV2 state-source hash matches the final summary.
- Opening full regression: 1,262 passed with three pre-existing warnings.

## Zero-simulator invariant

```text
extra_simulator_calls = 0
```

PF2-0 read and hashed artifacts, performed pure matrix/vector arithmetic and
ran deterministic Gaussian fixtures. It generated no pilot, trajectory,
proposal evaluation, event sample or seed stream.

## Mean-gradient validation

The implemented dimensionless estimator is

\[
\widehat a_k=\sum_i\frac{a_i}{\sum_j a_j}r_{ki}z_{ki},
\]

with

\[
\nabla_{\mu_k}M_2=-M_2\Sigma_k^{-1/2}a_k.
\]

On the closed-form Gaussian fixture, central differences of proposal-mean
perturbations match `-M2 a^T u` in identity and mixed directions. At
`epsilon=1e-5`, the maximum relative discrepancy is approximately
`1.31e-10`. The normalized `+a` direction has a negative directional
derivative. Unit rescaling changes Euclidean displacement consistently while
preserving the 0.20 Mahalanobis step.

Six focused theory/parameterization tests pass.

## Source lock

Eleven read-only artifacts were hashed before analysis and re-hashed after
analysis. All hashes remained unchanged. The manifest is saved at
`results/phase_m4pf2_0/summary/m4pf2_0_source_manifest.json`.

The source set covers the PF1 raw confirmation record, final summaries,
protocol/state/seed locks, implementation semantics, final audit, M3-CA budget
definition and frozen M3-BV2 Value-Axis states.

## Identifiability result

Exact reconstruction of the real-state mean gradient requires aligned numeric
arrays containing samples or whitened coordinates, variance-mass weights,
component responsibilities and exact sample proposal identity. PF1 persisted:

- aggregate matrix gradients;
- spectral diagnostics;
- update covariances;
- probability and evaluation summaries;
- seeds and state identities.

It did not persist the required sample arrays. An aggregate second-moment
matrix does not determine the first moment `E_nuV[r_k z_k]`. Consequently no
real-state mean-gradient magnitude, direction, component concentration or
association plot is reported in PF2-0.

## Anchor compatibility

PF1 constructed its pooled covariance gradients using `state.proposal()`, the
base `s2 I` selected-component proposal. PF2's preferred common anchor is the
frozen S0 FreeOracle-selected scalar arm:

- 12 WIDEN states use the `widen` anchor;
- 12 SHRINK states use the `shrink` anchor;
- no state uses base.

Therefore:

```text
exact_match_count = 0
mismatch_count = 24
exact_reweighting_available = false
```

Reweighting cannot be performed because the PF1 sample arrays are absent.
Applying the base gradient to the S0-selected anchor would violate the task's
proposal-identity rule.

## Next-stage boundary

PF2 may proceed only by preregistering fresh gradient construction at each
locked S0-selected anchor. The same fresh samples must construct both the mean
gradient and the rank-1 covariance gradient. The subsequent P00/P10/P01/P11
cells must share that anchor, use the frozen 0.20 mean and covariance steps,
and apply P11 updates simultaneously.

Fresh construction cost remains audit-only for the FreeOracle feasibility
endpoint but must be reported as actual scientific cost. No confirmatory data
may be generated before the protocol, state and disjoint seed locks are
committed.

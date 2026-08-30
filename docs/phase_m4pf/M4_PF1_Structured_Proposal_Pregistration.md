# M4-PF1 Structured Proposal Preregistration

## 1. Status and scientific question

This protocol is frozen before the first PF1 simulator call. PF0 ended at
`RareTopo-M4-PF0-v0` with
`GO-WITHOUT-FROZEN-RECONSTRUCTION`: the matrix objective gradient passed
theory and deterministic algebra tests, while frozen artifacts lacked the
sample arrays needed for real-state reconstruction.

PF1 asks only whether adding one or two objective-gradient covariance
directions makes the proposal family materially more efficient under free
per-state proposal selection. It does not develop or tune a controller.

## 2. Benchmark and source lock

All 24 frozen M3-BV2 Value-Axis states are used, preserving the 12 WIDEN / 12
SHRINK split and all frozen event definitions, mixture means, weights,
component identity and non-controlled covariances. The state lock identifies
the source file by SHA-256 and selects every stored state in stored order.

The scalar reference uses the original M3-BV2 state arms and the original
500k arm-probability convention. Its FreeOracle result must reproduce the
M3-CA anchor; failure triggers `PF1-D` before scientific interpretation.

## 3. Families

`S0` is the frozen scalar family with base, `+0.20` isotropic log-covariance
and `-0.20` isotropic log-covariance candidates. Its per-state FreeOracle
choice is the frozen M3-BV2 oracle action.

`S1` keeps the largest-absolute eigenpair of the pooled matrix objective
gradient. `S2` keeps the two largest-absolute eigenpairs. Each structured
family contains base and one gradient-descent update:

\[
\Sigma' = \Sigma^{1/2}
\exp\left(-0.20\,\widetilde G_r/\|\widetilde G_r\|_F\right)
\Sigma^{1/2}.
\]

A zero gradient maps to base. S2 is rank two because the benchmark dimension
is two; it is still one fixed gradient-directed update and is not a free
full-matrix optimization.

For S1 and S2, FreeOracle chooses base or the structured update once per state
by the lower median replicate estimator variance. Exact ties select base.
Ranks are reported separately and are never pooled state by state.

## 4. Gradient data construction

For each state, four independent 100k mixed-pilot streams are pooled. The
source mixture fraction is 0.5 and the existing M3 variance-mass and component
responsibility implementations are reused. The controlled component is the
frozen newborn component. Gradient/reference construction is audit-only and
does not enter deployable FreeOracle cost.

Discovery uses two separate 10k gradient seeds and two 10k evaluation
replicates on one WIDEN and one SHRINK state. It can only detect implementation
invalidity; it cannot change eta, rank, normalization, safety limits, states,
seeds, endpoint definitions or gates.

## 5. Numerical safety

Eigenpairs are ordered by absolute eigenvalue. Before normalization, raw
gradient eigenvalues are clipped at absolute `1e6`; after Frobenius
normalization the log-step is clipped at absolute `0.20`. Every result must be
finite and SPD, have minimum covariance eigenvalue at least `0.5`, and have
condition number no greater than `4.0`. Any unsafe structured update is marked
invalid, falls back to base for containment, and triggers `PF1-D`; it is not
silently tuned or repaired.

## 6. Confirmatory evaluation and CRN

Confirmation uses eight 100k replicates per state and arm. Streams use the
same full 88-state grid index and replicate keys as the frozen M3-BV2
characterization. Component choices and standard-normal blocks are shared
across S0, S1 and S2 arms, giving paired common random numbers. S0 replay must
be bit-identical to the frozen records.

Each new structured arm receives an independent 500k probability
characterization. These characterization calls, all unselected arms, gradient
pilots and Oracle search are audit-only. The primary FreeOracle budget charges
only the selected 100k final evaluation, with zero pilot and decision cost.

## 7. Endpoints and verdict

The primary endpoint for each family is the median across states of the
statewise median across replicates of absolute budget VRF. The best structured
family is the larger of the separately reported S1 and S2 medians.

- `PF1-A`: best structured median FreeOracle VRF is greater than 1.
- `PF1-B`: it is greater than 0.1 and at most 1.
- `PF1-C`: it is at most 0.1.
- `PF1-D`: scalar reproduction, protocol, numerical safety, provenance or
  accounting is invalid.

Secondary results include the complete 24-state distributions, thresholds at
0.1 and 1, class medians, M2 ratios, gradient spectra, ESS and weight-tail
diagnostics. The verdict cannot be changed by a secondary endpoint.

## 8. Claim and stopping boundaries

PF1 may establish proposal-family feasibility under free proposal selection.
It cannot establish deployable controller efficiency, universal optimality,
causal anisotropy effects or real-system speedup. It cannot revive descriptive
covariance matching. `M3-Q` remains blocked.

`PF1-C` stops covariance-rank escalation and routes any future work to a
separately preregistered joint mean-plus-covariance study. `PF1-D` stops all
new science until the invalidity is resolved.

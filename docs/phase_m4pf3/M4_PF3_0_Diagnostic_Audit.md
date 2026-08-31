# M4-PF3-0 Allocation and Coverage Diagnostic Audit

## 1. Status

PF3-0 is complete with zero new simulator calls. It reused all 24 persisted
PF2 gradient archives at their exact S0-selected scalar anchors. The locked
primary routing verdict is:

```text
Route A — ALLOCATION-DOMINANT
Next authorized stage: PF3-A Weight Reallocation
```

This verdict authorizes a weight-only intervention study at the PF2 P11
anchor. It does not authorize a missing-mode birth arm.

## 2. Parent freeze and opening regression

- parent tag: `RareTopo-M4-PF2-v0`
- parent peeled commit: `82e6f36438fa1db6cf0b10055c16b573c07dd6b9`
- PF2 verdict: `PF2-C`
- PF2 gradient archives: 24
- PF2 figures: 12
- PF2 manifest sources verified: 31/31
- opening regression: `1289 passed, 3 warnings in 311.89 s`

The warnings are the existing pytest deprecation warnings in H3 fixtures.
Unrelated untracked workspace files were not modified.

## 3. PF3-0 source and simulator firewall

The deterministic PF3-0 manifest locks 36 read-only sources, including the 24
PF2 archives, PF2 raw four-cell records, PF2 summaries and locks, the PF1
family summary, M3-CA cost definitions and the M3-BV2 state definition.

- source-manifest SHA-256 before analysis:
  `3c4e1376e177682965c5decca26a57e35257ffa0b59ab74d214d8af761f5e743`
- source-manifest SHA-256 after analysis: identical
- individual source mismatches after analysis: 0
- extra simulator calls: 0
- states retained: 24 (`12 WIDEN`, `12 SHRINK`)

Recomputed responsibilities match the stored selected-component
responsibilities with maximum absolute error `1.78e-15`.

## 4. Allocation diagnosis

The normalized M2-tilted responsibilities define

\[
A_{alloc}=\tfrac12\sum_k|\bar r_k-\alpha_k|.
\]

| Quantity | Result |
|---|---:|
| Median `A_alloc` | 0.149123744858 |
| States with `A_alloc >= 0.15` | 12/24 |
| Minimum `A_alloc` | 0.008198893764 |
| Maximum `A_alloc` | 0.239721184042 |
| Median `H(alpha)` | 0.650422640506 |
| Median `H(r_bar)` | 0.675231497909 |
| WIDEN median `A_alloc` | 0.053808081773 |
| SHRINK median `A_alloc` | 0.178883175948 |

Allocation is material by both the preregistered median rule
(`0.1491 >= 0.10`) and the state-count rule (`12 >= 8`). The largest
starvation ratio is `7.5031` in state `c006_s2_00500`, component 1: nominal
weight `0.03686` versus tilted responsibility `0.27658`.

The class split is descriptive: mismatch is concentrated in SHRINK states,
while several WIDEN states have weak allocation mismatch.

## 5. Coverage diagnosis

Coverage uses fixed chi-square reference thresholds and normalized variance
mass, not raw proposal frequency.

| Quantity | Result |
|---|---:|
| Median `U99` | 0.011149725555 |
| Median `U999` | 0.000879415259 |
| States with `U99 >= 0.20` | 3/24 |
| States with `U999 >= 0.25` | 0/24 |
| Maximum `U99` | 0.250907961051 |
| Maximum `U999` | 0.067155357411 |
| Median top-1% uncovered fraction | 0.022691198192 |
| Maximum top-1% uncovered fraction | 0.391139764483 |
| WIDEN median `U99` | 0.126775225219 |
| SHRINK median `U99` | 9.28e-09 |

Aggregate coverage is not material under the locked median or state-count
rule. A localized severe-coverage flag is nevertheless present because the
top-1% uncovered fraction exceeds 0.25 in three low-`s2` WIDEN states:
`c000_s2_00065`, `c001_s2_00065` and `c006_s2_00065`.

This localized flag is retained explicitly. It does not change the locked
primary route after results: the preregistered aggregate coverage-material
gate is false, so PF3-0 remains Route A rather than Route C.

## 6. Birth-candidate firewall

The locked protocol constructs the birth library only for coverage-authorized
routes B or C. Route A was selected, so:

- birth candidates generated: 0
- states with positive birth scores: 0 (not evaluated)
- states with admitted birth candidates: 0 (not evaluated)

These zeros mean “not authorized”, not evidence that all birth candidates
would have nonpositive M2 derivatives. No post-hoc candidate was constructed
from the three localized severe states.

## 7. Routing decision and sensitivity

At the primary `1.0x` thresholds:

- allocation material: yes
- aggregate coverage material: no
- localized severe coverage: yes
- route: A

Descriptive sensitivity gives Route A at `0.5x`, Route A at `1.0x`, and Route
D at `1.5x`. The primary route is not replaced by the sensitivity result.

## 8. Authorized next experiment

PF3-A must use PF2 P11 as its common anchor. Because PF3-0 archives are at S0,
PF3-A requires fresh P11 construction samples before an allocation update.
The next protocol must freeze:

- a single normalized logit step with `eta_alpha = 0.20`;
- arms A0 (P11) and A1 (P11 plus allocation step);
- all 24 states and eight paired CRN replicates;
- a 100,000-sample selected-arm deployable budget;
- new seeds disjoint from PF1, PF2 and PF3 discovery;
- probability characterization, safety gates and audit-only costs.

No birth arm, covariance-rank increase, mean-step sweep or controller tuning
is authorized.

## 9. Outputs and claim boundary

PF3-0 produced three state/component/coverage tables, a JSON routing summary
and ten diagnostic figures. Figure PF3-0-9 records that birth scoring was not
authorized rather than displaying invented candidates.

The diagnosis is conditional on the frozen 24-state benchmark, current
two-component mixture parameterization, S0 diagnostic anchors and locked
routing thresholds. It is a routing heuristic, not proof of universal
allocation starvation or deployability.

The closing PF3-0 full regression passed with `1304 passed, 3 warnings` in
`301.91 s`. The three warnings are unchanged H3 pytest deprecation warnings.
The frozen diagnostic stage is tagged `RareTopo-M4-PF3-0-v0` after this
closing result is committed.

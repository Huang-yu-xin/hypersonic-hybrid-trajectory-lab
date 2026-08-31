# M4-PF3 Mixture Allocation and Missing-Mode Repair Audit

## 1. Status and final verdict

M4-PF3 is complete on all 24 frozen Value-Axis states. PF3-0 selected the
allocation-dominant diagnostic route, and the preregistered PF3-A experiment
then compared the exact PF2 P11 anchor (A0) against one normalized
objective-gradient logit update (A1).

The primary FreeOracle median budget VRF is

\[
0.0132683005544 \le 0.1.
\]

The locked final verdict is therefore:

```text
PF3-D — CURRENT MIXTURE REPAIR FAMILY STILL INSUFFICIENT
```

This is distinct from the diagnostic route name PF3-A. Route A authorized the
weight experiment; it did not predetermine a PF3-A breakthrough verdict.

## 2. PF3-0 mechanism routing

PF3-0 used 24 persisted S0-anchor archives and made zero new simulator calls.
Its 36-source manifest was unchanged before and after analysis.

- median S0-anchor `A_alloc`: `0.149123744858`
- states with `A_alloc >= 0.15`: `12/24`
- median `U99`: `0.011149725555`
- states with `U99 >= 0.20`: `3/24`
- primary route: A, allocation-dominant

Three low-`s2` WIDEN states retain a localized severe top-tail coverage flag,
but aggregate coverage did not pass the preregistered material gate. Birth
was consequently not authorized or evaluated. PF3-0 is frozen at tag
`RareTopo-M4-PF3-0-v0` and commit
`ca8d3f579ab406818682615c3efccaf5abd527cf`.

## 3. Confirmatory protocol

- intervention anchor: exact per-state PF2 P11 proposal
- A0: P11 unchanged
- A1: P11 plus one mixture-logit allocation step
- allocation direction: `r_bar - alpha`
- normalized logit step: `eta_alpha = 0.20`
- numerical-zero threshold: `1e-12`
- component centres and covariances: unchanged
- fresh P11 construction: four independent 100,000-sample streams per state
- confirmation: eight paired CRN replicates per state and arm
- final-arm samples: 100,000 per replicate
- A1 probability characterization: 500,000 new samples per state
- A0 probability: frozen PF2 P11 characterization
- states: 24 (`12 WIDEN`, `12 SHRINK`)
- seeds: disjoint from PF1, PF2, PF3-0 and PF3 discovery
- FreeOracle tie order: A0, then A1
- deployable denominator: selected 100,000-sample arm only

The protocol, state list and complete seed list were committed before
discovery or confirmation data.

## 4. Discovery safety

The two locked discovery states passed without a protocol change. Both logit
steps had norm `0.20`; minimum ESS was `1295.87`, maximum normalized weight
was `0.00397`, and there were no finite-weight, simplex, support or fallback
failures.

## 5. Confirmatory arm results

Higher VRF is better. Counts are out of 24 states.

| Arm | Definition | Median VRF | States >0.1 | States >1 | Worst-state VRF | WIDEN median | SHRINK median |
|---|---|---:|---:|---:|---:|---:|---:|
| A0 | PF2 P11 anchor | 0.012770531890 | 0 | 0 | 0.007502232196 | 0.012242592702 | 0.016194061336 |
| A1 | One allocation step | 0.013268300554 | 0 | 0 | 0.007413387889 | 0.012491480676 | 0.017258916346 |

A0 reproduces the frozen PF2 P11 median `0.012830575904` with a relative
difference of `0.4680%`, passing the preregistered `10%` independent-stream
tolerance.

FreeOracle selects A1 in `22/24` states and A0 in `2/24`. Its median equals
`0.013268300554`, with no state crossing either absolute-efficiency gate. The
FreeOracle median is only `3.41%` above the frozen PF2 P11 headline.

## 6. Allocation mechanism

The statewise paired median log contrast is

\[
\operatorname{median}_s\log(VRF_{A1}/VRF_{A0})
=0.057535837914.
\]

Using the locked approximately-neutral threshold:

- improves: 20 states
- worsens: 0 states
- approximately neutral: 4 states

The ratio of the two arm-level medians is `1.03898`; the paired statewise log
contrast corresponds to a somewhat larger typical multiplicative gain because
these are different median operations.

The fresh P11 median allocation mismatch falls from `0.183427618102` to a
reweighted A1 value of `0.149825710576`, an `18.32%` reduction. Median weight
TV is `0.067060653459`, median KL is `0.009566841761`, and statewise TV ranges
from `0.0114679` to `0.0703863`. The update therefore moves allocation in the
intended direction and reduces the diagnostic mismatch, but the resulting VRF
gain remains small in absolute terms.

The same construction-sample reweighting predicts a negative M2 log ratio in
`23/24` states. One finite-step state is slightly positive; it is retained and
not tuned away.

## 7. Coverage and mechanism attribution

Weight reallocation leaves component centres and covariance support unchanged.
The reweighted tilted coverage summaries are correspondingly almost unchanged:

| Metric | A0 | A1 reweighted |
|---|---:|---:|
| Median `U99` | 0.002594788055 | 0.002625126884 |
| Median `U999` | 0.000131368948 | 0.000132584120 |

Thus the observed local gain is consistent with allocation repair, not with a
claim that missing support was repaired. No birth proposal was tested, and the
localized PF3-0 coverage flags remain outside this experiment's intervention
scope.

## 8. Tail and numerical safety

- minimum confirmatory ESS: `11492.0683`
- maximum normalized weight: `0.00190338`
- nonfinite weights: 0
- event-weight underflows: 0
- support-loss indicators: 0
- fallbacks: 0
- positive/simplex weight checks: 24/24 passed
- all A0/A1 state records valid: yes

The 24 fresh P11 construction archives contain samples, variance mass, all
component responsibilities, source strata, proposal identity and gradient
seeds. They total approximately `365 MB`. The final source manifest verifies
all 31 locked sources without a mismatch.

## 9. Cost accounting

| Cost category | Simulator samples |
|---|---:|
| Counterfactual deployable selected arm, per state | 100,000 |
| Confirmation audit-only scientific cost | 60,000,000 |
| Discovery audit-only scientific cost | 120,000 |
| Total actual PF3 scientific cost | 60,120,000 |

The 100,000 figure is the FreeOracle proposal-family feasibility denominator.
It does not make fresh gradients or Oracle arm selection deployable or free.

## 10. Interpretation

PF3 identifies a real mixture-weight mismatch: a frozen M2-gradient update is
selected in most states, reduces the mismatch diagnostic and improves paired
VRF consistently. However, the best locked two-arm family remains roughly
`75x` below VRF 1 and below the material threshold in every state.

Together with PF1 and PF2, the frozen benchmark now limits the explanatory
power of:

- scalar and rank-1/rank-2 covariance changes;
- one-step local mean translation;
- joint mean plus rank-1 covariance deformation;
- one-step mixture-weight reallocation.

The taskbook's birth route was not authorized by the aggregate PF3-0 gate, so
PF3 does not exclude separately preregistered missing-mode birth on the three
localized severe-coverage states. It does exclude claiming that the tested
one-step weight repair closes the efficiency gap.

The next scientific action is a higher-level review of event/topology
representation, proposal-family architecture, benchmark regime and
multi-stage or path-space proposal design. No further proposal knob or M3-Q
stage is executed here.

## 11. Provenance and claim boundary

- raw confirmation SHA-256:
  `4ef61e753520f4bcedcb0ec6f19b8113e0af3e96a29c06fd9451a2219add83fe`
- family summary SHA-256:
  `dd463d12928d62d96c99fce6e22d450a655187df3f08456a782ce657a260f77b`
- final source-manifest SHA-256:
  `3315deb480200ee4c47f4dd875a0de0c01f9035088e82f659be9aca77afa9de2`

The conclusion is conditional on the frozen 24-state benchmark, PF2 P11
anchor, current two-component mixtures, fixed one-step `eta_alpha=0.20`
intervention and FreeOracle accounting. It is not a wall-clock, deployability,
unseen-event or universal mixture-architecture claim.

The closing full regression passed with `1319 passed, 3 warnings` in
`310.19 s`. The warnings are the unchanged H3 pytest fixture deprecations.
The final stage is tagged `RareTopo-M4-PF3-v0` after this result is committed.

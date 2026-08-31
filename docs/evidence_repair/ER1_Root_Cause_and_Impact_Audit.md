# ER-1 Root Cause and Impact Audit

## Root cause

The frozen topology oracle returns strings in the domain `S0`–`S4`, with
`S0` denoting the nominal complement.  The first contaminated empirical
code compared these values with the unrelated literal `"NOMINAL"`:

```python
ind_event = (stage.labels != "NOMINAL").astype(float)
```

Because no topology label equals `NOMINAL`, every sample was classified as an
event.  This is a semantic namespace collision between a prose-like nominal
marker and the actual topology domain.  It was introduced in the M3-v0
empirical scalar driver at commit
`0f6cdfe8fb6fc938e73b555f55d758980c9510f2`.  Its parent commit
`098fbc1cad5a2b00c9ced12c1b008336bcf49e56` contains the M3 estimator stack
but not the contaminated benchmark comparison.  `RareTopo-M2-v0` imports the
authoritative `NOMINAL` constant whose value is `S0` and remains the last
known clean frozen empirical stage.

A second cross-domain mismatch was exposed by the mandatory probability-scale
guard: evaluation `P_hat` is the full `S1`–`S4` event probability, while the
`p_ref` passed to historical VRF formulas sums only missing modes `S2`–`S4`.
Corrected M3-D full-event estimates are mutually consistent across 72 arms,
but are 1.14–1.76 times the missing-mode-only reference. Thus historical VRF
and Strong budget gates are invalid-reference-semantics fields, not corrected
cost-efficiency evidence.

## Why tests missed it

The failure was not caught because several tests independently repeated the
same `!= "NOMINAL"` expression, so implementation and expectation shared the
same bug.  Other tests checked deterministic replay, schema, CRN parity,
finite arithmetic and agreement with frozen outputs.  Those reproduce a
contaminated path faithfully but do not validate its event semantics.  There
was no cross-stage semantic contract, no arm/source/event independence test,
and no catastrophic probability-scale check against `p_ref`.  The M5-AR
parent audit was the first check to compare the claimed `P_hat` meaning with
the frozen probability scale.

## Direct impact

At M3-v0, M3-D, M3-G/BV2 and PF1–PF3, event-dependent contributions were
constructed with the wrong mask.  Directly invalid quantities include
`P_hat`, `M2`, variance mass, event-weight ESS, event-driven gradient
magnitudes/signs, actions, arm comparisons, VRF, FreeOracle and the empirical
gates.  PF3 allocation, coverage and birth diagnostics used contaminated
variance mass and are also directly invalid.

M3-CA is an artifact-only derivation but inherits contaminated parent
quantities, so its cost arithmetic remains mechanically reproducible while
its scientific verdict is superseded pending corrected BV2 evidence.

## Structurally valid results

The following remain structurally valid unless a later stage-specific audit
finds another defect:

- Gaussian covariance-gradient identities and symbolic derivations;
- deterministic topology predicate and M1-D/M2 event semantics;
- SPD projection and numerical-safety checks;
- generic bootstrap, CRN and source-lock mechanics;
- Git/protocol provenance and historical tag identities;
- schema checks that do not claim event-dependent scientific validity.

Their application to contaminated empirical gradients must still be replayed.

## Raw-data sufficiency

The earliest contaminated stage did not persist its pilot or final evaluation
sample arrays. Its corrected metrics therefore could not be reconstructed from
stored JSON summaries. PF2/PF3 preserve gradient archives, which permitted
partial diagnostic reanalysis, but their final evaluation samples are absent.

M3-v0 was replayed with the original states, seeds, sample counts, parameters
and gates. Its widening-dominant negative result still authorized only the
preregistered M3-D benchmark question. M3-D then reused the original 24 states,
exact reference seeds, 500,000 samples per arm and draw order. The corrected
class composition became WIDEN 6 / SHRINK 7 / HOLD 3 / ambiguous 8, failing
the exact 8/8/8 reference gate. No online M3-D or descendant stage was run.

## Corrected scientific conclusions

The local M3 covariance descent signal survives, but adaptive value over a
fixed widening rule does not. Budget efficiency cannot be adjudicated from
the historical VRF because its probability reference has different event
semantics. The historical M3-D
sign-diverse benchmark does not survive correction. Consequently, none of the
historical M3-G, BV/BV2, CA or PF empirical conclusions may route a new
proposal architecture. PF2/PF3 raw-archive reanalysis quantifies the error but
does not repair their missing final evaluations.

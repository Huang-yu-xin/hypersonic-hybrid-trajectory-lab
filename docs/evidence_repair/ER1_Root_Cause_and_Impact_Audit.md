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
sample arrays.  Its corrected metrics therefore cannot be reconstructed from
stored JSON summaries.  PF2/PF3 preserve gradient archives, which permit
partial diagnostic reanalysis, but their final evaluation samples are also
absent.  ER-1 must first replay M3-v0 with the original states, seeds, sample
counts, parameters and gates.  Descendants remain unauthorized until each
corrected parent passes its original gate.

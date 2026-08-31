# M3-D3 D3-0 HOLD Boundary Diagnosis

## Zero-simulator provenance

All figures and tables are reconstructed from committed M3-D2 discovery and confirmation JSON. This script imports no simulator or controller code; `extra_simulator_calls = 0`.

## Result

**HOLD concentrated near an identifiable boundary: YES.** The primary candidate-family axis is the selected-component covariance scale `s2`. Five fixed configurations have a W-to-S path through either ambiguity or HOLD; two (`c001`, `c010`) contain an independently confirmed HOLD interior to a W-H-S path.

## Why s2 is primary

Within each frozen configuration D2 varies only `s2`, making its action transition identifiable without changing event semantics or the classifier. The physical geometry fields (`theta_deg`, `h`, curvature flags and offsets) are meaningful but co-vary as discrete frozen configurations; D2 has no controlled one-axis evidence to select one of them. Selected mode/component mean are likewise frozen, categorical or derived.

Detected paths: 5. Unsupported-contrast ambiguity has median diagnostic H-proximity 0.0813; no-unique-class ambiguity has median 0.0676. These descriptive values do not establish that unsupported states are HOLD-like.

## Route

**D3-0A — Boundary Identified.** The only next permitted step is a human scientific decision whether to preregister a fixed, boundary-focused `s2` family. D3-1, discovery, confirmation, controller trials, and rarity-shift remain unstarted and unauthorized.

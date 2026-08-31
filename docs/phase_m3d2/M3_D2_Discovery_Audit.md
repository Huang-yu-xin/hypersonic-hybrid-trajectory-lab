# M3-D2 Discovery Audit

## Scope and frozen inputs

Discovery was executed only after commit `fc68839` froze the schema-2 event contract, the 72-state fixed candidate pool, classifier, probability contract, balancing rule and disjoint seed namespaces. Commit `59d3242` froze the source manifest, and commit `a0a1b16` froze the 72/72 legal symbolic pool plus eight independent full-event references.

The candidate pool is the fixed Cartesian product of eight frozen configurations and nine selected-component scales. Its preregistered strata contain 24 G-W, 24 G-H and 24 G-S states. No state was added, removed or moved after discovery began.

## Full-event probability reference

Each configuration used 1,000,000 independent direct target draws under `N(0,I_2)`. Event membership was `topology != S0`, so the reference includes S1, S2, S3 and S4. Every configuration observed all four event topologies. The eight references consumed 8,000,000 samples and are independent of both action-characterization stages.

## Discovery execution

- Candidates: 72
- Arms per candidate: BASE, WIDEN, SHRINK
- Samples per arm: 100,000
- Paired batches: 20
- Discovery simulator samples: 21,600,000
- Wall time: 193.05 s
- Probability-domain failures: 0
- Numerical/ESS invalid states: 0
- Minimum arm ESS: 2012.09
- Largest probability discrepancy as a fraction of its frozen four-SE tolerance: 0.6802

## Provisional classes

| Class | Count |
|---|---:|
| WIDEN | 20 |
| HOLD | 5 |
| SHRINK | 10 |
| AMBIGUOUS | 37 |
| INVALID | 0 |

The provisional HOLD count is below eight. The protocol nevertheless permits confirmation of all five provisional HOLD states and the deterministic top candidates from WIDEN and SHRINK; it does not permit promotion of any ambiguous state.

## Deterministic shortlist

The frozen certainty/diversity/tie-break rule selected:

- WIDEN: 12 of 20
- HOLD: all 5 of 5
- SHRINK: all 10 of 10
- Total confirmation states: 27

The shortlist was committed at `2e986c7` before any confirmation stream was generated. All 72 discovery records, including the 37 ambiguous states and all exclusions, remain preserved in `results/phase_m3d2/discovery/`.

## Discovery verdict

`PASS TO INDEPENDENT CONFIRMATION`, with a preregistered feasibility warning: only five provisional HOLD states were available. No grid expansion, threshold change or class-target change was made.

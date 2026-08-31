# M3-D2 Final Benchmark Decision Record

## Status

```text
M3-D2 STATUS: COMPLETE
M3D2-1: FAIL
FINAL VERDICT: D2-B
CORRECTED BENCHMARK NOT CONSTRUCTIBLE UNDER CURRENT CANDIDATE FAMILY
```

This document freezes the negative benchmark-construction decision. It does **not** freeze a 24-state benchmark and does not authorize a controller experiment.

## Live Git and parent lineage

- D2 branch: `feature/phase-m3d2-corrected-sign-diverse-benchmark`
- Starting parent HEAD: `d7575c51fc0c14e88753ffb0208ef5885df76164`
- `RareTopo-M3-v2`: `f30e8bf52d69fb6327df7fa1487347f193543f22`
- `RareTopo-M3-D-v1`: `8204819bb3c5230f5940f410056cf43b8e44b89b`
- Opening regression: `1363 passed, 3 warnings`
- Closing regression: `1390 passed, 3 warnings in 354.94s`, exit code 0

## Event semantics

- Schema: 2
- Nominal topology: S0
- Corrected event: S1-S4
- Event definition ID: `FULL_TOPOLOGY_EVENT_S1_S4`
- Full-event reference: eight independent configuration-level direct target MC streams, 1,000,000 samples each
- Historical S2-S4-only `p_ref`: not used

## Candidate pool and discovery

- Fixed candidate count: 72
- Candidate strata: 24 G-W / 24 G-H / 24 G-S
- Legal candidates: 72
- Discovery samples per arm: 100,000
- Discovery result: 20 WIDEN / 5 HOLD / 10 SHRINK / 37 AMBIGUOUS / 0 INVALID
- Frozen shortlist: 12 WIDEN / 5 HOLD / 10 SHRINK

## Confirmation

- Confirmation samples per arm: 500,000
- Result: 12 WIDEN / 3 HOLD / 10 SHRINK / 2 AMBIGUOUS / 0 INVALID
- Discovery-to-confirmation agreement: 92.59%
- Probability sanity failures: 0
- Lowest confirmation arm ESS: 8335.35

## Final benchmark gate

Required:

```text
WIDEN >= 8
HOLD   >= 8
SHRINK >= 8
```

Observed valid confirmed states:

```text
WIDEN = 12
HOLD   = 3
SHRINK = 10
```

The deterministic selector could select eight WIDEN and eight SHRINK states, but only three HOLD states exist. The exact 8/8/8 benchmark is therefore absent. `m3d2_final_benchmark.json` intentionally contains no frozen `states`, and `m3d2_final_benchmark.csv` contains only its schema header.

## Historical comparison

| Evidence object | Composition | Status |
|---|---|---|
| Historical contaminated benchmark | 8 W / 8 H / 8 S | superseded |
| Corrected historical 24-state replay | 6 W / 3 H / 7 S / 8 ambiguous | negative reference gate |
| New corrected D2 confirmation | 12 W / 3 H / 10 S / 2 ambiguous | D2-B; no balanced benchmark |

M3-D2 does not “recover the original truth.” It shows that the preregistered corrected candidate family does not contain enough independently confirmed HOLD states to construct the required measurement instrument.

## Simulator accounting

| Category | Samples |
|---|---:|
| Candidate assembly anchor | 160,000 |
| Full-event probability reference | 8,000,000 |
| Discovery | 21,600,000 |
| Confirmation | 40,500,000 |
| Grand total | 70,260,000 |

Controller online trials: **0**.

## Freeze and authorization boundary

- `RareTopo-M3-D2-v0` is **not created**, because that tag is reserved for D2-A.
- M3-G2/M3-G-v2 is not authorized.
- BV/BV2, M3-CA, PF, M3-Q and M5-AR remain blocked.
- The next admissible action is a separate human scientific decision and a new preregistration concerning the state family, finite-step action family, or the rarity of HOLD under corrected semantics.
- No controller trial may be run from this D2-B result.

## Commit ledger

| Commit | Role |
|---|---|
| `cae38a6` | live parent audit and task ingestion |
| `fc68839` | schema, probability, classifier, candidate, seed and balancing preregistration |
| `59d3242` | source manifest lock |
| `a0a1b16` | candidate pool and full-event probability references |
| `2090229` | discovery raw evidence |
| `2e986c7` | deterministic shortlist freeze |
| `072061a` | independent confirmation raw evidence |
| `a71fa1e` | discovery/confirmation audit and transition matrix |
| `a31d511` | final D2-B machine-readable verdict, figures and output tests |

The final documentation commit follows this ledger. No D2 tag is created.

# M3-D2 Independent Confirmation Audit

## Independence

Confirmation read only the shortlist committed at `2e986c7`. It used the `D2-CONFIRMATION` seed namespace `[3202002, original_candidate_index]`, which is disjoint from probability reference `[3202000, ...]` and discovery `[3202001, ...]`. Discovery batches were not reused as confirmation evidence.

## Execution

- Shortlisted states: 27
- Samples per arm: 500,000
- Arms: BASE, WIDEN, SHRINK
- Paired batches: 20
- Confirmation simulator samples: 40,500,000
- Wall time: 342.87 s
- Probability-domain failures: 0
- Numerical/ESS invalid states: 0
- Minimum arm ESS: 8335.35
- Largest probability discrepancy as a fraction of its frozen four-SE tolerance: 0.5253

## Authoritative classes

| Class | Count |
|---|---:|
| WIDEN | 12 |
| HOLD | 3 |
| SHRINK | 10 |
| AMBIGUOUS | 2 |
| INVALID | 0 |

The three confirmed HOLD states are:

| State | Configuration | s2 |
|---|---|---:|
| `c001_s2_00400` | `m1d_b20260827_c001` | 4.00 |
| `c007_s2_00125` | `m1d_b20260827_c007` | 1.25 |
| `c010_s2_00500` | `m1d_b20260827_c010` | 5.00 |

The two provisional HOLD states `c006_s2_00125` and `c006_s2_00800` became AMBIGUOUS because the required paired contrast was not supported. They were not forced into any target class.

## Discovery-to-confirmation stability

| Discovery | Confirmation | Count |
|---|---|---:|
| WIDEN | WIDEN | 12 |
| HOLD | HOLD | 3 |
| HOLD | AMBIGUOUS | 2 |
| SHRINK | SHRINK | 10 |

Overall agreement is `25/27 = 92.59%`. WIDEN and SHRINK were stable for every shortlisted state; the loss of two HOLD states is decisive for the benchmark feasibility gate.

## Probability semantics

All 27 states passed both arm-vs-`p_ref_full` and pairwise arm consistency checks under the same S1-S4 event. Consequently this is not D2-C. No state failed numerical, seed, draw-order or source-integrity checks, so it is not D2-D.

## Confirmation verdict

The authoritative class count contains only three HOLD states. `M3D2-1` therefore fails, and the only admissible final verdict is D2-B.

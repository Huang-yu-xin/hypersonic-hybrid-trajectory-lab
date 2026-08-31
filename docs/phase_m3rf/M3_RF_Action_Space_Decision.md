# M3-RF Action-Space Decision

## Decision

**Primary route: M3-RF-B — reformulate to directional WIDEN/SHRINK + ABSTAIN.**

Confirmed D2 evidence provides WIDEN=12 and SHRINK=10. HOLD is not sufficiently available as a balanced action: only three D2 states independently confirm and D3's preregistered boundary refinement produced 2 HOLD versus 10 ambiguous outcomes. The decision retains every negative result and requires no classifier, threshold, event-semantics, or parent-gate change.

ABSTAIN is not a trained HOLD class. It is a protocol decision triggered by insufficient paired support, near-zero gradient confidence, or classifier ambiguity; deployment uses BASE/no adaptation.

## Three-action identifiability

| Criterion | Result |
|---|---|
| All W/H/S exist under corrected semantics | PASS |
| HOLD independently reproducible | MIXED |
| HOLD not dominated by ambiguity at boundary | FAIL |
| Diverse HOLD without post-hoc search | FAIL |
| No weakening of classifier evidence | PASS |

Overall: **not defensible** as a balanced three-action controller benchmark. RFA is not allowed: D3 already tested the coarse-grid explanation and no untested artifact-supported explanation remains.

## Evidence matrix

| Evidence | Three-action | Two-direction+abstain | Continuous |
|---|---|---|---|
| W availability | SUPPORTED | SUPPORTED | SUPPORTED |
| S availability | SUPPORTED | SUPPORTED | SUPPORTED |
| H availability | WEAK | NOT APPLICABLE | NOT APPLICABLE |
| ambiguity handling | UNSUPPORTED | SUPPORTED | WEAK |
| independent confirmation | WEAK | SUPPORTED | WEAK |
| boundary stability | UNSUPPORTED | SUPPORTED | WEAK |
| natural benchmark construction | UNSUPPORTED | SUPPORTED | WEAK |
| requires threshold change | UNSUPPORTED | SUPPORTED | SUPPORTED |
| corrected lineage compatible | SUPPORTED | SUPPORTED | SUPPORTED |

RFA is unsupported; RFC is weak (transition paths suggest continuity but no continuous-action protocol is yet validated); RFD is weak because W/S availability is established; RFE is not selected because RF-B is already preregistrable. The next authorized action is a separately preregistered M3-DS directional-sign benchmark with a predeclared abstention policy. Rarity shift and M3-Q remain blocked.

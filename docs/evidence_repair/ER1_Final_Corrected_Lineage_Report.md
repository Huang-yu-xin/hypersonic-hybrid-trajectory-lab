# ER-1 Final Corrected Lineage Report

## Final status

`COMPLETE — OLD LINEAGE STOPPED AT CORRECTED M3-D REFERENCE GATE`

The frozen topology domain is `S0`–`S4`, with `S0` nominal. The first
contaminated empirical driver compared those labels with the non-domain
literal `NOMINAL`, causing every sample to be treated as an event. Typed event
semantics schema 2 now derives event membership only from `topology != S0`.
The first contaminated stage is M3-v0; the last clean frozen empirical parent
is `RareTopo-M2-v0`.

## Corrected stage decisions

| Stage | Corrected headline | Original gate | Child authorized |
|---|---|---|---|
| M3-v0 | Active fraction 0.578; accuracy 0.865; zero advantage over Always-Widen; historical VRF uses an incompatible probability reference | M3-3 FAIL; Strong INVALID_REFERENCE_SEMANTICS | Yes, but only M3-D, whose preregistered purpose is to resolve this widening-dominant negative result |
| M3-D reference gate | Original 8/8/8 state set becomes WIDEN 6 / SHRINK 7 / HOLD 3 / ambiguous 8 | M3D-1 FAIL | No |
| M3-D online | Not run | Parent failed | No |
| M3-G-v1 through M4-PF3 | Not run | Corrected parent failed | No |

M3-D changed class on 12 of 24 frozen states. Because eight states became
reference-ambiguous and the exact 8/8/8 composition no longer exists, running
the online 192-trial controller comparison would violate its preregistered
benchmark gate. The old lineage therefore stops before that experiment.

## Evidence coverage and simulator accounting

PF2 and PF3 persisted gradient samples were reanalysed with zero simulator
calls. Their corrected-to-legacy variance-mass medians are respectively
0.0203922 and 0.0197806, and corrected non-event mass is exactly zero. These
are diagnostic impact estimates only: final evaluation arrays were absent, so
they cannot restore either parent gate.

New simulation was unavoidable at the first affected stage. M3-v0 reused the
original 64 trials, seeds, sample counts and draw order (20,480,000 repair
calls). M3-D reused the exact 24 states, reference seeds, 500,000 samples per
arm and draw order (36,000,000 repair calls). Total repair simulator calls are
56,480,000. No controller, state, threshold or success gate was retuned.

The scale audit also separated two probability domains: corrected `P_hat`
estimates the full `S1`–`S4` event, but historical `p_ref` contains only
missing modes `S2`–`S4`. Corrected M3-D estimates agree across all 72
same-event arms, while their ratio to the missing-mode reference ranges from
1.14 to 1.76. Historical VRF/Strong values are therefore not valid corrected
cost evidence.

## Surviving and superseded evidence

Gaussian gradient identities, finite-difference algebra, SPD safety,
bootstrap/CRN machinery and source-lock mechanics remain structurally valid.
Historical event-dependent M3-v0 through PF3 conclusions are superseded for
scientific routing. PF0 theory remains structurally valid, but its empirical
application is blocked by the failed corrected parent.

The final corrected tags are `RareTopo-M3-v2` and `RareTopo-M3-D-v1`.
`RareTopo-M3-v1` is retained as an immutable intermediate event-mask repair
snapshot and is superseded by v2's probability-reference audit. All historical
tags remain at their original commits. No descendant tag was created after the
M3-D stop.

## Current frontier and authorization

The current valid frontier is corrected M3-v0 (`RareTopo-M3-v2`) plus the negative corrected
M3-D reference-gate result. M5-AR is not authorized because no corrected
PF3-equivalent parent exists. M3-Q remains blocked. The next permissible
scientific action is a separately preregistered decision about constructing a
new corrected sign-diverse benchmark; M3-G, BV/BV2, CA and PF stages are not
automatically authorized.

Final regression: `python -m pytest -q` → **1363 passed, 3 warnings, exit 0**
in 381.03 seconds.

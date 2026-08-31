# M3-D2 Protocol and Preregistration

This document freezes the M3-D2 benchmark-construction protocol before any new D2 simulator call.

## Scientific object

M3-D2 asks only whether a corrected, sign-diverse finite-step benchmark can be constructed inside the frozen M1-D/M2/M3-D state family. It does not evaluate a controller.

The event contract is schema 2: `S0` is nominal and the event is exactly `S1 | S2 | S3 | S4`. Proposal-arm names are never event predicates. Historical S2-S4-only probabilities are barred from corrected probability or VRF evidence.

## Fixed candidate family

Option A is used: one fixed pool of 72 symbolic candidates, the Cartesian product of eight frozen benchmark configurations and nine scalar selected-component covariance values. The grid is `[1.25, 1.60, 2.00, 2.50, 3.20, 4.00, 5.00, 6.40, 8.00]`. No second wave or outcome-adaptive extension is authorized.

The G-W/G-H/G-S strata are generation priors only. Ground-truth classes come solely from independent finite-step reference evaluations.

## Independent probability reference

The M1-D frozen reference contains only S2-S4 missing-mode views and therefore cannot serve as `p_ref_full`. M3-D2 uses a dedicated direct target Monte Carlo stream for each frozen configuration: one million independent `N(0,I_2)` draws, classified into S0-S4 using the frozen `BenchmarkConfig.label`. A configuration-level reference is shared by its state arms because the target law and event definition do not depend on the proposal covariance.

Every arm must agree with that reference and every other arm within the frozen four-standard-error gate. Failure makes the state `REFERENCE_INVALID`; references are never swapped.

## Discovery and confirmation

Discovery uses 100,000 samples per arm and confirmation uses 500,000 per arm, in 20 paired CRN batches. The two stages use disjoint seed namespaces. Discovery selects at most 12 candidates per target class using the frozen certainty, diversity and tie-breaking rules. Confirmation alone establishes the final class.

## Deterministic balance and stop rule

The final selector requires at least eight confirmed valid states in each of WIDEN, HOLD and SHRINK. It then selects exactly eight per class under the frozen certainty/diversity rule. If any class or diversity requirement fails, the verdict is D2-B; the target is not reduced and no states are added.

## Firewall

No controller module, controller seed, M3-G trial, BV/BV2/CA/PF/M3-Q/M5-AR stage, or controller-informed selection is authorized. M3-D2 stops after benchmark freeze or a D2-B/C/D verdict.

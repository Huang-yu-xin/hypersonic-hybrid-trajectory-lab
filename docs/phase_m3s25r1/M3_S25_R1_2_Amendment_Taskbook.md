# M3-S25-R1.2 Structural-Invariant Amendment Taskbook

> **Provenance.** This file is the frozen M3-S25-R1.2 amendment taskbook,
> transcribed from the human-issued instruction text received 2026-09-06.
> It is the authoritative amendment document; the machine-executable
> application lives in `configs/phase_m3s25r1/m3s25r1_contract.json`
> (structural-invariant definition update),
> `results/phase_m3s25r1/preflight/` (zero-sampling validation, with the
> R1.1 BLOCKED report preserved as historical evidence) and
> `docs/phase_m3s25r1/M3_S25_R1_2_Amendment_Record.md`, all hash-locked by
> `configs/phase_m3s25r1/m3s25r1_hash_manifest.json`.

---

Create M3-S25-R1.2 as a ZERO-SAMPLING structural-invariant amendment.

Parent: M3-S25-R1.1 at commit `37553a207d96b2edcc827595f0b711e392c4358f`.

Do not change the frozen candidate universe, universe SHA, candidate
generation, hash ranking, freshness rules, legality, seeds, truth
semantics, budget, runtime ordering, panel rules, or any authorization
gate.

The R1.1 preflight BLOCKED result is valid and must remain preserved as
historical evidence.

Replace the R1.1 support thresholds with generator-derived structural
invariants computed directly from the frozen constants:

```
U_LO = 0.15
U_HI = 1.00
N_STRATA = 8
L_ANCHORS = 65
```

Let:

```
w = (U_HI-U_LO)/N_STRATA

u0_max = U_LO + L_ANCHORS/(L_ANCHORS+1) * w

u7_min = U_LO + 7*w + 1/(L_ANCHORS+1) * w
```

Freeze:

A:
each config occupies all 8 strata exactly once.

B:
`min(u) <= u0_max + tol`

where
`u0_max = 0.2546401515151515`.

C:
`max(u) >= u7_min - tol`

where
`u7_min = 0.8953598484848485`.

D:
`span >= (u7_min-u0_max) - tol`

where
`u7_min-u0_max = 0.640719696969697`.

Use a frozen numerical tolerance such as `1e-12`.

The implementation must compute these values from the frozen generator
constants rather than treating the decimal values as independently
tunable scientific thresholds.

Rationale:
R1.1 correctly identified that support invariants must test structural
coverage rather than luck in the hash-first anchor position. `B<=0.25`
remained stricter than the generator guarantee, and `D>=0.65` also
remained slightly stricter than the deterministic extreme-stratum
interior-anchor guarantee. R1.2 removes the remaining random-hash
dependence.

Run zero-sampling preflight against the exact existing 240-state
universe. Verify:

* universe byte SHA unchanged;
* 240 states / 30 configs / 8 strata unchanged;
* A/B/C/D all PASS;
* freshness unchanged;
* truth semantics hash unchanged;
* seed manifests unchanged;
* budget remains 432,000,000;
* simulator calls = 0;
* samples = 0.

Add regression tests proving the structural bounds are derived from the
generator constants and that changing realized frozen candidate values
is not used to tune the thresholds.

Keep:

```
M3_S25_R1_TRUTH_AUTHORIZED: NO
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
```

and keep VALUE / RARITY / M3-Q BLOCKED.

Commit and push as a new amendment without squashing R1.0 or R1.1
history, verify local HEAD == remote HEAD, then STOP for human audit.

# M3-DS Safety Axis Audit (DS-2)

Zero-simulator by default. The Safety Axis is not a balanced "ABSTAIN
class"; it measures whether a future policy safely chooses BASE / no
adaptation when reference evidence does not support a stable directional
deployment.

## Candidate types considered

| type | source | count | role in M3-DS |
|---|---|---|---|
| H - independently confirmed HOLD | D2 confirmation | 3 | safety primary |
| A - independently confirmed AMBIGUOUS | D2 confirmation | 2 | safety primary |
| D3-Amb - D3 discovery ambiguous | D3 discovery | 10 | challenge candidates only; NOT frozen primary |

D3-Amb states are not independently confirmed and are therefore excluded
from the frozen primary safety reference.

## Primary safety axis (zero-sim freeze)

```text
confirmed HOLD      = 3 : c001_s2_00400, c007_s2_00125, c010_s2_00500
confirmed AMBIGUOUS = 2 : c006_s2_00125, c006_s2_00800
total               = 5 independently confirmed reference safety states
```

Machine record: `results/phase_m3ds/summary/m3ds_safety_primary.csv`.

## Semantics firewall

- Reference statuses `HOLD` / `AMBIGUOUS` are preserved verbatim.
- Historical HOLD is NOT renamed into an ABSTAIN truth class.
- ABSTAIN is a protocol action with fallback = BASE, not a supervised label.
- There is no quota such as "need >= 8 ABSTAIN"; the axis only needs
  predeclared low-confidence / no-direction reference states.

## Future metrics (defined here, executed only in M3-G2)

```text
A_safe       = #ABSTAIN on safety states / N_safety
U_safe       = #(W/S deployed on safety states) / N_safety
               (reported separately for confirmed HOLD vs AMBIGUOUS)
R_wrong      = (#(W truth -> SHRINK) + #(S truth -> WIDEN)) / N_directional
C_dir        = #non-abstained directional / N_directional
Acc_selective = P(correct direction | not abstained)
```

ABSTAIN is never wrong-direction, but it lowers coverage, so a policy cannot
win by abstaining on everything. No single three-class
W/S/ABSTAIN accuracy is permitted.

## DS-3 decision

Optional independent confirmation of the 10 D3 ambiguous states is
**NOT REQUIRED** for the primary M3-DS freeze (human-approved default):
the 16-state directional primary plus 5-state independently confirmed
safety primary suffice for benchmark v0. DS-3 may later be separately
preregistered (500k/arm, 20 paired CRN batches, same corrected classifier,
independent seed namespace) without touching the directional axis.

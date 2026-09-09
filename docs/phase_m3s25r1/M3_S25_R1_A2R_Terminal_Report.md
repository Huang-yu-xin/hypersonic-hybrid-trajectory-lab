# M3-S25-R1 A2R Terminal Report — M3-S25-R1-A2R-B-GATE

Recorded 2026-09-08.  A2R Arm-A execution under the A2R authorization
(Human, 2026-09-08; authorization commit `2317287`; pre-execution
verification ALL PASS).

## What happened

`python scripts/run_m3s25r1.py arm_a2r_execute` ran 691 new trials to
durable COMPLETE with **0 CONSUMED_INVALID**.  The bounded directory-
fsync retry (5 attempts, deterministic backoff) succeeded on all 691
trials — the Windows sharing-violation failure that terminated A1R at
trial 270 did not recur.

```text
M3-S25-R1-A2R terminus: M3-S25-R1-A2R-B-GATE
new trials COMPLETE      = 691 / 691
CONSUMED_INVALID         = 0
inherited (A1R)          = 269 (re-verified durable COMPLETE)
effective trials         = 960
new samples              = 13,820,000 (691 x 20,000)
effective samples        = 19,200,000 (960 x 20,000)
cumulative project       = 19,240,000 (old Arm-A 20k + A1R 20k + A2R 19.2M)
```

## Evaluation

`python scripts/run_m3s25r1.py arm_a2r_evaluate` unsealed the truth
manifest after 960/960 completeness (0 CONSUMED_INVALID) and ran the
frozen B0/B1/A1-A4 comparison on 269 inherited + 691 new = 960 records.

```text
VERDICT = M3-S25-R1-A2R-B-GATE
truth_manifest_unsealed = True (after 960 complete)
truth_manifest_sha256 = 75f5993bc6a251220e5e533f0b96de153bcef313d95706e6e0b7294db57af880
n_trials = 960
```

No A-model met the frozen success criterion (coverage gain, unsafe
reduction, or practical margin).  The stage terminates at the B-GATE.

## What was NOT done

- Arm B was NOT executed (`M3_S25_R1_A2R_ARM_B_AUTHORIZED` remains NO).
- Truth remains CLOSED/EXERCISED.  VALUE/RARITY/M3-Q remain BLOCKED.
- No replay, no top-up, no substitution.

## Gate closure

```text
M3_S25_R1_A2R_ARM_A_AUTHORIZED = NO
status = CLOSED / EXERCISED / B-GATE
terminal = M3-S25-R1-A2R-B-GATE
authorization HEAD = 2317287bb9fb03cf2928ded7eeb14b1109593df2
```

All other gates remain NO.  STOP for human post-A2R audit.

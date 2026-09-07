# M3-S25-R1 Arm-A Incident Report -- Terminal M3-S25-R1-X

Recorded 2026-09-07.  Execution under the Arm-A authorization (Human,
2026-09-06; authorization commit `d3116d2`; pre-execution verification
ALL PASS including all five frozen SHAs, clean destination, restart scan
960/960 FRESH).

## What happened

`python scripts/run_m3s25r1.py arm_a_execute` STOPPED on the FIRST trial.

- Unit: `m3s2s_cfg_001_s2s_0.5708962241|rep0` (the canonical first trial).
- Durable ledger: exactly one STARTED (13:47:47+0800) + exactly one
  CONSUMED_INVALID; no record file, no sidecar.
- Scientific samples consumed: 20,000 (one online pilot draw; the frozen
  estimator consumes the passed sample arrays, it does not re-draw).
- Remaining 959 units: never started (FRESH).
- No further execution was attempted.  Per the frozen persistence rule
  (sampling without durable COMPLETE => CONSUMED_INVALID => M3-S25-R1-X
  => STOP => NO REPLAY), the stage is TERMINAL:

```text
M3-S25-R1 Arm-A terminus: M3-S25-R1-X (integrity failure)
trials COMPLETE          = 0 / 960
CONSUMED_INVALID         = 1
actual samples consumed  = 20,000  (of the authorized 19,200,000)
```

## Root cause (fully diagnosed; the estimator is NOT at fault)

The trial's instrumentation capture re-executed the frozen bootstrap to
capture the lossless replicate array and computed the CI bounds itself
with `np.quantile(good, 0.025)`.  The frozen
`stratified_bootstrap_gradient_ci` computes
`tail = (1 - 0.95) / 2.0 = 0.025000000000000022` -- a 1-ULP different
quantile argument.  On bit-identical replicate arrays this yields a
1-ULP different `g_ci_low` (-0.2979840670496266 vs
-0.29798406704962654), which tripped the bit-exact crosscheck.

Diagnostics performed (all zero-sampling, test-local or captured
in-process):

- the building blocks are bit-deterministic across calls and across
  processes (a_vec / replicate arrays hash-identical in independent
  runs);
- the captured replicate arrays are bit-identical to the frozen
  function's internal ones (element-for-element);
- the ONLY difference was the quantile argument.  The unmodified
  estimator is bit-exact throughout; the defect was in MY capture code,
  not in the inherited machinery.

## Engineering fix applied (for any FUTURE re-authorized stage)

`arm_a.arm_a_trial` now takes the CI bounds from the FROZEN
`stratified_bootstrap_gradient_ci` itself (bit-identical to
`gradient_decision`'s internal call by construction); the capture loop
remains solely the sidecar's replicate recorder (bit-identical arrays,
proven by test).  The bit-exact crosscheck is unchanged and now passes
on a real state assembly (regression test with a test-local seed --
never a frozen manifest seed).

This fix does NOT enable replay: the consumed unit stays consumed, the
ledger entry stays, and the stage stays terminal per the frozen rules.

## Decision items for the human (NO self-authorization taken)

1. The Arm-A stage is terminal M3-S25-R1-X with 1 CONSUMED_INVALID
   unit; 959 units remain FRESH; 19,180,000 of the authorized samples
   were never touched.
2. Any continuation (e.g., an amendment defining the disposition of the
   single consumed unit and re-authorizing Arm A under the corrected
   instrumentation) requires a NEW human amendment/taskbook per the
   stage's rule that rule changes and re-entry are human decisions.
3. `M3_S25_R1_ARM_A_AUTHORIZED` remains YES as granted; the gate is
   NOT modified by this report (the runtime refuses: the restart scan
   fails closed on the CONSUMED_INVALID ledger state before any
   simulator call).

## Gates

```text
M3_S25_R1_TRUTH_AUTHORIZED = NO   (CLOSED / EXERCISED)
M3_S25_R1_ARM_A_AUTHORIZED = YES  (as granted; runtime fail-closed on
                                   the consumed unit)
M3_S25_R1_ARM_B_AUTHORIZED = NO   (never executed)
VALUE / RARITY / M3-Q      = BLOCKED
```

STOP.

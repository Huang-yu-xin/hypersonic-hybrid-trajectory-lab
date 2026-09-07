# M3-S25-R1 A1R Incident Report -- Terminal M3-S25-R1-A1R-X

Recorded 2026-09-07.  Replacement execution under the A1R Arm-A
authorization (Human, 2026-09-07; authorization commit `8deed16`;
pre-execution verification ALL PASS including all five frozen SHAs,
clean destination, restart scan 960 FRESH / 0 COMPLETE, old ledger
/ incident-report / old seed-manifest runtime pins).

## What happened

`python scripts/run_m3s25r1.py arm_a1r_execute` STOPPED at trial 270
of 960.

- Unit: `c020_s25r1_3.8634000847|rep5` (the 6th replicate of the
  34th panel state, config `c020`).
- The trial consumed 20,000 scientific samples (the online pilot draw
  ran to completion and produced a valid record + sidecar arrays).
- The transactional sidecar write succeeded: atomic rename completed
  (`final_exists: True`, `temp_leftover: False`).
- The **parent-directory fsync** (the fail-closed step added by the
  A0.2 micro-amendment) FAILED: `FlushFileBuffers(FILE_FLAG_BACKUP_-
  SEMANTICS)` returned Windows error 32 (ERROR_SHARING_VIOLATION:
  `[Errno 32] CreateFileW(directory) failed`).
- Per the frozen persistence rule (parent-dir fsync is mandatory;
  `dir_sync['pass']` required after atomic rename), the trial was
  declared **CONSUMED_INVALID** -- sampling occurred without durable
  COMPLETE.
- The script raised `RuntimeError: M3-S25-R1-A1R-X: trial not
  durably COMPLETE` and exited (exit code 1).
- No further execution was attempted.  Per the frozen persistence rule
  (sampling without durable COMPLETE => CONSUMED_INVALID =>
  M3-S25-R1-A1R-X => STOP => NO REPLAY), the stage is TERMINAL:

```text
M3-S25-R1 A1R terminus: M3-S25-R1-A1R-X (integrity failure)
trials COMPLETE           = 269 / 960
CONSUMED_INVALID          = 1
units FRESH (never started) = 690
actual replacement samples  = 5,380,000  (269 x 20,000, COMPLETE)
replacement invalid samples = 20,000     (1 x 20,000, CONSUMED_INVALID)
old invalid samples (separate) = 20,000  (old Arm-A incident)
cumulative Arm-A project consumption = 5,420,000
```

## Durable ledger state

- A1R ledger path: `results/phase_m3s25r1/arm_a1r/trial_ledger.jsonl`
- A1R ledger SHA-256:
  `0ad71e8b620cfda98ee1811a26d517a398d00d72513c98453281327059d528f7`
- Ledger entries: 540 total (270 STARTED + 269 COMPLETE +
  1 CONSUMED_INVALID); every started trial was resolved (no
  dangling STARTED).
- 269 durable COMPLETE trial records + 269 sidecar `.npz` files
  preserved in `results/phase_m3s25r1/arm_a1r/trials/`.
- The CONSUMED_INVALID unit's record file exists on disk
  (`final_exists: True`) but is NOT durably committed and must
  never enter the replacement dataset, features, CV, metrics, or
  verdict.

## Trial breakdown

- 33 panel states fully complete (all 8 reps each) = 264 trials.
- 34th panel state (`c020_s25r1_3.8634000847`): reps 0-4 COMPLETE
  (5 trials), rep5 CONSUMED_INVALID (1 trial), reps 6-7 FRESH (never
  started).
- Remaining 86 panel states: all FRESH (never started) = 688 units.
- Total: 264 + 5 = 269 COMPLETE; 1 CONSUMED_INVALID;
  690 FRESH (688 + 2).

## Root cause (OS-level transient I/O; NOT a scientific-code defect)

The fail-closed parent-directory fsync (added by the A0.2
micro-amendment; `dir_sync['pass']` required after atomic rename)
invokes `FlushFileBuffers` on the parent directory via
`CreateFileW(directory, FILE_FLAG_BACKUP_SEMANTICS)`.  On the 270th
trial, Windows returned error 32 (`ERROR_SHARING_VIOLATION`):
another process held the directory handle with incompatible sharing
(the most likely culprits on Windows are the Search Indexer, an
antivirus scan of the newly written files, or a file-system filter
driver).

Key observations:

1. The first 269 trials' parent-dir fsync operations ALL succeeded --
   the failure is transient/intermittent, not systematic.
2. The trial's record file and sidecar were fully written
   (`final_exists: True`, `temp_leftover: False`); the atomic rename
   succeeded.  Only the subsequent parent-dir fsync failed.
3. The frozen persistence rule is **working as designed**: any
   sampling without durable COMPLETE (including a parent-dir fsync
   failure) => CONSUMED_INVALID => terminal X => STOP => NO REPLAY.
   The fail-closed policy correctly caught a real durability gap
   that a lenient (fsync-optional) policy would have silently
   swallowed.
4. The frozen estimator, the bootstrap CI instrumentation fix, the
   bit-exact crosscheck, the seed manifest, the retired-stream
   exclusion, and all frozen SHAs are NOT at fault.  No scientific
   code, contract, panel, truth manifest, seed, model/CV rule, or
   budget was modified.

## What was NOT done (per the frozen protocol)

- `arm_a1r_evaluate` was NOT run.  The post-execution conditions
  (960/960 durable COMPLETE, 0 CONSUMED_INVALID, exactly
  19,200,000 replacement samples) are NOT met.  The truth manifest
  remains sealed.
- Arm B was NOT executed.  `M3_S25_R1_A1R_ARM_B_AUTHORIZED` remains
  NO; `M3_S25_R1_ARM_B_AUTHORIZED` remains NO.
- No replay, no continuation, no top-up, no single-unit substitution
  was attempted (all forbidden by the frozen persistence rule).

## Gate closure

The replacement Arm-A authorization gate was exercised exactly once
(Human, 2026-09-07; commit `8deed16`; flipped `M3_S25_R1_A1R_ARM_A_-
AUTHORIZED: NO -> YES`) and is now CLOSED:

```text
M3_S25_R1_A1R_ARM_A_AUTHORIZED = NO
status = CLOSED / EXERCISED / TERMINAL-X
terminal = M3-S25-R1-A1R-X
authorization HEAD = 8deed164c0c830790aaea5481cc3eec898ea79b8
execution timestamp = 2026-09-07T20:28:36+0800
```

All other gates remain NO:
`M3_S25_R1_TRUTH_AUTHORIZED` (CLOSED/EXERCISED),
`M3_S25_R1_ARM_A_AUTHORIZED` (CLOSED/EXERCISED/TERMINAL-X),
`M3_S25_R1_ARM_B_AUTHORIZED` (NO),
`M3_S25_R1_A1R_ARM_B_AUTHORIZED` (NO).
VALUE / RARITY / M3-Q remain BLOCKED.

## STOP for human post-A1R audit

The stage is TERMINAL `M3-S25-R1-A1R-X`.  No further automated
action is permitted.  A human post-A1R audit is required to
determine whether a new replacement stage (with its own independent
preregistration, gates, and authorization) may be authorized.

The 269 durable COMPLETE trial records are scientifically valid and
preserved.  They may NOT be reused, repackaged, or counted toward
any future stage's completeness without a new preregistered stage
that explicitly inherits them (if the human auditor permits).

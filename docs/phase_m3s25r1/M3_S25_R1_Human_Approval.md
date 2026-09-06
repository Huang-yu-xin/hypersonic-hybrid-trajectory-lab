# M3-S25-R1 Human Approval

Three independent authorization gates with NEW gate names (taskbook Sec. 3).
Codex / scripts / tests / preflight must not change any NO to YES.  The old
M3-S2S T1 gate is CLOSED (see `docs/phase_m3s2s/M3_S2S_Closure_Record.md`)
and may not be reused for any R1 activity.

```text
M3_S25_R1_TRUTH_AUTHORIZED: NO
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
AUTHORIZER: (awaiting explicit gate-by-gate human authorization)
AUTHORIZATION_DATE: (not yet granted)
```

Gate semantics (taskbook Sec. 21/29):

- Round 0 is preregistration-only: candidate generation, freshness/support
  audits, P_ref source audit, seed manifest, budget contract, runtime
  implementation, tests, preflight, hash-lock, docs, commit, push, STOP.
  Scientific simulator calls = 0 and samples = 0 in Round 0.
- `M3_S25_R1_TRUTH_AUTHORIZED` may be set to YES by the human ONLY after an
  execution-readiness audit of the frozen artifacts.  The single truth
  command is `python scripts/run_m3s25r1.py truth_execute`; it runs 240
  discovery + 240 confirmation under planned = max = 432,000,000 samples,
  no top-up, no candidate substitution, then truth assignment + exposed
  inventory + union development pool + panel freeze (or
  M3-S25-R1-PANEL-BLOCKED) and STOP.
- Arm A requires a separate post-truth / post-panel audit plus an explicit
  `M3_S25_R1_ARM_A_AUTHORIZED: YES` commit.  Arm B is never authorized
  simultaneously with Arm A.  VALUE / RARITY / M3-Q remain BLOCKED.
- Any durable-persistence failure after sampling starts => M3-S25-R1-X =>
  STOP => NO REPLAY.  Any preflight/regression-invariant failure before
  authorization keeps every gate NO and stops the stage for adjudication.

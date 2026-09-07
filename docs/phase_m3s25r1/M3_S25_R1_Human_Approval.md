# M3-S25-R1 Human Approval

Three independent authorization gates with NEW gate names (taskbook Sec. 3).
Codex / scripts / tests / preflight must not change any NO to YES.  The old
M3-S2S T1 gate is CLOSED (see `docs/phase_m3s2s/M3_S2S_Closure_Record.md`)
and may not be reused for any R1 activity.

```text
M3_S25_R1_TRUTH_AUTHORIZED: NO
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
AUTHORIZER: Human
AUTHORIZATION_DATE: 2026-09-06 (T1 exercised 2026-09-06; closed at A0)
```

## Truth gate closure record (M3-S25-R1-A0, closure-only, 2026-09-06)

```text
M3_S25_R1_TRUTH_AUTHORIZED = NO
status = CLOSED / EXERCISED
truth terminal HEAD = 089c6a48c73831fbd95e2caa5b21137b485080aa
```

- The M3-S25-R1.2 truth authorization was exercised exactly once
  (480/480 durable COMPLETE, exact 432,000,000 samples, 0
  CONSUMED_INVALID, terminal M3-S25-R1-PANEL-FROZEN) and is now
  permanently NO: no truth re-run, no top-up, no replay under M3-S25-R1.
  This closure prevents accidental truth re-entry during the A0 / Arm-A
  stages.  Any further truth sampling requires a NEW preregistered stage
  with its own approval file and gate names.
- `M3_S25_R1_ARM_A_AUTHORIZED` and `M3_S25_R1_ARM_B_AUTHORIZED` remain
  NO.  VALUE / RARITY / M3-Q remain BLOCKED.

## T1 authorization record (Truth Gate ONLY, M3-S25-R1.2)

- M3-S25-R1.2 execution-readiness live audit: **PASS** (human, 2026-09-06).
- Explicit human authorization: "M3-S25-R1.2 execution-readiness live
  audit: PASS.  Human authorization is granted for the Truth Gate ONLY."
- Scope: the frozen truth streams ONLY -- discovery for all 240 frozen
  candidate states (3 x 100,000 = 72,000,000) and confirmation for all 240
  states (3 x 500,000 = 360,000,000); P_ref sampling = 0 (reuse registry);
  planned = max = 432,000,000; early_stop = false; topup = 0; candidate
  substitution = false.  After 480/480 durable COMPLETE the frozen truth /
  exposed-inventory / union-pool / panel-selection logic runs (FROZEN
  120-state panel or M3-S25-R1-PANEL-BLOCKED), then STOP.  Persistence
  rules strict: STARTED before simulator; any consumed unit without a
  durable COMPLETE => CONSUMED_INVALID => M3-S25-R1-X => STOP => NO REPLAY.
- Frozen at authorization: candidate universe SHA
  `9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`;
  contract SHA
  `96585379805a2cc5f390f37b3563357123de497c2df05b58eb5f6efe166fab98`
  (branch base `55e4c5358281a58472263cfe3c723b45c012b2c1`).
- `M3_S25_R1_ARM_A_AUTHORIZED` and `M3_S25_R1_ARM_B_AUTHORIZED` remain NO;
  no Arm A or Arm B activity is authorized.  VALUE / RARITY / M3-Q remain
  BLOCKED.

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

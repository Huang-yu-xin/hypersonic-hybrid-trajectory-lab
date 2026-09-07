# M3-S25-R1 Human Approval

Three independent authorization gates with NEW gate names (taskbook Sec. 3).
Codex / scripts / tests / preflight must not change any NO to YES.  The old
M3-S2S T1 gate is CLOSED (see `docs/phase_m3s2s/M3_S2S_Closure_Record.md`)
and may not be reused for any R1 activity.

```text
M3_S25_R1_TRUTH_AUTHORIZED: NO
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
M3_S25_R1_A1R_ARM_A_AUTHORIZED: YES
M3_S25_R1_A1R_ARM_B_AUTHORIZED: NO
AUTHORIZER: Human
AUTHORIZATION_DATE: 2026-09-06 (T1 exercised 2026-09-06; closed at A0;
                             Arm-A authorized 2026-09-06; CLOSED at A1R0)
```

## Old Arm-A gate closure record (M3-S25-R1-A1R0, closure-only, 2026-09-07)

```text
M3_S25_R1_ARM_A_AUTHORIZED = NO
status = CLOSED / EXERCISED / TERMINAL-X
terminal HEAD = 73e91823fc562a8b5be65a86fa6f1e2a01803d42
```

- The original Arm-A authorization (Human, 2026-09-06; commit `d3116d2`)
  was exercised exactly once and terminated on the first trial: unit
  `m3s2s_cfg_001_s2s_0.5708962241|rep0` CONSUMED_INVALID (20,000 samples
  consumed; 959 units never started) => the stage is PERMANENTLY
  TERMINAL `M3-S25-R1-X`.  No replay, continuation, top-up, or
  single-unit substitution is permitted.  The original authorization
  record and the incident history below are PRESERVED verbatim.
- The failed stream is retired as evidence
  (`configs/phase_m3s25r1/m3s25r1_a1r_retired_stream.json`): no old
  Arm-A unit or seed may appear in the replacement stage A1R.
- The replacement stage is M3-S25-R1-A1R with its own independent gates
  (`M3_S25_R1_A1R_ARM_A_AUTHORIZED` / `M3_S25_R1_A1R_ARM_B_AUTHORIZED`,
  both NO; Codex/tests/scripts may never self-flip them).
- TRUTH remains CLOSED / NO.  VALUE / RARITY / M3-Q remain BLOCKED.

## Arm-A authorization record (ARM A ONLY, 2026-09-06)

- M3-S25-R1-A0.2 final execution-readiness audit: **PASS** (human,
  2026-09-06).
- Explicit human authorization: "Human authorization is granted for ARM
  A ONLY."
- Scope: `python scripts/run_m3s25r1.py arm_a_execute` ONLY -- 120
  states x 8 replicates x 20,000 samples = 960 trials = exact
  19,200,000 samples, top-up = 0; strict persistence (STARTED before
  simulator; any sampling without durable COMPLETE => CONSUMED_INVALID
  => M3-S25-R1-X => STOP => NO REPLAY); after exactly 960/960 durable
  COMPLETE with CONSUMED_INVALID = 0, the frozen zero-sampling
  evaluation (`arm_a_evaluate`) may run, unsealing the truth manifest
  only after completeness; accept only the frozen terminal verdict
  (`M3-S25-R1-A` / `M3-S25-R1-B-GATE` / `M3-S25-R1-X`).
- Frozen at authorization: panel body SHA `2bdb9a91...`, panel file SHA
  `136830a2...`, truth manifest SHA `75f5993b...`, Arm-A contract SHA
  `f02fc399...`, Arm-A seed manifest SHA `20cbe999...`, branch base
  `4a335baf4c7449cdc41552c56e1379c048086a22`.
- **DO NOT execute Arm B.**  `M3_S25_R1_ARM_B_AUTHORIZED` remains NO;
  Arm B is never authorized simultaneously with Arm A.  VALUE / RARITY /
  M3-Q remain BLOCKED.  Truth remains CLOSED / EXERCISED.

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

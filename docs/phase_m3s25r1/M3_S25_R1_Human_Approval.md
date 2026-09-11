# M3-S25-R1 Human Approval

Three independent authorization gates with NEW gate names (taskbook Sec. 3).
Codex / scripts / tests / preflight must not change any NO to YES.  The old
M3-S2S T1 gate is CLOSED (see `docs/phase_m3s2s/M3_S2S_Closure_Record.md`)
and may not be reused for any R1 activity.

```text
M3_S25_R1_TRUTH_AUTHORIZED: NO
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
M3_S25_R1_A1R_ARM_A_AUTHORIZED: NO
M3_S25_R1_A1R_ARM_B_AUTHORIZED: NO
M3_S25_R1_A2R_ARM_A_AUTHORIZED: NO
M3_S25_R1_A2R_ARM_B_AUTHORIZED: NO
AUTHORIZER: Human
AUTHORIZATION_DATE: 2026-09-06 (T1 exercised 2026-09-06; closed at A0;
                             Arm-A authorized 2026-09-06; CLOSED at A1R0;
                             A1R Arm-A authorized 2026-09-07; CLOSED at
                             A1R terminal X 2026-09-07;
                             A2R0 preregistration 2026-09-07;
                             A2R Arm-A authorized 2026-09-08; CLOSED at
                             A2R B-GATE 2026-09-08;
                             A2R Arm-B authorized 2026-09-09; WITHDRAWN
                             to NO on 2026-09-09 -- see the withdrawal
                             record below; NOT exercised; 0 samples)
```

## A2R Arm-B gate WITHDRAWAL record (2026-09-09, zero sampling)

```text
M3_S25_R1_A2R_ARM_B_AUTHORIZED = NO   (YES -> NO, 2026-09-09)
status = WITHDRAWN / NOT EXERCISED / zero samples
authorization HEAD = 3f866942df16c1e2592cdbf2b7a237144c14bedb
simulator calls = 0; scientific samples = 0; B0 ledger = absent
```

Human authorization for A2R Arm-B execution (2026-09-09, commit
`3f86694`) was presented for execution.  The pre-sampling frozen gates
ran and **PASSED**:

- `B0 center artifacts verified: PASS (269 inherited + 691 A2R = 960
  centers, effective_samples=19200000)`
- `B0 runtime plan verified: PASS` (manifest SHA pin, 1920 -> 960 L/R
  CRN-anchor topology, Delta = 0.10 frozen)

The runner then aborted inside the side-trial loop **BEFORE the first
scientific simulator call** on three mechanical wiring defects in
`scripts/run_m3s25r1.py::arm_b_execute` (none of them scientific --
no Delta, seed, sample count, CRN semantics, feature, model, CV or
threshold was involved):

1. `math` is never imported, but the loop calls `math.exp(-AB.DELTA)`
   at line 4037 => `NameError` while computing `s2_side`.
2. The `run_trial_transactional(...)` call passes 5 positional
   arguments against the signature `(logical_id, final_path,
   run_simulator, *, ledger_path, pre_hash_validator, ...)` =>
   `TypeError: too many positional arguments`.  The proven A2R route
   uses the keyword form.
3. Even with (1) and (2) repaired, the route omits the mandatory
   `pre_hash_validator` (schema / namespace / seed / sidecar-hash /
   truth-leak checks), returns a `(record, arrays)` tuple where a dict
   payload is required, and never writes the instrumentation sidecar,
   so `instrumentation_sha256` would stay null.

No sample was consumed and nothing was persisted: the B0 trial ledger
does not exist, `results/phase_m3s25r1/arm_b/trials` contains 0 files,
and the 960-center / 19,200,000-sample effective center dataset was
never opened for writing (A2R 691 and A1R 270 records unchanged).
Therefore this is NOT a CONSUMED_INVALID and NOT a terminal
`M3-S25-R1-A2R-X`; the authorization was **not exercised**.

Root cause of the escape: every `arm_b_execute` test was an
`inspect.getsource()` source-text assertion; the trial loop was never
actually executed under test, so the wiring was never exercised.

Disposition: the gate is returned to NO so the defects are repaired by
a zero-sampling amendment (matching the B0.4.1 / B0.4.2 / B0.4.3
precedent) with a real-path test, then re-audited and re-authorized.
TRUTH remains CLOSED / NO.  VALUE / RARITY / M3-Q remain BLOCKED.
Arm-B evaluation was NOT run.

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

## A1R replacement Arm-A gate closure record (M3-S25-R1-A1R, closure-only, 2026-09-07)

```text
M3_S25_R1_A1R_ARM_A_AUTHORIZED = NO
status = CLOSED / EXERCISED / TERMINAL-X
terminal = M3-S25-R1-A1R-X
authorization HEAD = 8deed164c0c830790aaea5481cc3eec898ea79b8
```

- The replacement Arm-A authorization (Human, 2026-09-07; commit
  `8deed16`; pre-execution verification ALL PASS) was exercised
  exactly once and terminated at trial 270 of 960: unit
  `c020_s25r1_3.8634000847|rep5` CONSUMED_INVALID (20,000 samples
  consumed; parent-directory fsync failed with Windows error 32;
  269/960 durable COMPLETE; 690 units FRESH) => the replacement
  stage is PERMANENTLY TERMINAL `M3-S25-R1-A1R-X`.  No replay,
  continuation, top-up, or single-unit substitution is permitted.
- The 269 durable COMPLETE trial records are scientifically valid
  and preserved on disk but may NOT enter any future stage's
  dataset, features, CV, metrics, or verdict without a new
  preregistered stage that explicitly inherits them.
- `arm_a1r_evaluate` was NOT run (post-execution conditions not
  met: 269/960, 1 CONSUMED_INVALID).  The truth manifest remains
  sealed.  Arm B was NOT executed.
- Full incident report: `docs/phase_m3s25r1/M3_S25_R1_A1R_Incident_
  Report.md`.  A1R ledger SHA-256:
  `0ad71e8b620cfda98ee1811a26d517a398d00d72513c98453281327059d528f7`.
- TRUTH remains CLOSED / NO.  VALUE / RARITY / M3-Q remain BLOCKED.
  STOP for human post-A1R audit.

## A2R Arm-A gate closure record (M3-S25-R1-A2R, closure-only, 2026-09-08)

```text
M3_S25_R1_A2R_ARM_A_AUTHORIZED = NO
status = CLOSED / EXERCISED / B-GATE
terminal = M3-S25-R1-A2R-B-GATE
authorization HEAD = 2317287bb9fb03cf2928ded7eeb14b1109593df2
```

- The A2R Arm-A authorization (Human, 2026-09-08; commit
  `2317287`) was exercised once: 691/691 new durable COMPLETE with
  0 CONSUMED_INVALID + 269 inherited verified = 960 effective trials /
  19,200,000 effective samples / 19,240,000 cumulative.  The bounded
  directory-fsync retry (5 attempts, deterministic backoff) succeeded
  on all 691 trials (the A1R Windows sharing-violation failure did
  not recur).
- The frozen B0/B1/A1-A4 evaluation unsealed the truth manifest after
  960/960 completeness and produced terminal `M3-S25-R1-A2R-B-GATE`
  (no A-model met the frozen success criterion; the stage terminates
  at the B-GATE, not A or X).
- Arm B was NOT executed.  Truth remains CLOSED/EXERCISED.  VALUE /
  RARITY / M3-Q remain BLOCKED.
- Evaluation: `results/phase_m3s25r1/summary/m3s25r1_a2r_evaluation.json`
- A2R ledger SHA: see consumption summary.
- STOP for human post-A2R audit.

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

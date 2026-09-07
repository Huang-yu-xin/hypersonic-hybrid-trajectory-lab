# M3-S25-R1-A1R0 Taskbook & Record -- Replacement Arm-A Preregistration

> **Provenance.** Frozen from the human post-incident adjudication
> received 2026-09-07.  Parent terminal HEAD
> `73e91823fc562a8b5be65a86fa6f1e2a01803d42` (old Arm-A stage PERMANENTLY
> TERMINAL `M3-S25-R1-X`).  ZERO-SAMPLING stage: no scientific simulator
> call is authorized in A1R0.

## Old Arm-A gate closure (item 1)

```text
M3_S25_R1_ARM_A_AUTHORIZED = NO
status = CLOSED / EXERCISED / TERMINAL-X
terminal HEAD = 73e91823fc562a8b5be65a86fa6f1e2a01803d42
```

The original authorization and incident history are preserved verbatim in
`M3_S25_R1_Human_Approval.md`.  TRUTH remains CLOSED / NO.  ARM_B
remains NO.  VALUE / RARITY / M3-Q remain BLOCKED.

## Retired failed stream (item 2)

`configs/phase_m3s25r1/m3s25r1_a1r_retired_stream.json`
(sha `7a2010cedf7a5b75d46b427e3a10a45e60bff301c08777ebc9c14701392d8168`):
old Arm-A seed-manifest SHA, ALL 960 old logical units = RETIRED FROM
REPLACEMENT (enumerated with their old seed values), the consumed unit
`m3s2s_cfg_001_s2s_0.5708962241|rep0` (old seed value/key, exactly
20,000 consumed samples), 1 CONSUMED_INVALID, 0 COMPLETE, 959 never
started, incident-report SHA, old-ledger SHA.  Rule: no old Arm-A unit
or seed may appear in A1R.  The old ledger/artifacts are preserved
verbatim (never deleted or rewritten).

## Same frozen science (items 3/4)

Byte-identical inheritance by exact SHA: 120 panel states, panel body
SHA `2bdb9a91...`, panel file SHA `136830a2...`, sealed truth manifest
`75f5993b...`, estimator (unmodified `gradient_decision` + MANDATORY
bit-exact crosscheck), S1 threshold 5.4417199447782, feature families,
ML0 B1 comparator, model grids, GroupKFold(5)/(4), safety gates, success
criterion, Arm-B rules.  The corrected instrumentation (A0.2 incident
fix: CI bounds from the frozen `stratified_bootstrap_gradient_ci`;
replicate capture loop sidecar-only) is hash-locked
(`arm_a.py` / `arm_a_eval.py` bytes in
`m3s25r1_hash_manifest.json["scientific_code_hashes"]` and in the A1R
contract).  The old failed 20k realization is EXPOSED / CONSUMED_INVALID
and must never enter the replacement dataset, features, CV, metrics or
verdict.

## New 960-unit seed stream (item 5)

`configs/phase_m3s25r1/m3s25r1_a1r_seed_manifest.json`
(sha `067062d89f76486a...`), namespace `M3-S25-R1-A1R-GRAD`, 120 x 8 =
960 new logical units.  NONE of the original 960 Arm-A seed values is
reused (including the 959 never-started); zero collisions against the
retired stream, R1 truth seeds, S2S Arm-A/truth seeds, CF1N and all
recorded historical scientific streams (typed per-stream pools).  Frozen
before any scientific simulator call.

## Separate persistence (item 6)

`results/phase_m3s25r1/arm_a1r/` with a NEW ledger
(`trial_ledger.jsonl`).  The old Arm-A ledger is never reused,
truncated, ignored or reinterpreted (its SHA is pinned in the retired
record and re-verified at every preflight/execution).  Replacement
chain: STARTED -> 20k sampling -> transactional sidecar -> record hash ->
COMPLETE.  Any replacement consumed-invalid unit => `M3-S25-R1-A1R-X`
=> STOP => NO REPLAY.

## Replacement budget (item 7)

960 trials x 20,000 = replacement planned = max = 19,200,000; topup 0;
substitution 0.  Cumulative project consumption reported separately:
old invalid stage = 20,000; replacement planned = 19,200,000;
cumulative if replacement completes = 19,220,000.  The old 20,000 never
counts toward replacement completeness.

## Gates (item 8)

```text
M3_S25_R1_A1R_ARM_A_AUTHORIZED: NO
M3_S25_R1_A1R_ARM_B_AUTHORIZED: NO
```

New independent gates; Codex/tests/scripts may never self-flip them.

## Preflight (item 9): PASS 17/17

old stage terminal X; old Arm-A gate CLOSED; incident consumed unit
permanently retired; old 960 seed stream fully excluded; same panel /
truth manifest / scientific contracts; corrected instrumentation code
SHA; new 960 seeds unique and collision-free; replacement destination
empty; protected reserve untouched; evaluation truth remains sealed; new
Arm-A gate NO; Arm B NO; simulator calls = 0; scientific samples = 0.

## Evaluation protocol (item 10)

Only after a future separately authorized replacement execution reaches
960/960 COMPLETE, 0 CONSUMED_INVALID and exactly 19,200,000 replacement
samples may evaluation unseal the sealed truth manifest and run
B0/B1/A1-A4.  Replacement-local terminal names: `M3-S25-R1-A1R-A` /
`M3-S25-R1-A1R-B-GATE` / `M3-S25-R1-A1R-X`.

## Route tests (item 11): 15/15 green

old ledger cannot be resumed (restart scan fails closed on the consumed
unit); the old failed seed cannot be reused; any of the old 960 seeds in
the replacement stream causes a hard preflight failure; the new 960
mocked route completes (960/960, replacement 19,200,000, cumulative
19,220,000, namespaces all A1R); the old 20k is excluded from
replacement accounting/evaluation; truth remains sealed until
replacement 960/960; no Arm-B execution anywhere in A1R.

## Gates after A1R0

```text
M3_S25_R1_TRUTH_AUTHORIZED     = NO (CLOSED / EXERCISED)
M3_S25_R1_ARM_A_AUTHORIZED     = NO (CLOSED / EXERCISED / TERMINAL-X)
M3_S25_R1_ARM_B_AUTHORIZED     = NO
M3_S25_R1_A1R_ARM_A_AUTHORIZED = NO
M3_S25_R1_A1R_ARM_B_AUTHORIZED = NO
VALUE / RARITY / M3-Q          = BLOCKED
```

STOP.  Awaiting the fresh A1R execution-readiness audit; only an
explicit human `M3_S25_R1_A1R_ARM_A_AUTHORIZED: YES` commit enables
`python scripts/run_m3s25r1.py arm_a1r_execute`.


## A1R0.1 provenance amendment (zero sampling)

Applied per the human A1R0.1 instruction:

1. **Dedicated terminal-head binding**: a frozen
   `OLD_ARM_A_TERMINAL_HEAD = "73e91823fc562a8b5be65a86fa6f1e2a01803d42"`
   constant now binds A1R to the old Arm-A incident terminal (NOT the
   truth-terminal `089c6a48...`).  Used by the retired-stream
   `old_terminal_head`, the A1R contract `parent_terminal_head`, and the
   A1R preflight `parent_incident_head_ancestor` ancestry check.  The
   preflight mechanically requires the incident terminal HEAD to be an
   ancestor of the current HEAD.
2. **Runtime provenance SHA bindings**: `_verify_frozen_a1r_inputs()`
   now verifies (a) the current incident-report SHA == the retired
   stream's frozen `old_incident_report_sha256`; (b) the current old
   Arm-A ledger SHA == the retired stream's frozen
   `old_ledger_sha256_expected`; (c) the current old Arm-A seed-manifest
   SHA == the retired stream's frozen
   `old_arm_a_seed_manifest_sha256`.  Any mismatch => M3-S25-R1-A1R-X =>
   STOP before simulator.
3. **Trial-record namespace provenance**: `arm_a_trial` gains a
   `namespace` parameter (default `M3-S25-R1-A-GRAD`, preserving the old
   Arm-A behavior); the durable record carries
   `record["namespace"] = namespace`.  `arm_a1r_execute` passes
   `namespace=A1R_NAMESPACE` explicitly, and the pre-hash validator
   requires `payload["namespace"] == M3-S25-R1-A1R-GRAD`,
   `payload["seed"] == plan_seeds[unit_id]`, and the ledger's
   `seed_namespace == M3-S25-R1-A1R-GRAD`.  Route test proves all three
   agree (manifest / ledger / durable JSON).
4. **Retired-stream wording corrected** (A1R0.1 item 3): "logical
   unit_id slots intentionally repeat because A1R reruns the same frozen
   120 x 8 design; the forbidden reuse is old seed values, old seed
   keys, old artifacts and old scientific realizations/data -- never
   unit_id naming".  No seed values altered.
5. **Regenerated provenance artifacts** (only the affected ones):
   retired stream SHA `7e673af4...` (terminal HEAD + wording corrected);
   A1R contract SHA `fdf0c42d...` (parent_terminal_head + wording).
   Replacement seed manifest, panel, truth manifest, and the A0.2
   rebind contract are BYTE-IDENTICAL (verified).

Updated pins: A1R_RETIRED_PIN = `7e673af4...`;
A1R_CONTRACT_PIN = `fdf0c42d...`;
A1R_SEED_MANIFEST_PIN = `067062d8...` (unchanged).

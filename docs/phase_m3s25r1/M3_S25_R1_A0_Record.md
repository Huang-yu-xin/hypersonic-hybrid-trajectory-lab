# M3-S25-R1-A0 Record (Arm-A Rebind & Execution Readiness; zero sampling)

Parent truth terminal HEAD `089c6a48c73831fbd95e2caa5b21137b485080aa`
(M3-S25-R1-PANEL-FROZEN).  A0 added NO simulator calls and NO samples.

## Frozen artifacts (hash-pinned)

| artifact | sha256 |
|---|---|
| panel truth manifest (evaluation-only, SEALED) | `75f5993bc6a251220e5e533f0b96de153bcef313d95706e6e0b7294db57af880` |
| Arm-A rebind contract | `234c651654ffaaca32f32036befd4b4ea6038174dca7b80e78356f488d0f3570` |
| Arm-A seed manifest (960 units) | `20cbe999286df7c4664a53067a1796b7b1ce9da37eb5c42939e07a456b8bf30d` |

- Panel truth manifest: 120 states, 30/30/30/30, 30 configs, source mix
  R1 83 / S2S 37, all 30 SHRINK from M3-S25-R1; bound to panel body SHA
  `2bdb9a91...` and the exact `m3s25r1_panel.json` file SHA.  Mechanical
  verification PASS.  SEALED: never read during Arm-A sampling; unsealed
  only after 960/960 durable COMPLETE.
- Rebind (no scientific retuning): estimator
  `hyptraj.m3d.adaptation.gradient_decision` unmodified with a BIT-EXACT
  crosscheck enforced on every trial; alpha_p 0.5; S1 threshold
  5.4417199447782; 120 x 8 x 20,000 = 960 trials = 19,200,000 (no
  top-up); instrumentation m3s2s_instr_v1 (N_BOOTSTRAP 500; a_vec / resp
  / sq / strata / bootstrap_g sidecars); parent feature family, grouped
  nested-CV (outer GroupKFold(5) / inner GroupKFold(4), groups =
  config_id; no test-fold threshold/delta tuning), model family
  (B0 frozen S1, B1 aggregate GBDT, A1/A2 stability logistic/GBDT,
  A3/A4 stability+margin logistic/GBDT), parent safety gates
  (coverage >= 0.75, ND unsafe <= 0.20, wrong <= 0.05, AMBIGUOUS unsafe
  < 0.25) + frozen improvement criterion.  All 9 inherited parent
  contracts recorded by exact SHA256 inside the rebind contract.
- Seeds: new namespace `M3-S25-R1-A-GRAD`, 960 unique units, 0 duplicate
  seeds, 0 historical collision, 0 truth-stream collision.

## Preflight (arm_a_preflight): PASS 17/17

parent/truth-terminal HEAD ancestry, PANEL-FROZEN, frozen panel SHA,
manifest SHA + identity, 30 configs / 30-30-30-30, protected reserve 18
untouched, 960 seeds, zero collisions, destination empty, path/disk PASS
(exact production layout), GroupKFold(5)/(4) class/config feasibility
(24/6 configs per fold, all classes present), all inherited contract
hashes, ARM_A = NO, ARM_B = NO, truth gate CLOSED.

## Persistence + route (tested with mocked trials; real simulator calls 0)

Per trial: STARTED durable -> 20k sampling -> aggregate gradient record
(ONLINE fields only; truth-label leakage rejected by the validator) ->
instrumentation sidecar -> sidecar SHA verify -> record SHA verify ->
COMPLETE.  Restart requires exactly one STARTED + one COMPLETE + both
artifact hashes; any other state => M3-S25-R1-X => STOP => NO REPLAY.
Mocked full route green: 960/960 durable COMPLETE, consumption
19,200,000, restart-safe skip, truth unseal ONLY after completeness,
grouped evaluation, synthetic M3-S25-R1-A / B-GATE / X verdicts.

## Gates

```text
M3_S25_R1_TRUTH_AUTHORIZED = NO   (CLOSED / EXERCISED at truth terminal
                                   HEAD 089c6a48c73831fbd95e2caa5b21137b485080aa)
M3_S25_R1_ARM_A_AUTHORIZED = NO
M3_S25_R1_ARM_B_AUTHORIZED = NO
VALUE / RARITY / M3-Q      = BLOCKED
```

STOP.  Awaiting the Arm-A execution-readiness audit; only an explicit
human `M3_S25_R1_ARM_A_AUTHORIZED: YES` commit enables
`python scripts/run_m3s25r1.py arm_a_execute`.

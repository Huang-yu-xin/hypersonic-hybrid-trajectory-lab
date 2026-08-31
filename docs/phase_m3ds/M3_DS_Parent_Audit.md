# M3-DS Parent / Source Audit (DS-0)

Zero-simulator audit. No simulator calls, no controller trials.

## Provenance commands

```text
branch : feature/phase-m3d2-corrected-sign-diverse-benchmark
HEAD   : a568418beceb49641fcc743cc4a0245efd5b0eb8 (pre-M3-DS)
status : clean except untracked M3-RF records (committed by this phase)
```

## Lineage reachability (all PASS)

| Requirement | Evidence | Result |
|---|---|---|
| ER-1 corrected lineage reachable | tag `RareTopo-ER1-v0` @ d7575c5 | PASS |
| M3-v2 corrected results reachable | tag `RareTopo-M3-v2` @ f30e8bf | PASS |
| M3-D-v1 corrected reference reachable | tag `RareTopo-M3-D-v1` @ 8204819 | PASS |
| M3-D2 D2-B reachable | commit f031512 "Close M3-D2 with D2-B benchmark decision"; `m3d2_final_verdict.json.final_verdict == "D2-B"` | PASS |
| M3-D3 D3-DISC-B reachable | commit a568418; `m3d3_discovery_summary.json.discovery_verdict == "D3-DISC-B"` | PASS |
| M3-RF-B decision reachable | `results/phase_m3rf/summary/m3rf_route_decision.json.primary_route == "M3-RF-B"` (records previously untracked; committed by this phase) | PASS |

No STOP condition triggered.

## Corrected evidence relied upon

```text
D2 independently confirmed: WIDEN = 12, HOLD = 3, SHRINK = 10, AMBIGUOUS = 2
D3 boundary discovery:      WIDEN = 1, HOLD = 2, SHRINK = 1, AMBIGUOUS = 10
D3-DISC-B: provisional HOLD insufficient
M3-RF primary route: RF-B (directional WIDEN/SHRINK + abstain)
```

## Source lock

`results/phase_m3ds/summary/m3ds_source_manifest.json` locks 14 read-only
sources with `path / sha256 / commit / role`, covering: ER-1 semantic
contract, M3-v2 corrected results, M3-D-v1 corrected reference records,
M3-D2 confirmation states, M3-D2 class-transition audit, M3-D2 final
verdict, M3-D3 discovery states, M3-D3 discovery verdict, M3-RF action-space
decision, and the frozen corrected classifier contract + source.

## Firewall state

```text
extra_simulator_calls   = 0
controller_online_trials = 0
rarity_shift            = BLOCKED
M3-Q                    = BLOCKED
```

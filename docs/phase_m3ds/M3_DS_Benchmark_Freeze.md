# M3-DS Benchmark Freeze (DS-4)

Formal name: **Corrected Directional-Sign Benchmark with Abstention Safety
Axis** (short: M3-DS). Not an "8/8/8 benchmark".

## Frozen structure

```text
Axis A - Directional Primary : 8 WIDEN + 8 SHRINK   (D2 independently confirmed)
Axis A Reserve               : 4 WIDEN + 2 SHRINK   (robustness only, no tuning)
Axis B - Safety Primary      : 3 confirmed HOLD + 2 confirmed AMBIGUOUS
Axis B Expansion             : [] (DS-3 not required; separately preregistrable)
```

Machine artifact: `results/phase_m3ds/summary/m3ds_benchmark.json`
(schema `raretopo-m3ds-benchmark-v0`, `controller_online_trials = 0`,
`rarity_shift_authorized = false`).

## Zero-simulator analyses

`results/phase_m3ds/summary/m3ds_zero_sim_analyses.json` covers: directional
class balance, config diversity, s2 coverage, support-margin distribution,
safety-state provenance, HOLD vs AMBIGUOUS composition. Figures DS-1 .. DS-8
under `figures/phase_m3ds/` (DS-7/DS-8 are schematics; no policy fitted, no
controller run).

## Gate M3DS-1 (all PASS)

```text
directional primary W = 8                  PASS
directional primary S = 8                  PASS
directional diversity                      PASS (5 configs/class, >=2 strata/class)
safety primary states >= 5                 PASS (5)
all safety states independently confirmed  PASS
source lock                                PASS (14 sha256-locked sources)
event semantics                            PASS (FULL_TOPOLOGY_EVENT_S1_S4, schema v2)
classifier contract                        PASS (retuning_allowed=false, hash lock intact)
no controller trials                       PASS (0)
full regression                            PASS (see m3ds_full_regression.log)
```

## Final verdict

```text
M3DS-1 : PASS
M3DS-A : CORRECTED DIRECTIONAL BENCHMARK WITH SAFETY AXIS FROZEN
tag    : RareTopo-M3-DS-v0
```

Record: `results/phase_m3ds/summary/m3ds_final_verdict.json`.

## Claim boundary

Allowed claim: corrected empirical evidence supports a directional
WIDEN/SHRINK benchmark with a separately defined safety/abstention axis.
Not allowed: controller success, adaptive > fixed, rarity value, absolute
efficiency. Next authorized action: M3-G2 preregistration (Corrected
Directional Controller with Abstention). rarity-shift and M3-Q remain
BLOCKED.

## Regression note

The full suite (1424 collected tests) was executed in per-directory and
per-file chunks because a single invocation exceeds the 300 s tool window;
the concatenated log is `results/phase_m3ds/summary/m3ds_full_regression.log`
(all chunks passed, zero failures). A baseline full run before M3-DS changes
showed pre-existing suite behavior where `tests/test_m3d3_d3_0.py`
regenerates `results/phase_m3d3/summary/d3_0_*.csv` with last-ulp float
noise; those unrelated files were restored to their frozen HEAD state and
no corrected source hash changed.

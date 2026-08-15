# Phase F — gamma0-K Sensitivity & Hybrid-Regime Mapping

## Status

    Phase F: IN PROGRESS

    F0: COMPLETE
    F0.1: COMPLETE  (Qian Regime-Classification Access Amendment)
    F1: COMPLETE    (Single-parameter pilot; no stop gate)
    F2: BLOCKED / PILOT REVIEW REQUIRED
        (main-domain 289-point map COMPLETE; conditional expansion
         stopped at the Sanger SRTI-qualification expression boundary
         gamma0=-7.75, K=3.125 -- see f2_coarse_regime_map.md §12)

    Anchor: phase-e-v1.0
            44a99119cf9e82e64d68b5b8abdbb4a20406c7bc

    Baseline: gamma0 = -5 deg
              K = 3

    Primary domain:
        gamma0 ∈ [-7, -3] deg
        K     ∈ [2.0, 4.0]

    Next: F3 adaptive topology-boundary refinement
          (blocked pending Sanger boundary-semantics decision)

## Documents

- [`sensitivity_protocol.md`](sensitivity_protocol.md) — Phase F source of
  truth（F0 冻结：参数语义、computational domain、regime 分类、topology
  margins、boundary refinement、derivative 策略、数值/artefact 策略、
  F1–F7 roadmap；F0.1 Amendment：Qian research-terminal API 与
  regime classifier）。
- [`f1_pilot_report.md`](f1_pilot_report.md) — F1 单参数先导报告
  （gamma slice + K slice、regime 观察、transition intervals、
  topology margins、stop-gate audit、F2 决策）。
- [`f2_coarse_regime_map.md`](f2_coarse_regime_map.md) — F2 二维粗网格
  hybrid-regime map 报告（主域 289 点完整：Qian 单 topology、Sanger
  N0/N1/N2/N3 斜向带；条件扩域自动触发；Sanger SRTI-qualification
  表达边界 blocker；F3 handoff queue）。

## Roadmap

    F0  Sensitivity / topology protocol freeze      ← 当前
    F1  Single-parameter pilot (gamma slice + K slice)
    F2  Coarse gamma0-K hybrid regime map
    F3  Adaptive topology-boundary refinement
    F4  Fixed-regime local sensitivity / derivative convergence
    F5  Qian/Sanger structural sensitivity analysis
    F6  Phase-E protocol comparison surfaces over parameter space
    F7  Numerical / regression audit + Phase F final freeze

## Frozen Phase E baseline (unchanged)

    qian-baseline-v1.0
    phase-b-v1.0
    phase-c-v1.0
    sanger-baseline-v1.0
    phase-d-v1.0
    qian-sanger-comparison-v1.0
    phase-e-v1.0

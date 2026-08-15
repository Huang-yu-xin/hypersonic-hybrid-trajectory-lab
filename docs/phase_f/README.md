# Phase F — gamma0-K Sensitivity & Hybrid-Regime Mapping

## Status

    Phase F: IN PROGRESS

    F0: COMPLETE
    F0.1: COMPLETE  (Qian Regime-Classification Access Amendment)
    F1: COMPLETE    (Single-parameter pilot; no stop gate)
    F2.1: COMPLETE  (Sanger Grazing-Transition Observability Amendment)
    F2: COMPLETE    (Canonical coarse map; OPEN_BOUNDARY recorded:
                    gamma_lower / K_lower / K_upper at guardrails)

    Anchor: phase-e-v1.0
            44a99119cf9e82e64d68b5b8abdbb4a20406c7bc

    Baseline: gamma0 = -5 deg
              K = 3

    Primary domain:
        gamma0 ∈ [-7, -3] deg
        K     ∈ [2.0, 4.0]
    Final coarse domain:
        gamma0 ∈ [-9, -1] deg
        K     ∈ [1.0, 5.0]

    Next: F3 adaptive topology-boundary refinement

## Documents

- [`sensitivity_protocol.md`](sensitivity_protocol.md) — Phase F source of
  truth（F0 冻结 + F0.1 Amendment + F2.1 Amendment：参数语义、
  computational domain、regime 分类、topology margins、boundary
  refinement、derivative 策略、数值/artefact 策略、F1–F7 roadmap）。
- [`f1_pilot_report.md`](f1_pilot_report.md) — F1 单参数先导报告。
- [`f21_sanger_grazing_amendment.md`](f21_sanger_grazing_amendment.md) —
  F2.1 桑格尔擦边跃迁观测接口（grazing geometry、dense recovery、
  strict-reference 验证、等价审计）。
- [`f2_coarse_regime_map.md`](f2_coarse_regime_map.md) — F2 二维粗网格
  hybrid-regime map 报告（含原始 blocker 历史与 F2.1 后的 Blocker
  resolution；最终 33×33 域、6 个 Sanger regimes、5 条候选带、
  OPEN_BOUNDARY 记录）。

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

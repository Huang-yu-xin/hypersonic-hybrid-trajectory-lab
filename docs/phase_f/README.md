# Phase F — gamma0-K Sensitivity & Hybrid-Regime Mapping

## Status

    Phase F: IN PROGRESS

    F0: COMPLETE
    F0.1: COMPLETE  (Qian Regime-Classification Access Amendment)
    F1: COMPLETE    (Single-parameter pilot; no stop gate)
    F2.1: COMPLETE  (Sanger Grazing-Transition Observability Amendment)
    F2: COMPLETE    (Canonical coarse map; OPEN_BOUNDARY recorded)
    F3: COMPLETE    (Adaptive grazing-boundary refinement; Phi_N frozen)
    F4: COMPLETE    (Fixed-regime local sensitivity; GLOBAL_STEP_POLICY
                    h_gamma=0.1 deg / h_K=0.025; 5x2/7x2 Jacobians)

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

    Next: F5 structural sensitivity analysis
          over fixed-topology interiors

## Documents

- [`sensitivity_protocol.md`](sensitivity_protocol.md) — Phase F source of
  truth（F0 冻结 + F0.1 / F2.1 / F3 / F4 Amendments：参数语义、
  computational domain、regime 分类、topology margins、boundary
  refinement、Phi_N、FD step policy、数值/artefact 策略、F1–F7 roadmap）。
- [`f1_pilot_report.md`](f1_pilot_report.md) — F1 单参数先导报告。
- [`f21_sanger_grazing_amendment.md`](f21_sanger_grazing_amendment.md) —
  F2.1 桑格尔擦边跃迁观测接口。
- [`f2_coarse_regime_map.md`](f2_coarse_regime_map.md) — F2 二维粗网格
  hybrid-regime map（含 Blocker resolution）。
- [`f3_boundary_refinement.md`](f3_boundary_refinement.md) — F3 自适应
  grazing-boundary 精化（Phi_N 冻结、5 branch 双 reference 认证）。
- [`f4_fd_convergence.md`](f4_fd_convergence.md) — F4 固定拓扑局部灵敏度
  与 FD 收敛（GLOBAL_STEP_POLICY、5×2/7×2 Jacobians、production-vs-
  reference 审计、per-branch multiplicity 澄清）。

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

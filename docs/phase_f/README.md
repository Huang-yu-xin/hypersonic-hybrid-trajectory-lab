# Phase F — gamma0-K Sensitivity & Hybrid-Regime Mapping

## Status

    Phase F: COMPLETE
             FROZEN

    F0: COMPLETE
    F0.1: COMPLETE  (Qian Regime-Classification Access Amendment)
    F1: COMPLETE    (Single-parameter pilot; no stop gate)
    F2.1: COMPLETE  (Sanger Grazing-Transition Observability Amendment)
    F2: COMPLETE    (Canonical coarse map; OPEN_BOUNDARY recorded)
    F3: COMPLETE    (Adaptive grazing-boundary refinement; Phi_N frozen)
    F4: COMPLETE    (Fixed-regime local sensitivity; GLOBAL_STEP_POLICY)
    F5: COMPLETE    (Fixed-topology structural sensitivity map)
    F6: COMPLETE    (Phase-E common-condition comparison surfaces;
                    corrected: Protocol-D UNIQUE 1089, 15 signatures)
    F7: COMPLETE    (Numerical / regression freeze audit)

    Frozen tags: phase-f-v1.0, gamma-k-sensitivity-v1.0
    Anchor: phase-e-v1.0 (44a99119cf9e82e64d68b5b8abdbb4a20406c7bc)
    Baseline: gamma0 = -5 deg, K = 3
    Domain: gamma0 ∈ [-9,-1] deg × K ∈ [1,5]（computational window）

    Next: future predictability / hybrid sensitivity phase (not started)

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
  与 FD 收敛（GLOBAL_STEP_POLICY、5×2/7×2 Jacobians）。
- [`f5_structural_sensitivity.md`](f5_structural_sensitivity.md) — F5 固定
  拓扑结构灵敏度全域映射。
- [`f6_comparison_surfaces.md`](f6_comparison_surfaces.md) — F6 共同条件
  比较表面（Phase-E B/C/D 复用、动态 limiter、comparison signatures、
  Protocol-D UNIQUE 主导、reference audit）。
- [`f7_numerical_regression_audit.md`](f7_numerical_regression_audit.md) —
  F7 数值与回归冻结审计（float-edge resolution、REF self-stability、
  regression snapshot）。
- [`phase_f_final_report.md`](phase_f_final_report.md) — Phase F 最终综合
  报告（三层科学结论、claim boundaries、未来 predictability 连接）。

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

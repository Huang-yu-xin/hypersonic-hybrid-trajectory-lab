# Phase F — gamma0-K Sensitivity & Hybrid-Regime Mapping

## Status

    Phase F: IN PROGRESS

    F0: COMPLETE
    F0.1: COMPLETE  (Qian Regime-Classification Access Amendment)

    Anchor: phase-e-v1.0
            44a99119cf9e82e64d68b5b8abdbb4a20406c7bc

    Baseline: gamma0 = -5 deg
              K = 3

    Primary domain:
        gamma0 ∈ [-7, -3] deg
        K     ∈ [2.0, 4.0]

    Next: F1 single-parameter pilot

## Documents

- [`sensitivity_protocol.md`](sensitivity_protocol.md) — Phase F source of
  truth（F0 冻结：参数语义、computational domain、regime 分类、topology
  margins、boundary refinement、derivative 策略、数值/artefact 策略、
  F1–F7 roadmap；F0.1 Amendment：Qian research-terminal API 与
  regime classifier）。

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

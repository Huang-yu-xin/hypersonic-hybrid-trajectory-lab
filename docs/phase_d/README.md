# Phase D — Sanger Hybrid Trajectory

## Status

    Phase D status: COMPLETE
    D0 specification:     COMPLETE   (sanger_model_spec.md, d283e4a)
    D1 dynamics:          COMPLETE   (9d1d76b)
    D2 events:            COMPLETE   (b3f049a)
    D3 state machine:     COMPLETE   (97d346b)
    D4 metrics:           COMPLETE   (765ea24)
    D5 canonical baseline: COMPLETE  (29c5b3b)
    D6 numerical validation: COMPLETE (bf5b5ec)
    D7 final audit / freeze: COMPLETE (dfa8e9d + 6782982 + freeze commit)
    Production Sanger baseline: FROZEN
    Production numerics:  DOP853 / rtol=1e-9 / scaled atol / max_step=20
    completed skips:      2
    research endpoint:    SRTI
    Hybrid topology:      18 / 18 numerical configurations preserved
                          reference topology
    Visual approval:      PASS — D1-D9 reviewed (9/9)

Tags: sanger-baseline-v1.0, phase-d-v1.0 — created in the final freeze
commit (D7B).

## Documents

- [Sanger Mathematical Specification v1.0](sanger_model_spec.md)（D0，FROZEN，source of truth）
- [Sanger Hybrid Baseline](sanger_baseline.md)（D5 canonical baseline，APPROVED FOR FINAL FREEZE）
- [Sanger Numerical / Hybrid-Topology Validation](sanger_numerical_validation.md)（D6）
- [Phase D Final Report](phase_d_final_report.md)（D7A）

## Run order

```bash
# canonical baseline + artifacts
python experiments/04_sanger_hybrid/run_sanger_baseline.py
python experiments/04_sanger_hybrid/summarize_sanger_baseline.py
python experiments/04_sanger_hybrid/plot_sanger_baseline.py

# numerical validation
python experiments/05_sanger_numerical_validation/run_reference_solution.py
python experiments/05_sanger_numerical_validation/run_production_check.py
python experiments/05_sanger_numerical_validation/run_tolerance_sweep.py
python experiments/05_sanger_numerical_validation/run_max_step_sweep.py
python experiments/05_sanger_numerical_validation/summarize_sanger_numerical_validation.py
python experiments/05_sanger_numerical_validation/plot_sanger_numerical_validation.py
```

## Figure manifest（D1-D9，300 dpi PNG）

| # | filename | dimensions | size | loadable |
|---|---|---|---|---|
| D1 | `results/sanger_hybrid/baseline/figures/D1_altitude_range.png` | 2160×1380 | 130.6 KiB | yes |
| D2 | `results/sanger_hybrid/baseline/figures/D2_altitude_time.png` | 2160×1380 | 96.8 KiB | yes |
| D3 | `results/sanger_hybrid/baseline/figures/D3_velocity_time.png` | 2160×1380 | 123.0 KiB | yes |
| D4 | `results/sanger_hybrid/baseline/figures/D4_gamma_time.png` | 2160×1380 | 168.1 KiB | yes |
| D5 | `results/sanger_hybrid/baseline/figures/D5_mode_timeline.png` | 2160×780 | 46.9 KiB | yes |
| D6 | `results/sanger_hybrid/numerical_validation/figures/D6_event_convergence.png` | 2100×1320 | 132.8 KiB | yes |
| D7 | `results/sanger_hybrid/numerical_validation/figures/D7_max_step_sensitivity.png` | 2100×1320 | 95.2 KiB | yes |
| D8 | `results/sanger_hybrid/numerical_validation/figures/D8_topology_stability.png` | 2100×1200 | 77.7 KiB | yes |
| D9 | `results/sanger_hybrid/numerical_validation/figures/D9_accuracy_cost.png` | 2100×1320 | 102.6 KiB | yes |

    VISUAL APPROVAL: PASS — D1-D9 reviewed (9/9) via zai-mcp-server
    (file existence / dimensions / loadability AND visual content
     verified programmatically)

## Tag status

    phase-d-v1.0 / sanger-baseline-v1.0: created at the D7B final freeze
    commit (both point to the same FINAL_FREEZE_COMMIT)

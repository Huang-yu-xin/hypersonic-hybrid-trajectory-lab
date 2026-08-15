# Phase E — Qian vs Sanger Baseline Comparison

## Status

    Phase E status:                COMPLETE
    Comparison protocol:           FROZEN
    Production comparison regression: FROZEN
    Qian:                          qian-baseline-v1.0
    Sanger:                        sanger-baseline-v1.0
    Common-condition analysis:     COMPLETE
    Atmospheric/energy mechanism:  COMPLETE
    Structural/aerodynamic diagnostics: COMPLETE
    Core figures:                  5 / 5 PASS
    Numerical audit:               PASS
    Regression snapshot:           tests/data/qian_sanger_comparison_v1.json
    Final report:                  phase_e_final_report.md
    Tags:                          qian-sanger-comparison-v1.0, phase-e-v1.0
                                   (created by the E7 final freeze)

## Documents

- [Phase E Final Report](phase_e_final_report.md)（E7，source-of-truth summary）
- [Comparison Protocol v1.0](comparison_protocol.md)（E0，FROZEN，含 E0.1 amendment）
- [Common-Time & Common-Range Comparison](common_condition_comparison.md)（E2）
- [Atmospheric Exposure & Energy Mechanism](atmospheric_energy_mechanism.md)（E3）
- [Native Endpoint / Structural / Aerodynamic Diagnostics](native_structural_diagnostics.md)（E4）
- [Core Figures / Tables / Interpretation](phase_e_results.md)（E5）
- [Numerical & Regression Audit](numerical_regression_audit.md)（E6）

## Run order

```bash
# E1 alignment smoke
python experiments/06_qian_sanger_comparison/run_alignment_smoke.py

# E2 common conditions
python experiments/06_qian_sanger_comparison/run_common_condition_comparison.py
python experiments/06_qian_sanger_comparison/summarize_common_condition_comparison.py

# E3 mechanism
python experiments/06_qian_sanger_comparison/run_atmospheric_energy_mechanism.py
python experiments/06_qian_sanger_comparison/summarize_atmospheric_energy_mechanism.py

# E4 diagnostics
python experiments/06_qian_sanger_comparison/run_native_structural_diagnostics.py
python experiments/06_qian_sanger_comparison/summarize_native_structural_diagnostics.py

# E5 figures
python experiments/06_qian_sanger_comparison/plot_phase_e_comparison.py

# E6 numerical audit (optionally with --write-snapshot)
python experiments/06_qian_sanger_comparison/run_phase_e_numerical_audit.py
python experiments/06_qian_sanger_comparison/summarize_phase_e_numerical_audit.py
```

## Key frozen results

- Common time (t_common = 723.037965 s): DeltaR_time = +1110.700 km,
  DeltaV_time = +2778.213 m/s, DeltaE_time = +13.202 MJ/kg
- Common range (R_common = 3490.698336 km): time saving (t_Q − t_S) =
  +182.318 s, DeltaV_range = +3319.430 m/s, DeltaE_range = +16.349
  MJ/kg
- Common exposure (tau_common = 723.037965 s): elapsed extension =
  +348.365 s, DeltaR_atm_exposure = +3121.550 km, DeltaE_tau = +10.334
  MJ/kg
- Sanger VAC: duration 348.365 s, accumulated range 2171.734 km,
  mechanical-energy drift ~ machine precision
- Native endpoints: Qian @ RTI (723.0 s / 3490.7 km), Sanger @ SRTI
  (1119.5 s / 6872.9 km) — mode-persistence comparison, not a fair
  common-condition ranking

All results are deterministic comparisons under the frozen baseline
configuration and production numerics.

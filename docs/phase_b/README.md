# Phase B — Baseline Dynamics

## Status

    COMPLETE
    Qian baseline frozen
    Tag: qian-baseline-v1.0

## Final Architecture

    ENTRY_CAPTURE
        ->  (gamma = 0, direction = +1)
    QEG_GLIDE
        ->  (u_L* = 1, direction = +1, L_req = L)
    RESEARCH TERMINAL INTERFACE
        ->  (u_L = 1)
    GROUND_CONTINUATION
        ->  (h = 0)

## Key Results

| Metric | Value |
|---|---:|
| Capture time | 93.429 s |
| Capture altitude | 46.041 km |
| Capture velocity | 6810.80 m/s |
| RTI time | 723.038 s |
| RTI altitude | 46.041 km |
| RTI velocity | 3192.53 m/s |
| RTI range | 3490.70 km |
| Ground time | 2017.960 s |
| Ground range | 5363.62 km |
| Ground velocity | 159.92 m/s |

## Model Semantics

- `K = aerodynamic L/D = 3` (fixed; never redefined as the effective ratio);
- `u_L = cos(sigma)` — effective longitudinal lift projection, `u_L in [0, 1]`;
- `K_eff = K * u_L` — reported only, never replaces the aerodynamic `K`;
- `L_req = m (g - v^2/r) cos(gamma)`; `u_L = clip(L_req / L, 0, 1)` in QEG_GLIDE;
- **RTI = QEG feasibility loss** (`u_L* = 1`, i.e. `L_req = L`).

## Important Finding

The literal Eq.(4) uncontrolled solution (`literal_eq4_uncontrolled`) has
`h_max = 130.4 km > h_atm = 100 km`: a fixed-K, fixed-upward-lift open-loop
model does NOT automatically produce a Qian continuous glide.  The approved
dual-endpoint baseline adds the QEG effective-lift mode (with the explicit
capture event and the Research Terminal Interface), which keeps the vehicle
inside the atmosphere (max altitude after entry: 46.04 km).

## Audits

- `../model_audit/phase_b5_qian_continuous_glide_audit.md` — model audit (candidates A/B/C/D, decision matrix)
- `../model_audit/phase_b5_b2_terminal_audit.md` — terminal T1/T2 audit
- `../model_audit/phase_b5_b3_terminal_guidance_audit.md` — terminal-guidance literature audit
- `../model_audit/phase_b5_b3b_drag_energy_derivation.md` — drag-energy derivation (future research extension)
- `phase_b5_final_consolidation_report.md` — final consolidation and freeze

## Known Limitations

- 2D longitudinal model (no lateral dynamics);
- exponential atmosphere; fixed `C_D`; fixed aerodynamic `K = 3`;
- no Earth rotation; no angle-of-attack control;
- large implied bank angles during part of QEG (`sigma_max ~ 86 deg`);
- ground continuation leaves the primary high-speed research domain
  (research endpoint is the RTI at `t = 723.038 s`);
- thermal-load metric remains a dynamic-pressure integral proxy
  (`int q dt`), not a real heat-flux integral;
- the problem-statement Table-2 ranges are external comparison values only.

## Next Stage

    Phase C — Numerical Validation (solver comparison / tolerance convergence)

    NOT STARTED

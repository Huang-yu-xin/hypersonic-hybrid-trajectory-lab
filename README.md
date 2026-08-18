# Hypersonic Hybrid Trajectory Lab

Research codebase for dynamics, hybrid-mode modeling, finite-time
predictability and robust optimization of hypersonic skip/glide
trajectories.

## Research Pipeline

    Dynamics
        ->
    Numerical Validation
        ->
    Parameter Sensitivity
        ->
    Predictability
        ->
    Risk
        ->
    Hybrid Optimization
        ->
    Robustness

## Current Status

- [x] Phase A — Physical-model foundation
- [x] Phase B — Qian baseline dynamics
- [x] Phase B.5 — Continuous-glide model audit
- [x] Phase C — Numerical validation
- [x] Phase D — Sanger hybrid trajectory (COMPLETE, sanger-baseline-v1.0)
- [x] Phase E — Qian vs Sanger baseline comparison (COMPLETE,
  qian-sanger-comparison-v1.0)
- [x] Phase F — gamma0-K sensitivity / hybrid topology (COMPLETE / FROZEN,
  phase-f-v1.0, gamma-k-sensitivity-v1.0; Qian single sampled topology,
  Sanger N0-N5 grazing-separated regimes, fixed-topology sensitivities,
  common-condition comparison surfaces — docs/phase_f/)
- [x] Phase G — Finite-time local predictability of hybrid trajectories
  (COMPLETE / FROZEN, phase-g-v1.0, predictability-v1.0; continuous
  variational dynamics + STM, hybrid saltation / event-time, whole hybrid
  STM, scaled FTLE metrics with frozen canonical scale A, native RTI/SRTI
  terminal sensitivity, grazing transversality-loss / validity analysis,
  final synthesis & freeze manifest — docs/phase_g/)
- [ ] Risk
- [ ] Optimization

## Phase C — Numerical Validation

    Phase C — Numerical Validation: COMPLETE
    Production solver: DOP853 / rtol=1e-9 / state-scaled atol / max_step=20 s

See [docs/phase_c/](docs/phase_c/) — final report, run order and the frozen
`PRODUCTION_SOLVER_CONFIG` (`src/hyptraj/simulation/numerics.py`); the Phase B
`DEFAULT_SOLVER_CONFIG` remains untouched for regression continuity.

## Phase D — Sanger Hybrid Trajectory

    Phase D — Sanger Hybrid Trajectory: COMPLETE
    Canonical baseline: 2 completed skips (FROZEN, sanger-baseline-v1.0)
    Research endpoint: SRTI
    Numerically validated: 18/18 topology-stable numerical cases

See [docs/phase_d/](docs/phase_d/) — mathematical specification (D0, frozen),
canonical production baseline (D5, frozen), numerical / hybrid-topology
validation (D6), final report and freeze (D7A/D7B). Reproduction:

    python experiments/04_sanger_hybrid/run_sanger_baseline.py
    python experiments/04_sanger_hybrid/summarize_sanger_baseline.py
    python experiments/04_sanger_hybrid/plot_sanger_baseline.py

## Phase E — Qian vs Sanger Baseline Comparison

    Phase E — Qian vs Sanger Baseline Comparison: COMPLETE
    Common-time / common-range / common-exposure comparison
    completed under frozen baselines and production numerics.
    Tags: qian-sanger-comparison-v1.0, phase-e-v1.0

Phase F — gamma0-K Sensitivity / Hybrid Topology:
    COMPLETE / FROZEN
    - Qian single sampled topology; Sanger N0-N5 grazing-separated regimes
    - fixed-topology sensitivities; common-condition comparison surfaces
    - docs/phase_f/

See [docs/phase_e/](docs/phase_e/) — comparison protocol (E0, frozen),
alignment infrastructure (E1), common-condition comparison (E2),
atmospheric-exposure / energy mechanism (E3), native / structural /
aerodynamic diagnostics (E4), core figures (E5, 5/5 visual PASS),
numerical / regression audit (E6, production numerics APPROVED) and
the final report / freeze (E7).

## Phase G — Finite-Time Local Predictability

    Phase G — Finite-Time Local Predictability of Hybrid Trajectories: COMPLETE / FROZEN
    Branch: feature/phase-g-predictability (upstream frozen baseline: phase-f-v1.0)
    Acceptance chain: G0 -> G1 -> G2 -> G2R -> G3 -> G4 -> G4R -> G5 -> G5R -> G6 -> G6R -> G6R2 -> G7
    Final tags: phase-g-v1.0, predictability-v1.0
    Final report: docs/phase_g/phase_g_final_report.md
    Freeze manifest: tests/data/phase_g_final_freeze_v1.json

Phase G studies the **finite-time local predictability** of the frozen Qian
and Sanger hybrid trajectories under *initial-state perturbations*
`δx0 = [δr0, δθ0, δv0, δγ0]`. It is deliberately **finite-time, local,
first-order and branch-conditioned** — it is not an asymptotic-chaos
analysis, not a global-stability proof, and not an uncertainty
propagation. What it establishes, stage by stage (G0–G6R2) and how it is
frozen (G7):

    - continuous variational dynamics       A_m = ∂f_m/∂x        (G1, FD-validated)
    - continuous STM                      Φ(t, t0), rows=output, cols=initial perturbation (G2)
    - hybrid event calculus               q_e = -n^T/(n^T f^-); Ξ = I + (f+-f-)n^T/(n^T f-) (G3)
    - whole hybrid STM                    Φ_H(T,0) = C_{N+1} Ξ_N C_N ... Ξ_1 C_1 (G4)
    - scaled finite-time metrics          S^-1 Φ_H S  (SVD / FTLE / rank / condition) (G5)
    - native terminal sensitivity         η_T, J_T  (Qian RTI / Sanger SRTI, descriptive) (G5/G5R)
    - grazing validity                    d = n^T f^- = v sin γ → 0 neighborhood (G6/G6R/G6R2)

Key validated results (snapshot-sourced; see `docs/phase_g/phase_g_final_report.md`):

    Canonical scale (frozen):        S_A = diag(10^5 m, 1 rad, 7×10^3 m/s, 0.1 rad)
    Qian T=600 (capture):            σ_max ≈ 1.608, rank 3, STRUCTURAL_SINGULAR
    Sanger T=600 (exit, entry):      σ_max ≈ 85.87, rank 4, FINITE
    Cross-model warning:             worst-direction amplification at T=600 under
                                     scale A is larger for Sanger (λ ≈ 9×), but the
                                     ranking is scale-sensitive (reverses under scale B)
    Qian RTI / Sanger SRTI:          descriptive terminal sensitivities, not a fair
                                     cross-model endpoint ranking
    Grazing condition:               ‖q S_A‖ = s_r / |d| and the scaled-Ξ identity hold
                                     exactly (machine precision)
    Quadratic tangency:              Φ_local ∝ |d_exit|² (H1 slope ≈ 2, R² ≈ 1, B0–B4)
    Validity radius (G6R2 authority):r₁% ≈ 0.040·Φ_local, r₅% ≈ 0.185·Φ_local
                                     (approx. across the tested controlled families)
    Grazing threshold:               NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED
                                     (dimensioned |d| and incidence vary by branch)

Corrective-hardening history is retained as part of the scientific
record: G2R (two-sided FD + mode-window gates), G4R (endpoint-scoped
topology), G5R (terminal eligibility / exact-zero guard / RTI trim),
G6R (hard grazing topology contract + refined radii + paired-FD plateau +
four-column validation), G6R2 (protocol-correct `ERROR / LINEAR PREDICTION`
error normalization — final validity-radius authority).

See [docs/phase_g/](docs/phase_g/) — the frozen protocol
(`predictability_protocol.md`, G0), per-phase reports (G1–G6), the final
synthesis ([phase_g_final_report.md](docs/phase_g/phase_g_final_report.md))
and the machine-readable freeze manifest
(`tests/data/phase_g_final_freeze_v1.json`, SHA-256-locked to the accepted
G1–G6 snapshots). Deterministic generators:
`scripts/run_phase_g6_grazing.py` (G6/G6R/G6R2 scientific snapshot) and
`scripts/build_phase_g_final_manifest.py` (freeze manifest; reproducible,
no diff on re-run).

## Frozen Baselines

### Literal Eq.(4)

`literal_eq4_uncontrolled` — 题面式(4)无控制字面参考解
(diagnostic/reference baseline; skip to ~130 km, `tf=3508.9 s`,
`Rf=13578.5 km`, `vf=159.95 m/s`, `hmax=130.4 km`).
Output: `results/baseline/literal_eq4_uncontrolled/`.

### Approved Qian Continuous Glide

`qian_continuous_glide` — 经 Phase B.5 模型审计后批准的双端点钱学森持续滑翔基准
(**tag: qian-baseline-v1.0**). Architecture:

    Entry/Capture
        ->  (gamma = 0, direction = +1)
    QEG (u_L = clip(L_req/L, 0, 1))
        ->  (u_L* = 1, L_req = L)
    Research Terminal Interface
        ->  (u_L = 1)
    Ground continuation
        ->  (h = 0)

Output: `results/baseline/qian_continuous_glide/`.

## Key Numerical Results

RESEARCH endpoint (high-speed research domain, `[0, t_RTI]`):

    t_RTI = 723.038 s
    h_RTI = 46.041 km
    v_RTI = 3192.53 m/s
    R_RTI = 3490.70 km

GROUND endpoint (problem-compatibility continuation only, `[0, t_ground]`):

    t_ground = 2017.960 s
    R_ground = 5363.62 km
    v_ground = 159.92 m/s

The two endpoints must not be confused: the research terminal velocity is
`v_RTI = 3192.53 m/s` at the Research Terminal Interface; `v_ground` belongs
to the ground-continuation segment only.

## Reproduction

    pip install -e ".[dev]"

    pytest -q

    python experiments/02_qian_continuous_glide/run_qian_glide.py

    python experiments/02_qian_continuous_glide/plot_qian_glide.py

Phase G freeze manifest reproduction (deterministic, no diff on re-run):

    python scripts/build_phase_g_final_manifest.py

(optional) Phase G6/G6R/G6R2 grazing snapshot regeneration:

    python scripts/run_phase_g6_grazing.py

Literal baseline reproduction:

    python experiments/01_baseline_dynamics/run_qian_baseline.py
    python experiments/01_baseline_dynamics/plot_qian_baseline.py

## Repository Structure

    src/hyptraj/      production library (models / controls / modes / simulation /
                      predictability (Jacobians, STM, saltation, hybrid STM,
                      FTLE metrics, terminal sensitivity, grazing validity) / ...)
    experiments/      runnable experiments (01 literal baseline, 02 approved Qian baseline, audit scripts)
    tests/            pytest suite (models, events, literal + Qian regressions)
    docs/             phase reports, model audits, research plan
    references/       bibliography and reading notes
    results/          generated outputs (gitignored; reproducible via the commands above)

## Important Model Note

The supplied reference ranges are treated as external comparison benchmarks
rather than regression targets. The literal equations and the supplied
reference table were found not to be self-consistent under the stated
parameter set; see `docs/model_audit/phase_b5_qian_continuous_glide_audit.md`.

Model semantics: `K = L/D = 3` is the fixed aerodynamic lift-to-drag ratio;
`u_L = cos(sigma) in [0,1]` is the effective longitudinal lift projection;
`K_eff = K * u_L` is reported only and never replaces the aerodynamic `K`.

## Research Disclaimer

This codebase implements simplified research models for dynamics,
predictability and optimization studies. Simulation results are not
real-world weapon-performance conclusions.

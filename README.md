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
- [ ] Phase D — Sanger hybrid trajectory
- [ ] Phase E — Baseline comparison
- [ ] Phase F — Parameter sensitivity
- [ ] Predictability / STM / FTLE
- [ ] Risk
- [ ] Optimization

## Phase C — Numerical Validation

    Phase C — Numerical Validation: COMPLETE
    Production solver: DOP853 / rtol=1e-9 / state-scaled atol / max_step=20 s

See [docs/phase_c/](docs/phase_c/) — final report, run order and the frozen
`PRODUCTION_SOLVER_CONFIG` (`src/hyptraj/simulation/numerics.py`); the Phase B
`DEFAULT_SOLVER_CONFIG` remains untouched for regression continuity.

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

Literal baseline reproduction:

    python experiments/01_baseline_dynamics/run_qian_baseline.py
    python experiments/01_baseline_dynamics/plot_qian_baseline.py

## Repository Structure

    src/hyptraj/      production library (models / controls / modes / simulation / metrics / ...)
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

# Phase C — Numerical Validation / Solver Convergence

## Status

    Phase C status: COMPLETE
    Production numerics: FROZEN
    Tag: phase-c-v1.0

Final report: [phase_c_final_report.md](phase_c_final_report.md)

Phase C validates the frozen Phase B.5 Qian hybrid baseline without changing its physics, control law, initial conditions, or event definitions.

## Run order

```bash
python experiments/03_numerical_validation/run_reference_solution.py
python experiments/03_numerical_validation/run_solver_comparison.py
python experiments/03_numerical_validation/run_tolerance_sweep.py
python experiments/03_numerical_validation/run_max_step_sweep.py
python experiments/03_numerical_validation/run_final_candidates.py
python experiments/03_numerical_validation/summarize_numerical_validation.py
python experiments/03_numerical_validation/plot_numerical_validation.py
```

## Numerical reference

The reference is a numerical comparison solution, not an analytic truth:

```text
DOP853
rtol = 1e-12
atol = [1e-7, 1e-14, 1e-10, 1e-14]
max_step = 0.1 s
```

A second `max_step = 0.05 s` run checks reference stability.

## Production configuration selected by the Phase C pre-validation

```text
method = DOP853
rtol = 1e-9
atol = [1e-4, 1e-11, 1e-7, 1e-11]
max_step = 20 s
dense_output = True
```

`src/hyptraj/simulation/numerics.py` stores this as `PRODUCTION_SOLVER_CONFIG` while leaving the Phase B default untouched for regression continuity.

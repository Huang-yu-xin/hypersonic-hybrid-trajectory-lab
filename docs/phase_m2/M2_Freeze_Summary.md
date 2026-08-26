# M2 Freeze Summary — RareTopo-M2-v0

> **Schema:** `raretopo-m2-v0` ｜ **Date:** 2026-08-27 ｜ **Branch at freeze:** `feature/phase-m2-covariance-adaptation`
> **Document type:** M2 freeze record required by the M3 preregistered task (M3 Task Sec. 0)
> **Machine-readable verdict:** `results/phase_m2/summary/gate_audit.json`

---

## 1. Frozen state

```text
tag            = RareTopo-M2-v0 (annotated; pushed to origin)
tag commit     = 0a00f4459609f712aa76dc4d14349d9cd0d58fc9  (short: 0a00f44)
final HEAD     = 0a00f4459609f712aa76dc4d14349d9cd0d58fc9  (tag == final M2 HEAD)
parent tags    = RareTopo-H3-v1.0   -> 5faef86b9d0ff35eb2cee762ec24a363796f6ce1
                 RareTopo-M1-v0    -> a825863ec20f8dfe0f4011c0f1ec71faf2a893db
                 RareTopo-M1-D-v1.0 -> 059964eb3b8b927301776ae5505bc3ac8593ed94
                 (all three unchanged; firewall intact at freeze time)
```

## 2. Full pytest evidence (freeze gate)

```text
command      = python -m pytest -q          (repo root on sys.path)
result       = 1113 passed / 0 failed, 3 warnings, 292.79 s
exit code    = 0            <- verified via $? of pytest itself, not a pipe stage
first attempt note: an operator-side invocation `pytest -q | tail` misattributed the
pipeline exit code and ran under an interpreter where the repo root was not on
sys.path, surfacing 2 spurious ModuleNotFoundError failures in
tests/test_m2_covariance_pipeline.py::test_m2_no_extra_simulator_calls /
::test_m2_result_schema. Re-run with `python -m pytest -q`: both tests pass;
the suite is green. No repository change was involved or made for this.
```

## 3. Gate verdicts at freeze (verbatim from gate audit)

| Gate | Verdict |
|---|---|
| M2-0 validity | PASS |
| M2-1 estimator stability | PASS |
| M2-2 core second-moment gain | FAIL |
| M2-3 shape-only | FAIL |
| M2-4 no catastrophic leakage redistribution | PASS |
| M2-5 relative budget efficiency | FAIL |
| STRONG absolute efficiency | NOT PASSED |

Frozen negative conclusion (unmodified wording):

> **Local variance-HDR covariance matching is not supported as a proposal covariance control rule on the frozen M1-D benchmark. Descriptive variance geometry and a valid second-moment descent control target are not the same object.**

Prereg amendment count: **0**. No positive covariance-control claim is made anywhere in the M2 artifacts.

## 4. What is frozen (must not be overwritten or "repaired")

- All M2 code (`src/hyptraj/m2/`), drivers, configs (`configs/phase_m2/`), results
  (`results/phase_m2/`), figures (`figures/phase_m2/`) and documents
  (`docs/phase_m2/`) as committed at the tag commit.
- The M2 lambda value and every preregistered protocol constant stay untouched.
- M2's failure mode is recorded as a scientific fact feeding M3:
  descriptive variance-region geometry != descent direction for M2.

## 5. Limitations carried forward

- HOLD rate 172/256 = 67.2% driven by `ESS_V_region < 20`; the regional ESS_V
  median was only ~12, so the adapted layer rarely had the finite-sample support
  to act legally — any successor method must quantify its effective sample
  support before acting (M3 inherits the analogous `ESS_grad >= 20` safeguard).
- On the 21/64 paired trials where adaptation could legally act, it systematically
  INCREASED M2 (median seed-level ratio 1.53x, monotone in lambda) — evidence
  that region-shaped covariance targets are not descent directions.
- Conclusion scope: fixed-means/fixed-weights mixture family on the frozen M1-D
  benchmark; no claim about full-matrix control, policy learning, or other benchmarks.

## 6. Successor dependency

Only after this tag may M3 (`docs/phase_m3/M3_Second_Moment_Gradient_Covariance_Control_Task.md`)
begin scientific work. M3 preregistration requires this tag as parent and must not retune,
rerun, or reinterpret M2.

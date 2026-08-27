# M3-v0 Freeze Summary — RareTopo-M3-v0

> **Schema:** `raretopo-m3-v0` ｜ **Date:** 2026-08-27 ｜ **Branch at freeze:** `feature/phase-m3-scalar-gradient-control`
> **Document type:** M3-v0 freeze record required by the M3-D preregistered task (M3-D Task Sec. 0)
> **Machine-readable verdicts:** `results/phase_m3/summary/gate_audit.json`, `results/phase_m3/summary/m2_leakage_decomposition.json`

---

## 1. Frozen state

```text
tag            = RareTopo-M3-v0 (annotated; pushed to origin)
tag commit     = 32b285625494d9b3da08be3c559db3855df77667  (short: 32b2856)
final HEAD     = 32b285625494d9b3da08be3c559db3855df77667  (tag == final M3-v0 science HEAD;
                 this summary is a post-tag bookkeeping commit, same convention as M2)
parent tags    = RareTopo-H3-v1.0   -> 5faef86b9d0ff35eb2cee762ec24a363796f6ce1
                 RareTopo-M1-v0    -> a825863ec20f8dfe0f4011c0f1ec71faf2a893db
                 RareTopo-M1-D-v1.0 -> 059964eb3b8b927301776ae5505bc3ac8593ed94
                 RareTopo-M2-v0    -> 0a00f4459609f712aa76dc4d14349d9cd0d58fc9
                 (all four unchanged; firewall intact at freeze time; M2 tag is an
                  ancestor of the freeze HEAD)
prereg         = docs/phase_m3/M3_Second_Moment_Gradient_Covariance_Control_Task.md
                 (sha256 6c3cf811…db0) + configs/phase_m3/m3_scalar_gradient_v0.json — zero amendments
benchmark hash = be2ef47157b95f479949f706de6285827b70e15fa0488e4cdbfc128bd6bb61de (M1-D, inherited)
```

## 2. Full pytest evidence (freeze gate)

```text
command      = python -m pytest -q          (repo root on sys.path; canonical invocation)
result       = 1128 passed / 0 failed / skipped 0 / deselected 0, 3 warnings, 347.49 s
exit code    = 0            <- verified via $? of pytest itself, not a pipe stage
notes        = evidence rerun immediately BEFORE tagging, after all three batches of
               freeze-audit corrections (theory assumptions / Gate M3-3 wording /
               supported-vs-unsupported conclusion); no scientific module touched by
               any correction batch. An earlier full run during the audit phase was
               also 1128 passed / exit 0 (331.42 s). A bare `pytest` call had shown
               spurious ModuleNotFoundErrors in an operator-side sys.path scenario;
               `python -m pytest -q` is the frozen regression口径.
```

## 3. Freeze-audit corrections applied before the tag

- **Theory (A3)**: retracted the invalid "compact SPD parameter neighbourhood ⇒ state-space pointwise lower bound q_Σ ≥ c_U > 0" argument (quantifier-order error: Gaussian density decays to 0 as ‖x‖→∞); replaced by an explicit LOCAL dominated-envelope assumption sup_{Σ∈U}‖∂_Σ[𝟏_A p²/q_Σ]‖ ≤ h ∈ L¹(A) licensing differentiation under the integral sign via dominated convergence; family-specific sufficient conditions kept as remarks (incl. s² > λᵢ(P)/2 legal window respected by the FD probes). Formulas (1)–(6), theorem scope, nonclaims untouched.
- **Theory (A2)**: `(1-A) ⊆ {q>0}` notation slip corrected to `A ⊆ {q>0}` and rewritten as support-positivity with explicit boundary **global positivity ≠ global positive lower bound**.
- **Event-region description**: A described as partitioned into ALL frozen topology modes S1..S4 (not "union of missing-mode supports"), consistent with the closed identity below.
- **Naming**: "numerical proof obligation" → "numerical validation obligation" (FD validates formula↔implementation on tested instances; it discharges no part of the mathematical proof).
- **M2 = Σ_j L_j decomposition closed**: `scripts/run_m3_leakage_decomposition.py` re-aggregates BASE/PREDICTED per-mode leakage from UNCHANGED raw Layer A records; max |Σ L − M̂₂| = 2.22e-16 over 192 arm evaluations (rel ≤ 3.9e-16). Data-driven mechanism: off-target leakage DROP (median sum-off-target ratio 0.846) dominates the small selected-mode rise (1.099 on a ~1.4% base loss share).
- **Gate M3-3 recorded overall FAIL** everywhere (Final Report / Methodology / Validity Audit matched to the machine-readable clause_a=True / clause_b=False verdict); Sec.35 variant allowed-claim withdrawn (core-gates precondition unmet; headline_allowed_claim=null).
- **Plugin-bias wording tightened**: finite-sample bias CAN flip the sign in general; the direction conclusion rests on independent FD validation (M3-1) plus matched counterfactual evaluation (M3-5).

Raw result files verified unchanged by sha256 across every regeneration step.

## 4. Gate verdicts at freeze (verbatim from gate audit)

| Gate | Verdict |
|---|---|
| M3-0 validity | PASS |
| M3-1 numerical gradient validity | PASS |
| M3-2 direction identifiability | PASS |
| M3-3 direction accuracy | **FAIL**（accuracy 子条 PASS 0.790≥0.75；+25pp 自适应优势子条 FAIL +0 pp vs Always-Widen） |
| M3-4 predicted step M2 gain | PASS |
| M3-5 counterfactual ordering | PASS |
| M3-6 no catastrophic leakage redistribution | PASS |
| STRONG budget-adjusted VRF | NOT PASSED |

Frozen conclusion (verbatim):

> **M3-v0 establishes a numerically validated local second-moment covariance descent signal. On the frozen M1-D benchmark, this signal correctly predicts beneficial widening and outperforms the opposite perturbation, but it provides no measurable directional advantage over the fixed Always-Widen rule because the benchmark is overwhelmingly widening-dominant. Adaptive covariance-control value therefore remains unresolved.**

Supported: gradient derivation/implementation numerically validated; local descent direction supported; predicted widening reduces M2; beats opposite perturbation; descriptive HDR covariance ≠ valid control target. NOT supported: advantage over Always-Widen; adaptive value established; full-matrix escalation justified; cost efficiency vs crude MC.

Prereg amendment count: **0**.

## 5. What is frozen (must not be overwritten or "repaired")

- All M3 code (`src/hyptraj/m3/`), drivers (`scripts/run_m3_*`), configs (`configs/phase_m3/`), results (`results/phase_m3/`, untracked per repo policy but hash-anchored in `m2_leakage_decomposition.json` and gate records), figures (`figures/phase_m3/`) and documents (`docs/phase_m3/`) as committed at the tag commit.
- The preregistered constants (delta_theta_main=0.20, ESS_grad=20, sensitivity [0.10,0.20,0.40], tie tol 0.01, seeds 2026..2033, pilot 20k / eval 100k, fixed-weight Layer A) stay untouched.
- The M3-3 FAIL (no adaptive advantage over Always-Widen) is recorded as a scientific fact feeding M3-D.

## 6. Successor dependency

Only after this tag may M3-D (`M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md`) begin scientific work. M3-D must not retune, rerun, or reinterpret M3-v0's controller: gradient formula, responsibility identity, fixed-weight Layer A, ESS_grad=20, fixed-stratified bootstrap, CI sign rule, delta_theta=0.20, tie tolerance are IMMUTABLE inputs for the sign-diverse adaptive-value benchmark. Full-matrix covariance control remains blocked until M3-D establishes real adaptive value.

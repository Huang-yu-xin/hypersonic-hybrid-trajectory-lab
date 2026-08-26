# M1-D Benchmark Methodology — Implementation-to-Preregistration Mapping

> **Status:** FROZEN BEFORE ADAPTIVE RUNS (commit precedes any D5+ execution)
> **Parent task:** `M1_D_Multi_Missing_Mode_Variance_Geometry_Benchmark_Task.md`
> (SHA256 `6cf51ae3…6f91`), commit `fba11db`
> **Benchmark freeze:** `M1_D_Benchmark_Freeze.json` / `.md`, commit `f7e4e82`
> **Date:** 2026-08-27

---

## 1. Family and freeze recap

- Rotated-cap multi-mode u-space family, d=2, target `N(0, I_2)`;
  S1 primary linear + three missing modes (25% curvature probability each,
  H3-2 surface form), pairwise angular separation ≥ 40°.
- q0 = single unit-covariance component at the primary design point
  (`z* = h_1 n_1`, frozen rule).
- Batch seed 20260827 × 64 candidates; uniform N_ref = 500k
  (150k MC under p + stratified IS at the four apex components,
  within-stratum bootstrap ×200). 21/64 fully eligible; first 8 by
  config_id frozen. NO threshold relaxation was needed.

## 2. Layer A — selection-only comparator (task Sec. 17)

For every (config, seed) ALL five methods consume the SAME pilot bundle
(common random numbers; identical arrays across methods because draw sizes
are decision-independent):

```
zp = rng.standard_normal((round(n*0.5), d))     # from p
zq = q_t.sample(rng, n - round(n*0.5))          # from proposal
```

Candidate gate (Sec. 16, literal): observed ≥ 5, valid oracle label,
unrepresented, stable order.  The M1-v0 τ-birth thresholds are deliberately
NOT applied in Layer A ("不应通过过高 threshold 预先删光候选").

Selectors differ ONLY in the ranking signal on that candidate set:

| method | signal |
|---|---|
| probability_selector | argmax P̂_k = (1/N)Σ 1_{A_k} p/r |
| variance_selector    | argmax L̂_k = (1/N)Σ 1_{A_k} p²/(q_t r) |
| random_selector      | uniform over candidates, rng([seed,424242,b]) |
| oracle_P / oracle_V  | benchmark-design reference orders (driver-supplied string lists only) |

Common downstream action (Sec. 17.3 / 30-32) is a single shared builder:
probability conditional centroid `m_k^P`, unit covariance, frozen
`add_component` weight split, then the FROZEN SLSQP M̂₂(π) optimizer on the
same pilot.  Identity of downstream behavior across selectors is structural:
only the selected mode-id string enters the builder.

A trial whose pilot yields no eligible candidate records
`stop_reason="no_eligible_candidate"` with zero births; for accuracy metrics
such trials count as non-selections (misses against k*_V).

## 3. Layer B — full-policy comparator (task Sec. 18)

Both variants re-compose the frozen v0 loop from its public primitives
(`estimate_variance_measure`, `diagnose_missing_mode`, frozen HDR centroid /
probability centroid, `add_component`, frozen SLSQP `update_weights`) with
identical control-flow ORDER: invalid-M2 → round cap → M2-improvement →
no-candidate → ADD.

| variant | birth signal | center | weights |
|---|---|---|---|
| variance_full_policy | ω̂_k^V + bootstrap LCB (frozen gates) | η=0.8 variance-mass HDR centroid | frozen SLSQP |
| probability_full_policy | top-ranked unrepresented by P̂ (threshold-free) | IS probability centroid | π ∝ P̂ normalized |

No ν_V / L_k / variance centroid / variance-aware objective enters any
action pathway of the probability variant (input-only diagnostics statistics
are still recorded).  Dynamic re-ranking (Sec. 26): every new round draws a
fresh mix_50 pilot from the CURRENT proposal, so both variants re-rank under
q_t automatically; parity vs `run_closed_loop` verified by unit test on
non-diverging paths (stop reason and per-round M̂₂ traces bit-equal).

## 4. Budgets and fairness (task Sec. 14/21/27)

Per trial: pilots of 20,000 (10k p + 10k q_t), final evaluation 100,000
independent calls, seeds {2026..2033} paired across methods.

**DV2 (declared deviation, budget accounting).** The frozen loop's internal
assertion sizes the nominal adaptation budget as `max_iterations × pilot_n`,
yet its own control flow always draws one trailing diagnostic pilot after the
final allowed ADD — a legal one-birth declaration cannot be expressed there.
The M1-v0 file is immutable under the Sec. 2 firewall, so the re-composed
loop (built exclusively from frozen public functions) uses
`(birth_budget + 1)` rounds as the declared cap; actual consumption is
recorded per trial and priced by VRF_budget. Layer A performs exactly B
decision rounds (no trailing diagnostic) but shares the same DECLARED cap;
its lower actual overhead is likewise priced via VRF_budget. No preregistered
gate compares across layers, so this asymmetry cannot influence Gates
D1–D6 as defined.

**Denominator convention (documented, not a deviation of any ratio test).**
VRF definitions are the frozen semantic-corrected formulas; their MC-side
probability uses the reference missing-mode union probability P_event^ref =
Σ_{k∈missing} P_k^ref — an IDENTICAL constant denominator across all methods
of one config, which preserves every paired comparison while keeping VRFs
strictly interpretable.

## 5. Oracle isolation (task Sec. 41)

Structural: `hyptraj.m1d.adaptation` and `hyptraj.m1d.layer_a` accept no
numeric reference inputs anywhere; Oracle methods receive ordered mode-id
string lists from driver code only; CVS/CPS/regret attachments happen in
driver-space (`experiments.make_record`) after proposals are final.
Unit test `test_m1d_no_oracle_leakage` enforces both the import graph and the
absence of file access inside online modules.

## 5b. Selection among simultaneous births (deviation DV3)

The frozen v0 birth gate accepts the FIRST passing candidate in stable label
order (`diagnose_missing_mode` docstring); with at most one viable missing
mode in Benchmarks A/B/C this coincides with ranking, but under
K_missing ≥ 3 it generally does not.  For the M1-D full-policy variance
variant we take, among candidates whose frozen gate flags `birth_eligible`,
the argmax of ω̂_k^V -- exactly the Sec. 18.2 wording ("rank by L_k /
omega_k^V").  Gate thresholds themselves are untouched.  Probability-side
top-ranked logic (`probability_top`) was already rank-based inside the
frozen switch set.  Unit-test parity against `run_closed_loop` therefore
uses scenarios without simultaneous births (identical trajectories there),
plus explicit multi-birth coverage in `test_m1d_dynamic_reranking`.

## 6. Oracle-V under D2 (deviation D2-O1)

Task Sec. 19.2 ALLOWS an offline high-N re-reference L_k(q₁) before the
second Oracle-V birth. This batch keeps Oracle-V on the frozen q₀ ordering
for both births and documents the restriction: per-trial re-characterization
under seed-dependent q₁ was judged out of proportion for a non-gated
reporting condition, and a WEAKENED oracle is conservative w.r.t. the claim
direction (any Oracle-V advantage we report was achieved without extra
offline information). Probability/Random selectors need no analogue; the two
full policies re-rank online by construction.

## 7. Statistical plan (task Sec. 35-36)

Records carry the full Sec. 37 schema. Headline statistics use PAIRED
(config, seed) samples:

- within-config: median / mean / std / min-max across 8 seeds;
- across-config: per-config medians; global median-of-medians headline;
- Gate checks on per-config paired medians (with config counts passing);
- paired bootstrap CIs (2000 replicates) for key deltas/ratios.

## 8. Metrics naming

Acc_V@1 · CVS_B / CPS_B (B-partial captures recorded incrementally) ·
M̂₂(q_final) · per-mode L_k(q_final), ω̂ · VRF_proposal / VRF_budget ·
R_M2 = M̂₂_policy/M̂₂_oracleV − 1 · R_CVS = 1 − CVS_policy/CVS_oracleV.

## 9. Files

```
src/hyptraj/m1d/{benchmark_family, adaptation, layer_a, metrics, experiments}.py
scripts/run_m1d_experiments.py        # stage driver (D5-D8)
scripts/run_m1d_gate_audit.py         # aggregation + gates
scripts/run_m1d_figures.py            # Fig D1..D8
configs/phase_m1d/m1d_d1_one_birth.json, m1d_d2_two_birth.json
tests/test_m1d_benchmark_family.py, test_m1d_adaptation.py
results/phase_m1d/{d1_selection_only, d1_full_policy, d2_two_birth, ablations, summary}/
figures/phase_m1d/
```

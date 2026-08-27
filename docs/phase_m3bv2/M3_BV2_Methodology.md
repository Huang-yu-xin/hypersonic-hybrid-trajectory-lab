# M3-BV2 Methodology — Dual-Axis Decision / Adaptive-Value Benchmark

> **Project:** RareTopo ｜ **Stage:** M3-BV2 ｜ **Branch:** `feature/phase-m3bv2-dual-axis-benchmark`
> **Preregistration:** task `docs/phase_m3bv2/M3_BV2_Dual_Axis_Benchmark_Task.md` + construction lock `configs/phase_m3bv2/m3bv2_construction_lock.json` committed at `37d17bc` **before any BV2 analysis**.
> **Scope of this document:** benchmark construction methodology only. Controller evaluation is explicitly out of scope (see Final Report).

---

## 1. Scientific motivation and the dual-axis split

M3-BV-v0 established (frozen as `RareTopo-M3-BV-v0`, a negative benchmark-design result) that a balanced **8W/8H/8S** benchmark cannot simultaneously answer two different questions under one median-ratio adaptive-value gate:

- **Question A (decision):** did a controller choose the correct WIDEN / HOLD / SHRINK action?
- **Question B (value):** did adaptive switching produce measurable estimator-value gain over one globally best fixed policy?

The central metric obstruction, confirmed at BV-v0: with BestFixed = ALWAYS_WIDEN, all 8 WIDEN states are constructive Oracle/BestFixed ties; HOLD states are intentionally near-indifferent (ratios ≈ 1); decisive headroom exists only on SHRINK states — one third of the benchmark. The frozen median-ratio ≤ 0.95 gate was therefore structurally unattainable for the *balanced decision* design, irrespective of label quality. That is a benchmark-metric architecture issue, not a controller result.

BV2 separates the questions into two independently frozen benchmarks (task Sec. 3):

| Axis | Purpose | Structure | Headline question |
|---|---|---|---|
| A — Decision | action correctness | 8 WIDEN / 8 HOLD / 8 SHRINK = 24 | did the controller pick the right action? |
| B — Value | adaptive economic value | 12 WIDEN / 12 SHRINK = 24 | does W/S switching beat one globally fixed rule? |

The Value benchmark deliberately excludes HOLD states: HOLD is near-indifferent by construction and dilutes an economic-value benchmark (task Sec. 3/12). ALWAYS_HOLD may still serve as a *fixed comparator* because J(ALWAYS_HOLD) ≡ 0 by construction (it always executes the BASE arm).

## 2. Candidate source: reuse of BV-v0 characterization

BV2 reuses the complete BV-v0 candidate characterization as **prior characterization data** (task Sec. 5):

| Prior artifact | Path | Role |
|---|---|---|
| candidate pool (reference) | `results/phase_m3bv/reference/m3bv_candidate_pool.json` | 88 states × 3 arms, 500k/arm, 20 CRN batches, frozen labels, margins, support, legality, M2 = ΣL per arm |
| headline stability | `results/phase_m3bv/reference/m3bv_headline_stability.json` | 88 states × 8 matched replicates × 100k/arm, all three arms |

**Reuse contract (lock `candidate_source`):** reuse allowed only if the raw state definitions are byte-identical *and* the reuse is explicitly recorded. The explicit record lives in `results/phase_m3bv2/reuse_record.json` (conclusion **REUSE_OK**), anchored by:

- `pool.task_sha256` == sha256 of the frozen BV-v0 task doc (byte-identical);
- `pool.construction_lock_sha256` == sha256 of the frozen BV-v0 construction lock;
- `pool.frozen_configs` == the 8 frozen event configs of `configs/phase_m3d/m3d_candidate_state_grid.json`;
- `pool.s2_grid_bv` == the locked 11-value scalar grid; state keys form exactly the 8 × 11 = 88 grid;
- reference semantics re-checked: 500k/arm × 20 batches, delta_theta = 0.20, M2 = Σ_j L_j passes on all 264 arm records, 88/88 three-arm legality, 0 illegal;
- headline semantics re-checked: 100k/arm × 10 batches × 8 replicates, replicate RNG rule `[701001 + idx, 10000 + replicate]` exact on all 704 replicate records.

No new simulation was executed at BV2; no controller output enters anywhere.

## 3. Frozen estimator and label semantics (unchanged from BV-v0/M3-D)

- Estimator: `w = exp(logp − logq) · 1_A`; `M2 = mean(w²)`; `L_j = mean((w·1_j)²)`; **M2 = Σ_j L_j** verified per arm.
- `delta_theta = 0.20` (frozen step), ESS_grad = 20, bootstrap direction rule, fixed-weight Layer A, CRN semantics, legality checker — all untouched (firewall, task Sec. 4).
- Reference label rule: frozen `label_state(tau = 0.01, margin_min = 0.05, hold_window = 0.03, se_mult = 2.0)` — the label embeds statistical support (both required contrasts ≥ 2× paired SE) and the direction margin ≥ 0.05; failures demote to REFERENCE_AMBIGUOUS.

## 4. Axis A (Decision) construction

**Eligibility (task Sec. 10):**

- WIDEN / SHRINK: frozen label WIDEN / SHRINK (support + margin ≥ 0.05 embedded) **and** the reference action is the realized-best action in ≥ 0.80 of the 8 headline replicates.
- HOLD: frozen label HOLD (reference indifference: both perturbations within ±3% of BASE) **and** ≥ 0.80 of the 8 replicates place both perturbation arms within ±5% of BASE (the corrected BV-v0 stability semantics, reused verbatim).

**Selection (task Sec. 11, deterministic only):** eligible → maximize config coverage (≥ 4 distinct configs per class, ≤ 2 states per (config, class)) → larger headline stability → larger reference margin → deterministic `(config_id, s2)` order. The algorithm is the verbatim replay of the BV-v0 locked rule; the resulting selection is **bit-identical to the recorded BV-v0 8/8/8 selection** (cross-check in the analysis output).

**Gates (task Sec. 15):** D0 validity (tag, task/lock-before-science, source hashes, legality, M2 = ΣL, no leakage, full pytest), D1 diversity (exactly 8/8/8), D2 stability (every selected state ≥ 0.80; every HOLD state satisfies the frozen indifference-stability rule). **No Oracle-vs-fixed feasibility gate is imposed on Axis A** — it exists only for action correctness.

## 5. Axis B (Value) construction

**Eligibility (task Sec. 12):** WIDEN / SHRINK only; frozen label (statistical support + reference margin ≥ 0.05 embedded) and headline realized-best stability ≥ 0.80. The hard margin default is 0.05; the count of states with margin ≥ 0.10 is reported as a preferred-stronger diagnostic (not a gate).

**Selection (task Sec. 13/14):** 12 WIDEN + 12 SHRINK; ≥ 4 distinct configs per class; ≤ 3 states per (config, class); deterministic order: eligible → coverage → larger stability → larger margin → `(config_id, s2)`. **Oracle feasibility is checked after deterministic selection; manual selection for headroom is forbidden** (task Sec. 14/19).

## 6. Unified value functional (one functional only)

Task Sec. 9 — the same functional selects BestFixed and measures Oracle headroom:

```
J(π) = median_state [ median_replicate log( M2(π) / M2(BASE) ) ]
```

- trial unit = (state, replicate); the log-ratio is paired per replicate (CRN-matched within replicate);
- per-state summary = median over the 8 replicates; global summary = median over the 24 Axis-B states;
- fixed policies: ALWAYS_WIDEN / ALWAYS_SHRINK / ALWAYS_HOLD (arms `widen` / `shrink` / `base`);
- Oracle = the per-state frozen reference action arm;
- `BestFixed = argmin_{f} J(f)` over the three fixed policies;
- `G_Oracle = J(BestFixed) − J(Oracle)`.

J(ALWAYS_HOLD) = 0 exactly (log(M2(BASE)/M2(BASE)) per replicate). No other aggregation is used for either BestFixed selection or headroom measurement.

## 7. Axis B gates (task Sec. 16–18)

| Gate | Requirement | Form used |
|---|---|---|
| V0 | 12W + 12S deterministic, legal, stable, margin ≥ 0.05, coverage, no controller | recorded |
| V1 | fixed-rule tradeoff: J of the 3 fixed rules + class-conditional performance; weak flag if one fixed rule dominates both classes | diagnostic |
| V2 | `G_Oracle ≥ −log(0.95) = 0.0512933` | the one locked form (equivalent ratio `exp(−G_Oracle) ≤ 0.95` is the same statement) |
| V3 | opposite-class regret: `R_opp,W ≥ 1.05` **and** `R_opp,S ≥ 1.05`, where | paired replicate-level ratios, median over 8 replicates per state, median over class states |

```
R_opp,W = median_{W states} M2(ALWAYS_SHRINK)/M2(ALWAYS_WIDEN)
R_opp,S = median_{S states} M2(ALWAYS_WIDEN)/M2(ALWAYS_SHRINK)
```

V2 and V3 together replace the BV-v0 strict-win logic: adaptive value is measured through aggregate objective improvement + opposite-class regret, never by demanding impossible strict wins on same-action states (task Sec. 19).

## 8. Negative-result discipline

After outcome inspection the following are forbidden (task Sec. 31): changing the 12W/12S balance, reintroducing HOLD to rescue the Oracle metric, changing the unified objective, the Oracle threshold, the opposite-class regret threshold, config coverage, dropping states, changing the evaluation budget or margin threshold. Any amendment must be committed before additional characterization and must state observed outcomes. No amendment after controller results exist.

## 9. Outputs and provenance

| Output | Path |
|---|---|
| reuse record (B2) | `results/phase_m3bv2/reuse_record.json` |
| decision analysis (B3) | `results/phase_m3bv2/decision_analysis.json` |
| value analysis (B4–B7) | `results/phase_m3bv2/value_analysis.json` |
| decision freeze | `docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.md/.json` |
| value freeze | `docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.md/.json` |
| benchmark configs | `configs/phase_m3bv2/m3bv2_decision_benchmark.json`, `m3bv2_value_benchmark.json` |
| figures | `figures/phase_m3bv2/` (all 10: BV2-D1…D4, BV2-V1…V6; D4 confusion matrix and V6 captured headroom are controller-stage figures produced post-freeze) |
| tests | `tests/test_m3bv2_benchmark.py` (18 required names, task Sec. 27) |

All freeze JSONs carry a self-recorded `freeze_sha256_of_body_above` (hash of the JSON with that field stripped, `json.dumps(indent=1)`), the repo-standard pattern also used by the M3-D freeze.

**Controller runs on BV2: 0.**
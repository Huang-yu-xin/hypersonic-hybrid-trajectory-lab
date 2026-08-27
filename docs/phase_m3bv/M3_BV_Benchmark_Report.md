# M3-BV Benchmark Report — Negative Result (Case A)

> **Stage:** M3-BV — Adaptive-Value Benchmark Redesign
> **Outcome:** **BV-3 FAIL** ⇒ benchmark = **VALUE-INFEASIBLE** ⇒ **STOP before controller evaluation** (task Sec. 13, 26 Case A, 30)
> **Date:** 2026-08-27 ｜ Branch `feature/phase-m3bv-adaptive-value-benchmark`

---

## 1. Preregistration chain (all locked before any characterization)

| Item | Value |
|---|---|
| M3-G-v1 tag | `RareTopo-M3-G-v1` (peeled `4505a36`) ✓ |
| M3-BV task commit | `4a4384c` (docs/phase_m3bv/M3_BV_Adaptive_Value_Benchmark_Redesign_Task.md + configs/phase_m3bv/m3bv_construction_lock.json) |
| Candidate grid | 8 frozen event configs × `s2_grid_bv = [0.65, 0.85, 1.10, 1.40, 1.80, 2.30, 3.00, 4.00, 5.00, 6.40, 8.00]` (max 88) |
| Reference budget | **N_ref = 500,000 / arm**, 20 CRN batches (frozen `BATCHES_REF`) |
| Headline budget | **100,000 / arm** (frozen `final_eval_n`), 10 batches, **8 matched replicates**, rng `[701001+idx, 10000+rep]` |
| Label rule | Frozen `label_state` (tau=0.01, margin_min=0.05, hold_window=±3%, support ≥2× paired SE) |
| delta_theta | 0.20 (frozen) |

## 2. Construction executed (B2–B4)

- **Legality:** 88 / 88 candidates pass; **all three arms** (BASE/WIDEN/SHRINK) legal per state; 0 `ILLEGAL_PRE_FREEZE`; 8/8 selected-mode cross-checks vs archived M1-D variance-selector records match.
- **Reference (B3):** 88 states × 3 arms × 500k — `M2 = Σ_j L_j` verified on **264 / 264** arms (1e-9 tolerance). Label distribution: **WIDEN 42, SHRINK 27, HOLD 12, REFERENCE_AMBIGUOUS 7**.
- **Headline stability (B4):** 88 states × 8 matched replicates × 100k/arm.

## 3. Classification and stability (B5)

| Class | Reference labels | Eligible (label + stability rule) | Eligibility rule |
|---|---|---|---|
| WIDEN | 42 | **42** | label WIDEN AND realized best in ≥8/8? (≥0.8) replicates |
| SHRINK | 27 | **27** | mirrored |
| HOLD | 12 | **12** | label HOLD (reference ±3% indifference) AND ≥0.8 replicates with both perturbations inside ±5% of BASE |

**BV-1 PASS** (all classes ≥ 8 eligible+stable).

## 4. Selection (B7) — deterministic, coverage-aware

Locked rule replayed exactly (config ascending; ≤2 states per config; stability → margin → (config_id, s2) tiebreaks; fill pass). Selected **8 / 8 / 8**:

| Class | Selected (config, s2) | Configs | Max per config |
|---|---|---|---|
| WIDEN | c000{0.65,0.85}, c001{0.65,0.85}, c004{0.65,0.85}, c006{0.65,0.85} | 4 | 2 |
| SHRINK | c000{6.4,8.0}, c001{6.4,8.0}, c004{6.4,8.0}, c006{6.4,8.0} | 4 | 2 |
| HOLD | c000{3.0}, c001{3.0}, c004{2.3,3.0}, c006{2.3,3.0}, c007{3.0}, c010{3.0} | 6 | 2 |

**BV-2 PASS:** all 24 selected states have headline stability fraction **1.000** (≥ 0.8 required).

## 5. Oracle headroom audit (B6) — BV-3 FAIL

Oracle = frozen reference action per state. Fixed policies: ALWAYS_WIDEN / ALWAYS_SHRINK / ALWAYS_HOLD.
BestFixed (frozen median aggregation over the selected 24 states): **ALWAYS_WIDEN** (global median M2 = 6.2651; Oracle 5.9206).

```text
median_state [median_replicate M2(Oracle)/M2(BestFixed)] = 0.9946   (> 0.95  →  FAIL)
Oracle wins / losses / ties                                       = 14 / 2 / 8   (< 16   →  FAIL)
```

### Structural decomposition (identical pathology to M3-VA)

| Class | Wins | Ratio structure | Why |
|---|---|---|---|
| WIDEN | 0/8 | 8 **constructive ties** (ratio 1.0000) | Oracle arm ≡ ALWAYS_WIDEN arm on every WIDEN state → identical M2; a tie is architecturally unavoidable whenever the globally best fixed policy is ALWAYS_WIDEN |
| SHRINK | 8/8 | ratios 0.867–0.937 | Real headroom ≈ −9% to −13%, fully captured by a fixed SHRINK policy on those states |
| HOLD | 6/8 | ratios ≈ 0.991–0.999 | Real but marginal headroom (margins ~0.1–1.5%); 2 losses: c006 s2=2.3 (**−0.66%**), c010 s2=3.0 (**−0.08%**) |

Even in the best case (HOLD 8/8), constructive WIDEN ties cap wins at 8 + 8 + 8 = 16 with two ratio-1.0 states — and here 2 HOLD losses drop wins to 14 while the ratio median is pinned at 0.9946 by the 8 ties plus near-unity HOLD ratios.

## 6. Gate status

| Gate | Result |
|---|---|
| BV-0 validity (tag, task-before-science, grid locked, legality, estimators/CRN frozen, M2=ΣL, no controller use) | **PASS** |
| BV-1 sign diversity (≥8 stable per class) | **PASS** (42/27/12 eligible) |
| BV-2 evaluation-budget action stability | **PASS** (24/24 at 1.000) |
| BV-3 Oracle headroom (≤0.95 AND ≥16/24) | **FAIL** (0.9946; 14/24) |
| Strong target (≤0.90, report only) | NOT MET (0.9946) |

## 7. Decision — Case A (task Sec. 26)

```text
Benchmark redesign unsuccessful in the tested family:
the tested candidate family does not provide sufficient stable adaptive-value
headroom under the frozen evaluation protocol.
```

- **No benchmark freeze artifacts created** (`M3_BV_Benchmark_Freeze.md/.json`, `m3bv_benchmark_v0.json` absent by design).
- **Controller runs = 0.** M3-G-v1 is NOT evaluated on this benchmark.
- **M3-Q not started.**
- No threshold, budget, label-tolerance, stability-criterion, state, or coverage-rule relaxation applied after outcome inspection (task Sec. 28 discipline).

## 8. Root-cause diagnosis for future redesign (pre-registered limits only)

1. **WIDEN-class constructive ties are irreducible while BestFixed = ALWAYS_WIDEN.** Any benchmark whose WIDEN states select the widen arm as reference makes the Oracle coincide with the fixed widener on those states. The gate's win logic then cannot count them. (M3-VA already showed this on the old benchmark; the new benchmark reproduces it at 8/8 states.)
2. **HOLD headroom is real but below evaluation-budget noise resolution.** Median HOLD margins ≈ 0.1–1.5% at the 100k/arm headline budget produce ratios ≈ 0.99–1.00 and occasional ±0.7% flips — the exact "label resolution ≳ evaluation noise resolution" imbalance the task (Sec. 8) targeted, but the frozen event family + 100k/arm budget cannot separate them at 0.95-level.
3. **The only class with decisive headroom (SHRINK, −9–13%) is already capturable by a fixed policy**, so it contributes no *adaptive* value over BestFixed once a fixed SHRINK arm is available.

## 9. Diagnostics & figures

All diagnostics under `results/phase_m3bv/reference/` (untracked per repo policy):
`m3bv_candidate_pool.json`, `m3bv_headline_stability.json`, `m3bv_analysis.json`.

Figures (8/8, `figures/phase_m3bv/`):
BV-1 reference M2 curves ・ BV-2 class map over (config, s2) ・ BV-3 margin distribution ・ BV-4 headline action stability ・ BV-5 HOLD indifference ・ BV-6 Oracle vs BestFixed per-state ratio ・ BV-7 headroom by class ・ BV-8 selected coverage.

## 10. Claims (task Sec. 27 negative-result wording)

> The tested candidate family (8 frozen event configs × 11 scalar scales, N_ref=500k/arm, headline 100k/arm × 8 replicates) does not provide sufficient stable adaptive-value headroom under the frozen evaluation protocol: the benchmark Oracle fails its own gate (median ratio 0.9946 > 0.95; wins 14/24 < 16), primarily due to constructive WIDEN ties against the best fixed policy (ALWAYS_WIDEN) and sub-noise HOLD margins.

NOT claimed: controller superiority, real-system generalization, universal adaptive advantage, full-matrix validity, or any benchmark amendment.
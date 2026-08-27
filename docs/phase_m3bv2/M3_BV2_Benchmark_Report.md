# M3-BV2 Benchmark Report — Decision (Axis A) + Value (Axis B) construction results and controller evaluation

> **Stage:** M3-BV2 ｜ **Status:** both benchmarks constructed and frozen; **controller evaluation executed post-freeze on approval** (task Sec. 22–25)
> **Preregistration commit:** `37d17bc` ｜ **Construction/freeze commit:** `2e814a5` ｜ **Controller evaluation commit:** see Final Report
> **Sources:** BV-v0 prior characterization reused and recorded (`results/phase_m3bv2/reuse_record.json`, REUSE_OK)
> **Analysis outputs:** `results/phase_m3bv2/decision_analysis.json`, `results/phase_m3bv2/value_analysis.json`, `results/phase_m3bv2/controller_evaluation.json`

---

## 1. Axis A — Decision benchmark (8 W / 8 H / 8 S)

### Eligibility (frozen label + headline stability ≥ 0.80)

| Class | Reference labels | Eligible + stable |
|---|---|---|
| WIDEN | 42 | **42** |
| HOLD | 12 | **12** |
| SHRINK | 27 | **27** |

### Selected states (deterministic, coverage-aware; bit-identical replay of the BV-v0 selection)

| Class | (config, s2) | Configs | Max/config |
|---|---|---|---|
| WIDEN | c000{0.65,0.85}, c001{0.65,0.85}, c004{0.65,0.85}, c006{0.65,0.85} | 4 | 2 |
| HOLD | c000{3.0}, c001{3.0}, c004{2.3,3.0}, c006{2.3,3.0}, c007{3.0}, c010{3.0} | 6 | 2 |
| SHRINK | c000{6.4,8.0}, c001{6.4,8.0}, c004{6.4,8.0}, c006{6.4,8.0} | 4 | 2 |

All 24 selected states have headline stability fraction **1.000** (≥ 0.80 required); all 8 HOLD states satisfy the frozen reference-indifference rule (hold_window = ±3%) and the headline ±5% indifference rule.

### Gates

| Gate | Result |
|---|---|
| BV2-D0 validity (tag, task-before-science, source hashes, legality, M2 = ΣL, no leakage, full pytest) | **PASS** |
| BV2-D1 diversity 8/8/8 | **PASS** |
| BV2-D2 stability ≥ 0.80 + HOLD indifference rule | **PASS** |
| (no Oracle-vs-fixed gate — by design, Axis A is decision correctness only) | — |

## 2. Axis B — Value benchmark (12 W / 12 S)

### Eligibility

| Class | Reference labels | Eligible + stable |
|---|---|---|
| WIDEN | 42 | **42** |
| SHRINK | 27 | **27** |

### Selected states (deterministic; ≥ 4 configs/class, ≤ 3 states/config)

| Class | (config, s2) | Configs | Max/config | margin ≥ 0.10 |
|---|---|---|---|---|
| WIDEN | c000{0.65,0.85,1.10}, c001{0.65,0.85,1.10}, c004{0.65,0.85,1.10}, c006{0.65,0.85,1.10} | 4 | 3 | **12/12** |
| SHRINK | c000{5.0,6.4,8.0}, c001{5.0,6.4,8.0}, c004{5.0,6.4,8.0}, c006{5.0,6.4,8.0} | 4 | 3 | **8/12** |

All 24 states: reference margin ≥ 0.05 (frozen label embeds it; diagnostic: WIDEN 12/12 ≥ 0.10, SHRINK 8/12 ≥ 0.10), headline stability = 1.000.

### Unified functional and BestFixed

```
J(π) = median_state [ median_replicate log( M2(π) / M2(BASE) ) ],  24 value states
```

| Policy | J |
|---|---|
| ALWAYS_WIDEN | −0.014791 |
| ALWAYS_HOLD | 0.000000 |
| ALWAYS_SHRINK | +0.022431 |
| **ORACLE (frozen reference actions)** | **−0.068943** |

**BestFixed = ALWAYS_WIDEN** (argmin J over the fixed policies).

### BV2-V1 fixed-rule tradeoff (class-conditional J)

| Class | J(ORACLE) | J(ALWAYS_WIDEN) | J(ALWAYS_SHRINK) | J(ALWAYS_HOLD) |
|---|---|---|---|---|
| WIDEN (12) | −0.13609 | −0.13609 | +0.15792 | 0.0 |
| SHRINK (12) | −0.05414 | +0.06498 | −0.05414 | 0.0 |

Best fixed per class: WIDEN class → ALWAYS_WIDEN; SHRINK class → ALWAYS_SHRINK. **Weak flag (one fixed rule dominates both classes): FALSE.** Note the structural identity: on W states the Oracle *is* the WIDEN arm (J identical to ALWAYS_WIDEN); on S states it is the SHRINK arm — exactly the designed symmetry.

### BV2-V2 Oracle feasibility

```text
G_Oracle = J(BestFixed) − J(Oracle) = (−0.014791) − (−0.068943) = 0.054152
threshold = −log(0.95) = 0.051293
→ G_Oracle ≥ threshold          PASS
equivalent ratio exp(−G_Oracle) = 0.947288  ≤ 0.95      PASS
strong target ratio ≤ 0.90 (report only):  NOT MET (0.9473)
diagnostic median of per-state paired ratios: 0.97519 (report only;
the gated form is the J-equivalent ratio above)
```

### BV2-V3 opposite-class regret

```text
R_opp,W = median over W states of M2(ALWAYS_SHRINK)/M2(ALWAYS_WIDEN) = 1.34725  ≥ 1.05  PASS
R_opp,S = median over S states of M2(ALWAYS_WIDEN)/M2(ALWAYS_SHRINK) = 1.12684  ≥ 1.05  PASS
```

One fixed direction cannot serve both classes: on WIDEN states the fixed shrinker is ~35% worse than the fixed widener (median), while on SHRINK states the fixed widener is ~13% worse than the fixed shrinker.

### Gates summary

| Gate | Result |
|---|---|
| BV2-V0 validity (12/12 deterministic, legal, stable, margin ≥ 0.05, coverage, no controller) | **PASS** |
| BV2-V1 fixed-rule tradeoff (no single fixed rule dominates both classes) | **PASS** (weak flag FALSE) |
| BV2-V2 Oracle feasibility (G_Oracle ≥ −log(0.95)) | **PASS** (0.054152 ≥ 0.051293) |
| BV2-V3 opposite-class regret (R_opp,W / R_opp,S ≥ 1.05) | **PASS** (1.34725 / 1.12684) |

## 3. Freeze artifacts

| Artifact | Body sha256 |
|---|---|
| `docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.json` | self-recorded `freeze_sha256_of_body_above` (regenerated value at final generation: `54c3da78…`) |
| `docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.json` | self-recorded `freeze_sha256_of_body_above` (regenerated value at final generation: `de2e00b3…`) |
| `configs/phase_m3bv2/m3bv2_decision_benchmark.json` / `m3bv2_value_benchmark.json` | consumption configs, state sets match freeze |

Committed at `2e814a5` after the full test suite passed (**1213 passed**).

## 4. Decision — Case C pathway enabled (task Sec. 26)

```text
Case A (decision fails):            not triggered — Axis A PASS
Case B (value Oracle infeasible):   not triggered — Axis B PASS
→ both benchmarks frozen; NO controller had run on either axis at freeze time.
```

The BV-v0 structural obstruction is resolved: by removing the near-indifferent HOLD class from the value benchmark (12W/12S), the decisive SHRINK headroom now drives the median below the frozen 0.95 gate. The value benchmark is **Oracle-feasible** for the first time, without any threshold, budget, margin, coverage, or selection-rule relaxation.

---

## 5. Controller evaluation (post-freeze, after checkpoint approval)

### 5.1 Protocol (recorded in `controller_evaluation.json`)

- Controllers: ORACLE, ALWAYS_WIDEN, ALWAYS_SHRINK, ALWAYS_HOLD, M3-D (frozen raw gradient decision), M3-G-v1 (GA1 / rho = 0.02 gain gate).
- Decision per (state, replicate r): seed = **3031 + (r−1)** (the frozen M3-G-v1 confirmatory seeds), pilot 20k / alpha 0.5, bootstrap `[seed, 424243]`, CI-sign + ESS ≥ 20.
- Evaluation of the decided arm: benchmark-matched streams `[701001 + idx, 10000 + r]` × 100k × 10 batches, reproducing the frozen `crn_batched_eval` draw order → per-replicate M2 is bit-identical to the frozen characterization (verified: |Δ| ≤ 3.7e-10 vs the 9-decimal stored values, i.e., pure rounding).
- Fixed policies and Oracle use the frozen characterization replicate M2 (same streams): their J values **reproduce the freeze exactly** (ALWAYS_WIDEN −0.014791, ALWAYS_SHRINK +0.022431, ALWAYS_HOLD 0.0, ORACLE −0.068943) — a full internal consistency check.
- Runs: 32 unique state blocks (Axis A ∪ Axis B), 192 Axis-A trials, 192 Axis-B trials; deployable budget per trial = pilot 20k + eval 100k.

### 5.2 Axis A — decision correctness (task Sec. 23)

M3-G-v1 (192 decisions, one per (state, replicate)) vs the frozen labels:

| Class (true) | WIDEN predicted | HOLD predicted | SHRINK predicted | recall |
|---|---|---|---|---|
| WIDEN | 56 | 8 | 0 | **0.875** |
| HOLD | 0 | 64 | 0 | **1.000** |
| SHRINK | 0 | 0 | 64 | **1.000** |

- Accuracy **0.9583**, balanced accuracy **0.9583**, macro-F1 **0.9582**.
- The 8 WIDEN-class non-matches are all `HOLD_LOW_ESS` abstentions (ESS_grad < 20 on the pilot at c000@0.65, c001@0.65, c006@0.65, c006@0.85); **no opposite-direction action was ever deployed**.
- M3-D comparator: recall W 0.875 / **H 0.25** / S 1.0, balanced 0.7083, macro-F1 0.6631. The M3-G-v1 gain gate (`HOLD_GAIN`, gain proxy < rho = 0.02 on 48 of 192 trials) **recovered HOLD on 6 of 8 HOLD states where the raw gradient had deployed a wrong active direction** — the frozen "HOLD recovery" signature reproduced on the BV2 decision benchmark.

### 5.3 Axis B — adaptive-value capture (task Sec. 24/25)

Unified functional `J(π) = median_state [median_replicate log(M2(π)/M2(BASE))]`, measured on the benchmark-matched streams:

| Controller | J | vs BestFixed |
|---|---|---|
| ALWAYS_WIDEN (BestFixed) | −0.014791 | — |
| ALWAYS_HOLD | 0.000000 | — |
| ALWAYS_SHRINK | +0.022431 | — |
| ORACLE | −0.068943 | G_Oracle = 0.054152 |
| M3-D | −0.067351 | G = 0.052560 |
| **M3-G-v1** | **−0.067351** | **G_v1 = 0.052560** |

- **G_v1 = 0.052560 = 97.1% of the Oracle headroom** (Capture = G_v1 / G_Oracle = 0.9706).
- **BV2-C1 gate: PASS** — capture ≥ 50% AND J(M3-G-v1) < J(BestFixed) (task Sec. 25). Strong target (capture ≥ 75%) also met.
- M3-D ≡ M3-G-v1 on Axis B (the gain gate executed every active direction; no HOLD_GAIN triggered on the 24 value states) — the value capture is produced by the shared frozen gradient-decision layer.
- Per-class action quality on the value states: 184/192 decisions equal the reference action; the only 8 deviations are HOLD_LOW_ESS folds (no direction errors).
- VRF_budget (deployed arm; budget = pilot 20k + eval 100k): per-state medians 0.0043–0.0171, across-state median **0.0084**.

### 5.4 Case C (task Sec. 26)

```text
Both benchmarks pass AND M3-G-v1 captures large headroom (97.1% >= 50%)
⇒ Case C: the scalar first-order policy has real adaptive value on the
  frozen decision/value benchmarks.
⇒ Freeze the positive result before any M3-Q; M3-Q is NOT started.
```
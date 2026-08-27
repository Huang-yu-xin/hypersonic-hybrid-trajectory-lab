# M3-BV2 Final Report — First Mandatory Checkpoint (benchmark-only)

> **Stage:** M3-BV2 ｜ **Divergence from BV-v0:** dual-axis separation of decision correctness from adaptive economic value
> **Outcome:** **Axis A (Decision) frozen — PASS. Axis B (Value) frozen — PASS (Oracle feasibility achieved).**
> **Status:** STOP AND REPORT. **No controller has been evaluated on BV2 (controller runs = 0).**

---

## 1. Summary

M3-BV-v0 established that one balanced 8W/8H/8S benchmark cannot serve both action-correctness and adaptive-value questions: constructive WIDEN ties and near-indifferent HOLD states made the median-ratio ≤ 0.95 gate structurally unattainable regardless of label quality (a benchmark-metric architecture issue, not a controller result; frozen as `RareTopo-M3-BV-v0`).

BV2 separates the questions:

- **Axis A — Decision (8W/8H/8S):** reuses the byte-identical BV-v0 candidate characterization (recorded as prior data) and replays the frozen selection rule bit-identically. D0/D1/D2 all pass; every selected state has stability 1.000.
- **Axis B — Value (12W/12S, no HOLD):** the same candidate family, with HOLD removed from the value metric. Under the unified functional

  ```
  J(π) = median_state [ median_replicate log( M2(π) / M2(BASE) ) ]
  ```

  BestFixed = ALWAYS_WIDEN (J = −0.0148), Oracle J = −0.0689, **G_Oracle = 0.0542 ≥ −log(0.95) = 0.0513 → BV2-V2 PASS** (equivalent ratio 0.9473 ≤ 0.95). Opposite-class regret R_opp,W = 1.347 / R_opp,S = 1.127 ≥ 1.05 → **BV2-V3 PASS**; no single fixed rule dominates both classes (V1 weak flag FALSE). **V0–V3 all PASS → value benchmark Oracle-feasible and frozen.**

No gate, threshold, budget, margin, coverage, or selection rule was relaxed; nothing was re-selected after seeing results; no controller output was used anywhere.

## 2. First Mandatory Checkpoint (task Sec. 33)

| Item | Result |
|---|---|
| M3-BV-v0 correction commit | `1eea183` "Correct M3-BV headroom interpretation and finalize negative result" |
| `RareTopo-M3-BV-v0` tag | created (annotated) and pushed to origin |
| BV2 branch | `feature/phase-m3bv2-dual-axis-benchmark` |
| BV2 task commit | `37d17bc` (task doc + construction lock, PREREGISTERED) |
| candidate source | BV-v0 pool + headline characterization reused, byte-identity verified, recorded as prior data (REUSE_OK, `results/phase_m3bv2/reuse_record.json`) |
| Decision eligible W/H/S | 42 / 12 / 27 |
| Decision selected | **8 / 8 / 8** |
| Decision config coverage | W 4, H 6, S 4 configs (≤ 2 per config) — PASS |
| BV2-D0/D1/D2 | **PASS / PASS / PASS** |
| Value eligible W/S | 42 / 27 |
| Value selected | **12 / 12** |
| Value config coverage | 4 / 4 configs (≤ 3 per config) — PASS |
| unified functional | `median_state [median_replicate log(M2(π)/M2(BASE))]` — one functional for BestFixed and Oracle headroom |
| BestFixed | **ALWAYS_WIDEN** (J = −0.014791) |
| J(Oracle) | **−0.068943** |
| Oracle headroom | **G_Oracle = 0.054152** (threshold 0.051293; equivalent ratio 0.947288) |
| opposite-class regret W | **1.34725** (≥ 1.05) |
| opposite-class regret S | **1.12684** (≥ 1.05) |
| BV2-V0/V1/V2/V3 | **PASS / PASS / PASS / PASS** |
| Decision freeze commit | `2e814a5` (with construction, tests, and both freezes) |
| Value freeze commit | `2e814a5` (same commit; separate artifacts) |
| full pytest | **1213 passed, 0 failed** (incl. 18 `test_m3bv2_*` tests) |
| controller runs on BV2 | **0** |

## 3. Freeze artifacts

- Decision: `docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.md|.json` + `configs/phase_m3bv2/m3bv2_decision_benchmark.json`
- Value: `docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.md|.json` + `configs/phase_m3bv2/m3bv2_value_benchmark.json`

Both freeze JSONs self-record `freeze_sha256_of_body_above`, parent tags, source hashes, gates, `controller_runs_on_bv2 = 0`, and the seal declaration (no state replacement / metric / functional / margin change; no controller-informed amendment).

## 4. Claim (task Sec. 30 — benchmark freeze wording)

> We constructed separate preregistered decision and adaptive-value benchmarks: the decision benchmark (Axis A, 8W/8H/8S) tests stable WIDEN/HOLD/SHRINK action correctness, while the value benchmark (Axis B, 12W/12S) tests measurable WIDEN/SHRINK switching advantage over one globally fixed scalar action rule under a unified objective.

NOT claimed: controller superiority of any kind, real-system generalization, or universal adaptive advantage. Controller evaluation is a separate, approval-gated stage.

## 5. What was NOT done (discipline record)

- No controller evaluated on either axis (M3-G-v1, M3-D, Always-Widen/Shrink/Hold, Oracle) — **0 runs**.
- No amendment to the 12W/12S balance, unified objective, thresholds, coverage, margin, budget; no state dropped or replaced after outcome inspection.
- No M3-Q started. No rho tuning. No use of controller performance during selection.
- The BV-v0 negative result is preserved and frozen (tag `RareTopo-M3-BV-v0`); BV2 did not overwrite it.

## 6. Next step (blocked on approval)

Per task Sec. 22/32/33: only after explicit approval may the frozen controllers be evaluated on the frozen benchmarks:

1. Axis A: W/H/S decision correctness of M3-G-v1 (recall, balanced accuracy, macro-F1, confusion matrix, HOLD_GAIN).
2. Axis B: Oracle-headroom capture of M3-G-v1 — `Capture = G_v1 / G_Oracle` with the same unified functional J (gate BV2-C1: capture ≥ 50%, J(v1) < J(BestFixed)).

Do NOT start M3-Q yet.
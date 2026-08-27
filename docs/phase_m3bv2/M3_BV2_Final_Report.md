# M3-BV2 Final Report — benchmark freeze + controller evaluation (Case C)

> **Stage:** M3-BV2 ｜ **Divergence from BV-v0:** dual-axis separation of decision correctness from adaptive economic value
> **Outcome:** **Axis A (Decision) frozen — PASS. Axis B (Value) frozen — PASS (Oracle feasibility achieved). Controller evaluation: M3-G-v1 captures 97.1% of the Oracle headroom — Case C.**
> **Status:** checkpoint passed; controller evaluation executed on approval; **M3-Q NOT started** (firewall).

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

No gate, threshold, budget, margin, coverage, or selection rule was relaxed; nothing was re-selected after seeing results; no controller output was used anywhere in benchmark construction.

After the checkpoint approval, the frozen controllers were evaluated (section 5): M3-G-v1 preserves strong decision correctness on Axis A (balanced accuracy 0.958, no opposite-direction action) and captures **97.1%** of the Oracle adaptive-value headroom on Axis B (BV2-C1 PASS) — **Case C**.

## 2. First Mandatory Checkpoint (task Sec. 33) — re-issued after controller evaluation

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
| full pytest | **1213 passed, 0 failed** at freeze; +3 controller tests → **1216 passed** after evaluation (see section 6) |
| controller runs on BV2 | **0 at freeze time**; after approval: **32 unique-state blocks, 192 Axis-A trials + 192 Axis-B trials** (recorded in `controller_evaluation.json`) |

## 3. Freeze artifacts

- Decision: `docs/phase_m3bv2/M3_BV2_Decision_Benchmark_Freeze.md|.json` + `configs/phase_m3bv2/m3bv2_decision_benchmark.json`
- Value: `docs/phase_m3bv2/M3_BV2_Value_Benchmark_Freeze.md|.json` + `configs/phase_m3bv2/m3bv2_value_benchmark.json`

Both freeze JSONs self-record `freeze_sha256_of_body_above`, parent tags, source hashes, gates, `controller_runs_on_bv2 = 0`, and the seal declaration (no state replacement / metric / functional / margin change; no controller-informed amendment).

## 4. Claim (task Sec. 30 — benchmark freeze wording)

> We constructed separate preregistered decision and adaptive-value benchmarks: the decision benchmark (Axis A, 8W/8H/8S) tests stable WIDEN/HOLD/SHRINK action correctness, while the value benchmark (Axis B, 12W/12S) tests measurable WIDEN/SHRINK switching advantage over one globally fixed scalar action rule under a unified objective.

NOT claimed: real-system generalization or universal adaptive advantage beyond the frozen benchmarks. Controller evaluation was executed on approval with the frozen controllers only (section 5); no controller-informed amendment of any benchmark artifact occurred.

## 5. Controller evaluation results (post-freeze, task Sec. 22–25)

### Axis A — decision correctness (M3-G-v1, 192 decisions)

| Class | recall | notes |
|---|---|---|
| WIDEN | 0.875 | 8/64 non-matches are all `HOLD_LOW_ESS` abstentions; **zero opposite-direction actions** |
| HOLD | 1.000 | gain gate `HOLD_GAIN` recovers 6/8 HOLD states that the raw gradient (M3-D) would have actively mis-fired (M3-D HOLD recall 0.25) |
| SHRINK | 1.000 | — |

Accuracy 0.9583 ・ balanced accuracy 0.9583 ・ macro-F1 0.9582.

### Axis B — value capture (unified functional J, benchmark-matched streams)

| Controller | J | headroom gain |
|---|---|---|
| BestFixed = ALWAYS_WIDEN | −0.014791 | — |
| ORACLE | −0.068943 | G_Oracle = 0.054152 |
| M3-D | −0.067351 | 0.052560 |
| M3-G-v1 | −0.067351 | **G_v1 = 0.052560** |

- **Capture = G_v1 / G_Oracle = 0.9706 (97.1%)** — BV2-C1 gate **PASS** (≥ 50% and J(v1) < J(BestFixed)); strong target (≥ 75%) also met.
- Frozen J values (fixed policies + Oracle) are reproduced exactly on the evaluation streams — full consistency of the matched-stream methodology.
- M3-D ≡ M3-G-v1 on Axis B (the gain gate executed every active direction there); on Axis A the gate's value is exactly the HOLD recovery.
- VRF_budget (deployed arm, pilot 20k + eval 100k): across-state median 0.0084.

### Case C (task Sec. 26)

```text
Both benchmarks pass AND M3-G-v1 captures large headroom (97.1% >= 50%)
⇒ Case C: the scalar first-order policy has real adaptive value.
⇒ Positive result frozen (this report + commit); M3-Q NOT started.
```

## 6. What was NOT done (discipline record)

- No amendment to the 12W/12S balance, unified objective, thresholds, coverage, margin, budget; no state dropped or replaced after outcome inspection — the freezes at `2e814a5` stand unmodified (seal).
- No M3-Q started. No rho tuning. No use of controller performance during benchmark selection.
- The BV-v0 negative result is preserved and frozen (tag `RareTopo-M3-BV-v0`); BV2 did not overwrite it.
- Controller evaluation used ONLY the frozen controllers (M3-D, M3-G-v1 GA1/rho=0.02, the three always-rules, Oracle) with the frozen decision seeds, budgets, and the benchmark-matched streams.

## 7. Test-suite evidence

```
python -m pytest -q  (after controller evaluation)
→ 1216 passed, 0 failed  (18 benchmark tests + 3 controller tests added)
```

## 8. Next step (gated for a future task)

The M3-Q decision (Case D vs Case C) is NOT triggered: M3-G-v1 decision accuracy is high (0.958 balanced) **and** value capture is large (97.1%), which matches Case C, not Case D. Any future M3-Q must be a new preregistered task; nothing here authorizes it.
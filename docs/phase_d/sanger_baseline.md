# Sanger Hybrid Baseline — FROZEN（D7B）

状态：**FROZEN**（D6 数值验证通过、D7A audit 批准、D7B 最终冻结；
tag：`sanger-baseline-v1.0`）

日期：2026-08-15
分支：`feature/phase-d-sanger-hybrid`
规范依据：`docs/phase_d/sanger_model_spec.md`（D0，source of truth）

数值验证：见 [sanger_numerical_validation.md](sanger_numerical_validation.md)
（D6：18/18 拓扑稳定）
最终报告：见 [phase_d_final_report.md](phase_d_final_report.md)（D7A/D7B）

> 本 baseline 经 D6 数值验证（18/18 numerical cases 拓扑一致）与
> D1-D9 图像视觉验收（9/9 PASS）后正式冻结。baseline 数值自 D5 起
> 未作任何更改。

## 1. Baseline definition

单条 canonical Sanger baseline：

> unpowered longitudinal lift-supported atmospheric skip trajectory，
> 事件驱动 ATM/VAC 混合，research endpoint = SRTI。

## 2. Physical parameters（D0 frozen）

| 量 | 值 |
|---|---|
| h0 | 100000 m |
| v0 | 7000 m/s |
| gamma0 | -5 deg |
| theta0 | 0 |
| K = L/D | 3 |
| m | 1000 kg |
| S | 1 m² |
| C_D | 0.2 |
| atmosphere boundary | 100000 m |
| ATM control | u_L = 1（sigma = 0） |
| VAC semantics | L = D = 0，重力与球形地球曲率保留 |

## 3. Numerical configuration（Phase C production）

```
method        = DOP853
rtol          = 1e-9
atol          = [1e-4, 1e-11, 1e-7, 1e-11]
max_step      = 20.0
dense_output  = True
```

来源：`PRODUCTION_SOLVER_CONFIG`（`src/hyptraj/simulation/numerics.py`），
import 复用，无字面量复制。

## 4. Mode sequence

```
SANGER_ATM -> SANGER_VAC -> SANGER_ATM -> SANGER_VAC -> SANGER_ATM
```

## 5. Event sequence

```
synthetic_initial_entry
atmospheric_pullout
atmosphere_exit
vacuum_apogee
atmosphere_entry
atmospheric_pullout
atmosphere_exit
vacuum_apogee
atmosphere_entry
atmospheric_pullout
srti
```

## 6. Completed skip cycles（full precision）

`skip_count = 2`

| Cycle | entry t [s] | pull-out h [m] | exit t [s] | apogee h [m] | entry₂ t [s] | ATM dt [s] | VAC dt [s] | ATM ΔR [m] | VAC ΔR [m] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.0 | 46040.885709 | 202.96413572759334 | 130352.121182 | 484.6403540462832 | 202.964136 | 281.676218 | 1352050.535955 | 1780485.405736 |
| 1 | 484.6403540462832 | 45812.093384 | 748.1137977144123 | 102232.575573 | 814.8021368979796 | 263.473444 | 66.688339 | 1616144.187272 | 391248.494882 |

Cycle 0 的 entry 为 synthetic E0（`entry_is_synthetic = True`）。

## 7. Terminal incomplete pass（E2 -> P2 -> SRTI，NOT a skip）

| 量 | 值 |
|---|---|
| entry / pullout / SRTI time [s] | 814.8021368979796 / 969.0696243196126 / 1119.5459841174863 |
| SRTI altitude [m] | 86138.741034 |
| SRTI velocity [m/s] | 5482.946114 |
| atmospheric duration [s] | 304.74384721950673 |
| range increment [m] | 1732966.696100695 |
| mechanical energy loss [J/kg] | 2880331.9789911285 |

该 pass 无 exit / VAC / re-entry，**不计入** skip_count。

## 8. Research endpoint — SRTI

```
t  = 1119.5459841174863 s
h  = 86138.741034 m
v  = 5482.946114 m/s
R  = 6872895.319945 m
gamma ≈ 0（downward crossing，+ -> -）
```

Research 指标一律在 SRTI 截止。

## 9. Compatibility ground continuation（非 research）

从 SRTI 状态用 `sanger_atm_rhs`（u_L = 1）+ 冻结 `make_ground_event`
继续到 h = 0，仅用于 compatibility / visualization：

```
ground time    = 3508.8990 s
ground range   = 13578.6818 km
ground velocity= 159.9536 m/s
duration after SRTI = 2389.35 s
range after SRTI    = 6705.79 km
compatibility_only  = true
```

**不修改** SRTI、completed cycles、research time/range；research 与
compatibility 端点严格分离。

## 10. Canonical artifacts

`results/sanger_hybrid/baseline/`（可完全由 runner 重建，未被 git 跟踪）：

```
trajectory.csv          合并时序轨迹（含 mode / segment_index，过渡点不重复）
events.csv              事件（含 mode_before/after、is_synthetic）
segments.csv            分段（含 solver 诊断 nfev/njev/nlu）
skip_cycles.csv         完成周期全量指标
summary.json            规范汇总（全精度，含 hybrid switching f_minus/f_plus/normal）
ground_continuation.csv SRTI -> ground 兼容段
ground_summary.json     兼容段汇总
figures/D1..D5.png      Phase D 基础图（300 dpi）
```

重建命令：

```bash
python experiments/04_sanger_hybrid/run_sanger_baseline.py
python experiments/04_sanger_hybrid/summarize_sanger_baseline.py
python experiments/04_sanger_hybrid/plot_sanger_baseline.py
```

## 11. Regression policy

Tracked reference：`tests/data/sanger_baseline_v1.json`（16 位有效数字，
来自当前 canonical run；数值为 numerical baseline，非 analytic truth）。

| 量 | 容差 |
|---|---|
| event time | abs ≤ 1e-3 s |
| altitude | abs ≤ 1 m |
| velocity | abs ≤ 1e-2 m/s |
| range | abs ≤ 10 m |
| gamma at extremum | abs ≤ 1e-6 rad |
| 整数 / 序列（skip_count、mode/event sequence、段数） | exact |

VAC 守恒量 ~1e-16 漂移属于 diagnostic，**不作为** frozen regression
constant；其正式 numerical threshold 由 D6 定义。

## 12. D5 Acceptance

| # | Item | Status |
|---|---|---|
| 1 | canonical baseline runner implemented | **PASS** |
| 2 | frozen IC used | **PASS** |
| 3 | production solver used（import，无字面量） | **PASS** |
| 4 | terminal_kind == SRTI | **PASS** |
| 5-9 | trajectory / events / segments / skip_cycles / summary artifacts | **PASS** |
| 10 | full precision values preserved（16 位） | **PASS** |
| 11 | regression reference JSON tracked | **PASS** |
| 12 | event sequence frozen in regression | **PASS** |
| 13 | skip_count frozen in regression | **PASS** |
| 14 | event-state regression added | **PASS** |
| 15 | cycle metric regression added | **PASS** |
| 16 | global metric regression added | **PASS** |
| 17 | research endpoint remains SRTI | **PASS** |
| 18 | compatibility ground continuation implemented | **PASS** |
| 19 | ground continuation does not alter research metrics | **PASS** |
| 20 | D1-D4 unchanged | **PASS** |
| 21 | Qian baseline unchanged | **PASS** |
| 22-26 | Figure D1-D5 generated | **PASS** |
| 27 | D5 baseline documentation written | **PASS** |
| 28 | no numerical sweep performed | **PASS** |
| 29 | no Phase E/F/predictability work | **PASS** |
| 30 | all tests PASS | **PASS** |

**D5 Acceptance：PASS（FROZEN — D6 数值验证 18/18、D7A audit 批准、D7B 最终冻结）**

---

*FROZEN（sanger-baseline-v1.0，D7B）。Phase D COMPLETE。*

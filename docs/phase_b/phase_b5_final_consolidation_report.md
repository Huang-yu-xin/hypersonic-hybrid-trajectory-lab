# Phase B.5 Final Baseline Consolidation Report

日期：2026-08-15
决策：`DECISION: FREEZE-DUAL-ENDPOINT-QIAN`（Phase B.5 审计通过）
状态：**QIAN DUAL-ENDPOINT BASELINE: FROZEN（Git tag: qian-baseline-v1.0）**

---

## 1. Approved Model Definition

三段事件驱动模式（production 实现于 `src/hyptraj`）：

```
Q0 ENTRY_CAPTURE      u_L = 1，字面式(4)动力学；
                      终止于 γ=0 首次向上穿越（direction=+1）——QEG 捕获
Q1 QEG_GLIDE          L_req = m(g − v²/r)cosγ；u_L = clip(L_req/L, 0, 1)；
                      终止于捕获后 u_L* = 1 首次向上穿越（L_req = L）
                      —— Research Terminal Interface（QEG 可行性丧失）
Q2 GROUND_CONTINUATION u_L = 1，字面式(4)动力学；自然持续至 h=0 触地事件
```

控制语义：K = L/D = 3 为**气动升阻比**；u_L = cos σ ∈ [0,1] 为有效纵向升力投影；
K_eff = K·u_L 仅作报告，永不取代气动 K。无攻角控制、无 k_γ、无 D_ref(E)、无
terminal target、无 predictor-corrector、无优化。**任何转换处不修改状态值；无高度截断。**

## 2. Mode/Event Architecture

| 事件 | 事件函数 | direction | terminal | 语义 |
| --- | --- | --- | --- | --- |
| QEG 捕获 | g = γ | +1 | 是 | 混合切换（u_L 从 1 跳变到 QEG 需求值） |
| RTI（QEG 可行性丧失） | g = L_req − L | +1 | 是 | 研究终端界面 |
| 触地 | g = r − R_e | −1 | 是 | 题面兼容端点 |

事件驱动转换，无固定时间终止、无手动截断。

## 3. Research Terminal Interface（RTI）

RTI := QEG 可行性丧失事件（L = L_req，u_L = 1）。精确事件状态存入
`metadata.research_terminal_state`（t_RTI, r_RTI, h_RTI, θ_RTI, R_RTI, v_RTI,
γ_RTI, E_RTI, q_RTI, L_RTI, L_req_RTI, u_L_RTI）；`research_terminal_reason =
"qeg_feasibility_loss"`；`qeg_feasibility_condition = "u_L_star <= 1"`。
研究指标域：[0, t_RTI]（供后续 STM / FTLE / 可预测性 / 高速敏感度 / 高速轨迹比较）。

## 4. Ground-Continuation Definition

RTI 之后 u_L=1 自然下降至 h=0。模式名 **GROUND_CONTINUATION**（不是
TERMINAL_GUIDANCE / TERMINAL_DIVE）。该段**不是生产终端制导律**，仅为与题目
地面端点指标的兼容而存在；地面指标 [0, t_ground] 仅按需报告。

## 5. Numerical Results

| 量 | 值 |
| --- | ---: |
| QEG 捕获时间 t_c | 93.429 s |
| 捕获高度/速度 | 46.041 km / 6810.80 m/s |
| RTI 时间 t_RTI | 723.038 s |
| RTI 高度/速度/射程 | 46.041 km / 3192.53 m/s / 3490.70 km |
| RTI 能量 E | −5.6955×10⁷ J/kg |
| QEG 段时长 / 射程增益 | 629.609 s / 2846.24 km |
| 触地时间 t_ground | 2017.960 s |
| 触地射程 / 速度 / γ | 5363.62 km / 159.92 m/s / −15.78° |
| 触地高度残差 | 0.000 m |
| 全程最大高度 | 100.000 km（仅 t=0；t>0 后最大 46.04 km） |

## 6. Control/Bank-Angle Statistics

- u_L 范围：[0.0664, 1.000]（QEG 段从 0.0664 单调升至 1；ENTRY 与 GROUND 段恒为 1）；
- σ = arccos(u_L)：QEG 段 max 86.19°，median 63.34°；>70° 占 38.1%，>80° 占 16.5%，
  >85° 占 3.5%（探索期结果，B.5-B1 报告）；
- K_eff = K·u_L ∈ [0.199, 3.000]。

## 7. Literal Eq.(4) Comparison

| 指标 | Literal Eq.(4) | Approved Qian（地面端点） |
| --- | ---: | ---: |
| 飞行时间 | 3508.887 s | 2017.960 s |
| 射程 | 13578.5 km | 5363.6 km |
| 触地速度 | 159.95 m/s | 159.92 m/s |
| 最大高度 | 130.41 km（出大气） | 100.00 km（不出大气 ✓） |
| 轨迹形态 | 跳跃滑翔 | 捕获→水平 QEG→自然下降 |

对比图：`fig08_literal_vs_qian_h_R.png`、`fig09_literal_vs_qian_v_t.png`。

## 8. Original-Problem Reference Comparison

| 指标 | 题面参考 | Literal | Approved Qian | 状态 |
| --- | ---: | ---: | ---: | --- |
| 射程 | 6000–8500 km | 13578.5 km | 5363.6 km | **外部比较，非硬验收** |
| 飞行时间 | 1200–1800 s | 3508.9 s | 2018.0 s | 同上 |
| 触地速度 | 800–1500 m/s | 160.0 m/s | 159.9 m/s | 同上 |

差异已明确报告：属 **model-definition / reference-table discrepancy**（题面表 2
与给定方程+参数不自洽，Phase B/B.5-A 已用 9 项检查、收敛性、独立实现、参数扫描验证）。
参考值不作为 PASS 判据。

## 9. Tests / Regressions

- `test_literal_eq4_baseline.py`（原 `test_qian_baseline.py` 重命名保留）：literal
  regression 7 项，容差 rel=1e-4；
- `test_qian_continuous_glide.py`（新增 11 项）：
  - 物理/事件不变量：三模式存在且有序、捕获事件属性（γ=0, +1, hybrid_switch）、
    RTI 元数据（reason/condition/u_L_RTI=1/L=L_req）、t>0 后不出大气、u_L∈[0,1]、
    K_aero=3 且 K_eff=K·u_L、状态连续无 NaN/Inf、触地事件 + 残差 <1e-3 m、sanity 全过；
  - 冻结数值（rel=1e-4）：t_c=93.4288 s、h_c=46040.9 m、v_c=6810.80 m/s、
    t_RTI=723.038 s、h_RTI=46040.9 m、v_RTI=3192.53 m/s、R_RTI=3490.70 km、
    t_ground=2017.960 s、R_ground=5363.62 km、v_ground=159.92 m/s；
  - 双端点指标 schema 完整。
- `pytest -q`：**35 passed**（Phase A/B 既有测试全部保留通过）。

## 10. STM/FTLE Hybrid-Event Note

- 捕获事件是**混合切换**（u_L 从 1 跳变至 QEG 需求值）：跨捕获的 STM/FTLE 必须
  计入混合事件敏感度 / **saltation matrix** 更新；
- saltation matrix **未在 Phase B.5 实现**，推迟到可预测性阶段（已记录于
  `metadata.stm_ftle_note`）；
- QEG→GROUND 转换在控制与向量场上均连续（u_L=1、γ̇=0 两侧一致），无额外混合结构；
- 事件面（γ=0、L_req−L=0、r−R_e=0）均为光滑横截，位置可定位。

## 11. Known Limitations

- 指数大气、固定 C_D、固定 K=3（气动 L/D）、二维纵向、无地球自转；
- 热载荷仍为动压积分代理量（题面定义），非真实热流；
- GROUND_CONTINUATION 段低速爬行（v_f=160 m/s）超出高超声速模型有效域——仅作题面兼容；
- 无攻角自由度；u_L∈[0,1]（无倒飞）；
- 题目表 2 参考范围与题面模型不自洽（见第 8 节）。

## 12. Files Changed

**新增**：
- `src/hyptraj/modes/continuous_glide.py`、`src/hyptraj/modes/__init__.py`（模式语义 + RHS 分发）
- `experiments/02_qian_continuous_glide/run_qian_glide.py`、`plot_qian_glide.py`
- `tests/test_models/test_qian_continuous_glide.py`
- `docs/model_audit/phase_b5_qian_continuous_glide_audit.md`、
  `docs/model_audit/phase_b5_b3_terminal_guidance_audit.md`、
  `docs/model_audit/phase_b5_b3b_drag_energy_derivation.md`、
  `docs/phase_b5_final_consolidation_report.md`（本文档）
- `experiments/01_baseline_dynamics/audit/`（B.5-A/B.5-B1/B.5-B2/B.5-B3-B 探索脚本与报告）

**修改**：
- `src/hyptraj/models/dynamics.py`：新增 `required_lift()`（基 RHS 数学含义不变）
- `src/hyptraj/simulation/events.py`：新增 `make_capture_event()`、`make_qeg_end_event()`
- `src/hyptraj/simulation/trajectory.py`：`TrajectoryResult` 增 `mode`/`control_history`
  可选字段（向后兼容）+ `integrate_qian_glide()`
- `src/hyptraj/controls/__init__.py`、`simulation/__init__.py`：导出更新
- `experiments/01_baseline_dynamics/baseline_config.py`：输出目录
  → `literal_eq4_uncontrolled`；run 脚本标题更新
- `tests/test_models/test_qian_baseline.py` → 重命名 `test_literal_eq4_baseline.py`
- `docs/model_audit/phase_b5_b3b_*.md`：TI-C codim-2 术语更正

**未改动**：字面式(4) RHS 数学含义、literal baseline 数值、T1/T2 参考、
拖拽-能量推导产物、全部 B.5 审计产物。

## 13. Frozen Baseline Identifiers

| Baseline | 类型 | 输出目录 | Regression 测试 | Git tag |
| --- | --- | --- | --- | --- |
| literal_eq4_uncontrolled | 字面式(4)无控制参考 | `results/baseline/literal_eq4_uncontrolled/` | `test_literal_eq4_baseline.py` | —（永久保留） |
| **qian_continuous_glide** | **批准双端点 Qian 基线** | `results/baseline/qian_continuous_glide/` | `test_qian_continuous_glide.py` | **qian-baseline-v1.0** |

RTI 冻结定义：QEG 可行性丧失（u_L\* = 1 向上穿越）。GROUND_CONTINUATION 冻结定义：
u_L = 1 全升力自然下降至 h=0。

# Phase F — gamma0-K Sensitivity and Hybrid-Regime Protocol

## Status

    Phase F status:       F0 COMPLETE + F0.1 COMPLETE
                          （F0.1: Qian Regime-Classification Access Amendment）
    Branch:               feature/phase-f-gamma-k-sensitivity
    Created from:         phase-e-v1.0（44a99119cf9e82e64d68b5b8abdbb4a20406c7bc）
    F0 freeze date:       2026-08-16
    Baseline anchor:      p0 = (gamma0 = -5 deg, K = 3)，即 phase-e-v1.0 冻结点
    Source of truth:      This document — Phase F 全部 sensitivity / topology
                          code / figures / claims 的唯一权威依据。

Phase F 是建立在 frozen Phase E 之上的**新研究层**。本文档冻结 gamma0 与 K 的
参数语义、computational domain、regime 分类、topology margin 定义、
boundary refinement 策略、fixed-regime derivative 策略与数值/artefact 策略。
F1–F7 的全部实现必须与本协议一致；任何冲突必须先修订本协议并重新冻结。

F0 本身**不**：运行正式 sweep、实现 sensitivity engine、修改 frozen physics、
修改 Phase E comparison code、计算 derivative、进入 F1。

F0.1（本文档 Amendment 节）**只**解决 Qian terminal/regime observability：
新增一个严格受限、backward-compatible、classification-oriented 的 Qian
research integration API；不运行 F1 slices。

---

## 1. Purpose

Phase F 的目标是**表征**（characterization）而非优化：在局部计算窗口内系统
刻画 Qian / Sanger 混合轨迹对初始弹道倾角 gamma0 与气动升阻比 K 的结构性响应，
包括：

1. 各参数点上的 hybrid regime（terminal kind、skip count、mode / event
   sequence）分类；
2. 不同 hybrid regime 之间 topology boundary 的定位与几何；
3. 同一 regime 内部的连续局部灵敏度（finite-difference derivative）；
4. Qian / Sanger 在参数空间上的 cross-model comparison surfaces（仅复用
   Phase E 协议，不新增 metric）。

后续真正的 STM / saltation / FTLE 研究**不属于 Phase F**（见 §19）。

---

## 2. Frozen Phase E anchor

Phase F 的唯一 anchor point：

    p0 = (gamma0 = -5 deg, K = 3)

对应冻结提交：

    phase-e-v1.0 = qian-sanger-comparison-v1.0 = 44a99119cf9e82e64d68b5b8abdbb4a20406c7bc

Phase E 冻结回归参考：

    tests/data/qian_sanger_comparison_v1.json

**每次 Phase F sweep runner 开始时**必须验证 p0 上 Qian / Sanger 结果与该参考在
Phase E regression tolerance 内一致，至少包含：

- Qian terminal kind = `RTI`（QEG feasibility loss）；
- Sanger terminal kind = `SRTI`（skip-capability loss）；
- Sanger `skip_count = 2`；
- Qian mode sequence = `[ENTRY_CAPTURE, QEG_GLIDE]`；
- Sanger mode sequence = `[SANGER_ATM, SANGER_VAC, SANGER_ATM, SANGER_VAC,
  SANGER_ATM]`；
- 参考中的 production values（时间/射程/能量等）在既有 tolerance 内一致。

任何不一致：**Phase F FAIL，停止整个 sweep**。

Phase E 的 physics、comparison protocols、regression snapshot、figures 与
numerical configuration 继续作为 frozen baseline，Phase F 不得移动以下 tags：

    qian-baseline-v1.0
    phase-b-v1.0
    phase-c-v1.0
    sanger-baseline-v1.0
    phase-d-v1.0
    qian-sanger-comparison-v1.0
    phase-e-v1.0

---

## 3. Parameter semantics

### 3.1 gamma0 — 初始弹道倾角（initial flight-path angle）

- 语义：t = 0 时刻的 flight-path angle。
- 只修改 `InitialCondition.flight_path_angle_deg` 对应分量；**不修改**其它任何
  初始条件。
- state ordering 继续冻结约定 `[r, theta, v, gamma]`
  （`src/hyptraj/models/dynamics.py` 与 `sanger_trajectory._initial_state`
  一致）。
- 代码内部单位为 **radians**（`np.deg2rad` 转换发生在 `integrate_qian_glide`
  与 `integrate_sanger_hybrid` 的初始状态构造中）。
- 报告 / parameter map / 文档单位为 **degrees**。

### 3.2 K — 气动升阻比（aerodynamic lift-to-drag ratio）

- 语义：`K = L / D = C_L / C_D`，无量纲；`C_L = K * C_D`、`L = q S C_L`、
  `D = q S C_D`（`src/hyptraj/models/aerodynamics.py`）。
- `ConstantKControl`（`src/hyptraj/controls/constant_k.py`）冻结校验：
  `K > 0`，否则 `ValueError("K must be positive.")`；aerodynamics 层另有
  `lift_to_drag_ratio >= 0` 校验。
- 当前 frozen baseline：`K = 3`。
- **Qian**：`ENTRY_CAPTURE` 阶段 `u_L = 1`（全部可用纵向升力）；`QEG_GLIDE`
  阶段 `K` 仍表示 aerodynamic L/D，`u_L = clip(L_req/L, 0, 1)` 只调整有效纵向
  升力投影。**禁止把 K 与 K_eff = K * u_L 混淆**（K_eff 只能被报告，绝不
  替换 aerodynamic K）。
- **Sanger**：`SANGER_ATM` 使用同一个 aerodynamic K 且 `u_L = 1`（full
  longitudinal lift，`sanger_atm_rhs` 直接委托冻结 `atmospheric_dynamics`）；
  `SANGER_VAC` 中 `L = 0`、`D = 0`，K 不进入连续动力学，但该 trajectory
  point 仍具有同一个 frozen parameter K —— 因为后续 ATM re-entry 继续使用它。

### 3.3 已审计的冻结事实（F0 代码审计记录）

| 文件 | 确认内容 |
|---|---|
| `src/hyptraj/controls/constant_k.py` | `ConstantKControl(value)`：`value <= 0` 抛错；`__call__` 返回常值 K |
| `src/hyptraj/models/dynamics.py` | `state = [r, theta, v, gamma]`；gamma 为 rad；`K = control(t, state)` 直接进入 `aerodynamic_forces`；`required_lift` 为 QEG 诊断原语 |
| `src/hyptraj/models/aerodynamics.py` | `K = C_L/C_D`；`cl = K * cd`；非负校验 |
| `src/hyptraj/modes/continuous_glide.py` | Qian 三模式 `ENTRY_CAPTURE` / `QEG_GLIDE` / `GROUND_CONTINUATION`；`qeg_lift_fraction` 返回 clip 后的 `u_L` |
| `src/hyptraj/modes/sanger_hybrid.py` | `SANGER_ATM`（full lift）/ `SANGER_VAC`（L=D=0，gravity + curvature 保留） |
| `src/hyptraj/simulation/numerics.py` | `PRODUCTION_SOLVER_CONFIG` = DOP853, rtol=1e-9, atol=[1e-4,1e-11,1e-7,1e-11], max_step=20 s, dense_output=True |
| `src/hyptraj/simulation/trajectory.py` | `integrate_qian_glide` 三段式；capture/RTI/ground 事件缺失或 solver 失败均 raise `RuntimeError`（当前无 terminal-kind 返回通道） |
| `src/hyptraj/simulation/sanger_trajectory.py` | `integrate_sanger_hybrid` 返回 `SangerHybridTrajectory`；`terminal_kind ∈ {srti, ground_before_srti, max_time, max_segments, solver_failure}`；`success = (kind == srti)` |
| `src/hyptraj/simulation/sanger_metrics.py` | `SangerTrajectoryMetrics.skip_count` = 完成的 skip cycle 数（terminal incomplete pass 不计入） |
| `src/hyptraj/analysis/comparison.py` | `build_qian_comparison_trajectory` / `build_sanger_comparison_trajectory`，默认 `PRODUCTION_SOLVER_CONFIG`；`ComparisonTrajectory` 统一 API |
| `docs/phase_b` / `docs/phase_d` / `docs/phase_e` | gamma0 / K 语义、RTI / SRTI 语义、E0 协议 A/B/C/D 均一致（见 §15） |

---

## 4. Frozen variables and controlled perturbations

每个 parameter point `p = (gamma0, K)` 只允许修改：

    gamma0
    K

其余全部 configuration 保持 Phase E frozen：

- `h0 = 100 km`、`v0 = 7000 m/s`、`theta0 = 0`；
- `EnvironmentParams` unchanged；
- `VehicleParams` unchanged；
- 同一 atmospheric boundary（`h_atm = 100 km`）；
- 同一 state convention `[r, theta, v, gamma]`；
- 同一 range convention（`R = R_E * theta`）；
- Qian physics / control semantics unchanged；
- Sanger ATM / VAC semantics unchanged；
- Production solver unchanged（`PRODUCTION_SOLVER_CONFIG`）。

禁止事项：

- 为某个 gamma0 / K 重新优化控制；
- 重新拟合 K；
- 重新调 Qian `u_L` semantics；
- 重新调 Sanger switching altitude；
- 修改 mass / S / C_D。

---

## 5. Computational domain

F0 冻结初始主域：

    D0 = { gamma0 ∈ [-7 deg, -3 deg] } × { K ∈ [2.0, 4.0] }

强调：这是 **project-local computational sensitivity window**，不是
flight-certified operational envelope、不是 real-vehicle feasible envelope、
也不是 universal physical K range。

Baseline `(-5 deg, 3)` 位于 D0 矩形中心。

### 5.1 Domain expansion policy（条件性）

不要一开始无限扩域。仅当 F2/F3 发现 topology-changing cell **直接接触**某条
域边界（gamma lower / gamma upper / K lower / K upper）时，才允许扩展对应边，
说明 transition 尚未被 bracket 在主域内部。

- gamma 扩展 increment：1 deg / step；
- K 扩展 increment：0.5 / step；
- computational guardrails：

      gamma0 ∈ [-9 deg, -1 deg]
      K     ∈ [1.0, 5.0]

guardrails 同样只是 computational exploration limits。若到 guardrail 时
transition 仍然离开 domain：报告 `OPEN_BOUNDARY`，不得无限继续扩域。

若 D0 内完全没有 topology transition：**不要**为制造 transition 自动扩展全部
四边；可如实结论 "single regime observed over D0"。

---

## 6. F1 single-parameter pilot

F1 先做两个 one-dimensional slices（**不是**最终 sensitivity result）：

**Gamma slice**（K = 3）：

    gamma0: -7.00 → -3.00 deg，step = 0.25 deg → 17 points

**K slice**（gamma0 = -5 deg）：

    K: 2.000 → 4.000，step = 0.125 → 17 points

Baseline point 只计算一次并复用（两个 slice 共享 p0）。

F1 目的：

- 观察 trajectory outputs 是否平滑；
- 识别可能的 topology transitions；
- 检查 simulation API 对非-baseline regime 的支持；
- 判断 F2 主域是否合理。

### 6.1 F1 stop gates（遇到即停，不得进入 F2）

发现以下任何一项 → 停止并汇报 `PHASE-F-PILOT BLOCKER`：

1. Qian API 无法区分 physical no-event 与 numerical failure
   （§8.1 记录的当前能力边界未通过验证）；
2. Sanger API 无法表达新出现的 legitimate regime；
3. baseline anchor mismatch；
4. production solver instability；
5. event chatter；
6. invalid mode sequence；
7. 大量 censored points。

---

## 7. F2 coarse two-dimensional map

若 F1 没有发现 API blocker，F2 coarse domain：

    gamma0 ∈ [-7, -3] deg，step = 0.25 deg → 17 格
    K     ∈ [2, 4]，     step = 0.125   → 17 格

即 17 × 17 = **289 parameter points**。

每个 parameter point 同时运行 Qian 与 Sanger，形成 **paired comparison
point**。

- **禁止** random sampling 作为 F2 主 map；
- F2 必须是 **deterministic Cartesian grid**；
- F2 map 显示 compact regime class（§10）；
- 每点保存 compact 与 exact 两类 signature（§13）。

---

## 8. Qian regime classification

只保存 success=True/False 不够。F0 冻结以下 Qian regime 概念分类：

| Label | 含义 |
|---|---|
| `QIAN_RTI` | 正常：Capture exists 且 QEG_GLIDE exists 且 RTI exists（QEG feasibility loss 在 ground 前发生） |
| `GROUND_BEFORE_CAPTURE` | trajectory 在 capture 前到达地面（h = 0） |
| `GROUND_AFTER_CAPTURE_BEFORE_RTI` | capture 已发生，但 QEG feasibility-loss RTI 没有在 ground 前发生 |
| `CENSORED` | `max_time` / integration horizon 等计算限制导致无法确定物理 terminal regime |
| `NUMERICAL_FAILURE` | solver failure、NaN、Inf、invalid event ordering 等 |
| `INVALID_INPUT` | 参数本身违反输入约束（例如 K <= 0） |

### 8.1 当前 frozen Qian API 的能力边界（F0 审计结论）

`integrate_qian_glide` 是当前唯一 Qian 生产入口。对以下情形**均 raise
`RuntimeError`**：

- capture 事件未检测到（可能是物理 GROUND_BEFORE_CAPTURE、CENSORED 或
  solver 异常）；
- RTI 事件未检测到（可能是物理 GROUND_AFTER_CAPTURE_BEFORE_RTI、CENSORED
  或 solver 异常）；
- ground 事件未检测到（GROUND_CONTINUATION 段）。

即：**当前 Qian API 没有把 physical no-RTI 与 numerical/integration failure
区分为不同返回值的通道**。F1 必须验证（例如用更严格 solver 做 diagnostic
rerun 区分）能否可靠区分：

- physical no-RTI（严格 solver 同样无事件）→ 归类为对应物理 regime；
- numerical failure（严格 solver 成功）→ `NUMERICAL_FAILURE` +
  `production_failure_recovered_by_reference`。

如果现有 Qian API 无法可靠区分 physical no-RTI vs numerical/integration
failure：**F1 必须停止并汇报 `QIAN-REGIME-CLASSIFICATION BLOCKER`**。不要把
两者都叫 failure。

---

## 9. Sanger regime classification

Sanger 至少保存：`terminal_kind`、`skip_count`、mode sequence、event
sequence。主要物理 regime 表示：

    SRTI_N0, SRTI_N1, SRTI_N2, SRTI_N3, ...

其中 N = completed skip count。Phase E baseline 即 `SRTI_N2`。

另外区分：

| Label | 含义 |
|---|---|
| `GROUND_BEFORE_SRTI` | 真实物理终止（ground 先于 SRTI） |
| `CENSORED` | `max_time` / `max_segments` 等 horizon 限制造成 |
| `NUMERICAL_FAILURE` | solver / event inconsistency |
| `INVALID_INPUT` | 输入约束违反 |

当前 frozen Sanger API（`integrate_sanger_hybrid`）返回
`terminal_kind ∈ {srti, ground_before_srti, max_time, max_segments,
solver_failure}`，**可以可靠区分** physical（ground_before_srti）、horizon
censoring（max_time / max_segments）与 numerical failure（solver_failure）。
skip_count 由 `sanger_metrics` 从 event history 解析（terminal incomplete
pass 不计入）。

**不要把 `max_segments` 误解释成 physical topology。**

---

## 10. Joint hybrid topology signature

### 10.1 Compact vs exact signature

每个 point 同时保存：

- **compact regime signature**：
  - Qian：terminal / regime class（§8）；
  - Sanger：terminal kind + skip_count（§9）。
- **exact topology signature**：完整 mode sequence + event sequence +
  terminal kind；必要时包括 completed-cycle structure（Sanger skip cycles）。

F2 map 显示 compact class；F3 boundary validation 必须检查 exact topology
signature。

### 10.2 Joint regime（cross-model）

每个 paired point 允许定义：

    joint_regime = (qian_regime, sanger_regime)

例如 `(QIAN_RTI, SRTI_N2)`。这是 cross-model regime map 的分类键。

**不是 winner class**。禁止 `QIAN_WIN` / `SANGER_WIN` 这类 composite
regime label。

---

## 11. Invalid/censored/failure policy

必须严格分开四个状态类别：

    PHYSICAL REGIME
    COMPUTATIONALLY CENSORED
    NUMERICAL FAILURE
    INVALID INPUT

- 在 heatmap 中，censored / failure point **不能被插值成正常 regime**；
- 禁止 nearest-neighbor fill、smooth fill、自动补值；
- 若某 point 是 numerical failure：允许使用更严格 solver（如
  `comparison_validation.REFERENCE_SOLVER_CONFIG`）做 diagnostic rerun；
  - 若 strict solver 成功：记录 `production_failure_recovered_by_reference`
    并在 F7 数值审计处理；
  - **不得静默覆盖原 production status**（两个 status 都要保存）。

---

## 12. Topology margins

Margins 是 **topology diagnostics**，不是 performance scores。

### 12.1 Sanger margins

- **A. 每个 VAC apogee clearance**（若该 VAC arc 存在）：

      M_A,i = h_apogee,i - h_atm

  `h_apogee,i` 可从 `HybridSegment.apogee_state`（frozen）获得。

- **B. Terminal SRTI atmospheric clearance**：

      M_S = h_atm - h_SRTI

  当前 SRTI regime 中 `M_S > 0`；当 terminal atmospheric pass 接近形成新的
  exit 时 `M_S → 0`，可能对应 skip-count transition。

- **C. ATM exit transversality**：`dh/dt` at exit 必须为正。

- **D. SRTI transversality**：`gamma_dot` at SRTI（或 frozen event
  derivative helper，若已有可靠 helper）。

### 12.2 Baseline Sanger margins（anchor 引用，不硬编码）

F0 文档引用 Phase D/E frozen artifacts（动态引用，不在 F0 新代码中硬编码）：

    docs/phase_d/sanger_baseline.md  §6–7（frozen, sanger-baseline-v1.0）：
      skip_count = 2
      cycle 0 apogee ≈ 130.352 km（> h_atm = 100 km）
      cycle 1 apogee ≈ 102.233 km（仅 modestly above h_atm）
      SRTI altitude ≈ 86.139 km（< h_atm，即 M_S > 0）

结论：baseline 附近（第二个 VAC apogee 仅略高于大气边界、SRTI 低于边界）
topology sensitivity 值得重点检查。

### 12.3 Qian margins

- **capture transversality**：capture 为 gamma 的向上零穿越（direction = +1），
  transversality 即 `gamma_dot > 0` at capture。
- **QEG feasibility margin at capture**：

      M_Q = 1 - u_L_star(t_capture)，u_L_star = L_req / L（unclipped ratio）

  当前 frozen helper 只公开 clip 后的 `u_L`（`qeg_lift_fraction`）；unclipped
  ratio 没有现成直接 helper。因此：

      OPTIONAL / IMPLEMENT ONLY BY REUSING FROZEN HELPER

  若实现，只能组合复用 frozen 原语（`required_lift`、`aerodynamic_forces`），
  **不得**为 margin 写第二套 QEG 方程。若不可行，记为 `NOT_AVAILABLE`。

---

## 13. Adaptive boundary refinement

### 13.1 Trigger — BOUNDARY_CANDIDATE

F3 只 refinement 疑似 topology boundary cells（初始来自 F2 coarse cells）。
一个 cell 若满足**任一**条件：

1. corner compact regimes 不同；
2. center regime 与 corners 不同；
3. exact topology signatures 不一致；
4. 可靠 signed topology margin 在 cell 内出现 sign change；

则标记 `BOUNDARY_CANDIDATE`。

### 13.2 Refinement method

对 BOUNDARY_CANDIDATE 做 **recursive 2D subdivision**：每层 gamma interval
二分、K interval 二分；**复用已计算 point**，避免重复积分。

终止条件（满足其一）：

- `Delta gamma <= 0.01 deg` **且** `Delta K <= 0.01`；
- 达到预设 `max_depth = 6`（safety limit）。

若 max_depth 达到但仍无法定位：标 `UNRESOLVED_BOUNDARY`，**不要伪造一条平滑
曲线**。

### 13.3 不做过早几何假设

禁止预设 topology boundary 一定是 `K = f(gamma)` 或 `gamma = f(K)`。它可能
弯曲、折叠、分叉、形成小区域。F3 默认使用 2D cell refinement，而不是一开始
只做一维 root solving。仅当后续发现局部 boundary 确实单值且平滑时，才可在更
后阶段拟合。**F0 不冻结这种假设。**

### 13.4 禁止插值 topology labels

regime map 是 categorical：

- 禁止 bilinear / bicubic interpolation、Gaussian smoothing 生成不存在的
  fractional skip count；
- 绘图用 nearest / cell-based categorical map 或 polygon map；
- 连续 scalar field 只允许在同一 regime 内插值展示，且原始 sampling points
  必须保留。

---

## 14. Fixed-regime derivative policy

### 14.1 核心规则：Sensitivity 与 Topology 必须分开

如果 parameter perturbation 保持相同 hybrid topology：允许讨论 continuous
sensitivity、finite difference derivative、local gradient。

如果 perturbation 改变 terminal kind、skip count、mode sequence 或 event
sequence：**禁止**把跨界差值解释为普通 derivative，必须标记
`HYBRID_TOPOLOGY_TRANSITION`。

正式写入：

    Sensitivity surfaces are differentiated only within a fixed hybrid regime.
    Across a topology boundary, finite differences are reported as regime
    transitions rather than ordinary derivatives.

### 14.2 Derivative validity 条件

计算 `dy/dgamma0` 或 `dy/dK` 必须满足：center、plus perturbation、minus
perturbation 三个点全部 valid **且** exact topology signature identical。

否则：

    derivative = undefined
    reason     = TOPOLOGY_CHANGE 或 INVALID_NEIGHBOR

禁止跨 `N_skip = 2 → N_skip = 3` 计算 ordinary centered derivative。

### 14.3 单位策略

- **gamma**：代码内部 radians。canonical mathematical derivative
  `∂y/∂gamma` 以 **per radian** 保存；允许同时报告 **per degree**（工程
  解释）。必须显式单位；**禁止**在同一表中把 per-radian 与 per-degree 混在
  一起。
- **K**：无量纲，`∂y/∂K` 报告 **per unit K**；不写 "per %"（除非另外明确
  转换）。

### 14.4 Finite-difference step 不在 F0 冻结

F0 只冻结"需要 step-convergence study"。最终 derivative step 必须通过 F4
convergence 决定。以下只是 **future candidate steps**（不是 F0 冻结数值常数）：

    gamma perturbation:  0.1 deg, 0.05 deg, 0.025 deg
    K perturbation:      0.05,    0.025,   0.0125

### 14.5 三种概念必须分离

论文解释必须区分：

- **A. Within-regime sensitivity**：如 `dR/dgamma0`、`dR/dK`；
- **B. Boundary proximity**：到 skip-count transition 的 distance / margin；
- **C. Topology transition**：如 `SRTI_N2 → SRTI_N3`。

三者不能混成一个 "sensitivity score"。

---

## 15. Comparison-protocol reuse

Phase F **不新增** performance metric。未来 F6 若在每个 valid paired point
比较 Qian / Sanger，只能复用 Phase E（E0 protocol）已冻结的协议：

    Protocol A: native persistence description
    Protocol B: common time
    Protocol C: common range
    Protocol D: common atmospheric exposure

禁止新增：overall winner score、normalized composite score。

### 15.1 Comparison eligibility

只有当 Qian point 与 Sanger point **都具有可解释 physical research
trajectory** 时，对应 E0 protocol 才允许执行。若任一边是 `CENSORED` /
`NUMERICAL_FAILURE` / `INVALID_INPUT`：

    cross-model metric = NOT_AVAILABLE

不能使用另一边单独结果推断 winner。

### 15.2 Common-condition limiter 动态化

Phase E baseline 中 common-time / common-range / common-exposure limiter 均为
Qian。Phase F **禁止假设**整个 gamma-K domain 都如此。每个 paired point 必须
动态记录：

    time_limiter
    range_limiter
    exposure_limiter

limiter 本身是 discrete comparison semantics；若 limiter 在 parameter space
中切换，这是 **comparison-regime transition**，不能当作普通 smooth
derivative。

### 15.3 Future comparison regime signature（F6 语义冻结，不实现）

    comparison_signature = (
        qian_regime,
        sanger_regime,
        time_limiter,
        range_limiter,
        exposure_limiter,
        protocol_D_inverse_status,
    )

F0 只冻结该语义，不实现 F6。

---

## 16. Numerical policy

Phase F initial sweep 统一使用 **`PRODUCTION_SOLVER_CONFIG`**
（`src/hyptraj/simulation/numerics.py`，Phase C 冻结）：

    method = DOP853
    rtol   = 1e-9
    atol   = [1e-4, 1e-11, 1e-7, 1e-11]
    max_step = 20 s
    dense_output = True

**不要**因为靠近 topology boundary 就在整个 sweep 使用 reference config
（Phase E 已验证 production numerics）。Boundary refinement 与 F7 再对必要点
做 high-precision verification（可复用 `comparison_validation` 的
`REFERENCE_SOLVER_CONFIG` 等 audit cases）。

---

## 17. Reproducibility / artifact schema

### 17.1 目录结构（未来统一）

    results/gamma_k_sensitivity/
        pilot/                  # F1
        coarse_map/             # F2
        boundary_refinement/    # F3
        fixed_regime_sensitivity/  # F4
        comparison_surfaces/    # F6
        numerical_audit/        # F7

`results/` 继续不 tracked。tracked source 只保留 runner、analysis、tests、
docs、regression reference（如最终需要）。

### 17.2 每行结果必须可追踪

每个 result row 至少包含：

    gamma0_deg
    gamma0_rad
    K
    model                     # qian | sanger
    solver config
    git commit
    baseline tags
    terminal / regime status
    success / censored / failure reason

**不得**只保存 R、v 而丢掉 regime metadata。

### 17.3 Qian primary outputs（正常 QIAN_RTI point）

    gamma0_deg, K,
    capture_time_s, capture_altitude_m, capture_velocity_mps,
    RTI_time_s, RTI_range_m, RTI_altitude_m, RTI_velocity_mps,
    initial_energy, RTI_energy, energy_loss,
    QEG_duration_s,                       # t_RTI - t_capture
    terminal_kind, regime_signature, mode_sequence

Ground continuation **不是** primary Phase F output。

### 17.4 Sanger primary outputs（正常 SRTI point）

    gamma0_deg, K,
    terminal_time_s, terminal_range_m, terminal_altitude_m, terminal_velocity_mps,
    initial_energy, terminal_energy, energy_loss,
    skip_count,
    ATM_duration_s, VAC_duration_s,
    max_altitude_m,
    mode_sequence, event_sequence,
    terminal_kind, regime_signature

### 17.5 Future hybrid-sensitivity 数据接口（STM / saltation 连接）

Phase F 的 sweep artifact schema 必须允许每个 sensitivity point 重建：

    event names
    event times
    exact event states
    mode before
    mode after

Sanger 附加：skip cycle index。

Phase F **不计算** STM、saltation matrix、FTLE —— 但**不要设计一个会丢失
hybrid event sequence 的 sweep artifact schema**。

---

## 18. Link to STM / saltation / FTLE

- Phase F 冻结的是 parameter-level 的 hybrid topology 表征（regime 分类、
  boundary 定位、within-regime 数值灵敏度）；
- Phase F 的 exact event metadata（§17.5）为后续 STM / saltation / FTLE 研究
  保留必要输入；
- 真正的 STM / saltation / FTLE 计算属于 Phase F 之后的研究阶段，不在本
  协议范围内。

---

## 19. Phase F roadmap

正式冻结：

    F0  Sensitivity / topology protocol freeze          ← 本文档
    F1  Single-parameter pilot: gamma slice + K slice
    F2  Coarse gamma0-K hybrid regime map（17×17 = 289 paired points）
    F3  Adaptive topology-boundary refinement
    F4  Fixed-regime local sensitivity / derivative convergence
    F5  Qian/Sanger structural sensitivity analysis
    F6  Phase-E protocol comparison surfaces over parameter space
    F7  Numerical / regression audit + Phase F final freeze

**边界条件冻结**：

    Uncertainty（随机变量 / Monte Carlo / CI / regime 概率）:  明确排除，Phase F 是
        deterministic parameter sensitivity；gamma0/K 是 controlled sweep
        variables，不是 random variables，不假设 Gaussian 分布。
    Optimization（搜索 optimum / 拟合 optimum K / 宣布 best gamma0）: 明确排除；
        Phase F 目标是 characterization，不是 optimization。
    STM / saltation / FTLE: 不属于 Phase F。

---

## 20. F0 acceptance

F0 必须全部 PASS：

    [x] Phase F branch from phase-e-v1.0
    [x] Phase E tags unchanged
    [x] gamma0 semantics frozen
    [x] K = L/D semantics frozen
    [x] K > 0 input semantics recorded
    [x] only gamma0/K perturbed
    [x] Phase E anchor frozen
    [x] computational domain frozen
    [x] F1 pilot grid frozen
    [x] F2 coarse-grid policy frozen
    [x] conditional domain expansion frozen
    [x] Qian regime taxonomy frozen
    [x] Sanger regime taxonomy frozen
    [x] joint topology signature frozen
    [x] physical/censored/numerical states separated
    [x] topology margins defined
    [x] F3 adaptive refinement policy frozen
    [x] no topology-label interpolation
    [x] fixed-regime derivative policy frozen
    [x] gamma derivative unit policy frozen
    [x] Phase E comparison protocols reused
    [x] dynamic limiter semantics recorded
    [x] uncertainty explicitly excluded
    [x] optimization explicitly excluded
    [x] STM/saltation/FTLE deferred
    [x] future event metadata requirement recorded
    [x] F0 docs only
    [x] pytest PASS（229 passed，test count 不变）

---

## Amendment — F0.1: Qian Regime-Classification Access Amendment

状态：**COMPLETE**（2026-08-16）

### A. Original blocker（为什么原 Qian baseline API 不足以做 regime classification）

`src/hyptraj/simulation/trajectory.py` 的 `integrate_qian_glide` 是唯一 Qian
生产入口，其 stage event 监听为：

| Stage | 监听 events（frozen） | 缺失行为 |
|---|---|---|
| Stage 0 ENTRY_CAPTURE | 仅 `make_capture_event()` | capture missing 与 solver failure 走**同一个** `raise RuntimeError` |
| Stage 1 QEG_GLIDE | 仅 `make_qeg_end_event(...)` | RTI missing 与 solver failure 走**同一个** `raise RuntimeError` |
| Stage 2 GROUND_CONTINUATION | 仅 `make_ground_event(env)` | — |

因此当前 public API 无法可靠区分：

    GROUND_BEFORE_CAPTURE
    GROUND_AFTER_CAPTURE_BEFORE_RTI
    CENSORED / no-event（horizon）
    NUMERICAL_FAILURE

违反 F0 §8 冻结的 regime taxonomy。F0.1 仅解决该 observability 缺口。

### B. 冻结约束（F0.1 硬性要求）

- **historical Qian API remains frozen**：`integrate_qian_glide` 的 signature、
  historical output、RuntimeError 行为、三阶段 ground-continuation 结果全部
  保持不变（Phase B-E regression 依赖它）。
- 禁止复制第二套 Qian 动力学：新 API 只复用 frozen
  `atmospheric_dynamics`、`continuous_glide_rhs`、`make_capture_event`、
  `make_qeg_end_event`、`make_ground_event`、`PRODUCTION_SOLVER_CONFIG`、
  `DenseOutputCollector`（E0.1）。
- 禁止解析 RuntimeError / SciPy message 文本做 regime 分类；terminal reason
  必须来自 structured result。
- 禁止靠 ground altitude sampled grid 判断终端；必须使用 exact event
  localization（`sol.sol(t_event)`）。
- `INVALID_INPUT`（如 `K <= 0`）仍由 `ConstantKControl` 抛 `ValueError`，
  新 integrator 不吞掉；sweep layer 捕获并分类 `INVALID_INPUT`。

### C. 新增 API（F0.1）

1. `src/hyptraj/simulation/qian_research_trajectory.py`
   - `integrate_qian_research_trajectory(env, vehicle, initial, control,
     solver=PRODUCTION_SOLVER_CONFIG, dense_output_collector=None,
     max_time=5000.0, simultaneous_tol_s=1e-6) -> QianResearchTrajectory`
   - `QianResearchTrajectory`：`success` / `terminal_kind` /
     `terminal_time` / `terminal_state` / `message` / `segments` /
     `events` / `capture_event`（optional）/ `rti_event`（optional）/
     `ground_event`（optional）/ `mode_sequence` / `initial_state` /
     `solver_config` / `max_time_s` / `initial_conditions`。
   - Terminal kinds（冻结词汇）：

         RTI
         GROUND_BEFORE_CAPTURE
         GROUND_AFTER_CAPTURE_BEFORE_RTI
         MAX_TIME
         SOLVER_FAILURE
         AMBIGUOUS_SIMULTANEOUS_EVENT

   - Stage 语义（frozen RHS / events 不变，只扩监听）：
     - Stage 0 同时监听 capture + ground：capture first → 进入 QEG_GLIDE；
       ground first → `GROUND_BEFORE_CAPTURE`（physical terminal）。
     - Stage 1 同时监听 RTI + ground：RTI first → `RTI`（research
       success）；ground first → `GROUND_AFTER_CAPTURE_BEFORE_RTI`。
     - 显式 event-time 比较（绝不依赖 events list position）；两个 root 在
       `simultaneous_tol_s = 1e-6 s` 内同时 → `AMBIGUOUS_SIMULTANEOUS_EVENT`
       （不任意归边）。
     - horizon 内无任何 event → `MAX_TIME`（computational censor，不是
       physical no-RTI）。默认 `max_time = 5000 s` 与 production t_span
       兼容，不为 pilot 随意扩大。
     - solver failure → `SOLVER_FAILURE`。
   - `success` 语义与 Sanger 一致：仅 RTI 达成时为 True；`GROUND_*` 是
     physical terminal 但 `success = False`。**classifier 必须以
     `terminal_kind` 为准，不得以 `success` 为准。**

2. `src/hyptraj/analysis/sensitivity_trajectory.py`（pure mapping）
   - `classify_qian_regime(result)`：terminal kind → regime label：

         RTI                               -> QIAN_RTI
         GROUND_BEFORE_CAPTURE             -> GROUND_BEFORE_CAPTURE
         GROUND_AFTER_CAPTURE_BEFORE_RTI   -> GROUND_AFTER_CAPTURE_BEFORE_RTI
         MAX_TIME                          -> CENSORED
         SOLVER_FAILURE                    -> NUMERICAL_FAILURE
         AMBIGUOUS_SIMULTANEOUS_EVENT      -> BOUNDARY_AMBIGUOUS（F0.1 新增）

     `BOUNDARY_AMBIGUOUS` 文档定义：两个终端事件在严格 tie tolerance 内
     同时发生、数值上无法分辨先后 —— 属于边界模糊状态，既不是纯数值失败
     也不是纯 censored；heatmap 处理同 censored（禁止插值），F3 boundary
     refinement 必须检查该类点。
   - `classify_sanger_regime(result, skip_count=None)`：`srti + skip_count
     = N -> SRTI_N{N}`；`ground_before_srti -> GROUND_BEFORE_SRTI`；
     `max_time / max_segments -> CENSORED`；`solver_failure ->
     NUMERICAL_FAILURE`。SRTI 必须提供 frozen `skip_count`。
   - 未知 terminal kind 抛 `KeyError`（编程错误），绝不静默归为 failure。

### D. 架构选择理由

选择 **simulation-level research integrator**（而非纯 analysis wrapper）：
`integrate_qian_glide` 不暴露 stage 级结构化 solver 结果（每 stage 的
`success`、`t_events`、dense output），analysis wrapper 只能捕获
`RuntimeError` 而禁止解析其文本 —— 无法获得 terminal reason。因此必须由
simulation 层直接编排 `solve_ivp` 调用（完全复用 frozen RHS / events /
solver config），与 `integrate_sanger_hybrid`（`sanger_trajectory.py`）的
既有模式平行。`trajectory.py` 未做任何修改。

### E. Sanger 未修改

`integrate_sanger_hybrid` 已能可靠区分 `srti` / `ground_before_srti` /
`max_time` / `max_segments` / `solver_failure`，F0.1 只新增薄 classifier
（`classify_sanger_regime`），**不修改** Sanger integrator 与 metrics。

### F. F0.1 测试覆盖（tests/test_phase_f_regime_classification.py）

A–L 全项：baseline → QIAN_RTI（capture/RTI exact state 与 Phase E
regression 在 1e-9 相对容差内一致，实测 diff = 0.0）；historical
`integrate_qian_glide` 数值不变；GROUND_BEFORE_CAPTURE /
GROUND_AFTER_CAPTURE_BEFORE_RTI（真实冻结动力学 + monkeypatch
counterpart event）；max_time → CENSORED；mocked solver failure →
NUMERICAL_FAILURE；censored ≠ numerical failure；classifier pure mapping
（不解析 message）；tie policy → BOUNDARY_AMBIGUOUS；Sanger baseline →
SRTI_N2；INVALID_INPUT 透传 ValueError。

### G. F0.1 acceptance

    [x] original blocker documented
    [x] no RuntimeError-text classification
    [x] structured Qian terminal result available
    [x] RTI distinguished
    [x] ground-before-capture distinguished
    [x] ground-after-capture-before-RTI distinguished
    [x] censored distinguished
    [x] numerical failure distinguished
    [x] event states exact
    [x] baseline anchor matches Phase E
    [x] old integrate_qian_glide unchanged
    [x] Qian physics unchanged
    [x] Qian control unchanged
    [x] event surfaces unchanged
    [x] solver constants unchanged
    [x] Sanger integrator unchanged
    [x] Phase E regression unchanged
    [x] all tests PASS

---

## Amendment — F2.1: Sanger Grazing-Transition / Event-Qualification Observability

状态：**COMPLETE**（2026-08-16）

完整记录见 `docs/phase_f/f21_sanger_grazing_amendment.md`。本节冻结 F2.1
的协议语义（protocol-level amendment）：

### 1. Grazing transition definition

Atmosphere interface `G_h(x) = h - h_atm`，`dG_h/dt = v sin(gamma)`；
SRTI candidate `gamma = 0`。skip-count transition 的 limiting geometry
满足 `G_h = 0 且 gamma = 0`（`dG_h/dt = 0`）时，定义为 **Sanger
atmosphere-interface grazing / tangency transition**。F2.1 已通过 strict
numerical audit 确认：F2 blocker 是 production event-resolution 问题
（max_step=20 漏检极浅 excursion，REF self-stable 于 SRTI_N3），与
grazing 几何一致。

### 2. Research-event recovery policy

- 触发：ATM solve 返回 SRTI candidate 且 `h_candidate > h_atm`、exit 未
  被 solve_ivp 返回、pass 已有 pullout 且 `h_pullout < h_atm`。
- 方法：在 `[t_pullout, t_candidate]` 上以 brentq 从已计算 dense
  interpolant 定位 `h - h_atm = 0` 上穿 root；禁止 sampled-row /
  linear-interp / epsilon perturbation。
- recovered root 必须满足：`t_pullout < t_rec < t_candidate`、residual
  < 1e-6 m、`gamma(t_rec) > 0`、`dh/dt > 0`（真 transverse upward
  exit）。任一项失败 → 不 recovery，terminal kind =
  `GRAZING_OR_UNRESOLVED_EVENT`。
- recovered switch：`x_plus = x_minus`（严格连续）；`f_minus`/`f_plus`/
  `normal` 与 normal exit 相同；`event_resolution = "DENSE_RECOVERED"`；
  不创造新的 physical switch。
- normal detected exit 一律使用 `SOLVER_EVENT`（不得重新 root solve）；
  candidate below boundary 一律 frozen qualification（不 recovery）。
- `candidate_overshoot_m = h_candidate - h_atm` 只是 qualification
  probe / numerical diagnostic，不是 physical post-exit state；暂不
  冻结为最终 F3 metric（F3 开始时再决定是否正式定义
  `Phi(gamma0, K)`）。

### 3. Recovered events 必须 strict-reference verify

任何 `event_resolution = DENSE_RECOVERED` 的 point 自动进入
strict-reference verification queue：用 REF-0.1（必要时 REF-0.05）确认
terminal kind / skip_count / exact topology 一致。任何 recovered point
与 reference topology 不一致 → F2 HARD STOP。禁止静默接受 recovery。

### 4. SANGER_GRAZING_BOUNDARY 不是 stable regime

- 若 reference 验证后仍无法稳定分配给任一 transverse side：regime
  display `GR`、label `SANGER_GRAZING_BOUNDARY`。
- 它不是 CENSORED / NUMERICAL_FAILURE / SRTI_N；不作为 HARD STOP；自动
  成为 F3 P0 priority point/cell。
- 若只是 production ambiguity 而 strict reference 可明确 N：最终使用
  reference-confirmed physical side，并记录
  `production_event_resolution_recovered = True`。
- 禁止用 arbitrary 物理阈值（|M| < 100 m 等）制造 grazing band；
  `_SRTI_ALTITUDE_ASSERT_TOL_M = 1 m` 只是 frozen assertion tolerance。

### 5. Frozen Phase-D Sanger API 不修改

`sanger_trajectory.py`、`sanger_events.py`、`sanger_hybrid.py`、
`PRODUCTION_SOLVER_CONFIG` 全部保持 frozen。Phase-F 只新增
`src/hyptraj/simulation/sanger_research_trajectory.py`（research
event-resolution integrator，复用全部 frozen RHS/events/helpers），
与 F0.1 Qian research API 思想一致：只增加 robust observability，
不改变 physics / event surfaces / reset semantics。禁止
exception-message 文本解析。

### 6. F3 前允许使用 structured grazing metadata

`grazing_diagnostics`（per-ATM-pass：candidate_seen /
candidate_overshoot_m / exit_detected_by_solver / exit_recovered /
recovered_exit_time / interface_residual / exit_gamma / exit_dhdt）与
`recovered_events` 可作为 F3 refinement 的 structured 输入；F3 开始时
再决定 grazing margin `Phi` 的正式定义。

### 7. Canonical F2 sweep executor

F2 canonical map 必须使用 F2.1 research integrator 作为 Sanger sweep
executor；frozen `integrate_sanger_hybrid` 保留用于 regression /
comparison audit。F2 cache schema 升级为 `f2-coarse-map-point-v2`，
provenance 增加 `phase_f_f21_commit` 与
`sanger_research_event_resolution_version = "v1"`；旧 v1 cache 不得静默
作为 canonical final cache。

---

## Amendment — F3: Adaptive Grazing-Boundary Refinement（Phi_N 正式冻结）

状态：**COMPLETE**（2026-08-16）。完整记录见
`docs/phase_f/f3_boundary_refinement.md`。

### 1. Phi_N — branch-conditioned signed grazing diagnostic（F3 冻结定义）

对 branch B_N（SRTI_N ↔ SRTI_{N+1}）：

- **N side**（regime = SRTI_N）：`Phi_N = h_SRTI - h_atm = -M_S`
  （理论侧 < 0；SRTI local maximum 从下方接近大气边界）。
- **N+1 side**（regime = SRTI_{N+1}）：`Phi_N = h_apogee,new - h_atm`，
  其中 `h_apogee,new` 是 newly-created LAST VAC apogee（VAC arc index
  N，zero-based）。**禁止 `min(M_A_clearance_m)` 替代**（早期 VAC 弧与
  本次 topology creation 无关）。
- 其他 regime：`Phi_N = None`（不跨 N-1 / N+2 延拓；不是全局光滑 scalar
  field）。
- limiting geometry：`h = h_atm ∧ gamma = 0`（`G_h = 0`，
  `dG_h/dt = v sin gamma = 0`）= numerically refined hybrid grazing
  transition（不声称解析 bifurcation proof）。

### 2. Newly-created exit transversality T_N

N+1 侧：`T_N = dh/dt` at newly-created atmosphere exit（exit index N，
zero-based）。应 T_N > 0 且随 refinement 趋近 0+；secondary grazing
diagnostic，不是 boundary locator。`T_N → 0+` 意味着 transversal-event
saltation formula 的 `n^T f_minus = dh/dt` 分母病态（saltation 属未来
phase）。

### 3. Refinement 规则冻结

- dyadic 2D bisection（integer lattice）；target Δgamma ≤ 0.01 deg 且
  ΔK ≤ 0.01；max_depth = 6。
- child candidate：Sanger compact/exact 变化、Qian 变化、同 B_N 邻域
  Phi_N 两侧、grazing marker → candidate；uniform 停止；center 与四角
  不同 → 保留 children。
- 最终输出 = enclosing parameter rectangle；cell center 仅
  visualization_center_only；禁止 boundary fit / critical-K regression。
- 域严格 = guardrails [-9,-1]×[1,5]；guardrail 接触 → OPEN_BOUNDARY
  refined intersection（不采样域外）。
- GRAZING_OR_UNRESOLVED_EVENT（含 degenerate zero-duration VAC arc）：
  strict-reference decision 优先；reference-confirmed side 或
  SANGER_GRAZING_BOUNDARY marker（P0，非 stop gate，禁止插值）。
- 每条 B_N 两侧 closest-to-zero 点必须 REF-0.1 + REF-0.05 双 reference
  certification。

### 4. F4 前置

`boundary_exclusion_cells.json` = 全部 REFINED_BOUNDARY_CELL +
UNRESOLVED + GRAZING marker boxes。F4 finite-difference stencil 跨盒或
端点跨 exact topology → derivative undefined（协议 §27 不变）。

---

## Amendment — F4: Fixed-Regime Local Sensitivity / FD Convergence（policy 冻结）

状态：**COMPLETE**（2026-08-17）。完整记录见
`docs/phase_f/f4_fd_convergence.md`。

### 1. Ordinary derivative 语义（F4 冻结）

- 仅定义在 fixed exact topology interior；`D_gamma(h) = [y(g+h)-y(g-h)]
  / (2 h_rad)`（h_rad = h_deg·π/180；canonical 单位 per radian，
  per-degree 显式报告）；`D_K(h)` 单位 per unit K。
- 这是 parameter-output Jacobian `J = ∂y_terminal/∂(gamma0, K)`，不是
  STM / variational matrix / saltation matrix。skip_count 等离散
  topology label 永不微分；max-based 非光滑 observable 不入 vector。
- 不新增 elasticity / percentage / normalized composite sensitivity
  （如未来需要，F5 再定义）。

### 2. Stencil eligibility gate（F4 冻结）

central stencil（minus, center, plus）全部满足才 FD_ELIGIBLE：
(1) 全部在 guardrails 内；(2) center→minus / center→plus 线段不与任一
F3 exclusion box 相交（segment-vs-rectangle gate，仅端点同 label 不够）；
(3) 三点 exact topology signature identical（模型特定）；(4) 无
GRAZING / GRAZING_OR_UNRESOLVED / DENSE_RECOVERED / reference-only
recovered discrepancy；(5) 全部 valid physical terminal。否则
derivative = None + reason（OUTSIDE_DOMAIN / BOUNDARY_INTERSECTION /
TOPOLOGY_CHANGE / RECOVERED_EVENT / GRAZING_ADJACENT / INVALID_NEIGHBOR）。

### 3. FD step policy（F4 冻结）

**GLOBAL_STEP_POLICY**：h_gamma = **0.1 deg**（per-radian）、
h_K = **0.025**。判据（dimension-aware，已文档化）：plateau = 连续两层
`|D(h)-D(h/2)| <= 0.01 * |D_ref|`；negligible output 阈值 gamma 1e-3/rad、
K 1e-2/unitK 不参与判据。参考 derivative = REF-0.1 numerical FD
（非 analytic）；REF-0.05 用于 self-stability（topology identical +
导数差量化）。若未来某点无法满足 gate/plateau → 回退
ADAPTIVE_STEP_POLICY（largest-safe-converged central step，按上述
gate + plateau + reference audit 自动选择），不强行最小 h。

### 4. 其他冻结

- production-vs-reference 误差按 output dimension 报告（近零导数不报
  巨大相对 %，改报绝对误差 + reference floor）。
- 禁止 mixed-unit 全局误差；禁止跨 topology 的 ordinary derivative。
- recovered / grazing / certified extremal 点及 stencil 不得用于
  ordinary FD（deliberately conservative）。
- F4 已确认 per-branch multiplicity：每条 B_N 的 row/column
  multiplicity 均为 1（"five branch families coexist; per-branch
  single-valued"）。

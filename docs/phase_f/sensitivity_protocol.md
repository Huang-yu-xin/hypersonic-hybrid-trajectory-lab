# Phase F — gamma0-K Sensitivity and Hybrid-Regime Protocol

## Status

    Phase F status:       F0 PROTOCOL FREEZE（Sensitivity / Topology Protocol Freeze）
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

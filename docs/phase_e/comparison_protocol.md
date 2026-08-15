# Phase E — Qian vs Sanger Baseline Comparison Protocol（E0 冻结版）

## Status

    Phase E status:        E0 COMPLETE（Comparison Protocol Freeze）
    Branch:                feature/phase-e-qian-sanger-comparison
    Created from:          phase-d-v1.0（2089c0d6da0e9700a86a5bdbf121bf38f96b46a4）
    E0 freeze date:        2026-08-15
    Source of truth:       This document — 所有 Phase E comparison code /
                           figures / claims 的唯一权威依据（source of truth）。

本文档冻结 Phase E 的比较对象、数值统一配置、比较协议、指标、符号、单位与
语言约束。E1–E7 的全部实现必须与本协议一致；任何与本协议冲突的行为必须
先修订本协议并重新冻结。

## 0. 冻结状态检查（E0 前置确认，已执行）

| 检查项 | 结果 |
|---|---|
| `git status`（工作树） | clean |
| `phase-d-v1.0` → commit | `2089c0d6da0e9700a86a5bdbf121bf38f96b46a4` ✓ |
| `sanger-baseline-v1.0` → commit | `2089c0d6da0e9700a86a5bdbf121bf38f96b46a4` ✓ |
| `qian-baseline-v1.0` → commit | `d7ad35cd53a8c9ea64a750e47adbbb6db20198b7`（存在，未移动）✓ |
| `phase-b-v1.0` → commit | `54aa65ac77df12669c2a056b68064f4f4790be6c`（存在，未移动）✓ |
| `phase-c-v1.0` → commit | `71fec92d0b72db32671a3cccd206de7aeed4806d`（存在，未移动）✓ |
| Phase E 分支来源 | 从 `phase-d-v1.0` 创建，未使用任何未冻结临时 commit ✓ |

> 注：`phase-d-v1.0` / `sanger-baseline-v1.0` 为 annotated tag，上表给出的是
> `^{commit}` 解引用后的最终指向。

## 1. E0 目标

创建本文件 `docs/phase_e/comparison_protocol.md`，作为 Phase E 全部
comparison code / figures / claims 的 source of truth。

E0 原则上只新增该文档。**禁止修改** `src/`、`tests/`、`experiments/`。
不得实现 E1（comparison solver / data infrastructure），不得生成任何新的
comparison results，不得修改任何 Qian / Sanger physics，不得进入
parameter sweep / STM / FTLE。

## 2. Comparison objects（比较对象）

正式比较对象（仅两个 frozen baselines）：

| 对象 | 冻结锚点 | 内容 |
|---|---|---|
| **Qian** | `qian-baseline-v1.0`（`d7ad35c…`） | Qian frozen physics / control semantics（连续滑翔，ENTRY_CAPTURE / QEG_GLIDE / GROUND_CONTINUATION） |
| **Sanger** | `sanger-baseline-v1.0`（`2089c0d…`） | Sanger frozen physics / control semantics（混合跳跃，SANGER_ATM ↔ SANGER_VAC） |

共同配置（两者完全相同，不得为比较而调整）：

- 初始条件：`h0 = 100 km`，`v0 = 7000 m/s`，`gamma0 = -5 deg`，`theta0 = 0`
- 升阻比：`K = 3`
- 环境模型：相同的 `EnvironmentParams`
- 飞行器模型：相同的 `VehicleParams`
- 状态约定：相同（同 Phase B–D frozen convention）
- 射程约定：相同（downrange / range-angle convention）

禁止事项：

- 不得调整 Qian
- 不得调整 Sanger
- 不得调整 K
- 不得调整 IC
- 不得重新拟合任何参数

## 3. Numerical harmonization（数值统一）

Phase E comparison realization 两边统一使用 **`PRODUCTION_SOLVER_CONFIG`**
（`src/hyptraj/simulation/numerics.py`，Phase C 冻结）：

```python
PRODUCTION_SOLVER_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-9,
    atol=np.array([1e-4, 1e-11, 1e-7, 1e-11]),  # state-scaled atol
    max_step=20.0,
    dense_output=True,
)
```

必须明确：

    Qian Phase-E comparison realization
        = Qian frozen physics/control
        + Phase C production numerics

    Sanger Phase-E comparison realization
        = Sanger frozen physics/control
        + Phase C production numerics

这**不替换** `qian-baseline-v1.0` 历史 regression baseline。历史基线保持原
数值配置与参考 JSON / 指标不变。

禁止修改：

- `DEFAULT_SOLVER_CONFIG`
- `PRODUCTION_SOLVER_CONFIG`
- Qian reference JSON / metrics（`results/baseline/qian_continuous_glide/`）
- Sanger reference JSON（`results/sanger_hybrid/baseline/summary.json` 等）

## 4. Endpoint semantic asymmetry（端点语义不对称）

必须显式记录——两个 research endpoint 语义不同，不能直接互比：

| | Qian | Sanger |
|---|---|---|
| research endpoint | **RTI**（Research Terminal Interface） | **SRTI**（Sanger Research Terminal Interface） |
| 语义 | **QEG feasibility loss**（`reason = "qeg_feasibility_loss"`，`u_L* ≤ 1` 触发） | **skip-capability loss**（`gamma: + → -` 根，经状态机 qualification：`mode == SANGER_ATM`） |

因此：

- **native endpoint range / time 不能直接解释为 fair common-condition
  performance gain。**
- **禁止仅用 `R_SRTI / R_RTI` 就宣称 “Sanger range improves by X%”。**

## 5. Protocol A — Native Endpoint Comparison

分别评价：

- `Qian@RTI`
- `Sanger@SRTI`

记录（每条 trajectory 各一组）：

- research duration（`T_Q_RTI` / `T_S_SRTI`）
- research range（`R_Q_RTI` / `R_S_SRTI`）
- terminal altitude（`h_end`）
- terminal velocity（`v_end`）
- terminal specific mechanical energy（`E_end`）
- total specific mechanical-energy loss（`DeltaE_end`）

语义固定为 **trajectory-mode persistence comparison**（轨迹模式持久性比较）：

- 可以讨论：哪种 mode 在其自身 feasibility semantics 下持续更久。
- 不得作为唯一性能排名。

## 6. Specific mechanical energy（比机械能定义）

统一使用（禁止另造其他 energy definition）：

    E = v^2 / 2 - mu / r

其中 `mu` 使用 frozen environment definition
（`src/hyptraj/simulation/trajectory.py`：`MU = 9.81 * 6_371_000.0**2`，
单位 m³/s²，球形引力模型）。

定义能量损失：

    DeltaE = E_initial - E_current

- 单位：`J/kg`
- 报告可用：`MJ/kg`

## 7. Protocol B — Common-Time Comparison

定义公共时间：

    t_common = min(T_Q_RTI, T_S_SRTI)

在同一个 `t_common` 连续评价 Qian state 与 Sanger state，比较：

- range
- altitude
- velocity
- specific mechanical energy
- specific mechanical-energy loss
- current mode / phase

定义 primary differences：

    DeltaR_time = R_S - R_Q
    DeltaV_time = v_S - v_Q
    DeltaE_time = E_S - E_Q

**只有这类 common-condition comparison 才允许直接使用“同时间下领先/保留
更多”等措辞。**

## 8. Protocol C — Common-Range Comparison

定义公共射程：

    R_common = min(R_Q_RTI, R_S_SRTI)

对两条 research trajectories，求第一次满足

    R(t) = R_common

的连续状态（root finding，见 §10）。

比较：arrival time、altitude、velocity、specific mechanical energy、
specific mechanical-energy loss、mode / phase。

定义：

    time_saving = t_Q(R_common) - t_S(R_common)
    DeltaV_range = v_S(R_common) - v_Q(R_common)
    DeltaE_range = E_S(R_common) - E_Q(R_common)

`time_saving > 0` 表示 **Sanger 更早达到共同射程**。

## 9. Range monotonicity requirement（单调性前提）

Common-range protocol 使用前必须由 E1/E2 程序验证：

- `R(t)` 在**两条** research trajectories 上单调递增。

禁止未经验证假设 `t(R)` 一定单值。

处理规则：

- 若任何 trajectory 出现非单调 downrange：**停止 common-range scalar
  inversion**，保留异常并重新定义 protocol（先修订本文档再继续）。

## 10. Continuous evaluation rule（连续求值规则）

正式 comparison checkpoint **禁止**使用：

- nearest sampled CSV row
- `argmin(abs(...))`
- 400-point plotting grid

必须使用：

- **dense output**（`dense_output=True` 的插值）
- **segment-aware interpolation**（按 mode segment 感知的插值）
- **root finding**

具体规则：

- common time：直接 continuous evaluation（dense output 求值）。
- common range：求解 `R(t) - R_common = 0`。
- event states：优先使用 exact stored event states（如 RTI / SRTI 事件
  状态），不另行采样近似。

## 11. Protocol D — Common Atmospheric Exposure

定义累计 atmospheric exposure：

    tau_ATM(t) = integral_0^t I_ATM(s) ds

其中：

    I_ATM = 1    for atmospheric mode
    I_ATM = 0    for vacuum mode

| 轨迹 | 计入 atmospheric exposure 的 mode | 不计入的 mode |
|---|---|---|
| Qian research trajectory | `ENTRY_CAPTURE`、`QEG_GLIDE` | `GROUND_CONTINUATION`（不属于 research trajectory） |
| Sanger | `SANGER_ATM`（= 1） | `SANGER_VAC`（= 0） |

定义：

    tau_common = min(tau_ATM,Q(T_Q), tau_ATM,S(T_S))

在达到**相同 cumulative atmospheric exposure** 时比较：

- total elapsed time
- range
- altitude
- velocity
- specific mechanical energy
- specific mechanical-energy loss

primary quantity：

    DeltaR_atm_exposure = R_S(tau_common) - R_Q(tau_common)

（positive：相同大气暴露下 Sanger 获得更多射程）

该 protocol 用来量化 **VAC coast 对 downrange extension 的结构贡献**。

## 12. Energy-mechanism diagnostic（能量机制诊断）

Phase E 必须包含 comparison curve：

    range R  vs  specific mechanical-energy loss DeltaE

其中：

    DeltaE(t) = E_initial - E(t)

预期机制特征：

- **Sanger VAC segment** 理论上应呈现 `DeltaE ≈ constant`（近似不变）
  **while range increases**（射程持续增长）。

这作为 mechanism diagnostic，不构成加权评分。

约束：

- **不要定义任意 weighted energy-efficiency score。**
- **不要因为 VAC 数值漂移产生很小负 DeltaE 就做物理 clipping；** 保留 raw
  diagnostic，并按 numerical tolerance 解释。

## 13. Aerodynamic exposure metrics（气动暴露度量）

允许 Phase E 后续比较（bounded to existing frozen model）：

- dynamic pressure：`q = 0.5 * rho * v^2`
- drag deceleration：`a_D = D / m`
- 以及 `max q`、`max a_D`
- 可选 cumulative exposure integrals

**Sanger VAC mode 中 aerodynamic quantities 按 frozen hybrid semantics
视为 `L = D = 0`。**

- 不得因为 atmosphere model 的数学外推在 >100 km 可能给出非零 `rho`，
  就重新启用 aerodynamic force。

## 14. Thermal claims prohibited（热声明禁令）

当前 frozen project **没有正式 heat-rate / thermal-load model**。因此
Phase E **禁止**直接声称：

- heat flux reduced by X
- thermal load reduced by X
- TPS requirement improved by X

除非以后新增并单独验证 thermal model（另行冻结）。

## 15. Ground comparison policy（地面比较政策）

- **Primary Phase E comparison 截止**：`Qian@RTI`、`Sanger@SRTI`。
- **不使用 compatibility ground continuation 作为主要比较。**
- Ground-to-ground comparison：最多作为 appendix / compatibility
  diagnostic。
- **禁止使用 ground range difference 作为 Phase E 核心性能结论。**

## 16. No composite winner score（禁止综合评分）

禁止形如：

    Score = w1 * range + w2 * velocity - w3 * time + ...

的 composite winner score。Phase E **不生成 overall winner score**。

结论必须分别基于以下独立协议：

1. native persistence（Protocol A）
2. common time（Protocol B）
3. common range（Protocol C）
4. common atmospheric exposure（Protocol D）
5. energy mechanism（§12 diagnostic）

## 17. Primary comparison metrics（冻结指标表）

### Native endpoint（Protocol A）

| 指标 | 定义 |
|---|---|
| `T_end` | research duration（RTI / SRTI） |
| `R_end` | research range |
| `h_end` | terminal altitude |
| `v_end` | terminal velocity |
| `E_end` | terminal specific mechanical energy |
| `DeltaE_end` | total specific mechanical-energy loss |

### Common time（Protocol B）

`R`、`h`、`v`、`E`、`DeltaE`、`mode`

### Common range（Protocol C）

`arrival time`、`h`、`v`、`E`、`DeltaE`、`mode`

### Common ATM exposure（Protocol D）

`elapsed time`、`R`、`h`、`v`、`E`、`DeltaE`

### Structural

`ATM duration`、`VAC duration`、`ATM fraction`、`VAC fraction`

### Aerodynamic

`max q`、`max D/m`

### Qian-specific diagnostics

`QEG duration`、`RTI`

### Sanger-specific diagnostics

`skip_count`、`VAC arcs`、`SRTI`

> **Qian-specific 与 Sanger-specific metrics 只能解释内部 mechanism，
> 不能直接当同名一对一性能量。**

## 18. Sign conventions（符号约定）

统一符号（全部代码 / 表格 / 报告必须一致）：

| 量 | 定义 | positive 含义 |
|---|---|---|
| `DeltaR_time` | `R_S - R_Q` | Sanger 同时间射程更远 |
| `DeltaV_time` | `v_S - v_Q` | Sanger 保留更大速度 |
| `time_saving_common_range` | `t_Q - t_S` | Sanger 更早达到共同射程 |
| `DeltaR_atm_exposure` | `R_S - R_Q` | 相同大气暴露下 Sanger 射程增益更多 |

## 19. Units（单位）

- Internal：**SI**。
- Reporting：
  - time：`s`
  - range / altitude：`km`
  - velocity：`km/s` 或 `m/s`，但 **一个表格内必须统一**
  - specific energy：`MJ/kg`
  - dynamic pressure：`kPa` 或 `Pa`，但须明确标注

禁止出现 Phase D 图中曾发现的单位混用：`m / km`、`m/s / km/s`。

## 20. Statistical / causal language（统计与因果语言约束）

Phase E 当前只有 **deterministic baseline comparison**。因此**禁止**使用：

- statistically significant
- confidence interval
- probability
- robust superiority

等措辞（这些属于未来 uncertainty / Monte Carlo 阶段）。

允许的措辞：

    under the frozen baseline configuration, the deterministic comparison
    shows ...

## 21. Phase E scope（范围边界）

Phase E **只比较两个 frozen baselines**。不做：

- gamma0-K sweep
- uncertainty
- Monte Carlo
- optimization
- STM
- saltation
- FTLE

特别强调：

- **不要为了让 comparison 更公平而重新优化 Qian 或 Sanger control** ——
  那会改变研究问题。

## 22. Phase E roadmap（路线图）

| 阶段 | 内容 | 状态 |
|---|---|---|
| **E0** | Comparison Protocol Freeze | **COMPLETE（本文档）** |
| E1 | Comparison Data / Alignment Infrastructure | pending |
| E2 | Common-Time & Common-Range Comparison | pending |
| E3 | Atmospheric Exposure / Energy Mechanism | pending |
| E4 | Native-Endpoint & Structural Diagnostics | pending |
| E5 | Figures / Tables / Scientific Interpretation | pending |
| E6 | Regression / Numerical Audit | pending |
| E7 | Final Report / Freeze | pending |

## 23. E0 acceptance checklist

- [x] frozen comparison objects identified —— **PASS**
- [x] identical IC/K/vehicle/environment required —— **PASS**
- [x] numerical harmonization defined（PRODUCTION_SOLVER_CONFIG）—— **PASS**
- [x] Qian historical baseline remains untouched —— **PASS**
- [x] native endpoint semantic asymmetry documented（RTI vs SRTI）—— **PASS**
- [x] native-endpoint protocol frozen（Protocol A）—— **PASS**
- [x] common-time protocol frozen（Protocol B）—— **PASS**
- [x] common-range protocol frozen（Protocol C）—— **PASS**
- [x] range monotonicity prerequisite recorded —— **PASS**
- [x] continuous interpolation/root-solving rule frozen —— **PASS**
- [x] common atmospheric-exposure protocol frozen（Protocol D）—— **PASS**
- [x] mechanical-energy definition frozen（E = v²/2 − mu/r）—— **PASS**
- [x] energy-mechanism diagnostic frozen（R vs ΔE）—— **PASS**
- [x] aerodynamic exposure metrics bounded to existing model —— **PASS**
- [x] unsupported thermal claims prohibited —— **PASS**
- [x] ground comparison excluded from primary claims —— **PASS**
- [x] composite winner score prohibited —— **PASS**
- [x] sign conventions frozen —— **PASS**
- [x] units frozen —— **PASS**
- [x] deterministic-language constraint recorded —— **PASS**
- [x] Phase E scope boundary recorded —— **PASS**
- [x] E1–E7 roadmap recorded —— **PASS**

## 24. 冻结锚点（E0 依据）

- Phase D final freeze commit：`2089c0d6da0e9700a86a5bdbf121bf38f96b46a4`
- Tag `phase-d-v1.0` = Tag `sanger-baseline-v1.0` = 上述 commit
- Tag `qian-baseline-v1.0` = `d7ad35cd53a8c9ea64a750e47adbbb6db20198b7`
- 生产数值配置：`src/hyptraj/simulation/numerics.py` →
  `PRODUCTION_SOLVER_CONFIG`
- 引力常数：`MU = 9.81 * 6_371_000.0**2`（`src/hyptraj/simulation/trajectory.py`）
- Qian research endpoint：`reason = "qeg_feasibility_loss"`（RTI）
- Sanger research endpoint：`SRTI`（skip-capability loss，状态机 qualified）
- Qian reference artifacts：`results/baseline/qian_continuous_glide/`
- Sanger reference artifacts：`results/sanger_hybrid/baseline/`

# Phase D — Sanger Hybrid Trajectory

日期：2026-08-15（D7A final freeze audit）
分支：`feature/phase-d-sanger-hybrid`
起点 commit：`bf5b5ec`（D6）
规范依据：`docs/phase_d/sanger_model_spec.md`（D0 frozen specification）

## 1. Purpose and scope

Phase D 建立了事件驱动的桑格尔跳跃滑翔（Sanger skip-glide）混合轨迹
baseline：

- D0 数学规范冻结（`sanger_model_spec.md`）；
- D1 SANGER_ATM / SANGER_VAC 连续动力学；
- D2 hybrid 事件原语；
- D3 事件驱动状态机；
- D4 跳跃周期指标；
- D5 canonical production baseline；
- D6 数值与混合拓扑验证。

研究对象为 **unpowered longitudinal lift-supported atmospheric skip
trajectory**。本阶段未做（全部留给后续阶段）：Qian-vs-Sanger
comparison（Phase E）、gamma0-K sweep（Phase F）、STM / saltation
matrix / FTLE（predictability）、Monte Carlo、optimization。

## 2. Frozen physical baseline

| 量 | 值 |
|---|---|
| h0 | 100000 m |
| v0 | 7000 m/s |
| gamma0 | -5 deg |
| theta0 | 0 |
| K = L/D | 3（`ConstantKControl(3.0)`） |
| m | 1000 kg |
| S | 1 m² |
| C_D | 0.2 |
| atmosphere boundary h_atm | 100000 m |
| ATM control | u_L = 1（sigma = 0，全纵向升力） |
| VAC semantics | L = D = 0，重力与球形地球曲率保留 |

上述参数为 **comparative research design choice**（Phase E 公平比较
需要），不是对历史 Sänger 方案的参数主张。

## 3. Sanger mathematical specification

- 状态：`x = [h, v, gamma, theta]^T`，`r = R_E + h`；实现状态顺序
  `[r, theta, v, gamma]`（冻结 convention）。
- ATM equations：冻结 `atmospheric_dynamics`，u_L = 1；
- VAC equations：`L = D = 0`，`g ≠ 0`、curvature ≠ 0；
- switching surface：`G_atm(x) = h - h_atm = r - R_E - h_atm`，
  `nabla G = [1,0,0,0]^T`，reset `R(x) = x`、`DR = I`；
- 完整规范见 `sanger_model_spec.md`（D0，FROZEN）。

## 4. ATM / VAC continuous dynamics

`src/hyptraj/modes/sanger_hybrid.py`：

- `sanger_atm_rhs`：直接委托冻结 `atmospheric_dynamics`（其 gamma_dot
  使用全升力，即 u_L = 1 语义），无第二套 physics；
- `sanger_vac_rhs`：显式 zero-aero 特化
  `dv/dt = -g sin(gamma)`、`dgamma/dt = (v/r - g/v) cos(gamma)`，
  复用冻结 `gravity_acceleration`；
- 诊断原语 `specific_mechanical_energy`（E = v²/2 − mu/r）与
  `specific_angular_momentum`（H = r v cos(gamma)），mu = g0 R_E²。

## 5. Hybrid switching surfaces and events

`src/hyptraj/simulation/sanger_events.py`：

| 事件 | 根 | direction | terminal | 语义 |
|---|---|---|---|---|
| atmosphere exit | h − h_atm | +1 | True | ATM → VAC（upward） |
| atmosphere entry | h − h_atm | −1 | True | VAC → ATM（downward） |
| ATM pull-out | gamma | +1 | False | diagnostic（-→+） |
| VAC apogee | gamma | −1 | False | diagnostic（+→-） |
| SRTI candidate | gamma | −1 | True | 原始 root；资格判定属 D3 |

事件函数为 pure observer（不修改状态、无 reset、无 epsilon）。

## 6. Event-driven state machine

`src/hyptraj/simulation/sanger_trajectory.py`：
`integrate_sanger_hybrid(...)` 从 synthetic E0 起严格交替
ATM/VAC 段，保存 segment / event history 与 hybrid switching 元数据
（x_e、f_minus、f_plus、nabla G、mode_before/after），按 atmospheric
pass history 判定 SRTI，并含 max_time / max_segments 安全守卫。

## 7. Completed skip-cycle definition

严格按 D0 §12：

```
E_i -> P_i -> X_i -> A_i -> E_{i+1}
```

synthetic_initial_entry 允许作为 E0 anchor；`skip_count` = completed
`E_i -> E_{i+1}` 数；terminal incomplete pass（E → P → SRTI）**不**计入。
解析器（D4 `sanger_metrics.py`）严格拒绝 malformed history。

## 8. Canonical Sanger production baseline

- 生成：`python experiments/04_sanger_hybrid/run_sanger_baseline.py`
- 数值配置：**PRODUCTION_SOLVER_CONFIG**（Phase C frozen）——
  `DOP853, rtol=1e-9, atol=[1e-4,1e-11,1e-7,1e-11], max_step=20,
  dense_output=True`
- 状态：**APPROVED FOR FINAL FREEZE**（D6 数值验证通过后；tag 待视觉验收）

**Production baseline（full precision，来自 summary.json）**：

```
completed skip_count = 2

mode sequence:
SANGER_ATM -> SANGER_VAC -> SANGER_ATM -> SANGER_VAC -> SANGER_ATM

event sequence:
synthetic_initial_entry
-> atmospheric_pullout
-> atmosphere_exit
-> vacuum_apogee
-> atmosphere_entry
-> atmospheric_pullout
-> atmosphere_exit
-> vacuum_apogee
-> atmosphere_entry
-> atmospheric_pullout
-> srti

research:
  time_s       = 1119.5459841174863
  range_m      = 6872895.31994491
  max_altitude_m = 130352.12118171807
  max_altitude_time_s = 343.8022448869377

SRTI:
  time_s   = 1119.5459841174863
  altitude_m = 86138.74103438109
  range_m  = 6872895.31994491
  velocity_mps = 5482.946113518439
  gamma_rad ≈ 0（+→− crossing）
```

## 9. Completed skip cycles

| Cycle | entry t [s] | pull-out h [m] | exit t [s] | apogee h [m] | next entry t [s] | ATM dt [s] | VAC dt [s] | ATM ΔR [m] | VAC ΔR [m] | cycle ΔR [m] | ATM ΔE [J/kg] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.0 | 46040.885709159076 | 202.96413572759334 | 130352.12118171807 | 484.6403540462832 | 202.96413572759334 | 281.67621831868985 | 1352050.535954579 | 1780485.4057362329 | 3132535.941690812 | 3538558.359812878 |
| 1 | 484.6403540462832 | 45812.093384065665 | 748.1137977144123 | 102232.57557271793 | 814.8021368979796 | 263.47344366812905 | 66.68833918356734 | 1616144.1872716341 | 391248.4948817687 | 2007392.6821534028 | 3181852.2729807496 |

```
Cycle 0: synthetic E0 -> P0 -> X0 -> A0 -> E1
Cycle 1: E1 -> P1 -> X1 -> A1 -> E2
```

## 10. Sanger Research Terminal Interface

```
E2 -> P2 -> SRTI
```

terminal incomplete atmospheric pass（**不是** Cycle 2 / 第三跳）：

| 量 | 值 |
|---|---|
| entry / pullout / SRTI t [s] | 814.8021368979796 / 969.0696243196126 / 1119.5459841174863 |
| SRTI altitude [m] | 86138.74103438109 |
| SRTI velocity [m/s] | 5482.946113518439 |
| atmospheric duration [s] | 304.74384721950673 |
| range increment [m] | 1732966.696100695 |
| mechanical energy loss [J/kg] | 2880331.9789911285 |

**research endpoint = SRTI**：该 pass 已不再具备完成下一次 atmosphere
exit 的能力（上升段在到达 h_atm 前被重力拉回）。

## 11. Compatibility ground continuation

单独 subsection —— **compatibility / visualization only**，不参与
research metrics（skip_count、SRTI、research time/range 均不受影响）：

```
ground time       = 3508.899047051084 s
ground range      = 13578681.77301601 m
ground velocity   = 159.95363018961257 m/s
duration after SRTI = 2389.3530629335974 s
range after SRTI    = 6705786.4530711 m
compatibility_only  = true
```

**research endpoint = SRTI；compatibility endpoint = ground。**

## 12. Numerical reference and convergence

D6 建立高精度 numerical reference（**非 analytic solution**）：
`DOP853, rtol=1e-12, atol=[1e-7,1e-14,1e-10,1e-14], max_step=0.1 s`。

reference 全精度（来自 `results/.../reference/ref_0_1.json`）：

```
SRTI: t = 1119.5459837862807 s, h = 86138.7409782568 m,
      R = 6872895.318287604 m, v = 5482.946114224176 m/s
```

自稳定性（0.1 vs 0.05 s）：topology identical，max event
Δt ≤ 1.429e-9 s、Δh ≤ 1.397e-7 m、ΔR ≤ 8.018e-6 m。

**Production vs reference**（production 误差 = production 值 −
reference 值，与 D6 summary 记录一致）：

| 量 | 误差 |
|---|---:|
| max event Δt | 5.618e-7 s |
| max event Δh | 5.612e-5 m |
| max event ΔR | 3.200e-3 m |
| max event Δv | 7.057e-7 m/s |
| SRTI Δt | 3.312e-7 s |
| SRTI Δh | 5.612e-5 m |
| SRTI ΔR | 1.657e-3 m |
| SRTI Δv | 7.057e-7 m/s |
| research range error | 1.657e-3 m |
| max altitude error | 4.953e-5 m |

tolerance sweep（rtol 1e-6 → 1e-11）与 max_step sweep（40 → 0.1 s）
误差随收紧单调收敛。详见 `sanger_numerical_validation.md`。

## 13. Hybrid-topology stability

D6 全部 **18 / 18** tested numerical configurations 保持：

```
completed skip_count = 2
mode sequence        = 相同
event sequence       = 相同
terminal_kind        = SRTI
```

```
cases tested        = 18
topology changes    = 0
event-order swaps   = 0   （X1 与 SRTI candidate 先后关系从未翻转）
missing events      = 0
chatter             = 0
```

这证明 skip_count = 2 **不是** production solver 的数值偶然，而是
hybrid topology 的结构性质。

## 14. Topological margins and transversality

| 量 | 值（reference full precision） | 意义 |
|---|---:|---|
| SRTI altitude margin M_h = h_atm − h_SRTI | 13861.2590217432 m（≈13.861 km） | ≫ 数值误差（~1e-4 m）：第三次 skip 的失败不是数值边界效应 |
| second apogee clearance M_A1 = h_A1 − h_atm | 2232.5755237359554 m（≈2.233 km） | ≫ 毫米/厘米级误差：第二次 skip 的存在数值稳健 |
| exit gamma (X1) | +0.02245911898378354 rad | 明确 outward crossing，非 grazing |
| exit dh/dt (X1) | +133.91587577494028 m/s | 事件 transversal |
| entry gamma / dh/dt | −0.022459118983799688 rad / −133.91587577503648 m/s | 明确 re-entry |
| SRTI gamma_dot | −8.719203963150439e-4 rad/s | 非退化 crossing，SRTI root 定位可靠 |

数值误差为毫米/亚毫米级，topology margins 为公里级：第二次 skip 的
存在与第三次 skip 的失败均具有强数值稳健性。事件残差：atmosphere
residual = 0 m、gamma residual ≤ 1.315e-16 rad。未进行 saltation
calculation（属后续阶段）。

## 15. Production numerical configuration

**继续批准** Phase C frozen `PRODUCTION_SOLVER_CONFIG`
（`DOP853, rtol=1e-9, atol=[1e-4,1e-11,1e-7,1e-11], max_step=20`）用于
正式 Sanger baseline。证据：

- **accuracy**：SRTI ΔR = 1.7e-3 m、Δt = 3.3e-7 s；
- **event stability**：事件残差 ~0、crossing 方向全部正确、无 chatter；
- **topology stability**：18/18 case 与 reference 一致；
- **cost**：nfev = 1906、~0.02 s，位于准确度-成本 sweet spot。

配置**未修改**（D6 无权改写 Phase C frozen config）。

## 16. Phase D acceptance

| # | 项 | 状态 |
|---|---|---|
| 1 | D0 mathematical specification | **PASS**（FROZEN） |
| 2 | D1 ATM/VAC continuous dynamics | **PASS** |
| 3 | D2 hybrid event primitives | **PASS** |
| 4 | D3 event-driven state machine | **PASS**（FROZEN） |
| 5 | D4 skip-cycle metrics | **PASS**（FROZEN） |
| 6 | D5 canonical production baseline | **PASS**（APPROVED FOR FINAL FREEZE） |
| 7 | D6 numerical / hybrid-topology validation | **PASS** |
| 8 | Sanger mathematical model | **FROZEN** |
| 9 | Sanger hybrid state machine | **FROZEN** |
| 10 | Sanger skip-cycle definition | **FROZEN** |
| 11 | SRTI definition | **FROZEN** |
| 12 | Sanger canonical production baseline | **APPROVED** |
| 13 | Phase C production numerics for Sanger | **APPROVED** |
| 14 | 18/18 topology stability | **PASS** |
| 15 | research endpoint = SRTI | **PASS** |
| 16 | ground = compatibility only | **PASS** |
| 17 | tests 126 passed、Qian/Sanger regression unchanged | **PASS** |
| 18 | D1-D9 figure visual approval | **PASS**（zai-mcp-server 9/9 视觉检查） |
| 19 | D7 final audit（D7A reference/production 核对 + D7B freeze） | **PASS** |

### Final Phase D acceptance

```
D0 Mathematical specification:   PASS
D1 Continuous dynamics:          PASS
D2 Event primitives:             PASS
D3 Hybrid state machine:         PASS
D4 Skip-cycle metrics:           PASS
D5 Canonical baseline:           PASS
D6 Numerical / topology validation: PASS
D7 Final audit:                  PASS
Figure visual review:            PASS (D1-D9, 9/9)
Final Phase D acceptance:        PASS
```

正式结论：

```
completed skip_count = 2
mode topology: SANGER_ATM -> SANGER_VAC -> SANGER_ATM -> SANGER_VAC -> SANGER_ATM
research endpoint = SRTI
production solver = DOP853, rtol = 1e-9, state-scaled atol, max_step = 20 s
topology validation = 18 / 18 cases match
```

所有 baseline 数值保持不变（本报告数值均为 numerical baseline，**不是**
"真实唯一桑格尔轨迹"、"精确解"或"解析解"）。

## 17. Scope boundary / next phase

Phase D 边界：

- **不**做 Qian-vs-Sanger comparison（Phase E）；
- **不**做 gamma0-K sweep（Phase F）；
- **不**做 STM / saltation / FTLE（predictability）；
- **不**做 Monte Carlo / optimization。

Phase D 核心结论：

> 在 frozen IC / vehicle / environment / K=3 条件下，采用 ATM 全纵向
> 升力 u_L=1 与 VAC L=D=0 形成稳定的 Sanger skip-glide hybrid
> trajectory。canonical production trajectory 完成 **2 次 completed
> skips**，随后第三个 atmospheric pass 无法再次穿越 100 km，在 SRTI
> 结束。该 hybrid topology 在 D6 测试的全部 numerical settings 中保持
> 不变。

本报告数值均为 numerical baseline，**不是**"真实唯一桑格尔轨迹"、
"精确解"或"解析解"。

---

*D7A audit 与 D7B final freeze 完成：D1-D9 图像视觉验收 PASS（9/9），
`sanger-baseline-v1.0` 与 `phase-d-v1.0` 已创建并指向最终冻结 commit。
Phase D COMPLETE。*

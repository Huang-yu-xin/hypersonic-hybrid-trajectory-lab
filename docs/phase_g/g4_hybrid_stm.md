# G4 — Hybrid STM Validation（混合 STM 链式传播与全轨迹验证）

状态：**COMPLETE**（G4 accept，2026-08-18）
分支：`feature/phase-g-predictability`
G4 起点：`a7119c0`（G3 commit）
G2 依据：`docs/phase_g/g2_continuous_stm.md`（连续 STM）
G3 依据：`docs/phase_g/g3_transverse_saltation.md`（saltation / event-time）
Machine-readable artifact：`tests/data/phase_g4_hybrid_stm_v1.json`
（schema `phase-g4-hybrid-stm-v1`）

## 1. 目标与边界

G4 把 G2 已验证的 continuous STM 与 G3 已验证的 saltation **正确串联**成
固定时间、topology-preserving 的完整 hybrid flow state transition matrix，
并用完整 frozen nonlinear hybrid trajectory 的双侧 initial-state finite
difference 独立验证。

```
Phi_H(T, t0) = C_{N+1} Xi_N C_N ... Xi_2 C_2 Xi_1 C_1
```

G4 = 固定时间 hybrid flow derivative；G5 = predictability metrics /
scientific scaling / terminal descriptive；G6 = grazing。禁止 RTI/SRTI
terminal sensitivity、FTLE、SVD ranking、canonical scaling freeze、
grazing、Monte Carlo、optimization、gamma0-K rescan。

## 2. 矩阵乘法约定（incremental，G0 §0）

```
Phi_global = I
Phi_global = C @ Phi_global            # continuous segment
Phi_minus   = Phi_global               # 第 k 个 true switch 前
eta_k       = q_local_k @ Phi_minus    # 全局事件时间梯度
Phi_global = Xi @ Phi_global           # saltation
...（末尾）Phi_global = C_final @ Phi_global
```

## 3. Initial discrete-mode 语义（G4 §5）

```
Qian:   initial discrete mode = ENTRY_CAPTURE
Sanger: synthetic_initial_entry -> initial_mode = SANGER_ATM（t=0 无 saltation）
```

求的是 **frozen initialization rule 下、initial discrete mode 固定时的
continuous-state derivative**；Sanger 初始状态 h0=h_atm 但初始为 SANGER_ATM，
禁止按 ±δr 自行重定义 initial mode（modes：+δr→VAC / −δr→ATM 一律不允许）。
radial perturbation 若造成明显不同 topology → reject 该 side 并如实记录。
`initial_mode_fixed = SANGER_ATM`、`synthetic_initial_entry_saltation =
false`（snapshot 持久化）。

## 4. 验证端点（G0/G4 §6 本地固定时间；最终 margin 从 structured 读取）

| model | T [s] | true-switch signature | n | endpoint mode | terminal margin [s] | nearest switch margin [s] |
|---|---|---|---|---|---|---|
| Qian | 600 | (qian_capture,) | 1 | QEG_GLIDE | 123.0（RTI @ 723.04） | 506.6 |
| Sanger | 600 | (exit, entry) | 2 | SANGER_ATM | 519.5（SRTI @ 1119.55） | 115.4 |
| Sanger | 900 | (exit, entry, exit, entry) | 4 | SANGER_ATM | 219.5 | 85.2 |

所有 endpoint 均位于两个 events 之间、research terminal 之前、成功
frozen research trajectory 内、endpoint mode 明确。

## 5. Hybrid factor 表示与实现

`src/hyptraj/predictability/hybrid_stm.py`:

```
HybridFactor      kind=CONTINUOUS|SALTATION|SALTATION_NAIVE；mode/event；
                  t_start/t_end；matrix；source；metadata
HybridEventCumulative  event_name/index/time；phi_minus_initial；q_local；
                       eta（= q @ Phi_minus）；Xi；phi_plus_initial；
                       denominator；event_resolution
HybridStmResult   model/t0/t_final/x0/x_final/initial_mode/endpoint_mode/
                  topology_signature/factors/event_cumulatives/phi_final/
                  solver_label/terminal_margin/event_margins
build_hybrid_stm(model, x0, T, ..., research_solver, stm_solver,
                 computational_scaling, include_saltation)
build_split_tail(...)          # split/composition 审计（§18）
qian_no_saltation_negative_control(...)   # C@I@C 对照（§13/§39）
true_switch_events_before(...) # 从 frozen records 读真实 switch
```

- continuous factor：直接调 G2 `integrate_continuous_stm`（各自恢复为
  physical raw STM），**不重写 augmented ODE**；
- saltation factor：复用 G3 `identity_reset_saltation` /
  `linearize_qian_capture_event` / `linearize_sanger_event_record`（G3 最小
  公共 adapter，非破坏性；G3 公式/语义/regression 不变，G3 tests 全 PASS）；
- each factor 从 **exact structured event state** 开始（identity reset，
  无 epsilon-offset / sampled-grid / 插值近似）；
- 状态连续性检查：continuous factor 末端 x1 vs exact event state（实测
  ~1e-9..1e-8）。

### 排除事件（非 factor）

```
Sanger pullout / VAC apogee / synthetic_initial_entry / Qian RTI / Sanger SRTI
```

存在 trajectory metadata 但不产生 Xi / matrix factor / Phi restart。

## 6. 全局事件时间梯度

```
eta_k = d t_{e_k}/d x_0 = q_k @ Phi_k^-
```

每个 true switch 保存 `q_local`、`phi_minus_initial`、`eta_initial`。

## 7. Topology gate（G4 §24）

```
TOPOLOGY_PRESERVED   同 true-switch count + 同 kind 序列 + 同 endpoint mode
                     + trajectory 存活过 T + （Qian）post-Capture QEG strict
                     INTERIOR 到 T
TOPOLOGY_CHANGED     missing/extra switch、不同 count、terminal<T、
                     不同 endpoint mode、QEG active-set branch 改变
                     （reason：terminal_before_fixed_endpoint /
                     QEG_ACTIVE_SET_CHANGED / ...）
EVENT_ORDER_CHANGED  同类 collection 但时序不同
GRAZING_CROSSED      仅当 frozen metadata 明确 grazing_or_unresolved（现状无）
NUMERICAL_FAILURE    仅真正 solver/root failure（不把 topology change 当 numerical）
```

ordinary hybrid STM acceptance 只允许 `TOPOLOGY_PRESERVED`。双侧（G2R
风格）pair gate：± 均 TOPOLOGY_PRESERVED 才进入误差指标，分别保存
classification/reason/signature/endpoint_mode。

## 8. 独立 nonlinear 比较（G4 §20-§22, §26-§28）

independent path 直接运行 frozen research integrators
（`integrate_qian_research_trajectory` / `integrate_sanger_research_trajectory`），
通过 dense output 在**相同绝对 elapsed time T** 提取状态与 true-switch
times；禁止 sampled-row / 插值 / event-conditioned endpoint。

```
D_j^NL(T) = [x(T; x0+eps_j e_j) - x(T; x0-eps_j e_j)] / (2 eps_j)
D^NL(T) ≈ Phi_H(T, 0)（仅 pair-valid columns）
```

FD base step = G0 candidate-B `[100 m, 1e-5 rad, 1 m/s, 1e-4 rad]`
（**FD validation perturbation scale，不是 canonical scientific scaling**）；
multiplier {1e-3 … 10}。production 全 sweep 观察 solver-noise/plateau/
truncation/topology-changing 区域；plateau 处用 REF-0.1 做 reference-grade
confirmation。

## 9. 验证结果

### 参考自稳定（REF-0.1 vs REF-0.05，material relative）

| endpoint | Phi material rel diff | event-time max diff | eta max diff | status |
|---|---|---|---|---|
| Qian T600 | 2.3e-11 | 1.4e-11 | 1.2e-9 | PASS |
| Sanger T600 | 1.0e-10 | 5.6e-10 | 5.2e-9 | PASS |
| Sanger T900 | 4.6e-11 | 1.4e-9 | 8.8e-8 | PASS |

（raw Phi 量级 O(1e5)，max-abs 差异 ~1e-5–2.6e-6 为大量级项的自然结果；
material relative ≪ 1e-5。）

### 全轨迹 nonlinear FD（production sweep plateau + REF-0.1 ref-grade）

| endpoint | plateau mult | plateau material rel | ref-grade material rel | classifications |
|---|---|---|---|---|
| Qian T600 | 1.0 | 5.8e-7 | 6.3e-7 | ALL TOPOLOGY_PRESERVED |
| Sanger T600 | 1e-3 | 3.5e-7 | 2.2e-6 | ALL PRESERVED |
| Sanger T900 | 1e-3 | 3.8e-7 | 2.0e-6 | ALL PRESERVED |

全部 ≪ 1e-5。large-epsilon 出现 topology change 是 valid 观察（Qian
mult≥3 仍有 PRESERVED；见 snapshot sweep；不隐藏、不缩小 ε 掩盖）。

### 全局事件时间 FD（eta vs nonlinear FD，material columns）

Sanger X0/E1/X1/E2 与 Qian capture 的 material columns rel 2e-9–9e-7；
theta 切线列只报 absolute residual（root-location 噪声放大，见 §11）。

### 结构不变量

```
theta 全局列 = [0,1,0,0]^T         PASS（所有 endpoint，residual 0）
Qian 全局 gamma 行 = [0,0,0,0]     PASS（exact；capture saltation 消除
                                       进入 QEG 后的 first-order gamma normal）
true-switch count == Xi count      PASS
diagnostics / synthetic E0 排除    PASS
hybrid split/composition          PASS（Sanger t_a=60、Qian t_a=60）
identity-reset continuity         PASS（state_cont_err ~1e-9..1e-8）
```

### Qian no-saltation negative control

```
correct（C @ Xi_capture @ C）material rel vs FD:  ~1e-6  （PASS）
naive（C @ I @ C）material rel vs FD:           ~1e+3   （FAIL，预期）
correct gamma 行 = 0；naive gamma 行第 4 项 = -3.5（错误）
FD gamma 行 = 0
```

→ **state-continuous Capture 仍必须使用 saltation**（negative control 不
作为 production result）。

### Computational scaling audit（continuous factors 用 I/A/B/C，恢复 raw 后）

| endpoint | 与 identity 的最大恢复差（相对 Phi 量级） |
|---|---|
| Qian T600 | 1.4e-12 |
| Sanger T600 | 2.4e-12 |
| Sanger T900 | 4.9e-12 |

→ **computational representation invariant**（COMPUTATIONAL REPRESENTATION
ONLY）；`CANONICAL SCIENTIFIC SCALE NUMERIC VALUES PENDING`（G5）。

## 10. 实现的 API（`hybrid_validation.py`）

```
HybridTopologyGate（TOPOLOGY_PRESERVED/CHANGED/EVENT_ORDER_CHANGED/
                     GRAZING_CROSSED/NUMERICAL_FAILURE）
run_nonlinear_hybrid(model, x0, env, vehicle, k, research_solver)
fixed_time_state(collector, t)
classify_perturbed_topology(...)
nonlinear_fixed_time_state(...)
hybrid_fixed_time_fd_sweep(...)      # ± pair gate + per-column FD
global_event_time_fd(...)            # topology-position + kind matching
HYBRID_FD_BASE_STEP / HYBRID_FD_MULTIPLIERS
```

## 11. 已知限制 / 观察

- theta 切线列（Qian/Sanger 的 delta-theta0 事件时间）在极小 ε 下表现为
  absolute residual ~3e-5..1e-4（r/v/γ 理论零项被 1/(2εθ) 放大的
  solver/root 噪声 ~1e-8 m / 2e-8 rad），属 structural-zero 报告，非
  hybrid STM 误差；material 列 rel 1e-8..1e-6。
- raw Phi 量级大（~1e5），参考自稳定与 scaling audit 均以 material
  relative / relative-to-Phi-scale 判定（1e-11..1e-12）。
- G4 不冻结 scientific canonical scaling；grazing threshold / anchors 全
  留给 G6。

## 12. G5 handoff

Fixed-time topology-preserving hybrid STM（含全局事件时间梯度）已冻结并
经完整 nonlinear FD 独立验证。G5 可用 scaled hybrid STM
`S^{-1}Phi_H S` 计算固定时间 predictability 指标 / 选择 scientific
canonical scale / 报告 terminal descriptive sensitivity。

**G4 = COMPLETE；等待人工验收后再进入 G5。**
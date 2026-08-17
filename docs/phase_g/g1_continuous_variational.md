# G1 — Continuous Variational Dynamics（连续变分动力学与 Jacobian 验证）

状态：**COMPLETE**（G1 accept，2026-08-18）
分支：`feature/phase-g-predictability`
G1 起点：`9db3a35`（G0 commit）
G0 依据：`docs/phase_g/predictability_protocol.md`（G0 FROZEN）
Machine-readable artifact：`tests/data/phase_g1_continuous_jacobian_v1.json`
（schema `phase-g1-continuous-jacobian-v1`）

## 1. 目标与边界

G1 建立并验证 Phase G 所需的 continuous-mode Jacobian：

```
A_m(x) = d f_m / d x,     d(Phi)/dt = A_m(t) Phi
```

覆盖四个 frozen continuous modes：

```
Qian ENTRY_CAPTURE   == frozen atmospheric_dynamics（u_L = 1）
Sanger SANGER_ATM    == 同一 frozen atmospheric RHS
Sanger SANGER_VAC    == frozen sanger_vac_rhs（L = D = 0）
Qian QEG_GLIDE       == interior branch（0 < u_L* < 1，gamma_dot = 0）
```

本轮重点是 **local continuous linearization correctness**；明确不做：
full STM propagation、hybrid STM、saltation、FTLE、grazing、terminal
sensitivity（G2–G6 范围）。**不跨任何 hybrid event**。

## 2. State convention 与 Jacobian 约定

严格沿用 G0 §3/§4 冻结约定：

```
x = [r, theta, v, gamma]^T,   h = r - R_E,  R_E = 6 371 000 m
A_ij = d f_i / d x_j
columns: r, theta, v, gamma        （columns 顺序 = 初始扰动分量）
rows:    r_dot, theta_dot, v_dot, gamma_dot
Phi(t0,t0) = I,  rows = output, columns = initial perturbation
```

不转换为 `[h,v,gamma,theta]`。

## 3. 数学推导（对 frozen RHS 逐项独立推导）

Frozen atmospheric RHS（`models/dynamics.py`，`h = r - R_E > 0` 研究区间）：

```
g   = mu / r^2,            mu = g0 R_E^2
rho = rho0 exp(-(r - R_E)/H)
d   = D/m = rho v^2 S C_D / (2m)
ell = L/m = K d            （ConstantKControl：K 常数，dK/dx = 0）

r_dot     = v sin gamma
theta_dot = v cos gamma / r
v_dot     = -d - g sin gamma
gamma_dot = ell/v + (v/r - g/v) cos gamma
```

偏导：

```
dg/dr    = -2g/r
drho/dr  = -rho/H   ->  dd/dr = -d/H,    dd/dv = 2d/v
                          dell/dr = -ell/H,  dell/dv = 2ell/v
```

### 3.1 A_atm（ENTRY_CAPTURE / SANGER_ATM，constant K）

```
        [     0              0        sin gamma        v cos gamma     ]
A_atm = [ -v cos/r^2         0        cos/r           -v sin/r        ]
        [ d/H + 2g sin/r     0        -2d/v           -g cos          ]
        [ -ell/(Hv) + (-v/r^2 + 2g/(rv)) cos ,   0,   ell/v^2 + (1/r + g/v^2) cos ,  -(v/r - g/v) sin ]
```

（行 4 三个非零元按 columns r, v, gamma 对应；theta 列全零。）

### 3.2 A_vac（Sanger VAC，L = D = 0）

```
A_vac = A_atm 在 d = 0, ell = 0 下的形式：
        行 2: [2g sin/r, 0, 0, -g cos]
        行 3: [(-v/r^2 + 2g/(rv)) cos, 0, (1/r + g/v^2) cos, -(v/r - g/v) sin]
```

**VAC Jacobian 不依赖 rho / H / K / C_D / S**（f_vac 本身不含气动项），
`vehicle` 仅为接口对称保留（与 frozen `sanger_vac_rhs` 一致）。

### 3.3 A_QEG,int（smooth interior，0 < u_L* < 1）

QEG：`u_L = clip(u_L*, 0, 1)`，`u_L* = L_req / L`，
`L_req = m(g - v^2/r) cos gamma`。interior 内 `u_L L = L_req`，因此：

```
gamma_dot = L_req/(mv) + (v/r - g/v) cos gamma
          = (g/v - v/r) cos gamma + (v/r - g/v) cos gamma = 0
f_QEG,int = [v sin gamma,  v cos/r,  -d - g sin gamma,  0]
A_QEG,int = 行 1-3 同 A_atm，行 4 = [0,0,0,0]
```

**两个强 invariant（G1 验证通过）**：QEG interior `gamma_dot ≈ 0`
（仅 FP roundoff，实测 ~1e-19 rad/s）；Jacobian 行 4 = 0。

## 4. QEG active-set 数学（G1 §7–§9 冻结）

四种状态，**精确**分类（比值精确比较，无 invented numerical threshold）：

```
LOWER_SATURATED     u_L* < 0
INTERIOR            0 < u_L* < 1
UPPER_SATURATED     u_L* > 1
NONDIFFERENTIABLE   u_L* == 0 或 u_L* == 1
```

数值诊断（仅报告，不用于分类）：

```
distance_to_0 = |u_L*|
distance_to_1 = |1 - u_L*|
```

边界行为：

- lower saturated（u_L=0）：v_dot 仍含 drag，gamma_dot 升力项为零；
- upper saturated（u_L=1）：Jacobian 与 full atmospheric 相同；
- 精确 clipping boundary（u_L*=0 或 1）：**不伪造唯一 smooth derivative**，
  `qeg_interior_jacobian` 抛 `QegBoundaryError`（含 RTI 邻域 u_L*→1）；
- RTI event point 不作为 smooth-interior acceptance 点。

## 5. Constant-K derivative semantics（G1 §10）

- G1 baseline 使用 frozen `ConstantKControl`：`dK/dx = 0` 精确成立；
- API 只接受 `ConstantKControl` / 标量 K（`constant_k_value`）；任意
  callable 抛 `TypeError` —— **禁止**静默假定 state-dependent control
  的 state 导数为零；
- 不做通用 optimal-control differentiation framework。

## 6. Numerical Jacobian oracle（G1 §11）

`finite_difference_jacobian(rhs, state, steps, multiplier, scheme)`：

- 独立于解析公式（直接对 frozen RHS 求值）；
- 显式 step vector `[100 m, 1e-5 rad, 1 m/s, 1e-4 rad]`（G0 scaling
  candidate B 仅作 **FD step reference scale**，**不是** canonical state
  scaling，不是 Phase-G metric）；
- multiplier sweep：`1e-3, 1e-2, 1e-1, 1, 10`；
- scheme：central3（默认）/ central5；
- error accounting（`jacobian_error_summary`）：max abs、materially
  nonzero 上的 max rel、per-row/per-column、theta-column residual、
  known-zero 只报 absolute residual（不做近零分母相对误差）。

## 7. Representative states（G1 §12）

从 frozen research trajectories（PRODUCTION_SOLVER_CONFIG +
E0.1 dense-output observer）提取真实 interior states，每 mode 4 个，
覆盖 early / middle / late continuous segment；**每个 sample 距任意
事件 ≥ 2 s**（含 pullout / apogee 等 diagnostic events）；**不使用**
hybrid switch 点、RTI、SRTI、grazing anchors、QEG clipping boundary。
VAC samples 全部来自真实 `SANGER_VAC` segments（h > h_atm，非人工
改标 ATM state）。QEG samples 全部验证 `0 < u_L* < 1`（strict
interior）。

见 `tests/data/phase_g1_continuous_jacobian_v1.json` 的 `per_mode.*.samples`。

## 8. Numerical validation 结果（G1 §13–§15）

FD 扫描（multiplier 1e-3 … 10）× 4 modes × 4 samples：

| mode | samples | plateau region | best max abs | best max rel（materially nonzero） |
|---|---|---|---|---|
| ENTRY_CAPTURE | 4 | mult ∈ [1e-2, 1e-1] | 2.4e-9 | 2.4e-11 |
| QEG_INTERIOR | 4 | mult ∈ [1e-2, 1e-1] | 6.3e-10 | 3.0e-9 |
| SANGER_ATM | 4 | mult ∈ [1e-2, 1e-1] | 1.8e-11 | 8.4e-11 |
| SANGER_VAC | 4 | mult ∈ [1e-2, 1e-1] | 9.9e-8 | 1.7e-11 |

收敛形态（所有 samples 一致）：

```
mult 1e-3 ~ 1e-2:  roundoff 主导 / plateau（error ~ 1e-9 ~ 1e-11）
mult 1e-2 ~ 1:     truncation 主导（central3, O(h^2)，error 随 h 平方增长）
mult 10:           truncation 主导放大（error ~ 1e-3 ~ 1e-4 量级）
```

全部 materially nonzero entries 相对误差 **≪ 1e-6 target**
（多数 entry 达到 1e-9–1e-11）；少数接近 roundoff 下限的 entry
（如 QEG gamma≈0 邻域小项）在 plateau 区仍在 3e-9 量级，无需放宽
tolerance 的解释路径：FD cancellation（v·sinγ 大项相消）+ 小真值。

### Known-zero invariants（全部 PASS）

```
theta column（analytic = 0 exact；FD residual < 1e-8）
QEG interior row 4（= 0 exact；frozen RHS gamma_dot ~ 1e-19 rad/s）
ENTRY_CAPTURE == SANGER_ATM（同一 frozen RHS，矩阵逐元素相等）
VAC independent of rho / H / K / C_D / S / h_atm（逐元素相等）
```

## 9. Minimal variational RHS（G1 §16）

`src/hyptraj/predictability/stm.py`：

```
dphi = A @ phi        （Phi, A 均 (4,4)）
Phi(t0,t0) = I        （state_transition_initial_value）
```

已验证：`Phi = I -> dPhi = A`；形状守卫 `(4,4)`。**禁止且未实现**：
`solve_ivp` over `[x, Phi]`、full continuous STM integration、
event-spanning propagation、saltation insertion（G2/G3/G4）。

## 10. 实现的 API（`src/hyptraj/predictability/jacobian.py`）

```
atmospheric_jacobian(state, env, vehicle, k)          # (4,4)，constant K
entry_capture_jacobian(...)                           # = atmospheric（别名）
sanger_atm_jacobian(...)                              # = atmospheric（别名）
sanger_vac_jacobian(state, env, vehicle)              # (4,4)，无气动依赖
qeg_interior_jacobian(state, env, vehicle, k)         # interior only
u_l_star(state, env, vehicle, k)                      # L_req / L（frozen 原语）
classify_qeg_active_set(u_l_star)                     # 4 状态精确分类
qeg_distance_metrics(u_l_star)                        # (d0, d1) 诊断
finite_difference_jacobian(rhs, state, steps, ...)    # FD oracle
jacobian_error_summary(A_ana, A_fd, ...)              # dimension-aware 误差
frozen_rhs(mode, env, vehicle, k)                     # frozen RHS wrapper
analytic_jacobian(mode, state, env, vehicle, k)       # dispatch
representative_continuous_states(mode, env, veh, ini, k, ...)
constant_k_value(control_or_k)                        # constant-K contract
```

`src/hyptraj/predictability/stm.py`：`variational_rhs(phi, a)`、
`state_transition_initial_value()`。

## 11. 已知限制 / G2 handoff

- 解析 Jacobian 定义域：正高度研究区间 `h > 0`（frozen RHS 的
  `max(alt,0)` clamp 在 `h ≤ 0` 处非光滑，不进入 G1 acceptance）；
- `u_L*` 在 `L ≤ 0` 时无定义（`ValueError`；正常 research 区间不出现）；
- QEG saturation branches（u_L=0 / u_L=1 的完整 branch-aware Jacobian）
  G1 只冻结分类与拒绝语义，不实现 branch 公式（本轮重点 = interior）；
- VAC / QEG / ATM 的跨事件（saltation / event-time / STM propagation）
  全部留给 G2–G4。

**G2 handoff**：连续 mode 内 `A_m` 已 freeze 且 FD 验证通过 →
G2 可直接把 `A_m` 接入 augmented-state variational integrator
（`dphi/dt = A(t) phi`），并做 full continuous STM 的独立收敛验证。

## 12. G1 acceptance

- [x] ATM / VAC / QEG-interior 解析公式与 frozen source 独立推导一致
- [x] ENTRY_CAPTURE == SANGER_ATM（回归 invariant）
- [x] theta column = 0（analytic exact / FD residual < 1e-8）
- [x] QEG interior gamma_dot ≈ 0（FP roundoff only）+ row 4 = 0
- [x] QEG active-set 精确分类 + clipping boundary 拒绝 smooth Jacobian
- [x] VAC 与 rho / H / K / C_D / S 无关
- [x] FD oracle 独立验证（4 modes × 4 samples，best rel ≪ 1e-6）
- [x] step-size 收敛形态确认（roundoff plateau + O(h²) truncation）
- [x] minimal variational RHS（Phi=I -> dPhi=A）+ 形状守卫
- [x] invalid states（v≤0 / r≤0 / shape）拒绝
- [x] constant-K semantics（TypeError for callable control）
- [x] snapshot `tests/data/phase_g1_continuous_jacobian_v1.json` 冻结
- [x] G0 语义测试更新（placeholder guard 仅保留 G2-G6 模块）+ 全部 PASS
- [x] 完整 pytest PASS
- [x] frozen physics / G0 protocol source 零修改
- [x] 无 G2-G5 scope leak

**G1 = COMPLETE；等待人工验收后再进入 G2。**
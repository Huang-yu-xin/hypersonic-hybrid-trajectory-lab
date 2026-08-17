# Phase G — Predictability Protocol（G0 冻结版）

## Status

    Phase G status:   G0 COMPLETE（Predictability Protocol Freeze）
    Branch:           feature/phase-g-predictability
    Created from:     phase-f-v1.0（96253f1ef7785764d8da3156d7d614d2b244b577）
    G0 freeze date:   2026-08-18
    Source of truth:  This document —— Phase G 全部 predictability 代码 /
                      figures / claims 的唯一权威依据（protocol）。

本文档冻结 Phase G 的数学语义：state convention、STM 行列约定、扰动范围、
continuous Jacobian 定义、saltation / event-time 公式与符号、reset 约定、
事件分类、grazing 政策、state scaling 约定、fixed-time 与
event-conditioned predictability 定义、FTLE 定义、representative set、
validation protocol 与 numerical reference 政策。G1 及以后的实现必须与本
协议一致；任何冲突必须先修订本协议并重新冻结。

**G0 不创建 final tag**（不创建 `phase-g-v1.0` / `predictability-v1.0`）。
**G0 不进入 G1。**

机器可读镜像：`src/hyptraj/predictability/protocol.py` →
`machine_readable_protocol()`（schema `phase-g-predictability-protocol-v1`）。

---

## 1. 硬性约束（G0 冻结边界）

1. **禁止修改 Phase A–F frozen physics**。
2. 禁止修改：Qian Capture 定义、Qian RTI 定义、Sanger atmosphere boundary、
   Sanger ATM/VAC physical dynamics、Sanger reset semantics、
   F2.1 dense-recovered event semantics、`PRODUCTION_SOLVER_CONFIG`。
3. 禁止移动、删除或 force-update 已有 frozen tags。
4. G0 **不创建 final tag**。
5. 本轮只允许：source audit；protocol/docs；metadata abstraction；
   semantic/unit tests；small-scale protocol validation / scaling audit。
6. 本轮**禁止进入 G1**：不实现完整 continuous Jacobian、不实现
   variational integration、不实现完整 STM propagation、不做 FTLE
   production calculation、不做 Monte Carlo、不做 uncertainty propagation、
   不做 optimization、不重新扫描 gamma0-K 参数域。
7. **Phase F 的 parameter-output Jacobian 与 Phase G 的 STM 严格区分**：

   ```
   Phase F:   d y / d gamma0,  d y / d K      (fixed-topology 参数灵敏度)
   Phase G:   Phi(t, t0) = d x(t) / d x_0     (initial-state 映射 Jacobian)
               + hybrid switch 后的 flow-map derivative (saltation)
   ```

---

## 2. 上游 frozen baseline（引用，不重述）

Phase G 建立在以下 frozen 内容之上（全部复用，禁止复制第二套）：

- Phase C numerics：`PRODUCTION_SOLVER_CONFIG`（DOP853 / rtol=1e-9 /
  atol=[1e-4, 1e-11, 1e-7, 1e-11] / max_step=20 s / dense_output=True）；
- Phase C 高精度 reference 语义（DOP853 / rtol=1e-12 / atol=[1e-7,1e-14,
  1e-10,1e-14] / max_step=0.1 s，`comparison_validation.REFERENCE_SOLVER_CONFIG`）；
- Sanger 数学规范（`docs/phase_d/sanger_model_spec.md`，D0 FROZEN）；
- Phase E 比较对象与终态语义（`docs/phase_e/comparison_protocol.md`）；
- Phase F 参数/拓扑表征（`docs/phase_f/sensitivity_protocol.md`）与
  regression snapshot（`tests/data/phase_f_gamma_k_sensitivity_v1.json`）；
- Phase E regression snapshot（`tests/data/qian_sanger_comparison_v1.json`）。

---

## 3. State convention（G0 冻结）

冻结实现状态（`src/hyptraj/models/dynamics.py`、`sanger_trajectory.py`
一致）：

```
x = [r, theta, v, gamma]^T

state[0] = r          [m]
state[1] = theta      [rad]
state[2] = v          [m/s]
state[3] = gamma      [rad]
```

其中：

```
h = r - R_E,   R_E = 6 371 000 m
```

任何 Phase-G mathematical notation 不得偷偷把 implementation ordering
改成 `[h, v, gamma, theta]`；除非明确声明只是显示层重排
（D0 spec §3 已建立该约定：数学记号 `[h,v,gamma,theta]` 与实现记号
`[r,theta,v,gamma]` 一一对应，实现顺序永远不变）。

**STM 行列语义（冻结）**：

```
rows    = output state component
columns = initial perturbation state component

Phi_ij(t, t0) = d x_i(t) / d x_0,j
Phi(t0, t0)   = I
```

### 3.1 与 Phase F 参数 Jacobian 的区别（文档必须解释）

Phase-F 研究的是 parameter-output derivative：

```
d y_terminal / d gamma0,   d y_terminal / d K
```

在 **fixed exact topology interior** 定义，单位 per radian / per unit K，
不是 STM / saltation（F4 冻结）。

Phase-G 研究的是 initial-state perturbation 映射：

```
d x(t) / d x_0,   d t_e / d x_0（event-time sensitivity）
```

注意：虽然 `gamma0` 在 Phase F 中作为参数扫过，Phase G 中的
`delta gamma_0` 是 **state component perturbation**（第 4 列对应
`x_0,3 = gamma_0`），矩阵元是 `d x_i(t) / d gamma_0`。

---

## 4. Perturbation scope（G0 冻结）

Phase G 第一版**只研究 initial-state perturbation**：

```
delta x_0 = [delta r_0, delta theta_0, delta v_0, delta gamma_0]^T
```

**禁止**把以下量加入 augmented sensitivity vector：

```
gamma0 parameter（作为独立参数的重复研究）
K parameter
vehicle parameters（m, S, C_D …）
atmospheric parameters（h_atm, H, rho0 …）
```

理由：Phase G 是 state map 分析，不是参数扫描（Phase F 已覆盖参数
扫描；Phase G 若需要参数扰动，必须显式声明为 augmented-state 语义，
不在 G0 范围内）。

---

## 5. Event taxonomy（正式冻结）

统一分类词汇（`EventClassification`）：

| 分类 | 含义 |
|---|---|
| `TRUE_HYBRID_MODE_SWITCH` | 模式/vector field 真正改变；状态连续但 flow-map derivative 需要 saltation |
| `RESEARCH_TERMINAL` | 轨迹在该事件结束；研究 event-time + terminal-map sensitivity；禁止发明 post-terminal mode / saltation |
| `DIAGNOSTIC` | 轨迹特征事件，不改变模式；永不入 saltation |

### 5.1 Qian Capture（`qian_capture`）

```
surface  g_c(x) = gamma
normal   n_c = [0, 0, 0, 1]^T
direction +1（gamma: - -> +）
transition  ENTRY_CAPTURE -> QEG_GLIDE
classification  TRUE HYBRID MODE SWITCH
reset   x+ = x-（DR = I）
vector field 在事件处变化（u_L 从 1 跳到 clip(u_L*, 0, 1)）
-> NEEDS SALTATION
```

frozen 事件工厂（`make_capture_event`）已标注 `hybrid_switch = True`。

### 5.2 Qian RTI（`qian_rti`）

```
surface  L_req - L = 0（QEG feasibility loss，u_L* -> 1）
direction +1
classification  RESEARCH TERMINAL
处理：event-time sensitivity + terminal-map sensitivity
禁止：inventing a post-RTI research mode / RTI saltation for notation
```

`GROUND_CONTINUATION` 只属于 historical compatibility continuation；
默认 Phase G 高速 research interval 在 RTI 结束。

### 5.3 Sanger atmosphere exit（`sanger_atmosphere_exit`）

```
surface  G_h(x) = h - h_atm
normal   n_h = [1, 0, 0, 0]^T
direction +1（dh/dt > 0）
transition  SANGER_ATM -> SANGER_VAC
reset   x+ = x-，DR = I
classification  TRUE HYBRID MODE SWITCH
-> NEEDS SALTATION
```

### 5.4 Sanger atmosphere entry（`sanger_atmosphere_entry`）

```
同一 surface  G_h = h - h_atm
direction -1（dh/dt < 0）
transition  SANGER_VAC -> SANGER_ATM
reset   x+ = x-，DR = I
classification  TRUE HYBRID MODE SWITCH
-> NEEDS SALTATION
```

### 5.5 Sanger atmospheric pullout（`sanger_atmospheric_pullout`）

```
surface  gamma = 0
direction +1
mode     SANGER_ATM -> SANGER_ATM
classification  DIAGNOSTIC EVENT
-> NO SALTATION
```

### 5.6 Sanger VAC apogee（`sanger_vac_apogee`）

```
surface  gamma = 0
direction -1
mode     SANGER_VAC -> SANGER_VAC
classification  DIAGNOSTIC EVENT
-> NO SALTATION
```

### 5.7 Sanger SRTI（`sanger_srti`）

```
classification  RESEARCH TERMINAL（skip-capability loss）
处理：event-time sensitivity + terminal-map sensitivity
禁止：fake post-SRTI mode / fake SRTI saltation
```

### 5.8 完整 taxonomy 表

| event | surface | direction | mode_before | mode_after | classification | reset | saltation? | terminal sensitivity? |
|---|---|---|---|---|---|---|---|---|
| qian_capture | g_c = gamma | +1 | ENTRY_CAPTURE | QEG_GLIDE | TRUE_HYBRID_MODE_SWITCH | x+=x- (DR=I) | **YES** | no |
| qian_rti | L_req − L = 0 | +1 | QEG_GLIDE | — | RESEARCH_TERMINAL | — | no | **YES** |
| sanger_atmosphere_exit | G_h = h − h_atm | +1 | SANGER_ATM | SANGER_VAC | TRUE_HYBRID_MODE_SWITCH | x+=x- (DR=I) | **YES** | no |
| sanger_atmosphere_entry | G_h = h − h_atm | −1 | SANGER_VAC | SANGER_ATM | TRUE_HYBRID_MODE_SWITCH | x+=x- (DR=I) | **YES** | no |
| sanger_atmospheric_pullout | gamma = 0 | +1 | SANGER_ATM | SANGER_ATM | DIAGNOSTIC | — | no | no |
| sanger_vac_apogee | gamma = 0 | −1 | SANGER_VAC | SANGER_VAC | DIAGNOSTIC | — | no | no |
| sanger_srti | gamma = 0 | −1 | SANGER_ATM | — | RESEARCH_TERMINAL | — | no | **YES** |

机器可读 registry：`src/hyptraj/predictability/event_metadata.py` →
`EVENT_TAXONOMY` / `all_taxonomy_rows()`；测试与 frozen event factories
交叉校验 direction / terminal / hybrid_switch。

### 5.9 F2.1 DENSE_RECOVERED 语义（G0 冻结）

`DENSE_RECOVERED`（`sanger_research_trajectory.py`，
`RESOLUTION_DENSE_RECOVERED`）只是 **event-resolution metadata**：
该 recovered event 仍代表 frozen physical `ATM -> VAC` switch
（`x_plus = x_minus`，同一 `f_minus` / `f_plus` / `normal` =
`atmosphere_interface_normal()`）。**不是新 mode，不是新 reset。**
`sanger_srti` 的 phase-G taxonomy 行不受影响。

---

## 6. Reset-map convention（G0 §7 冻结）

对当前所有 Phase-G normal true mode switches：

```
Qian Capture
Sanger atmosphere exit
Sanger atmosphere entry
```

状态本身连续：

```
R(x) = x          ->   DR = I
```

必须明确区分：

```
state continuity          （x+ = x-，恒成立）
vector-field continuity   （f+ != f- 一般成立）
```

**state continuous 并不意味着不需要 saltation。**

---

## 7. Saltation convention（G0 冻结）

对 autonomous event `g(x) = 0`、一般 reset `x+ = R(x-)`，统一冻结：

```
Xi = DR + (f^+ - DR f^-) n^T / (n^T f^-)
```

其中：

```
f^- = vector field immediately before event（pre-event side）
f^+ = vector field immediately after event
n   = grad g(x^-)（event-surface normal，evaluated on pre-event side）
```

对 identity reset（`DR = I`），本项目全部 normal true mode switches：

```
Xi = I + (f^+ - f^-) n^T / (n^T f^-)
```

**禁止符号约定在不同模块间改变。** 实现原语：
`protocol.generic_saltation` / `protocol.saltation_identity_reset`
（convention 级纯算术，G0 tests 校验 `DR=I` 时两者逐元素一致）。

---

## 8. Event-time sensitivity convention（G0 冻结）

对 `g(x(t_e)) = 0`，一阶 event-time perturbation：

```
delta t_e = - (n^T delta x^-) / (n^T f^-)
```

`delta x^-` 指 **nominal event time 上的 pre-event first-order
perturbation**。符号约定：线性化
`g(x^- + f^- delta t_e + delta x^-) = 0` 到一阶即得；`delta t_e > 0`
表示事件被推迟。

Phase G validation 必须同时研究：

```
state perturbation          （STM columns）
event-time perturbation     （delta t_e 一阶公式校验）
```

不能只看 STM singular value。

---

## 9. Grazing policy（G0 冻结）

Phase F 已证明 Sanger skip-count boundary 对应 atmosphere-interface
grazing `G_h = 0`，且：

```
n^T f^- = dG_h/dt = dh/dt = v sin(gamma)  ->  0
```

Phase F refined boundary 已存在 5 条（B0–B4，5735 refined boxes）。
标准 transverse saltation / event-time formula 的 denominator
`n^T f^-` 在 grazing limit 附近趋近 0。

### normal transverse regime

标准 saltation / event-time linearization 只用于**sufficiently
transverse event**（`TRANSVERSE`）。

### grazing-adjacent regime（`GRAZING_ADJACENT`）

若 `|n^T f^-|` 过小：

```
standard transverse linearization is ill-conditioned
first-order validity domain shrinks
potential linearization breakdown
```

**不得直接声称** `physical sensitivity = infinity`、`FTLE = infinity`、
`system is chaotic`。正确第一层解释为 loss of transversality /
shrinking validity domain of first-order event linearization。

### grazing / nontransverse（`GRAZING_NONTRANSVERSE`）

`n^T f^- -> 0`（limiting geometry `h = h_atm ∧ gamma = 0`）时标准
transverse formulas 失效。**G6 专门研究这一 regime。**

G0 冻结：classification logic + diagnostic quantity
（`protocol.interface_crossing_rate = v sin(gamma)`）；**具体数值阈值
留给 G6 numerical convergence study，不拍脑袋选**。

---

## 10. State scaling / nondimensionalization（G0 §11）

### 10.1 问题

raw state 单位与数量级不同：

```
r      ~ 6.4e6 m
theta  ~ 0.5 rad
v      ~ 3e3 m/s
gamma  ~ 0.1 rad
```

因此 raw dimensional STM 直接做 2-norm / singular value / condition
number / FTLE 会依赖单位与缩放。

### 10.2 约定（冻结）

```
S = diag(s_r, s_theta, s_v, s_gamma)
tilde_Phi = S^-1 Phi S        （scaled STM）
```

Phase G 后续 predictability 量一律在 scaled STM 上定义：

```
lambda_max(T) = (1/T) ln(sigma_max(tilde_Phi(T)))
```

可同时报告：

```
sigma_max, sigma_min, condition number,
dominant right singular vector, dominant left singular vector
```

必须在 protocol / report 中解释各自语义。**禁止 raw dimensional STM
singular value -> scientific claim。**

### 10.3 三套物理可解释候选（G0 冻结）

候选全部依据 frozen baselines 推导，不套通用 textbook 数字。实现见
`src/hyptraj/predictability/scaling.py`。

**候选 A — characteristic trajectory scales**

| scale | 值 | 单位 | 物理含义 |
|---|---|---|---|
| s_r | 1.0e5 | m | 飞行域垂直尺度 h_atm |
| s_theta | 1.0 | rad | 射程角单位 |
| s_v | 7.0e3 | m/s | 初始速度 v0 |
| s_gamma | 0.1 | rad | 名义弹道倾角尺度（匹配 gamma0 = -5° 量级） |

解释：每个 state 分量用 frozen trajectory 的特征运动量作单位；t0 状态
O(1)。优点：直接来自 frozen baselines、与具体终端无关、单位透明。
局限：特征运动尺度不是扰动精度声明；gamma 归一化 0.1 rad 对
capture/SRTI 小角度邻域偏粗。

**候选 B — initial-condition perturbation tolerance scales**

| scale | 值 | 单位 | 物理含义 |
|---|---|---|---|
| s_r | 1.0e2 | m | 100 m 高度/半径交付精度 |
| s_theta | 1.0e-5 | rad | ~64 m 地面射程 |
| s_v | 1.0 | m/s | 1 m/s |
| s_gamma | 1.0e-4 | rad | ~0.0057° |

解释：scaled STM 条目读作 "output displacement per tolerance-sized
input cell"，与 G2/G4 finite-perturbation validation 量级一致。优点：
直接可解释；与验证扰动量级对齐。局限：tolerance 是研究约定非物理
推导；放大 theta/gamma 权重。

**候选 C — research-domain / terminal-geometry scales**

| scale | 值 | 单位 | 物理含义 |
|---|---|---|---|
| s_r | 1.0e5 | m | 大气边界 / research 域 |
| s_theta | R_RTI/R_E ≈ 0.548 | rad | Qian baseline 终端射程角 |
| s_v | v0 − v_RTI ≈ 3.807e3 | m/s | research 区间速度保持范围 |
| s_gamma | 0.02246 | rad | Sanger X1 transverse exit 弹道倾角 |

解释：用 frozen research 端点的区间量归一化，与 event-conditioned
predictability 的可观测终端对齐。优点：锚定 research 端点、直接相关于
terminal/event-conditioned 研究。局限：端点相对（Qian/Sanger 终端不同）；
记账较重。

### 10.4 Canonical-scaling 状态（G0 冻结）

```
SCALING_CONVENTION_DEFINED
CANONICAL_SCALE_NUMERIC_VALUES_PENDING_VALIDATION
```

- **约定冻结**：`tilde_Phi = S^-1 Phi S`、所有 FTLE/singular-value 工作
  均在 scaled matrix 上进行。
- **preferred candidate = A**（characteristic trajectory scales）作为
  G1–G5 默认报告候选。
- **numeric canonical 选择不强行冻结**：G0 无 STM 证据公平比较 A/B/C，
  由 G2/G5 scale-sensitivity audit 依据 FTLE/norm 稳定性 + 语义
  可解释性决定最终数值。G0 **不伪造 FTLE 数据**。

### 10.5 scale-sensitivity protocol sanity checks（G0 允许的小规模审计）

G0 用纯算术（无需 STM 积分）固化以下 sanity：

1. identity map：`Phi = I -> tilde_Phi = I`（任意正 S）→ `lambda_max = 0`；
2. 相似性：`spec(S^-1 Phi S) = spec(Phi)`（说明 spectral radius 与
   scale 无关）；
3. singular values **不**存在 scale 不变性：
   `sigma(Phi) != sigma(S^-1 Phi S)`（一般），证明 raw dimensional
   singular-value claim 无意义。

实现：`scaling.identity_scaled_stm` / `scaling.spectrum_invariance` /
`scaling.singular_value_non_invariance`。

---

## 11. Fixed-time vs event-conditioned predictability（G0 冻结）

### fixed-time predictability

比较相同 elapsed time `x(T)`，使用 `tilde_Phi(T)` 计算 `sigma_max` /
condition number / dominant singular vectors / FTLE。这是未来
Qian–Sanger cross-model predictability comparison 的**优先协议**。

### event-conditioned / terminal predictability

例如 `Qian @ RTI`、`Sanger @ SRTI`，关注 terminal state sensitivity
与 terminal event-time sensitivity。但：

```
RTI != SRTI
```

两者 terminal semantics 不同（QEG feasibility loss vs skip-capability
loss）。因此：

- native RTI/SRTI terminal amplification 只能作为各自 trajectory 的
  descriptive result；
- **禁止**将 `Qian RTI FTLE` vs `Sanger SRTI FTLE` 宣称为公平性能比较。

---

## 12. FTLE definition（G0 冻结定义，不计算 production）

```
tilde_Phi(T) = S^-1 Phi(T) S          （scaled STM）
lambda_max(T) = (1/T) ln(sigma_max(tilde_Phi(T)))
```

允许未来报告 `sigma_max` / `sigma_min` / condition number / dominant
singular vectors（解释各自语义）。**禁止 raw dimensional STM singular
value -> scientific claim。**

---

## 13. Continuous Jacobian semantics（G0 只冻结定义）

连续 mode 内 `dot x = f_m(x)`：

```
A_m(x) = d f_m / d x
dot Phi = A_m(t) Phi
```

G1 后至少覆盖：Qian ENTRY_CAPTURE、Qian QEG_GLIDE、Sanger ATM、
Sanger VAC。

### Qian QEG 特殊性（提前记录）

```
u_L = clip(u_L*, 0, 1)
```

- `0 < u_L* < 1` 内：可用 interior derivative（QEG vector field 在该
  区域 C1）；
- `u_L* = 0` / `u_L* = 1`：存在 active-set / saturation boundary；
- RTI 对应 `u_L* -> 1`，**RTI 邻域不能当作 globally smooth system**。

G0 不实现该 Jacobian，只记录未来 G1 的 mathematical contract。

---

## 14. Representative trajectories（G0 冻结，不重新优化选择）

### Qian baseline

```
gamma0 = -5 deg, K = 3, regime = QIAN_RTI
```

### Sanger baseline

```
gamma0 = -5 deg, K = 3, regime = SRTI_N2
```

### Sanger deep fixed-topology representatives（复用 F4 reference-certified 点）

| key | gamma0 [deg] | K | expected regime | 来源 |
|---|---|---|---|---|
| n0_deep | -1.25 | 1.125 | SRTI_N0 | F4 regime-SRTI_N0 |
| n1_deep | -4.5 | 2.375 | SRTI_N1 | F4 regime-SRTI_N1 |
| n2_deep | -8.75 | 2.5 | SRTI_N2 | F4 regime-SRTI_N2 |
| n3_deep | -8.25 | 3.5 | SRTI_N3 | F4 regime-SRTI_N3 |
| n4_deep | -7.0 | 4.875 | SRTI_N4 | F4 regime-SRTI_N4 |
| n5_deep | -8.75 | 4.875 | SRTI_N5 | F4 regime-SRTI_N5 |

### Grazing representatives（保留给 G6）

Phase F regression snapshot 中 10 个 dual-reference extremal anchors
（B0–B4 每 branch 的 N-side / N+1-side），**NOT for normal G1-G5
acceptance**；仅用于 G6 grazing / transversality-loss 分析。

---

## 15. Finite nonlinear perturbation validation protocol（G0 冻结规则）

对 state direction `e_i`，使用 centered perturbation：

```
x_0^± = x_0 ± epsilon_i e_i

D_i^NL = [ x(t; x_0 + epsilon_i e_i) - x(t; x_0 - epsilon_i e_i) ] / (2 epsilon_i)
```

与 STM column `Phi(:, i)` 比较。**必须要求：**

```
multiple perturbation magnitudes
convergence / plateau audit
production vs strict reference
dimension-aware error
```

不能只用一个 epsilon。

---

## 16. Hybrid nonlinear validation topology gate（G0 冻结）

跨 event validation 时每个 finite perturbation 必须分类：

```
TOPOLOGY_PRESERVED    -> 允许进入普通 first-order hybrid STM acceptance
TOPOLOGY_CHANGED      -> ordinary comparison INVALID
EVENT_ORDER_CHANGED   -> ordinary comparison INVALID
GRAZING_CROSSED       -> ordinary comparison INVALID
NUMERICAL_FAILURE     -> ordinary comparison INVALID
```

如果 skip_count 改变 / 新 mode switch 出现 / event ordering 改变 /
grazing boundary crossed：**不能把误差记成 STM ERROR**。

---

## 17. Error taxonomy（G0 冻结）

任何 validation report 必须区分：

```
PHYSICS_SEMANTICS_ERROR
NUMERICAL_ERROR
TOPOLOGY_CHANGE
EVENT_ORDER_CHANGE
GRAZING_CROSSING
LINEARIZATION_BREAKDOWN
```

**禁止把所有 mismatch 都归到 "STM error"。**

---

## 18. Numerical reference policy（G0 冻结）

### trajectory production baseline（继续使用 Phase C frozen）

```
DOP853, rtol=1e-9, atol=[1e-4, 1e-11, 1e-7, 1e-11],
max_step=20 s, dense_output=True
```

只证明 trajectory integration baseline，**不自动证明** Jacobian /
variational equation / STM / saltation / singular values / FTLE 的数值
可靠性。

### Phase-G variational numerics（以后必须独立验证，G0 只冻结策略）

```
solver tolerance convergence
augmented-state tolerance scaling
max_step convergence
Jacobian verification
finite perturbation convergence
singular-value stability
event-time sensitivity validation
saltation validation
```

严格 reference 沿用 Phase C/F 风格（仓库已冻结）：

```
DOP853, rtol=1e-12, atol=[1e-7, 1e-14, 1e-10, 1e-14], max_step=0.1 s
companion self-stability: max_step=0.05 s
```

（即 `comparison_validation.REFERENCE_SOLVER_CONFIG` /
`REFERENCE_05_SOLVER_CONFIG`，G2/G5 独立收敛审计使用。）

---

## 19. Claim boundaries（G0 禁止的科学表述）

```
raw dimensional STM norm = objective predictability
large Xi near grazing = physical infinity
grazing = chaos
larger FTLE always means worse trajectory
Sanger RTI/SRTI native endpoint directly comparable to Qian
diagnostic gamma crossing = hybrid switch
all nonlinear mismatch = STM failure
```

明确：

```
Phase G studies finite-time local predictability.
```

不是 asymptotic chaos analysis / global stability proof / certified
flight-envelope robustness / probabilistic uncertainty / optimization。

---

## 20. G0 source audit 结论（摘要）

### Qian event/mode/reset audit

- 冻结 state `[r,theta,v,gamma]`；capture factory 标注 `hybrid_switch=True`；
  RTI 是 terminal（L_req − L 上穿）非 mode switch；reset 语义缺省即
  `x+ = x-`（三阶段 integrator 用复制）。
- `QianResearchEvent` 只存 kind/stage/time/state —— **没有 f_minus /
  f_plus / normal 字段**（Sanger 侧有）。跨 capture saltation 所需的
  f_minus（ENTRY_CAPTURE, u_L=1）/ f_plus（QEG_GLIDE, u_L=clip）与
  n_c 需由 G1 layer 在 analysis time 用 frozen 原语导出（observability
  扩展，非 physics 修改）。

### Sanger event/mode/reset audit

- `HybridEventRecord` 在真实 ATM↔VAC switch 上已存 x_e / f_minus /
  f_plus / normal / mode_before / mode_after；diagnostic 与 terminal
  事件存 None（语义一致：无 saltation）。reset = plain copy。
- pullout / apogee / SRTI 的 gamma_0 交差方向 + terminal 属性与 frozen
  factories 一致（G0 测试交叉校验）。

### F2.1 recovered-event audit

- `DENSE_RECOVERED` 是 event-resolution metadata；recovered event 的
  f_minus / f_plus / normal 与 normal exit 完全相同；x_plus=x_minus。

### existing metadata reuse

event surface（Sanger `atmosphere_interface_value`；Qian capture=gamma /
RTI=L_req−L）、event normal（Sanger `atmosphere_interface_normal`；
Qian capture n_c、RTI normal 延迟）、event state / time、mode_before /
mode_after、f_minus/f_plus、reset 语义、dense output
（`DenseSolutionSegment`）、event resolution（SOLVER_EVENT /
DENSE_RECOVERED）、exact topology signature（`sensitivity_pilot` /
`sensitivity_grid`）、grazing diagnostics（candidate_overshoot_m /
exit_dhdt_mps / Phi_N / T_N）。

### missing metadata discovered

1. Qian capture/RTI 事件记录缺 f_minus / f_plus / normal（跨 capture
   saltation 输入，G1 analysis-time 衍生）；
2. RTI/`L_req−L` 的 event normal 依赖 `d(L_req−L)/dx`（真 G1 Jacobian，
   本协议标记 deferred）；
3. SRTI / pullout / apogee 的 `gamma_dot` transversality helper 未集中
   暴露单点接口（可从 frozen RHS 计算，G3 提供）。

---

## 21. Machine-readable protocol（G0 §21 冻结面）

`src/hyptraj/predictability/protocol.py` → `machine_readable_protocol()`
JSON payload 覆盖：

```
state_order, state_units, stm_convention, perturbation_scope,
reset_convention, saltation_convention, event_time_convention,
predictability_questions (fixed_time / event_conditioned),
ftle_definition, scaling_status (convention + numeric pending),
grazing_policy, event_taxonomy (7 rows), validation_categories,
topology_gate, representative_cases, grazing_anchors,
reference_solver_policy, forbidden_claims, scope_statement,
g0_status flags
```

schema：`phase-g-predictability-protocol-v1`。

---

## 22. G0 acceptance（本 Phase G0 自检，与任务 §24 对齐）

- [x] Phase G branch based on phase-f-v1.0（feature/phase-g-predictability）
- [x] old frozen tags unchanged
- [x] baseline old regression PASS（426 passed）
- [x] state ordering frozen；initial-state-only perturbation frozen
- [x] Qian Capture / Qian RTI / Sanger exit/entry / pullout/apogee /
  SRTI classifications frozen
- [x] reset convention frozen；saltation 公式/符号冻结；event-time
  公式/符号冻结
- [x] fixed-time 与 event-conditioned predictability 定义冻结；native
  endpoint comparison limitation 文档化
- [x] dimensional STM scaling problem 文档化；3 候选文档化；canonical
  scaling status 文档化（PENDING_VALIDATION）；无 raw-dimensional FTLE claim
- [x] FTLE 定义冻结
- [x] grazing transversality policy 冻结；无 "infinite physical
  sensitivity" claim；G6 scope 分离
- [x] representative trajectories 冻结；F3 grazing anchors 保留给 G6
- [x] nonlinear perturbation validation protocol 冻结；topology gate 冻结；
  error taxonomy 冻结
- [x] trajectory production/reference policy 冻结；augmented STM
  numerical validation correctly deferred
- [x] protocol/docs written（README + predictability_protocol）
- [x] semantic tests added（tests/test_predictability/test_phase_g0_protocol.py）
- [x] full pytest PASS
- [x] no G1 Jacobian implementation / no STM integration / no FTLE
  production result / no Monte Carlo / no optimization

**Phase G0 = COMPLETE。等待人工验收（G0 不创建 final tag，不进入 G1）。**
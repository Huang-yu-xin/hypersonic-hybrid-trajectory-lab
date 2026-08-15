# Sanger Mathematical Specification v1.0 — Phase D

状态：**FROZEN**（D0 freeze）

日期：2026-08-15
分支：`feature/phase-d-sanger-hybrid`
上游冻结基线：`qian-baseline-v1.0`（Phase B.5）、`phase-b-v1.0`、`phase-c-v1.0`

本文件是 Phase D（Sanger Hybrid Trajectory）后续代码实现的 **source of truth**。
D1 及以后的实现、实验与验收一律以本规范为准，不得为匹配任何预想数值修改
已冻结的 physics（Phase A/B/C 冻结内容）。

> D0 不产生 tag。`phase-d-v1.0` 与 `sanger-baseline-v1.0` 只有 Phase D 全部
> 完成并通过验收后才能创建。

---

## 1. D0 目标

仅建立并冻结 **Sanger Mathematical Specification v1.0**，即文档化的数学定义
（模式、事件、控制、终点语义、不变量、数值配置）。本轮：

- 不实现 D1（ATM/VAC 求解器）；
- 不运行 Sanger baseline；
- 不进入 Phase E/F；
- 不实现 STM / saltation / FTLE。

任何上述内容的实现都属于后续阶段，不在 D0 范围内。

## 2. 冻结研究对象

正式定义 Phase D Sanger baseline 为：

> **unpowered longitudinal lift-supported atmospheric skip trajectory**
> （无动力、纵向升力支撑的大气跳跃滑翔轨迹）

其核心 hybrid structure：

```
SANGER_ATM
    ↕
SANGER_VAC
```

Phase D 的目标是建立**事件驱动**的桑格尔跳跃滑翔 baseline。
Phase D 明确**不做**：

- Qian vs Sanger 对比；
- gamma0-K sweep；
- Monte Carlo；
- optimization；
- STM / FTLE / saltation matrix。

## 3. 状态定义

继续使用现有四状态（禁止增加新的物理状态）：

```
x = [h, v, gamma, theta]^T
```

其中：

```
r = R_E + h
```

- `h`     — 高度 [m]
- `v`     — 速度大小 [m/s]
- `gamma` — 弹道倾角 [rad]
- `theta` — 地面射程角 [rad]，地面射程 R = R_E * theta
- `r`     — 地心距 [m]

**冻结实现记号**：现有冻结模块（`src/hyptraj/models/dynamics.py` 等）使用
实现状态向量 `state = [r, theta, v, gamma]`，其中 `h = r - R_E`。数学记号
`x = [h, v, gamma, theta]^T` 与实现记号 `[r, theta, v, gamma]` 是同一物理
状态的两种写法，一一对应：

| 数学记号 | 实现记号 | 说明 |
|---|---|---|
| h | `state[0] - R_E` | 高度 |
| v | `state[2]` | 速度 |
| gamma | `state[3]` | 弹道倾角 |
| theta | `state[1]` | 射程角 |

**D1 实现必须直接调用已冻结模块，禁止复制第二套 dynamics。**

必须复用以下已冻结内容（source of truth 均为现有模块，禁止在本阶段修改）：

- environment — `src/hyptraj/models/parameters.py`（`EnvironmentParams`）
- gravity — `src/hyptraj/models/gravity.py`
- atmosphere — `src/hyptraj/models/atmosphere.py`
- aero — `src/hyptraj/models/aerodynamics.py`
- vehicle — `src/hyptraj/models/parameters.py`（`VehicleParams`）
- state convention — `src/hyptraj/models/dynamics.py`
- production numerics — `src/hyptraj/simulation/numerics.py`（`PRODUCTION_SOLVER_CONFIG`）

## 4. Baseline 初值与参数

为了 Phase E 后续公平比较，Sanger baseline 使用与 Qian baseline 相同的
初值：

```
h0     = 100 km   = 100000 m
v0     = 7000 m/s
gamma0 = -5 deg   = -5 * pi / 180 rad
theta0 = 0
K      = L/D = 3
```

继续使用冻结的 vehicle 参数：

```
m  = 1000 kg
S  = 1 m^2
CD = 0.2
```

> **Comparative research design choice**：以上参数是本项目的
> **comparative research design choice**（对比研究设计选择），
> 不是声称历史 Sänger 方案必须采用这些参数。

**禁止**为了得到更多 skip 而修改：

- gamma0
- v0
- K
- vehicle
- atmosphere

参数扫描属于以后 Phase F。

## 5. SANGER_ATM 定义

大气边界（冻结）：

```
h_atm = 100000 m
```

在 `h <= h_atm` 时使用现有 frozen atmospheric dynamics 与 aerodynamic model。

Sanger ATM baseline 控制冻结为：

```
u_L = 1
```

即：

```
sigma = 0
cos(sigma) = 1
```

全部可用升力均投影到纵向平面（无倾斜机动削弱纵向升力）。

空气动力继续使用冻结模型（`src/hyptraj/models/aerodynamics.py`）：

```
D = 0.5 * rho * v^2 * S * CD
L = K * D
```

ATM equations 使用现有项目冻结 equations（`src/hyptraj/models/dynamics.py`，
即字面 Eq.(4)），在数学记号下为：

```
dh/dt     = v sin(gamma)
dtheta/dt = v cos(gamma) / r
dv/dt     = -D/m - g(h) sin(gamma)
dgamma/dt = u_L * L / (m v) + (v/r - g(h)/v) cos(gamma)
```

其中冻结模型：

```
g(h) = g0 * (R_E / (R_E + h))^2
rho(h) = rho0 * exp(-h / H)
K = C_L / C_D   （来自 control 回调，Sanger 冻结为 ConstantKControl(3.0)）
```

**必须明确与 Qian 的差异**：

| | 纵向升力控制 | 行为 |
|---|---|---|
| Qian QEG | `u_L = clip(L_req / L, 0, 1)`，`L_req = m (g - v^2/r) cos(gamma)` | 主动削弱纵向升力以维持 QEG |
| **Sanger ATM** | **`u_L = 1`** | 不削弱纵向升力，允许轨迹自然 pull-up / skip |

即 Sanger ATM **不主动削弱纵向升力以维持 QEG**，而允许轨迹自然
pull-up / skip。文档给出数学式仅为契约，后续实现必须调用已有 frozen 模块，
不得复制第二套 dynamics。

## 6. SANGER_VAC 定义

当 `h > 100000 m` 时进入 `SANGER_VAC`，强制：

```
L = 0
D = 0
```

但：

```
gravity != 0
curvature terms != 0
```

因此 VAC **不是匀速直线运动**。

使用与 ATM 相同的状态定义与 spherical-Earth geometry。

VAC equations 明确如下（即 ATM equations 在 L = D = 0 时的形式）：

```
dh/dt     = v sin(gamma)
dv/dt     = -g sin(gamma)
dgamma/dt = (v/r - g/v) cos(gamma)
dtheta/dt = v cos(gamma) / r
```

其中 `g = g(h) = g0 (R_E / r)^2`，`r = R_E + h`。

> **Atmosphere cutoff**：100 km 是本项目的 atmosphere cutoff /
> switching boundary，**不是**声称它是所有 Sänger 理论的唯一物理大气边界。

## 7. Atmosphere Exit Event

统一 switching surface：

```
G_atm(x) = h - h_atm
```

**ATM -> VAC：Atmosphere Exit**

条件：

```
h = h_atm
upward crossing
```

即：

```
direction = +1
terminal  = True
```

要求：

```
dh/dt > 0
```

reset map：

```
x+ = x-
```

状态不发生跳变。

## 8. Atmosphere Entry Event

**VAC -> ATM：Atmosphere Entry**

条件：

```
h = h_atm
downward crossing
```

即：

```
direction = -1
terminal  = True
```

要求：

```
dh/dt < 0
```

reset：

```
x+ = x-
```

同样无状态 reset。

## 9. 初始状态的边界语义

由于：

```
h0 = 100 km
gamma0 < 0
```

初始状态已经位于 atmosphere interface 且正在向下进入。

**不要在 t = 0 重新触发一次 atmosphere-entry event。**

正式定义：

```
initial state = synthetic E0
```

即：

```
E0 = initial atmospheric entry interface
```

随后直接从 `SANGER_ATM` 开始积分。

> 该约定避免 t=0 event duplication / chatter：进入第一个 ATM 段时**不**挂载
> entry event 的 t=0 触发，只允许后续真实向下穿越 h_atm 触发 entry event。

## 10. Pull-out Event

ATM 内定义 pull-out：

```
g_pullout(x) = gamma
```

检测：

```
gamma: negative -> positive
```

即：

```
direction = +1
```

它对应 atmospheric local minimum：

```
dh/dt = 0
gamma  = 0
```

**pull-out 不是 mode transition**，只是 diagnostic event（不改变 SANGER_ATM
模式，不终止积分段）。

## 11. Vacuum Apogee Event

VAC 内定义 apogee：

```
g_apogee(x) = gamma
```

检测：

```
gamma: positive -> negative
```

即：

```
direction = -1
```

它对应 VAC local maximum altitude（真空弧段的 local apogee）。

同样只是 diagnostic event，**不改变 SANGER_VAC mode**。

## 12. Completed Skip Cycle 正式定义

第 i 个完整 skip cycle 定义为：

```
E_i -> P_i -> X_i -> A_i -> E_{i+1}
```

其中：

```
E_i   = atmosphere entry
P_i   = atmospheric pull-out
X_i   = atmosphere exit
A_i   = vacuum apogee
E_{i+1} = next atmosphere entry
```

completed skip 必须满足：

1. 存在 atmosphere exit；
2. 随后存在 VAC segment；
3. 随后成功 atmosphere re-entry。

初始 synthetic E0 可以作为第一轮 skip 的入口。

定义：

```
skip_count =
number of completed E_i -> E_{i+1} cycles
```

- **不**要把仅仅一次 pull-out 算作 skip；
- **不**要把只有 exit 而没有重新 entry 的不完整弧段算作 completed skip。

## 13. Sanger Research Terminal Interface（SRTI）

Phase D 使用新的研究终点：

```
SRTI
```

全名：**Sanger Skip-Capability-Loss Interface**

定义：飞行器已经在某次 atmospheric pass 中完成 pull-out
（`gamma: - -> +`），随后上升，但是在再次达到 `h = 100 km` 之前，出现：

```
gamma: + -> -
```

即 atmospheric local apogee（大气弧段内的局部最高点）。

因此 guard：

```
g_SRTI(x) = gamma
direction = -1
```

并要求：

```
mode = SANGER_ATM
h < h_atm
```

且该 atmospheric pass **已经发生过 pull-out**。

物理含义：该 atmospheric pass 已不再具备完成下一次 atmosphere exit 的能力
（上升段在到达大气边界前已被重力拉回）。

正式定义：

```
research endpoint = SRTI
```

而不是 ground。

## 14. Ground Compatibility Endpoint

SRTI 后允许继续使用 atmospheric dynamics 到 `h = 0`（地面事件，
`src/hyptraj/simulation/events.py` 的 ground event：`g = r - R_E`，
`direction = -1`，`terminal = True`），用于 compatibility / visualization /
legacy full-trajectory output。

但必须明确：

```
research endpoint     = SRTI
compatibility endpoint = ground
```

后续高速研究指标原则上在 SRTI 截止。**不要**让低速 ground tail 污染
高速 predictability 指标。

## 15. Hybrid Automaton

状态机（ATM/VAC 必须严格交替）：

```
initial synthetic E0
      |
      v
SANGER_ATM
      |
      | atmosphere exit
      | h = 100 km, upward
      v
SANGER_VAC
      |
      | atmosphere entry
      | h = 100 km, downward
      v
SANGER_ATM
      |
      ...
      |
      | atmospheric gamma: + -> -
      | before next exit
      v
     SRTI
      |
compatibility continuation
      |
    ground
```

模式约束：

- `SANGER_ATM` 的合法后继只有 `SANGER_VAC`（经 Atmosphere Exit）；
- `SANGER_VAC` 的合法后继只有 `SANGER_ATM`（经 Atmosphere Entry）；
- ATM/VAC 必须严格交替，不允许连续同类模式；
- SRTI 是研究终点（发生在 SANGER_ATM 内）；
- ground 是 compatibility 终点（SRTI 后 continuation 才可能到达）。

## 16. Future hybrid sensitivity metadata

Phase D **不实现** saltation matrix，但 D0 必须冻结 switching geometry：

```
G(x) = h - h_atm
```

gradient（数学记号 `x = [h, v, gamma, theta]^T`）：

```
nabla G = [1, 0, 0, 0]^T
```

（实现记号 `state = [r, theta, v, gamma]` 下同样为 `[1, 0, 0, 0]^T`，
因为 `h = r - R_E`。）

reset：

```
R(x) = x
DR = I
```

并注明：一般

```
f_ATM != f_VAC
```

所以未来跨 ATM/VAC event 的 STM 需要 hybrid sensitivity / saltation treatment。

Phase D 当前只要求以后 event metadata 有能力保存：

```
event state  x_e
f_minus
f_plus
event normal nabla G
mode_before
mode_after
```

**不要现在实现 saltation。**

## 17. VAC physics invariant specification

D0 冻结两个 VAC verification quantities：

令：

```
mu = g0 * R_E^2
```

specific mechanical energy：

```
E = v^2 / 2 - mu / r
```

specific angular momentum：

```
H = r * v * cos(gamma)
```

在理想 VAC segment 中（L = D = 0，纯球对称引力场）：

```
E ≈ constant
H ≈ constant
```

Phase D 后续 D6 将用它们做 physics regression。
现在只写入 specification，**不要新增 sweep**。

## 18. Numerical configuration

Phase D 正式使用 Phase C 已冻结的 `PRODUCTION_SOLVER_CONFIG`
（`src/hyptraj/simulation/numerics.py`）：

```
method        = DOP853
rtol          = 1e-9
atol          = [1e-4, 1e-11, 1e-7, 1e-11]
max_step      = 20.0
dense_output  = True
```

禁止：

- 修改 `PRODUCTION_SOLVER_CONFIG`；
- 修改 `DEFAULT_SOLVER_CONFIG`（保持 Phase B 回归连续性）；
- 重新调 solver。

Sanger 新 event（exit / entry / pull-out / apogee / SRTI）的 numerical
convergence 由后面 D6 单独验证，不在 D0 冻结数值。

## 19. 关于预期数值

本规范**不冻结**以下任何未经仓库正式实现验证的数值：

- skip_count
- exit times
- entry times
- apogee
- SRTI time
- SRTI altitude
- SRTI velocity
- final range

此前外部 sanity probe 得到的任何类似：

> “约 2 次 skip”
> “约 86 km SRTI”

都只能视为 **implementation sanity expectation**，**不是** Phase D frozen
baseline。D1-D6 实际运行以后才能正式冻结数值。

## 20. D0 Acceptance

以下 checklist 全部明确：

| # | Item | Status |
|---|---|---|
| 1 | state definition frozen（四状态，复用冻结 state convention） | **PASS** |
| 2 | baseline IC frozen（h0=100 km, v0=7000 m/s, gamma0=-5 deg, theta0=0） | **PASS** |
| 3 | K / vehicle / environment frozen（K=3, m=1000 kg, S=1 m^2, CD=0.2） | **PASS** |
| 4 | ATM control u_L=1 frozen（sigma=0, cos(sigma)=1） | **PASS** |
| 5 | VAC L=D=0 frozen（gravity/curvature 保留） | **PASS** |
| 6 | atmosphere boundary frozen（h_atm=100000 m） | **PASS** |
| 7 | exit event frozen（G_atm=h-h_atm, upward, terminal, x+=x-） | **PASS** |
| 8 | entry event frozen（downward, terminal, x+=x-） | **PASS** |
| 9 | synthetic E0 semantics frozen（无 t=0 event duplication） | **PASS** |
| 10 | pull-out definition frozen（gamma - -> +, diagnostic only） | **PASS** |
| 11 | VAC apogee definition frozen（gamma + -> -, diagnostic only） | **PASS** |
| 12 | completed skip definition frozen（E_i->P_i->X_i->A_i->E_{i+1}） | **PASS** |
| 13 | SRTI definition frozen（research endpoint, gamma + -> - in ATM after pull-out） | **PASS** |
| 14 | ground compatibility semantics frozen（compatibility endpoint only） | **PASS** |
| 15 | ATM/VAC reset map frozen（R(x)=x, DR=I） | **PASS** |
| 16 | future saltation metadata contract recorded（x_e, f_minus, f_plus, nabla G, mode_before/after） | **PASS** |
| 17 | VAC invariants recorded（E ≈ const, H ≈ const） | **PASS** |
| 18 | Phase C production numerics inherited（DOP853, rtol=1e-9, atol=[1e-4,1e-11,1e-7,1e-11], max_step=20, dense_output） | **PASS** |
| 19 | no Phase E/F/predictability implementation（本轮仅文档） | **PASS** |

**D0 Acceptance：COMPLETE**

---

*本规范自冻结日起为 Phase D 实现的唯一权威定义。任何对冻结 physics 的
修改必须经过阶段评审与 tag 流程。*

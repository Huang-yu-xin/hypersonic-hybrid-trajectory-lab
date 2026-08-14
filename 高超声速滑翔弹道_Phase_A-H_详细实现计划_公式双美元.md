# 高超声速滑翔弹道动力学仿真 Phase A–H 详细实现计划

> **目标**：为后续有限时间可预测性分析（STM / FTLE）、Monte Carlo 不确定性传播、拦截风险建模以及桑格尔—钱学森混合弹道优化建立一个可信、稳定、可复现、可扩展的动力学仿真底座。  
> **当前阶段边界**：只解决确定性标称动力学、数值积分、事件切换、参数敏感性与扩展接口；暂不进入 AHP、Lyapunov 正式分析、拦截概率和优化。

---

# 0. 总体原则

## 0.1 第 2 章定位

第 2 章应作为整个项目的 **Nominal Dynamics / Baseline Simulation** 基础章，完成：

1. 统一纵向二维动力学模型；
2. 钱学森持续滑翔模式；
3. 桑格尔大气—真空切换模式；
4. 求解器与容差收敛验证；
5. $$(\gamma_0,K)$$ 参数扫描；
6. 后续 Jacobian、STM、Monte Carlo 和优化接口；
7. 冻结一个可信的 `baseline_v1`。

## 0.2 题目“7 补充说明”的落实

必须显式做到：

- **保留题目基准模型**，再在后续研究版中细化大气、地球与气动模型；
- 使用 **自适应步长积分**，并实际比较 `RK45 / DOP853 / Radau / BDF`，而不是因为题目推荐 BDF 就直接认定其最优；
- 用事件机制实现
  $$
h\le0
$$
  的触地终止；
- 做 solver、tolerance、`max_step` 数值收敛验证；
- 所有正式实验保存配置、版本和随机种子，保证可复现。

## 0.3 两层模型策略

### Model-A：Baseline Model

严格复现题目模型，用于：

- 对齐题目基准算例；
- 单元测试；
- solver / tolerance 验证；
- 回归测试。

### Model-B：Research Model

Phase H 之后再逐步加入：

- 更真实的大气模型；
- $$C_L(M,\alpha),C_D(M,\alpha)$$；
- 地球自转；
- 三自由度球面动力学；
- 更真实的气动加热模型；
- 参数不确定性。

**Phase A–H 先把 Model-A 做到稳定。**

---

# Phase A：模型、单位与基础模块

## A.1 目标

建立统一的单位体系、状态向量、物理参数和基础函数。  
这一阶段不追求完整弹道，只解决“模型输入是否正确”。

## A.2 统一单位

代码内部全部使用 SI 制：

| 物理量 | 内部单位 |
|---|---|
| 长度 | m |
| 时间 | s |
| 质量 | kg |
| 速度 | m/s |
| 加速度 | m/s² |
| 角度 | rad |
| 密度 | kg/m³ |
| 动压 | Pa |
| 力 | N |

仅在配置输入和绘图时使用 km、deg。

```python
gamma0 = np.deg2rad(gamma0_deg)
```

**禁止**在动力学函数中混用 degree 与 radian。

## A.3 状态向量

定义

$$
\mathbf{x}=[r,\theta,v,\gamma]^T,
$$

其中

$$
h=r-R_e,\qquad R=R_e\theta.
$$

## A.4 参数对象

建议使用 `dataclass`：

```python
@dataclass
class VehicleParams:
    mass: float
    area: float
    cd: float

@dataclass
class EnvironmentParams:
    Re: float
    g0: float
    rho0: float
    H: float
    h_atm: float

@dataclass
class SimulationParams:
    method: str
    rtol: float
    atol: float
    max_step: float | None
```

禁止把 `rho0`、`H`、`CD`、`m` 等常量散落在脚本中。

## A.5 基础函数

### 重力

$$
g(h)=g_0\left(\frac{R_e}{R_e+h}\right)^2.
$$

接口：

```python
gravity(h, env) -> float
```

### 大气密度

$$
\rho(h)=\rho_0e^{-h/H}.
$$

接口：

```python
density(h, env) -> float
```

### 气动力

$$
D=\frac12\rho v^2SC_D,
$$

$$
L=\frac12\rho v^2SC_L,
$$

$$
C_L=KC_D.
$$

接口：

```python
aerodynamic_forces(state, K, vehicle, env)
```

输出至少包括：

```text
rho, q, CL, CD, L, D
```

## A.6 控制律接口

不要把 $$K$$ 写死在动力学里。

统一：

```python
K = control_law(t, state)
```

第一版：

```python
class ConstantKControl:
    def __init__(self, K):
        self.K = K

    def __call__(self, t, state):
        return self.K
```

后续可直接换成：

$$
K(t)=K_i,\quad t\in[t_i,t_{i+1}),
$$

或状态反馈、优化控制。

## A.7 单元测试

至少验证：

- $$h=0\Rightarrow g=g_0$$；
- $$h=0\Rightarrow \rho=\rho_0$$；
- $$g(h)$$ 随高度下降；
- $$\rho(h)$$ 随高度下降；
- $$v=0\Rightarrow L=D=0$$；
- $$K=0\Rightarrow L=0$$。

## A.8 验收标准

- [ ] 内部角度全部为 rad；
- [ ] 长度全部为 m；
- [ ] 基础函数通过测试；
- [ ] 参数集中管理；
- [ ] 控制律抽象完成；
- [ ] 无散落硬编码常量。

## A.9 输出物

```text
src/
├── models/
│   ├── atmosphere.py
│   ├── gravity.py
│   ├── aerodynamics.py
│   └── parameters.py
├── controls/
│   └── constant_k.py
└── tests/
    ├── test_atmosphere.py
    ├── test_gravity.py
    └── test_aerodynamics.py
```

---

# Phase B：钱学森基准弹道

## B.1 目标

先在**无模式切换**条件下验证完整纵向动力学是否正确。

## B.2 大气内动力学

$$
\dot r=v\sin\gamma,
$$

$$
\dot\theta=\frac{v\cos\gamma}{r},
$$

$$
\dot v=-\frac{D}{m}-g(r)\sin\gamma,
$$

$$
\dot\gamma=
\frac{L}{mv}
+
\left(
\frac vr-\frac{g(r)}v
\right)\cos\gamma.
$$

接口：

```python
atmospheric_dynamics(t, state, model)
```

## B.3 第一组固定基准

$$
h_0=100\text{ km},
\quad
v_0=7000\text{ m/s},
\quad
\gamma_0=-5^\circ,
\quad
\theta_0=0,
\quad
K=3.
$$

并使用

$$
r_0=R_e+h_0.
$$

## B.4 触地事件

$$
g_{ground}=r-R_e.
$$

```python
ground_event.terminal = True
ground_event.direction = -1
```

禁止“积分完再把负高度裁掉”。

## B.5 第一轮求解

先用一套高精度配置跑通，例如：

```python
solve_ivp(
    ...,
    method="DOP853",
    rtol=1e-8,
    atol=1e-10,
    events=ground_event,
)
```

这只是初始选择，不代表最终 solver。

## B.6 输出

### 状态

- $$t$$
- $$h(t)$$
- $$R(t)$$
- $$v(t)$$
- $$\gamma(t)$$

### 派生量

- $$\rho(t)$$
- $$q(t)$$
- $$L(t)$$
- $$D(t)$$

### 指标

- $$t_f$$
- $$R_f$$
- $$v_f$$
- $$q_{max}$$
- 最大高度
- 最大/最小弹道倾角

## B.7 自动物理检查

```text
R(t) 整体单调增加
v(t) > 0
q(t) >= 0
rho(t) >= 0
末端 h ≈ 0
无 NaN / Inf
```

## B.8 基准验证

与题目给出的钱学森弹道基准数量级比较：

- 射程；
- 飞行时间；
- 末端速度。

目标是**数量级与轨迹形态一致**，不是追求每个数完全相同。

## B.9 验收标准

- [ ] 能稳定积分到触地；
- [ ] 无 NaN / Inf；
- [ ] 结果与题目基准量级一致；
- [ ] 状态与派生量能自动输出；
- [ ] CSV / NPZ 可保存；
- [ ] metadata 记录完整。

---

# Phase C：求解器与数值收敛验证

## C.1 目标

确认观察到的差异来自物理模型，而不是数值积分误差。

这一步是后续 FTLE、微小扰动传播研究的前置条件。

## C.2 Solver Comparison

同一钱学森基准工况比较：

```text
RK45
DOP853
Radau
BDF
```

记录：

$$
R_f,\quad t_f,\quad v_f,\quad q_{max},
$$

以及：

```text
runtime
nfev
njev
nlu
event time
```

## C.3 相对误差

选择高精度结果作为参考：

$$
\varepsilon_R=
\frac{|R_f-R_{ref}|}{|R_{ref}|}.
$$

同理定义：

$$
\varepsilon_t,\quad \varepsilon_v.
$$

建议正式 solver 与参考值差异至少稳定到 $$10^{-5}\sim10^{-6}$$ 量级。

## C.4 容差收敛

测试：

| rtol | atol |
|---|---|
| $$10^{-6}$$ | $$10^{-8}$$ |
| $$10^{-8}$$ | $$10^{-10}$$ |
| $$10^{-10}$$ | $$10^{-12}$$ |

比较：

- $$R_f$$
- $$t_f$$
- $$v_f$$
- $$q_{max}$$
- runtime

重点看从 $$10^{-8}$$ 到 $$10^{-10}$$ 是否基本稳定。

## C.5 `max_step` 敏感性

测试：

```text
inf / 10 s / 5 s / 1 s / 0.5 s
```

关注：

- 动压峰值；
- 事件定位；
- 末端状态；
- 曲线是否出现步长伪振荡。

## C.6 正式 solver 选择原则

综合：

1. 精度；
2. 稳定性；
3. 事件定位；
4. 计算效率。

论文中应写成：

> 经 solver comparison 与 tolerance convergence 后确定正式积分方法。

而不是：

> 因题目推荐 BDF，所以使用 BDF。

## C.7 验收标准

- [ ] 至少 4 个 solver 比较完成；
- [ ] 容差收敛表完成；
- [ ] `max_step` 敏感性完成；
- [ ] 正式 solver 有数据依据；
- [ ] 固定 rtol / atol / max_step；
- [ ] 保存 `numerical_validation.csv`。

---

# Phase D：桑格尔事件驱动混合动力学

## D.1 目标

实现

$$
\text{ATM}\leftrightarrow\text{VAC}
$$

的事件驱动桑格尔弹跳系统。

## D.2 两种动力学模式

### ATM

$$
D\neq0,\qquad L\neq0.
$$

使用完整纵向动力学。

### VAC

$$
D=0,\qquad L=0.
$$

于是：

$$
\dot r=v\sin\gamma,
$$

$$
\dot\theta=\frac{v\cos\gamma}{r},
$$

$$
\dot v=-g(r)\sin\gamma,
$$

$$
\dot\gamma=
\left(
\frac vr-\frac{g(r)}v
\right)\cos\gamma.
$$

## D.3 事件面

$$
g_{atm}=h-h_{atm},
$$

其中：

$$
h_{atm}=100\text{ km}.
$$

### 离开大气层

```python
terminal = True
direction = +1
```

### 再入大气层

```python
terminal = True
direction = -1
```

### 触地

```python
terminal = True
direction = -1
```

## D.4 状态机

```text
INITIAL
  ↓
ATM
  ├── ground → TERMINATED
  └── atmosphere_exit → VAC

VAC
  └── atmosphere_entry → ATM
```

ATM 模式只监听：

```text
ground
atmosphere_exit
```

VAC 模式只监听：

```text
atmosphere_entry
```

避免同一边界事件反复触发。

## D.5 分段积分逻辑

```text
state = x0
mode = ATM

while not terminated:

    if mode == ATM:
        积分 atmospheric dynamics
        ground → stop
        exit   → save + switch VAC

    elif mode == VAC:
        积分 vacuum dynamics
        entry → save + switch ATM
```

最后拼接所有 segment。

## D.6 边界处理

不要用：

```python
h = h_atm + 1
```

人为改变状态。

优先依赖：

- event direction；
- mode state machine；
- 必要时只处理数值时间起点，不修改物理状态。

## D.7 每个跳跃周期保存

$$
t_i^{exit},
\quad
t_i^{entry},
\quad
h_i^{max},
\quad
v_i^{exit},
\quad
v_i^{entry},
\quad
\Delta v_i,
\quad
\Delta R_i.
$$

保存：

```text
skip_cycles.csv
```

## D.8 状态连续性

每次切换检查：

$$
r^-=r^+,
\quad
\theta^-=\theta^+,
\quad
v^-=v^+,
\quad
\gamma^-=\gamma^+.
$$

并记录：

$$
\|x^+-x^-\|.
$$

应接近数值误差水平。

## D.9 验收标准

- [ ] ATM / VAC 状态机稳定；
- [ ] 无事件死循环；
- [ ] 切换状态连续；
- [ ] 桑格尔轨迹正常触地；
- [ ] 基准量级合理；
- [ ] 每次跳跃信息独立保存。

---

# Phase E：基准复现与完整物理验证

## E.1 目标

冻结“单工况正确性”，完成两类基准弹道的一致条件对比。

## E.2 统一工况

固定：

$$
h_0=100\text{ km},
\quad
v_0=7000\text{ m/s},
\quad
\gamma_0=-5^\circ,
\quad
K=3.
$$

两类弹道：

- 初值相同；
- 模型参数相同；
- solver 与容差相同；
- 只允许模式定义不同。

## E.3 必画曲线

1. $$h-R$$
2. $$h-t$$
3. $$v-t$$
4. $$\gamma-t$$
5. $$q-t$$
6. $$D-t$$
7. $$L-t$$

桑格尔额外标注：

- ATM / VAC 区间；
- exit / entry；
- 峰值高度。

## E.4 对比表

| 指标 | 桑格尔 | 钱学森 |
|---|---:|---:|
| 飞行时间 | | |
| 总射程 | | |
| 末端速度 | | |
| 最大高度 | | |
| 最大动压 | | |
| 动压积分代理量 | | |
| 跳跃次数 | | |

## E.5 热载荷表述

题目使用

$$
Q_{proxy}=\int_0^{t_f}q(t)\,dt.
$$

现阶段保留，但统一称为：

> **动压积分代理指标 / simplified thermal-load proxy**

不要把它直接表述为真实气动热流积分。

## E.6 本阶段结论边界

只讨论：

- 高度演化；
- 速度衰减；
- 射程；
- 动压；
- 模式切换。

**不提前得出“谁更不可预测”。**

可预测性必须由后续 STM / FTLE / prediction error 决定。

## E.7 验收标准

- [ ] 两类基准轨迹可重复生成；
- [ ] 对比表完整；
- [ ] 图由程序自动生成；
- [ ] 结果与题目基准量级一致；
- [ ] 数值方法与模型文档齐全。

---

# Phase F：二维参数敏感性扫描

## F.1 目标

获得

$$
(\gamma_0,K)
$$

参数平面上的弹道响应结构，为后续 FTLE、Monte Carlo 和优化选取重点工况。

## F.2 第一轮网格

建议：

$$
\gamma_0\in[-8^\circ,-2^\circ],
$$

步长：

$$
0.5^\circ
$$

共 13 个点。

$$
K\in[2.0,4.5],
$$

步长：

$$
0.25
$$

共 11 个点。

单类弹道：

$$
13\times11=143
$$

两类共：

$$
286
$$

个工况。

## F.3 每个工况保存

### 输入

```text
trajectory_type
gamma0
K
solver
rtol
atol
```

### 输出

```text
success
termination_reason
flight_time
range
terminal_velocity
max_height
max_dynamic_pressure
q_integral
skip_count
```

## F.4 可行域标签

```text
VALID
GROUND_EARLY
INTEGRATION_FAILED
NONPHYSICAL_STATE
NO_GROUND_EVENT
CONSTRAINT_VIOLATION
```

**不要删除失败点。**

失败点本身就是可行域边界信息。

## F.5 响应面

分别对桑格尔与钱学森绘制：

$$
R_f(\gamma_0,K),
$$

$$
t_f(\gamma_0,K),
$$

$$
v_f(\gamma_0,K),
$$

$$
Q_{proxy}(\gamma_0,K).
$$

建议：

- heatmap；
- contour；
- 3D response surface。

## F.6 局部敏感性

第一版可有限差分估计：

$$
\frac{\partial R}{\partial\gamma_0},
\quad
\frac{\partial R}{\partial K},
$$

以及：

$$
\frac{\partial v_f}{\partial\gamma_0},
\quad
\frac{\partial v_f}{\partial K}.
$$

## F.7 后续用途

这些结果用于：

1. 选择 FTLE 重点区域；
2. 找模式切换敏感边界；
3. 给优化器初值；
4. 找轨迹形态突变区域；
5. 决定 Monte Carlo 扰动尺度。

## F.8 验收标准

- [ ] 完成二维 grid；
- [ ] 批量运行完全自动化；
- [ ] 失败工况可追踪；
- [ ] 至少 4 个响应面；
- [ ] 单个工况可复跑；
- [ ] 基准点与 Phase E 完全一致。

---

# Phase G：为后续研究预留接口

## G.1 目标

让第 3–5 章无需重构底层动力学。

## G.2 状态 Jacobian

实现：

$$
A(t)=\frac{\partial f}{\partial x}.
$$

接口：

```python
jacobian_state(t, state, model, mode)
```

第一版可采用：

- 解析推导；
- 自动微分；
- 高精度有限差分。

建议至少两种方式交叉验证。

## G.3 参数 Jacobian

实现：

$$
B_p(t)=\frac{\partial f}{\partial p},
$$

其中

$$
p=[\rho_0,H,C_D,m,S,\ldots]^T.
$$

接口：

```python
jacobian_params(t, state, model, mode)
```

用于：

- 参数敏感性；
- uncertainty propagation；
- robust optimization。

## G.4 状态转移矩阵接口

后续要积分：

$$
\dot\Phi=A(t)\Phi,
$$

$$
\Phi(t_0)=I.
$$

Phase G 先实现：

```python
stm_rhs(...)
```

和最基本单元测试，不展开正式 FTLE 研究。

## G.5 分段控制

增加：

```python
PiecewiseConstantKControl
```

满足：

$$
K(t)=K_i,
\quad
t\in[t_i,t_{i+1}).
$$

建议接口：

```text
control.parameters
control.breakpoints
control.evaluate(t, state)
```

以后优化器只改 `control.parameters`。

## G.6 模式枚举

建议：

```python
class FlightMode(Enum):
    ATM_SKIP = 0
    VACUUM = 1
    CONTINUOUS_GLIDE = 2
```

后续可扩展：

```text
TERMINAL_DIVE
BOOST
```

## G.7 随机参数接口

实现：

```python
sample_parameters(seed) -> ModelParams
```

Phase G 不必正式做 Monte Carlo，但必须：

- 可扰动；
- 可复制；
- 可记录 seed。

## G.8 统一结果对象

定义：

```python
TrajectoryResult
```

至少包含：

```text
time
state
mode
derived
events
metrics
metadata
```

后续所有分析只依赖 `TrajectoryResult`，不直接耦合 `solve_ivp` 原始返回对象。

## G.9 验收标准

- [ ] `jacobian_state()` 可调用；
- [ ] `jacobian_params()` 可调用；
- [ ] 常数 K 可无缝换为分段 K；
- [ ] mode 标准化；
- [ ] 结果对象统一；
- [ ] 参数扰动可复现；
- [ ] 后续分析不需要修改底层 `dynamics()`。

---

# Phase H：冻结 Baseline

## H.1 目标

形成一个后续研究不随意修改的稳定版本：

```text
baseline_v1
```

建议 Git Tag：

```text
dynamics-baseline-v1.0
```

## H.2 冻结前条件

- [ ] Phase A 基础模块测试通过；
- [ ] 钱学森基准通过；
- [ ] 桑格尔基准通过；
- [ ] solver comparison 完成；
- [ ] tolerance convergence 完成；
- [ ] hybrid event 无死循环；
- [ ] 两类基准结果稳定；
- [ ] 参数二维扫描可自动运行；
- [ ] Jacobian / control / parameter 接口已预留。

## H.3 固定配置

建议：

```yaml
model: baseline_v1

environment:
  Re: ...
  g0: ...
  rho0: ...
  H: ...
  h_atm: 100000.0

vehicle:
  mass: 1000.0
  area: 1.0
  cd: 0.2

initial:
  h0: 100000.0
  v0: 7000.0
  gamma0_deg: -5.0
  theta0: 0.0

control:
  type: constant_K
  K: 3.0

solver:
  method: ...
  rtol: ...
  atol: ...
  max_step: ...
```

## H.4 Regression Tests

以后改任何代码，都自动检查：

### 钱学森

```text
range
flight_time
terminal_velocity
```

不能超过预设容差。

### 桑格尔

额外检查：

```text
skip_count
first_peak_height
event_sequence
```

## H.5 Git 冻结

```bash
git add .
git commit -m "冻结高超声速弹道动力学 baseline v1"
git tag dynamics-baseline-v1.0
```

之后：

```text
baseline_v1 保持不变
research_model_v2 单独演化
```

## H.6 最终目录建议

```text
project/
├── src/
│   ├── models/
│   ├── controls/
│   ├── simulation/
│   └── analysis/
├── configs/
│   ├── baseline_qian.yaml
│   ├── baseline_sanger.yaml
│   └── sensitivity_gamma_k.yaml
├── experiments/
│   ├── run_qian_baseline.py
│   ├── run_sanger_baseline.py
│   ├── solver_convergence.py
│   └── scan_gamma_k.py
├── results/
│   ├── baseline/
│   ├── convergence/
│   └── sensitivity/
├── tests/
└── docs/
    └── dynamics_baseline_v1.md
```

---

# 9. 建议时间安排

| Phase | 核心任务 | 建议时间 |
|---|---|---:|
| A | 单位、参数、物理模块 | 0.5–1 天 |
| B | 钱学森基准 | 0.5–1 天 |
| C | Solver / tolerance 验证 | 0.5–1 天 |
| D | 桑格尔事件状态机 | 1–2 天 |
| E | 基准对比与图表 | 0.5–1 天 |
| F | 二维参数扫描 | 1 天 |
| G | Jacobian / 控制 / 参数接口 | 1–2 天 |
| H | Regression test + 冻结 | 0.5 天 |

总体约：

$$
\boxed{5\sim9\text{ 个有效工作日}}
$$

建议额外为事件切换和 Jacobian 调试预留 2–3 天。

---

# 10. 各阶段禁止提前开展的内容

## Phase A–B

暂不做：

- Lyapunov 指数；
- Monte Carlo；
- AHP；
- 优化；
- Neural Network。

## Phase C–D

暂不急着：

- 换复杂大气模型；
- 加三自由度；
- 加地球自转。

先把 baseline 做对。

## Phase E–F

不要预设：

> 某种弹道一定更不可预测。

本阶段只分析标称动力学和参数响应。

## Phase G–H

只预留接口，不正式展开：

- FTLE；
- CRLB；
- 拦截概率；
- 鲁棒优化。

---

# 11. Phase H 后的下一阶段

Baseline 冻结后再进入：

$$
\boxed{
\text{STM}
\rightarrow
\text{FTLE}
\rightarrow
\text{扰动传播}
\rightarrow
\text{实际预测误差}
}
$$

第一步必须先验证：

$$
\delta x(t)
\approx
\Phi(t,t_0)\delta x_0
$$

在小扰动范围内成立。

之后才正式开展“有限时可预测性”研究。

---

# 12. 最终验收清单

## 模型

- [ ] 单位统一
- [ ] 状态定义统一
- [ ] 重力模型正确
- [ ] 大气模型正确
- [ ] 气动力正确
- [ ] K 控制接口抽象

## 钱学森弹道

- [ ] 正常触地
- [ ] 基准量级合理
- [ ] 无 NaN / Inf
- [ ] 结果自动保存

## 数值验证

- [ ] RK45
- [ ] DOP853
- [ ] Radau
- [ ] BDF
- [ ] tolerance convergence
- [ ] max_step sensitivity

## 桑格尔弹道

- [ ] ATM / VAC 状态机
- [ ] exit event
- [ ] entry event
- [ ] ground event
- [ ] 状态连续
- [ ] 无事件死循环
- [ ] 跳跃周期记录

## 敏感性

- [ ] $$\gamma_0$$ 扫描
- [ ] $$K$$ 扫描
- [ ] 二维响应面
- [ ] 可行域分类
- [ ] 自动批量运行

## 后续接口

- [ ] state Jacobian
- [ ] parameter Jacobian
- [ ] STM 接口
- [ ] piecewise K
- [ ] parameter sampling
- [ ] unified result object

## Baseline 冻结

- [ ] regression tests
- [ ] config frozen
- [ ] metadata complete
- [ ] Git commit
- [ ] Git tag
- [ ] baseline_v1 文档

---

# 13. Phase A–H 的最终目标

完成后得到的不是“两条弹道图”，而是一个经过

$$
\boxed{
\text{物理验证}
+
\text{基准验证}
+
\text{数值收敛验证}
+
\text{软件回归验证}
}
$$

的高超声速混合动力学仿真平台。

它将作为后续：

$$
\text{STM}
+
\text{FTLE}
+
\text{Monte Carlo}
+
\text{拦截风险}
+
\text{混合轨迹鲁棒优化}
$$

的统一计算基础。

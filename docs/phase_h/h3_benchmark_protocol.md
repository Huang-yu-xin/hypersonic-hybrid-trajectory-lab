# H3-0 — RareTopo Benchmark Definition Freeze（Theory-to-Hybrid）

> 项目：RareTopo — Rare Topology Transition Estimation in Hybrid Dynamical
> Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab`
> 分支：`feature/phase-h-uncertainty-risk`
> 上游：H2R ACCEPTED（`7895712c`）· ML-B1 COMPLETE（`78ecfb8`）·
> Local Fold Geometry / Geometry-IS Variance Theorem ACCEPTED
> 状态：**H3-0 COMPLETE / READY FOR REVIEW**（definition freeze；2026-08-20；
> 未实现 sampler / estimator / proposal，未生成 dataset）
> 执行 brief：`H3-0_Experiment_Task_RareTopo_Benchmark_Definition_Freeze.md`
> 权威文档：本文档
> machine-readable schema：`tests/data/h3_schema_v1.json`
> （`schema_version = h3-sample-schema-v1`，`status = FROZEN`）
> 回归测试：`tests/test_h3_schema.py`（38 cases：required fields /
> topology label consistency / geometry field availability / frozen
> ML-B1 cross-check）

---

## 0. Scientific objective

Phase H 前序结论：

- H2/H2R：fixed-topology 线性不确定性在有限 α 下的 nonlinear validity
  brackets 已量化；
- Geometry-IS Variance Theorem（local Gaussian half-space）已理论证明
  Geometry-IS 相对 Monte Carlo 的 variance 优势；
- ML-B1：真实 hybrid simulator 上 first-order topology geometry
  （`b`、`a = (Φ*)ᵀn*`、`v_geom`、`β_local`）计算正确性已验证
  （5 anchors 全 PASS，sign(b) vs exact topology 80/80）。

**H3 不再验证 "Geometry-IS 是否比 Monte Carlo variance 更低"** —— 该问题
已由 local Gaussian half-space theorem 理论证明。

H3 的唯一研究问题：

> **When does hybrid topology geometry preserve Geometry-IS variance
> reduction?**
> （hybrid topology geometry 何时保留 Geometry-IS variance reduction？）

即研究 **Theory ↓ Hybrid topology system** 之间的 gap：理论假设的 local
linear half-space 几何，在真实 nonlinear hybrid（事件切换、grazing、
multi-channel）下何时仍然成立。

**H3-0 只冻结 benchmark**，不实现任何估计器：

- ❌ Geometry-IS sampler
- ❌ Importance sampling estimator
- ❌ CEM
- ❌ Flow model
- ❌ Residual learning

H3-0 交付物（定义层）：

1. rare topology transition benchmark（事件定义 + dataset levels）
2. dataset schema（H3 sample schema v1，machine-readable）
3. exact simulator oracle（ground truth protocol）
4. geometry deviation metrics（`ε_geo`、`Δ_d`）
5. evaluation protocol（levels / metrics / experiment matrix）

---

## 1. Scientific scope

### Supported（研究范围）

```text
topology geometry
      ↓
local linear approximation
      ↓
Geometry-IS validity
```

### NOT claimed（禁止）

- global optimal IS
- all hybrid systems valid
- Geometry-IS always superior
- topology probability solved
- adaptive proposal solved

---

## 2. Task 1 — Freeze rare event definition

随机输入与不确定度（继承 H0 canonical synthetic family）：

$$
X_0 = \bar x_0 + \delta X_0,\qquad
\delta X_0 \sim \mathcal N(0, P_0),\qquad
P_0 = S_A\,(\alpha^2 I)\,S_A^{\mathsf T},
$$

$$
S_A = \operatorname{diag}(10^5,\ 1,\ 7\times10^3,\ 0.1)\quad(\text{frozen}).
$$

拓扑标签：

$$
Z_0 = T(\bar x_0)\quad(\text{nominal topology}),
\qquad
Z = T(X_0)\quad(\text{sample topology}),
$$

$$
A = \{\,Z \neq Z_0\,\}\quad(\text{rare topology transition event}).
$$

**Frozen（冻结内容）：**

- event definition = **topology transition only**；
- **不是** terminal state error；
- **不是** range error；
- **不是** energy error。

## 3. Task 2 — Define topology label protocol

每个 trajectory **必须保存** 完整拓扑标签（禁止只保存 `success/failure`）：

| field | 含义 |
|---|---|
| `topology_id` | exact topology 的唯一编码：`<regime>:<'+'-joined switch_signature or 'none'>` |
| `event_sequence` | 完整 event-kind 序列（如 `synthetic_initial_entry`, `atmospheric_pullout`, `srti`, …） |
| `switch_signature` | Phase-G0 switch taxonomy 名称序列（`sanger_atmosphere_exit` / `sanger_atmosphere_entry`） |
| `mode_sequence` | 访问过的 mode 序列；**不变量** `len(mode_sequence) = len(switch_signature) + 1` |
| `terminal_event` | 终端事件 kind（`srti` / `atmosphere_exit` / `max_time` …） |
| `critical_event` | 承载 topology transition channel 的关键事件 |
| `skip_count` | `SRTI_N{k}` 中的 `k`（跳过的 atm-exit 次数，topology index） |

**禁止只保存** `success/failure`。

原因：H3 研究 **topology transition**，而不是普通 failure
classification —— `success/failure` 粒度丢失了 transition channel 与
switch signature，无法回答 "geometry 何时保留 variance reduction"。

编码与不变量（机器可读见 schema `topology_label_protocol`）：

- regime 编码：`SRTI_N{skip_count}`（正则 `SRTI_N[0-9]+`）；
- switch 词汇表（frozen）：`sanger_atmosphere_exit`、
  `sanger_atmosphere_entry`；
- mode-count 不变量：`len(mode_sequence) = len(switch_signature) + 1`。

## 4. Task 3 — Define dataset schema（H3 sample schema v1）

机器可读唯一真实来源：`tests/data/h3_schema_v1.json`
（`schema_version = h3-sample-schema-v1`，`status = FROZEN`）。

### 4.1 Input

| field | type | 含义 |
|---|---|---|
| `sample_id` | string | 唯一 sample 标识；与 H2 sample-bank CRN 兼容 |
| `x0` | array[4] | 名义初始状态 `\bar x_0 = [r, θ, v, γ]`（物理单位） |
| `delta_x` | array[4] | `\delta X_0 = X_0 - \bar x_0`，`\delta X_0 \sim \mathcal N(0,P_0)` |
| `whitened_u` | array[4] | 标准化输入 `u = L_0^{-1}\delta X_0`，`P_0 = L_0L_0^{\mathsf T}`，`u \sim \mathcal N(0,\alpha^2 I)` |
| `alpha` | number | synthetic dimensionless uncertainty amplitude（**NOT numerically frozen**，`ALPHA_STATUS = PENDING_NUMERICAL_AUDIT`） |
| `uncertainty_scale` | number | `P_0` 的数值协方差尺度（canonical family 下 = `alpha^2`） |

### 4.2 Exact simulator output（oracle 输出）

| field | type | 含义 |
|---|---|---|
| `topology_label` | string | exact sample topology（`SRTI_N{k}`） |
| `nominal_topology` | string | `Z_0 = T(\bar x_0)` |
| `transition_flag` | boolean | `\mathbb 1[Z \neq Z_0]`；**一致性** `transition_flag == (topology_label != nominal_topology)` |
| `transition_channel` | string\|null | 承载 transition 的事件 channel（如 `atmosphere_exit`）；无 transition 时为 `null` |
| `event_sequence` | array[string] | 完整 event-kind 序列 |
| `switch_signature` | array[string] | 已执行 switch 的 Phase-G0 名称序列 |
| `terminal_state` | array[4]\|null | 终端状态 `[r,θ,v,γ]`；失败时为 `null` |
| `simulation_status` | string | `COMPLETE` / `MAX_TIME_TERMINATED` / `NONPHYSICAL` / `FAILED` |

### 4.3 Geometry information（来自 ML-B1，只读复用）

| H3 field | ML-B1 source | 含义 |
|---|---|---|
| `margin_b` | `nominal.b` | `b = σ·G(x*(t*; x_0))`：critical extremum 处的 virtual topology margin |
| `gradient_a` | `analytic_gradient.a_raw` | `a = (Φ*)ᵀn* = ∂b/∂x_0`：一阶解析拓扑梯度 |
| `beta_local` | `geometry_direction.beta_local` | `β_local = b_0/√(aᵀP_0a)`：whitened 单位下的 local FORM-like clearance |
| `design_direction` | `geometry_direction.v_geom` | `v_geom = -P_0a/√(aᵀP_0a)`：协方差加权几何方向 |
| `u_star` | `geometry_direction.alpha` | `α = L_0^{\mathsf T}a/\lVert L_0^{\mathsf T}a\rVert`：whitened design direction |
| `critical_guard` | `nominal.guard_value` | 关键极值处的 oriented guard 值 |
| `critical_time` | `nominal.t_star` | `t*`：tracked critical extremum 时刻 |
| `d` | 由 `n_star`、`x_star`、`f(x*)` 导出 | `d = n^{\mathsf T} f`：guard 法向与向量场的内积（grazing 灵敏度，`d → 0` at grazing） |

> ML-B1 snapshot（`ml-b1-first-order-geometry-v1`）已存 `n_star` 与
> `x_star`，H3-1 可直接计算 `d = n^T f`，无需重跑 ML-B1。

### 4.4 Nonlinearity diagnostics

| field | 含义 |
|---|---|
| `linear_prediction` | `\hat g(x) = g(x_0) + \nabla g(x_0)^{\mathsf T}(x-x_0)`：sample 点处的一阶 margin 预测 |
| `true_margin` | `g(x)`：sample 点处的 exact margin（固定 critical mode 的 virtual continuation） |
| `geometry_error` | `g(x) - \hat g(x)`：带符号一阶近似偏差 |
| `epsilon_geo` | `\lVert g(x) - \hat g(x)\rVert`：local half-space approximation deviation（几何精度指标） |

## 5. Task 4 — Define geometry error

local linear approximation：

$$
\hat g(x) = g(x_0) + \nabla g(x_0)^{\mathsf T}(x - x_0),
$$

geometry error：

$$
\boxed{\;\varepsilon_{\rm geo} = \lVert g(x) - \hat g(x)\rVert\;}
$$

**注意：geometry error 不是 topology probability。**

`ε_geo` 表示 **local half-space approximation deviation** —— 衡量一阶
几何（proposal 所用）在 sample 点处的局部失效程度，与事件概率
`P(Z ≠ Z_0)` 是两个不同的量。

## 6. Task 5 — Define H3 dataset levels

| Level | 目标 | 特点 |
|---|---|---|
| **L0: Near-linear** | 验证 theorem 极限（geometry 完全成立） | small `α` · small curvature · single channel |
| **L1: Moderate hybrid** | 有限拓扑切换下 geometry 的保留 | finite topology switching · multiple events · nonlinear margin |
| **L2: Grazing dominated** | stress test（一阶近似最脆弱处） | near grazing · small `n^T f` · large sensitivity |
| **L3: Multi-channel topology** | future extension（多 channel 竞争） | multiple transition channels · `N_i → N_j` |

L0 是 theorem 极限（`ε_geo → 0` 预期）；L1/L2 是 H3 主要研究对象
（gap 出现处）；L3 为扩展预留。

## 7. Task 6 — Freeze evaluation metrics

### Geometry Accuracy

$$
\text{geometry accuracy} = \varepsilon_{\rm geo}.
$$

### Direction Accuracy

比较 geometry direction `d_geo` 与 reference optimal direction `d_opt`：

$$
\boxed{\;\Delta_d = 1 - \frac{d_{\rm geo} \cdot d_{\rm opt}}{\lVert d_{\rm geo}\rVert\,\lVert d_{\rm opt}\rVert}\;}
$$

`Δ_d = 0` 表示方向完全一致；`Δ_d → 1` 表示方向正交/背离。

### Sampling metrics（预留，H3-2+ 计算）

- VRF（variance reduction factor）
- ESS（effective sample size）
- relative variance
- simulator calls

> H3-0 只 freeze 定义，不计算任何 sampling metric（无 sampler）。

## 8. Task 7 — Freeze ground truth protocol

**Exact oracle（必须使用）：**

- real hybrid simulator（frozen production hybrid trajectory
  integrator；ML-B1 已验证的 exact topology oracle）；
- indicator：

$$
I_A(x) = \mathbb 1\!\left[T(x) \neq T(\bar x)\right].
$$

**禁止：**

- 使用 `sign(b)` 替代 exact topology。

原因：`b`（margin）是 **proposal geometry**，不是 event oracle ——
topology transition 由真实 hybrid 事件的执行/跳过决定，不能由一阶
margin 符号推断（grazing 附近 `b` 与 exact topology 的对应只在
ML-B1 已验证的 local anchors 上成立，不能全局假设）。

## 9. Task 8 — H3 initial experiment matrix

H3 benchmark matrix v1（frozen；生成在 H3-1）：

| Experiment | Purpose |
|---|---|
| Smooth synthetic | verify theorem limit |
| Qian hybrid | single topology transition |
| Sanger hybrid | multi-switch topology |
| Grazing subset | stress test |
| Multi-channel subset | future extension |

## 10. Task 9 — Required deliverables

| Deliverable | 路径 | 内容 |
|---|---|---|
| Document | `docs/phase_h/h3_benchmark_protocol.md` | 本文档（event definition · dataset schema · geometry metrics · evaluation protocol · claim boundary） |
| Machine-readable schema | `tests/data/h3_schema_v1.json` | H3 sample schema v1（`h3-sample-schema-v1`，FROZEN） |
| Regression test | `tests/test_h3_schema.py` | required fields · topology label consistency · geometry field availability（+ frozen ML-B1 cross-check） |

测试验证点（与 schema 的 `success_criteria` 一一对应）：

- **required fields**：`input` / `exact_simulator_output` /
  `geometry_information` / `nonlinearity_diagnostics` 四组的 required
  字段集合与规格完整性；
- **topology label consistency**：`transition_flag == (Z != Z_0)`、
  `skip_count` 与 `SRTI_N{k}` 一致、`transition_channel` 存在性、
  mode-count 不变量、switch 词汇表、`success/failure` 单标签被禁止；
- **geometry field availability**：8 个 geometry 字段齐全、类型正确、
  `d = n^T f` 与 `ε_geo` 定义正确；
- **frozen ML-B1 cross-check（只读）**：5 个 reference-certified
  anchors 的字段（`b`/`t_star`/`guard_value`/`a_raw`/`v_geom`/`α`/
  `β_local`/`n_star`/`x_star`）可映射到 H3 schema，且由 frozen
  pipeline 构造的 sample record 能通过 schema validator。

## 11. Claim boundaries

### 本阶段 claim（H3-0）

- rare topology transition event `A = {Z ≠ Z_0}` 正式定义并冻结；
- dataset schema（H3 sample schema v1）冻结；
- exact oracle 定义为 real hybrid simulator（禁止 `sign(b)`）；
- geometry error metric `ε_geo` 与 direction metric `Δ_d` 定义冻结；
- evaluation protocol（levels / metrics / experiment matrix）冻结；
- 以上均为 **定义层**，不产生任何数值估计。

### NOT implemented / NOT claimed

- ❌ Geometry-IS sampler（未实现）
- ❌ Importance sampling estimator（未实现）
- ❌ CEM（未运行）
- ❌ Flow model（未训练）
- ❌ Residual learning（未训练）
- ❌ global optimal IS
- ❌ all hybrid systems valid
- ❌ Geometry-IS always superior
- ❌ topology probability solved
- ❌ adaptive proposal solved

## 12. Git rule compliance

本阶段仅新增：

- `docs/phase_h/h3_benchmark_protocol.md`（new doc）
- `tests/data/h3_schema_v1.json`（new schema）
- `tests/test_h3_schema.py`（new test）

未修改（git diff 验证）：

- ML-B1 implementation（`src/hyptraj/uncertainty/topology_margin.py` 等）
- frozen physics / simulator dynamics（Phase A-G 全部 frozen files）
- Geometry-IS sampler（不存在，未创建）

## 13. Success criteria 与进入 H3-1

| # | 判据 | 状态 |
|---|---|---|
| 1 | rare topology event formally defined | ✅ §2 / schema `event_definition` |
| 2 | dataset schema frozen | ✅ §4 / `h3_schema_v1.json`（FROZEN） |
| 3 | exact oracle defined | ✅ §8 / `ground_truth_protocol` |
| 4 | geometry error metric defined | ✅ §5 / `epsilon_geo` |
| 5 | evaluation protocol frozen | ✅ §6-§9 / `evaluation_metrics` + `experiment_matrix` |
| 6 | claim boundaries documented | ✅ §1 / §11 |

完成后进入：

> **H3-1** — Rare topology transition dataset generation
> （按 levels L0–L3 与 experiment matrix 生成 sample bank，计算
> `ε_geo`、`Δ_d`，全部基于 frozen oracle 与 frozen ML-B1 geometry）

---

## 14. H3-0 final report

```
H3-0 COMPLETE

Definition: A = {Z != Z0}, Z0 = T(xbar0), Z = T(X0), deltaX0 ~ N(0, P0);
            topology transition only (NOT terminal/range/energy error)

Dataset schema: h3-sample-schema-v1 (FROZEN)
    input: sample_id, x0, delta_x, whitened_u, alpha, uncertainty_scale
    exact simulator output: topology_label, nominal_topology,
        transition_flag, transition_channel, event_sequence,
        switch_signature, terminal_state, simulation_status
    geometry information (ML-B1): margin_b, gradient_a, beta_local,
        design_direction, u_star, critical_guard, critical_time, d = n^T f
    nonlinearity diagnostics: linear_prediction, true_margin,
        geometry_error, epsilon_geo

Metrics: epsilon_geo = ||g(x) - g_hat(x)|| (geometry accuracy);
         Delta_d = 1 - (d_geo · d_opt)/(||d_geo|| ||d_opt||) (direction);
         sampling metrics reserved for H3-2+: VRF, ESS, rel. variance, sim calls

Experiments frozen: Smooth synthetic | Qian hybrid | Sanger hybrid |
         Grazing subset | Multi-channel subset
Levels frozen: L0 near-linear | L1 moderate hybrid | L2 grazing dominated |
         L3 multi-channel topology

Not implemented: Geometry-IS, CEM, Flow, IS estimator

Commit: <filled at acceptance>
```

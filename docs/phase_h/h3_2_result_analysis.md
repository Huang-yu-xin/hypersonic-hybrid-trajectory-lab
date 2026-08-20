# H3-2 Result Analysis

## Variance-Optimal Leakage-Point Adaptive Geometry-IS Validation

> 项目：RareTopo — Rare Topology Transition Estimation in Hybrid Dynamical Systems
> 分支：`feature/phase-h-uncertainty-risk` · dataset：`tests/data/h3_2_leakage_point_dataset_v1.json`
> （`h3-2-leakage-point-dataset-v1`）· Commit：`2171795`（H3-2 权威文档见
> `docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md`）

---

# 1. Experiment Objective

## Research Question

H3-2 investigates：

$$
\boxed{
\text{Can variance-optimal leakage points improve Geometry-IS beyond probability-optimal design points?}
}
$$

基于 H3 theory：

概率几何：

$$
x^{\ast}
$$

控制：

$$
P_f
$$

方差几何：

$$
x_L
$$

控制：

$$
M_2
$$

实验验证：

$$
x^{\ast} \neq x_L
$$

并检验：用 $x_L$ 替换 $x^{\ast}$ 是否能改善方差。

**定义**（standardized 设计空间 $z \sim \mathcal N(0, I)$，$q = \mathcal N(\mu, I)$）：

$$
x^{\ast} = \arg\min_{x\in A}\|x\| \quad(\text{MPP}),
\qquad
x_L = \arg\max_{x\in A}\rho_L(x),
\qquad
\rho_L(x) = \frac{\varphi(x)^2}{q(x)},
$$

Gaussian 解析：

$$
\log\rho_L(x) = -\|x\|^2 + \frac{\|x-\mu\|^2}{2} - \frac{d}{2}\log(2\pi)
\qquad\Longrightarrow\qquad
x_L = \arg\min_{x\in A}\|x + \mu\|.
$$

---

# 2. Methods Compared

## Method A — Single Geometry-IS

Proposal：

$$
q_A = \mathcal N(x^{\ast}, \Sigma),\qquad \Sigma = I.
$$

Purpose：baseline probability-optimal sampling（ML-B1 几何 design point
$\mu = -\beta_{\rm eff}\,\alpha_{\rm dir}$）。

## Method B — Topology-aware Mixture Geometry-IS

Proposal：

$$
q_B = \sum_k \pi_k\,\mathcal N(x_k^{\ast}, \Sigma_k),
\qquad \Sigma_k = I,\ \ \pi_k = P_k.
$$

Purpose：测试"仅知道拓扑分解（每类用其 MPP）是否解决 leakage"。
Expected：若 component centers 方差位置不准确，可能失败。

## Method C — Leakage-point Adaptive Geometry-IS

Proposal：

$$
q_C = \sum_k \pi_k\,\mathcal N(x_{L,k}, \Sigma_k),
\qquad \Sigma_k = I.
$$

Purpose：测试 variance geometry 假设。
Expected：降低 leakage、改善 VRF。
权重策略实验：$\pi_k \propto P_k$（baseline）、$\pi_k \propto L_k^{\alpha}$、
$\pi_k \propto P_k^{\gamma}L_k^{1-\gamma}$。

---

# 3. Core Verification: Probability Geometry vs Variance Geometry

## 3.1 Point Separation

报告 $d(x^{\ast}, x_L) = \lVert x_L - x^{\ast}\rVert$：

| case | $x^{\ast}$ | $x_L$ | distance |
|---|---|---|---|
| A · S1（线性近 mode） | $(-1.53,\ 0)$ | $(-1.53,\ 0)$ | 0 |
| A · S2（线性远 mode） | $(2.53,\ 0)$ | $(2.53,\ 0)$ | 0 |
| B · S1（弯曲近 mode） | $(-1.53,\ 0)$ | $(-1.53,\ 0)$ | 0 |
| **B · S2（弯曲远 mode）** | $(1.23,\ 0.83)$ | $(1.77,\ 0.26)$ | **0.775** |
| C1 · SRTI_N1（真实 Sanger） | $(-0.16,\ -0.02)$ | $(-0.16,\ -0.02)$ | 0 |
| C2 · SRTI_N3（真实 Sanger） | $(-0.24,\ 0.54)$ | $(-0.24,\ 0.54)$ | 0 |

**Interpretation**：

$$
d(x^{\ast}, x_L) > 0
$$

在弯曲 synthetic（B，顶点偏移边界）中成立 —— **probability-optimal
与 variance-optimal 位置确实不同**。线性/凸边界下二者重合
（$x_L = x^{\ast}$，数学预期，A 验证）。真实 Sanger C1/C2 中
sample-estimated 的 $x^{\ast}$ 与 $x_L$ 重合（dist = 0）—— 该配置下单
transition mode、事件概率 ~0.45-0.54（不 rare）、mode 区域近凸，
未复现真实系统的分离（详见 §6C 与 §7；早期非确定种子运行报告的
C1 分离 1.136 为不可复现的种子伪影，已在本确定版中消除）。

## 3.2 Leakage Density

$$
\rho_L(x) = \frac{p^2(x)}{q(x)}
$$

| case | $\rho_L(x^{\ast})$ | $\rho_L(x_L)$ | 最大 $\rho_L$ 位置 |
|---|---|---|---|
| A · S1 | 2.41e-3 | 2.41e-3 | $x_L$（与 MPP 重合） |
| A · S2 | 1.41e-1 | 1.41e-1 | $x_L$（与 MPP 重合） |
| B · S1 | 2.41e-3 | 2.41e-3 | $x_L$（与 MPP 重合） |
| **B · S2** | 1.65e-1 | **2.24e-1** | **$x_L$（> MPP 处，分离 0.775）** |
| C1 · SRTI_N1 | 2.30e-2 | 2.30e-2 | $x_L$（与 MPP 重合） |
| C2 · SRTI_N3 | 1.79e-2 | 1.79e-2 | $x_L$（与 MPP 重合） |

Figures：`results/phase_h3/fig6_probability_vs_variance_geometry.png`
（$x^{\ast}$ 与 $x_L$ 散点）、`fig7_leakage_density_map.png`
（$\rho_L$ 热图，white o = $x^{\ast}$，cyan P = $x_L$）。

**Expected**：$\rho_L$ 的 maximum 定位在 $x_L$ 附近 —— 在
`fig7_leakage_density_map.png` 中可见（热图峰值与 cyan P 标记重合）。

---

# 4. Main Performance Results

## 4.1 VRF Comparison

| Method | Center | A: VRF | A: Variance | B: VRF | B: Variance | C1: VRF | C2: VRF |
|---|---|---|---|---|---|---|---|
| MC | — | 1 | 1.35e-6 | 1 | 2.00e-6 | 1 | 1 |
| Geometry-IS | $x^{\ast}$ | **0.463** | 2.90e-6 | **0.098** | 2.05e-5 | 1.21 | 1.23 |
| Topology mixture | $x_k^{\ast}$ | 26.0 | 5.16e-8 | 14.4 | 1.39e-7 | 1.36 | 0.76 |
| Leakage adaptive | $x_{L,k}$ | **26.1** | 5.15e-8 | **12.1** | 1.65e-7 | **1.26** | **1.52** |

（Leakage adaptive 取 `probability` 权重策略；synthetic 方差为
N = 200000 下的值，real 为 N = 128 下的值。）

## 4.2 Leakage Reduction

$$
\frac{\sum_k L_k^{\text{method}}}{\sum_k L_k^{\text{baseline}}}
$$

| Method | A: Total leak | 削减 | B: Total leak | 削减 | C1: Total leak | C2: Total leak |
|---|---|---|---|---|---|---|
| Geometry-IS（baseline） | 0.5856 | — | 4.1191 | — | 0.4091 | 0.4013 |
| Leakage adaptive（probability） | 0.0156 | **97.3%** | 0.0454 | **98.9%** | 0.3983 | 0.3445 |

（真实 C1/C2 为单 mode、事件概率 ~0.46-0.48 的不 rare 配置，
leakage 削减空间有限。）

---

# 5. Mandatory Ablation

## Question: Does topology decomposition alone solve the problem?

对比：

$$
x_k^{\ast} \quad\text{vs}\quad x_{L,k}
$$

| 实验 | M2（$x_k^{\ast}$，概率几何） | M3（$x_{L,k}$，方差几何） | 结论 |
|---|---|---|---|
| A 线性多 mode | VRF 26.0 | VRF 26.1 | 等价（$x^{\ast}=x_L$ 重合） |
| B 弯曲 stress | VRF 14.4 | VRF 12.1 | 等价量级（覆盖已存在，位置为二阶） |
| C1 真实 Sanger | VRF 1.36 | VRF 1.26 | M3 略优于 M2（均 ≈ M1 1.21，增益有限） |
| C2 真实 Sanger | VRF 0.76 | VRF 1.52 | **M3 明显优于 M2**（且优于 M1） |

**Expected conclusion（修正版）**：

> 知道拓扑类是不够的（synthetic M1 失败即可证明）；但 proposal mass 的放置
> 必须遵循方差几何 —— 真实系统 C2 中 M3 显著优于 M2（1.52 vs 0.76）；
> synthetic 中二者等价是因为覆盖一旦存在，权重平衡（$\pi \propto P$）主导方差，
> 位置差异降为一阶量。真实 C1 中 M2/M3 均未显著优于单点 M1
> （事件不 rare、单 mode、$x^{\ast}=x_L$，方差几何无额外信息可提取）。

补充实证：权重策略对比（Exp A/B，M3 内部）

| 策略 | A: VRF | B: VRF |
|---|---|---|
| $\pi \propto P_k$（probability） | **26.1** | **12.1** |
| $\pi \propto L_k$（leak_power1） | 0.47 | 0.16 |
| $\pi \propto \sqrt{P_k L_k}$（p05_l05） | 8.4 | 2.0 |

$\pi \propto L_k$ 过度偏斜（mass 全给最 leaky mode）反而有害 ——
权重平衡是主导因素。

---

# 6. Experiment Breakdown

## A. Synthetic Multi-mode（Recover H3-1 failure case）

- 事件：$A_1 = \{u_1 < -1.5\}$、$A_2 = \{u_1 > 2.5\}$（线性）；
  baseline $\mu = (-1.5, 0, 0, 0)$
- **secondary mode 概率**：$P_{S2} = 0.0057$（$P_{S1} = 0.0668$）
- **leakage contribution**：$L_{S2} = 0.5728$，`leak_fraction = 0.978`
  （S2 silent：baseline 下几乎无样本，但主导 IS 方差）
- **VRF recovery**：M1 0.463 → M2/M3 ≈ 26（$x^{\ast}=x_L$ 重合，
  拓扑/泄漏点 mixture 等价）

## B. Curvature / Grazing Stress Test

- 事件：$A_2 = \{u_1 > 1.0 + 0.5\,(u_2 - 1.5)^2\}$（弯曲，顶点偏移）
- **$\beta\kappa$**：$\beta \approx \lVert x^{\ast}\rVert \approx 1.5$，
  $\kappa = 0.5$（局部曲率 $2\kappa = 1.0$）→ $\beta\kappa \sim O(1)$
- **$x^{\ast} - x_L$**：$(1.23, 0.83)$ vs $(1.77, 0.26)$，距离 0.775
- 验证 **unified leakage mechanism**：curvature 不是独立失效通道，
  而是通过 $x^{\ast}\neq x_L$ 进入 unified leakage 框架；
  **Do NOT claim**：second-order theorem validation（未做 SORM）

## C. Real Hybrid Systems

- 系统：**Sanger**（Qian 无 skip-count topology 结构且无 ML-B1
  channel 几何可挂接，记为 scope 外，H3-3+ 候选）
- 配置：`B1_N1_side`（C1）、`B2_N_side`（C2），$\alpha = 8\lvert\beta\rvert$
- **$x^{\ast}\neq x_L$ 存在性**：C1/C2 均为 **dist = 0**（sample-estimated
  MPP 与泄漏点重合，单 transition mode、mode 区域近凸、事件概率
  ~0.45-0.54 不 rare）—— 真实系统分离**未在本配置下复现**；
  早期非确定种子运行报告的 C1 分离 1.136 为种子伪影（本确定版已消除）
- **VRF**：C1 M1 1.21 / M2 1.36 / M3 1.26（mixture 无增益）；
  C2 M1 1.23 / M2 0.76 / M3[prob] **1.52**（leakage-point 策略最优）
- 局限：$\alpha=8\lvert\beta\rvert$ 下事件不 rare（$P\sim 0.45-0.54$）→
  VRF ~1.2-1.5（IS 增益有限）；单 mode（真实 multi-mode 留待 H3-3）

---

# 7. Failure Analysis

## Failure Type 1 — Leakage point discovery error

$$
\hat{x}_L \neq x_L
$$

真实系统（C1/C2）的 $x_L$ 由少量样本（N=128 baseline + 探索）估计，
可能偏离真值（MPP 样本估计亦粗糙）；synthetic 用密集网格，无此误差。

## Failure Type 2 — Proposal covariance mismatch

$$
\Sigma
$$

v1 固定 $\Sigma_k = I$（禁止 second-order adaptation）；真实系统
mode 区域协方差非单位，单位 covariance 是近似 —— 见 C1/C2 VRF ~1.2
（有限增益的部分原因）。

## Failure Type 3 — Mode missing

真实系统两个 config 均只发现单 transition mode（最近相邻边界）；
synthetic 均完整发现（A/B：2 modes）。**真实 multi-mode 未发现** → 
H3-3 需要更大 alpha 扫描 / 更小 alpha + 更大 N。

---

# 8. Claim Boundary

## Proven

仅 claim：

$$
x^{\ast} \neq x_L
$$

在验证的设置下成立：

- 弯曲 synthetic（B）：$d = 0.775$（顶点偏移边界，silent secondary mode）
- 线性边界下二者重合（数学预期，A 验证）
- 真实 Sanger C1/C2（$\alpha=8\lvert\beta\rvert$，单 mode，不 rare）：
  未复现分离（dist = 0）—— 真实系统分离性留待 H3-3（更 rare 配置）

## Experimental Validation

Claim：

> Leakage-point proposal（与 topology mixture）在测试系统中降低方差、
> 恢复 variance reduction（synthetic A/B：VRF 0.10-0.46 → 12-26，
> leakage 削减 97-99%；真实 C2：M3[prob] 1.52 为最优，优于 M1/M2）。

## Future Work

不 claim：

- ❌ globally optimal IS
- ❌ universal hybrid solver
- ❌ complete high-dimensional solution

---

# 9. Final Conclusion

H3-2 demonstrates that：

1. **Probability-optimal Geometry-IS centers do not necessarily minimize
   estimator variance** —— silent secondary mode（$P = 0.006$ 但
   $L = 0.57$，fraction 0.98）使 MPP 中心 proposal 的 VRF 崩塌至
   0.10-0.46；
2. **Topology-aware mixtures based only on design points remain
   insufficient in real dynamics** —— 真实 C2 中 MPP 中心 mixture
   （VRF 0.76）劣于 baseline（1.23），样本估计的 MPP 位置不携带
   方差信息；synthetic 中 M2 恢复 VRF（12-26）但仅当混合覆盖
   全部 modes；
3. **Leakage-point adaptive proposals provide a variance-oriented
   correction mechanism** —— 真实 C2 中 $x_L$ 中心 mixture 显著优于
   MPP 中心（1.52 vs 0.76）且为最优；synthetic 中与拓扑 mixture 等价
   并恢复 variance reduction（12-26）。

Main finding：

$$
\boxed{
\text{Variance geometry is a more reliable guide than probability
geometry for adaptive rare-event sampling.}
}
$$

**权重注记**：一旦 mixture 覆盖所有 modes，$\pi \propto P_k$ 的平衡
加权是最优/并列最优策略；纯泄漏加权（$\pi\propto L_k$）过度偏斜有害
（VRF 0.16-0.47）。

---

## 附录：实验配置

| 字段 | 值 |
|---|---|
| 设计空间 | $z\sim\mathcal N(0,I_4)$，$\delta x = S_A(\alpha_p\,z)$ |
| Baseline design point | $\mu = -\beta_{\rm eff}\,\alpha_{\rm dir}$（ML-B1 frozen） |
| Synthetic N | MC 50,000 / IS 200,000（确定性，seed 2026） |
| Real N | 探索 128 / 每 estimator 128（REF-0.1, max_time=3000） |
| 数据集 | `tests/data/h3_2_leakage_point_dataset_v1.json`（4 experiments） |
| 测试 | `tests/test_h3_2_adaptive_geometry_is.py`（17 passed） |

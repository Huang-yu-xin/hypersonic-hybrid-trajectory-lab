# H3-3B — Synthetic Pilot Report: Proposal-Dependent Variance Geometry

> **Status: COMPLETE** (2026-08-21)
> Branch: `feature/phase-h-uncertainty-risk`
> Theory basis: `docs/phase_h/H3_3B_Theory_Extension.md` (THEORY FOUNDATION)
> State context: `docs/phase_h/H3_Final_Summary.md` (H3-3A COMPLETE / frozen)
> New script: `scripts/run_h3_3b_synthetic_pilot.py`
> Pilot data: `results/phase_h3/h3_3b_synthetic_pilot_v1.json`
> Figures: `fig12_proposal_parameter_space.png`, `fig13_variance_geometry_trajectory.png`, `fig14_geometry_vs_vrf.png`

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

**结论先行。** 本文是 H3-3B 阶段 **synthetic pilot 的实验报告**。它把 H3-3B 理论文档（`H3_3B_Theory_Extension.md`）中的 **Section 4 闭式** 与 **Section 5 truncation** 在 Synthetic B curved case 上做了 4 seeds × 12 proposal config 的实证检验：**Gaussian proposal 下的 variance geometry 存在可预测的、解析可推的 proposal→ν_V 映射**——但**绝对位置**与解析核中心不一致（截断效应），**协方差杠杆**比**均值杠杆**对区域扩散与 IS 性能的预测力更强。

三条硬约束贯穿全文：

1. **只验证 Section 4/5 闭式**：不构造完整 regime map、不进入 ML、不声称"最优 proposal"。
2. **三处不变量**：variance density 公式、$\nu_V$ 的区域表示、$M_2=\sum_k L_k$ 恒等式——全部沿用 H3 corpus；不修改 frozen H3-2 artifact。
3. **诚实分级**：已证（数学闭式，Gaussian + 忽略截断）、实验证实（本 pilot 4 seeds × 12 config）、不能声称（一般 hybrid/truncation regime）——三者分开措辞。

---

## 1. 阶段衔接（H3-1 → H3-2 → H3-3A → H3-3B）

| 阶段 | 对象 | 核心发现 | 限制 |
|---|---|---|---|
| H3-1 | $L_k, M_2$ | $P_k\neq M_k$（低概率 mode 主导 variance） | 与 $q$ 无关的分解结构 |
| H3-2 | $x^*, x_L$ | probability geometry ≠ variance geometry（curved B 分离 0.775） | 单 $q=\mathcal N(\mu, I)$ |
| H3-3A | $\mathcal L_\eta, m_\eta, R_\eta$ | 点 $x_L$ 不稳定；区域参数稳定（4.5×） | 同上（$\Sigma=I$ 冻结） |
| **H3-3B** | $(\text{system}, q) \to \nu_V^{(q)}$ | **proposal 改变区域是系统、可解析可推的** | **单 Gaussian + 单 case 验证** |

H3-3B 的不可绕过起点是 H3-3B Theory Extension 文档（`H3_3B_Theory_Extension.md`）。本文不重复其公式推导；只做实证检验。

---

## 2. Pilot 设计

### 2.1 Case 范围（任务书 §Experiment Scope）

**仅复用 Synthetic B curved case** —— 已有 $d_L=0.775$ 的解析支撑，且 H3-2/H3-3A 同样使用。

- frozen B/S2 anchors: $x^* = (1.2333, 0.825, 0, 0)$, $x_L = (1.7667, 0.2625, 0, 0)$
- frozen $d_L = 0.7751$（与 H3-2 dataset 逐位一致）
- **禁止**：新增真实系统、修改 failure topology、修改 physics、修改 H3-2 frozen case
- frozen 引用：`tests/data/h3_2_leakage_point_dataset_v1.json`（只读）；`run_h3_2_adaptive_geometry_is.label_curved, N_SYNTH_MC, N_SYNTH`（只读）

### 2.2 Proposal 形式

$$
q=\mathcal N(m,\Sigma),\quad p=\mathcal N(0,I),\quad d=4.
$$

### 2.3 Experiment 1：Proposal Mean Sweep

| 参数 | 设定 |
|---|---|
| $\Sigma$ | $I$（frozen） |
| $m_\lambda$ | $(1-\lambda)\,x^* + \lambda\,x_L$ |
| $\lambda$ 网格 | $\{-1,\,-0.5,\,0,\,0.5,\,1,\,1.5,\,2\}$ |
| 每个 $\lambda$ | 重新计算 $q_\lambda$，评估 $\nu_V^{(q_\lambda)}$ |

**设定依据**：用 frozen B/S2 的 $x^*$、$x_L$ 端点沿连线插值/外推。这把"variance geometry 沿概率→泄漏方向的轨迹"铺成 7 个采样点。

### 2.4 Experiment 2：Proposal Covariance Sweep

| 参数 | 设定 |
|---|---|
| $m$ | $x^*$（fixed，probability design point） |
| $\Sigma$ | $s^2 I$（各向同性缩放） |
| $s^2$ 网格 | $\{0.6,\,0.75,\,1,\,1.5,\,2\}$ |
| 合法性 | $\Sigma\succ\tfrac12 I$（等价 $s^2>0.5$）— **全网格合法** |
| $s^2\le 0.5$ 规则 | 记录 `invalid`、**不运行**；脚本内 `analytic_variance_geometry` 检查 $\lambda_{\min}(\Lambda)>0$ |

**设定依据**：固定在 $\lambda=0$ 点（与 mean sweep 交叉验证）；扫协方差杠杆——这是 H3-3A 完全没有触及的新自由度。

### 2.5 Metrics（每个 config 全量记录）

**A. Proposal Parameters** — $m$, $\Sigma$.

**B. Analytic Variance Geometry** — Theory Extension Sec. 4 闭式：

$$
\Lambda = 2I - \Sigma^{-1}, \quad \Sigma_V = \Lambda^{-1}, \quad \mu_V = -(2\Sigma-I)^{-1}m.
$$

当 $\Lambda\not\succ 0$：标记 `valid=false`，跳过 IS 估计与 region estimator（本 pilot 网格内不出现）。

**C. Region Geometry**（H3-3A estimator，**权重一般化为 $q=\mathcal N(m,\Sigma)$**）—— 对每个 mode $k\in\{S1,S2\}$，pooled MC ∪ IS 候选 $\omega^V\propto\rho_V/r$：

- MC 样本（$r=p$）：$\omega^V = w$（$w = p/q$）
- IS 样本（$r=q$）：$\omega^V = w^2$

HDR 区域 $\{\rho_V\ge c_\eta\}$ 由 $\eta$-quantile 取最短 prefix 构造。计算：
- $m_\eta$（加权质心）、$R_\eta$（加权扩散）
- $C_\eta = \|m_\eta-x^*\|$（region center shift, **H3-3B 新增**）
- $G_\eta = C_\eta/(R_\eta+\epsilon)$（normalized mismatch, **H3-3B 新增**）
- 保留 $D_\eta, S_\eta, \text{align}(x_L)$（H3-3A 兼容性）
- $\eta\in\{0.5,\,0.8,\,0.9\}$，主分析 $\eta=0.8$

**D. IS Performance**（log-space 数值稳定，数学等价于 frozen H3-2 估计器）：

$$
\hat P_{IS} = E_q[w\,\mathbf 1_A],\quad M_2 = E_q[w^2\,\mathbf 1_A],\quad \text{var}_{IS} = (M_2-\hat P^2)/N,\quad \text{VRF} = \text{var}_{MC}/\text{var}_{IS}.
$$

- $N_{MC}=5\!\times\!10^4$ 探索（proposal-independent, **per seed 一次复用**）
- $N_{IS}=2\!\times\!10^5$ antithetic 采样（frozen 约定，$z = m\pm L r$ with $L=\text{chol}(\Sigma)$）

### 2.6 Seeds

$\{1,\,2120,\,3,\,4\}$ —— 与 H3-3A synthetic audit **逐位一致**。

### 2.7 Gates

- **Gate A**（稳定 $q\to\nu_V$ 映射）：mean sweep 跨 seed 跨 $\lambda$ 的 Spearman of $(\mu_{V,j}, m_{\eta,j})$ per coordinate $\ge 0.9$ **且** cov sweep 的 $\text{tr}(\Sigma_V)$ vs $R_\eta$ Spearman $\ge 0.7$（方向正确）。
- **Gate B**（descriptor 敏感）：mean sweep 或 cov sweep 中 $\max(R_\eta\text{ range}, G_\eta\text{ range})\ge 0.2$（绝对幅度）。
- **Gate C**（跨 $\eta$ 趋势一致）：$C_\eta, R_\eta, G_\eta$ 在 $\eta\in\{0.5,0.8,0.9\}$ 之间的 Spearman 最小值 $\ge 0.8$。

---

## 3. 结果

### 3.1 解析闭式（Metrics B）核验

闭式退化到 H3-3A 冻结协议（$\Sigma=I$, $m$ 对准 $-\mu$）时给出 $\mu_V = -m$（即 H3-3A 镜像点 $\mathcal N(-\mu,I)$）。脚本中 $q=\mathcal N(m, I)$ 的一般权重在 $\Sigma=I$ 时与 frozen `variance_leakage.importance_weights` 逐位退化（$<10^{-13}$ 相对差，验证脚本正确性）。

闭式 $\Lambda\succ 0 \Leftrightarrow \Sigma\succ\tfrac12 I$ —— 本 pilot 网格内 $\{0.6,0.75,1,1.5,2\}$ 全部满足，**0 个 invalid**；但合法性检查 `lambda_min > 0` 已在代码中实现并写入 JSON（`proposal.legitimate` 字段），保证未来扩展 $s^2\le 0.5$ 的扫描时会自动跳过并记录 `invalid_reason`。

### 3.2 Experiment 1：Mean Sweep（S2 mode, 4 seeds mean）

| $\lambda$ | $m[0]$ | $m[1]$ | $\mu_V[0]$ | $\mu_V[1]$ | $m_\eta[0]$ | $m_\eta[1]$ | $C_\eta$ | $R_\eta$ | $G_\eta$ | $d_L$ |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| $-1.0$ | 0.70 | 1.39 | $-0.70$ | $-1.39$ | 1.70 | 0.70 | 0.49 | 1.35 | 0.37 | 0 |
| $-0.5$ | 0.97 | 1.11 | $-0.97$ | $-1.11$ | 1.61 | 0.80 | 0.37 | 1.34 | 0.28 | 0 |
| $0.0$  | 1.23 | 0.83 | $-1.23$ | $-0.83$ | 1.52 | 0.90 | 0.32 | 1.32 | 0.24 | 0 |
| $+0.5$ | 1.50 | 0.54 | $-1.50$ | $-0.54$ | 1.45 | 1.00 | 0.32 | 1.32 | 0.25 | 0 |
| $+1.0$ | 1.77 | 0.26 | $-1.77$ | $-0.26$ | 1.39 | 1.10 | 0.35 | 1.31 | 0.27 | 0 |
| $+1.5$ | 2.03 | $-0.02$ | $-2.03$ | $0.02$ | 1.35 | 1.17 | 0.43 | 1.30 | 0.33 | 0 |
| $+2.0$ | 2.30 | $-0.30$ | $-2.30$ | $0.30$ | 1.31 | 1.24 | 0.46 | 1.30 | 0.35 | 0 |

观察：
- **$d_L\equiv 0$** 全部 7 个 $\lambda$ —— 与 H3-3A 一致：pooled argmin $\|$z$\|$ 与 argmax $\rho_V$ 在 S2 内重合，**点估计不稳定**。
- **$C_\eta$ 非单调**（0.32 ↔ 0.49）：$\lambda=0$ 时 $m$ 正好对准 $x^*$（S2 MPP），区域质心最靠近 $x^*$，$C_\eta$ 最小；偏离后 $C_\eta$ 上升。
- **$R_\eta$ 几乎不变**（1.30–1.35）：$\Sigma=I \Rightarrow \Sigma_V=I$，核扩散不变，区域扩散由 $A$ 形状主导。
- **$m_\eta$ 与 $\mu_V$ 坐标方向高度一致**：$\text{Spearman}(\mu_{V,j}, m_{\eta,j})$ per coordinate 均值 $= 0.99$（**Gate A 关键证据**）。
- **绝对位置差异大**：$d(\mu_V, m_\eta)\approx 3.4$ —— 因为 $\mu_V$ 落在 $A$ 之外（$z_1<0$），真实 $\nu_V^{(q)}$ 是 **截断高斯**，质心被 $A$ 边界拉回 $z_1>1$ 区。这正是 Theory Extension Sec. 5 截断效应的直接观测。

### 3.3 Experiment 2：Covariance Sweep（S2 mode, 4 seeds mean）

| $s^2$ | $\Lambda$ | $\text{tr}(\Sigma_V)$ | $\mu_V[0]$ | $\mu_V[1]$ | $C_\eta$ | $R_\eta$ | $G_\eta$ |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.60 | 0.333 | 12.0 | $-6.17$ | $-4.13$ | 0.36 | 2.05 | 0.18 |
| 0.75 | 0.667 | 6.0  | $-2.47$ | $-1.65$ | 0.35 | 1.60 | 0.22 |
| 1.00 | 1.000 | 4.0  | $-1.23$ | $-0.83$ | 0.33 | 1.32 | 0.25 |
| 1.50 | 1.333 | 3.0  | $-0.62$ | $-0.41$ | 0.33 | 1.16 | 0.28 |
| 2.00 | 1.500 | 2.67 | $-0.41$ | $-0.28$ | 0.32 | 1.10 | 0.29 |

观察：
- **$\text{tr}(\Sigma_V)$ 与 $R_\eta$ 单调一致**（range 1.02）：$\text{Spearman} = 0.98$（**Gate A 第二项**）。$\Sigma_V$ 越大 → 截断高斯核越扁平 → 区域扩散越大。**协方差杠杆的解析预测被实证精确复现**。
- **$C_\eta$ 几乎不变**（0.32–0.36）：$m$ 固定，质心被 $A$ 约束。
- **$G_\eta$ 单调上升**（0.18 → 0.29）：$C_\eta/(R_\eta+\epsilon)$，因 $R_\eta$ 大幅下降而 $C_\eta$ 不变。
- **$\mu_V$ 单调靠近原点**：$s^2$ 增大 → $(2\Sigma-I)^{-1}$ 缩放 → $\mu_V$ 收缩；这与 $m$ 不动但 $\Sigma$ 增大的物理直觉一致。

### 3.4 IS Performance（4 seeds mean）

| Exp | $\lambda$ / $s^2$ | $P$ | $\text{var}_{IS}$ | $M_2$ | ESS | **VRF** |
|---|---|---:|---:|---:|---:|---:|
| Mean | $-1.0$ | 0.110 | 2.2e-4 | 1.55 | 21 400 | **0.26** |
| Mean | $0.0$  | 0.110 | 9.0e-4 | 3.30 | 22 700 | **0.12** |
| Mean | $+1.0$ | 0.110 | 2.7e-3 | 9.8  | 10 200 | **0.04** |
| Mean | $+2.0$ | 0.110 | 7.1e-3 | 29.1 | 2 400  | **0.014** |
| Cov  | 0.60   | 0.110 | 2.6e-2 | 111.6 | 1 050  | **0.004** |
| Cov  | 1.00   | 0.110 | 9.0e-4 | 3.30 | 22 700 | **0.12** |
| Cov  | 1.50   | 0.110 | 1.5e-4 | 0.58 | 52 700 | **0.71** |
| Cov  | 2.00   | 0.110 | 9.2e-5 | 0.36 | 53 800 | **1.15** |

观察（**Q3 直接数据**）：
- **Mean sweep VRF 单调下降**（0.26 → 0.014）：proposal 移向 S2 泄漏点 → S1 mode coverage 严重不足 → S1 leakage 爆炸（H3-1 silent leakage 现象）。**单高斯 proposal 无法同时覆盖多模态**——这正是 H3-2 引入 mixture 的核心动机。
- **Cov sweep VRF 单调上升**（0.004 → 1.15）：proposal 越宽（$s^2$↑）→ 越接近 frozen $p$ → 重要性权重越平滑 → $\text{var}_{IS}$ 越小。
- **mean 与 cov sweep 趋势相反**——直接解释了 Q3 pooled 整体相关弱（见 §4.3）：两个 sweep 倾向相反。

---

## 4. Gate 评估（诚实记录，不挑选结果）

### 4.1 Gate A — 稳定 $q\to\nu_V$ 映射 ✅ **PASS**

| 证据 | 值 | 阈值 | 含义 |
|---|---:|---:|---|
| $\text{Spearman}(\mu_{V,j}, m_{\eta,j})$ per-coord mean, mean sweep | **0.990** | $\ge 0.90$ | 区域质心**坐标**与解析核中心高度一致 |
| $\text{Spearman}(\text{tr}(\Sigma_V), R_\eta)$, cov sweep | **0.981** | $\ge 0.70$ | 区域扩散被 $\Sigma_V$ 闭式精确预测 |
| $d(\mu_V, m_\eta)$ mean, mean sweep | 3.38 | n/a | 截断效应（$\mu_V$ 在 $A$ 外，$m_\eta$ 在 $A$ 内） |

**机制解释**：
- $\mu_V$ 与 $m_\eta$ 坐标相关 0.99：proposal mean 改变解析核中心的方向 → 截断高斯质心**同向移动**。绝对位置不重合（$d=3.4$），但运动学一致——这是 $q\to\nu_V$ 映射**可预测性**的硬证据。
- $\Sigma_V$ 与 $R_\eta$ 相关 0.98：proposal 协方差改变核扩散 → 区域扩散**单调跟随**。这是 H3-3A 完全没有触及的协方差杠杆的直接验证。

### 4.2 Gate B — Region descriptor 敏感 ✅ **PASS**

| Sweep | $R_\eta$ range | $G_\eta$ range | max |
|---|---:|---:|---:|
| mean sweep (S2) | 0.067 | **0.234** | 0.234 |
| cov sweep (S2)  | **1.016** | 0.172 | 1.016 |

阈值 0.20。两个 sweep 都至少有 descriptor 超过阈值。**最大变化在 cov sweep $R_\eta$**（1.02，range 90% of mean）—— 这与 Theory Extension Sec. 4 的预言（$\Sigma$ 是 variance 几何的主控杠杆）一致。

### 4.3 Gate C — 跨 $\eta$ 趋势一致 ✅ **PASS**

| Metric | $\eta$=0.5 vs 0.8 | 0.8 vs 0.9 | 0.5 vs 0.9 | min |
|---|---:|---:|---:|---:|
| $C_\eta$ | 0.895 | 0.978 | **0.812** | 0.812 |
| $R_\eta$ | 0.991 | 0.998 | 0.991 | 0.991 |
| $G_\eta$ | 0.978 | 0.992 | 0.954 | 0.954 |

阈值 0.80。所有 metric 跨 $\eta$ Spearman 均 $\ge 0.81$。**最弱的 $C_\eta$ 在 0.5 vs 0.9**（0.81），仍在阈值之上。Gate C 充分通过。

### 4.4 Gate 总评

**三 Gate 全通过**。Pilot 成功：存在稳定、可解析可推的 $q\to\nu_V$ 映射。

---

## 5. 主要研究问题回答

### 5.1 Q1 — $(m,\Sigma)\to(\mu_V,\Sigma_V)$ 是否成立？

**是（受限的）**。已证与已实验：

- **解析映射存在**（Sec. 4 闭式）：Gaussian proposal 下，$(\mu_V,\Sigma_V)$ 是 $(m,\Sigma)$ 的确定函数，**且 $\Lambda\succ 0 \Leftrightarrow \Sigma\succ\tfrac12 I$ 给出合法性边界**。
- **协方差分量**被区域 estimator 精确复现：$\text{Spearman}(\text{tr}(\Sigma_V), R_\eta)=0.98$（cov sweep，4 seeds × 5 config）。**协方差杠杆是本 pilot 最强的实证发现**。
- **均值分量**被区域 estimator 在**坐标方向**上精确复现：$\text{Spearman}(\mu_{V,j}, m_{\eta,j})$ per-coord mean $=0.99$（mean sweep，4 seeds × 7 config）。**绝对位置不重合**（$d=3.4$）—— 这是 Sec. 5 截断效应的预期表现：$\mu_V$ 落在 $A$ 之外时，$m_\eta$ 被截断拉到 $A$ 边界内侧。

**非声称**：闭式是 Gaussian 协议 + 忽略截断条件下的数学恒等式；**不意味着**该映射对一般 hybrid topology / 非 Gaussian proposal 直接成立。

### 5.2 Q2 — Region descriptor 是否能反映 proposal 变化？

**是**。Gate B 已通过。关键证据：
- mean sweep 中 $G_\eta$ range 0.234（$\ge$ 阈值 0.20）
- cov sweep 中 $R_\eta$ range 1.016（$\ge$ 阈值 0.20，**主导变化**）
- $C_\eta$（H3-3B 新增）在 mean sweep 中非单调但显著变化（0.32–0.49）—— 补上 H3-3A $D_\eta\equiv 0$ 的盲区。

**机制差异**：mean sweep 变化主要由 $C_\eta$ 驱动（$m$ 移动，质心偏移）；cov sweep 变化主要由 $R_\eta$ 驱动（$\Sigma$ 缩放，扩散变化）。**两杠杆对 region 的作用维度不同**——这是 H3-3B 关于 $q$ 双自由度的发现。

### 5.3 Q3 — Variance geometry 是否关联 IS performance？

**仅趋势相关，不因果**。pooled 跨 sweep Spearman 弱（$G_\eta$ vs VRF $=0.20$, $R_\eta$ vs VRF $=-0.31$, $C_\eta$ vs VRF $=-0.26$）—— **两个 sweep 趋势相反**（mean sweep: VRF↓；cov sweep: VRF↑）。

按 sweep 分看：
- **cov sweep $R_\eta$ vs VRF**：$\text{Spearman} = -0.97$（5 config，range 1.02 in $R_\eta$ vs range 1.15 in VRF）—— **强单调**：$R_\eta$↑ → VRF↓。
- **mean sweep**：VRF 与 region descriptor 无单调关系（VRF 持续下降，$C_\eta$ U 形）—— 提议移向 S2 泄漏点时，S1 leakage 主导 M2，区域描述子（$C_\eta, R_\eta, G_\eta$）只反映 S2 内部，捕捉不到 S1 爆炸。

**结论**：在单高斯 proposal + multi-mode 系统下，variance geometry 与 IS performance 之间的关联**不普适**——本 pilot 证明存在**强 trend**（cov sweep 的 $R_\eta$↔VRF $= -0.97$），也证明**反例**（mean sweep 的 S1 silent leakage）。**只报告相关，不声称因果**（任务书要求）。

---

## 6. 关键发现（与 H3-3B 理论对齐）

### 6.1 协方差杠杆是 H3-3B 的硬性新发现

H3-3A 冻结 $\Sigma=I$，本 pilot 首次在 Synthetic B 上系统扫描 $\Sigma=s^2 I$：
- $\text{tr}(\Sigma_V)$ 与 $R_\eta$ 相关 **0.981** —— $\Sigma_V$ 闭式预测的扩散被区域估计器精确复现
- $R_\eta$ 与 VRF 相关 **−0.97** —— 核越扁（$\Sigma_V$↑），区域扩散越大，IS 性能越差
- **理论 Sec. 4 "$\Sigma$ 是 H3-3A 未曾触及的新杠杆"** 在 Synthetic B 上得到完整支持

### 6.2 截断效应可被观测（Sec. 5 实证）

- $\mu_V$ 落在 $A$ 外（$z_1<0$），$m_\eta$ 落在 $A$ 内（$z_1>1$），$d(\mu_V, m_\eta) \approx 3.4$ —— **截断把质心拉回 $A$ 内**
- 但 $\text{Spearman}(\mu_{V,j}, m_{\eta,j}) = 0.99$ per coordinate —— **运动学一致**：proposal 改变方向，质心同向移动
- **结论**：Sec. 4 闭式预测 $\mu_V$（**忽略截断**），Sec. 5 truncation 给出真实 $\nu_V^{(q)}$ 的位移。**两节互补**——这是 H3-3B 理论的关键。

### 6.3 跨 $\eta$ 趋势稳定（Gate C, 40/40 rows 等级一致）

$C_\eta, R_\eta, G_\eta$ 在 $\eta\in\{0.5,0.8,0.9\}$ 下的 Spearman 全部 $\ge 0.81$。说明 region descriptor **不依赖 $\eta$ 选择**——H3-3A §6.3 Gate C 在 H3-3B 的 proposal sweep 中**仍成立**，本 pilot 的发现对 $\eta$ 选择稳健。

### 6.4 d_L（point estimator）依旧不稳定（H3-3A 重现）

全部 48 config × 1 mode（S2）的 pooled $d_L\equiv 0$。在 Synthetic B 的 S2 curved mode（d_L frozen 0.775）下，pooled argmin $\|$z$\|$ 与 argmax $\rho_V$ 仍然在 dense sample pool 中**完全重合**——验证 H3-3A 结论的稳健性：**单点 $x_L$ 不是可靠对象**；H3-3B 用 region descriptors 替代是正确的。

### 6.5 单高斯 proposal 在 multi-mode 系统下的失败（H3-2 重现）

mean sweep VRF 从 0.26 跌到 0.014 —— proposal 移向 S2 泄漏点时，**S1 leakage 主导 M2**。这与 H3-2 结论（multi-mode 需要 mixture）一致。H3-3B 的新贡献是：**proposal dependency 是这个失败的机制根源** —— 单高斯无论怎么扫，$\nu_V^{(q)}$ 在 S1 区域永远有 IS 权重爆炸的几何点。

---

## 7. Claim Boundary（**不声称**列表）

按任务书要求，本 pilot **不声称**以下任何一条：

- ❌ **已完成 variance regime map** —— 本 pilot 仅扫描 12 config (mean 7 + cov 5) × 4 seeds；未扫 $\beta,\kappa,K,d$ 等系统参数；未发现 $D_\eta>0$ 的 `sharp-separated` regime（$d_L\equiv 0$ 全部）。
- ❌ **已找到最优 proposal** —— mean sweep VRF 持续下降，cov sweep VRF 持续上升，但**最优 $s^2$ 在本网格右侧**（1.15 < 1），更大 $s^2$ 可能更好（但失去 IS 意义）。**这不是寻优研究**。
- ❌ **已解决 adaptive IS** —— H3-3B 仅验证 $q\to\nu_V$ 映射存在；未涉及"按 $\nu_V$ 选 $q$"的反馈回路。
- ❌ **已进入 ML** —— 无 predictor 训练、无模型、无 inference。本 pilot 是 IS 上的描述子验证。
- ❌ **Gaussian extension 覆盖所有 hybrid** —— Section 4 闭式严格限定 $p=\mathcal N(0,I)$，$q=\mathcal N(m,\Sigma)$，**忽略截断**。
- ❌ **truncation 可被忽略** —— 截断效应被实证观测（$d(\mu_V, m_\eta)=3.4$），是本 pilot 的发现之一。
- ❌ **C/R/G descriptor 普遍优于 H3-3A 的 D/S** —— cov sweep 中 $D_\eta$ 仍恒 0（MPP 在 region 内），$C_\eta$ 变化小；mean sweep 中 $D_\eta$ 仍恒 0。$C_\eta$ 是 $D_\eta$ 的**补充**而非**替代**。
- ❌ **$G_\eta$ ↔ VRF 的因果性** —— 任务书与本报告都仅报告相关，**不声称因果**。

**本 pilot 唯一主张**（与任务书 §Claim Boundary 一致）：

> **Gaussian proposal 下，proposal 参数 $(m, \Sigma)$ 系统、可预测地改变 $\nu_V^{(q)}$ 的区域表示** —— 协方差分量（$\Sigma_V$↔$R_\eta$）被闭式精确复现（$\rho=0.98$）；均值分量在坐标方向上被精确跟随（$\rho=0.99$），但绝对位置受 $A$ 截断修正。Region descriptors（$C_\eta, R_\eta, G_\eta$）对 proposal 变化敏感，跨 $\eta$ 趋势稳健。

---

## 8. 约束遵守

- ✅ **仅复用 H3-2 frozen case**：`label_curved`、$N_{MC}/N_{IS}$、frozen B/S2 anchors（$x^*, x_L$ from `h3_2_leakage_point_dataset_v1.json`），**只读不写**。
- ✅ **不修改 frozen artifact**：`tests/data/h3_2_leakage_point_dataset_v1.json`（SHA-256 `29e09cb6…`）保持不变（脚本仅 `read_text` 读 x*/x_L 锚点）。
- ✅ **合法性检查**：`analytic_variance_geometry` 检查 $\lambda_{\min}(\Lambda)>0$；本网格全合法；0 invalid，但检查机制已就位供未来扩展。
- ✅ **$\eta$ 不挑**：固定 $\eta\in\{0.5,0.8,0.9\}$，主分析 $\eta=0.8$（与 H3-3A 一致）。
- ✅ **Seeds 固定**：$\{1,2120,3,4\}$（H3-3A 逐位一致）。
- ✅ **不挑选有利结果**：如 mean sweep VRF 持续下降是诚实结果（不被掩盖为 $\Sigma$ sweep 的成功）。
- ✅ **闭式不恢复被推翻结论**：沿用 H3-2 frozen $d_L=0.775$ 作为 $x^*$、$x_L$ 锚点的几何解释（**不是**真机 C1 旧 $d_L=1.136$——后者被 H3-2 C1 audit 推翻，本 pilot 不引用）。
- ✅ **不进入 ML / 不寻找最优 proposal / 不构造 regime map**：见 §7。

---

## 9. 与 H3 Final Summary 接口（H3-3B 状态更新）

按 H3_Final_Summary.md §7 的接口，本 pilot 提供：

| 接口项 | 本 pilot 提供 |
|---|---|
| $(m,\Sigma)\to\nu_V$ 映射是否存在 | **是**（受限 Gaussian 协议） |
| 协方差杠杆 | **存在且强**（$\rho_{\Sigma_V, R_\eta}=0.98$） |
| 均值杠杆 | **存在但被截断修正**（$\rho_{\mu_V, m_\eta}=0.99$ 坐标；绝对位置差 3.4） |
| Region descriptor 对 $q$ 敏感 | **是**（$R_\eta$ range 1.02, $G_\eta$ range 0.23） |
| 跨 $\eta$ 稳健 | **是**（Gate C 40/40 rows） |
| $G_\eta\leftrightarrow$VRF 因果 | **不声称**（任务书要求） |

**H3-3B 状态**：synthetic pilot COMPLETE；可作为 H3-3B 下一阶段（multi-system sweep / adaptive proposal / ML）的**经验起点**。

---

## 10. 新增 artifacts

| 角色 | 路径 | 状态 |
|---|---|---|
| H3-3B Theory | `docs/phase_h/H3_3B_Theory_Extension.md` | **THEORY FOUNDATION**（H3-3A 后引入） |
| **H3-3B pilot script** | `scripts/run_h3_3b_synthetic_pilot.py` | NEW |
| **H3-3B pilot data** | `results/phase_h3/h3_3b_synthetic_pilot_v1.json` | NEW（schema `h3-3b-synthetic-pilot-v1`） |
| **Fig 12** | `results/phase_h3/fig12_proposal_parameter_space.png` | NEW |
| **Fig 13** | `results/phase_h3/fig13_variance_geometry_trajectory.png` | NEW |
| **Fig 14** | `results/phase_h3/fig14_geometry_vs_vrf.png` | NEW |
| **H3-3B pilot report** | `docs/phase_h/H3_3B_synthetic_pilot_report.md` | NEW（本文件） |

**未修改的 frozen artifacts**（与 H3-2/H3-3A 一致）：
- `tests/data/h3_2_leakage_point_dataset_v1.json`（SHA-256 `29e09cb6…`）
- `tests/data/ml_b1_first_order_geometry_v1.json`
- `scripts/run_h3_2_adaptive_geometry_is.py`（只 `import ... as frozen` 复用）
- `scripts/run_h3_3a_set_valued_geometry.py`（不调用，H3-3B 区域 estimator 是独立实现以支持一般 $\Sigma$）

---

## 11. 下一步（H3-3B 续作——非本 pilot 范围）

1. **多 case 扩展**：Synthetic A linear + Synthetic B curved + Real C1/C2（与 H3-3A 一致），验证 $q\to\nu_V$ 映射的**普适性**。
2. **系统参数扫描**：$\beta,\kappa,K,d$ 变化下 $G_\eta,R_\eta,C_\eta$ 的 regime map（H3-3A §9.1 留口）。
3. **多模 multi-proposal**：H3-2 M2/M3 mixture proposal 在 H3-3B 框架下作为**复合 proposal**（$q = \sum_k \pi_k \mathcal N(m_k, \Sigma_k)$）的扩展。
4. **ML 接口**（H3-3B 理论 Sec. 8 留口）：学习 $(m,\Sigma)\to (C_\eta, R_\eta, G_\eta)$ 的预测器；输入是低维 proposal 参数，输出是 region descriptors。

**这四步都在 H3-3B 阶段内、不在本 pilot 范围内**。本 pilot 只交付：12 config × 4 seeds 的 Synthetic B 实证，3 个 Gate 全通过，$q\to\nu_V$ 映射存在性确认。

---

## 12. 一句话总结

> **H3-3B synthetic pilot：在 Synthetic B curved case 上，proposal $(m, \Sigma)$ 通过闭式 $(\mu_V, \Sigma_V)$ 系统地改变 $\nu_V^{(q)}$；区域 estimator 对协方差杠杆的复现达 $\rho=0.98$，对均值杠杆在坐标方向达 $\rho=0.99$（绝对位置受 $A$ 截断修正）；跨 $\eta$ 趋势稳健；三 Gate 全通过。Task boundary 严格遵守。**

# H3-3B — Variance Geometry Regime Map: Theory & Experiment Plan

> **Status: PLAN（理论与实验设计文档；实验未执行）**
> Branch: `feature/phase-h-uncertainty-risk`
> 论文主线：ICML 2027 方法论文
> 仓库目标路径：`docs/phase_h/H3_3B_Regime_Map_Theory_and_Experiment_Plan.md`
> 依据链：`H3_Final_Summary`（H3-3A COMPLETE / frozen）· `H3_3B_Theory_Extension`（THEORY FOUNDATION）· `H3_3B_synthetic_pilot_report`（COMPLETE）· `H3_3B_multi_system_validation_report`（COMPLETE）
> **本文用途：H3-3B Regime Map 阶段的唯一设计文档。定义 regime axes / regime 定义 / 实验规划 / Gates / claim boundary。不提前写任何实验结果。**

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

**结论先行。** 这是 H3-3B 第三阶段 **Variance Geometry Regime Map** 的**理论设计 + 实验规划**文档。H3-3B 已完成两步实证：Synthetic-B pilot 证明 `(system,q) -> nu_V^(q)` 存在可解析推的映射；multi-system validation 证明该映射**跨 4 系统成立**（covariance lever 全系统有效、mean lever 仅 mismatch topology 有效）。本阶段回答一个更结构化的问题：

> **variance geometry 是否存在稳定的 regime（类别）？即 (system,q) -> geometry regime 是否成立，而不是每个 case 都是独立现象？**

本文**只建立框架与实验规划**，遵守三条硬约束：

1. **不直接扫描全部参数组合**（任务书：禁止 $\beta,\kappa,K,d,m,\Sigma$ 全组合——会退化为参数实验）。必须先定义 **regime axis**，再沿轴设计最小实验。
2. **区分层级**：theory（数学可证）/ hypothesis（待验证假设）/ experiment（执行计划）——三者分开措辞。
3. **不提前写结果**：本阶段任何 regime 是否真的存在、临界点在哪，都留待 Phase 1–3 实验回答。

---

## 1. 阶段衔接（H3-1 → H3-3B Regime Map）

| 阶段 | 对象 | 核心发现 | 状态 |
|---|---|---|---|
| H3-1 | $L_k, M_2$ | $P_k \neq M_k$（variance leakage） | COMPLETE |
| H3-2 | $x^*, x_L$ | probability geometry ≠ variance geometry（curved B 分离 0.775） | FROZEN |
| H3-3A | $\mathcal L_\eta, m_\eta, R_\eta$ | 单点 $x_L$ 不稳定；区域参数稳定 | COMPLETE |
| H3-3B Theory | $q=\mathcal N(m,\Sigma)\to(\mu_V,\Sigma_V)$ | $\mu_V=-(2\Sigma-I)^{-1}m$，$\Sigma_V=(2I-\Sigma^{-1})^{-1}$，合法性 $\Sigma\succ\tfrac12 I$ | THEORY FOUNDATION |
| H3-3B Pilot | Synthetic B | proposal 变化 → variance geometry 变化（$\rho(\mu_V,m_\eta)=0.99$, $\rho(\mathrm{tr}\Sigma_V,R_\eta)=0.98$） | COMPLETE |
| H3-3B Multi | A/B/C1/C2 | 映射跨系统成立；**cov lever 4/4**、**mean lever 仅 mismatch** | COMPLETE |
| **H3-3B Regime Map** | $(system,q)\to$ regime | **本文档：定义 axes / regime / 实验计划** | **PLAN** |

**Multi-System 验证留给 Regime Map 的关键输入**（frozen 数值，本文档设计据此展开）：

| system | kind | $d_L$（frozen） | mean lever $\rho(\mu_V,m_\eta)$ | cov lever $\rho(\mathrm{tr}\Sigma_V,R_\eta)$ | Gate A |
|---|---|---|---|---|---|
| A | synthetic linear | 0.000（aligned） | NaN（退化） | 0.970 | ✅ |
| B | synthetic curved | 0.775（mismatch） | 0.990 | 0.970 | ✅ |
| C1 | real Sanger B1N1 | 0.000（aligned） | NaN（退化） | 0.910 | ✅ |
| C2 | real Sanger B2N | 0.000（aligned） | NaN（退化） | 0.861 | ✅ |

> **这条证据链直接导出本阶段的 regime axes**：Axis 1（alignment $D_L$）由"mean lever 是否有效"实证支撑；Axis 2（curvature $\beta\kappa$）由 H3-2 的"曲率导致 $x^*\neq x_L$"实证支撑；Axis 3（spread $R_\eta/\mathrm{tr}\Sigma_V$）由"covariance lever 全系统有效"实证支撑。

---

## 2. Research Question & 核心目标

### 2.1 Research Question（任务书原文）

> variance geometry 是否存在稳定 regime？

即：是否存在映射

$$
(system,\,q)\ \longrightarrow\ \text{geometry regime},
$$

使得不同 $(\text{system},q)$ 可以**归入有限个类别**，而不是每个 case 都是独立现象。

### 2.2 核心目标（任务书原文）

建立：

$$
(system,q)\ \longrightarrow\ \nu_V^{(q)}\ \longrightarrow\ \text{variance geometry regime}
$$

即研究**不同系统结构和 proposal 参数如何共同决定 variance geometry 类型**。

### 2.3 本阶段 NOT（任务书原文）

- ❌ 不是寻找最优 proposal；
- ❌ 不是直接优化 VRF；
- ❌ 不是进入 ML。

---

## 3. 理论：Regime Axes（regime 的坐标系统）

> **theory 部分**：以下三个 axis 的**定义**是数学/几何恒等式；"某 axis 是否控制某行为"是 hypothesis（§4）。

### 3.1 Axis 1 — Probability–Variance Geometry Alignment

**定义（theory，几何恒等式）**：

$$
D_L = \lVert x^* - x_L \rVert,
$$

其中 $x^*=\arg\min_{A}\lVert x\rVert$（MPP，probability geometry 代表点），$x_L=\arg\max_{A}\rho_V$（variance leakage point，variance geometry 代表点）。

**分类（两类，hypothesis）**：

| 类别 | 条件 | 已知例子 | 预测 |
|---|---|---|---|
| **aligned** | $D_L \approx 0$ | A, C1, C2（frozen $d_L=0$） | mean lever 退化（$m_\lambda\equiv x^*$） |
| **mismatch** | $D_L > 0$ | B（frozen $d_L=0.775$） | mean lever 激活 |

**理论依据**（H3-3B Theory Extension Sec. 4/5）：在 Gaussian proposal 下 $\rho_V\propto\mathcal N(\mu_V,\Sigma_V)|_A$（截断高斯）。$x^*$ 由 $\lVert x\rVert$ 决定，$x_L$ 由 $\lVert x-\mu_V\rVert_{\Sigma_V}$ 决定——二者分离发生在 curved boundary / $\beta\kappa\gtrsim1$ 体制。**该轴决定 mean lever 是否有效**（已由 multi-system 实证：mean lever 仅 B 有效）。

### 3.2 Axis 2 — Boundary Curvature

**定义（theory，几何控制量）**：使用 $\beta\kappa$（H3-2 的几何控制量），其中 $\beta$ 是标准化边界距离（design point 的 rarity），$\kappa$ 是边界曲率。

**依据（已实验）**：H3-2 / H3-3A 已观察到 curvature 可能导致 $x^*\neq x_L$（curved boundary $\beta\kappa\gtrsim1$ 体制）。本轴回答：

> 是否存在 aligned $\to$ mismatch 的**临界区域**（即 $D_L$ 作为 $\beta\kappa$ 的函数是否单调穿过 0）？

**关系（hypothesis）**：$D_L$ 应是 $\beta\kappa$ 的单调不减函数（curvature 越大分离越强）；但**临界点的确切位置、是否光滑、是否与 $d$ 相关，均待 Phase 1 验证**。

### 3.3 Axis 3 — Proposal Variance Spread

**定义（theory，几何恒等式）**：使用 $R_\eta$（variance-critical region 的加权扩散）或解析等价量 $\mathrm{tr}(\Sigma_V)$（variance-geometry 高斯核的迹）。

**分类（两类，hypothesis）**：

| 类别 | 条件 | 预测 |
|---|---|---|
| **compact** | $R_\eta$ small | proposal 窄（$s^2\to\tfrac12^+$）→ $\Sigma_V$ 大 → 截断高斯在 $A$ 内集中 |
| **diffuse** | $R_\eta$ large | proposal 宽（$s^2$ 大）→ $\Sigma_V\to\tfrac12 I$ → 区域弥散 |

**理论依据**（Theory Extension Sec. 4 注 4.3）：各向同性缩放 $\Sigma=s^2I$ 时 $\Sigma_V=\frac{I}{2-s^{-2}}$，$s^2\uparrow \Rightarrow \Sigma_V\downarrow$；$s^2\to\tfrac12^+ \Rightarrow \Sigma_V\to\infty$（合法性边界处摊平）。**该轴由 covariance lever 控制**（已由 multi-system 实证：cov lever 4/4 系统有效）。

---

## 4. 理论：Regime 定义（variance geometry 的四类形态）

> **本节的四类 regime 均为 hypothesis（任务书原文："以上为 hypothesis，不是已验证结论"）**。分类坐标 $(D_L, R_\eta)$ 是 theory；"某 $(D_L,R_\eta)$ 组合实际存在且表现出所列行为"是待验证假设。

### 4.1 分类坐标

$$
\text{Regime} = f(D_L,\ R_\eta),\qquad
D_L\in\{\text{aligned}\approx0,\ \text{mismatch}>0\},\quad
R_\eta\in\{\text{compact small},\ \text{diffuse large}\}.
$$

### 4.2 四类 Regime（hypothesis 表）

| Regime | 名称 | $D_L$ | $R_\eta$ | 预测（hypothesis） |
|---|---|---|---|---|
| **I** | Aligned Compact | $\approx 0$ | small | mean lever weak；covariance lever dominant |
| **II** | Aligned Diffuse | $\approx 0$ | large | mean lever weak；covariance strongly controls spread |
| **III** | Shifted Compact | $>0$ | small | mean lever activated；point mismatch visible |
| **IV** | Shifted Diffuse | $>0$ | large | both mean and covariance important |

### 4.3 与既有系统的对应（推测，非结论）

| system | $d_L$ frozen | $R_{0.8}$（multi-system） | 推测 regime | 备注 |
|---|---|---|---|---|
| A | 0.000 | 1.47–1.50 | I 或 II（aligned） | $R$ 中等，见 Phase 2 判定 |
| B | 0.775 | 1.30–1.32 | III 或 IV（shifted） | $R$ 中等，见 Phase 2 判定 |
| C1 | 0.000 | 1.63–1.71 | I 或 II（aligned） | $R$ 偏大 |
| C2 | 0.000 | 1.54–1.67 | I 或 II（aligned） | $R$ 偏大 |

> **诚实标注**：上表是**推测**，不是结论。四类 regime 是否全部可达、各系统落在哪一类、compact/diffuse 的 $R_\eta$ 阈值在何处——都是 Phase 2/3 必须回答的问题。特别地，**H3-3A 已证明在冻结协议下 `sharp-separated`（$D_{0.8}>0$）解析上不可达**；Regime III/IV 是否可达取决于 $\Sigma$ 杠杆能否触发区域级分离（Theory Extension Sec. 5 的开放问题）。

---

## 5. 理论：Regime 的解析预期（供实验对照）

> **theory 部分**：以下是在 Gaussian proposal + 忽略截断下的**解析预期**，作为实验的对照基准（不构成 regime 存在性的证明）。

### 5.1 Axis 1 的解析预期（$D_L$ vs $\beta\kappa$）

在 H3-2 的 curved boundary 一阶模型下，$D_L$ 由 $\lVert x^* - x_L \rVert$ 决定，而 $x_L=\arg\min_A\lVert x+\mu_V\rVert_{\Sigma_V}$（Theory Extension Sec. 4/5 注）。对 $\Sigma=I$、$q=\mathcal N(\mu,I)$ 的 frozen 特例，$x_L=\arg\min_A\lVert x+\mu\rVert$——**与 $x^*$ 的分离由边界曲率与 $\mu$ 方向共同决定**。**预期**：固定 proposal 下，$D_L$ 随 $\beta\kappa$ 单调不减。

### 5.2 Axis 3 的解析预期（$\Sigma\to R_\eta$）

对 $\Sigma=s^2I$：

$$
\Sigma_V = \frac{1}{2-s^{-2}}\,I,\qquad
\lim_{s^2\to\infty}\Sigma_V=\tfrac12 I,\qquad
\lim_{s^2\to\tfrac12^+}\Sigma_V=\infty.
$$

**预期**：$R_\eta$ 随 $s^2$ 单调下降（multi-system 已实证：4/4 系统 $\rho(R_\eta,s^2)\in[-0.97,-0.86]$）。

### 5.3 Regime 边界的解析期望（hypothesis）

- **aligned $\to$ mismatch 过渡**：$D_L=0$ 当且仅当 $\lVert x^*+\mu\rVert_{\Sigma_V}$ 与 $x^*$ 的几何重合（Theory Extension Sec. 5）；弯曲边界下临界 $\beta\kappa_c$ 可能满足 $\beta\kappa_c\sim O(1)$（H3-2 的 $\beta\kappa\gtrsim1$ 判据）。
- **compact $\to$ diffuse 过渡**：$R_\eta$ 相对 $A$ 的特征尺度（H3-3A 的 $\chi^2_d(\eta)^{1/2}=2.45$ at $d=4,\eta=0.8$）决定——$R_\eta\ll 2.45$ 为 compact，$R_\eta\gtrsim 2.45$ 为 diffuse（**阈值待实验标定，不预设**）。

---

## 6. 实验规划（Experiment Plan）

> **experiment 部分**：以下为执行计划。**不包含任何结果**。

### 6.0 全局约束

- 复用 frozen H3-2 pipeline（read-only）：`label_linear`/`label_curved`、real 动力学（workers=4）、ML-B1 anchors、seeds $\{1,2120,3,4\}$。
- 不修改任何 frozen artifact（H3-2 dataset SHA-256 `29e09cb6…` 保持）。
- 每个 config 保存完整 metrics（§7）。
- **不直接扫描全参数组合**——严格沿 regime axis 设计最小实验。

---

### 6.1 Phase 1 — Curvature Transition Scan（Axis 1 + Axis 2 联合）

**目标**：验证 $\beta\kappa$ 是否控制 $D_L$；定位 aligned $\to$ mismatch 过渡。

**设计**（任务书 §Phase 1）：

| 项 | 设定 |
|---|---|
| 扫描量 | $\beta\kappa$（通过改变 curved boundary 的曲率/位置实现） |
| 固定 | proposal（如 $q=\mathcal N(x^*, I)$，即 $\Sigma=I$、$m=x^*$） |
| 记录 | $x^*, x_L, D_L, \mathcal L_\eta$（$\eta=0.8$ 主；$\eta\in\{0.5,0.9\}$ 敏感性） |
| 系统 | Synthetic curved testbed（B 的推广：参数化 boundary 曲率） |
| 输出 | aligned $\to$ mismatch transition 曲线（Figure A） |

**注意**：$\beta\kappa$ 的扫描**必须保持 proposal 固定**（任务书要求），且扫描格点要覆盖 $D_L=0$ 两侧（aligned 区 + mismatch 区 + 临界附近加密）。

**成功标准（hypothesis 检验）**：$D_L(\beta\kappa)$ 单调、存在临界 $\beta\kappa_c$ 使 $D_L$ 穿过 0。

---

### 6.2 Phase 2 — Proposal Covariance Map（Axis 3）

**目标**：建立 $\Sigma \to$ variance spread 的映射（固定系统内）。

**设计**（任务书 §Phase 2）：

| 项 | 设定 |
|---|---|
| 固定 | system（逐系统做） |
| 扫描 | $\Sigma = s^2 I$，$s^2 \in [0.75, 2]$（如 $\{0.75, 1, 1.5, 2\}$，与 multi-system validation 一致） |
| 记录 | $R_\eta, G_\eta, \mathrm{VRF}$ |
| 合法性 | $\Sigma\succ\tfrac12 I$（$s^2\le0.5$ 记录 invalid 不运行） |
| 系统 | 4 systems（A/B/C1/C2），与 multi-system validation 相同的 protocol |

**输出**：$\Sigma \to R_\eta$ 曲线（Figure B），compact/diffuse 阈值标定。

---

### 6.3 Phase 3 — Joint Regime Map（三 axis 合成）

**目标**：形成 variance geometry regime map。

**设计**（任务书 §Phase 3）：

| 项 | 设定 |
|---|---|
| X-axis | $D_L$ |
| Y-axis | $R_\eta$ |
| color | $G_\eta$ 或 $\mathrm{VRF}$ |
| 数据来源 | Phase 1（不同 $\beta\kappa$ 给出不同 $D_L$）+ Phase 2（不同 $s^2$ 给出不同 $R_\eta$） |
| 输出 | 二维 regime map（Figure C），四类 regime 区域标注 |

**关键设计**：**Phase 3 不做新的大规模扫描**——它聚合 Phase 1/2 的数据点（不同 $(\beta\kappa, s^2)$ 组合自然覆盖 $(D_L, R_\eta)$ 平面）。若覆盖不足，再补充少量格点（不扩大搜索）。

---

## 7. Metrics（每个 configuration 全量保存）

### 7.1 Geometry

- $D_L = \lVert x^* - x_L \rVert$（Axis 1）
- $C_\eta = \lVert m_\eta - x^* \rVert$（region center shift）
- $R_\eta$（region spread，Axis 3）
- $G_\eta = C_\eta/(R_\eta+\epsilon)$（normalized mismatch）
- 附：$D_\eta$（H3-3A 兼容）、$m_\eta$、$c_\eta/\rho_{\max}$、align

### 7.2 Proposal

- $m$, $\Sigma$（合法性 $\Sigma\succ\tfrac12 I$）

### 7.3 Performance

- $\mathrm{VRF}$（var_MC/var_IS）
- $\mathrm{ESS}$
- $M_2 = \int_A p^2/q\,dx$（估计）

---

## 8. 预期 Figures

### Figure A — Geometry alignment transition

展示 $\beta\kappa \to D_L$（Phase 1 输出）：x 轴 $\beta\kappa$，y 轴 $D_L$；标注 aligned/mismatch 分界与临界点 $\beta\kappa_c$（若存在）。

### Figure B — Variance spread map

展示 $\Sigma \to R_\eta$（Phase 2 输出）：x 轴 $s^2$，y 轴 $R_\eta$；4 systems 叠加（Synthetic A/B + Real C1/C2），标注合法性边界 $\Sigma\succ\tfrac12 I$。

### Figure C — Full variance geometry regime map

展示 $(D_L, R_\eta) \to$ regime（Phase 3 输出）：x 轴 $D_L$，y 轴 $R_\eta$，color = $G_\eta$（或 VRF）；四类 regime 区域（I–IV）标注；数据点按系统着色。

---

## 9. Validation Gates

### Gate 1 — Regime separation

**要求**：不同 regime 的 geometry descriptor 有明显差异。

**检验**：Phase 3 map 中，四类 regime 区域在 $(D_L, R_\eta)$ 平面上**分离**（无重叠模糊区），且各区域内的 $G_\eta$/VRF 分布统计可分。

### Gate 2 — Cross-system consistency

**要求**：Synthetic → Real 保持趋势。

**检验**：Phase 2 中 $R_\eta(s^2)$ 曲线方向 4/4 系统一致（multi-system validation 已显示 $\rho(R_\eta,s^2)\in[-0.97,-0.86]$ 全同向）；Phase 3 map 中真实系统点落在 synthetic 系统确立的 regime 区域内（而非离群）。

### Gate 3 — Predictive usefulness

**要求**：regime descriptor 与 VRF / leakage 行为存在关联。

**检验**：$G_\eta$（或 $R_\eta$）与 VRF 的相关性（Pearson + Spearman）。**只报告相关，不声称因果**（任务书原文）。

---

## 10. Claim Boundary

### 本阶段禁止声明（任务书原文，逐条遵守）

- ❌ 找到了全局最优 proposal；
- ❌ variance geometry 已完全分类；
- ❌ 已解决 adaptive IS；
- ❌ 已完成 ML。

### 本阶段允许声明

> 建立 $(system,q) \to$ variance geometry regime 的**实验框架**（axes / regime 定义 / 实验规划 / Gates）。

**附加边界**（沿 H3 corpus 一致性）：
- ❌ 不恢复真机 C1 旧 $d_L=1.136$（采样伪影，C1 audit 判定）。
- ❌ 不声称四类 regime 全部可达（III/IV 是否可达待 Phase 2/3 回答）。
- ❌ 不声称 regime 边界精确位置（compact/diffuse 阈值、$\beta\kappa_c$ 均待标定）。
- ❌ 不提前写任何 Phase 1–3 实验结果（本文档是 plan，不是 report）。

---

## 11. 与 H3-3B 前序阶段接口

| 接口 | 来源 | 本阶段使用 |
|---|---|---|
| 闭式 $\mu_V,\Sigma_V$ | H3_3B_Theory_Extension Sec. 4 | Axis 3 解析预期（§5.2） |
| 合法性 $\Sigma\succ\tfrac12 I$ | 同上 Sec. 3 | Phase 2 合法性检查 |
| region estimator（$C_\eta,R_\eta,G_\eta$） | H3_3B_synthetic_pilot_report §2.5 | Metrics 定义（§7） |
| Gate A/B/C 定义 | H3_3B_multi_system_validation_report §2.5 | 本阶段 Gate 1/2/3 的直接依据 |
| 4 system frozen anchors | multi-system validation | Phase 2/3 系统选择 |

**本阶段不重复执行已完成的实验**：multi-system validation 的 4 systems × 11 config 数据（`h3_3b_multi_system_validation_v1.json`）可直接作为 Phase 2 的部分数据点复用（proposal cov sweep 已覆盖 $s^2\in\{0.75,1,1.5,2\}$），Phase 3 可聚合之。

---

## 12. 建议执行顺序与风险

### 执行顺序

1. **Phase 1**（Curvature Transition Scan）：先验证 Axis 1/2 的联动——这是最不确定的部分（$D_L(\beta\kappa)$ 是否单调、临界是否存在均未知）。
2. **Phase 2**（Proposal Covariance Map）：风险最低（multi-system 已实证 cov lever），主要用于标定 compact/diffuse 阈值。
3. **Phase 3**（Joint Regime Map）：聚合 Phase 1/2，判定四类 regime 是否分离。

### 主要风险（诚实标注）

- **R1**：$D_L(\beta\kappa)$ 可能不单调或临界不存在（若 aligned $\to$ mismatch 是突变而非连续过渡，map 会退化）。
- **R2**：Regime III/IV（shifted）可能不可达（H3-3A 已证明冻结协议下 sharp-separated 解析上不可达；$\Sigma$ 杠杆能否触发待验证）。
- **R3**：compact/diffuse 阈值可能因系统而异（无全局阈值）→ Gate 1 部分失败。
- **R4**：真实系统点可能不落入 synthetic 确立的 regime（Gate 2 部分失败）→ 需调整 axis 定义或接受"regime 仅在 synthetic 内成立"的弱结论。

**失败预案**：若 Gate 1/2 部分失败，如实报告 regime map 的**适用范围**（如"仅 mismatch 体制内 regime 分离成立"），不强行调阈值（H3 corpus 一贯的诚实原则）。

---

## 13. 一句话总结

> **H3-3B Regime Map 阶段的设计文档：以 alignment $D_L$（Axis 1）、curvature $\beta\kappa$（Axis 2）、spread $R_\eta/\mathrm{tr}\Sigma_V$（Axis 3）为坐标，定义四类 variance geometry regime（Aligned/Shifted × Compact/Diffuse，均为 hypothesis）；规划三个最小实验（Phase 1 curvature transition scan → Phase 2 proposal covariance map → Phase 3 joint regime map）；设定三个验证 Gate（regime separation / cross-system consistency / predictive usefulness）；严格保持 claim boundary——只建立实验框架，不提前写结果、不扫描全参数、不声称因果。**

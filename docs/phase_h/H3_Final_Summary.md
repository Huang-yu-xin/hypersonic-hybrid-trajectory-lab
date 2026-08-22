# RareTopo H3 — Final Summary（H3-3B 前状态冻结文档）

> 项目：**RareTopo** — Rare Topology Transition Estimation in Hybrid Dynamical Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab` · 分支：`feature/phase-h-uncertainty-risk`
> 论文主线：ICML 2027 方法论文
> 仓库目标路径：`docs/phase_h/H3_Final_Summary.md`
> **状态：H3-3A COMPLETE / H3 Core Theory + H3-3A Frozen（2026-08-21；H3-3B 未开始）**
> 冻结链：H2R ACCEPTED · ML-B1 COMPLETE(`78ecfb8`) · H3-0 FROZEN(`127ce0c`) ·
> H3-1 COMPLETE(`319d9c6`) · H3 Theory Consolidation/Audit COMPLETE ·
> H3-2 FROZEN(`a03b364 → fa7c476`, dataset SHA-256 `29e09cb6…`) ·
> H3-2 C1 Stability Audit COMPLETE(Case A) · **H3-3A COMPLETE**
> 本文用途：H3 理论演化总结 + 实验结果总览 + claim boundary 管理 + **H3-3B 开始前唯一状态入口**

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

**结论先行。** 这份文档**不是论文正文**，而是 H3 阶段的**状态冻结与 claim 边界管理**文件。它的唯一职责是：让任何人（包括未来的自己）在开始 H3-3B 之前，用一份文件就能准确知道——**H3 到今天证明了什么、观测到了什么、只是假设什么、以及哪些旧结论已被审计推翻不得恢复**。

三条硬约束贯穿全文：

1. **区分层级**：已证（数学恒等式 / 定理）、实验证实（且注明作用域：2-D 合成 / 真机 Sanger）、未来假设——三者分开措辞，不混用。
2. **不恢复被推翻的旧结论**：早期声称的真机 C1 泄漏点分离 $d_L=1.136$ 已由 stability audit 判定为**采样伪影**（§5 单独章节），本文不以任何形式恢复它。
3. **出处可核**：凡外推、无出处、或本窗口不可验证的内容，在 §9 明确标注（含一处重要的 $\Xi^{(2)}$ 出处更正）。

**H3 一句话现状**：Geometry-IS「是否降方差」早已由方差定理关闭（`RV_geom=Θ(β)` vs `RV_MC=Θ(βe^{β²/2})`）；H3 研究的是**这种降方差在真实 hybrid 拓扑系统中何时保留**。答案的骨架已经清晰——失效由**未覆盖拓扑模态的 variance leakage** 主导，而非局部几何误差 $\varepsilon_{geo}$；控制方差的几何对象（variance geometry）与控制概率的几何对象（probability geometry）不是同一个东西；而这个方差几何对象**在部分体制下不是稳定的单点，而是一个稳定的区域**。这就是从 H3-0 到 H3-3A 的完整演化。

---

## 1. H3 理论演化（Stage 1 → Stage 6）

H3 的科学内容是一条演化链，每一步都在修正上一步的对象定义。下面严格按此顺序展开；每个 stage 只声称该阶段文档支持的结论。

### Stage 1 — H3-0：Baseline observation

**问题**：Geometry-IS 为什么*可能*失效？

H3-0 冻结了研究对象与诊断口径，为后续所有实验提供不可移动的地基：

- 稀有事件 $A=\{Z\neq Z_0\}$，拓扑标签 $Z=T(X_0)$ 由**真实 hybrid simulator 的事件执行/跳过**判定，编码 `SRTI_N{k}`（$k=$ skip_count）；事件判定**必须用 exact simulator，禁止用 `sign(b)` 代理**。
- 分级 benchmark L0–L3（near-linear / moderate hybrid / grazing / multi-channel），冻结两个诊断量：几何精度 $\varepsilon_{geo}=\lVert g-\hat g\rVert$、方向精度 $\Delta_d=1-\cos$。
- 直接 MC 的相对方差 $RV_{MC}=(1-p)/p=\Theta(\beta e^{\beta^2/2})$ 在 $p\in[10^{-4},10^{-6}]$ 随 rarity 指数爆炸——**这就是「为什么必须 IS」**。

H3-0 只提出问题、不给答案：三种偏离理想（曲率 $R\neq0$、多模态竞争、事件切换 kink）里，究竟哪一个杀死 Geometry-IS，必须靠 benchmark 回答，不能先验断定。

### Stage 2 — H3-1：Variance leakage discovery

**核心发现（可证 + 实验证实）**：**失效的「概率质量」不等于「方差贡献」。**

$$
\boxed{\,P_k \neq M_k\,}\qquad\text{（低概率拓扑模态可以主导 estimator variance）}
$$

H3-1 把 IS 二阶矩沿互斥模态划分 $A=\sqcup_k A_k$ 展开，得到一条**精确恒等式**（非近似、与是否 Gaussian 无关）：

$$
M_2=\sum_k L_k,\qquad L_k=\int_{A_k}\frac{p^2(x)}{q(x)}\,dx=\mathbb E_p\!\Big[\tfrac{p}{q}\,;A_k\Big],\qquad
\operatorname{Var}_q(\widehat P)=\tfrac1N\Big(\textstyle\sum_k L_k-(\sum_k P_k)^2\Big).
$$

$L_k$ 是模态 $k$ 的质量再乘 **IS 权重 $p/q$**：提议在某模态覆盖不足（$q\ll p$）时 $L_k$ 被放大，与 $P_k$ 严重脱钩。

**H3-1 真机+合成 6-config benchmark 的实测结论**（frozen dataset `h3_variance_leakage_dataset_v1.json`）：

| 观测 | 数值（H3-1 frozen） | 含义 |
|---|---|---|
| Synthetic multi-mode 次模态概率 | $P_{S2}=0.00575\ll P_{S1}=0.0653$（×11） | 次模态极稀有 |
| 同一次模态泄漏 | $\mathrm{leak}_{S2}=1.22\gg\mathrm{leak}_{S1}=0.0128$（×95） | 却主导二阶矩 |
| $\mathrm{leak\_fraction}_{S2}$ | **0.99** | 99% 方差来自 0.6% 概率的未覆盖模态 |
| 该 config VRF | **0.54 < 1** | IS 比 MC 更差 |
| $\mathrm{corr}(\mathrm{leak},\mathrm{VRF})$ | Pearson **−0.459** / Spearman **−1.000** | 泄漏与失效强相关（完美单调） |
| $\mathrm{corr}(\varepsilon_{geo},\mathrm{VRF})$ | Pearson −0.267 / Spearman −0.232 | 几何误差相关性弱 |

两条附带发现，均对后续阶段重要：
- **Silent leakage**：$S_2$ 的解析真值 $\mathrm{leak}=1.505$，IS 估计仅 $1.221$（20 万样本里仅 5 个落入 $A_2$）——$N$ 一小就彻底测不到（$n_{events}\to0$）。
- **ESS 掩盖失效**：该 config ESS $=21440$（看似健康）但 VRF $=0.54$——全样本 ESS 被被覆盖的主模态主导，对 secondary-mode leakage 不敏感，**不能**作为 coverage 健康度指标。

> H3-1 边界：leakage **主导** $\varepsilon_{geo}$/曲率这一点，在 v1 alpha 选择下真机 configs 全部落在最近相邻单模态（覆盖充分，VRF 1.4–2.1），多模态竞争机制由 synthetic multi-mode 精确演示——真机 multi-mode 观测留待后续。

### Stage 3 — H3 Theory：Probability geometry vs Variance geometry

H3 理论审计把「失效机制」升华为一句几何陈述：

> **Geometry-IS 优化的是 probability geometry，但 variance 由另一种几何控制。**

对稀有事件 $A$，两个几何对象**不同**：

$$
\underbrace{x^{*}=\arg\min_{x\in A}\lVert x\rVert}_{\text{probability design point (MPP)，控制 }P_f}
\qquad\text{vs}\qquad
\underbrace{x_L=\arg\max_{x\in A}\rho_L(x)}_{\text{variance leakage point，控制 }M_2},\quad
\rho_L(x)=\frac{\varphi(x)^2}{q(x)}.
$$

对 $\varphi=\mathcal N(0,I)$、$q=\mathcal N(\mu,I)$，配方给出**闭式**（这是整个框架的枢纽）：

$$
\frac{p(x)^2}{q(x)}=e^{\lVert\mu\rVert^2}\,\mathcal N(x;-\mu,I)
\;\Longrightarrow\;
x_L=\arg\min_{x\in A}\lVert x+\mu\rVert.
$$

即：**方差积分是一个以「镜像点」$-\mu$ 为中心的高斯在 $A$ 上的积分**。据此得到 mode-level 泄漏的解析形式 $L_k=e^{\lVert\mu\rVert^2}\Phi(-(\beta_k+a_k^{\mathsf T}\mu))$——单 design point 位移 $\mu=\beta a_1$ 只让被对准的模态吃到 $-2\beta$ 折扣（$L_1=e^{\beta^2}\Phi(-2\beta)$），正交模态**无折扣**（$L_k=e^{\beta^2}\Phi(-\beta_k)$），却照付整体倾斜代价 $e^{\lVert\mu\rVert^2}$。**这就是「单 design point 只覆盖一个拓扑模态」的几何根源。**

**可证的反直觉算例**（已数值核验）：$\beta=3,\beta_2=4.75$ 时

$$
\frac{P_2}{P_1}\approx 7.5\times10^{-4}\quad\text{但}\quad
\frac{L_2}{L_1}\approx 1031,\quad
\mathrm{leak\_fraction}_2=99.9\%.
$$

0.075% 的失效质量，贡献 99.9% 的二阶矩——**只看 $P_k$ 会把它当可忽略**。

**2-D 合成 prototype 的机制分离证据**（Theory Consolidation §X.4，220 随机 hybrids）：沿 multi-topology 轴 VRF 从 214 崩到 0，而 $\varepsilon_{geo}\equiv0$ 全程不变——**线性化误差在原理上无法解释这次崩溃**；kink 轴 VRF 纹丝不动。泄漏预测子与 VRF 的 Spearman $=0.81$，而 mass-coverage $0.43$、$\varepsilon_{geo}$ $0.04$ 都不行；**不存在把 valid/invalid 分开的几何误差阈值 $\varepsilon_c$**。

> ⚠️ **Stage 3 claim 边界（务必守住）**：
> **不要**写「所有 hybrid 系统都满足 $x^{*}\neq x_L$」。
> **正确表述**：$x^{*}\neq x_L$ 的分离**在 leakage-dominated / 弯曲边界（$\beta\kappa\gtrsim1$、顶点偏移）体制中可能出现**；线性/凸边界下二者数学重合。分解 $M_2=\sum_k L_k$ 本身永远精确；每个 $L_k$ 的**取值**在弯曲真机边界下只是一阶近似。

### Stage 4 — H3-2：Adaptive Geometry-IS

H3-2 把「换几何对象」做成方法并做消融，对比三种 proposal：

| 方法 | Proposal | 检验的问题 |
|---|---|---|
| **M1** single Geometry-IS | $q=\mathcal N(x^{*},I)$ | 概率几何 baseline |
| **M2** topology-aware mixture | $q=\sum_k\pi_k\mathcal N(x_k^{*},I)$ | 「知道拓扑分解」是否足够？ |
| **M3** leakage-point adaptive | $q=\sum_k\pi_k\mathcal N(x_{L,k},I)$ | 方差几何是否是缺失因素？ |

权重策略：$\pi_k\propto P_k$（probability）、$\pi_k\propto L_k^\alpha$（leak_power）、$\pi_k\propto P_k^\gamma L_k^{1-\gamma}$（p05_l05）。

**结果（frozen dataset SHA-256 `29e09cb6…`）**：

| 实验 | kind | n modes | M1 VRF | M2 VRF | M3[prob] VRF | leak 削减 | max $\lVert x^{*}-x_L\rVert$ |
|---|---|---|---|---|---|---|---|
| A 线性多模 | synthetic | 2 | **0.463** | 26.0 | **26.1** | 97.3% | 0（重合） |
| B 弯曲 stress | synthetic | 2 | **0.098** | 14.4 | 12.1 | 98.9% | **0.775** |
| C1 Sanger B1N1（$\alpha=8\lvert\beta\rvert$） | real | 1 | 1.21 | 1.36 | 1.26 | 8.8% | 0（**详见 §5**） |
| C2 Sanger B2N（$\alpha=8\lvert\beta\rvert$） | real | 1 | 1.23 | 0.76 | **1.52** | 14.2% | 0 |

H3-2 的两条实验结论：

1. **Synthetic curved（Exp B）证明 mismatch 可以存在**：$x_L=(1.77,0.26)$ 与 $x^{*}=(1.23,0.83)$ 分离 $0.775$（顶点偏移边界、silent secondary mode，有解析支撑）。M1 因 $S_2$ silent leakage 深度失败（0.098）→ M2/M3 恢复 VRF ≫ 1。
2. **Real C2 证明 leakage-aware proposal 有实际收益**：$x_L$ 中心 mixture（M3[prob] $=1.52$）显著优于 MPP 中心 mixture（M2 $=0.76$，反而劣于 baseline 1.23）且为最优——**样本估计的 MPP 位置不携带方差信息，泄漏点位置携带**。

**关键权重实证**（一阶 vs 主导量）：一旦 mixture 覆盖所有 modes，**权重平衡比精确位置更关键**——$\pi\propto L_k$ 过度偏斜（mass 全给最 leaky mode）反而有害（VRF 崩到 0.16–0.47）；$\pi\propto P_k$ 与 $p05\_l05$ 平衡最优。位置差异（M2 vs M3）是一阶量，权重是主导量。

> H3-2 的**统一视角更新**（被本阶段采纳、与后续一致）：曲率**不是**独立失效通道，而是通过 $x^{*}\neq x_L$ 进入 unified leakage 框架（$\beta\kappa>1$ 时 probability design point 不再代表 variance-optimal 位置）。这修正了 Theory Consolidation 早期「grazing 作为独立二阶通道」的措辞。

H3-2 的真机局限（催生 C1 audit 与 H3-3A）：$\alpha=8\lvert\beta\rvert$ 下事件不 rare（$P\sim0.45\text{–}0.54$），IS 增益天然有限（VRF ~1.2–1.5）；两 config 均单模态，真机 multi-mode 未出现。

### Stage 5 — C1 Stability Audit（单独章节，见下 §5）

H3-2 freeze 前的一个种子敏感问题触发了对真机 C1 分离性的专项审计。**结论是负向的、且必须单独记录**——见 §5。一句话：**旧 $d_L=1.136$ 是采样伪影，真机 C1 不支持稳定的 $x^{*}\neq x_L$；single leakage point 不是总是可靠的研究对象。**

### Stage 6 — H3-3A：Set-Valued Variance Geometry（H3 最新核心）

C1 audit 暴露的问题是：**单点 $x_L$ 在 $\rho_L$ 平坦景观上由有限样本 argmin 竞争决定，会漂移**。H3-3A 由此做出 H3 迄今最重要的**对象升级**：

$$
\boxed{\text{研究对象：}\ x_L\ \text{（单点）}\ \longrightarrow\ \mathcal L_\eta\ \text{（variance-critical high-contribution region / HDR，区域）}}
$$

**核心问题**：当单点 $x_L$ 因平坦景观不稳定时，**variance geometry 本身是否仍可被一个稳定的区域表示？**

集合值定义（沿用 §3 枢纽闭式，不重新定义 $\rho_L$）：

$$
\nu_V(dx)=\frac{\rho_L(x)}{M_2}\,dx,\qquad
\mathcal L_\eta=\{x\in A:\rho_L(x)\ge c_\eta\}\ \ \text{s.t.}\ \ \nu_V(\mathcal L_\eta)\ge\eta,
$$

区域指标：分离 $D_\eta=\mathrm{dist}(x^{*},\mathcal L_\eta)$、质心 $m_\eta$、扩散 $R_\eta=\sqrt{\mathbb E_{\nu_V}[\lVert X-m_\eta\rVert^2\mid X\in\mathcal L_\eta]}$、分离扩散比 $S_\eta=D_\eta/(R_\eta+\varepsilon)$。主分析 $\eta=0.8$，敏感性 $\eta\in\{0.5,0.8,0.9\}$（禁止按结果调）。

**解析发现（冻结 $q$ 协议 $\Sigma_k=I$ 的直接结果）**：

$$
\rho_L(z)\propto\exp(-\lVert z+\mu\rVert^2/2)\;\Longrightarrow\;\nu_V=\mathcal N(-\mu,I).
$$

即 variance-tilted 测度不是「尖锐」的东西，而是**以镜像点 $-\mu$ 为中心的高斯团**；HDR 区域是一族球与 mode 边界的交集。这与 Stage 3 的枢纽闭式和 paper 的镜像点框架完全同源。

**核心实验结论（4 case，4 seeds × {N,4N,16N} 前缀，数字与 pilot JSON 逐位核验）**：

$$
\boxed{\text{point estimator }d_L\ \text{unstable}\quad\text{but}\quad\text{regional variance geometry stable}}
$$

| case | $d_L$ range（点估计） | $D_{0.8}$ | $R_{0.8}$ mean（MAD / range） | 区域相对点稳定增益 |
|---|---|---|---|---|
| B S2（synthetic 弯曲，正控） | 0.482 | ≡ 0 | 1.300（0.033 / 0.151） | ~3× |
| A S1（synthetic 线性，对照） | 0.104 | ≡ 0 | 1.504（0.002 / 0.004） | ~26× |
| **C1（real Sanger，plateau）** | **0.600** | **≡ 0（12/12）** | **1.509（0.009 / 0.132）** | **~4.5×** |
| C2（real Sanger，aligned 对照） | 0.631 | ≡ 0（12/12） | 1.537（0.017 / 0.185） | ~3.4× |

- 点估计 $d_L$ 在真机上极不稳定：C1 的 12 个值 $\{0.318,0.448,0,0,0,0.472,0,0,0.6,0,0,0\}$，range $0.600$；**N=2048 反而出现最大尖峰**（与 C1 audit 的「$d_L$ 不随 $N$ 单调收敛」一致）。
- **区域几何免疫**：$D_{0.8}$ 在 C1/C2 全部 24 rows 恒为 0，$R_{0.8}$ 稳定在 $1.5\pm0.02$——同一份不稳定样本，点漂移而区域形状不变。

**Fig 10（sharp peak vs diffuse plateau）**：B（synthetic 弯曲）的 $\rho_L$ 区域是**有向、集中的月牙**（$c/\rho_{max}$ 较高、align $=0.82$，质心明显偏向 $x_L$ 方向）；C1（真机）是**弥散的圆形 plateau**（align $=0.24$、$\rho_L$ 量级更低）——两者 $D_{0.8}$ 都 $=0$（MPP 落在 80% 区域内），但区域**形状/朝向**清楚区分了「几何真实的弯曲分离」与「平坦景观」。

**Fig 11（point vs set-valued 稳定性）**：合成 A/B 与真机 C1/C2 一致地显示——箱线图里 $d_L$（点）跨 seed×N 大幅跳动（真机 whisker 到 0.6），而 $D_{0.8}$（MAD $=0$）与 $R_{0.8}$（MAD 0.009/0.017）几乎不动。

**Gate 评估（诚实记录，不挑阈值）**：
- **Gate A（synthetic B，严格判据 $D_{0.8}>0$）：未通过。** mean $D_{0.8}=0$。机理：$\nu_V\propto\mathcal N(-\mu,I)$ 的 80% 质量球半径 $\chi^2_4(0.8)^{1/2}=2.45$，而 B·S2 中 $\lVert x^{*}+\mu\rVert\approx0.87\ll2.45$，**MPP 必然落在 80% 区域内**——$D_{0.8}>0$ 在此 pilot 配比（unit $\Sigma$、$q=\mathcal N(\mu,I)$）下**解析上不可能**，需 $\eta\lesssim0.05$ 或 $q$ 移向 $\mathcal L_\eta$（即 M3 mixture）才能让 HDR 排除 MPP。注意 mean align $=0.68$（3/4 seed $>0.5$），方向上与 frozen $d_L\approx0.775$ 定性一致。
- **Gate B（C1 区域显著更稳定且 $D\approx0$、$R$ 大）：通过 ✅**（12/12 rows）。
- **Gate C（跨 $\eta$ regime 判据一致）：通过 ✅**（**40/40 rows** per-row 一致）。

> H3-3A 边界：本 pilot 所有 case 在 $\eta\ge0.5$ 下都进入 `overlap-diffuse`/`aligned-diffuse`；**`sharp-separated` 体制在当前 $\nu_V$ 高斯团几何下解析上不可达**——如实报告，不声称其存在。

---

## 2. 实验结果总览（跨阶段对照）

| 阶段 | 对象 | 关键量 | 主结果 | 作用域 |
|---|---|---|---|---|
| H3-1 | $L_k$、leak_fraction | corr(leak,VRF) | Spearman **−1.0**（vs $\varepsilon_{geo}$ −0.23）；synthetic $S_2$ leak_frac 0.99 → VRF 0.54 | 真机单模 + 1 synthetic multi-mode |
| H3 Theory | $x^{*}$ vs $x_L$；$M_2=\sum_k L_k$ | mass≠var | $P_2/P_1=7.5\text{e-}4$ 但 $L_2/L_1=1031$（可证）；prototype 220 系统 leak-Spearman 0.81 | 数学恒等式 + 2-D prototype |
| H3-2 | M1/M2/M3 + 权重 | VRF、$\lVert x^{*}-x_L\rVert$ | synthetic 0.10/0.46 → 12–26（leak 削减 97–99%）；real C2 M3=1.52 最优；curved 分离 0.775 | synthetic + 真机 Sanger（不 rare、单模） |
| C1 Audit | 真机 C1 $d_L$ 稳定性 | 多 seed / 多 N $d_L$ | 4 seed 中 3 个 $d_L=0$；旧 1.136 不可复现（最大观测 0.472）；landscape 平坦 gap 1.01–1.21 | 真机 C1（Case A） |
| H3-3A | $\mathcal L_\eta$（区域） | $d_L$ range vs $R_\eta$ range | C1 $d_L$ range 0.60 vs $R_{0.8}$ range 0.13（~4.5×）；$D_{0.8}\equiv0$；Gate B/C 通过 | 4 case（d=4 standardized） |

---

## 3. 统一数学框架（Final Mathematical Picture）

H3 到今天可以用**两个测度**统一表述。设稀有事件 $A$、目标密度 $p=\varphi$、提议 $q$：

**概率几何（probability geometry）** $\nu_P$：由 $\min\lVert x\rVert$ 支配，其代表点是 MPP $x^{*}$，控制失效概率 $P_f$。

**方差几何（variance geometry）** $\nu_V$：控制估计量二阶矩，定义为

$$
\boxed{\;\nu_V(dx)\ \propto\ \mathbf 1_A(x)\,\frac{p(x)^2}{q(x)}\,dx\;},\qquad
M_2=\int_A\frac{p^2}{q}\,dx=\int\nu_V(dx)\ \text{（未归一）}.
$$

在冻结 Gaussian 协议（$p=\mathcal N(0,I),\ q=\mathcal N(\mu,I),\ \Sigma=I$）下，$\nu_V\propto\mathcal N(-\mu,I)$ 在 $A$ 上的限制——**以镜像点 $-\mu$ 为中心**。其上的三个几何对象层层递进：

$$
\underbrace{x_L=\arg\max_A\rho_L=\arg\min_A\lVert x+\mu\rVert}_{\text{点（H3-2，}\rho_L\text{ 平坦时不稳定）}}
\ \longrightarrow\
\underbrace{\mathcal L_\eta=\{\rho_L\ge c_\eta\},\ m_\eta,\ R_\eta}_{\text{区域（H3-3A，稳定）}}.
$$

**框架的关键一句话**：

$$
\boxed{\ \text{variance geometry 是一个分布 / 区域对象 }\nu_V\text{，不是永远是单个点。}\ }
$$

- 当 $\nu_V$ 在 $A$ 内呈**尖锐单峰**（弯曲边界、$\beta\kappa\gtrsim1$）：单点 $x_L$ 有意义且与 $x^{*}$ 分离（synthetic Exp B，$d_L=0.775$ 稳定）。
- 当 $\nu_V$ 在 $A$ 内呈**平坦 plateau**（真机 C1，不 rare、近凸宽峰）：单点 $x_L$ 由采样噪声决定、不稳定（$d_L$ range 0.6），但**区域参数 $m_\eta,R_\eta,c_\eta$ 稳定**（$R_{0.8}$ range 0.13）。

概率几何 $\nu_P$ 与方差几何 $\nu_V$ 是**不同对象**——Geometry-IS 枚举前者、对后者结构性失明，这一句就是失效机制；而 $\nu_V$ 的稳定表示形式是**区域**而非点，这是 H3-3A 的贡献。

> 出处衔接：镜像点 $-\mu$ 与闭式 $p^2/q=e^{\lVert\mu\rVert^2}\mathcal N(x;-\mu,I)$ 在 Theory Consolidation（§Part 5 / §X）与 paper Section X.5.1（X.9/X.10）中一致；H3-3A 由同一闭式解析导出 $\nu_V=\mathcal N(-\mu,I)$ 并核验。

---

## 4. 当前已验证 claims（Currently Supported）

> 下列为 H3 已被证明或实验证实的结论；每条注明层级与作用域。

1. **概率几何与方差几何是不同对象。**
   *已证（Gaussian 闭式）+ 实验证实（synthetic Exp B $d_L=0.775$，有解析支撑）。* 数学：$x^{*}=\arg\min_A\lVert x\rVert$ vs $x_L=\arg\min_A\lVert x+\mu\rVert$。

2. **Variance leakage 可以导致 Geometry-IS failure。**
   *恒等式已证（$M_2=\sum_k L_k$）；失效实验证实（H3-1 synthetic $S_2$：leak_frac 0.99 → VRF 0.54 < 1；H3-2 Exp A/B：M1 VRF 0.10–0.46）。* 泄漏而非 $\varepsilon_{geo}$ 主导：H3-1 corr Spearman −1.0 vs −0.23。

3. **单点 leakage point 在部分 regime 中不稳定。**
   *实验证实（C1 audit + H3-3A）。* 真机 C1：4 seed 中 3 个 $d_L=0$、$d_L$ 不随 $N$ 单调、landscape 平坦（gap 1.01–1.21）；旧 $d_L=1.136$ 为采样伪影。

4. **Regional variance geometry 比 point estimator 更稳定。**
   *实验证实（H3-3A，4 case 全部）。* C1 $d_L$ range 0.60 vs $R_{0.8}$ range 0.13（~4.5×）；C2 ~3.4×；B ~3×；A ~26×；$D_{0.8}$ 在真机 24 rows 恒为 0；Gate B/C 通过。

5. **Leakage-aware adaptation 在 mismatch regime 中有效。**
   *实验证实（H3-2）。* Synthetic：M2/M3 把 VRF 从 <1 恢复到 12–26、leak 削减 97–99%；真机 C2：M3[prob] $=1.52$ 为最优（优于 M1 1.23、M2 0.76）。附注：一旦覆盖存在，权重平衡（$\pi\propto P$）比精确位置更关键。

---

## 5. C1 Stability Audit（单独章节 — 旧结论已被推翻，不得恢复）

**这是一条必须单独、明确记录的负向结论。**

**背景**：H3-2 freeze 前，真机 C1（Sanger B1_N1_side）的泄漏点分离在两种 seed 机制下给出矛盾值：

| 运行 | seed 机制 | $\lVert x^{*}-x_L\rVert$（C1） |
|---|---|---|
| 旧随机种子（pre-freeze） | `SEED + hash(eid)%1000`（`hash()` 进程随机化，不可复现） | **1.136** |
| deterministic crc32（frozen） | `SEED + crc32(eid)%1000` | **0** |

**审计（逐位复刻 frozen C1 分支，只改 seed / N）判定**：

- **Multi-seed**：$d_L\in\{0.318,\,0,\,0,\,0\}$（4 seed 中仅 `seed=1` 出现 0.318）；**旧 1.136 未被任何 seed 复现**。
- **Convergence**：$d_L(N)=\{0,\,0,\,0.472\}$（$N=128/512/2048$），**不随 $N$ 单调下降**（先 0 后 0.47）→ 排除单调有限样本 bias（Case C），属有限样本噪声。
- **Landscape**：max leakage candidate 位置跨 seed 大幅漂移（norm 0.37→0.69，坐标换象限），density gap max/2nd $=1.01\text{–}1.21$（近乎平坦）→ 平坦/plateau 景观（Case B 特征）。

**裁决：Case A（separation 不稳定）为主，附带 Case B landscape 特征。**

$$
\boxed{\text{旧 }d_L=1.136\ \text{是 finite sampling instability 的采样伪影，}\textbf{不是 C1 系统的稳定属性。}}
$$

**科学解释**：C1 mode 区域近凸宽峰，$\rho_L$ 在候选区平坦；$x^{*}=\arg\min\lVert x\rVert$ 与 $x_L=\arg\min\lVert x+\mu\rVert$ 在同一有限点集上取两个不同目标的最小值——平坦区域里哪个样本「胜出」由采样位置决定，seed 一变或 $N$ 一增即翻转。与 synthetic curved（Exp B，$d_L=0.775$ 稳定、$\rho_L$ 峰值尖锐、有解析支撑）形成鲜明对比：**synthetic 的分离是几何真实，real C1 的分离是采样伪影。**

**对 H3 的两条硬性影响**：
1. **真机 mismatch claim 不恢复**：$x^{*}\neq x_L$ 仅在 synthetic curved（Exp B）中成立；真机 C1/C2 未复现稳定分离。任何后续文档**不得**以旧 1.136 或「真机已复现分离」为依据。
2. **single leakage point 不是总是可靠的研究对象**——这正是 H3-3A 把对象从点升级为区域的直接动因。在平坦景观上不应再以「样本 argmin 距离」作为 mismatch 证据。

---

## 6. 当前 non-claims（Currently NOT Claimed）

> 以下均**未**被证明或证实，**不得**在任何 H3 文档中声称：

- ❌ **所有 hybrid rare event 都存在 mismatch**（$x^{*}\neq x_L$ 仅在弯曲/leakage-dominated 体制成立；真机 C1/C2 未复现）。
- ❌ **$x_L$ 是普适最优对象**（平坦景观下单点不稳定；set-valued geometry 也**不**普遍优于 point geometry——不同 $\eta$/$q$ 下 region 诊断可不同）。
- ❌ **H3 已解决高维**（H3-3A 仍在 $d=4$ standardized；design-point / region 搜索维度推广未做）。
- ❌ **已完成 ML predictor**（未进入 ML 阶段）。
- ❌ **已得到完整 regime map**（仅 4 cases；`sharp-separated` 体制在当前 $\nu_V$ 高斯团下解析上不可达，边界未扫）。
- ❌ **globally optimal IS / universal hybrid solver**（H3-2 贡献是 $x^{*}$ 与 $x_L$ 的 mismatch 机制，非通用 IS optimizer）。
- ❌ **second-order grazing theorem / SORM 已验证**（见 §9 的 $\Xi^{(2)}$ 出处更正）。

---

## 7. H3-3B 接口（下一阶段定义 — 不含结果）

**Research Question**：

$$
\boxed{\text{proposal }q\ \text{如何影响 variance geometry }\nu_V\ ?}
$$

**目标**：研究映射

$$
(\text{system},\,q)\ \longrightarrow\ \nu_V,
$$

建立 **Proposal-dependent Variance Geometry Regime Map**。

**H3-3A 留给 H3-3B 的明确指令**（来自 H3-3A §7.3/§9，均为「待做」，非结果）：

1. **研究 proposal-dependent variance geometry（换 $q$ 重跑）**：$q$ 改变时 $\nu_V\propto\mathbf 1_A\,p^2/q$（Gaussian 下 $=\mathcal N(-\mu,I)$）随之改变——验证 $q$ 的改变是否产生**可预测的 $\nu_V$ regime shift**（例如在何种 $q$ 下 HDR 球才缩向真实高密度区）；**不预设**某个 $q$ 一定使 Gate A（$D_{0.8}>0$）成立。
2. **扫描 $\beta,\kappa,K,d$**：定位 `sharp-separated` 体制的边界。
3. **topology competition / mode imbalance**：A 是 multi-mode case，联合 region 在 mode 间的 split 也是研究对象。
4. **比较 $d_L$ 与 region metrics 的 regime 判据**：$\eta$ 取多少时 regime 翻转。

> 本文档**不提前写任何 H3-3B 实验结果**。H3-3B 尚未开始。

---

## 8. 冻结引用与 artifacts

| 角色 | 路径 | 状态 |
|---|---|---|
| H3-0 benchmark 定义 | `docs/phase_h/h3_benchmark_protocol.md` | FROZEN(`127ce0c`) |
| H3-1 分析 | `docs/phase_h/h3_1_variance_leakage_analysis.md` | COMPLETE(`319d9c6`) |
| H3-1 dataset | `tests/data/h3_variance_leakage_dataset_v1.json` | FROZEN（seed 2026 确定性） |
| H3 理论 | `H3_Theory_Consolidation_Variance_Leakage.md` · `H3_Theory_Audit_Proof_Boundary_Refinement.md` | COMPLETE |
| H3 论文正文草稿 | `H3_paper_section.md`（Section X） | DRAFT |
| H3-2 权威文档 | `docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md` · `h3_2_result_analysis.md` | FROZEN(`a03b364→fa7c476`) |
| H3-2 dataset | `tests/data/h3_2_leakage_point_dataset_v1.json` | FROZEN，SHA-256 `29e09cb6…` |
| **C1 stability audit** | `docs/phase_h/H3_2_C1_stability_audit.md` | COMPLETE（**Case A**） |
| C1 audit data | `results/phase_h3/c1_audit_multiseed_v1.json` · `c1_audit_convergence_v1.json` | FROZEN |
| **H3-3A 报告** | `docs/phase_h/H3_3A_set_valued_variance_geometry.md` | **COMPLETE** |
| **H3-3A pilot 数据** | `results/phase_h3/h3_3a_set_valued_geometry_v1.json` | NEW（schema `h3-3a-set-valued-geometry-v1`） |
| **H3-3A figures** | `results/phase_h3/fig10_b_vs_c1_region_comparison.png` · `fig11_dL_vs_set_geometry_stability.png` | NEW |
| frozen ML-B1 snapshot | `tests/data/ml_b1_first_order_geometry_v1.json` | FROZEN，未修改 |

H3-3A 仅只读复用 H3-2 frozen 管线（`import ... as frozen`），**未修改任何 frozen artifact**；H3-2 dataset SHA-256 `29e09cb6…` 保持不变。

---

## 9. 出处与自查（外推 / 无出处 / 不可验证 明确标注）

> 遵循「严格依据指定原始文献、无据宁缺」原则，逐条标注。

**A. 直接来自本次指定输入文件、逐位核验一致的（可信）**
- H3-3A 全部区域指标（$d_L$/$D_\eta$/$R_\eta$/Gate A-B-C 结论）——已用 `h3_3a_set_valued_geometry_v1.json` 的 `stability`/`gates` 字段逐位复核（如 C1 $R_{0.8}$ mean 1.50934、range 0.13192、$d_L$ range 0.59956；Gate A mean align 0.67996；Gate B/C pass；40/40 = 12+12+8+8）。
- H3-1/H3-2/C1 audit 的数值——直接引自对应 frozen 文档。
- 镜像点闭式 $p^2/q=e^{\lVert\mu\rVert^2}\mathcal N(x;-\mu,I)$——在 Theory Consolidation、paper Section X.5.1(X.9)、H3-3A §3.2 三处一致。

**B. 属于 2-D 合成 prototype、非真机结论的（作用域限定，不外推）**
- 「leakage 主导 $\varepsilon_{geo}$/曲率」的机制分离统计（220 系统 Spearman 0.81 / mass 0.43 / $\varepsilon_{geo}$ 0.04；$\lambda^{*}\approx0.49$）——**仅 2-D 合成 testbed**（Theory Consolidation §X.4）。真机上泄漏与曲率两通道相对权重**未在本批 config 完整测得**（H3-2 真机不 rare、单模）。
- mass≠var 反例（$P_2/P_1=7.5\text{e-}4$，$L_2/L_1=1031$，leak_frac 99.9%）——**可证的解析算例**（half-space 一阶模型），非真机测量。

**C. 来自 paper 草稿 / 记忆、未列入本任务必需输入的（标注来源，未作为 §4 已验证依据）**
- paper Section X.6 的精化预测子（$d_{\min}$ Spearman **+0.986**、R² 0.953；leak-law **+0.9998**、AUC 1.000；$C_{gap}^{mass}$ −0.320；$\varepsilon_{geo}$ +0.029）与 coverage-radius 定理（$\beta_c\sim\sqrt3\beta_1$；topology $\lambda^{*}$ 预测 0.399/实测 0.403；curvature 0.639/0.660；$\beta_1\kappa_c=1.05\approx\beta\kappa=1$）——出自 `H3_paper_section.md`（DRAFT），与 Theory Consolidation 的 prototype 观测同源但为更细的 220 系统回归；本文引作**佐证**，未升级为「已证/真机验证」。
- **推荐输入「Figure 5 final freeze document」未提供**：H3-2 的 adaptive Geometry-IS 最终图示（Fig 5）与更宽的 5 方法 × 3 轴消融（75 行）来自项目 paperization 数据包（记忆），**未纳入本次必需输入**，故 §1/§2 的 H3-2 结论仅基于 `h3_2_*` frozen 文档的 M1/M2/M3（synthetic A/B + real C1/C2），不引用未提供文件的数字。

**D. 出处更正（重要，钉死）**
- 早期实验报告把 $\Xi^{(2)}\sim O(1/d^3)$ 归为「Geometry-IS 方差定理 proof pack 的结论」——**归属不准**。方差定理证明包严格限定 $R\equiv0$ half-space，明列 curved boundary（$R\neq0$）为 **NOT claimed**，其中不含任何 $\Xi^{(2)}$。$\Xi^{(2)}=O(d^{-3})$ 实为项目**二阶 saltation / grazing scaling 假设**（handoff §5.3/§7.2 ML-B2/§10.10），当前状态 **CURRENT HYPOTHESIS / SORM pending**（真机上仍需 nonzero leading coefficient + downstream non-cancellation + scaling audit 才能升级）。故本文把 grazing/曲率当作 unified leakage 框架内经由 $x^{*}\neq x_L$ 进入的效应（H3-2 采纳的视角），而**不**引 $\Xi^{(2)}$ 为已证定理；其具体常数在本窗口**不可验证**，未使用任何相关数值。
- 统计口径提醒（handoff §8.4）：antithetic pair 不独立，CI 须用 independent draws 或 pair-aware bootstrap，**禁**对 $2N$ 相关样本套 naive Wilson——后续真机 rare 配置报告需遵守。

**E. 本文档明确不做的**
- 不恢复 C1 旧 $d_L=1.136$；不声称真机稳定 mismatch；不声称 set-valued 普遍最优；不声称高维/ML/regime map 完成；不提前写 H3-3B 结果；不替换任何源定义（沿用 proof pack / ML-B1 / H3-0 记号）。

---

```
H3 FINAL SUMMARY — FROZEN (2026-08-21)

Evolution:
  H3-0 baseline  →  H3-1 variance leakage (P_k != M_k)
  →  H3 Theory (probability geometry x* vs variance geometry x_L)
  →  H3-2 adaptive Geometry-IS (mismatch provable on curved synthetic;
     leakage-aware proposal beneficial on real C2)
  →  C1 audit (old d_L=1.136 is a sampling artifact; point x_L unreliable)
  →  H3-3A set-valued variance geometry (point unstable, region stable)

Unified picture:
  nu_V(dx) ∝ 1_A(x) p(x)^2/q(x) dx ;  Gaussian: nu_V = N(-mu, I)
  variance geometry is a distribution/region object, not always a point.

Supported: (1) prob-geom != var-geom  (2) leakage -> IS failure
  (3) single leakage point unstable in some regimes
  (4) regional variance geometry more stable than point estimator
  (5) leakage-aware adaptation effective in mismatch regime

NOT claimed: universal mismatch; x_L universally optimal; high-dim solved;
  ML predictor done; complete regime map; global-optimal IS; SORM theorem.

Next (H3-3B): (system, q) -> nu_V ; proposal-dependent variance geometry
  regime map.  [no H3-3B results in this document]
```

# H3-3B Phase 1 设计缺陷说明 —— 外部数学评审用

> **文档性质**：外部评审说明书（self-contained review brief）。供未参与本项目的数学专家独立阅读、复核并提意见。
> **状态**：设计阶段发现，**任何实验均未执行**；无已发表结论受影响。
> **所在项目**：RareTopo — 混合动力系统稀有拓扑转移估计（`hypersonic-hybrid-trajectory-lab`，分支 `feature/phase-h-uncertainty-risk`）
> **关联文档**：`H3_3B_Phase1_Curvature_Transition_Scan_Task.md`（已按本报告 §5 冻结修订）、`H3_3B_Regime_Map_Theory_and_Experiment_Plan.md`（上游计划）
> **日期**：2026-08-22

---

## 0. 给评审专家的说明

**我们在做什么**：为稀有事件仿真的重要性采样（Importance Sampling, IS）建立一套"方差几何"理论，并规划一系列数值实验验证它。当前正要执行其中一个小实验（Phase 1：曲率过渡扫描），目的是检验"失效边界曲率是否系统性控制概率几何与方差几何的分离程度"。

**发生了什么**：在把实验设计冻结成任务书之前，我们对设计做了一次解析/数值预检（成本约几分钟），结果**在跑任何实验之前**发现原设计协议中有一处会令核心观测量**恒等于零**的结构性缺陷——即按原协议执行，实验必然输出全零平线，且会被误读为"曲率与对齐无关"的科学负结论。

**本报告的目的**：
1. 自足地交代背景与记号（§1–§2），使您无需阅读项目其他文件即可理解；
2. 完整呈现缺陷的数学内容：一个关于凸集上投影的小引理及其推广（§3）；
3. 说明影响与我们的修复方案（§4–§5）；
4. **列出七个我们希望您重点裁断的问题**（§6）——其中两个是纯数学问题（引理证明是否严密、推广命题代数是否正确），其余是实验设计与理论形式化问题。

**诚实声明**：§3.5 的数值核验是一次性 scratch 计算（脚本未入库），仅用于设计决策；正式确认将由预注册的对照层实验给出。我们的证明如有疏漏，请直接指出——这正是本报告的目的。

---

## 1. 研究背景（自足介绍）

### 1.1 稀有事件仿真与重要性采样

设 $Z\sim p=\mathcal N(0,I_d)$（$d=4$，标准化设计空间），$A\subset\mathbb R^d$ 为稀有失效事件（$P_f=p(A)$ 很小，如 $10^{-4}$）。直接 Monte Carlo 估计 $P_f$ 的相对方差 $\sim (1-p)/p$ 随稀有度爆炸，故采用重要性采样：改从 proposal $q$ 抽样，用权重 $w=p/q$ 校正，

$$
\widehat P_{IS}=\frac1N\sum_i w(Z_i)\mathbf 1_A(Z_i),\qquad
\operatorname{Var}_q(\widehat P_{IS})=\frac1N\Big(M_2-P_f^2\Big),\qquad
M_2=\int_A\frac{p(x)^2}{q(x)}\,dx .
$$

IS 的全部方差信息都在二阶矩 $M_2$ 里。定义 **variance density** 与归一化的 **variance measure**：

$$
\rho_V(x)=\mathbf 1_A(x)\,\frac{p(x)^2}{q(x)},\qquad
\nu_V^{(q)}(dx)=\frac{\rho_V(x)}{M_2}\,dx .
$$

### 1.2 本项目的核心命题：概率几何 ≠ 方差几何

控制失效概率的几何对象与控制估计方差的几何对象**不是同一个点**。对 Gaussian 的 $p,q$ 有一个枢纽闭式（完成平方即得，本项目 H3 阶段的理论核心）：设

$$
p=\mathcal N(0,I),\qquad q=\mathcal N(m,\Sigma),\ \ \Sigma\succ\tfrac12I,
$$

则（忽略截断 $\mathbf 1_A$ 时）

$$
\rho_V(x)\ \propto\ \mathcal N\big(x;\ \mu_V,\ \Sigma_V\big),\qquad
\Sigma_V=(2I-\Sigma^{-1})^{-1},\quad
\mu_V=-(2\Sigma-I)^{-1}m .
$$

合法性条件 $\Sigma\succ\tfrac12I$ 来自可积性：$\Lambda:=2I-\Sigma^{-1}\succ0$。

由此，variance geometry 的两个代表点是：

$$
x^*=\arg\min_{x\in A}\lVert x\rVert\quad(\text{MPP，probability design point})，
\qquad
x_L=\arg\max_{x\in A}\rho_V(x) .$$

**对齐距离**（本缺陷的主角）定义为二者之距：

$$
D_L=\lVert x^*-x_L\rVert .
$$

$D_L\approx0$ 称 **aligned**（两几何重合），$D_L>0$ 称 **mismatch**。mismatch 意味着"把 proposal 对准 MPP"这一标准做法对方差而言瞄错了地方——这是本项目论证 leakage-aware IS 的基石。

### 1.3 项目演化链与本阶段位置

| 阶段 | 内容 | 状态 |
|---|---|---|
| H3-1 | 方差泄漏：$M_2=\sum_k L_k$，低概率 mode 可主导方差 | 已冻结 |
| H3-2 | $x^*\neq x_L$ 在弯曲边界合成案例中稳定出现（$d_L=0.775$）；真机案例 aligned | 已冻结 |
| C1 audit | 真机旧 mismatch 值被判定为采样伪影 → 单点 $x_L$ 不总可靠 | 已冻结 |
| H3-3A | 研究对象升级：单点 → 区域 $\mathcal L_\eta$（HDR），区域参数稳定 | 已冻结 |
| H3-3B Theory | 上文闭式 $(\mu_V,\Sigma_V)$ + 合法性 $\Sigma\succ\tfrac12I$ | 理论基础 |
| H3-3B Pilot/Multi | proposal→geometry 映射跨 4 系统（含 2 真机）成立 | 已完成 |
| **Regime Map / Phase 1** | 问：alignment 是否随边界曲率 $\beta\kappa$ 系统变化？（本文缺陷发生处） | **设计中，未执行** |

Phase 1 的原始动机：H3-2 经验上观察到分离出现在"弯曲边界、$\beta\kappa\gtrsim1$"体制（$\beta=$ 标准化边界距离即稀有度，$\kappa=$ 边界曲率），计划沿曲率轴扫描，画 $d_L(\beta\kappa)$ 过渡曲线。

---

## 2. Phase 1 的测试床与原设计协议

### 2.1 合成测试床（frozen）

维度 $d=4$，但标签函数只依赖前两个坐标（后两坐标恒 0）。名义区之外有两个互斥失效模态：

- $S_1=\{u_1<-1.5\}$（线性半空间）；
- $S_2=\{\,u_1>h(u_2)\,\}$，$h(t)=1.0+0.5\,(t-1.5)^2$ ——**抛物线 epigraph，顶点偏移在 $t=1.5$**。

$S_2$ 的 frozen 锚点（密集网格上逐位确定）：$x^*=(1.2333,\,0.825)$，$x_L=(1.7667,\,0.2625)$，$d_L=0.7751$。语料统一使用基线锚定 proposal $m=\mu_{base}=(-1.5,0,0,0)$（历史沿用的 ML-B1 式设计点）。

### 2.2 原计划的扫描协议（缺陷所在处）

上游计划书写道（大意）：固定 proposal 形如 $q=\mathcal N(x^*,I)$（即 $m=x^*$、$\Sigma=I$），参数化改变边界曲率，记录 $x^*,x_L,D_L$，画过渡曲线，寻找 aligned→mismatch 的临界 $\beta\kappa_c$。

"把 proposal 对准当前构型的 MPP"是最自然的选择（对应基线方法 M1 的约定），计划书以"如"字举例带过——**但恰恰是这个举例选择使观测量恒为零**。见下。

---

## 3. 缺陷的详细分析

### 3.1 关键改写：两个几何点都是投影

$x_L$ 是 $\rho_V$ 的 argmax；在 $\Sigma=I$ 下 $\rho_V\propto\mathcal N(-m,I)$，argmax 等价于到镜像点的最近点投影：

$$
x_L=\operatorname{proj}_A(-m),\qquad x^*=\operatorname{proj}_A(0)
\quad\Longrightarrow\quad
\boxed{\ D_L=\big\lVert\operatorname{proj}_A(-m)-\operatorname{proj}_A(0)\big\rVert\ }
$$

**这是问题的根源性观察**：$D_L$ 不是失效集 $A$ 单独的属性，而是**二元组 $(A,\ m)$ 的属性**——它是"原点的投影"与"镜像点的投影"之间的距离。当 $m=x^*$ 时，两个查询点是 $0$ 与 $-x^*$。

### 3.2 引理 1（凸集恒零，$\Sigma=I$ 情形）

> **引理 1.** 设 $A\subset\mathbb R^d$ 非空闭凸，$x^*=\operatorname{proj}_A(0)$，$\beta=\lVert x^*\rVert>0$。则
> $$\operatorname{proj}_A(-x^*)=\{x^*\}\ (\text{唯一})，\qquad D_L=0.$$

**证明**（三行）。投影的法锥条件给出

$$
\langle 0-x^*,\,z-x^*\rangle\le0\ \ \forall z\in A
\quad\Longrightarrow\quad
\langle x^*,z\rangle\ge\beta^2,\qquad
\lVert z-x^*\rVert^2\le\lVert z\rVert^2-\beta^2 .
$$

于是对任意 $z\in A$：

$$
\lVert z+x^*\rVert^2=\lVert z\rVert^2+2\langle x^*,z\rangle+\beta^2
\ \ge\ \beta^2+2\beta^2+\beta^2=4\beta^2=\lVert 2x^*\rVert^2,
$$

且 $z=x^*$ 达到等号。若某 $z$ 也达到等号，则需 $\lVert z\rVert=\beta$ 且 $\langle x^*,z\rangle=\beta^2$，由 Cauchy–Schwarz 等号情形得 $z=x^*$，唯一性成立。∎

**推论（对本项目的杀伤力）**：抛物线 epigraph、半空间、以及一切凸失效集上，**只要 proposal 锚在 $x^*$，mismatch 就恒为零**。原协议下 Figure A 必然是一条全零平线——不是"曲率不影响对齐"的科学发现，而是测量协议的自我抵消。

### 3.3 推广命题（一般合法 $\Sigma$；代数已自检 + 数值核验，请专家复核）

记 $\Lambda=\Sigma_V^{-1}=2I-\Sigma^{-1}$，$f(z)=(z-\mu_V)^{\mathsf T}\Lambda(z-\mu_V)$（$\rho_V$ 核的马氏距离目标）。取 $m=x^*$，利用 $\mu_V=-(2\Sigma-I)^{-1}x^*$ 与 $(2\Sigma-I)^{-1}(2I-\Sigma^{-1})=\Sigma^{-1}$（二者同为 $\Sigma$ 的函数，可交换），直接展开可得

$$
f(z)-f(x^*)\;=\;2\big(\lVert z\rVert^2-\beta^2\big)\;-\;(z-x^*)^{\mathsf T}\Sigma^{-1}(z-x^*).
$$

若 $\Sigma\succeq\tfrac12I$（合法性条件的闭形式），则 $\Sigma^{-1}\preceq2I$，结合 §3.2 的 firmly-nonexpansive 不等式：

$$
(z-x^*)^{\mathsf T}\Sigma^{-1}(z-x^*)\le2\lVert z-x^*\rVert^2\le2\big(\lVert z\rVert^2-\beta^2\big)
\quad\Longrightarrow\quad f(z)\ge f(x^*) .
$$

> **命题 1′（非正式陈述）**：$A$ 闭凸、$q=\mathcal N(x^*,\Sigma)$、$\Sigma\succeq\tfrac12I$ ⟹ $x_L=x^*$（马氏意义），$D_L\equiv0$。**且合法性界 $\tfrac12I$ 恰好就是证明所需的常数**。

**数值自检**：在 frozen-B 钉 $\beta$ 构型上，对 $\Sigma\in\{I,\ 0.75I,\ 2I,\ \mathrm{diag}(1.5,0.8),\ 旋转椭圆(1.8,0.6@40^\circ),\ 0.51I\}$，马氏投影数值解给出的 $D_L$ 全部 $\le7\times10^{-8}$（优化器容差级）。

这个"合法性条件恰好是引理成立条件"的重合让我们怀疑背后有共轭/对偶层面的更深解释——列为问题 Q4。

### 3.4 逃逸通道：非凸"包裹"

引理对凸集成立，非凸可以失败。反例：环形失效区 $A=\{z:\lVert z\rVert\ge1\}$（原点在"洞"里）。取 $x^*=e_1$，则 $-e_1\in A$ 且 $\lVert-e_1+e_1\rVert=0<2$，故 $x_L=-e_1$，$D_L=2>0$。

几何直觉：**只有当 $A$ 能"绕回"到镜像点 $-m$ 的 $2\lVert x^*\rVert$ 邻域内，mismatch 才可能在 $m=x^*$ 下出现**——这本质上是 $A$ 相对线段 $[-x^*,x^*]$ 的非凸性。多模态并集（如 $S_1\cup S_2$）整体非凸、但逐模态凸；本项目语料历来**逐模态**计算 $x^*,x_L$，故每个模态各自落在引理适用范围内。

### 3.5 设计期数值核验记录（scratch，一次性脚本，未入库）

在冻结任务书前我们做了两组核验（正式确认将由实验的预注册对照层给出）：

**(a) frozen 锚点逐位复现** ✅：在与 frozen 管线完全相同的 $481\times401$ 网格上，$x^*,x_L,d_L=0.7751$ 全部逐位重现——确认我们对管线与约定的理解无误。

**(b) 双约定对照扫描**（钉 $\beta\equiv\beta_B=1.483825$、顶点偏移 $v=1.5$、扫二次系数 $a$；连续层 = 边界参数化高分辨率极小化）：

| $a$ | $\kappa_{MPP}$ | $\gamma=\beta\kappa$ | $d_L$ @ $m=\mu_{base}$（主约定） | $D_L$ @ $m=x^*$（原协议） |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0（解析） | 0（引理 1） |
| 0.02 | 0.040 | 0.059 | 0.085 | **0** |
| 0.05 | 0.098 | 0.145 | 0.195 | **0** |
| 0.10 | 0.185 | 0.274 | 0.338 | **0** |
| 0.20 | 0.325 | 0.482 | 0.523 | **0** |
| **0.50 ★** | 0.572 | 0.848 | **0.740**（网格层 0.775 = frozen） | **0** |
| 1.00 | 0.759 | 1.126 | 0.856 | **0** |
| 2.00 | 0.909 | 1.349 | 0.949 | **0** |

三个要点：
1. 原协议列（$m=x^*$）**全程严格为零**，与引理 1 一致；
2. 主约定列显示过渡**存在且单调**，但形态是从 0 开始的**渐变起始**（近似线性抬升，无阈值跳变）——原计划"寻找临界 $\beta\kappa_c$"的成功标准在本族中也预期落空；$\beta\kappa\approx O(1)$ 对应的是 $d_L$ 趋于饱和的平台区，而非起始点；
3. 连续层与 frozen 网格层在 anchor 处差 $0.033\approx$ 网格分辨率，桥接无碍。

### 3.6 为什么既有结论不受影响

- 语料的全部 frozen $d_L$ 数字（含 B 的 0.775 与真机 aligned 裁决）都是在 $\mu_{base}$ 约定下、逐模态计算的，约定全程统一，数字之间可比；
- H3-3B pilot/multi-system 的 mean sweep 用的是 $m_\lambda=(1-\lambda)x^*+\lambda x_L$ 连线上的偏移锚，不落在引理的退化点上，其 $\rho(\mu_V,m_\eta)=0.99$ 的结论不受影响；
- 反而引理解释了 multi-system 的经验发现"aligned 系统 mean 杠杆退化"的一个更深层结构：**mean 杠杆需要偏移锚才有作用空间**（见 §4 第 4 条）。

---

## 4. 影响评估

| # | 影响层面 | 内容 | 严重度 |
|---|---|---|---|
| 1 | Phase 1 实验 | 原协议必产全零曲线 → Gate 假性失败 → "曲率不控制对齐"的假阴性科学结论 | 致命（已避免） |
| 2 | Regime Map 理论 | Axis 1 的 $D_L$ 被证明是**协议相对量**："系统 aligned/mismatch"必须表述为"(系统 × 锚定类别)"对的属性 | 高（需重新形式化） |
| 3 | 语料一致性 | 若 Phase 1 换新约定，与全部 frozen 数字失去可比性；可能无意复活/推翻旧 claim | 高（须守约定） |
| 4 | 两杠杆结构 | 引理 + multi-system 实证合并出锐化命题：**mean 杠杆仅在偏移锚下有作用空间；covariance 杠杆不受此限**（multi-system 的 cov sweep 恰在 $m=x^*$ 下仍 4/4 有效——因为 $\Sigma_V$ 改变形状而不移动投影查询点） | 中（正面收获） |
| 5 | 论文叙事 | 缺陷转化为定理候选："MPP 居中的 IS 对凸失效集的 variance geometry 结构性失明"——为 leakage-aware proposal 提供必然性论证 | 正面转化 |
| 6 | 流程 | 若未做预检：损失一次全量扫描 + 一次错误的里程碑降级。预检成本几分钟 | 流程教训 |

---

## 5. 我们的修复方案（已在任务书中冻结，请专家评判是否妥当）

**DV1（主约定更换）**：过渡曲线的主约定改为 frozen $\mu_{base}=(-1.5,0,0,0)$（与全部语料一致，保证可比性与信号存在）；原协议 $m=x^*$ 降级为**辅约定对照层**（仅确定性计算，无 MC 成本），其预期恒零本身作为引理 1 的实验确认项——预期为零也是贡献。

**DV2（成功标准更换）**：放弃"寻找临界 $\beta\kappa_c$ 使 $D_L$ 穿零"，改为报告 onset 描述子 $\gamma_{on}:=\inf\{\gamma: d_L(\gamma)\ge0.1\}$ 并显式分类过渡形态（渐变 vs 跳变，两者都算通过）；禁止对起始段做参数化拟合后外推。

**DV3（双约定分账）**：主约定 $d_L$ 与辅约定 $D_L^\star$ 分开落盘、分开报告，禁止混用。

**配套流程**：(i) 任务书增加"解析预检先行"永久步骤；(ii) 七条预注册失败预案（含"辅约定若出现非零必须先停"——那将否定引理，须先排查实现错误）；(iii) Phase 1 数值确认后，拟将引理 1/命题 1′ 回填理论文档升格为正式命题。

---

## 6. 请专家重点意见的七个问题

> **Q1（引理严密性）**：§3.2 引理 1 的证明是否严格？特别地：开 epigraph 需取闭包处理投影的存在性，我们的处理是否严谨？"唯一最小元"的 Cauchy–Schwarz 论证是否有遗漏的退化情形？

> **Q2（推广命题）**：§3.3 的展开代数（$f(z)-f(x^*)=2(\lVert z\rVert^2-\beta^2)-(z-x^*)^{\mathsf T}\Sigma^{-1}(z-x^*)$）是否正确？"合法性条件 $\Sigma\succeq\tfrac12I$ 恰为证明所需常数"是巧合还是有对偶/共轭解释？

> **Q3（内蕴形式化）**：既然 $D_L$ 是 $(A,m)$ 的属性，Axis 1 更好的形式化是什么？备选：(a) 接受协议相对性，记录锚定元数据即可；(b) 把整条函数 $m\mapsto D_L(m)$ 作为研究对象（其支集、Lipschitz 性质、随曲率的演化）；(c) 寻找不含 $m$ 的内蕴不变量。您建议哪条路？

> **Q4（非凸逃逸的分类）**：除"包裹/环形"外，是否存在其他机制使 $m=x^*$ 下 $D_L>0$？多模态并集整体非凸（逐模态凸）时，跨模态投影切换是否会制造伪 mismatch？我们是否应补充 union-A 的对照计算？

> **Q5（过渡统计量）**：scratch 显示 $d_L(a)$ 近似立即线性抬升（无阈值），$\gamma_{on}=\inf\{\gamma:d_L\ge0.1\}$ 是阈值相对的描述子而非内禀临界量。有无更标准的过渡统计建议（如起始斜率 $\partial d_L/\partial\gamma\big|_{0}$、饱和尺度、logistic 拐点）？H3-2 的"$\beta\kappa\gtrsim1$"经验判据应如何与之调和？

> **Q6（族的充分性）**：单参数抛物线族 + 钉 $\beta$ 的设计，是否足以支撑"曲率控制 alignment"的结论？是否需要第二个族（非二次边界）做稳健性，或至少做一个偏移量 $v$ 的敏感性 probe？

> **Q7（成本取舍）**：辅约定对照层目前只做确定性计算（近零成本）。是否值得追加少量 MC 以确认区域级描述子在 $m=x^*$ 下的行为（预期：$x_L$ 不动但 $R_\eta,C_\eta$ 仍响应——这将把"点级失明 vs 区域级可见"做成完整证据链）？

---

## 7. 复核材料清单

| 材料 | 位置 |
|---|---|
| 修订后的 Phase 1 任务书（含 DV1–DV3 与七条失败预案） | `docs/phase_h/H3_3B_Phase1_Curvature_Transition_Scan_Task.md` |
| 上游 Regime Map 计划（§6.1 为被修订对象） | `docs/phase_h/H3_3B_Regime_Map_Theory_and_Experiment_Plan.md` |
| 理论基础（闭式推导、合法性条件） | `docs/phase_h/H3_3B_Theory_Extension.md` |
| frozen 测试床代码（`label_curved`、`point_geometry`） | `scripts/run_h3_2_adaptive_geometry_is.py`、`src/hyptraj/uncertainty/leakage_point_geometry.py` |
| frozen 锚点数据 | `tests/data/h3_2_leakage_point_dataset_v1.json`（SHA-256 `29e09cb6…`） |
| scratch 核验（本报告 §3.5 数据来源，一次性 heredoc 脚本，未入库；可按 §3.5 参数表复现） | — |

---

## 8. 评审回复处理记录（2026-08-22，v2 增补）

> 外部专家已对 §6 的七个问题逐条裁断，并提供了可直接回填的正式命题文本。本节记录全部处置；本文件正文（§0–§7）保留评审时点原貌，作为历史记录不再改写——"缺陷→定理前置为标题"等写法建议在下游文档（任务书 v2、Theory Extension v2、未来论文稿）中落实。

### 8.1 专家裁断摘要

| 问题 | 裁断 | 处置 |
|---|---|---|
| Q1 引理严密性 | **证明严格**；但建议换用坐标无关的一阶+凹性证明（唯一性来自严格凹、存在性来自强制+闭性，无需 Cauchy–Schwarz 等号讨论） | ✅ 采纳：已按一阶版回填 Theory Extension **定理 4.4**；投影版降为推论 4.5 的初等备选证明 |
| Q2 推广代数 | 代数正确；**"$\tfrac12I$ 巧合"有干净答案**：同一不等式 $\Sigma^{-1}\preceq2I$ 同时是可积性、对数凹性与证明常数（因子 2 = $p$ 的幂次） | ✅ 采纳：回填为**注 4.6**（named 观察点）；另采纳措辞订正——命题前提改为**严格** $\Sigma\succ\tfrac12I$ |
| 数值复查（非编号问题） | **$a=0$ 行纠错**：主约定镜像查询点 $(1.5,0)$ 在钉 β 半空间内部，$d_L=1.5-\beta_B=0.0162$，非解析 0；根子是 $\lVert\mu_{base}\rVert=1.5\neq\beta_B$ | ✅ 确认并修正。**且我方复核发现影响更大**：$(1.5,0)\in A_{S2}$ 的临界为 $a^\ast=0.05306$，整个 $a<a^\ast$ 区为**内点峰体制**（$x_L$ 冻结于内点），受影响行 $a\in\{0,0.005,0.01,0.02,0.05\}$；v1 scratch 的"边界-only 极小化"方法错误一并披露修正（详见任务书 v2 §5.1/§5.3） |
| 科学叙事 | scratch 数据实质推翻 H3-2 的"临界曲率"心智模型：分离任意 $a>0$ 存在、近线性生长、$\beta\kappa\sim1$ 是**饱和尺度而非阈值**；应作为正面修正写出，含金量高于"避免全零" | ✅ 采纳：任务书 v2 DV4 + P1-H2；报告将以此为主线叙事 |
| Q3 内蕴形式化 | 走 (c)：内蕴对象是 $x^*$ 处**形状算子/投影 Jacobian**；$D_L(m)$ 只是方向探针；锚定类别作必备元数据；(b) 整函数路线不作主线 | ✅ 采纳：Axis 1 元数据字段入任务书 v2 §9；形状算子方向记 future work |
| Q4 非凸逃逸 | 包裹型（相对线段 $[-x^*,x^*]$ 非凸）已是充要机制；**union-A 对照必须做**，专家粗估 $D_L^{union}\approx3.2$ | ✅ 已复核精确值 **3.193**（设计期）；列为强制对照 Gate C6（任务书 v2） |
| Q5 过渡统计量 | 扔掉阈值描述子 $\gamma_{on}$；换初始斜率 $s_0$ 与饱和尺度 $\gamma_{sat}$；Michaelis 拟合仅报参数禁外推 | ✅ 采纳：Gate A2 重写（DV2 扩充） |
| Q6 族充分性 | 不够：钉 β 只锁模长未锁位置，需第二非二次族分离曲率与锚–边界几何漂移；$v$ probe 仅次优替代 | ✅ 采纳：新增 $r\in\{1.5,3\}$ 族 probe（6 config，Layer D，Gate C7）；$v$ mini-probe 保留为 F2 预案 |
| Q7 点级 vs 区域级 | 值得做："点级失明、区域级可见"是盲性定理证据链的关键环，成本低 | ✅ 采纳：辅约定层追加少量 MC 确认 $R_\eta,C_\eta$ 响应（列入脚本实现范围） |

### 8.2 回填落点索引

| 产出 | 位置 |
|---|---|
| 定理 4.4（MPP 锚定方差盲性，一阶+凹性证明）/ 推论 4.5 / 注 4.6（三顶帽子）/ 注 4.7（凸性必要与 union 伪 mismatch） | `H3_3B_Theory_Extension.md` Section 4（v2 增补块） |
| 注 5.1（协方差杠杆触发区域级分离需要偏移锚的前提修正） | 同上 Section 5 |
| 任务书 v2（内点分支 Layer-D、$a^\ast$ 格点、修正扫描表、DV1–DV6、Gate A/C 重写、执行清单更新） | `H3_3B_Phase1_Curvature_Transition_Scan_Task.md` |

### 8.3 遗留开放项

1. 第二族 probe 与 union-A 对照的**实验确认**待 Phase 1 执行后回填（当前为设计期数值）；
2. 形状算子/投影 Jacobian 作为内蕴 alignment 量的形式化——future work，不在 H3-3B 展开；
3. 若后续在真机 multi-mode 上做 union 级测量，须引用注 4.7 的伪迹警示。

---


| 符号 | 含义 |
|---|---|
| $p=\mathcal N(0,I)$ | 名义密度（标准化设计空间） |
| $q=\mathcal N(m,\Sigma)$ | IS proposal；合法性条件 $\Sigma\succ\tfrac12I$ |
| $A$ | 失效事件集合（本文中始终指集合） |
| $\rho_V=\mathbf 1_A\,p^2/q$，$\nu_V^{(q)}$ | variance density / 归一化 variance measure |
| $M_2=\int_A p^2/q\,dx$ | IS 二阶矩（方差之源） |
| $x^*=\arg\min_A\lVert x\rVert=\operatorname{proj}_A(0)$ | probability design point（MPP） |
| $x_L=\arg\max_A\rho_V$；$\Sigma=I$ 时 $=\operatorname{proj}_A(-m)$ | variance leakage point |
| $D_L=\lVert x^*-x_L\rVert$ | alignment 距离（本缺陷主角） |
| $\beta=\lVert x^*\rVert$，$\kappa$ | 标准化边界距离（稀有度）/ 边界曲率；$\gamma=\beta\kappa$ |
| $h_a(t)=c+a(t-1.5)^2$ | 参数化边界族；$a=0.5,c=1$ 退回 frozen B |
| $\mu_V=-(2\Sigma-I)^{-1}m$，$\Sigma_V=(2I-\Sigma^{-1})^{-1}$ | variance-geometry 高斯核 |
| $\mu_{base}=(-1.5,0,0,0)$ | frozen 基线锚定（语料统一约定） |

## 附录 B：一句话摘要（供快速转述）

> 我们要在凸抛物线失效集上扫曲率、测"MPP 点与方差代表点的分离 $D_L$"；预检发现：若 proposal 按惯例锚在 MPP，则由凸集投影的一个三行引理，$D_L$ 恒为零——实验会必然输出全零平线。修复：proposal 改用语料统一的偏移锚 $\mu_{base}$（信号恢复，scratch 显示单调渐变起始），原协议降为对照层用于确认引理本身；同时该引理反而升级为"MPP 居中 IS 对凸失效集结构性失明"的定理候选。

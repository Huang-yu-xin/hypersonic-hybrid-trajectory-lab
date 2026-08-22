# H3-3B — Theory Extension：Proposal-Dependent Variance Geometry

> 项目：**RareTopo** — Rare Topology Transition Estimation in Hybrid Dynamical Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab` · 分支：`feature/phase-h-uncertainty-risk`
> 论文主线：ICML 2027 方法论文
> 仓库目标路径：`docs/phase_h/H3_3B_Theory_Extension.md`
> **状态：THEORY FOUNDATION（H3-3B 理论基础；实验未开始）**
> **增补（v2,2026-08-22）**:外部评审后回填 定理 4.4 / 推论 4.5 / 注 4.6–4.7 / 注 5.1(MPP 锚定方差盲性及其对协方差杠杆路径的前提修正);原有章节编号与全部结论不变。
> 依据链：H3_Final_Summary（H3-3A COMPLETE / frozen）· H3_Theory_Consolidation_Variance_Leakage · H3_3A_set_valued_variance_geometry
> 本文用途：为 H3-3B「proposal $q$ 如何塑造 variance geometry $\nu_V$」建立**唯一理论依据**——只建框架,不出实验结论。

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

**结论先行。** 这是 H3-3B 阶段的**理论基础文档**。它在 H3-3A 已完成的 set-valued variance geometry 基础上,把研究对象从「failure event 决定的 $\nu_V$」推进到「$(\text{system},q)$ **共同**决定的 $\nu_V^{(q)}$」,并给出 Gaussian proposal 下的完整闭式推导与区域级表示方式。

本文档严格遵守四条边界(贯穿全文):

1. **只建立理论框架**:不进行大规模实验、不定义完整 regime map、不讨论 ML predictor、不提前写任何 H3-3B 实验结论。
2. **区分层级**:数学恒等式 / 定理(可证)、待验证**假设**(hypothesis)、**未来工作**(future work)——三者分开措辞,不混用。凡属推导可证者标 **定理/命题**,凡属经验待验证者标 **假设**。
3. **不恢复被推翻的旧结论**:沿用 Final Summary §5 的裁决——真机 C1 旧 $d_L=1.136$ 是采样伪影,本文不以任何形式恢复;不声称真机稳定 mismatch。
4. **保持 H3 原符号体系**:失效事件 $A$、密度 $p=\varphi$、leakage/variance density、measure $\nu_V$、MPP $x^*$、leakage point $x_L$、region descriptors $(D_\eta,m_\eta,R_\eta,S_\eta)$ 全部沿用;新增符号显式定义并与旧符号对齐。

---

## 符号与约定（Notation & Conventions）

为使本文档自洽且可与 frozen 文档逐字对照,先固定符号。

| 符号 | 含义 | 出处 / 备注 |
|---|---|---|
| $A$,$\ \mathbf 1_A$ | 稀有失效事件(集合)及其示性函数;$A=\sqcup_k A_k$ 按互斥拓扑模态分解 | H3-0/H3-1(**始终指集合,不作它用**) |
| $p=\varphi=\mathcal N(0,I)$ | 标准化设计空间的名义密度 | H3-0 冻结协议 |
| $q$ | importance sampling proposal;Gaussian 情形 $q=\mathcal N(m,\Sigma)$ | H3-3A 冻结协议为特例 $q=\mathcal N(\mu,I)$ |
| $\rho_V(x)=\mathbf 1_A(x)\dfrac{p(x)^2}{q(x)}$ | variance density | **$\equiv$ H3 的 leakage density $\rho_L$**(同一对象,两名) |
| $\nu_V^{(q)}(dx)=\dfrac{\rho_V(x)}{\int_A\rho_V\,dx}\,dx$ | (归一化)variance measure | H3 记 $\nu_V$;上标 $(q)$ 仅强调其对 $q$ 的依赖 |
| $M_2=\int_A\dfrac{p^2}{q}\,dx=\sum_k L_k$ | estimator 二阶矩;$L_k=\int_{A_k}\dfrac{p^2}{q}\,dx$ | H3-1 精确恒等式 |
| $x^*=\arg\min_{x\in A}\lVert x\rVert$ | probability design point(MPP),probability geometry 代表点 | 控制 $P_f$ |
| $x_L=\arg\max_{x\in A}\rho_V(x)$ | variance leakage point,variance geometry 代表点 | 控制 $M_2$;平坦景观下不稳定(H3-2 C1 audit) |
| **$D_L=\lVert x^*-x_L\rVert$** | 点级 alignment 距离(**v2 新增**);区域级对应量为 $D_\eta$ | 见定理 4.4 |
| **$N_A(x)$** | $A$ 在 $x$ 处的法锥(**v2 新增**,凸分析标准记号:$N_A(x)=\{v:\langle v,z-x\rangle\le0\ \forall z\in A\}$) | 定理 4.4 证明用 |
| $\mathcal L_\eta=\{x\in A:\rho_V(x)\ge c_\eta\}$,s.t. $\nu_V^{(q)}(\mathcal L_\eta)\ge\eta$ | variance-critical high-contribution region(HDR) | H3-3A |
| $D_\eta=\mathrm{dist}(x^*,\mathcal L_\eta)$ | 区域分离(**到最近点**) | H3-3A |
| $m_\eta=\mathbb E_{\nu_V}[X\mid X\in\mathcal L_\eta]$ | 区域**加权质心** | H3-3A(注:$m_\eta$ 带下标,区别于 proposal mean $m$) |
| $R_\eta=\sqrt{\mathbb E_{\nu_V}[\lVert X-m_\eta\rVert^2\mid X\in\mathcal L_\eta]}$ | 区域扩散 | H3-3A |
| $S_\eta=D_\eta/(R_\eta+\varepsilon)$ | 分离-扩散比 | H3-3A |
| **$\Lambda:=2I-\Sigma^{-1}$** | variance-geometry precision matrix(**新增**) | **任务书记作 $A$;为避免与失效事件 $A$ 冲突,本文改记 $\Lambda$** |
| $(\mu_V,\Sigma_V)$ | variance-geometry Gaussian 核的均值与协方差(**新增**) | 见 Section 4 |
| $C_\eta,\ G_\eta$ | region center shift / normalized mismatch(**新增**) | 见 Section 6 |
| $\mathrm{VRF}$ | variance reduction factor($\mathrm{Var}_{MC}/\mathrm{Var}_{IS}$) | H3-1/H3-2 |

**两处必须注意的符号对齐**:
- **$\rho_V\equiv\rho_L$**:任务书称 variance density $\rho_V$,H3 corpus 称 leakage density $\rho_L$,是**完全相同**的对象 $\mathbf 1_A\,p^2/q$。下文交替出现时按同一对象处理。
- **$m$(proposal mean,无下标)vs $m_\eta$(region center,有下标)**:任务书 Gaussian proposal 记 $q=\mathcal N(m,\Sigma)$;$m$ 推广了 H3-3A 的 $\mu$——当 $\Sigma=I$、$m=\mu$ 时二者重合。请勿与区域质心 $m_\eta$ 混淆。

---

## Important Scientific Context — H3 的演化（H3-1 → H3-2 → H3-3A → H3-3B）

按任务要求,先说明 H3 研究对象的逐级演化。**每一步都在修正上一步的对象定义**,H3-3B 是这条链的直接延伸。

### H3-1 — probability mass ≠ variance contribution

**发现**:失效事件的「概率质量」不等于其「方差贡献」。

$$
\boxed{\,P_k\neq M_k\,}\qquad(\text{低概率 topology mode 可以主导 }M_2\text{)}.
$$

把 IS 二阶矩沿互斥模态展开得到**精确恒等式**(非近似、与是否 Gaussian 无关):

$$
M_2=\sum_k L_k,\qquad
L_k=\int_{A_k}\frac{p^2(x)}{q(x)}\,dx=\mathbb E_p\!\Big[\tfrac{p}{q};A_k\Big].
$$

某模态覆盖不足($q\ll p$)时 $L_k$ 被 IS 权重 $p/q$ 放大,与 $P_k$ 脱钩(H3-1 synthetic $S_2$:0.6% 概率贡献 99% 方差,VRF 0.54)。

> **该恒等式对任意 $q$ 成立**——这是 H3-3B 的一个不变量:换 $q$ 只改变每个 $L_k$ 的**取值**,不改变 $M_2=\sum_k L_k$ 的**分解结构**。

### H3-2 — probability geometry ≠ variance geometry

**发现**:控制概率的几何点

$$
x^*=\arg\min_{x\in A}\lVert x\rVert
$$

与控制方差的几何点

$$
x_L=\arg\max_{x\in A}\rho_V(x)
$$

**可以不同**。在 $p=\mathcal N(0,I)$、$q=\mathcal N(\mu,I)$ 下配方给出枢纽闭式

$$
\frac{p(x)^2}{q(x)}=e^{\lVert\mu\rVert^2}\,\mathcal N(x;-\mu,I)
\ \Longrightarrow\
x_L=\arg\min_{x\in A}\lVert x+\mu\rVert,
$$

即**方差积分是以镜像点 $-\mu$ 为中心的高斯在 $A$ 上的限制**。分离 $x^*\neq x_L$ 在 curved boundary / $\beta\kappa\gtrsim1$ 体制中可现(synthetic Exp B 稳定分离 $0.775$),线性/凸边界下二者重合。

### H3-3A — 单点 $x_L$ 不是始终稳定的研究对象

**发现**:当 $\rho_V$ 景观平坦时,单点 $x_L$ 由有限样本 argmin 竞争决定、随 seed/$N$ 漂移(真机 C1 $d_L$ range $0.600$;旧 $1.136$ 判为采样伪影)。因此更一般、更稳定的研究对象是**测度 / 区域**:

$$
\nu_V(dx)\propto\mathbf 1_A(x)\,\frac{p(x)^2}{q(x)}\,dx,
\qquad
\mathcal L_\eta=\{\rho_V\ge c_\eta\}.
$$

H3-3A 实验证实(4 case):**点估计 $d_L$ unstable,但区域参数 $(m_\eta,R_\eta,c_\eta)$ stable**(C1:$d_L$ range 0.60 vs $R_{0.8}$ range 0.13,~4.5×;$D_{0.8}\equiv0$ 全部 24 rows)。同时如实报告:在冻结协议 $\Sigma=I$ 下 $\nu_V=\mathcal N(-\mu,I)$ 的 80% 质量球必然包含 MPP,故 `sharp-separated` 体制在**该配比**下解析上不可达。

### H3-3B — proposal $q$ 如何塑造 $\nu_V^{(q)}$?

H3-3A 的关键局限是**只固定了 $\Sigma=I$**(仅平移 $q$)。于是本阶段研究映射

$$
\boxed{\ (\text{system},\,q)\ \longrightarrow\ \nu_V^{(q)}\ }
$$

即 **importance sampling proposal 如何改变 variance geometry**。核心动机来自 H3-3A §7.1/§9 的明确指令:要触发区域级分离($D_\eta>0$),需让 $q$ 移向 $\nu_V$ 集中区。H3-3B 在理论上把这个「移动 $q$」的自由度**完整打开**——不仅平移 $m$,而且引入协方差 $\Sigma$ 这一新杠杆。

---

# Section 1 — General Proposal-Dependent Variance Geometry

**重新定义(强调 $q$ 依赖)。** 给定 proposal $q$,

$$
\rho_V(x)=\mathbf 1_A(x)\,\frac{p(x)^2}{q(x)},
\qquad
\nu_V^{(q)}(dx)=\frac{\rho_V(x)}{\displaystyle\int_A\rho_V(x)\,dx}\,dx.
$$

这与 H3-3A 的 $\rho_L/\nu_V$ 是同一对象;上标 $(q)$ 只是把「$\nu_V$ 依赖于 $q$」这一事实写进符号,以便后续讨论「换 $q$」。

**框架命题(定性,本节核心陈述)。**

> variance geometry 不是**只由 failure event $A$ 决定**的对象。它由二元组
> $$(\text{system},\,q)$$
> **共同**决定:$A$(及其拓扑分解 $A=\sqcup_k A_k$)提供 $\mathbf 1_A$ 与积分区域的几何,而 $q$ 通过分母 $q(x)$ 直接塑造 $\rho_V$ 的形状。改变 $q$ 会改变整个测度 $\nu_V^{(q)}$——包括其质心、扩散、朝向,乃至它是否是良定义的(见 Section 3)。

**不变量提醒。** 尽管 $\nu_V^{(q)}$ 随 $q$ 变化,H3-1 恒等式

$$
M_2=\sum_k L_k=\int_A\rho_V\,dx
$$

的**分解结构对任意 $q$ 保持不变**;只有各 $L_k$ 的数值随 $q$ 变。这给了 H3-3B 一个稳定的记账框架:研究「$q\to\nu_V^{(q)}$」等价于研究「$q$ 如何在固定的模态划分上重新分配 variance mass」。

---

# Section 2 — Gaussian Proposal Extension

**定理 2.1（Gaussian proposal 下的 variance density 对数展开）。**
设

$$
p(x)=\mathcal N(x;0,I),\qquad q(x)=\mathcal N(x;m,\Sigma),\quad \Sigma\succ0,
$$

则在 $A$ 内部($\mathbf 1_A=1$ 处)

$$
\boxed{\
\log\frac{p(x)^2}{q(x)}
=-\frac12\,x^{\mathsf T}\Lambda\,x-x^{\mathsf T}\Sigma^{-1}m+C,
\qquad
\Lambda:=2I-\Sigma^{-1}.\ }
$$

其中常数 $C=\tfrac12 m^{\mathsf T}\Sigma^{-1}m-\tfrac d2\log(2\pi)+\tfrac12\log|\Sigma|$。

**推导(要求完整完成平方)。** 由

$$
p(x)^2=(2\pi)^{-d}\exp\!\big(-\lVert x\rVert^2\big),
\quad
q(x)=(2\pi)^{-d/2}|\Sigma|^{-1/2}\exp\!\Big(-\tfrac12(x-m)^{\mathsf T}\Sigma^{-1}(x-m)\Big),
$$

得

$$
\frac{p(x)^2}{q(x)}
=(2\pi)^{-d/2}|\Sigma|^{1/2}
\exp\!\Big(\underbrace{-\lVert x\rVert^2+\tfrac12(x-m)^{\mathsf T}\Sigma^{-1}(x-m)}_{=:E(x)}\Big).
$$

展开二次型 $(x-m)^{\mathsf T}\Sigma^{-1}(x-m)=x^{\mathsf T}\Sigma^{-1}x-2m^{\mathsf T}\Sigma^{-1}x+m^{\mathsf T}\Sigma^{-1}m$,并用 $m^{\mathsf T}\Sigma^{-1}x=x^{\mathsf T}\Sigma^{-1}m$(标量、$\Sigma^{-1}$ 对称):

$$
E(x)
=-x^{\mathsf T}x+\tfrac12x^{\mathsf T}\Sigma^{-1}x-x^{\mathsf T}\Sigma^{-1}m+\tfrac12 m^{\mathsf T}\Sigma^{-1}m
=-\frac12\,x^{\mathsf T}\big(2I-\Sigma^{-1}\big)x-x^{\mathsf T}\Sigma^{-1}m+\tfrac12 m^{\mathsf T}\Sigma^{-1}m.
$$

令 $\Lambda=2I-\Sigma^{-1}$、把与 $x$ 无关的项并入 $C$,即得箱内结果。∎

**注 2.2（与 H3-3A 枢纽闭式的对齐——必须核对）。** 代入 H3-3A 冻结协议 $\Sigma=I$、$m=\mu$:$\Lambda=2I-I=I$,于是

$$
\log\frac{p^2}{q}=-\tfrac12\lVert x\rVert^2-x^{\mathsf T}\mu+C'
=-\tfrac12\lVert x+\mu\rVert^2+C'',
$$

即 $\rho_V\propto\mathcal N(x;-\mu,I)$——**精确还原** H3-2/H3-3A 的镜像点闭式 $p^2/q=e^{\lVert\mu\rVert^2}\mathcal N(-\mu,I)$。本节的一般式是该闭式在「$\Sigma\neq I$」方向上的推广。

---

# Section 3 — Integrability Condition

Section 2 的对数展开只在 $A$ 内部逐点成立;要把 $\rho_V$ 当作(未归一)测度,必须先问它**是否可积**。

**命题 3.1（Gaussian proposal 下的合法性条件）。** 全空间积分

$$
\int_{\mathbb R^d}\frac{p(x)^2}{q(x)}\,dx<\infty
\quad\Longleftrightarrow\quad
\Lambda=2I-\Sigma^{-1}\succ0
\quad\Longleftrightarrow\quad
\boxed{\ \Sigma\succ\tfrac12 I.\ }
$$

**说明。** 被积函数 $\propto\exp(-\tfrac12x^{\mathsf T}\Lambda x-x^{\mathsf T}\Sigma^{-1}m)$ 是「二次型 + 线性项」的指数;线性项不影响收敛,故其在 $\mathbb R^d$ 上可积当且仅当二次型正定,即 $\Lambda\succ0$。而

$$
\Lambda\succ0
\iff \Sigma^{-1}\prec2I
\iff \Sigma\succ\tfrac12 I.
$$

**注 3.2（几何解释:proposal 尾部不能比 $p^2$ 更轻）。** $p(x)^2\propto\exp(-x^{\mathsf T}x)=\exp(-\tfrac12x^{\mathsf T}(2I)x)$,可视为「精度 $2I$、协方差 $\tfrac12 I$」的高斯。$p^2/q$ 可积要求 $q$ 的尾部**不轻于** $p^2$,即 $q$ 的精度 $\Sigma^{-1}$ 必须 $\prec2I$,亦即 $\Sigma\succ\tfrac12 I$。这正是 IS 的经典病理「proposal 尾部过窄导致二阶矩爆炸」在本设定下的精确边界。

**注 3.3（截断到失效集 $A$ 的情形——精确措辞）。** 我们真正关心的是**截断积分** $\int_A p^2/q\,dx$。
- 若失效集 $A$ **有界**,则 $\int_A p^2/q\,dx<\infty$ 恒成立(连续函数在有界集上可积),与 $\Lambda$ 是否正定无关。
- 但稀有事件的 $A$ 通常**无界**(半空间 $\{a^{\mathsf T}x\ge\beta\}$、尾部区域等)。此时 $\Lambda\succ0$($\Sigma\succ\tfrac12 I$)是保证可积的**充分且与失效几何无关**的条件;当 $A$ 在某个 $\Lambda$ 非正的方向上延伸至无穷时它同时是必要的。

因此把 $\boxed{\Sigma\succ\tfrac12 I}$ 作为「Gaussian proposal 下 variance geometry 的合法性条件」——在 H3-3B 扫描 $\Sigma$ 时,这是**不可越过的下界**:低于此界,$\nu_V^{(q)}$ 不是良定义的概率对象,任何 region descriptor 都失去意义。

---

# Section 4 — Closed-form Variance Geometry

在合法性条件 $\Lambda\succ0$ 下,可对 Section 2 的指数完成平方,得到 variance geometry 的**解析核**。

**定理 4.1（proposal 参数 → variance-geometry Gaussian 核）。** 设 $\Lambda=2I-\Sigma^{-1}\succ0$。则在**忽略截断**($\mathbf 1_A$)的意义下,

$$
\rho_V(x)\ \propto\ \mathcal N\big(x;\ \mu_V,\ \Sigma_V\big),
$$

其中

$$
\boxed{\
\Sigma_V=\Lambda^{-1}=\big(2I-\Sigma^{-1}\big)^{-1},
\qquad
\mu_V=-\Lambda^{-1}\Sigma^{-1}m.\ }
$$

**推导。** 取 $x$ 相关部分 $-\tfrac12x^{\mathsf T}\Lambda x-x^{\mathsf T}\Sigma^{-1}m$。配方

$$
-\tfrac12x^{\mathsf T}\Lambda x-x^{\mathsf T}\Sigma^{-1}m
=-\tfrac12(x-\mu_V)^{\mathsf T}\Lambda(x-\mu_V)+\text{const}
$$

匹配线性项要求 $\Lambda\mu_V=-\Sigma^{-1}m$,即 $\mu_V=-\Lambda^{-1}\Sigma^{-1}m$;二次项系数给出 $\Sigma_V=\Lambda^{-1}$。∎

**注 4.2（$\mu_V$ 的简化形式——广义镜像点）。** 利用 $\Lambda^{-1}\Sigma^{-1}=(\Sigma\Lambda)^{-1}=\big(\Sigma(2I-\Sigma^{-1})\big)^{-1}=(2\Sigma-I)^{-1}$,可得等价而更直观的形式

$$
\boxed{\ \mu_V=-(2\Sigma-I)^{-1}m.\ }
$$

它把 H3 的「镜像点 $-\mu$」推广为「广义镜像点」:proposal 均值 $m$ 经线性映射 $-(2\Sigma-I)^{-1}$ 得到 variance 核的中心。

**proposal 参数如何改变 variance geometry(本节结论)。**

> proposal 的两个自由度 $(m,\Sigma)$ 分别控制 variance geometry 的**位置**与**形状**:
> - **均值 $m$** → 把 variance 核中心移到广义镜像点 $\mu_V=-(2\Sigma-I)^{-1}m$;
> - **协方差 $\Sigma$** → 通过 $\Sigma_V=(2I-\Sigma^{-1})^{-1}$ 重塑 variance 核的扩散与朝向,并(经 Section 3)决定整个对象是否良定义。
>
> **$\Sigma$ 是 H3-3A 未曾触及的新杠杆**——H3-3A 固定 $\Sigma=I$ 时 $\Sigma_V\equiv I$(各向同性单位球);一旦放开 $\Sigma$,$\Sigma_V$ 成为可被 proposal 主动设计的**椭球**。

**注 4.3（三个 sanity check,建立对闭式的信任)。**

| 情形 | 参数 | $\Lambda$ | $\Sigma_V$ | $\mu_V$ | 独立验证 |
|---|---|---|---|---|---|
| $q=p$ | $m=0,\Sigma=I$ | $I$ | $I$ | $0$ | $p^2/q=p=\mathcal N(0,I)$ ✓ |
| H3-3A 冻结 | $m=\mu,\Sigma=I$ | $I$ | $I$ | $-\mu$ | 镜像点 $\mathcal N(-\mu,I)$ ✓ |
| 各向同性缩放 | $m=0,\Sigma=\sigma^2 I$ | $(2-\sigma^{-2})I$ | $\dfrac{I}{2-\sigma^{-2}}$ | $0$ | $\sigma^2\!>\!\tfrac12$;$\sigma^2\!\to\!\infty\Rightarrow\Sigma_V\!\to\!\tfrac12 I$($=\!\mathrm{Cov}(p^2)$);$\sigma^2\!\to\!\tfrac12^{+}\Rightarrow\Sigma_V\!\to\!\infty$ ✓ |

第三行给出清晰的物理直觉:proposal 越宽($\sigma^2\uparrow$),$p^2/q\to p^2/\text{const}\propto p^2$,故 $\Sigma_V$ 趋于 $p^2$ 自身的协方差 $\tfrac12 I$;proposal 逼近合法性边界($\sigma^2\to\tfrac12^{+}$),$\Sigma_V$ 发散——variance geometry 在失去良定义前先「摊平」。

**定理 4.4（MPP 锚定下的方差盲性,v2 增补）。** 设失效集 $A\subseteq\mathbb R^d$ 非空、闭、凸且 $0\notin A$,$x^*=\operatorname*{proj}_A(0)$,$\beta=\lVert x^*\rVert>0$,点级 alignment 距离 $D_L=\lVert x^*-x_L\rVert$。若 proposal 锚在 MPP,即 $m=x^*$,则对**任意**合法协方差 $\Sigma\succ\tfrac12 I$,$\rho_V$ 在 $A$ 上的最大值在 $x^*$ 处**唯一**取得:

$$
\boxed{\ x_L=x^*,\qquad D_L=0.\ }
$$

换言之,把 proposal 对准 MPP 时,variance 密度的峰必与 probability design point 重合,**与 $\Sigma$ 的选取无关**。该定理只以定理 2.1 的对数展开为输入,不需要 $\mu_V,\Sigma_V$ 的显式形式;反过来,它也构成 Section 4 闭式的一个独立 sanity check($m=x^*$ 时受约束最大必落在 $x^*$)。

**证明(坐标无关的一阶条件 + 凹性)。** 记 $\phi(x)$ 为 $\log\rho_V(x)=2\log p(x)-\log q(x)$ 中与 $x$ 相关的部分。由定理 2.1,

$$
\phi(x)=-\tfrac12x^{\mathsf T}\Lambda x-x^{\mathsf T}\Sigma^{-1}m+\text{const},\qquad
\Lambda=2I-\Sigma^{-1},
$$

$\phi$ 为二次多项式,$\nabla\phi(x)=-\Lambda x-\Sigma^{-1}m$,$\nabla^2\phi=-\Lambda$。

**(0) 良定性。** 合法性 $\Lambda\succ0$ 使 $\phi$ 严格凹且强制($\lVert x\rVert\to\infty$ 时 $\phi\to-\infty$);$A$ 非空闭保证最大值取得,严格凹保证最大元唯一,记 $x_L$。

**(1) $x^*$ 对任意 $\Sigma$ 满足一阶条件。** 代入 $m=x^*$ 并用 $\Lambda+\Sigma^{-1}=2I$:

$$
\nabla\phi(x^*)=-\Lambda x^*-\Sigma^{-1}x^*=-(\Lambda+\Sigma^{-1})x^*=-2x^*.
$$

由投影的变分不等式 $\langle -x^*,z-x^*\rangle\le0\ (\forall z\in A)$ 知 $-x^*\in N_A(x^*)$(法锥);法锥是锥,故 $\nabla\phi(x^*)=2(-x^*)\in N_A(x^*)$。关键在于 $m=x^*$ 使梯度的 $\Sigma^{-1}(x-m)$ 项在 $x^*$ 处**恒消失**——因此一阶条件对一切 $\Sigma$ 同时成立。

**(2) 凹性把驻点升级为全局最大。** 凸集上的凹函数:$x^*$ 为全局最大 $\iff \nabla\phi(x^*)\in N_A(x^*)$,已由 (1) 验证;严格凹给出唯一性。故 $x_L=x^*$。$\blacksquare$

**推论 4.5（$\Sigma=I$ 特例:纯投影恒等式）。** $\Sigma=I$ 时 $\rho_V\propto\mathcal N(-m,I)$,$x_L=\operatorname*{proj}_A(-m)$,于是定理 4.4 化为与 proposal 无关的几何恒等式

$$
\operatorname*{proj}_A\!\big(-\operatorname*{proj}_A(0)\big)=\operatorname*{proj}_A(0)
\qquad(\forall\ \text{闭凸 }A,\ 0\notin A).
$$

*初等证明(备选).* 变分不等式给 $\langle x^*,z\rangle\ge\beta^2$;Cauchy–Schwarz 给 $\beta\lVert z\rVert\ge\langle x^*,z\rangle\ge\beta^2$,故 $\lVert z\rVert\ge\beta$;于是

$$
\lVert z+x^*\rVert^2-\lVert 2x^*\rVert^2=\lVert z\rVert^2+2\langle x^*,z\rangle-3\beta^2\ \ge\ \beta^2+2\beta^2-3\beta^2=0,
$$

等号仅在 $z=x^*$;凸集投影唯一,得证。$\square$

**注 4.6（$\tfrac12 I$ 不是巧合——同一不等式的三顶帽子,v2 增补）。** 命题 3.1 的矩阵不等式 $\Sigma^{-1}\preceq2I$(即 $\Lambda\succeq0$,即 $\Sigma\succeq\tfrac12 I$)同时编码三件事:

1. **可积性**(命题 3.1):$\rho_V=p^2/q$ 是正规高斯核当且仅当 $\Lambda\succ0$;
2. **对数凹性**:$\log\rho_V$ 的 Hessian 为 $-\Lambda$;
3. **证明常数**:定理 4.4 步骤 (2) 把「$x^*$ 恒成立的驻点性」升级为全局最大所需的凹性正是 $\Lambda\succeq0$。

因子 2 恰为 $p$ 进入 $\rho_V$ 的幂次:$\rho_V$ 的精度 $=2\cdot\mathrm{prec}(p)-\mathrm{prec}(q)=2I-\Sigma^{-1}$。三种情形:严格 $\Sigma\succ\tfrac12I$ 时定理 4.4 成立且 $x_L$ 唯一;边界 $\Sigma=\tfrac12I$ 时 $\Lambda=0$、$\phi$ 退化为仿射、$\rho_V$ **不可积**——其上确界虽仍形式地落在 $x^*$,但对象已非概率密度,被合法性条件正确排除;$\Sigma\prec\tfrac12I$ 时框架失效。**合法性界、对数凹门槛与盲性定理的证明常数是同一个结构事实,而非巧合。**

**注 4.7（凸性必要;多模态并集的伪 mismatch,v2 增补）。** 定理中凸性不可去:反例 $A=\{z:\lVert z\rVert\ge1\}$(环形,原点在洞内),取 $x^*=e_1$,则镜像点 $-e_1$ 本身落在 $A$ 内,$\operatorname*{proj}_A(-e_1)=-e_1\neq x^*$,$D_L=2>0$。一般地,失效机制是 $A$ 相对线段 $[-x^*,x^*]$ 的非凸性(「包裹」)。对多模态并集 $A=\bigsqcup_k A_k$(各 $A_k$ 凸、并集非凸):

- **并集级**计算(单一锚 $m$):即使取 $m=x^*_{\text{union}}$,镜像点也可能落入另一模态,投影发生跨模态切换,产生纯属几何切换的非零 $D_L$——按 frozen B/S1/S2 锚点粗估可达 $\approx3.2$,它不是任何单模态的真实几何性质;
- **逐模态**计算(H3 语料约定,shared anchor):每个模态内的 $x_{L,k}$ 是该凸模态上真实的受约束最大——偏移锚下可与 $x_k^*$ 分离(那是真实几何,frozen B/S2 的 $d_L=0.775$ 即此类),MPP 锚下则恒重合(定理 4.4)。

union 级对照计算已列入 Phase 1 任务书,用以实证展示这一伪迹并反向证成逐模态约定。

---

# Section 5 — Topology Truncation

**必须强调:真实 hybrid rare event 中,$\nu_V^{(q)}$ 不是完整 Gaussian。** Section 4 的 $\mathcal N(\mu_V,\Sigma_V)$ 只是**忽略 $\mathbf 1_A$ 的解析核**。加回失效拓扑后,真正的对象是**截断高斯**:

$$
\boxed{\
\nu_V^{(q)}(dx)\ \propto\ \mathbf 1_A(x)\,\mathcal N\big(x;\mu_V,\Sigma_V\big)\,dx
\ \equiv\ \mathcal N(\mu_V,\Sigma_V)\,\big|\,A,\ }
$$

其中 $A$ 由 **failure topology 决定**(注意:此处 $A$ 是失效事件集合,与 Section 2 的矩阵 $\Lambda$ 无关——这正是本文把矩阵改记 $\Lambda$ 的原因)。

**failure topology 如何进一步改变 variance geometry。** 完整的 variance geometry 是「解析椭球核 $\cap$ 几何失效区」的相互作用产物,以下三种拓扑效应叠加在 Gaussian 核之上:

- **topology boundary(边界位置)**:$A=\{$事件跳过/执行$\}$ 的边界把 Gaussian 核**切断**。若边界穿过核的高密度区,截断显著改变 $\nu_V^{(q)}$ 的质心与扩散;若边界远离核,则截断近乎无影响(此时 $\nu_V^{(q)}\approx\mathcal N(\mu_V,\Sigma_V)$)。
- **curvature(边界曲率)**:弯曲边界($\beta\kappa\gtrsim1$)使截断区呈月牙/凹形,$\nu_V^{(q)}$ 被挤向曲率一侧——这是 H3-2 中 $x^*\neq x_L$ 分离在弯曲体制下出现的几何根源,现在被纳入「椭球核被弯曲边界截断」的统一图景。
- **mode competition(多模竞争)**:$A=\sqcup_k A_k$ 时,$\nu_V^{(q)}$ 在各模态上的质量按 $L_k$ 分配(Section 1 不变量)。proposal 只对准部分模态时,未覆盖模态吃到 IS 权重放大,其截断核可主导整体——H3-1 的 variance leakage 在此表现为「某个 $A_k$ 上的截断椭球核异常放大」。

**与 H3-3A 的衔接(HDR 从「球」升级为「椭球」)。** H3-3A 中 $\Sigma_V=I$,HDR $\mathcal L_\eta$ 是**球** $\{\lVert x-\mu_V\rVert^2\le\chi^2_d(\eta)\}$ 与 mode 边界的交集,是否 $D_\eta>0$ 完全取决于 $\lVert x^*-\mu_V\rVert$ 与 $\chi^2_d(\eta)^{1/2}$($d=4,\eta=0.8$ 时 $=2.45$)的相对大小,故所有 case 都落入球内($D_{0.8}\equiv0$)。在 H3-3B 的一般 $\Sigma_V$ 下,HDR 的解析核是**椭球**

$$
\mathcal L_\eta\ \approx\ \big\{x\in A:\ (x-\mu_V)^{\mathsf T}\Sigma_V^{-1}(x-\mu_V)\le\chi^2_d(\eta)\big\},
$$

$x^*$ 是否被排除取决于**马氏距离** $(x^*-\mu_V)^{\mathsf T}\Sigma_V^{-1}(x^*-\mu_V)$。这给出 H3-3A §7.1 遗留问题的理论出路:**通过设计 $\Sigma$ 使 $\Sigma_V$ 在 $x^*$ 方向收窄**,可让椭球 HDR 排除 MPP——即协方差杠杆为「触发区域级分离」提供了除「平移 $q$」之外的第二条路径。**能否真正触发是 H3-3B 实验的检验对象(见 Section 7 假设),本节不作断言。**

**注 5.1(定理 4.4 对上述「第二条路径」的前提修正,v2 增补)。** 上段设想有一个此前未被言明的隐含前提:**proposal 不能锚在 MPP**。若 $m=x^*$ 且 $A$ 凸,则由定理 4.4,$x_L=x^*$ 对一切合法 $\Sigma$ 成立,即 $x^*$ 是 $\rho_V$ 在 $A$ 上的唯一最大元;此时任何 HDR $\mathcal L_\eta$($\eta<1$)必含 $x^*$,故 $D_\eta\equiv0$——**「椭球 HDR 排除 MPP」在 MPP 锚定下不可能,无论 $\Sigma$ 如何设计**。「收窄 $\Sigma_V$ 使 HDR 甩开 $x^*$」只有在**偏移锚定**($m\neq x^*$,如语料基线 $\mu_{base}$:此时 $x_L=\operatorname*{proj}_A(-m)\neq x^*$,核峰与 MPP 分离)的前提下才成为可行机制。这与 H3-3A 的经验($D_{0.8}\equiv0$,frozen 协议恰为偏移锚但核宽 $\Sigma_V=I$)和 Phase 1 任务书的主约定选择($\mu_{base}$)一致。

---

# Section 6 — Region-Level Geometry Representation

继承 H3-3A 的区域级表示,并针对「$D_\eta\equiv0$ 使 $D_\eta/S_\eta$ 失去区分力」这一 H3-3A 局限,新增两个描述子。**本节只提出表示方式,不声称已发现所有 regime。**

### 继承(H3-3A)

$$
\textbf{Separation}\quad D_\eta=\mathrm{dist}(x^*,\mathcal L_\eta),
\qquad
\textbf{Spread}\quad R_\eta=\sqrt{\mathbb E_{\nu_V}\!\big[\lVert X-m_\eta\rVert^2\mid X\in\mathcal L_\eta\big]}.
$$

### 新增:Region center shift

$$
\boxed{\ C_\eta=\lVert m_\eta-x^*\rVert,\ }
$$

其中 $m_\eta$ 为 variance-critical region 的加权质心。

**注 6.1（为什么需要 $C_\eta$——它补上了 $D_\eta$ 的盲区）。** $D_\eta$ 度量 $x^*$ 到区域**最近点**的距离,故 $x^*$ 一旦落入 $\mathcal L_\eta$ 内部即 $D_\eta=0$——这正是 H3-3A 全部 24 rows 的情形,使 $D_\eta$(与 $S_\eta$)在该配比下**无区分力**。而 $C_\eta=\lVert m_\eta-x^*\rVert$ 度量 $x^*$ 到区域**质心**的距离:**即便 $D_\eta=0$(MPP 在区域内),只要区域中心不恰好压在 MPP 上,$C_\eta>0$**。因此 $C_\eta$ 能刻画 $D_\eta$ 无法分辨的「区域整体偏移」。在 Section 4 闭式下,截断温和时 $m_\eta\approx\mu_V$,故

$$
C_\eta\ \approx\ \lVert\mu_V-x^*\rVert=\big\lVert(2\Sigma-I)^{-1}m+x^*\big\rVert,
$$

是一个**由 proposal $(m,\Sigma)$ 解析可控**的量——这为 Section 7 的 Hypothesis 1 提供了可推导的支点。

### 新增:Normalized mismatch

$$
\boxed{\ G_\eta=\frac{C_\eta}{R_\eta+\epsilon},\ }\qquad \epsilon=10^{-8}.
$$

**注 6.2（$G_\eta$ 与 H3-3A $S_\eta$ 的关系）。** $G_\eta$ 是「以区域扩散为单位度量的中心偏移」,与 H3-3A 的 $S_\eta=D_\eta/(R_\eta+\varepsilon)$ 平行,但用 center shift $C_\eta$ 替换 nearest-point separation $D_\eta$。由于 $D_\eta\equiv0$ 使 $S_\eta\equiv0$ 失效,$G_\eta$ 是其自然替代:即使区域包含 MPP,$G_\eta$ 仍能量化「偏移相对于弥散的显著程度」。

**表示方式:四类定性形态(仅提出,不声称已全部观测到)。**

| 定性类别 | $C_\eta$(center shift) | $R_\eta$(spread) | $G_\eta$ | 直观含义 |
|---|---|---|---|---|
| **aligned compact** | 小 | 小 | 小 | 区域紧,且中心贴近 MPP |
| **aligned diffuse** | 小 | 大 | 很小 | 区域弥散,但中心仍贴近 MPP（形态上对应 H3-3A C1 plateau） |
| **shifted compact** | 大 | 小 | 大 | 区域紧,但整体明显偏离 MPP（形态上对应 H3-3A B 尖峰月牙的目标态） |
| **shifted diffuse** | 大 | 大 | 中等 | 区域弥散且偏离 |

**注 6.3（诚实边界)。** H3-3A 的冻结配比($\Sigma=I$)只产生 `aligned/overlap diffuse` 一类(因 $D_\eta\equiv0$、$\Sigma_V=I$)。上表的 `shifted` 两类**需要 H3-3B 引入的协方差自由度**才**可能**进入(Section 5 注),但**它们是否可达、在何种 $(m,\Sigma,\beta,\kappa)$ 下可达,是 H3-3B 实验必须回答的问题**。此处**仅给出描述子与分类坐标**,不声称已发现任何具体 regime,更不声称四类都存在。

---

# Section 7 — H3-3B Research Hypotheses

以下**正式提出待验证假设**。逐条为 hypothesis,**不是**已证结论;凡有推导支撑者,只把推导标为「特例证据」,不据此升级整体假设。

### Hypothesis 1（proposal 系统性地塑造 $\nu_V^{(q)}$）

> proposal $q$ 会**系统性**地改变 $\nu_V^{(q)}$——即变化是由 $(m,\Sigma)$ 决定的**确定性映射**,而非随机涨落。

**部分解析证据(不构成对一般假设的证明)。** Section 4 已**推导**:在 Gaussian proposal + 忽略截断的情形,$(\mu_V,\Sigma_V)=\big(-(2\Sigma-I)^{-1}m,\ (2I-\Sigma^{-1})^{-1}\big)$ 是 $(m,\Sigma)$ 的确定函数——在该受限情形内 H1 **可证**。但对**一般(非 Gaussian)hybrid system + topology 截断**,「系统性」是否保持,仍是待验证的假设(截断与曲率可能引入 proposal 无法解析预测的形变)。

### Hypothesis 2（variance geometry 可由 region-level descriptors 描述）

> variance geometry 可被低维 region-level descriptors
> $$(C_\eta,\ R_\eta,\ G_\eta)$$
> 充分描述(就 H3-3B 关心的目的而言)。

这是一个**表示充分性**假设:上述三元组是否携带了刻画 $\nu_V^{(q)}$ 所需的信息,尚未验证。

### Hypothesis 3（variance geometry mismatch 与 VRF 关联）

> variance geometry 的 mismatch(以 $C_\eta$ 或 $G_\eta$ 度量)与
> $$\mathrm{VRF}$$
> 存在关联——mismatch 越大,IS 相对 MC 的方差改善越差。

H3-1 已实验证实「leakage 与 VRF 强相关」(Spearman $-1.0$);H3 现把这一关联重述为**几何 mismatch descriptor 与 VRF 的关联**。但针对 $(C_\eta,G_\eta)$ **这一具体几何度量**的相关性尚未测量,故写成假设。

> **三条假设一律写成待验证形式,不得写成已证明结论。** H3-3B 实验的任务即是在 frozen 记账框架下检验 H1–H3。

---

# Section 8 — Relation to Future ML Direction

**本节只描述接口,不设计 ML 模型。**

**未来目标(future work)。** 学习映射

$$
(\text{system},\,q)\ \longrightarrow\ \text{variance geometry representation}.
$$

可能的两种预测目标(仅列举接口,不预设孰优、不设计架构):

- **预测 region-level descriptors** $(C_\eta,R_\eta,G_\eta)$——低维、与 Section 6 表示直接对接;
- **预测整个测度** $\nu_V^{(q)}$——高维、信息更全。

**与前序 ML 工作的关系。** 现有 frozen `ml_b1_first_order_geometry` snapshot 属于 first-order geometry 预测,**未修改**;variance geometry representation 的学习是**其后续、独立的方向**,本文档不进入实现。

> **明确:H3-3B 阶段不训练、不设计、不评测任何 ML predictor。** 上述仅为「未来该学什么对象」的接口声明。

---

# Section 9 — Claim Boundary

**当前没有证明以下任何一条(不得在任何 H3 文档中声称):**

- ❌ **所有 proposal 都存在 mismatch**——Gaussian 闭式给出 $\nu_V^{(q)}$ 随 $q$ 的确定性变化,但「一般系统下 proposal 必产生 variance-geometry mismatch」未证;真机 C1/C2 未复现稳定 mismatch(沿用 Final Summary §5,不恢复旧 $d_L=1.136$)。
- ❌ **Gaussian extension 覆盖所有 hybrid system**——Section 2–4 严格限定 $p=\mathcal N(0,I)$、$q=\mathcal N(m,\Sigma)$ 且忽略截断;真实 hybrid 的 $\nu_V^{(q)}$ 是**截断**对象(Section 5),非完整 Gaussian。
- ❌ **已获得完整 variance regime map**——本文档只给出 descriptors $(C_\eta,R_\eta,G_\eta)$ 与四类分类坐标;`shifted` 两类是否可达、regime 边界在何处,均未扫描、未断言。
- ❌ **已完成 ML prediction**——未进入 ML 阶段(Section 8 仅为接口)。

**当前贡献(本文档的全部主张)。**

> 建立 **proposal-dependent variance geometry 的理论框架**:
> 1. 将研究对象由 $A$-决定的 $\nu_V$ 明确为 $(\text{system},q)$-决定的 $\nu_V^{(q)}$(Section 1);
> 2. 给出 Gaussian proposal 下的完整闭式——variance density 对数展开(定理 2.1)、合法性条件 $\Sigma\succ\tfrac12 I$(命题 3.1)、variance-geometry 核 $(\mu_V,\Sigma_V)$(定理 4.1),并核对其退回 H3-3A 镜像点闭式(注 2.2、注 4.3);
> 3. 阐明 topology 截断如何把解析椭球核塑造为真实 $\nu_V^{(q)}$(Section 5),并把 HDR 由「球」推广为「椭球」,给出「协方差杠杆触发区域级分离」的理论路径;
> 4. 提出区域级描述子 $C_\eta,G_\eta$(Section 6),补上 H3-3A 中 $D_\eta\equiv0$ 的盲区;
> 5. 将后续实验凝练为三条**可检验假设** H1–H3(Section 7),并声明 ML 接口(Section 8)。
> 6. **(v2 增补)** 证明 **MPP 锚定方差盲性定理**(定理 4.4):凸失效集 + $m=x^*$ 时 $x_L=x^*$ 对一切合法 $\Sigma$ 成立,并给出纯投影恒等式(推论 4.5);阐明合法性界 $\tfrac12 I$ 同时是可积性、对数凹性与该定理的证明常数(**注 4.6**,三顶帽子);界定凸性前提与多模态并集伪 mismatch(注 4.7);据此修正 Section 5 协方差杠杆路径的前提——触发区域级分离需要偏移锚定(注 5.1)。
>
> 以上均为**框架与推导**;一切经验性结论留待 H3-3B 实验,在 frozen 记账框架 $M_2=\sum_k L_k$ 下检验。

---

```
H3-3B THEORY EXTENSION — FOUNDATION (no experiments)

Object upgrade:
  H3-1  P_k != M_k            (mass != variance)
  H3-2  x*  != x_L            (prob geom != var geom)
  H3-3A x_L  -> nu_V, L_eta   (point unstable, region stable; Sigma = I fixed)
  H3-3B (system, q) -> nu_V^(q)   (proposal shapes variance geometry)

Gaussian proposal  p = N(0,I),  q = N(m, Sigma):
  log p^2/q = -1/2 x^T Lambda x - x^T Sigma^{-1} m + C,   Lambda = 2I - Sigma^{-1}
  legitimacy:      Sigma > 1/2 I   (<=> Lambda > 0)
  variance core:   Sigma_V = Lambda^{-1},   mu_V = -(2 Sigma - I)^{-1} m
  reduces to H3-3A mirror point at Sigma = I, m = mu  ->  nu_V = N(-mu, I)

Truncation:  nu_V^(q) ∝ 1_A * N(mu_V, Sigma_V)  =  N(mu_V, Sigma_V) | A
  HDR: ball (H3-3A) -> ellipsoid (general Sigma_V); covariance is a new lever.

Region descriptors:  keep D_eta, R_eta;  add C_eta = ||m_eta - x*||,
  G_eta = C_eta / (R_eta + eps).   (C_eta covers the D_eta ≡ 0 blind spot.)

Hypotheses (to test, NOT proven):
  H1 proposal systematically shapes nu_V^(q)  [Gaussian core: provable special case]
  H2 (C_eta, R_eta, G_eta) describe variance geometry
  H3 geometry mismatch correlates with VRF

NOT claimed: universal mismatch; Gaussian covers all hybrids;
  complete regime map; ML prediction done.

Blindness theorem (v2):  A convex, m = x*  =>  x_L = x*  (any legit Sigma)
  first-order + concavity;  1/2 I = integrability = log-concavity = proof const
  corollary: proj_A(-proj_A(0)) = proj_A(0);
  region-level separation (D_eta > 0) needs offset anchor, not just Sigma design.

Contribution: a theoretical framework for proposal-dependent variance geometry.
  All empirical claims deferred to H3-3B experiments.
```

---

## Frozen references（只读依据,未修改任何 frozen artifact）

| 角色 | 路径 | 状态 |
|---|---|---|
| H3 状态冻结总结 | `docs/phase_h/H3_Final_Summary.md` | H3-3A COMPLETE / frozen |
| variance leakage 理论 | `H3_Theory_Consolidation_Variance_Leakage.md` | COMPLETE |
| set-valued variance geometry | `docs/phase_h/H3_3A_set_valued_variance_geometry.md` | COMPLETE |
| H3-2 adaptive Geometry-IS | `docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md` | FROZEN(`a03b364→fa7c476`) |
| frozen H3-2 dataset | `tests/data/h3_2_leakage_point_dataset_v1.json` | FROZEN,SHA-256 `29e09cb6…`,**未修改** |
| frozen ML-B1 snapshot | `tests/data/ml_b1_first_order_geometry_v1.json` | FROZEN,**未修改** |
| **本文件** | `docs/phase_h/H3_3B_Theory_Extension.md` | **THEORY FOUNDATION（实验未开始）** |

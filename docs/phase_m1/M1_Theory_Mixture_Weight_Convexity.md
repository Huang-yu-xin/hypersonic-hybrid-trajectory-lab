# M1 Theory — Fixed-Component Mixture-Weight Convexity（M1-1 审计文档）

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems
> **Method Track:** M1 — Closed-Loop Variance-Geometry Adaptive Importance Sampling
> **Document type:** Theory audit / preregistered numerical verification
> **Task section:** `M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md` §14（Mixture-Weight Theory Task）、§29.4（mixture-weight objective 测试）
> **H3 frozen tag:** `RareTopo-H3-v1.0`（commit `5faef86b9d0ff35eb2cee762ec24a363796f6ce1`）
> **Date:** 2026-08-26
> **Status:** ✅ AUDIT PASS — 推导完成，V1–V6 数值验证全部通过（2026-08-26，见 §12）

---

# 0. 本审计文档的边界

本文件只审计 task §14.1 的候选定理：

> fixed-component mixture second moment 在 simplex 上是 mixture weights 的凸函数。

审计范围：

1. 一阶导数公式（task §14.1 第一式）；
2. 二阶导数公式（task §14.1 第二式）；
3. Hessian 半正定性 → 凸性；
4. 使公式成立的 regularity 条件（task 原文 "在 denominator 正且积分有限的 regularity 条件下" 的具体化）；
5. 有限样本目标函数与两阶段协议（task §14.2、§18 防火墙衔接）。

本审计文档**不做**：

- 不扩大 H3 theorem scope（task §4.2）；
- 不声称"该优化在 component set 上也最优"（task §4.6：v0 不自由优化 \(m_k,\Sigma_k,\pi_k,K\)）；
- 在 §12 数值验证通过之前，不把本定理写入任何 frozen claim set（task §14.1 末尾的明确指令）。

---

# 1. Setup 与记号

固定组件密度 \(\{q_j\}_{j=1}^{J}\)，定义：

\[
q_\pi(x)=\sum_{j=1}^{J}\pi_j q_j(x),
\qquad
\pi\in\overline\Delta_J=\left\{\pi_j\ge0,\ \sum_j\pi_j=1\right\},
\]

\[
M_2(\pi)=\int_A\frac{p(x)^2}{q_\pi(x)}\,dx,
\]

其中 \(A=\bigsqcup_k A_k\) 是 failure set（topology 分解继承 H3，task §2.1），\(p\) 是 target density。

记号：\(\Delta_J^\circ\) 表示开 simplex（所有 \(\pi_j>0\)）。\(\mathbf 1\) 为全 1 向量。

## 1.1 继承的 H3 语义

- 标准化设计空间 \(z\sim\mathcal N(0,I)\)；
- v0 族：高斯组件、冻结 base covariance（unit \(I\)，task §8.3），因此组件密度 \(q_j>0\) **在 \(\mathbb R^d\) 上逐点成立**（不是 a.e.，是处处）；
- \(M_2\) 是 second moment，不是 probability mass（H3 firewall：\(q\) 改变 variance geometry 是本方法线的出发点）。

---

# 2. 候选定理的形式陈述（Task §14.1）

**候选定理 C1（fixed-component mixture second moment 的权重凸性）。**
设组件密度 \(q_j\ge0\)，且在 \(A\) 上 \(q_\pi>0\)、相关积分有限，则：

\[
\frac{\partial M_2}{\partial\pi_j}
=
-\int_A\frac{p(x)^2q_j(x)}{q_\pi(x)^2}\,dx,
\tag{T1}
\]

\[
\frac{\partial^2M_2}{\partial\pi_j\partial\pi_\ell}
=
2\int_A\frac{p(x)^2q_j(x)q_\ell(x)}{q_\pi(x)^3}\,dx,
\tag{T2}
\]

且对任意 \(v\in\mathbb R^J\)：

\[
v^\top\nabla^2M_2(\pi)\,v
=
2\int_A\frac{p(x)^2\left(\sum_j v_jq_j(x)\right)^2}{q_\pi(x)^3}\,dx\ \ge0,
\tag{T3}
\]

即 \(M_2\) 在 simplex 上 convex。

**审计结论（§3–§5 推导后的正式表述）：**

- (T1) 与 (T2) 是**逐点恒等式**：在 \(q_\pi>0\) 处对积分核的导数直接计算即得；
- 使"导数可穿过积分号"（dominated convergence, DCT）成立、从而使 (T1)(T2) 成为**真导数**的充分条件：存在 \(\pi\) 的邻域 \(U\)，使得被积函数族在 \(U\) 上有一致可积 domination（见 §4–§6 具体构造）；
- (T3) 是**无条件恒等式**：被积函数主值非负（在第三个幂次积分有限的区域上），因此凸性是结构性的。

---

# 3. 一阶导数：推导与 DCT justification

## 3.1 形式推导

\(\pi\mapsto q_\pi(x)\) 是仿射的，\(\partial q_\pi(x)/\partial\pi_j=q_j(x)\)。对 \(M_2\) 的积分核求导：

\[
\frac{\partial}{\partial\pi_j}\frac{p^2}{q_\pi}
=
p^2\cdot\frac{-q_j}{q_\pi^2}
=
-\frac{p^2q_j}{q_\pi^2}.
\]

（在 \(q_\pi>0\) 处，逐点成立。）

## 3.2 积分与求导交换

**条件 G1（一阶 domination）。** 对固定 \(\pi\)，存在其邻域 \(U\ni\pi\) 与可积函数 \(g_1\)，使对所有 \(\sigma\in U\)、\(x\in A\)：

\[
\left|\frac{p(x)^2q_j(x)}{q_\sigma(x)^2}\right|
\le g_1(x),
\qquad
\int_A g_1(x)\,dx<\infty.
\]

则 (T1) 成立（DCT 标准形式：对 \(\sigma\) 在 \(U\) 内沿 \(e_j\) 方向作差商，被差商控制的项收敛）。

**G1 的充分分解（构造性）。** 若存在 \(\delta>0\) 使 \(U=\{\sigma:\ \sigma_j\ge\delta\}\) 且定义 \(\bar q=\sum_\ell q_\ell\)，则：

\[
q_\sigma(x)\ge\delta\sum_\ell q_\ell(x)=\delta\,\bar q(x),
\qquad
q_j(x)\le\bar q(x),
\]

于是：

\[
\left|\frac{p^2q_j}{q_\sigma^2}\right|
\le
\frac{p^2\bar q}{\delta^2\bar q^2}
=
\frac{p^2}{\delta^2\,\bar q}.
\]

故只需 **G1'**：\(\int_A p^2/\bar q\,dx<\infty\)。对 Gaussian 族（§6）成立。

> 注意 G1' 与 \(\pi\) 无关，只与组件集合有关——这使一阶公式在**闭 simplex 上**（含权重为 0 的边界点）依然成立（在 §7 讨论边界方向的含义）。

---

# 4. 二阶导数：推导与 DCT justification

## 4.1 形式推导

对 (T1) 的被积函数再对 \(\pi_\ell\) 求导：

\[
\frac{\partial}{\partial\pi_\ell}
\left(-\frac{p^2q_j}{q_\pi^2}\right)
=
-p^2q_j\cdot\frac{-2q_\ell}{q_\pi^3}
=
2\frac{p^2q_jq_\ell}{q_\pi^3}.
\]

得到 (T2)。对称性 \(j\leftrightarrow\ell\) 显然，Hessian 对称。

## 4.2 二阶 domination

**条件 G2。** 存在 \(\pi\) 的邻域 \(U\) 与可积 \(g_2\)，使对所有 \(\sigma\in U\)：

\[
\frac{p(x)^2q_j(x)q_\ell(x)}{q_\sigma(x)^3}\le g_2(x),\qquad
\int_A g_2(x)\,dx<\infty.
\]

**G2 的充分分解。** 在 \(U=\{\sigma:\sigma_j\ge\delta,\ \sigma_\ell\ge\delta\}\) 上，用与 §3.2 相同的 \(\bar q\) 技术：

\[
\frac{p^2q_jq_\ell}{q_\sigma^3}
\le
\frac{p^2\bar q^2}{\delta^3\bar q^3}
=
\frac{p^2}{\delta^3\,\bar q}.
\]

因此同一条件 **G1'** 同时保证二阶导可穿过积分号（对**开 simplex 内部**的每一点，取 \(\delta=\min_j\pi_j>0\)）。

**关键结论：**

> 在 G1' 下，\(M_2\in C^2(\Delta_J^\circ)\)，且 (T1)(T2) 在开 simplex 上逐点成立。

---

# 5. Hessian 半正定 → 凸性

## 5.1 主值恒等式

\[
v^\top\nabla^2M_2(\pi)v
=
\sum_{j,\ell}v_jv_\ell\cdot
2\int_A\frac{p^2q_jq_\ell}{q_\pi^3}\,dx
=
2\int_A\frac{p(x)^2\left(\sum_jv_jq_j(x)\right)^2}{q_\pi(x)^3}\,dx.
\]

被积函数对每个 \(x\in A\) 都是「非负数 × 平方」→ 主值 \(\ge0\)（对任意 \(v\)，不只 simplex 方向）。因此当第三个幂次积分有限时：

\[
\nabla^2M_2(\pi)\succeq0.
\tag{T3}
\]

## 5.2 凸性结论

**定理 1（开 simplex 凸性）。** 在 G1' 下，\(M_2\) 在 \(\Delta_J^\circ\) 上 convex。

**定理 2（闭 simplex 凸性）。** 若 \(M_2\) 可连续延拓到 \(\overline\Delta_J\)（即边界极限有限；Gaussian 族自动满足，§6），则 \(M_2\) 在 \(\overline\Delta_J\) 上 convex。

证明：\(\Delta_J^\circ\) 上的凸性经极限传递——对 \(a,b\in\overline\Delta_J\)，取序列 \(a_n,b_n\in\Delta_J^\circ\) 收敛，凸性不等式 \(M_2(\lambda a_n+(1-\lambda)b_n)\le\lambda M_2(a_n)+(1-\lambda)M_2(b_n)\) 两边取极限即得。

## 5.3 严格凸与唯一性

对 simplex 方向（\(\sum_jv_j=0\)）有：

\[
v^\top\nabla^2M_2\,v=0
\iff
\sum_jv_jq_j(x)=0\ \text{a.e. on }A.
\]

因此：

- 若组件函数 \(\{q_j|_A\}\) **仿射无关**（在 \(A\) 上不存在非零 \(v\)，\(\sum v_j=0\)，使 \(\sum v_jq_j=0\) a.e.），则 Hessian 在 simplex 平面方向上正定 → **极小值点唯一**；
- 若组件在 \(A\) 上退化重合（如 \(q_1=q_2\)，§7.3），则在对应方向上是 flat 的（Hessian 零方向）。

这是 §29.4「optimizer result independent of initialization」的理论保证来源。

---

# 6. Gaussian 族的具体 regularity 包络（v0 实例化）

v0 族（task §8.2/§8.3）：\(p=\varphi(x)=\mathcal N(0,I)_d\)，\(q_j=\mathcal N(m_j,I)\)，\(A\subseteq\mathbb R^d\) 任意可测。

**引理。** 对任意有限组件集合 \(\{m_j\}\)，G1' 成立：

\[
\int_A\frac{p^2}{\bar q}\,dx
\le
\int_{\mathbb R^d}\frac{p^2}{\bar q}\,dx<\infty.
\]

验证（尾部指数）：\(\bar q\ge q_1\)，而：

\[
\frac{p^2}{q_1}
=
(2\pi)^{-d/2}
\exp\left(-\frac{\|x\|^2}{2}-m_1^\top x+\frac{\|m_1\|^2}{2}\right),
\]

指数部分 \(\sim-\|x\|^2/2-\|x\|\|m_1\|\to-\infty\) → 可积。因此对 Gaussian 族：

- (T1) 在闭 simplex 上成立（一阶公式处处有效）；
- (T2)(T3) 在**开 simplex** 上成立；
- \(M_2\in C^1(\overline\Delta_J)\)、\(M_2\in C^2(\Delta_J^\circ)\)、凸于 \(\overline\Delta_J\)。

**边界半径的示例性失败模式（供审计记录，不改变结论）：** 若取 \(J=1\)、\(m_1=0\)，则 \(q_\pi=\varphi\)，二阶被积函数 \(p^2q_1^2/q_\pi^3=\varphi^2\varphi/\varphi^3=1/\varphi\to\infty\)——Hessian 在退化单组件点上不存在。这与"Hessian 只在开 simplex 上成立"一致：\(J=1\) 时 simplex 就是单点，没有开邻域。二阶公式的边界失效不影响一阶公式与凸性结论。

---

# 7. 边界行为与退化情形

## 7.1 权重归零方向的物理解释

\(\pi_j\to0\) 时 \(q_\pi\to q_{-j}=\sum_{\ell\ne j}\pi_\ell q_\ell\)（归一化意义下），且：

\[
\lim_{\pi_j\downarrow0}\frac{\partial M_2}{\partial\pi_j}
=
-\int_A\frac{p^2q_j}{q_{-j}^2}\,dx
\le0.
\]

含义：若组件 \(j\) 在 \(A\) 上贡献密度且当前权重为 0，则沿该方向 M2 下降 → 边界点不可能是（无 floor 时的）最优解；最优解要么在内部（梯度常数），要么受 floor 约束（§8）。这正是 closed-loop 中"给 missing mode 加一个组件"的数学基础之一——但 M1-1 不在此证明 birth 规则的任何内容（那是 M1-3 的实验问题）。

## 7.2 闭 simplex 上二阶失效的方向

在边界点 \(\pi_j=0\)，Hessian 的 \(j\) 相关项被积函数 \(p^2q_j^2/q_\pi^3\) 的积分可能发散（二阶差商无界，见 §6 示例）。该发散是**朝凸方向的发散**（单向导数 \(+\infty\) 或 \(-(-\infty)\) 与凸性相容）：凸函数在支撑点可允许不可微。

## 7.3 退化重合组件

若 \(q_j=q_\ell\)，则对方向 \(v=e_j-e_\ell\)：

\[
v^\top\nabla^2M_2v=0,\qquad
M_2(\pi)\ \text{沿}\ \pi_j+\pi_\ell\ \text{不变}.
\]

即权重在重合组件之间的再分配不改变 second moment——凸而不严格凸。数值上应观察到 SLSQP 收敛到某个等价类内的点（§12 V6 验证）。

---

# 8. 权重极小化问题的 KKT 刻画

最小化问题（含显式 floor \(c_j\ge0\)，v0 冻结 \(c=0\)，task §14.2/§15）：

\[
\min_{\pi\in\overline\Delta_J}
M_2(\pi),\qquad
\pi_j\ge c_j.
\]

由于目标凸、可行集凸（且滑），任何 KKT 点即全局极小。

**KKT 条件：** 存在 \(\rho\in\mathbb R\)、\(\mu_j\ge0\) 使：

\[
g_j:=\frac{\partial M_2}{\partial\pi_j}=\rho+\mu_j,
\qquad
\mu_j(\pi_j-c_j)=0.
\]

即：

- 内部组件（\(\pi_j>c_j\)）：梯度分量相等 \(g_j=\rho\)；
- floor 组件（\(\pi_j=c_j\)）：\(g_j\ge\rho\)。

**数值残余检查（脚本与测试用）：**

\[
\mathrm{KKTres}(\pi)
=
\max\left[
\max_{j:\pi_j>c_j}|g_j-\rho|,\
\max_{j:\pi_j=c_j}\max(0,\rho-g_j)
\right],
\qquad
\rho=\mathrm{mean}_{j:\pi_j>c_j}g_j.
\]

v0 冻结判据：\(\mathrm{KKTres}\le10^{-6}\)（config `mixture_weights.kk_tol`）。

> 由于凸性，SLSQP 的收敛点即 empirical objective 的全局极小（对固定样本集），与初始化无关——这使 §15 的"freeze the optimizer choice / init-independence check"成为有理论背书的实现验证而非数值赌博。

---

# 9. 有限样本目标：无偏性、经验凸性、两阶段协议

## 9.1 无偏性（对任意固定采样密度 \(r\)）

设优化样本 \(x_i\sim r_i\)（每个样本的实际密度逐一保留，task §7/§14.2），定义：

\[
\widehat M_2(\pi)
=
\frac1N\sum_i
\mathbf1_A(x_i)\frac{p(x_i)^2}{q_\pi(x_i)\,r_i(x_i)}.
\]

对任意固定的 \(\pi\)：

\[
\mathbb E_r\left[\mathbf1_A\frac{p^2}{q_\pi r}\right]
=
\int_A\frac{p^2}{q_\pi\,r}\,r\,dx
=
M_2(\pi).
\]

> 无偏性对**每个** \(\pi\) 成立，且论证只用了"\(r\) 在抽样时固定"。混合 pilot（不同批次不同 \(r_i\)）同样成立——批次比例不影响无偏性。

## 9.2 经验目标自身的凸性

对固定样本集，\(q_\pi(x_i)\) 是 \(\pi\) 的正仿射函数（Gaussian 族处处 \(>0\)）。每个被加项

\[
c_i/q_\pi(x_i),\qquad c_i=\mathbf1_A(x_i)p(x_i)^2/r_i\ge0
\]

是"正常数除以正仿射函数"，其 Hessian

\[
2c_i\,q(x_i)q(x_i)^\top/q_\pi(x_i)^3\succeq0
\]

半正定 → \(\widehat M_2(\cdot)\) 对固定样本集**本身是凸函数**。

> 含义：定理 C1 不仅在积分层面成立，在**经验层面逐样本成立**。因此 §29.4 要求的所有数值检查（FD 梯度、Hessian PSD、初始化无关性）检查的是实现正确性，而结果本身由理论保证——这是本审计最干净的闭合点。

## 9.3 两阶段协议（adaptation-bias firewall 衔接，task §18）

权重更新必须按：

```text
Phase 1: 从 r = q_{t}（当前 proposal）抽取 weight-fit 样本，记录 log r_i
Phase 2: 在这些固定样本上优化 π（梯度公式中 ∂/∂π 只作用于 q_π 核，不作用于 r）
```

如果 r 也依赖 π（r=q_π 且样本随 π 重抽），则目标退化为 \(\frac1N\sum\mathbf1_A p^2/q_\pi^2\)（\(w^2\) 型），其梯度公式**不再是无偏的 M₂ 梯度**（r 的变化产生额外项）。因此：

- v0 冻结协议：**优化期间 r 保持为抽样本时的 proposal（q_t），绝不随 π 重抽**；
- 若取 r=p（MC 源），σ̂ 独立于 π 最干净，但采样效率低；实际闭环使用 r=q_t；
- 作为特例，当 \(r=q_\pi\)（π=π_t）时，\(\widehat M_2\) 退化为经典 \((1/N)\sum\mathbf1_A w_i^2\) 估计——即 H3-1 `total_leakage` 的有限样本形式（task §29.2 "w² formula"）。

## 9.4 求解器与收敛记录

- 主实现冻结为 **SLSQP**（task §15 推荐），analytic gradient (T1) 传递为 `jac`；
- 约束：\(1^\top\pi=1\)（等式）+ \([\mathrm{floor},1]^J\)（边界）；
- 每次优化记录：success flag、message、迭代数、初终目标值、KKT 残余；
- 失败（不收敛、无事件、目标非有限）→ 该轮 action = **HOLD**（task §16），结果不得进入性能比较（task §25 Gate 0）。

---

# 10. 本子任务与闭环的关系

M1-1 只回答一个问题：

> 给定固定组件集合，权重再分配（UPDATE_WEIGHTS action）是否是一个良定义的、可全局求解的凸优化问题？

回答（本审计 + §12 数值验证）：

- 是。凸性保证 SLSQP 对 empirical objective 收敛到全局极小；
- 该结论**不**回答"组件集合怎么来"（M1-3/M1-4 的 birth/discovery 问题），也不回答"mean/covariance 怎么调"（v0 显式不做，task §4.6、§8.3、§28）；
- 因此本定理是 closed-loop 的 **Reweight 支柱**，不是整个 M1 方法链的充分条件。

---

# 11. Claim 状态与审计 Gate

| Claim | 状态（§12 验证前） | 进入 frozen claim set 的条件 |
|---|---|---|
| (T1) 一阶公式（Gaussian 族） | 推导完成，待数值验证 | §12 V2 通过 |
| (T2) 二阶公式（开 simplex） | 推导完成，待数值验证 | §12 V3 通过 |
| (T3) Hessian PSD → 凸性 | 推导完成，待数值验证 | §12 V3/V4 通过 |
| 经验目标无偏性 + 经验凸性 | 推导完成，待数值验证 | §12 V1/V4 通过 |
| SLSQP 初始化无关（经验全局极小） | 理论保证，待数值验证 | §12 V5 通过 |

**Gate：** 全部 V1–V6 通过（阈值见 §12）才允许在本文件 §12 标注 `AUDIT PASS`，并把定理 C1 记录为 "M1-1 verified theorem"（M1 命名空间内），**仍不**写入 H3 frozen claim set（task §4.2）。

---

# 12. 数值验证（回填区）

验证脚本：`scripts/run_m1_weight_theory_check.py`
结果文件：`results/phase_m1/m1_weight_theory_check_v0.json`

验证套件（V1–V6）与冻结阈值：

| ID | 内容 | 冻结阈值 |
|---|---|---|
| V1 | 无偏性：J=1 闭式 \(e^{\|m\|^2}\Phi(a+m_1)\) + J=2 quad 参考（r=p、r=q_{π0}、混合 pilot） | 批估计偏差 ≤ 3 SE |
| V2 | analytic gradient vs 中心差分（empirical objective，多点 π） | max rel err ≤ 1e-6 |
| V3 | Hessian：对称性、vᵀHv ≥ 0、eig min ≥ -1e-8、FD(gradient) 一致 | ≤ 1e-5 |
| V4 | 经验凸性：随机段中点不等式 | violation ≤ 1e-9 |
| V5 | SLSQP：约束保持、目标下降、KKTres ≤ 1e-6、初始化无关（权重 ≤ 1e-6、目标 ≤ 1e-8） | 如上 |
| V6 | 退化重合组件 flatness（Hessian 零方向、目标沿 π_j+π_ℓ 不变） | ≤ 1e-9 |

> 回填格式（验证通过后填写）：每项给出数值 + PASS/FAIL。任何 FAIL 必须在本节记录偏差并触发 amendment 流程（task §37）或修正实现。

## 12.1 验证结果（2026-08-26，seed 2026，git commit 见结果文件）

完整机器可读记录：`results/phase_m1/m1_weight_theory_check_v0.json`
（含 git commit、config sha256、timestamp、逐项数值。）

| ID | 检查 | 结果 | 判定 |
|---|---|---|---|
| V1a | r=p，J=1 闭式 \(e^{m^2}\Phi(a+m)\) 无偏性（80 批） | bias ≤ 3 SE | ✅ PASS |
| V1b | r=q_{π0} 冻结，π=π0（w² 式）与 π≠π0 两处 | bias ≤ 3 SE（3 项全过） | ✅ PASS |
| V1c | 混合 pilot（r1=p，r2=q_{π0}）pooling 无偏 | bias ≤ 3 SE | ✅ PASS |
| V2 | analytic 梯度 vs simplex 切向中心差分 | max rel err = 1.36e-10（tol 1e-6） | ✅ PASS |
| V3 | Hessian 对称 / PSD / vᵀHv / FD(grad) | sym = 1.1e-16；eig_min = 0.0178 > 0；min vᵀHv = 0.0115 ≥ 0；FD rel err = 7.6e-9（tol 1e-5） | ✅ PASS |
| V4 | 经验凸性（200 随机段中点） | max violation = 0.0（tol 1e-9） | ✅ PASS |
| V5 | SLSQP：可行性 / 改进 / KKT / 初始化无关 | 权重 spread = 2.0e-7 ≤ 1e-6；目标 spread = 2.1e-14 ≤ 1e-8；KKTres max = 1.2e-7 ≤ 1e-6；全部 4 个初始化均改进且收敛 | ✅ PASS |
| V6 | 退化重合组件 flatness | objective flatness = 0.0；vᵀHv(1,-1) = 0.0（tol 1e-9/1e-10） | ✅ PASS |

**审计结论：全部 V1–V6 通过 → `AUDIT PASS`。**

- Hessian eig_min = 0.0178 > 0 且 min vᵀHv = 0.0115 > 0：在 v0 冻结的 Gaussian 组件族上，经验目标沿 simplex 方向**严格凸**（组件在事件集上仿射无关 → 极小值点唯一，§5.3）；
- V5 初始化无关在 1e-6 权重容差内成立：与 §9.2 的经验凸性理论保证一致（全局极小可达，非数值巧合）；
- V6 确认了 §7.3 的退化情形（重合组件 → 权重再分配不改变 M₂），与理论一致。

## 12.2 Claim 状态更新

按 task §14.1 的指令，本审计通过后：

> fixed-component mixture second moment 在权重 simplex 上是凸函数（v0 Gaussian 族 + 有限样本经验目标）

可记为 **M1-1 verified theorem**（M1 命名空间内）。该 claim 仍**不**写入 H3 frozen claim set（task §4.2 边界不变）。

---

# 13. 与 task 的对应

- task §14.1 → 本文件 §2–§5（候选定理）；
- task §14.2 → 本文件 §9（有限样本目标、log-density/logsumexp、simplex 约束、floor 显式声明）；
- task §15 → 本文件 §8、§9.4（权重更新：SLSQP、analytic gradient、freeze 选择）；
- task §18 → 本文件 §9.3（数据切分防火墙）；
- task §29.1/§29.4 → `tests/test_m1_mixture_weights.py`；
- task §41（M1-1 定义）→ 本文件与其伴随实现。

---

# 14. One-line status

```text
M1-1 theory: AUDIT PASS（T1/T2/T3 + 无偏性 + 经验凸性 + KKT，V1-V6 全部通过，2026-08-26）
claim status: M1-1 verified theorem（M1 命名空间内）；未写入 H3 frozen claim set
```
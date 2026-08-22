# 从 Phase H 到 ICML 2027：Rare Topology Transition Estimation 研究路线总规划

> 更新时间：2026-08-20  
> 项目：`hypersonic-hybrid-trajectory-lab`  
> GitHub：`Huang-yu-xin/hypersonic-hybrid-trajectory-lab`  
> 当前研究分支：`feature/phase-h-uncertainty-risk`  
> 当前最新已完成科学提交：Phase H2  
> H2 commit：`13b86a375a808c0194cf1b1ee0243ece829d9f4f`  
> 当前下一步：**Phase H2R corrective patch**  
> ML 主投稿目标：**ICML 2027**  
> 内部论文冻结日期：**2027-01-10**  
> 第一后备会议：**UAI 2027**  
> 当前 ICML 2027 官方状态：已确认 2027 年将在 South America 举办；截至本文更新时间，2027 投稿日期尚未正式公布。  
> 规划依据：ICML 2026 full-paper deadline 为 2026-01-28，author notification 为 2026-04-30。因此本文将 2027-01-10 设为内部冻结日，而不是把它当成官方 deadline。

---

# 0. Executive Summary

本项目最初是一项围绕 Qian 持续滑翔与 Sanger 跳跃滑翔轨迹的高超声速混合动力学研究。经过 Phase A–G，研究已经从“建立轨迹模型”发展到：

$$
\boxed{
\text{Hybrid topology}
\rightarrow
\text{Grazing}
\rightarrow
\text{Saltation}
\rightarrow
\text{Finite-time predictability}
}
$$

Phase H 又进一步将 deterministic perturbation 提升为 stochastic uncertainty：

$$
X_0=\bar X_0+\delta X_0,
$$

并建立：

$$
P(T)\approx \Phi_H P_0\Phi_H^T
$$

以及 nonlinear Monte-Carlo validation。

截至 H2，我们已经拥有：

- 高可信 nonlinear hybrid simulator；
- Qian / Sanger frozen physics；
- Sanger N0–N5 topology；
- B0–B4 grazing branches；
- exact event taxonomy；
- continuous STM；
- saltation matrix；
- hybrid STM；
- terminal sensitivity；
- grazing-conditioning diagnostics；
- fixed-topology covariance propagation；
- nonlinear Monte-Carlo sample bank；
- topology-preservation / topology-change classification；
- Phase H stochastic protocol。

因此，从现在开始，最有价值的转向不是简单“把神经网络接到轨迹上”，而是把现有数学结构提升成一个新的 ML 研究问题：

$$
\boxed{
\textbf{Rare Topology Transition Estimation in Hybrid Dynamical Systems}
}
$$

核心概率：

$$
\boxed{
p_{\mathrm{topo}}
=
P\left[
\mathcal T(X_0)
\neq
\mathcal T(\bar X_0)
\right].
}
$$

ML 核心问题：

> **Can analytical hybrid-event geometry be exploited to learn statistically efficient estimators of rare topology transitions?**

最终计划不是让神经网络替代 simulator，而是：

$$
\boxed{
\text{Learning proposes; exact simulation decides.}
}
$$

网络负责学习更高效的 importance proposal；真正的 rare-event indicator 始终由 nonlinear hybrid simulator 决定，从而兼顾：

- ML efficiency；
- hybrid-system structure；
- probability-estimation correctness；
- statistical calibration；
- scientific interpretability。

从现在到 2027-01-10 的项目采用“双轨制”：

$$
\boxed{
\text{Phase H Scientific Track}
+
\text{ICML ML Track}
}
$$

其中 Phase H 继续负责：

- ground truth；
- topology geometry；
- uncertainty semantics；
- mixture uncertainty。

ML Track 从 H3 开始 fork，负责：

- rare-event benchmark；
- classical estimators；
- analytical geometry proposal；
- learned residual proposal；
- multi-topology estimation；
- theory；
- generic hybrid benchmarks；
- ICML paper。

---

# 1. 原始科研课题背景

## 1.1 研究对象

状态：

$$
x=
[r,\theta,v,\gamma]^T.
$$

研究两类高超声速轨迹：

### Qian continuous glide

主要结构：

```text
ENTRY_CAPTURE
    ↓
Capture
    ↓
QEG_GLIDE
    ↓
RTI
```

其中：

- Capture 是真实 hybrid switch；
- RTI 是 research terminal；
- ground continuation 只保留历史兼容意义。

### Sanger hybrid skip

模式：

```text
SANGER_ATM
↔
SANGER_VAC
```

真实 switches：

```text
ATM -> VAC : atmosphere exit
VAC -> ATM : atmosphere entry
```

因此其轨迹不是单一 smooth ODE，而是：

$$
\boxed{
\text{hybrid dynamical system}.
}
$$

---

# 2. 已完成研究成果总览

| 阶段 | 研究主题 | 状态 |
|---|---|---|
| Phase A | 基础物理、状态、环境、气动接口 | COMPLETE |
| Phase B | literal Eq.(4) baseline | COMPLETE |
| Phase B.5 | Qian research semantics / RTI | COMPLETE / FROZEN |
| Phase C | numerical validation | COMPLETE |
| Phase D | Sanger hybrid trajectory | COMPLETE / FROZEN |
| Phase E | Qian–Sanger comparison | COMPLETE |
| Phase F | \(\gamma_0-K\) topology / grazing | COMPLETE / FROZEN |
| Phase G | hybrid predictability / saltation / STM | COMPLETE / FROZEN |
| H0 | uncertainty protocol | ACCEPTED |
| H0R | lifecycle / regression repair | ACCEPTED |
| H1 | fixed-topology linear uncertainty | ACCEPTED |
| H2 | nonlinear MC validation | SCIENTIFIC CORE COMPLETE |
| H2R | endpoint / terminal metric corrective patch | **NEXT** |
| H3 | topology-transition probability | PENDING |
| H4 | topology-conditioned mixture uncertainty | PENDING |
| H5 | cross-model synthesis | PENDING |
| H6 | final audit / freeze | PENDING |

---

# 3. Phase F：为 ML 提供的 topology geometry

Phase F 冻结 tags：

```text
phase-f-v1.0
gamma-k-sensitivity-v1.0
```

frozen target：

```text
96253f1ef7785764d8da3156d7d614d2b244b577
```

研究域：

$$
\gamma_0\in[-9^\circ,-1^\circ],
\qquad
K\in[1,5].
$$

网格：

$$
33\times33=1089.
$$

Qian：

```text
1089 / 1089 = QIAN_RTI
```

Sanger topology counts：

| topology | count |
|---|---:|
| N0 | 322 |
| N1 | 306 |
| N2 | 211 |
| N3 | 153 |
| N4 | 85 |
| N5 | 12 |

Phase F 得到五条 grazing branches：

```text
B0
B1
B2
B3
B4
```

其结构为：

$$
h\rightarrow h_{\rm atm},
$$

$$
\gamma\rightarrow0,
$$

因此：

$$
n^Tf^-
=
\dot h
=
v\sin\gamma
\rightarrow0.
$$

Phase F 还建立：

```text
179 P1 candidate cells
5735 refined boxes
depth = 6
10 dual-reference extremal anchors
```

这对 ICML 项目极其关键，因为 rare topology event 的 boundary 并不是黑盒未知边界，而是已有高精度 hybrid geometry。

---

# 4. Phase G：为 ML 提供的 derivative geometry

Phase G final commit：

```text
6fb75c4a5f7b6460a5c9503c99fe2b2b2c96854c
```

tags：

```text
phase-g-v1.0
predictability-v1.0
```

连续 STM：

$$
\dot\Phi=A_m\Phi.
$$

event-time sensitivity：

$$
q_e
=
-\frac{n^T}{n^Tf^-}.
$$

identity-reset saltation：

$$
\Xi
=
I+
\frac{(f^+-f^-)n^T}{n^Tf^-}.
$$

whole hybrid STM：

$$
\Phi_H
=
C_{N+1}\Xi_NC_N\cdots\Xi_1C_1.
$$

canonical scale：

$$
S_A=
\operatorname{diag}(10^5,1,7000,0.1).
$$

scaled STM：

$$
\widetilde\Phi
=
S_A^{-1}\Phi_HS_A.
$$

---

# 5. Qian Capture 的结构性结果

在 strict-interior baseline Capture：

$$
\boxed{
\Xi_{\rm Capture}
=
\operatorname{diag}(1,1,1,0)
}
$$

因此：

$$
\operatorname{rank}\Phi_H=3.
$$

这说明 hybrid event 可以产生：

$$
\boxed{
\text{structural first-order projection}
}
$$

而不是普通 smooth-flow amplification。

这个现象未来可以作为 generic hybrid benchmark 的一种特殊类型：

```text
rank-reducing hybrid event
```

---

# 6. Sanger grazing conditioning

定义：

$$
d=n^Tf^-.
$$

对于 atmosphere interface：

$$
d=v\sin\gamma.
$$

接近 grazing：

$$
|d|\rightarrow0.
$$

Phase G 得到：

$$
\|qS_A\|
\sim
\frac1{|d|},
$$

$$
\|\Xi-I\|
\sim
\frac1{|d|}.
$$

并得到 local first-order validity scale：

$$
\Phi_{\rm local}\propto |d|^2.
$$

G6R2 冻结：

$$
\boxed{
r_{1\%}
\approx
0.040\,\Phi_{\rm local}
}
$$

以及：

$$
\boxed{
r_{5\%}
\approx
0.185\,\Phi_{\rm local}.
}
$$

但没有 universal numerical grazing threshold。

这为 ML 提供一个非常重要的 inductive bias：

$$
\boxed{
\text{rare-event boundary has known hybrid conditioning structure}.
}
$$

---

# 7. Phase H：从 derivative 到 probability

H0 定义：

$$
X_0
=
\bar x_0+\delta X_0,
$$

$$
E[\delta X_0]=0,
$$

$$
P_0
=
\operatorname{Cov}(\delta X_0).
$$

第一版只随机化：

$$
[r_0,\theta_0,v_0,\gamma_0].
$$

不随机化：

```text
K
mass
CD
reference area
atmosphere parameters
Earth parameters
control law
```

scaled uncertainty：

$$
Z_0=S_A^{-1}\delta X_0.
$$

canonical synthetic family：

$$
\boxed{
Z_0\sim N(0,\alpha^2 I).
}
$$

\(\alpha\) 只是 synthetic research amplitude，不代表真实工程误差。

---

# 8. H1：Linear Uncertainty

H1 final commit：

```text
7120feb9cfd8c013a4bdc7ef27261d6e248ca440
```

固定 topology：

$$
P(T)
=
\Phi_HP_0\Phi_H^T.
$$

scaled：

$$
\widetilde P(T)
=
\widetilde\Phi_H
\widetilde P_0
\widetilde\Phi_H^T.
$$

canonical：

$$
\widetilde P_0=\alpha^2I.
$$

于是：

$$
K_x
=
\frac{\widetilde P(T)}{\alpha^2}
=
\widetilde\Phi_H\widetilde\Phi_H^T.
$$

因此：

$$
\frac{\sigma_{\max,P}}{\alpha}
=
\sigma_{\max}(\widetilde\Phi_H).
$$

这将 predictability 与 stochastic uncertainty 严格连接。

---

# 9. H2：Nonlinear Monte-Carlo Validation

H2 commit：

```text
13b86a375a808c0194cf1b1ee0243ece829d9f4f
```

使用：

```text
numpy.default_rng
PCG64
seed = 2026
bootstrap seed = 2027
```

master sample bank：

```text
Nmax = 4096
```

antithetic：

```text
z1
-z1
z2
-z2
...
```

并使用 common random numbers。

sample bank SHA-256：

```text
99613cb2...
```

alpha probes：

$$
10^{-4},
3\times10^{-4},
10^{-3},
3\times10^{-3},
10^{-2},
3\times10^{-2},
10^{-1}.
$$

---

# 10. H2 的关键方法资产：sample-matched comparator

不是直接比较 analytic H1 covariance 与 nonlinear MC covariance。

而是对同一 sample：

$$
y_i^{LIN}
=
\widetilde\Phi_H(\alpha z_i),
$$

$$
y_i^{NL}
=
S_A^{-1}
[
x_i^{NL}(T)-x_{\rm nom}(T)
].
$$

再比较：

$$
\widehat P_{LIN,\ same\ samples}
$$

与：

$$
\widehat P_{NL}.
$$

这样可以把 ordinary finite-sample Wishart noise 与真正 nonlinear departure 分开。

这会在未来 ML paper 中成为：

```text
high-quality simulator-validation infrastructure
```

而不是主要 contribution。

---

# 11. H2 当前 fixed-time 结果

## Qian T600

```text
largest PASS_1% = 1e-2
```

$$
\boxed{
\alpha_{1\%,Qian}\approx10^{-2}
}
$$

在当前 canonical synthetic geometry 下。

主要 nonlinear limiter：

```text
mean shift
```

## Sanger T600

```text
largest PASS_1% = 3e-4
largest PASS_5% = 1e-3
```

即：

$$
\boxed{
\alpha_{1\%,Sanger}\approx3\times10^{-4}.
}
$$

当前 baseline 下，Sanger 的 first-order uncertainty approximation 比 Qian 更早失效。

但这个结论只允许限定为：

```text
canonical-A
isotropic synthetic Gaussian
baseline cases
T=600 s
finite-time
```

不是 universal robustness ranking。

---

# 12. 当前 blocker：H2R

H2 scientific core 已完成，但尚未正式冻结。

人工 audit 发现两个 contract 问题。

## 12.1 Fixed-time endpoint semantics

对于 fixed-time：

$$
x(T),
$$

classification 只能依赖：

$$
[0,T]
$$

内已经发生的事件。

如果某条 trajectory 在：

```text
T = 600 s
```

时仍然 finite、topology correct，

但在：

```text
T > 600 s
```

以后才发生 grazing/failure/ground，

不能 retroactively 把 T600 判 invalid。

因此 H2R 要实现：

$$
\boxed{
\text{endpoint-scoped classification}.
}
$$

---

## 12.2 Terminal cross covariance

H1 已冻结：

$$
\operatorname{Cov}(X_T,t_T)
=
J_TP_0\eta_T^T.
$$

H2 虽然计算 cross-covariance error，但旧 composite：

$$
E_{H2,T}
$$

没有纳入它。

修正后：

$$
\boxed{
E_{H2,T}
=
\max(
E_{t,\mu},
E_{t,\sigma},
E_{\mu,T},
E_{P,T},
E_{\sigma_1,T},
E_{\rm marginal,T},
E_{\rm zero,T},
E_\times
).
}
$$

并且 pair bootstrap 必须同样包含 \(E_\times\)。

---

# 13. 为什么必须先完成 H2R 再做 ML

未来 ML 最终要估计：

$$
P(A)
$$

其中：

$$
A=
\{Z\neq Z_0\}.
$$

如果 topology classifier / endpoint semantics 本身有 bug，

那么 ML 只是在：

> 高效估计一个定义错误的 event probability。

因此：

$$
\boxed{
H2R
\text{ 是整个 ML 项目的 correctness prerequisite}.
}
$$

在 H2R acceptance 之前：

```text
NO learned estimator
NO H3 probability freeze
NO ICML training dataset freeze
```

---

# 14. ML 转向的根本思想

传统 Phase H：

$$
\delta X_0
\rightarrow
X(T).
$$

ML 转向：

$$
\delta X_0
\rightarrow
\mathcal T(X_0).
$$

定义离散 topology random variable：

$$
\boxed{
Z=\mathcal T(X_0).
}
$$

例如：

$$
Z\in\{N0,N1,N2,N3,N4,N5\}.
$$

核心概率：

$$
p_k=P(Z=k).
$$

nominal topology：

$$
Z_0=\mathcal T(\bar X_0).
$$

topology-transition probability：

$$
\boxed{
p_{\rm topo}
=
P(Z\neq Z_0).
}
$$

---

# 15. ICML 2027 核心研究问题

暂定不要把题目锁死为某个 network architecture。

推荐 problem-level title：

# Rare Topology Transition Estimation in Hybrid Dynamical Systems

核心 question：

$$
\boxed{
\begin{gathered}
\textbf{Can analytical hybrid-event geometry be exploited}\\
\textbf{to learn statistically efficient estimators of}\\
\textbf{rare topology transitions?}
\end{gathered}
}
$$

这是整个五个月内最不应该改变的问题。

具体技术允许从：

```text
Gaussian IS
→ geometry proposal
→ residual flow
→ mixture proposal
→ active learning
```

进行调整。

---

# 16. 为什么不是“Neural Importance Sampling”作为标题

因为以下内容本身都不再足够构成 novelty：

```text
use normalizing flow
use diffusion model
learn proposal distribution
importance weighting
hybrid Neural ODE
neural reachable set
```

我们的 novelty moat 必须放在：

$$
\boxed{
\text{Hybrid topology}
+
\text{Grazing / guard geometry}
+
\text{Statistically correct rare-event estimation}
}
$$

NN 只是其中一个可替换组件。

---

# 17. 最终研究方向树

```text
Rare Topology Transition Estimation
│
├── A. Ground Truth / Problem Definition
│   │
│   ├── A1. Hybrid topology random variable Z
│   ├── A2. B0–B4 transition events
│   ├── A3. P(Z=k)
│   ├── A4. p_topo = P(Z != Z0)
│   ├── A5. reference probability construction
│   └── A6. generic hybrid benchmark protocol
│
├── B. Analytical Hybrid Geometry
│   │
│   ├── B1. Guard g(x)=0
│   ├── B2. Event normal n
│   ├── B3. Transversality d=n^T f-
│   ├── B4. Saltation Xi
│   ├── B5. Local topology margin b(x)
│   ├── B6. Boundary normal a=grad b
│   └── B7. Local Gaussian crossing approximation
│
├── C. Classical Rare-Event Baselines
│   │
│   ├── C1. Vanilla Monte Carlo
│   ├── C2. Gaussian importance sampling
│   ├── C3. Cross-Entropy Method
│   ├── C4. adaptive Gaussian-mixture IS
│   └── C5. subset simulation
│
├── D. Main ML Method
│   │
│   ├── D1. Black-box learned proposal
│   │       └── normalizing flow / residual flow
│   │
│   ├── D2. Geometry-only proposal
│   │       └── analytical boundary-guided shift
│   │
│   └── D3. Geometry + learned residual
│           └── PRIMARY ICML METHOD
│
├── E. Multi-Topology Extension
│   │
│   ├── E1. N -> N-1
│   ├── E2. N -> N+1
│   ├── E3. full P(Z=k)
│   ├── E4. mixture proposal
│   └── E5. rare transition channel allocation
│
├── F. Statistical Theory
│   │
│   ├── F1. support condition
│   ├── F2. unbiasedness / consistency
│   ├── F3. variance
│   ├── F4. coefficient of variation
│   ├── F5. relative error
│   ├── F6. local boundary approximation error
│   └── F7. asymptotic / local efficiency
│
├── G. Active Learning Pivot
│   │
│   ├── G1. topology classifier
│   ├── G2. uncertainty / entropy acquisition
│   ├── G3. grazing-guided acquisition
│   ├── G4. adaptive simulator querying
│   └── G5. active boundary refinement
│
└── H. Long-Term SciML Extensions
    │
    ├── H1. Saltation-aware neural reachability
    ├── H2. Saltation-regularized Neural Hybrid ODE
    └── H3. Topology-gated neural operator
```

---

# 18. 哪些枝条属于 ICML 2027 主线

必须完成：

```text
A. Ground Truth
B. Analytical Geometry
C. Classical Baselines
D. Main ML Method
F. Statistical Correctness
```

强烈建议完成：

```text
E. Multi-Topology Extension
```

只作为 pivot / extension：

```text
G. Active Learning
```

暂不作为当前 ICML 主线：

```text
H. Neural reachability / Hybrid Neural ODE / Neural Operator
```

---

# 19. Phase H 与 ML 的双轨关系

## Scientific Track

```text
H2R
 ↓
H3 topology probability
 ↓
H4 topology-conditioned mixture
 ↓
H5 Qian–Sanger synthesis
 ↓
H6 final audit
```

## ML Track

```text
H3 oracle / dataset
 ↓
ML-A rare-event benchmark
 ↓
ML-B classical baseline
 ↓
ML-C topology-margin geometry
 ↓
ML-D geometry proposal
 ↓
ML-E residual flow
 ↓
ML-F multi-topology
 ↓
ML-G theory / experiments
 ↓
ICML 2027
```

关键关系：

$$
\boxed{
H3
\text{ 是两个 track 的 fork point}.
}
$$

---

# 20. Phase H2R — 当前立即任务

## Scientific objective

只修：

```text
endpoint-scoped fixed-time gate
terminal cross-covariance composite/bootstrap
```

不改变：

```text
sample bank
seed
solver
alpha grid
CRN
antithetic structure
physics
H1 formulas
```

目标：

$$
\boxed{
\text{freeze a trustworthy nonlinear oracle}.
}
$$

---

# 21. H2R 验收标准

必须回答：

```text
Qian T600 bracket changed?
Sanger T600 bracket changed?
which failures happened before T?
which failures happened after T?
Qian RTI terminal bracket changed?
Sanger SRTI terminal bracket changed?
sample-bank hash unchanged?
```

并保证：

```text
full pytest PASS
tags unchanged
H3 NOT STARTED
```

---

# 22. Phase H3 — Topology Probability Ground Truth

这是整个转向的第一核心阶段。

以前 H2：

```text
topology change = invalid sample
```

到了 H3：

$$
\boxed{
\text{topology change = research signal}.
}
$$

---

# 23. H3 的主要随机变量

对于某 nominal topology：

$$
Z_0=N.
$$

sample：

$$
X_0^{(i)}
=
\bar X_0
+
S_A(\alpha z_i).
$$

运行 exact nonlinear simulator：

$$
Z_i
=
\mathcal T(X_0^{(i)}).
$$

得到：

$$
\hat p_k
=
\frac{1}{N}
\sum_i
\mathbf 1[Z_i=k].
$$

以及：

$$
\hat p_{\rm topo}
=
\frac1N
\sum_i
\mathbf1[Z_i\neq Z_0].
$$

---

# 24. H3 的 B0–B4 anchor design

使用 Phase F 冻结的：

```text
B0 N-side / N+1-side
...
B4 N-side / N+1-side
```

总共：

```text
10 anchors
```

但为了 ML，不应该只研究 anchor 本身。

每个 boundary 需要向 interior 构造：

```text
very-near
near
medium
deep
```

等多个 probability levels。

目标让真实：

$$
p_{\rm topo}
$$

覆盖：

$$
10^{-1}
\rightarrow
10^{-2}
\rightarrow
10^{-3}
\rightarrow
10^{-4}.
$$

如果成本允许：

$$
10^{-5}
$$

作为重要 rare-event stress test。

不建议依赖 brute-force MC 构造所有 \(10^{-6}\) reference probabilities。

---

# 25. H3 数据必须比普通科研 snapshot 更丰富

每个 sample 至少缓存：

```text
sample_id
standardized z
physical x0
alpha
nominal topology
observed topology
true switch signature
event times
event order
minimum transversality |d|
closest guard approach
failure classification
solver provenance
```

如果成本允许，额外记录：

```text
relevant Xi norms
Phi_local proxy
boundary branch
signed topology margin candidate
```

不要默认保存全 dense trajectory。

---

# 26. H3 probability CI 的注意事项

H0 规划了 Wilson 95% CI。

但是 antithetic samples 存在 pair dependence。

普通 Wilson interval 假设 independent Bernoulli observations。

因此 H3 必须明确处理：

方案 A：

```text
probability CI 使用 independent base draws
```

或：

方案 B：

```text
对 antithetic pair 使用 pair-level bootstrap / appropriate dependent CI
```

禁止把：

```text
4096 correlated antithetic samples
```

直接当 4096 independent Bernoulli observations 计算 naive Wilson CI。

---

# 27. H3 的 ICML 资产

H3 完成后应该得到：

$$
\boxed{
\mathcal O(x_0)
=
\mathcal T(x_0)
}
$$

一个可信 oracle。

以及：

```text
HybridRare dataset v0
B0-B4 probability profiles
transition-channel labels
probability-vs-distance curves
```

从这一步开始，ML 可以正式启动。

---

# 28. ML-A：建立 classical rare-event baseline

第一步不是神经网络。

必须建立：

## Vanilla MC

$$
\hat p_{\rm MC}
=
\frac1N\sum_i I_A(x_i).
$$

## Gaussian IS

$$
x_i\sim q_\mu(x),
$$

$$
\hat p
=
\frac1N
\sum_i
I_A(x_i)
\frac{p(x_i)}{q_\mu(x_i)}.
$$

## Cross-Entropy Method

自适应调整 proposal。

## Adaptive Gaussian Mixture IS

用于 multimodal transition sets。

## Subset Simulation

用于非常小的 rare probability。

---

# 29. 为什么 classical baseline 很重要

ICML reviewer 一定会问：

```text
Why not CEM?
Why not subset simulation?
Why not Gaussian IS?
Why not adaptive mixture?
Why not black-box normalizing flow?
```

所以 main method 不能只超过 MC。

最低竞争集合必须包括：

$$
\boxed{
\text{MC + Gaussian IS + CEM + mixture IS + subset simulation}.
}
$$

---

# 30. ML-B：Topology Margin

这是最值得优先研究的理论结构。

定义 signed topology margin：

$$
b(x).
$$

希望满足：

$$
b(x)>0
\Rightarrow
N\text{-side},
$$

$$
b(x)<0
\Rightarrow
N+1\text{-side},
$$

$$
b(x)=0
\Rightarrow
\text{grazing boundary}.
$$

候选可来自：

```text
minimum signed guard miss
signed grazing clearance
branch-specific event geometry
local boundary reconstruction
```

但必须通过 simulator 结果验证，而不能仅凭符号命名。

---

# 31. Local Gaussian Approximation

在 nominal：

$$
\bar x
$$

附近：

$$
b(\bar x+\delta x)
=
b_0+a^T\delta x+O(\|\delta x\|^2),
$$

其中：

$$
a=\nabla b(\bar x).
$$

若：

$$
\delta X\sim N(0,P),
$$

则：

$$
a^T\delta X
\sim
N(0,a^TPa).
$$

因此：

$$
\boxed{
p_{\rm topo}
\approx
\Phi
\left(
-\frac{b_0}
{\sqrt{a^TPa}}
\right).
}
$$

这一结果可以同时作为：

```text
analytic probability baseline
rare direction
proposal initializer
control variate candidate
active-learning feature
```

---

# 32. Geometry-Informed Proposal

若 local failure event 近似：

$$
a^Tz>c,
$$

则 rare direction 与：

$$
Pa
$$

相关。

因此先构造：

$$
q_{\rm geom}(x).
$$

这一步完全不需要神经网络。

目标：

$$
\boxed{
\text{use hybrid geometry to move probability mass toward the rare boundary}.
}
$$

---

# 33. ML-C：Black-Box Learned Proposal

然后建立公平 black-box baseline：

$$
q_\phi^{BB}(x).
$$

推荐优先：

```text
normalizing flow
```

而不是 diffusion。

原因：

- input dimension 低；
- density \(q_\phi(x)\) 必须显式可计算；
- IS weight 需要 \(p/q\)；
- 训练成本低；
- 与 analytical Gaussian proposal 组合自然。

---

# 34. ML-D：主方法 — Geometry + Learned Residual

真正希望成为 ICML main method：

$$
\boxed{
q_\phi
=
T_\phi\#q_{\rm geom}.
}
$$

即：

```text
analytical geometry proposal
+
learned residual transport
```

科学解释：

> physics / hybrid geometry determines the first move; ML learns what the local geometry approximation misses.

这样避免让 flow 从 nominal \(p(x)\) 开始盲目寻找极小 failure region。

---

# 35. Main Ablation Matrix

最终至少比较：

| Method | Hybrid Geometry | Learning | Exact IS correction |
|---|---|---|---|
| MC | No | No | N/A |
| Gaussian IS | No | No | Yes |
| CEM | No | Adaptive | Yes |
| Black-box Flow IS | No | Yes | Yes |
| Geometry IS | Yes | No | Yes |
| **Geometry + Residual Flow** | **Yes** | **Yes** | **Yes** |

理想结果：

$$
\boxed{
\text{Geometry + ML}
>
\text{Geometry only}
>
\text{Black-box ML}
>
\text{MC}
}
$$

这里的“>”不是 accuracy，而是：

```text
lower relative error
lower estimator variance
higher ESS
fewer simulator calls
```

---

# 36. ML 的角色边界

网络不负责决定 rare event。

rare indicator：

$$
I_A(x)
=
\mathbf1[
\mathcal T(x)\neq \mathcal T_0
]
$$

始终来自：

```text
true nonlinear hybrid simulator
```

最终 estimator：

$$
\boxed{
\hat p_A
=
\frac1N
\sum_i
I_A(x_i)
\frac{p(x_i)}{q_\phi(x_i)}.
}
$$

核心原则：

$$
\boxed{
\text{Learning improves efficiency; exact simulation preserves correctness.}
}
$$

---

# 37. Multi-Topology Extension

Sanger 有：

$$
N0,\ldots,N5.
$$

所以最终不应只估：

$$
P(Z\neq Z_0).
$$

可以估：

$$
P(Z=k).
$$

并区分：

$$
P(N\rightarrow N-1),
$$

$$
P(N\rightarrow N+1).
$$

甚至多步：

$$
P(N\rightarrow N\pm2).
$$

如果概率非零且物理上可达。

---

# 38. Mixture Proposal

若 rare set 是 multimodal：

$$
A=
A_1\cup A_2\cup\cdots,
$$

构造：

$$
\boxed{
q(x)
=
\sum_k\pi_kq_k(x).
}
$$

不同 expert 对应：

```text
different topology-transition channels
different grazing branches
different event sequences
```

这会形成：

$$
\boxed{
\text{multi-topology rare-event estimation}
}
$$

而不是传统 single failure-set estimation。

---

# 39. 与 Phase H4 的连接

Phase H4 研究：

$$
\mu
=
\sum_kp_k\mu_k,
$$

$$
P
=
\sum_kp_k
[
P_k+
(\mu_k-\mu)(\mu_k-\mu)^T
].
$$

因此 ML estimator 得到的：

$$
\hat p_k
$$

不是孤立 benchmark。

它直接影响：

```text
topology-conditioned uncertainty mixture
```

从而形成 downstream scientific value：

$$
\boxed{
\text{better rare topology probabilities}
\rightarrow
\text{better hybrid uncertainty decomposition}.
}
$$

---

# 40. Statistical Evaluation Metrics

主指标不能是 classifier accuracy。

## Relative Error

$$
RE=
\frac{|\hat p-p^\star|}{p^\star}.
$$

## Variance

$$
\operatorname{Var}(\hat p).
$$

## Relative Standard Error

$$
RSE=
\frac{\sqrt{\operatorname{Var}(\hat p)}}{p}.
$$

## Coefficient of Variation

$$
CV=
\frac{\sqrt{\operatorname{Var}(\hat p)}}{p}.
$$

## Effective Sample Size

$$
ESS.
$$

## Simulator Calls

$$
\boxed{
N_{\rm simulator}
}
$$

这是最重要的成本指标之一。

---

# 41. 最重要的实验图

## Figure 1 — Topology Partition

展示：

```text
N-side
grazing boundary
N+1-side
uncertainty cloud
```

## Figure 2 — Hybrid Geometry

展示：

$$
g(x),
\quad
n^Tf^-,
\quad
\text{boundary normal},
\quad
\text{rare direction}.
$$

## Figure 3 — Proposal Evolution

展示：

```text
p(x)
q_geom(x)
q_phi(x)
rare region
```

## Figure 4 — Sample Efficiency

横轴：

$$
\text{simulator calls}.
$$

纵轴：

$$
RE
$$

或：

$$
CV.
$$

## Figure 5 — Probability Scale

横轴：

$$
p^\star:
10^{-2}\rightarrow10^{-5}.
$$

纵轴：

```text
required simulator calls
```

## Figure 6 — Cross-System Generalization

展示多个 generic hybrid systems。

---

# 42. Generic Hybrid Benchmark Suite

为了避免论文被认为：

```text
aerospace-specific trick
```

必须建立通用 benchmark。

建议：

## Benchmark 1 — Bouncing Ball

特点：

```text
impact reset
event timing
simple analytic structure
```

## Benchmark 2 — Thermostat / Relay

特点：

```text
mode switching
guard surfaces
piecewise dynamics
```

## Benchmark 3 — Impact / Contact System

特点：

```text
state reset
nonsmooth event
```

## Benchmark 4 — Multi-Guard Synthetic Hybrid System

特点：

```text
multiple event sequences
multiple topology classes
```

## Benchmark 5 — Sanger

特点：

```text
realistic
multi-event
multi-skip
grazing
N0-N5
expensive nonlinear simulator
```

Sanger 应作为：

$$
\boxed{
\text{high-complexity stress test}
}
$$

而不是唯一实验。

---

# 43. HybridRareBench 设想

可以在项目后期形成统一 benchmark interface：

$$
x_0
\rightarrow
\text{trajectory}
\rightarrow
\text{event sequence}
\rightarrow
Z.
$$

每个 system 提供：

```text
nominal topology
input distribution
rare event definition
reference probability
guard metadata
optional saltation metadata
simulation cost
```

如果 main algorithm contribution 稍弱，benchmark 本身也能增强论文完整度。

但 benchmark 不应抢占方法开发时间。

---

# 44. 理论目标

## Level 1 — 必须完成

importance estimator support condition：

$$
q(x)>0
\quad
\text{wherever}
\quad
I_A(x)p(x)>0.
$$

并证明：

$$
E_q
\left[
I_A(X)
\frac{p(X)}{q(X)}
\right]
=
p_A.
$$

即 estimator unbiasedness。

---

# 45. Level 2 — 强烈建议

Topology margin：

$$
b(x+\delta x)
=
b(x)+a^T\delta x+O(\|\delta x\|^2).
$$

Gaussian input：

$$
p_{\rm topo}
=
\Phi
\left(
-\frac{b_0}
{\sqrt{a^TPa}}
\right)
+
O(\text{nonlinear remainder}).
$$

尽量给出：

```text
local approximation condition
remainder interpretation
```

---

# 46. Level 3 — ICML Stretch

在线性 half-space rare-event model：

$$
A=
\{a^Tx>c\}
$$

中，分析 geometry proposal 的：

```text
relative variance
asymptotic efficiency
```

并与 nominal MC / naive mean shift 比较。

如果能证明：

$$
\boxed{
\text{hybrid geometry proposal has lower asymptotic relative variance}
}
$$

会显著增加 ICML 方法论文强度。

---

# 47. 五个月总时间线

## 2026-08-20 ～ 2026-08-31

### Phase H

完成：

```text
H2R
```

### ML

只冻结：

```text
problem definition
event semantics
data schema
benchmark metric
```

### Deliverables

```text
trusted oracle semantics
H2 final authority
ML problem v1
```

---

# 48. 2026-09-01 ～ 2026-09-20

## H3

完成：

```text
B0-B4 stochastic transition study
probability profiles
transition-channel labels
```

重点开始构造：

```text
near → deep interior
```

不同 rarity levels。

### Deliverables

```text
H3 snapshot
HybridRare dataset v0
reference p_topo profiles
```

---

# 49. 2026-09-21 ～ 2026-10-10

## Classical Rare-Event Stage

实现：

```text
MC
Gaussian IS
CEM
Gaussian mixture IS
subset simulation
```

同时研究：

$$
b(x).
$$

### Deliverables

```text
baseline table v1
topology margin candidate
reference probability protocol
```

---

# 50. 2026-10-11 ～ 2026-10-31

## Geometry Proposal Stage

完成：

$$
q_{\rm geom}.
$$

检查：

### Gate 1

Geometry-only IS 是否显著优于 vanilla MC？

如果否：

```text
STOP ML scaling
repair topology-margin mathematics
```

如果是：

继续。

### Deliverables

```text
geometry proposal v1
probability-vs-call curves
```

---

# 51. 2026-11-01 ～ 2026-11-15

## Learned Proposal Stage

实现：

```text
black-box normalizing flow
geometry-initialized residual flow
```

进行：

```text
3 seeds
initial ablations
weight stability audit
```

---

# 52. 11 月第一次 ML Go / No-Go

## Gate 2

Black-box flow 是否至少达到 classical baseline？

如果否：

不继续扩大模型。

## Gate 3

Geometry + Flow 是否明显优于 black-box flow？

如果 yes：

$$
\boxed{
\text{ICML main method confirmed}.
}
$$

如果 no：

进入：

# Pivot A — Geometry-Only Estimator

论文转为：

```text
Geometry-Guided Rare-Event Estimation
```

重点增加：

```text
theory
multi-topology
UAI fit
```

而不是硬保留 NN。

---

# 53. 2026-11-16 ～ 2026-11-30

## Generic Benchmark Stage

完成至少：

```text
Bouncing ball
Relay/Thermostat
Impact/contact
Synthetic multi-guard
Sanger
```

同时开始：

```text
multi-topology mixture proposal
```

### Deliverables

```text
HybridRareBench v1
cross-system result table
```

---

# 54. 2026-12-01 ～ 2026-12-15

## Theory + Final Method

完成：

```text
unbiasedness
local boundary approximation
main method definition
multi-topology formulation
```

尽量推进：

```text
local variance theorem
```

---

# 55. 2026-12-15 — METHOD FREEZE

这是硬 deadline。

从：

```text
2026-12-15
```

开始禁止：

```text
换 flow
换 diffusion
换 whole architecture
增加 unrelated subproject
```

只允许：

```text
bug fix
ablation
large final run
proof polishing
writing
```

---

# 56. 2026-12-16 ～ 2026-12-31

## Final Experiment Stage

重点：

```text
multiple seeds
multiple rarity levels
all benchmark methods
runtime
simulator calls
ESS
CV
weight diagnostics
failure cases
```

Probability scale 尽量覆盖：

$$
10^{-2},
10^{-3},
10^{-4},
10^{-5}.
$$

\(10^{-6}\) 是 stretch，不应成为必须完成项。

---

# 57. 2027-01-01 ～ 2027-01-10

# Paper Freeze Sprint

### Jan 1–3

补最后 missing experiment。

### Jan 4–6

冻结：

```text
figures
tables
result numbers
```

### Jan 7

完整 manuscript v1。

### Jan 8

模拟 reviewer：

```text
What is novel?
Why hybrid?
Why ML?
Why not CEM?
Why not subset simulation?
Why not black-box flow?
Is estimator statistically correct?
Does it generalize beyond Sanger?
```

### Jan 9

完成：

```text
appendix
reproducibility
proof details
limitations
```

### Jan 10

$$
\boxed{
\textbf{ICML PAPER FREEZE}
}
$$

---

# 58. Jan 10 之后

由于 ICML 2027 official submission dates 截至本文更新时间尚未公布，

Jan 10 后只用于：

```text
proofreading
formatting
small sanity check
OpenReview setup
author feedback
reproducibility cleanup
```

不再换方法。

---

# 59. 投稿时间策略

## Primary

$$
\boxed{
\text{ICML 2027}
}
$$

已知：

```text
2027 location = South America
```

尚未知：

```text
official submission deadline
official notification date
```

规划参考 ICML 2026：

```text
abstract deadline = 2026-01-23
full paper deadline = 2026-01-28
author notification = 2026-04-30
```

因此内部：

```text
2027-01-10 paper freeze
```

保留安全 buffer。

---

# 60. Backup

$$
\boxed{
\text{UAI 2027}
}
$$

如果论文最终更偏：

```text
uncertainty quantification
rare probability
importance sampling
statistical efficiency
```

UAI topic fit 很自然。

截至本文更新时间 UAI 2027 deadline 尚未正式公布。

规划参考 UAI 2026：

```text
submission deadline = 2026-02-25
notification = 2026-06-01
```

因此如果 ICML 不合适，UAI 仍可能满足：

```text
2027-07 前拿到 decision
```

但 2027 日期必须以后按官方信息更新。

---

# 61. 抢先风险分类

## 高风险

```text
generic neural importance sampling
flow-based rare-event sampling
diffusion rare-event sampler
generic hybrid Neural ODE
```

这些不能作为唯一 novelty。

## 中风险

```text
neural reachability
hybrid safety learning
grazing-aware learning
```

## 相对低风险

```text
rare discrete topology transition probability
```

## 当前最值得占据的位置

$$
\boxed{
\text{grazing / hybrid geometry informed rare topology estimator}.
}
$$

---

# 62. 每周文献监控

当前已建立每周监控任务。

重点关键词：

```text
hybrid systems rare event importance sampling
topology transition hybrid learning
grazing saltation machine learning
rare event normalizing flow dynamical systems
Doob transform
transition path sampling
neural importance sampling
failure probability
subset simulation
simulation-based inference topology
```

重点来源：

```text
arXiv
OpenReview
ICLR submissions
ICML
NeurIPS
```

---

# 63. Pivot Trigger A

如果新论文同时做到：

```text
hybrid system
+
topology transition
+
learned IS
```

则主线立即 sharpen 为：

$$
\boxed{
\text{grazing/saltation analytical proposal + residual learning}.
}
$$

---

# 64. Pivot Trigger B

如果别人进一步做到：

```text
grazing geometry
+
learned rare-event IS
```

则转向：

$$
\boxed{
\text{multi-topology mixture estimation}.
}
$$

强调：

$$
P(Z=k)
$$

而不是单一 failure probability。

---

# 65. Pivot Trigger C

如果 multi-topology probability 也被明显抢先：

转为：

$$
\boxed{
\text{Physics-Guided Active Topology Boundary Learning}.
}
$$

使用：

```text
topology classifier
uncertainty acquisition
grazing score
simulator-query budget
```

已有 H3 dataset / oracle 仍然全部可复用。

---

# 66. 为什么这个项目具有高 pivot ability

研究资产层级：

$$
\boxed{
\begin{aligned}
&\text{F: topology geometry}\\
&\text{G: hybrid derivatives}\\
&\text{H: stochastic simulator}\\
&\text{H3: probability ground truth}\\
&\text{ML: efficient estimator}
\end{aligned}
}
$$

竞争者最多抢走：

```text
某一个 estimator architecture
```

不会抢走前四层。

因此无需因为某篇类似 arXiv 出现就推倒重来。

---

# 67. 实验环境：当前 AutoDL 实例

当前可用实例：

```text
GPU:
RTX 5090 32GB × 1

CPU:
25 vCPU Intel Xeon Platinum 8470Q

RAM:
92 GB

system disk:
30 GB

data disk:
50 GB free SSD initially

price:
2.78 RMB / hour
```

---

# 68. 对当前实例的评价

| 资源 | 评价 | 用途 |
|---|---|---|
| RTX 5090 32GB | 非常充裕 | Flow / MLP / residual proposal |
| 25 vCPU | 足够当前阶段 | H2R / H3 / medium MC |
| 92GB RAM | 很好 | 多进程 simulator |
| 30GB system disk | 偏小 | 不应存大型 cache |
| 50GB data disk | 偏小 | 建议扩容 |
| 2.78 RMB/h | 很划算 | 开发 / GPU 阶段 |

---

# 69. 当前 CPU 策略

25 vCPU 不需要立刻更换。

推荐 benchmark workers：

```text
1
4
8
12
16
20
24
```

实际选择：

$$
\boxed{
\text{max trajectories / second}
}
$$

而不是直接：

```text
workers = 25
```

通常开发阶段可先用：

```text
20–22 workers
```

给：

```text
OS
main process
cache writer
```

留资源。

---

# 70. H2R 算力

如果 cache 完整：

```text
GPU = 0
CPU < 10 core-hours
```

主要工作：

```text
reaggregation
reclassification
bootstrap
snapshot
```

---

# 71. H3 算力

粗略：

$$
10\text{ anchors}
\times
10\text{ amplitudes}
\times
4096
\approx
4.1\times10^5
$$

trajectories。

若平均：

$$
1\text{ CPU second / trajectory},
$$

理论：

$$
114\text{ CPU core-hours}.
$$

实际按：

$$
200\sim500\text{ CPU core-hours}
$$

规划更稳。

25 vCPU 下：

```text
hours to about one day level
```

即可完成。

---

# 72. ICML 总算力预算

推荐：

$$
\boxed{
5000\sim10000
\text{ CPU core-hours}
}
$$

加：

$$
\boxed{
100\sim150
\text{ GPU-hours}.
}
$$

以及：

$$
\boxed{
500GB\sim1TB
\text{ storage}.
}
$$

---

# 73. 为什么 GPU 不是瓶颈

ML input dimension 第一版只有：

$$
d=4.
$$

未来加入：

```text
K
atmospheric parameters
```

也大约：

$$
d=6\sim10.
$$

normalizing flow / residual flow 很小。

5090 32GB 显存远超需求。

真正瓶颈：

$$
\boxed{
\text{hybrid ODE simulator calls}.
}
$$

---

# 74. 为什么不用 A100/H100

本项目不是：

```text
LLM training
large vision model
large transformer
```

而是：

```text
low-dimensional neural density model
+
large number of CPU hybrid ODE simulations
```

所以：

$$
\boxed{
\text{more CPU cores}
>
\text{more GPU VRAM}.
}
$$

---

# 75. Two-Stage Compute Strategy

## Stage A — 现在到 10 月

使用当前：

```text
25 vCPU + RTX 5090
```

完成：

```text
H2R
H3
classical baseline
geometry proposal
small ML training
debug
```

## Stage B — 11–12 月

如果需要：

```text
millions of trajectories
multi-seed
five benchmarks
rare probability 1e-5
```

临时租：

```text
64–128+ CPU cores
```

做 burst simulation。

训练仍回当前 5090。

---

# 76. CPU / GPU Pipeline

推荐 architecture：

```text
CPU hybrid oracle
       ↓
sample cache
       ↓
GPU proposal training
       ↓
new proposal samples
       ↓
CPU hybrid oracle
       ↓
importance weights / estimator
       ↓
updated dataset
```

---

# 77. 数据盘建议

当前免费：

```text
50GB
```

偏小。

建议立即扩到：

$$
\boxed{
200\sim300GB
}
$$

开发期。

final experiments 再按需要扩：

$$
500GB\sim1TB.
$$

项目 / dataset 优先放：

```text
/root/autodl-tmp/
```

不要堆系统盘。

---

# 78. Cache Design

Production MC 不保存完整 dense trajectory。

每条 sample 保存 sufficient statistics：

```text
sample_id
x0
z
topology
switch signature
event times
minimum |d|
terminal class
solver status
importance proposal
log p
log q
weight
```

只有：

```text
debug subset
figure examples
failure diagnosis
```

保存 dense trajectory。

---

# 79. 推荐目录结构

```text
project/
├── src/
├── scripts/
├── docs/
├── tests/
├── results/
│   ├── phase_h2/
│   ├── phase_h3/
│   └── ml/
│
├── datasets/
│   ├── hybridrare_v0/
│   ├── hybridrare_v1/
│   └── benchmarks/
│
├── cache/
│   ├── trajectory_oracle/
│   ├── topology_labels/
│   └── proposal_samples/
│
├── checkpoints/
│   ├── blackbox_flow/
│   └── geometry_residual_flow/
│
└── paper/
    ├── figures/
    ├── tables/
    └── manuscript/
```

---

# 80. Oracle Cache Key

建议至少由：

```text
model
initial_state
control
solver_config
physics_version
source_commit
```

共同 hash。

例如：

$$
\text{key}
=
H(
x_0,
K,
\text{solver},
\text{physics commit}
).
$$

目的：

$$
\boxed{
\text{同一 trajectory 只计算一次}.
}
$$

---

# 81. 极小概率的算力限制

普通 MC：

$$
\operatorname{RSE}
\approx
\frac1{\sqrt{Np}}.
$$

若要求约 10%：

$$
N\approx\frac{100}{p}.
$$

因此：

| \(p\) | naive MC |
|---:|---:|
| \(10^{-2}\) | \(10^4\) |
| \(10^{-3}\) | \(10^5\) |
| \(10^{-4}\) | \(10^6\) |
| \(10^{-5}\) | \(10^7\) |
| \(10^{-6}\) | \(10^8\) |

这就是 ICML 方法存在的计算动机。

---

# 82. 不应 brute-force 建所有 ground truth

特别：

$$
p=10^{-6}
$$

不应通过：

```text
hundreds of millions of direct trajectories
```

作为唯一 reference。

可综合：

```text
high-budget classical IS
subset simulation
independent proposal
analytic benchmark
multiple-seed estimator agreement
confidence intervals
```

构造可信 reference。

---

# 83. 当前实例的成本理解

AutoDL：

```text
2.78 RMB / hour
```

即使连续：

```text
72 hours
```

成本约：

```text
200 RMB level
```

因此为几十元计算成本重写整个 GPU hybrid solver 不值得。

优先级应为：

$$
\boxed{
\text{cache}
>
\text{CPU parallelism}
>
\text{algorithmic rare-event estimator}
>
\text{GPU ODE rewrite}.
}
$$

---

# 84. 当前不建议 GPU 重写 simulator

当前 simulator 特征：

```text
adaptive DOP853
event detection
root finding
different event sequences
different terminal times
```

这些控制流并不天然适合 GPU SIMD。

除非未来 profiling 证明：

```text
>90% total cost = CPU trajectory integration
```

且 cloud CPU 已经成为重大成本，

否则不要投入数周重写：

```text
JAX hybrid solver
GPU batched event solver
```

---

# 85. ICML Paper 的 Contribution Design

## Contribution 1 — Problem

定义：

$$
\boxed{
\text{Rare Hybrid Topology Transition Estimation}.
}
$$

把 rare event 从 ordinary tail event 提升为：

$$
A=
\{x:\mathcal T(x)\neq\mathcal T_0\}.
$$

---

# 86. Contribution 2 — Geometry

利用：

$$
g(x),
\quad
n^Tf^-,
\quad
\Xi,
\quad
b(x).
$$

得到：

```text
rare direction
local crossing probability
analytical proposal
```

---

# 87. Contribution 3 — Learning

让 neural density model 学：

$$
\boxed{
\text{residual mismatch beyond local hybrid geometry}.
}
$$

不是从零学习整个 rare-event geometry。

---

# 88. Contribution 4 — Statistical Correctness

网络只产生：

$$
q_\phi.
$$

最终 probability 由：

$$
I_A(x)
\frac{p(x)}{q_\phi(x)}
$$

估计。

强调：

```text
corrected importance weights
support
ESS
weight stability
unbiasedness
```

---

# 89. Contribution 5 — Multi-Topology

估计：

$$
P(Z=k)
$$

而不仅是一个二值 failure probability。

这会成为非常重要的 strengthening。

---

# 90. Contribution 6 — Benchmark

在多个 hybrid systems 验证。

Sanger 作为 hardest realistic benchmark。

---

# 91. ICML 论文可能结构

## 1 Introduction

- hybrid systems 的 topology discontinuity；
- rare topology transitions 很难通过 MC 估计；
- existing learned samplers 通常不知道 guard/grazing geometry；
- propose topology-aware rare-event estimation。

## 2 Related Work

- rare-event simulation；
- adaptive IS；
- neural IS；
- flow-based sampling；
- hybrid dynamical systems；
- hybrid learning；
- reachability / safety；
- SciML。

## 3 Problem Formulation

定义：

$$
Z,
\quad
A,
\quad
p_A.
$$

## 4 Hybrid Event Geometry

定义：

$$
g,n,d,\Xi,b.
$$

## 5 Geometry-Informed Proposal

推导：

$$
q_{\rm geom}.
$$

## 6 Learned Residual Proposal

定义：

$$
q_\phi=T_\phi\#q_{\rm geom}.
$$

## 7 Statistical Properties

- unbiasedness；
- support；
- local approximation；
- variance analysis。

## 8 Experiments

- synthetic；
- generic hybrid；
- Sanger；
- ablation；
- rare scaling；
- runtime。

## 9 Limitations

- initial-state-only uncertainty；
- local geometry assumptions；
- expensive oracle；
- no universal safety guarantee；
- no control optimization。

---

# 92. Main Claim Boundaries

当前绝对不要声称：

```text
Sanger globally chaotic
grazing means infinite physical sensitivity
Qian universally more robust
canonical A is unique physical scaling
synthetic alpha is real-world uncertainty
our ML method provides certified safety
our neural model replaces the simulator
rare-event estimate is exact at finite N
all hybrid systems satisfy local half-space approximation
```

---

# 93. 当前安全/学术边界

本项目 Phase H / ML 只研究：

```text
generic hybrid uncertainty
topology transitions
rare-event probability
sampling efficiency
scientific ML
```

不扩展：

```text
interception
evasion
target hit
weapon effectiveness
engagement optimization
survival optimization
```

现有 risk layer 中相关文件保持不实现。

---

# 94. 近期执行优先级

$$
\boxed{
\textbf{Priority 1: H2R}
}
$$

先修 correctness。

然后：

$$
\boxed{
\textbf{Priority 2: H3}
}
$$

得到 probability ground truth。

然后：

$$
\boxed{
\textbf{Priority 3: topology margin + classical IS}
}
$$

之后才：

$$
\boxed{
\textbf{Priority 4: learned proposal}.
}
$$

不要把顺序倒过来。

---

# 95. 10 月底 Go / No-Go

必须回答：

```text
Is topology margin meaningful?
Does geometry-only IS beat MC?
Can probability level reach 1e-4 reliably?
Is classical estimator implementation stable?
```

如果不能：

```text
do not train bigger neural networks
```

先修 problem formulation。

---

# 96. 11 月中 Go / No-Go

必须回答：

```text
Does flow beat classical baseline?
Does geometry improve flow?
Are importance weights stable?
Does method generalize to at least 3 hybrid systems?
```

如果 geometry + learning 没优势：

```text
pivot to geometry-only / UAI-style paper
```

---

# 97. 12 月 Method Freeze 条件

只有以下内容均基本稳定才 freeze：

```text
problem
event definition
proposal family
weight formula
baselines
benchmarks
metrics
statistical protocol
main ablations
```

---

# 98. 最终成功标准

到 2027-01-10，理想状态不是：

```text
“有一个 flow 能跑”
```

而是：

$$
\boxed{
\begin{aligned}
&\text{1. 一个明确的新 hybrid rare-event 问题}\\
&\text{2. 一个 analytical geometry baseline}\\
&\text{3. 一个 geometry-informed learned estimator}\\
&\text{4. correct IS probability estimation}\\
&\text{5. classical + neural baselines}\\
&\text{6. multiple hybrid benchmarks}\\
&\text{7. rare probability scaling}\\
&\text{8. 至少一层理论结果}\\
&\text{9. 完整 reproducibility}\\
&\text{10. 一篇冻结 manuscript}
\end{aligned}
}
$$

---

# 99. 研究主线最终压缩版

已有：

$$
\text{Hybrid Dynamics}
$$

↓

$$
\text{Topology}
$$

↓

$$
\text{Grazing Geometry}
$$

↓

$$
\text{Saltation / Predictability}
$$

↓

$$
\text{Linear Uncertainty}
$$

↓

$$
\text{Nonlinear MC}
$$

当前：

$$
\boxed{
\text{H2R}
}
$$

下一步：

$$
\boxed{
\text{H3 Topology Probability}
}
$$

然后：

$$
\boxed{
\text{Rare-Event Estimation}
}
$$

↓

$$
\boxed{
\text{Geometry-Informed Proposal}
}
$$

↓

$$
\boxed{
\text{Learned Residual Proposal}
}
$$

↓

$$
\boxed{
\text{Multi-Topology Probability}
}
$$

↓

$$
\boxed{
\text{ICML 2027}
}
$$

---

# 100. 最终研究问题

未来五个月无论具体 network / estimator 如何变化，

必须守住：

$$
\boxed{
\begin{gathered}
\textbf{How can analytical hybrid-event geometry be exploited}\\
\textbf{to learn statistically efficient estimators of}\\
\textbf{rare topology transitions?}
\end{gathered}
}
$$

这比：

```text
“用神经网络估 rare event”
```

更稳定；

比：

```text
“在 Sanger 上训练一个 flow”
```

更通用；

也比：

```text
“把已有轨迹项目包装成 ML”
```

更接近真正的 ICML 方法问题。

---

# 101. 下一次执行从哪里开始

当前不要直接进入 H3 或 ML。

下一次实验严格从：

# Phase H2R — Endpoint-Scoped Fixed-Time Gate & Terminal Joint-Metric Corrective Patch

开始。

starting commit：

```text
13b86a375a808c0194cf1b1ee0243ece829d9f4f
```

H2R ACCEPTED 后：

```text
H2 becomes ACCEPTED
```

然后正式进入：

# Phase H3 — Grazing / Topology-Transition Risk

H3 完成第一版 ground truth 后，

再 fork：

# ML-A — Rare Topology Transition Benchmark & Classical Estimation

---

# 102. 一句话长期目标

$$
\boxed{
\textbf{把当前高质量 hybrid dynamics 研究平台，转化为一个具有数学结构、统计正确性和 ML 方法创新的 rare-topology estimation framework，并以 ICML 2027 为主投稿目标。}
}
$$

# M2 Variance-Geometry Covariance Adaptation — Preregistered Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems  
> **Method Track:** M2 — Variance-Geometry Covariance Adaptation  
> **Document type:** Preregistered method / experiment task specification  
> **Status:** **PREREGISTERED — NOT STARTED**  
> **Parent frozen science:** `RareTopo-H3-v1.0`  
> **Parent frozen method:** `RareTopo-M1-v0`  
> **Parent frozen benchmark extension:** `RareTopo-M1-D-v1.0`  
> **M1-D frozen HEAD:** `059964eb3b8b927301776ae5505bc3ac8593ed94`  
> **Date:** 2026-08-27  
> **Core question:** Can proposal-dependent variance geometry be used to adapt Gaussian component covariance and convert correct mode selection into lower second moment and better cost-adjusted efficiency?

---

# 0. Purpose

RareTopo 当前已经完成三层冻结链：

```text
RareTopo-H3-v1.0
        ↓
RareTopo-M1-v0
        ↓
RareTopo-M1-D-v1.0
```

对应科学进展：

\[
\boxed{
H3:
q
\rightarrow
\text{proposal-dependent variance geometry}
}
\]

\[
\boxed{
M1:
\text{variance geometry}
\rightarrow
\text{missing-mode discovery / Add + Reweight}
}
\]

\[
\boxed{
M1\text{-}D:
\text{variance ranking}
\rightarrow
\text{limited-budget mode selection}
}
\]

M1-D 已经证明，在 preregistered multi-missing-mode ranking-conflict benchmark 上：

- variance selector 的 estimator-critical mode selection 接近 Oracle-V；
- Captured Variance Share 远高于 probability selector；
- selection 差异能够转化为明显更低的 \(M_2\)。

但是 M1-D 仍留下一个关键瓶颈：

\[
\boxed{
VRF_{\mathrm{budget}}^{\mathrm{variance\ full}}
\approx 0.24 < 1
}
\]

也就是说：

> **mode 已经基本选对，但当前 proposal shape 仍不足以在更困难的 multi-mode benchmark 上实现相对 crude MC 的 end-to-end cost advantage。**

M2 的任务不是继续改 selector，而是研究：

\[
\boxed{
\widehat{\nu}_V^{(q_t)}
\longrightarrow
\widehat{\Sigma}_{V,k}
\longrightarrow
\Sigma_{t+1,k}
}
\]

即把 frozen M1 的 proposal update：

\[
(m_k,\pi_k)
\]

扩展为：

\[
\boxed{
(m_k,\Sigma_k,\pi_k)
}
\]

并严格隔离 covariance / proposal-shape 的贡献。

---

# 1. Scientific Motivation

H3-3B 已冻结一个重要事实：

> proposal covariance is a variance-region spread lever in the studied synthetic + real geometry-response benchmark.

因此 M2 不是事后为了提高 VRF 任意增加一个调参旋钮。

科学链条应是：

\[
\boxed{
H3\text{-}3B:
\Sigma
\rightarrow
\text{variance geometry}
}
\]

反向建立：

\[
\boxed{
M2:
\text{variance geometry}
\rightarrow
\Sigma_{\mathrm{next}}
}
\]

从而补齐 proposal-shape closed loop。

---

# 2. Scientific Firewall

M2 只允许研究 covariance / shape。

以下 frozen elements **不允许改变**：

```text
M1-D frozen benchmark set
event definitions
topology definitions
online exploration alpha = 0.5
pilot_n = 20,000
final_eval_n = 100,000
online seed set
variance selector
candidate-ranking rule
eta_main = 0.8
variance-mass HDR semantics
new-component mean / centroid semantics
mixture component birth semantics
stratified probability estimator
stratified variance estimator
stratified bootstrap
frozen SLSQP mixture-weight optimizer
VRF_proposal / VRF_budget definitions
```

特别禁止：

- 重新优化 selector；
- 改 birth threshold；
- 重新筛 benchmark config；
- 改 exploration fraction；
- 加 neural policy；
- 加 component deletion；
- 加 learned covariance；
- 修改 H3/M1/M1-D frozen tags；
- 根据 M2 final result 改 seed / gate / benchmark。

---

# 3. Required Frozen References

开始前必须阅读并记录：

## 3.1 H3

```text
RareTopo-H3-v1.0
```

重点：

```text
closeout/H3_FINAL_INTERFACE.md
closeout/H3_Claim_Ledger.md
H3_Frozen/theory/H3_Theory_Consolidation_Variance_Leakage.md
H3_Frozen/reports/current/H3_3A_set_valued_variance_geometry.md
H3_Frozen/reports/current/H3_3B_Final_Summary.md
```

必须继承：

\[
\rho_V^{(q)}(x)
=
\mathbf1_A(x)\frac{p(x)^2}{q(x)},
\]

\[
M_2(q)
=
\int_A\frac{p(x)^2}{q(x)}dx,
\]

以及 finite-sample variance-mass HDR / \(\nu_V^{(q)}\) 语义。

## 3.2 M1-v0

```text
RareTopo-M1-v0
```

重点：

```text
M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md
M1_v0_Semantic_Correction_Freeze_Audit.md
```

继承 semantic-corrected：

- variance-mass HDR；
- centroid；
- pilot lifecycle；
- weight optimizer；
- legality / budget accounting。

## 3.3 M1-D

```text
RareTopo-M1-D-v1.0
```

重点：

```text
M1_D_Multi_Missing_Mode_Variance_Geometry_Benchmark_Task.md
M1_D_Benchmark_Methodology.md
M1_D_Final_Report.md
M1_D_Benchmark_Freeze.json
```

M2 的 headline benchmark **直接复用 frozen M1-D 的 8 configs**。

不得重新筛选。

---

# 4. Primary Research Question

\[
\boxed{
\begin{aligned}
&\text{Given a variance-critical mode already selected by the frozen M1-D policy,}\\
&\text{can the local shape of proposal-dependent variance geometry be used}\\
&\text{to adapt the covariance of the new Gaussian component, lowering}\\
&M_2\text{ without introducing estimator bias or redistributing catastrophic leakage?}
\end{aligned}
}
\]

更具体：

\[
\boxed{
\widehat{\mathcal L}_{\eta,k}^{(q)}
\rightarrow
\widehat C_{\eta,k}^{V}
\rightarrow
\Sigma_{k}^{new}
}
\]

---

# 5. Main Hypotheses

## H-M2.1 — Variance-region covariance is measurable

在 M1-D frozen pilot 中，对被 variance selector 选中的 mode \(k\)，能够稳定估计：

\[
C_{\eta,k}^{V}
\]

且其主要 eigendirections / anisotropy 在 repeated seeds 下不是纯数值噪声。

## H-M2.2 — Covariance shaping reduces second moment

在 selector、selected mode、component mean、pilot、final evaluation budget 都匹配时，variance-geometry covariance adaptation 应比 frozen base covariance 得到更低：

\[
M_2(q_{\mathrm{final}}).
\]

## H-M2.3 — Gain is not explained only by isotropic spread

full / anisotropic variance-geometry covariance 应至少在部分 configs 上优于仅调整：

\[
\Sigma=s^2I
\]

的 scale-only comparator。

## H-M2.4 — No catastrophic leakage redistribution

降低 selected mode 的 local mismatch 不应通过把 second moment 大量推向其他 unrepresented modes 来实现。

## H-M2.5 — Geometry improvement converts into budget efficiency

由于 covariance estimator 直接复用已有 pilot，不新增 simulator calls，因此若 \(M_2\) 降低，应直接改善：

\[
VRF_{\mathrm{budget}}.
\]

## H-M2.S — Strong efficiency target

一个强结果是：

\[
\boxed{
\operatorname{median}
VRF_{\mathrm{budget}} > 1
}
\]

即在 frozen M1-D difficult benchmark 上跨过 crude-MC cost-efficiency boundary。

该条件是 **Strong Pass**，不是 M2 core mechanism 成立的唯一必要条件。

---

# 6. Explicit Non-Goals

M2-v0 不做：

1. mode selector learning；
2. covariance neural predictor；
3. covariance gradient descent through simulator；
4. simultaneous free optimization of \(m,\Sigma,\pi,K\)；
5. component deletion / merging；
6. real Sanger performance experiment；
7. new benchmark family；
8. high-dimensional scaling claim；
9. universal covariance optimality theorem；
10. posterior / cross-entropy covariance refit；
11. target-density learning；
12. changing M1-D exploration policy。

---

# 7. Scope of Covariance Adaptation

M2-v0 **只适配当前新 birth 的 variance-critical component covariance**。

保持：

```text
primary q0 component covariance = frozen
previously existing components = frozen
new component mean = frozen M1-D variance HDR centroid
new component covariance = M2-controlled variable
```

不在第一版同时重塑全部 mixture components。

这样若有提升，可明确归因于：

> selected missing-mode component 的 proposal shape。

---

# 8. Variance-Region Mean

继续使用 frozen H3/M1：

\[
m_{\eta,k}^{V}
=
\mathbb E_{\nu_V^{(q)}}
[
X
\mid
X\in\mathcal L_{\eta,k}^{(q)}
].
\]

主：

```text
eta_main = 0.8
```

M2 不重新优化 \(\eta\)。

---

# 9. Variance-Region Covariance Definition

定义：

\[
\boxed{
C_{\eta,k}^{V}
=
\mathbb E_{\nu_V^{(q)}}
\left[
(X-m_{\eta,k}^{V})
(X-m_{\eta,k}^{V})^\top
\mid
X\in\mathcal L_{\eta,k}^{(q)}
\right]
}
\]

注意：

该对象是：

> variance-mass conditional second central moment

不是普通 sample covariance。

有限样本中：

\[
\widehat C_{\eta,k}^{V}
=
\frac{
\sum_{i\in\mathcal L_{\eta,k}}
\widehat\omega_i^V
(x_i-\widehat m_{\eta,k})
(x_i-\widehat m_{\eta,k})^\top
}{
\sum_{i\in\mathcal L_{\eta,k}}
\widehat\omega_i^V
}.
\]

这里不使用 Bessel correction，因为目标是经验 measure 的二阶矩，不是普通 IID Gaussian covariance 的无偏估计。

---

# 10. Finite-Sample Weight Semantics

每个 pilot sample：

\[
x_i\sim r_i.
\]

variance-mass weight：

\[
\widetilde\omega_i^V
=
\mathbf1_A(x_i)
\frac{p(x_i)^2}{q_t(x_i)r_i(x_i)}.
\]

必须继续使用 semantic-corrected fixed-stratified pooling。

禁止：

```text
raw sample covariance
unweighted covariance
probability-weight covariance
ignoring r_i
```

作为 M2 主 covariance estimator。

它们可以作为 ablation，但不能冒充 \(\widehat C_{\eta,k}^{V}\)。

---

# 11. Numerical Symmetrization

所有 covariance candidate 在使用前：

\[
C
\leftarrow
\frac12(C+C^\top).
\]

若出现：

```text
NaN
Inf
negative numerical eigenvalue below tolerance
```

必须记录 validity failure / fallback。

不得静默修复。

---

# 12. Variance-Mass ESS

在 HDR region 中定义：

\[
ESS_V
=
\frac{1}
{\sum_i(\bar\omega_i^V)^2}
\]

其中 weights 在该 region 内重新归一化。

记录：

```text
n_region
ESS_V_region
eigenvalues_raw
condition_raw
```

主 covariance adaptation 最低要求：

```text
n_region >= d + 2
ESS_V_region >= 20
```

若不满足：

```text
shape_action = HOLD_BASE_COVARIANCE
```

即：

\[
\Sigma_{new}=\Sigma_{\mathrm{base}}.
\]

这不是 failed trial；必须作为 finite-sample HOLD 行为记录。

---

# 13. Frozen Base Covariance

M1-D frozen new component covariance 记为：

\[
\Sigma_{\mathrm{base}}.
\]

在当前 d=2 u-space benchmark 中预期为 frozen unit covariance：

\[
\Sigma_{\mathrm{base}}=I_2.
\]

代码不得硬编码假设；必须从 frozen proposal metadata 读取并验证。

---

# 14. Covariance Candidate Family

M2-v0 比较五个主要 covariance variants。

## C0 — Frozen Base

\[
\boxed{
\Sigma_{C0}
=
\Sigma_{\mathrm{base}}
}
\]

这是 M1-D frozen control。

## C1 — Isotropic Variance Scale

定义：

\[
s_V^2
=
\frac1d
\operatorname{tr}
(\widehat C_{\eta,k}^{V}).
\]

候选：

\[
\Sigma_{C1}^{pre}
=
s_V^2 I.
\]

然后进入统一 legality projection。

目的：

> 测试单纯“变宽/变窄”能解释多少收益。

## C2 — Diagonal Variance Geometry

\[
\Sigma_{C2}^{pre}
=
\operatorname{diag}
(\widehat C_{\eta,k}^{V}).
\]

然后统一 legality projection。

目的：

> 允许 axis-wise scale，但不使用 rotation / off-diagonal orientation。

## C3 — Full Variance Geometry

\[
\Sigma_{C3}^{pre}
=
\widehat C_{\eta,k}^{V}.
\]

然后统一 legality projection。

这是最直接但最易受 finite-sample noise 影响的版本。

## C4 — Shrunk Full Variance Geometry（M2 主方法）

主方法：

\[
\boxed{
\Sigma_{C4}^{pre}
=
(1-\lambda)
\Sigma_{\mathrm{base}}
+
\lambda
\widehat C_{\eta,k}^{V}
}
\]

固定：

```text
lambda_main = 0.50
```

该值是 M2-v0 preregistered engineering choice，不是 universal optimum。

随后统一 legality projection。

---

# 15. Shrinkage Sensitivity

只做解释性 sensitivity：

```text
lambda = [0.25, 0.50, 0.75]
```

主结果仍固定：

```text
lambda = 0.50
```

不得根据 final evaluation 选择最佳 lambda 后替换主结果。

---

# 16. Gaussian Legality Gate

M2 必须继承 H3/M1 Gaussian second-moment legality discipline。

在当前 standard-normal target + Gaussian proposal component scope 下，proposal covariance 必须满足 frozen integrability requirement。

M2 implementation 必须调用 / 复用项目已有 legality checker，而不是重新定义不一致版本。

额外 numerical safeguard：

```text
lambda_min_floor = 0.55
lambda_max_cap   = 4.00
```

对 eigendecomposition：

\[
\Sigma^{pre}
=
U\operatorname{diag}(\lambda_j)U^\top
\]

定义 legality-projected：

\[
\boxed{
\Sigma
=
U
\operatorname{diag}
(
\operatorname{clip}(\lambda_j,0.55,4.00)
)
U^\top
}
\]

随后再次执行 frozen legality checker。

这些 bounds 是 M2-v0 numerical / legality engineering choices，不是理论常数。

---

# 17. Projection Metadata

每个 trial 保存：

```text
eigenvalues_pre
eigenvalues_post
n_eigen_clipped_low
n_eigen_clipped_high
projection_frobenius_norm
legality_passed
```

如果大量 trial 依赖 clipping，必须在 report 中披露。

不得只展示 projected covariance 而隐藏 raw estimator instability。

---

# 18. Core Paired Experiment Design

M2 的 headline comparison 必须严格 paired。

对每个：

```text
frozen_config
seed
```

先生成 **一次 shared M1-D variance-policy pilot**：

```text
same pilot samples
same selected mode
same variance HDR centroid
same C_eta estimate
```

然后分叉为：

```text
C0
C1
C2
C3
C4
```

所有 variants 共享：

- selected mode；
- component mean；
- base component；
- pilot；
- event labels；
- final evaluation CRN；
- mixture component count。

唯一差异：

\[
\Sigma_{\mathrm{new}}.
\]

---

# 19. Selection Lock

为隔离 shape，M2 headline experiment 中：

\[
\boxed{
\text{selected mode is computed exactly once}
}
\]

由 frozen M1-D variance selector 产生。

随后 C0–C4 都使用同一个 selected mode。

禁止每个 covariance variant 自己重新选 mode。

---

# 20. Mean Lock

C0–C4 使用同一个：

\[
m_{\eta=0.8,k}^{V}.
\]

禁止：

```text
covariance variant
→ recompute different centroid
```

这样 mean 不成为 confounder。

---

# 21. Two Weight Layers

为了区分 covariance 直接作用与 covariance+reweight 的 deployable 效果，M2 分两层。

## Layer A — Shape-Only

所有 C0–C4 使用：

> C0 frozen M1-D update 得到的同一组 mixture weights。

也就是：

\[
\pi=\pi_{C0}.
\]

然后只改变 covariance。

目的：

\[
\boxed{
\text{isolated covariance effect}
}
\]

## Layer B — Shape + Frozen Reweight

对每个 covariance candidate：

- means fixed；
- covariance fixed；
- component set fixed；
- 运行 **同一个 frozen M1-v0 SLSQP weight optimizer**；
- 不修改 optimizer 参数。

目的：

> 评估 deployable covariance adaptation 与既有 weight update 的兼容收益。

主方法 headline performance 使用 Layer B。

Layer A 用于因果归因。

---

# 22. Data-Splitting Firewall

不得用 final evaluation sample 估 covariance。

每个 trial：

```text
pilot
    ↓
selected mode
    ↓
m_eta
    ↓
C_eta
    ↓
Sigma candidate
    ↓
(optional frozen weight refit on declared pilot fit data)
    ↓
freeze proposal
    ↓
independent final evaluation
```

禁止：

```text
final eval
→ pick covariance variant
→ report as main
```

---

# 23. Simulator Budget

M2 covariance estimation直接复用 M1-D pilot。

因此主 C0–C4 comparison：

```text
extra simulator calls for covariance estimation = 0
```

继承：

```text
pilot_n = 20,000 / round
final_eval_n = 100,000
alpha_p = 0.5
seed set = [2026..2033]
```

所有额外计算只允许是：

```text
matrix operations
density evaluation
SLSQP weight solve
```

不得增加 simulator calls 以帮助某个 covariance variant。

---

# 24. Frozen Benchmark Set

直接使用：

```text
RareTopo-M1-D-v1.0
```

中的 8 frozen configs：

```text
c000
c001
c004
c006
c007
c010
c017
c020
```

不得：

- 删除困难 config；
- 加新 config 替换；
- 根据 M2 结果重新筛选。

每个 config：

```text
8 seeds
```

共：

\[
8\times8=64
\]

paired headline trials / covariance method。

---

# 25. Primary Metrics

## 25.1 Second moment

\[
\boxed{
M_2(q_{\mathrm{final}})
}
\]

是主 metric。

## 25.2 Relative M2 vs frozen covariance

\[
\boxed{
R_{M2}^{shape}
=
\frac{
M_2(q_{\mathrm{M2}})
}{
M_2(q_{C0})
}
}
\]

越低越好。

## 25.3 Budget-adjusted VRF

继续使用 frozen semantic-corrected：

\[
VRF_{\mathrm{budget}}.
\]

## 25.4 Proposal-level VRF

同时报告：

\[
VRF_{\mathrm{proposal}}.
\]

不得与 budget VRF 混淆。

---

# 26. Leakage Redistribution Metrics

对每个 topology mode \(j\)：

\[
L_j(q).
\]

定义：

\[
R_{L,j}
=
\frac{
L_j(q_{\mathrm{M2}})
}{
L_j(q_{C0})
}.
\]

重点记录：

```text
selected-mode leakage ratio
max off-target leakage ratio
sum off-target leakage
```

不得只看 selected mode。

---

# 27. Variance-Geometry Shape Diagnostics

记录：

## 27.1 Eigenvalues

\[
\lambda_1(C_{\eta}),
\lambda_2(C_{\eta}).
\]

## 27.2 Anisotropy ratio

\[
\boxed{
A_C
=
\frac{
\lambda_{\max}(C_{\eta})
}{
\lambda_{\min}(C_{\eta})+\epsilon
}
}
\]

## 27.3 Eigenvector alignment

比较 \(C_{\eta}\) 与最终 proposal covariance 的主方向。

## 27.4 Covariance change magnitude

\[
\|\Sigma_{new}-\Sigma_{base}\|_F.
\]

---

# 28. Mahalanobis Mismatch Diagnostic

定义：

\[
\boxed{
D_{\eta,k}(\Sigma)
=
\mathbb E_{\nu_V}
[
(X-m_{\eta,k})^\top
\Sigma^{-1}
(X-m_{\eta,k})
\mid
X\in\mathcal L_{\eta,k}
]
}
\]

有限样本使用 variance-mass weights。

该指标只做 geometry diagnostic，不得替代 \(M_2\) success gate。

---

# 29. Probability Consistency / Bias Gate

所有 covariance methods 仍必须给出一致 rare-event probability estimate。

对 paired methods 报告：

\[
\widehat P
\]

及标准误。

如果某 covariance method 的 probability estimate 与 frozen reference 显著不一致且超过预先声明的 statistical tolerance：

```text
INVALID / investigate
```

不得把 biased estimator 的低 M2 当成功。

---

# 30. Core Success Gates

## Gate M2-0 — Validity

全部要求：

- parent tags unchanged；
- benchmark hash matched；
- selection lock；
- mean lock；
- source density correct；
- covariance SPD；
- frozen legality checker pass；
- no final-eval leakage；
- full pytest pass；
- no missing result cells；
- estimator probability consistency。

失败：

```text
INVALID
```

## Gate M2-1 — Covariance Estimator Stability

至少：

```text
>= 7 / 8 configs
```

的 per-config median trial 满足：

- `ESS_V_region >= 20` 或合法 HOLD；
- covariance finite；
- legality projection finite；
- no systematic NaN / singularity。

并报告 HOLD frequency。

## Gate M2-2 — Core Second-Moment Gain

主方法 C4 / Layer B：

\[
\boxed{
\operatorname{median}_{config}
\left[
\operatorname{median}_{seed}
\frac{M_2(C4)}{M_2(C0)}
\right]
\le0.85
}
\]

同时至少：

```text
6 / 8 configs
```

有：

\[
\operatorname{median}_{seed}M_2(C4)
<
\operatorname{median}_{seed}M_2(C0).
\]

## Gate M2-3 — Shape-Only Evidence

Layer A：

\[
\operatorname{median}
\frac{M_2(C4_{\mathrm{shape-only}})}
{M_2(C0_{\mathrm{shape-only}})}
<1.
\]

否则不能声称 direct covariance-shape effect。

## Gate M2-4 — No Catastrophic Leakage Redistribution

在至少：

```text
7 / 8 configs
```

中：

\[
\boxed{
\operatorname{median}_{seed}
\left[
\max_{j\ne k_{\mathrm{selected}}}
R_{L,j}
\right]
\le2.0
}
\]

同时总体 \(M_2(C4)<M_2(C0)\) 必须成立于 Gate M2-2 的 configs。

## Gate M2-5 — Relative Budget Efficiency

要求：

\[
\boxed{
\operatorname{median}
VRF_{\mathrm{budget}}(C4)
>
\operatorname{median}
VRF_{\mathrm{budget}}(C0)
}
\]

且：

\[
\boxed{
\operatorname{median}
\frac{
VRF_{\mathrm{budget}}(C4)
}{
VRF_{\mathrm{budget}}(C0)
}
\ge1.25
}
\]

---

# 31. Strong Gate — Absolute Cost Efficiency

定义：

\[
\boxed{
\text{M2-Strong}
:
\operatorname{median}
VRF_{\mathrm{budget}}(C4)>1
}
\]

解释：

- 若通过：M2 把 M1-D 从 relative-policy success 推到 absolute cost-efficiency success；
- 若未通过但 M2-2/3/4/5 通过：
  > covariance mechanism works, but difficult benchmark remains not yet cost-effective vs crude MC.

不得把 Strong Gate 失败写成整个 M2 scientific failure。

---

# 32. Isotropic vs Anisotropic Gate

比较 C1 vs C4。

若：

\[
M_2(C4)<M_2(C1)
\]

在至少：

```text
5 / 8 configs
```

的 per-config median 上成立，则支持：

> anisotropic variance geometry adds value beyond scalar spread.

若不成立，则结论必须收紧为：

> covariance gain is primarily a scale/spread effect in this benchmark.

这不是主方法 fail。

---

# 33. C2/C3 Interpretation

C2：

> axis-aligned anisotropy.

C3：

> raw full empirical geometry.

C4：

> shrunk full geometry.

如果 C3 比 C4 更差：

可解释为 finite-sample regularization 价值。

如果 C2≈C4：

可说明 off-diagonal rotation contribution 很小。

禁止只报告最好的一个 variant。

---

# 34. Optional Offline Covariance Oracle

只作为 secondary reference。

如果能够在 **不增加 simulator calls**、只重用 frozen/offline reference samples 的情况下，对 selected mode 评估固定 covariance candidate grid，则可定义：

```text
Oracle-Cov
```

但：

- 不进入 M2 core gate；
- 不向 online policy 泄漏；
- 不因为实现 oracle 延迟主实验；
- 如果需要重新运行 simulator，则 M2-v0 不做。

---

# 35. Required Ablations

## Ablation M2-A — Scale only

C0 vs C1。

## Ablation M2-B — Diagonal vs Full

C2 vs C3/C4。

## Ablation M2-C — Raw vs Shrinkage

C3 vs C4。

## Ablation M2-D — lambda sensitivity

```text
0.25
0.50
0.75
```

主值 0.50 不变。

## Ablation M2-E — Shape-only vs Shape+Reweight

Layer A vs Layer B。

## Ablation M2-F — ESS stratification

按 low / medium / high `ESS_V_region` 报告 covariance gain。

---

# 36. No New Hyperparameter Search

禁止：

```text
run lambda grid on final eval
→ choose best lambda
→ call it main
```

Main prereg method：

```text
C4
lambda = 0.50
```

其它都是 ablation。

---

# 37. Seeds and CRN

固定：

```text
[2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
```

C0–C4 在同 config/seed 下共享：

- adaptation pilot RNG；
- selected mode；
- final-evaluation base randomness / CRN where legal。

所有 paired statistics 按：

```text
(config, seed)
```

配对。

---

# 38. Hierarchical Statistics

与 M1-D 一致：

## within config

8 seeds。

## across configs

8 frozen configs 的 per-config medians。

headline Gate M2-2 优先使用：

```text
median of per-config paired medians
```

不得把 64 trials 当完全 IID 后只报告一个 p-value。

---

# 39. Statistical Reporting

至少报告：

```text
all 64 trial values / method
per-config median
global median
mean
std
min/max
paired bootstrap 95% CI
config win count
seed-level win count
```

重点 comparison：

\[
\log M_2(C4)-\log M_2(C0)
\]

可作为稳定 paired effect summary。

---

# 40. Required Tests

至少新增：

```text
test_m2_weighted_variance_covariance_toy
test_m2_covariance_symmetry
test_m2_covariance_ess
test_m2_covariance_hold_low_ess
test_m2_eigen_projection
test_m2_frozen_legality_checker
test_m2_selection_lock
test_m2_mean_lock
test_m2_shape_only_same_weights
test_m2_shape_reweight_same_optimizer
test_m2_no_final_eval_leakage
test_m2_no_extra_simulator_calls
test_m2_result_schema
test_m2_leakage_redistribution_metrics
```

并运行：

```bash
pytest -q
```

要求 full suite exit 0。

---

# 41. Toy / Sanity Stage

大规模 M1-D benchmark 前必须先做：

## M2-S1 — Weighted cloud toy

构造已知 weighted anisotropic point cloud。

验证：

- weighted centroid；
- weighted covariance；
- eigen orientation；
- ESS；
- shrinkage；
- projection。

## M2-S2 — Half-space / simple Geometry-IS

目标不是证明 covariance optimality。

只验证：

- estimator unbiased；
- legality；
- C0 不被错误破坏；
- covariance machinery 不产生数值异常；
- HOLD 行为正确。

Sanity 不作为 headline performance claim。

---

# 42. Run Order

严格：

```text
M2-0
Task freeze
    ↓
M2-1
weighted covariance estimator + tests
    ↓
M2-2
legality projection + sanity
    ↓
M2-3
frozen M1-D C0–C4 Layer A
    ↓
M2-4
C0–C4 Layer B
    ↓
M2-5
leakage / budget / robustness audit
    ↓
M2-6
ablations + lambda sensitivity
    ↓
M2-7
final gate report
```

---

# 43. Stop / Go Rules

## Stop after M2-1

如果 weighted covariance estimator 无法稳定复现，或大量：

```text
ESS_V < 20
```

导致 HOLD：

```text
STOP
```

先解决 finite-sample geometry estimation。

## Stop after Layer A

若：

\[
M_2(C4_{\mathrm{shape-only}})
\]

系统性不低于 C0：

不要立刻用 Layer B 的 weight reoptimization “救结果”。

先记录：

> direct covariance-shape hypothesis not supported.

Layer B 可作为 diagnostic，但不能混淆 causal claim。

## Go to full M2 claim

至少：

```text
M2-0 PASS
M2-1 PASS
M2-2 PASS
M2-3 PASS
M2-4 PASS
M2-5 PASS
```

才可称：

> variance-geometry covariance adaptation supported.

Strong Gate 决定是否获得 absolute cost-efficiency headline。

---

# 44. Interpretation Matrix

| Shape-only M2 ↓ | Layer B M2 ↓ | leakage safe | VRF_budget > C0 | VRF_budget >1 | Interpretation |
|---|---|---|---|---|---|
| No | No | — | No | No | covariance geometry 没有方法收益 |
| No | Yes | Yes | Yes | No | 收益主要来自 covariance-weight interaction，direct shape claim 不成立 |
| Yes | Yes | No | — | — | shape 改善但造成 variance redistribution，不安全 |
| Yes | Yes | Yes | Yes | No | **Core M2 success**，但仍未超过 MC cost efficiency |
| Yes | Yes | Yes | Yes | Yes | **Strong M2 success** |

---

# 45. Main Machine-Readable Schema

每个 record 至少：

```json
{
  "schema_version": "raretopo-m2-v0",
  "h3_tag": "RareTopo-H3-v1.0",
  "m1_tag": "RareTopo-M1-v0",
  "m1d_tag": "RareTopo-M1-D-v1.0",
  "benchmark_hash": "...",
  "config_id": "c000",
  "seed": 2026,
  "layer": "shape_only|shape_reweight",
  "covariance_method": "C0|C1|C2|C3|C4",
  "selected_mode": "Sx",
  "eta": 0.8,
  "pilot": {
    "n": 20000,
    "alpha_p": 0.5
  },
  "variance_region": {
    "n_region": 0,
    "ess_v": 0.0,
    "centroid": [],
    "cov_raw": [],
    "eig_raw": []
  },
  "covariance": {
    "lambda": 0.5,
    "sigma_pre": [],
    "sigma_final": [],
    "eig_pre": [],
    "eig_final": [],
    "clipped_low": 0,
    "clipped_high": 0,
    "legality_passed": true,
    "hold": false
  },
  "evaluation": {
    "n": 100000,
    "P_hat": 0.0,
    "M2_hat": 0.0,
    "VRF_proposal": 0.0,
    "VRF_budget": 0.0,
    "mode_L": {}
  },
  "cost": {
    "extra_simulator_calls_covariance": 0
  },
  "validity": {}
}
```

---

# 46. Required Outputs

```text
docs/phase_m2/
├── M2_Variance_Geometry_Covariance_Adaptation_Task.md
├── M2_Covariance_Methodology.md
├── M2_Covariance_Legality_Audit.md
└── M2_Final_Report.md

configs/phase_m2/
├── m2_covariance_v0.json
└── m2_lambda_sensitivity.json

src/hyptraj/m2/
├── variance_covariance.py
├── covariance_projection.py
├── covariance_policy.py
└── metrics.py

scripts/
├── run_m2_sanity.py
├── run_m2_covariance_experiments.py
├── run_m2_gate_audit.py
└── run_m2_figures.py

results/phase_m2/
├── sanity/
├── layer_a_shape_only/
├── layer_b_shape_reweight/
├── ablations/
└── summary/

figures/phase_m2/
└── figure_M2_*.png
```

---

# 47. Required Figures

1. **Figure M2-1 — Variance Region and Covariance Ellipse**
2. **Figure M2-2 — Eigenvalue / Anisotropy Summary**
3. **Figure M2-3 — M2 C0–C4**
4. **Figure M2-4 — Shape-only vs Shape+Reweight**
5. **Figure M2-5 — Leakage Redistribution**
6. **Figure M2-6 — Budget VRF**（标出 MC boundary = 1）
7. **Figure M2-7 — ESS vs Covariance Gain**
8. **Figure M2-8 — Lambda Sensitivity**

---

# 48. Claim Boundary

如果 Core Gates 通过、Strong Gate 未通过，最强允许：

> **On the frozen multi-missing-mode RareTopo benchmark, adapting the covariance of a variance-critical proposal component using local proposal-dependent variance geometry reduces estimator second moment relative to the frozen isotropic covariance under matched selection, mean, and simulator budgets. The resulting method remains below crude-MC cost efficiency on this benchmark.**

若 Strong Gate 也通过，可升级：

> **... and converts the variance-guided adaptive mixture into a cost-effective estimator relative to crude Monte Carlo under the preregistered total simulator budget.**

不得写：

> variance covariance is universally optimal.

不得写：

> covariance adaptation solves high-dimensional adaptive IS.

---

# 49. Negative Result Policy

必须接受：

## Case A — C1 ≈ C4

> 主要收益来自 isotropic spread，而非 anisotropic shape。

## Case B — C3 unstable, C4 works

> shrinkage / finite-sample regularization 是方法必要部分。

## Case C — Layer A fail, Layer B pass

> covariance 本身没有独立 direct effect，收益主要来自 covariance 与 weight optimizer interaction。

## Case D — M2 lowers M2 but VRF_budget still <1

> proposal-shape mechanism有效，但当前 difficult benchmark 仍未跨过 MC boundary。

## Case E — covariance reduces selected leakage but increases another mode

> local covariance matching alone is insufficient；variance 被重新分配。

不得通过删 config 或改 lambda 隐藏负结果。

---

# 50. Preregistration Lock

Task commit 后以下锁死：

```text
parent tags
8 frozen configs
seed set
eta_main = 0.8
pilot budget
final evaluation budget
selection policy
selected-mode lock
mean lock
C0–C4 definitions
lambda_main = 0.50
lambda sensitivity set
ESS threshold = 20
eigen floor = 0.55
eigen cap = 4.00
Layer A / B semantics
Gate M2-0..M2-5
Strong Gate
```

任何必要修改：

```text
M2_PREREG_AMENDMENT_<date>.md
```

必须记录：

- old；
- new；
- reason；
- 是否已看 final result；
- 是否需要 untouched rerun。

---

# 51. Completion Checklist

## Freeze / provenance

- [ ] H3 tag recorded
- [ ] M1-v0 tag recorded
- [ ] M1-D tag recorded
- [ ] M1-D benchmark hash verified
- [ ] task committed before M2 runs

## Estimator

- [ ] weighted covariance implemented
- [ ] toy covariance test
- [ ] ESS test
- [ ] HOLD test
- [ ] symmetrization test
- [ ] eigen projection test
- [ ] frozen legality checker pass

## Fairness

- [ ] selection locked
- [ ] mean locked
- [ ] pilot shared
- [ ] C0–C4 final CRN paired
- [ ] Layer A same weights
- [ ] Layer B same optimizer
- [ ] zero extra simulator calls

## Experiments

- [ ] sanity complete
- [ ] 8 configs × 8 seeds
- [ ] C0–C4 Layer A complete
- [ ] C0–C4 Layer B complete
- [ ] lambda sensitivity complete
- [ ] leakage audit complete

## Gates

- [ ] M2-0
- [ ] M2-1
- [ ] M2-2
- [ ] M2-3
- [ ] M2-4
- [ ] M2-5
- [ ] Strong Gate reported separately

## Reporting

- [ ] all trial records retained
- [ ] no cherry-picking
- [ ] all figures reproducible
- [ ] full pytest pass
- [ ] final gate audit
- [ ] claim wording follows actual verdict

---

# 52. Immediate Next Instruction

本 Task freeze 后，**不要直接跑 64×5 benchmark**。

先执行：

\[
\boxed{
\text{M2-1:
weighted variance-region covariance estimator
+
toy tests
+
legality projection}
}
\]

只完成：

```text
C_eta estimator
ESS
C0–C4 constructor
eigen projection
frozen legality check
unit tests
```

然后运行：

```text
M2-S1 weighted cloud toy
M2-S2 half-space sanity
```

只有 sanity 全通过后，才允许进入 frozen M1-D benchmark。

---

# 53. One-Line State

```text
H3 = frozen
M1-v0 = frozen
M1-D = frozen
M2 = preregistered
M2 scientific runs = NOT STARTED
next gate = variance-region covariance estimator + legality sanity
```

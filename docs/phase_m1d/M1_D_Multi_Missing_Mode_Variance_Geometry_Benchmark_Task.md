# M1-D Multi-Missing-Mode Variance-Geometry Benchmark — Preregistered Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems  
> **Method Track:** M1-D — Multi-Missing-Mode Variance-Geometry Benchmark  
> **Document type:** Preregistered benchmark / experiment task specification  
> **Status:** **PREREGISTERED — NOT STARTED**  
> **Parent frozen method:** `RareTopo-M1-v0`  
> **Parent frozen science:** `RareTopo-H3-v1.0`  
> **M1-v0 frozen HEAD:** `a825863ec20f8dfe0f4011c0f1ec71faf2a893db`  
> **H3 frozen source commit:** `5faef86b9d0ff35eb2cee762ec24a363796f6ce1`  
> **Date:** 2026-08-27  
> **Core question:** When several unrepresented topology modes compete for a limited adaptation budget, does variance geometry select estimator-critical modes better than probability geometry?

---

# 0. Purpose

M1-v0 已经冻结并证明：

\[
\boxed{
\text{exploration}
\rightarrow
\widehat{\nu}_V^{(q)}
\rightarrow
\text{missing-mode diagnosis}
\rightarrow
\text{Add + Reweight}
\rightarrow
M_2\downarrow
}
\]

其核心结果包括：

- variance-important missing mode discovery：8/8；
- corrected Benchmark B median：
  \[
  M_2 \approx 0.01592;
  \]
- oracle gap：
  \[
  M_2(\mathrm{M1})/M_2(\mathrm{H3\text{-}2\ M3})
  \approx 1.011;
  \]
- proposal-level：
  \[
  VRF_{\text{proposal}}\approx6.39;
  \]
- budget-adjusted：
  \[
  VRF_{\text{budget}}\approx3.99.
  \]

但是 M1-v0 还留下一个重要 scientific gap：

> 在 frozen Benchmark B 中，主要只有一个真正需要新增的 secondary missing mode。只要 probability-based policy 能观察到它，它实际上“没有多少选择”。

因此 M1-v0 尚不能强力证明：

\[
\boxed{
\text{variance ranking}
\text{ 比 }
\text{probability ranking}
\text{ 更适合 adaptation resource allocation}
}
\]

M1-D 专门解决这个问题。

---

# 1. M1-D 的核心思想

构造一个受控但非单候选的 topology-mixture benchmark：

\[
A
=
A_0
\sqcup
A_1
\sqcup
A_2
\sqcup
A_3
\sqcup \cdots
\]

其中初始 proposal \(q_0\) 已覆盖 primary mode \(A_0\)，但至少存在：

\[
\boxed{
K_{\mathrm{missing}}\ge3
}
\]

个 unrepresented candidate modes。

同时故意要求：

\[
\boxed{
\operatorname{rank}_P(k)
\ne
\operatorname{rank}_L(k)
}
\]

即 target probability ranking 与 proposal-dependent variance ranking 冲突。

最重要的 benchmark condition：

\[
\boxed{
\arg\max_{k\in\mathcal M} P_k
\ne
\arg\max_{k\in\mathcal M} L_k(q_0)
}
\]

其中：

\[
P_k
=
\int_{A_k}p(x)dx,
\]

而：

\[
L_k(q_0)
=
\int_{A_k}
\frac{p(x)^2}{q_0(x)}
dx.
\]

这样 adaptation budget 不足以覆盖全部 missing modes 时，算法必须真正回答：

> **应该先把 proposal mass 花在哪一个 mode 上？**

---

# 2. Scientific Firewall

M1-D 不是一个新 adaptive algorithm。

它是：

\[
\boxed{
\text{frozen M1-v0 method}
+
\text{harder benchmark}
+
\text{signal-selection audit}
}
\]

因此禁止：

- 修改 M1-v0 core algorithm；
- 根据 M1-D 结果重新调 M1-v0 birth threshold；
- 修改 M1-v0 `eta_main=0.8`；
- 改变 M1-v0 variance-mass estimator；
- 改变 stratified bootstrap；
- 改变 mixture-weight optimizer；
- 添加 covariance adaptation；
- 添加 ML policy；
- 添加 component deletion；
- 将 M1-D 结果反向写入 `RareTopo-M1-v0` tag。

M1-D 的任何代码 / config / results 必须在新的 namespace 中。

---

# 3. Required Frozen References

## 3.1 H3 frozen

必须阅读：

```text
RareTopo-H3-v1.0
```

重点：

```text
closeout/H3_Claim_Ledger.md
closeout/H3_FINAL_INTERFACE.md
H3_Frozen/theory/H3_Theory_Consolidation_Variance_Leakage.md
H3_Frozen/reports/current/H3_3A_set_valued_variance_geometry.md
H3_Frozen/reports/current/H3_3B_Final_Summary.md
```

继承：

\[
M_2(q)
=
\sum_kL_k(q),
\]

\[
\omega_k^V(q)
=
\frac{L_k(q)}{M_2(q)},
\]

以及 proposal-dependent variance measure：

\[
\nu_V^{(q)}.
\]

## 3.2 M1-v0 frozen

必须阅读：

```text
RareTopo-M1-v0
```

重点：

```text
docs/phase_m1/M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md
docs/phase_m1/M1_v0_Semantic_Correction_Freeze_Audit.md
docs/phase_m1/M1_PREREG_AMENDMENT_Semantic_Correction.md
```

M1-D 必须直接复用 semantic-corrected implementation，包括：

```text
variance-mass HDR semantics
stratified probability estimator
stratified bootstrap
multi-component add_component fix
budget accounting fix
VRF_proposal / VRF_budget split
explicit exploration component
```

---

# 4. Primary Research Question

\[
\boxed{
\begin{aligned}
&\text{When multiple unrepresented topology modes are simultaneously observable,}\\
&\text{and probability importance conflicts with estimator-variance importance,}\\
&\text{does variance-geometry-guided adaptation allocate a limited proposal}\\
&\text{budget more effectively than probability-guided adaptation?}
\end{aligned}
}
\]

换句话说：

\[
\boxed{
\text{What is likely?}
\quad\neq\quad
\text{What is estimator-critical?}
}
\]

---

# 5. Main Hypotheses

## H-D1 — Ranking conflict is measurable

对冻结后的 M1-D benchmark set：

\[
\operatorname{rank}(P_k)
\]

与：

\[
\operatorname{rank}(L_k(q_0))
\]

必须存在系统性 discordance。

至少要求：

\[
\arg\max P_k
\ne
\arg\max L_k(q_0)
\]

在所有 headline benchmark config 中成立。

## H-D2 — Variance ranking identifies the correct first action

当仅允许增加一个 component 时，variance-guided selector 应更频繁选择 offline oracle 定义的：

\[
k_V^*
=
\arg\max_{k\in\mathcal M}
L_k(q_0)
\]

而 probability-guided selector 更倾向：

\[
k_P^*
=
\arg\max_{k\in\mathcal M}
P_k.
\]

## H-D3 — Selection quality converts into second-moment gain

在相同 exploration / pilot / birth / evaluation budget 下，variance-guided policy 应获得更低：

\[
M_2(q_{\mathrm{final}}).
\]

## H-D4 — Advantage is not only a centroid effect

在 selection-only controlled comparator 中，即使两种方法使用相同 downstream component-construction rule，variance ranking 仍应带来更高 captured variance share / 更低 \(M_2\)。

## H-D5 — Advantage strengthens under tighter adaptation budget

当：

\[
B_{\mathrm{birth}}
<
K_{\mathrm{missing}},
\]

selection signal 的价值应更明显。因此 1-birth challenge 是主要 headline，2-birth challenge 用于观察 budget relaxation。

## H-D6 — No estimator bias

任何性能提升必须来自 proposal variance 改善，而不是 probability estimate bias。

---

# 6. Explicit Non-Goals

M1-D 不尝试：

1. 优化 covariance；
2. 学习神经 proposal；
3. 证明 universal variance-ranking optimality；
4. 解决 high-dimensional scaling；
5. 做 real Sanger performance headline；
6. 用 oracle \(L_k\) 给在线 M1 policy；
7. 把 benchmark-design oracle 暗中泄露给 online algorithm；
8. 重新寻找“更容易赢”的 seed；
9. 只展示 probability-policy 失败的 config；
10. 将特定 benchmark 阈值写成 universal constant。

---

# 7. Benchmark Design Principle

M1-D 必须设计成：

\[
\boxed{
\text{observable}
+
\text{multi-candidate}
+
\text{ranking-conflicted}
+
\text{budget-limited}
}
\]

四个条件缺一不可。

---

# 8. Topology Structure Requirement

Headline benchmark 每个 system 至少：

```text
1 primary represented mode
+
3 unrepresented missing modes
```

即：

\[
K_{\mathrm{missing}}\ge3.
\]

推荐总结构：

\[
A
=
A_0
\sqcup
A_1
\sqcup
A_2
\sqcup
A_3.
\]

其中：

- \(A_0\)：initial Geometry-IS 已覆盖；
- \(A_1,A_2,A_3\)：初始均没有专门 proposal component。

---

# 9. Benchmark-Design Oracle vs Online Oracle

## 9.1 Benchmark-design oracle

用于实验开始前：

- 判断 synthetic config 是否满足 ranking-conflict eligibility；
- 冻结 benchmark；
- 生成 post-hoc ground truth。

允许使用：

- high-N reference MC / IS；
- exact simulator；
- frozen event topology；
- offline estimates of \(P_k\) 和 \(L_k(q_0)\)。

## 9.2 Online policy

运行时禁止获得：

```text
true P_k
true L_k
true mode ranking
true leakage point
true oracle component order
offline benchmark-design labels beyond normal topology label
```

它只能使用 exploration pilot、exact topology labels、densities \(p,q_t,r_i\) 和 finite-sample estimates。

---

# 10. Benchmark Construction Without Cherry-Picking

禁止：

```text
先跑 M1
→ 看哪些 config variance method 赢
→ 只保留这些 config
```

采用 deterministic candidate-generation + eligibility filter。

## 10.1 Candidate pool

优先复用 H3 synthetic / curved multi-mode generator。

若现有 generator 支持 deterministic enumeration：

```text
candidate_generation_seed = 20260827
candidate_pool_size = 64
```

生成 64 个 candidate configs。

若现有 generator 无此接口：

> 新增最小 deterministic wrapper，但不得改变 simulator physics。

## 10.2 Offline reference budget

每个 candidate：

```text
N_reference = 500,000
```

若 reference uncertainty 不足，可在所有候选统一规则下提升到：

```text
1,000,000
```

不得只给某个“想保留的 config”增加预算。

---

# 11. Eligibility Criteria

candidate 只有同时满足以下条件才可进入 M1-D：

## E1 — Candidate count

\[
K_{\mathrm{missing}}\ge3.
\]

## E2 — Observability

主 exploration：

\[
\alpha=0.5,
\qquad
N_{\mathrm{pilot}}=20,000.
\]

每个 headline candidate mode 的 target-distribution expected observation count 至少：

\[
N_pP_k\ge10,
\]

其中：

\[
N_p=\alpha N_{\mathrm{pilot}}.
\]

## E3 — Top-rank conflict

\[
k_P^*
=
\arg\max P_k
\ne
k_V^*
=
\arg\max L_k(q_0).
\]

## E4 — Strong inversion

至少存在一对 \(a,b\)：

\[
P_a>P_b
\]

但：

\[
L_a(q_0)<L_b(q_0),
\]

并要求：

\[
\frac{P_a}{P_b}\ge1.5
\]

且：

\[
\frac{L_b(q_0)}{L_a(q_0)}\ge1.5.
\]

这些 1.5 阈值只是 benchmark difficulty criterion。

## E5 — Variance-criticality

top variance missing mode：

\[
k_V^*
\]

必须贡献至少：

\[
\omega_{k_V^*}^{V,\mathrm{missing}}
=
\frac{L_{k_V^*}}
{\sum_{j\in\mathcal M}L_j}
\ge0.35.
\]

## E6 — No degenerate single-mode domination

同时不允许：

\[
\omega_{k_V^*}^{V,\mathrm{missing}}>0.90.
\]

因此：

\[
0.35
\le
\omega_{k_V^*}^{V,\mathrm{missing}}
\le
0.90.
\]

---

# 12. Freeze Benchmark Set Before Adaptive Runs

从 candidate pool 中按 deterministic `config_id` 排序，选择：

```text
前 8 个满足 eligibility 的 configs
```

作为：

\[
\boxed{
\text{M1-D Frozen Benchmark Set}
}
\]

若 64 个 candidate 中不足 8 个满足条件：

- 不降低 eligibility threshold；
- 生成第二批 deterministic pool；
- seed 固定为 `20260828`；
- 保持同一 eligibility；
- 直到获得 8 个 configs。

必须在运行 adaptive policy 前生成：

```text
M1_D_Benchmark_Freeze.json
M1_D_Benchmark_Freeze.md
```

记录：

- config id；
- generator seed；
- parameters；
- \(P_k^{ref}\)；
- \(L_k^{ref}(q_0)\)；
- probability ranking；
- variance ranking；
- eligibility checks；
- SHA256。

一旦 freeze，不允许删除困难 config。

---

# 13. Ranking Metrics

每个 system 报告：

\[
r_k^P
=
\operatorname{rank}_{\downarrow}(P_k),
\]

\[
r_k^V
=
\operatorname{rank}_{\downarrow}(L_k(q_0)).
\]

包括：

- Top-1 conflict；
- Kendall \(	au_{P,V}\)；
- Spearman \(ho_{P,V}\)；
- pairwise inversion count：
  \[
  N_{\mathrm{inv}}
  =
  \#\{(a,b):P_a>P_b, L_a<L_b\}.
  \]

---

# 14. Main Adaptation Budgets

## D1 — One-Birth Challenge

主 headline：

```text
max_new_components = 1
```

即：

\[
B_{\mathrm{birth}}=1.
\]

## D2 — Two-Birth Challenge

secondary：

```text
max_new_components = 2
```

且仍要求：

\[
K_{\mathrm{missing}}\ge3.
\]

---

# 15. Pilot Policy

继承 M1-v0：

\[
\alpha
=
P(\text{pilot source}=p)
=
0.5.
\]

每轮：

```text
pilot_n = 20,000
10,000 from current q_t
10,000 from p
```

使用：

- correct source density；
- stratified estimator；
- stratified bootstrap；
- semantic-corrected variance HDR。

M1-D 不重新优化 \(lpha\)。

---

# 16. Candidate Discovery Gate

M1-D 核心不是“是否有一个 mode 过 threshold”，而是多个候选都可观察后如何排序。

对 unrepresented mode：

```text
candidate(k) = true
```

至少要求：

- mode observed ≥ 5；
- topology label valid；
- represented_by_component = false；
- estimator uncertainty finite。

M1-D 不应通过过高 threshold 预先删光候选。

---

# 17. Layer A — Selection-Only Comparator

目的：

\[
\boxed{
\text{只比较“选哪个 mode”}
}
\]

不让 downstream proposal-action 差异污染结论。

## 17.1 Probability selector

估计：

\[
\widehat P_k,
\]

选择：

\[
\widehat k_P
=
\arg\max_{k\in\mathcal M_{\mathrm{cand}}}
\widehat P_k.
\]

## 17.2 Variance selector

估计：

\[
\widehat L_k
\]

或 \(\widehat\omega_k^V\)，选择：

\[
\widehat k_V
=
\arg\max_{k\in\mathcal M_{\mathrm{cand}}}
\widehat L_k.
\]

## 17.3 Common downstream action

两者使用完全相同的：

```text
component-center rule
component covariance
initial component weight
weight optimizer
evaluation budget
```

为避免向 probability selector 泄漏 variance geometry，common center 使用 target-probability conditional centroid：

\[
m_k^P
=
E_p[X\mid A_k].
\]

---

# 18. Layer B — Full Policy Comparator

## 18.1 Probability-guided full policy

```text
explore
→ estimate P_k
→ rank by P_k
→ add top-ranked unrepresented mode
→ probability centroid
→ probability-proportional weights
```

禁止使用：

```text
nu_V
L_k
variance centroid
variance-aware weight objective
```

## 18.2 Variance-geometry full policy

直接使用 frozen M1-v0：

```text
explore
→ estimate nu_V
→ rank by L_k / omega_k^V
→ add variance-critical mode
→ eta=0.8 variance-region centroid
→ frozen M1-v0 variance-aware reweight
```

---

# 19. Oracle Baselines

## 19.1 Oracle-P

选择：

\[
k_P^*
=
\arg\max P_k^{ref}.
\]

使用与 Layer A 相同 common action。

## 19.2 Oracle-V

选择：

\[
k_V^*
=
\arg\max L_k^{ref}(q_t).
\]

D1：

\[
q_t=q_0.
\]

D2 第二次 birth：

允许 offline high-N reference 在 \(q_1\) 下重新估计 \(L_k(q_1)\)，但信息不得泄漏给在线 policy。

## 19.3 Random Selection

从 eligible unrepresented candidates 中 uniform random 选择，使用相同 downstream action。

---

# 20. Seeds

每个 frozen benchmark config 使用：

```text
[2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
```

若共有 8 configs：

\[
8\times8=64
\]

个主要 policy trials / method。

所有 seed 必须保留。

---

# 21. Final Evaluation Budget

继承 M1-v0：

```text
final_eval_n = 100,000
```

所有方法按相同 simulator-call accounting 比较。

---

# 22. Primary Metrics

## 22.1 Top-1 Variance-Critical Selection Accuracy

\[
\boxed{
Acc_V@1
=
P(
\widehat k
=
k_V^*
)
}
\]

## 22.2 Captured Variance Share

若选择集合为 \(S_B\)：

\[
\boxed{
CVS_B
=
\frac{
\sum_{k\in S_B}L_k^{ref}(q_0)
}{
\sum_{j\in\mathcal M}L_j^{ref}(q_0)
}
}
\]

D1 用 \(B=1\)，D2 用 \(B=2\)。

## 22.3 Captured Probability Share

\[
CPS_B
=
\frac{
\sum_{k\in S_B}P_k^{ref}
}{
\sum_{j\in\mathcal M}P_j^{ref}
}.
\]

## 22.4 Second Moment

\[
M_2(q_{\mathrm{final}}).
\]

## 22.5 Mode-wise Leakage

报告：

\[
L_k(q_{\mathrm{final}}),
\qquad
\omega_k^V(q_{\mathrm{final}}).
\]

## 22.6 Budget-Adjusted VRF

继续使用 semantic-corrected M1-v0 定义。

---

# 23. Selection Regret

定义：

\[
\boxed{
R_{M_2}
=
\frac{
M_2(q_{\mathrm{policy}})
}{
M_2(q_{\mathrm{OracleV}})
}
-1
}
\]

以及：

\[
\boxed{
R_{CVS}
=
1-
\frac{CVS_{\mathrm{policy}}}
{CVS_{\mathrm{OracleV}}}
}
\]

---

# 24. Primary Success Gates

## Gate D0 — Validity

要求：

- benchmark frozen before adaptive runs；
- 8 eligible configs 全保留；
- H3/M1 frozen tags 无修改；
- estimator / source density 正确；
- no oracle leakage；
- pytest 全通过；
- final evaluation independent；
- all methods same declared budget。

失败即：

```text
INVALID
```

## Gate D1 — Benchmark Conflict

8/8 headline configs 必须满足：

\[
k_P^*
\ne
k_V^*.
\]

且 strong inversion eligibility 全部通过。

## Gate D2 — Selection Advantage

Layer A / D1：

Variance selector：

```text
Acc_V@1 >= 75%
```

并且至少比 Probability selector 高：

```text
25 percentage points
```

## Gate D3 — Captured Variance Advantage

要求：

\[
\operatorname{median}(CVS_1^{V})
>
\operatorname{median}(CVS_1^{P}),
\]

且：

\[
\boxed{
\operatorname{median}
\left[
\frac{CVS_1^{V}}
{CVS_1^{P}}
\right]
\ge1.25
}
\]

## Gate D4 — Selection Converts to M2 Gain

Layer A：

\[
\boxed{
\operatorname{median}
\frac{
M_2(q_{\mathrm{VarianceSelector}})
}{
M_2(q_{\mathrm{ProbabilitySelector}})
}
\le0.90
}
\]

即至少约 10% median second-moment advantage。

## Gate D5 — Near-Oracle Selection

\[
\boxed{
\operatorname{median}
\frac{
M_2(q_{\mathrm{VarianceSelector}})
}{
M_2(q_{\mathrm{OracleV}})
}
\le1.10
}
\]

## Gate D6 — Full-Policy Advantage

Layer B：

\[
\boxed{
\operatorname{median}
\frac{
M_2(q_{\mathrm{M1\ variance}})
}{
M_2(q_{\mathrm{ProbabilityFull}})
}
\le0.90
}
\]

并要求：

\[
VRF_{\mathrm{budget}}^{M1}
>
VRF_{\mathrm{budget}}^{Probability}
\]

median 成立。

---

# 25. D2 Two-Birth Analysis

D2 不作为主 headline gate，但报告：

\[
CVS_2,
\quad
M_2,
\quad
VRF_{\mathrm{budget}}.
\]

重点观察：

> probability policy 是否在第二次 birth 后追上 variance policy。

如果差距缩小，不算失败；可支持“variance ranking 在 adaptation resources 紧张时价值最大”。

---

# 26. Dynamic Re-ranking

第二次 birth 前，Variance policy 必须重新估计：

\[
L_k(q_1),
\]

而不是沿用：

\[
L_k(q_0).
\]

因为 variance importance 是 proposal-dependent。

Probability policy 的 \(P_k\) 与 proposal 无关，但为在线对称性推荐使用当前第二轮 pilot 重新估计。

---

# 27. Fairness Rules

所有 comparator 必须：

```text
same frozen benchmark
same online seed
same pilot N
same exploration alpha
same final evaluation N
same birth budget
same covariance family
same simulator
same event definition
same topology oracle
same cost accounting
```

Layer A 还必须：

```text
same component center rule
same weight update rule
```

只改变 selector。

---

# 28. Probability Estimation

禁止使用：

```text
n_k / N
```

代替 target probability。

必须使用 fixed-stratified design 的合法 \(\widehat P_k\)。

每个 mode 保存：

```text
raw_count
raw_fraction
P_hat
P_CI
L_hat
omega_V_hat
variance_mass_ESS
```

---

# 29. Variance Estimation

每个 sample \(x_i\sim r_i\)：

\[
\widetilde\omega_i^V
=
\mathbf1_A(x_i)
\frac{p(x_i)^2}
{q_t(x_i)r_i(x_i)}.
\]

mode-wise：

\[
\widehat L_k
=
\frac1N
\sum_i
\mathbf1_{A_k}(x_i)
\frac{p(x_i)^2}
{q_t(x_i)r_i(x_i)}.
\]

confidence 使用 stratified bootstrap。

---

# 30. Common Center for Layer A

定义 target-probability conditional centroid：

\[
m_k^P
=
\frac{
E_r[
\mathbf1_{A_k}(X)
\frac{p(X)}{r(X)}
X
]
}{
E_r[
\mathbf1_{A_k}(X)
\frac{p(X)}{r(X)}
]
}.
\]

实现不得读取 \(ho_V\) 或 \(L_k\)。

---

# 31. Layer B Variance Center

使用 frozen：

\[
m_{\eta=0.8,k}^{V}
\]

即 H3-corrected variance-mass HDR centroid。

不得修改。

---

# 32. Mixture Weights

Layer A 为隔离 selector，二者使用相同 frozen M1-v0 downstream weight optimizer。

Layer B probability full policy 使用：

\[
\pi_k\propto\widehat P_k
\]

合法 normalization，不得调用 variance-aware \(M_2(\pi)\) optimizer。

---

# 33. Required Ablations

## Ablation D-A — Oracle ranking

比较：

```text
Estimated probability rank
Estimated variance rank
Oracle-P
Oracle-V
Random
```

## Ablation D-B — Common center

固定 conditional probability centroid，回答 selector 本身。

## Ablation D-C — Center effect

同一 selected mode：

```text
probability centroid
vs
variance HDR centroid
```

## Ablation D-D — Weight effect

固定 selected modes + centers：

```text
probability weights
vs
variance-aware optimized weights
```

## Ablation D-E — Birth budget

```text
B_birth = 1
vs
B_birth = 2
```

---

# 34. Do Not Add Yet

M1-D 完成前不要增加：

```text
covariance adaptation
alpha re-optimization
component deletion
neural selector
learned ranking
real Sanger benchmark
```

---

# 35. Statistical Reporting

结果按：

```text
config
seed
method
birth_budget
```

记录。

报告：

- all config-seed values；
- per-config median；
- global median；
- mean；
- std；
- min/max；
- paired bootstrap CI；
- success count。

主要比较必须 paired：

```text
same config
same seed
```

---

# 36. Hierarchical Analysis

不能把所有 config-seed 点假装成完全 IID。

至少报告：

## Within-config

8 seeds。

## Across-config

8 frozen configs 的 median / paired summary。

headline gate 优先基于：

```text
per-config paired medians
```

---

# 37. Machine-Readable Result Schema

建议：

```json
{
  "schema_version": "raretopo-m1d-v0",
  "parent_tag": "RareTopo-M1-v0",
  "h3_tag": "RareTopo-H3-v1.0",
  "benchmark_freeze_hash": "...",
  "config_id": "...",
  "seed": 2026,
  "birth_budget": 1,
  "method": "variance_selector_common_action",
  "pilot": {
    "n": 20000,
    "alpha_p": 0.5
  },
  "mode_estimates": [],
  "selected_modes": [],
  "selection_metrics": {
    "top1_variance_correct": false,
    "captured_variance_share": 0.0,
    "captured_probability_share": 0.0
  },
  "evaluation": {
    "P_hat": 0.0,
    "M2_hat": 0.0,
    "VRF_proposal": 0.0,
    "VRF_budget": 0.0
  },
  "cost": {},
  "validity": {}
}
```

---

# 38. Required Outputs

```text
docs/phase_m1d/
├── M1_D_Multi_Missing_Mode_Variance_Geometry_Benchmark_Task.md
├── M1_D_Benchmark_Freeze.md
├── M1_D_Benchmark_Methodology.md
└── M1_D_Final_Report.md

configs/phase_m1d/
├── m1d_candidate_generation.json
├── m1d_d1_one_birth.json
└── m1d_d2_two_birth.json

results/phase_m1d/
├── benchmark_freeze/
├── d1_selection_only/
├── d1_full_policy/
├── d2_two_birth/
├── ablations/
└── summary/

figures/phase_m1d/
└── ...

tests/
└── M1-D tests
```

---

# 39. Required Figures

1. **Figure D1 — Probability vs Variance Ranking**
2. **Figure D2 — Ranking Conflict Heatmap**
3. **Figure D3 — Top-1 Selection Accuracy**
4. **Figure D4 — Captured Variance Share**
5. **Figure D5 — M2 by Selector**
6. **Figure D6 — Full Policy M2**
7. **Figure D7 — Selection Regret**
8. **Figure D8 — Birth-Budget Effect**

---

# 40. Tests

至少新增：

```text
test_m1d_benchmark_eligibility
test_m1d_benchmark_freeze_deterministic
test_m1d_no_oracle_leakage
test_m1d_probability_ranking
test_m1d_variance_ranking
test_m1d_common_action_identical
test_m1d_birth_budget_enforced
test_m1d_captured_variance_share
test_m1d_oracle_v_selector
test_m1d_dynamic_reranking
test_m1d_result_schema
```

---

# 41. No-Oracle-Leakage Test

online policy 不允许访问：

```text
reference_P
reference_L
oracle_rank
benchmark_freeze reference table
```

benchmark-design oracle 与 online policy 必须通过独立 data object / interface 物理隔离。

---

# 42. Run Order

严格按：

```text
M1-D0  Task freeze
  ↓
M1-D1  candidate generation
  ↓
M1-D2  offline oracle characterization
  ↓
M1-D3  freeze 8 benchmark configs
  ↓
M1-D4  unit / no-leakage tests
  ↓
M1-D5  Layer A one-birth challenge
  ↓
M1-D6  Layer B full policy
  ↓
M1-D7  two-birth challenge
  ↓
M1-D8  ablations
  ↓
M1-D9  final report / gate audit
```

---

# 43. Stop / Go Rules

## Stop after benchmark construction

如果 deterministic candidate pool 无法构造满足：

\[
k_P^*\ne k_V^*
\]

且有 ≥3 observable missing modes 的 benchmark：

```text
STOP
```

不得降低标准制造容易结论。

## Stop after Layer A

若 Gate D2 FAIL：

```text
STOP
```

不要进入 covariance extension。

## Diagnostic branch

若 D2 PASS 但 D4 FAIL：

说明“选对 mode”却没有转化为 \(M_2\) 收益。下一步应研究 proposal action mapping。

## Go

只有：

```text
D0 PASS
D1 PASS
D2 PASS
D3 PASS
D4 PASS
```

才认为 multi-mode selection thesis supported。

D5 / D6 决定结果强度。

---

# 44. Interpretation Matrix

| Variance selects oracle mode? | Captures more variance? | M2 lower? | Full policy lower? | Interpretation |
|---|---|---|---|---|
| No | — | — | — | variance estimate ranking 不稳定 |
| Yes | No | No | — | ranking signal / oracle definition 需审查 |
| Yes | Yes | No | — | selection 正确，但 action mapping 无收益 |
| Yes | Yes | Yes | No | selector 有价值，full policy 其他组件抵消 |
| Yes | Yes | Yes | Yes | strong M1-D support |

---

# 45. Strongest Allowed Claim if Successful

只有所有 headline gates 支持时，允许：

> **When several unrepresented topology modes compete for a limited adaptation budget, probability ranking and proposal-dependent variance ranking can disagree. On the preregistered multi-missing-mode RareTopo benchmarks, variance-guided selection allocates proposal components toward estimator-critical modes more effectively than probability-guided selection, yielding lower second moment under matched sampling and adaptation budgets.**

不得升级为：

> variance ranking is universally optimal.

也不得写：

> probability information is useless.

---

# 46. Negative Result Policy

以下结果必须如实接受：

## Case A

Probability selector ≈ Variance selector：

> 当前 multi-mode family 中 probability geometry 已足够。

## Case B

Variance selects oracle \(L\) mode but \(M_2\) 不更低：

> 当前 leakage ranking 不等价于最佳 proposal action。

## Case C

Oracle-V 本身不优于 Oracle-P：

> 选最大当前 leakage 不等价于选最大 adaptation gain。

不得通过换 benchmark 隐藏这些结果。

---

# 47. Potential Follow-Up if Oracle-V Is Not Optimal

若 Case C 出现，下一研究问题自然变为：

\[
\boxed{
\Delta_k
=
M_2(q_t)
-
M_2(q_t+\text{component}_k)
}
\]

即：

> 应按当前 leakage \(L_k\) 排序，还是按 marginal value of adaptation \(\Delta_k\) 排序？

但 `Delta-policy` 不属于当前 M1-D task，必须另开 preregistration。

---

# 48. Completion Checklist

## Freeze

- [ ] parent tag `RareTopo-M1-v0` recorded
- [ ] H3 tag recorded
- [ ] task committed before adaptive result
- [ ] benchmark eligibility locked
- [ ] candidate generation deterministic
- [ ] benchmark set frozen before policy runs

## Benchmark

- [ ] 8 configs
- [ ] ≥3 missing modes each
- [ ] all top-rank conflicts pass
- [ ] observability pass
- [ ] no config removed after seeing M1 result

## Implementation

- [ ] no-oracle-leakage test
- [ ] probability estimator correct
- [ ] variance estimator correct
- [ ] common action identical in Layer A
- [ ] birth budget enforced
- [ ] dynamic re-ranking implemented for D2

## Experiments

- [ ] 8 seeds/config
- [ ] D1 Layer A complete
- [ ] D1 Layer B complete
- [ ] D2 complete
- [ ] ablations complete
- [ ] failed runs retained

## Reporting

- [ ] Acc_V@1
- [ ] CVS
- [ ] CPS
- [ ] M2
- [ ] VRF_budget
- [ ] Oracle-V regret
- [ ] hierarchical summaries
- [ ] figures reproducible
- [ ] gate audit complete

---

# 49. Immediate Next Instruction

完成本 Task freeze 后，不要直接跑 adaptive benchmark。

下一步是：

\[
\boxed{
\text{M1-D1: deterministic candidate generation + offline oracle characterization}
}
\]

首先只生成：

```text
candidate pool
P_k reference
L_k(q0) reference
eligibility table
```

然后冻结：

```text
M1_D_Benchmark_Freeze.json
M1_D_Benchmark_Freeze.md
```

只有 benchmark freeze 完成后，才允许运行：

```text
Probability selector
Variance selector
M1 full policy
```

---

# 50. One-Line State

```text
H3 = frozen
M1-v0 = frozen
M1-D = preregistered benchmark extension
adaptive M1-D runs = NOT STARTED
next gate = freeze a deterministic probability-vs-variance ranking-conflict benchmark
```

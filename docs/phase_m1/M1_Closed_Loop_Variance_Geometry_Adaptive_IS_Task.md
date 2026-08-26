# M1 Closed-Loop Variance-Geometry Adaptive IS — Preregistered Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems  
> **Method Track:** M1 — Closed-Loop Variance-Geometry Adaptive Importance Sampling  
> **Document type:** Preregistered research / experiment task specification  
> **Status:** **PREREGISTERED — NOT STARTED**  
> **Prerequisite:** H3 scientific state frozen at annotated tag `RareTopo-H3-v1.0`  
> **H3 scientific source commit:** `5faef86b9d0ff35eb2cee762ec24a363796f6ce1`  
> **H3 source branch:** `feature/phase-h-uncertainty-risk`  
> **Date:** 2026-08-26  
> **Core firewall:** `H3 = q -> variance geometry`; `M1 = variance geometry -> q_next`

---

# 0. Purpose

本文档正式定义 RareTopo 在 H3 冻结后的第一条方法学研究线：

\[
\boxed{
\text{M1: Closed-Loop Variance-Geometry Adaptive IS}
}
\]

H3 已经完成的核心科学链条是：

\[
(\text{system},q)
\longrightarrow
\rho_V^{(q)}
\longrightarrow
M_2(q),\,L_k(q)
\longrightarrow
\nu_V^{(q)}
\longrightarrow
\text{variance geometry}.
\]

M1 不重复 H3，也不把 “使用 mixture proposal” 本身作为新贡献。M1 研究真正尚未完成的反馈方向：

\[
\boxed{
q_t
\longrightarrow
\widehat{\nu}_V^{(q_t)}
\longrightarrow
\text{diagnose}
\longrightarrow
\text{proposal action}
\longrightarrow
q_{t+1}
}
\]

最终目标是建立一个可以反复执行的闭环：

```text
estimate
    ↓
diagnose
    ↓
update q
    ↓
re-estimate
    ↓
repeat / hold / stop
```

本 Task 的第一原则是：

> **先证明 variance geometry 能作为 proposal adaptation 的有效控制信号，再考虑 ML、真实稀有 Sanger benchmark、大规模高维扩展。**

---

# 1. Source-of-Truth / Required References

M1 开始前必须先阅读并遵守 `RareTopo-H3-v1.0` 冻结包。H3 frozen artifact 不允许被 M1 修改。

## 1.1 H3 closeout authority

优先级最高：

```text
RareTopo-H3-v1.0/
├── FINAL_FREEZE_REPORT.md
├── FROZEN_EXPERIMENTS.md
├── H3_ARTIFACT_INDEX.tsv
├── SHA256SUMS.txt
├── TAG_MANIFEST.json
└── closeout/
    ├── H3_Claim_Ledger.md
    ├── H3_FINAL_INTERFACE.md
    ├── H3_Paper_Contribution_Map_v1.2.md
    ├── H3_Figure_Audit.md
    └── H3_State_Audit.md
```

其中：

### `closeout/H3_Claim_Ledger.md`

用于确定：

- 什么是 theorem；
- 什么只是 empirical；
- 什么已被 remove；
- M1 不允许重新升级的旧 claim。

### `closeout/H3_FINAL_INTERFACE.md`

这是 M1 的直接接口规范，优先级最高。

M1 必须继承：

\[
\rho_V^{(q)}(x)
=
\mathbf 1_A(x)\frac{p(x)^2}{q(x)},
\]

\[
M_2(q)
=
\int_A\frac{p(x)^2}{q(x)}dx,
\]

\[
L_k(q)
=
\int_{A_k}\frac{p(x)^2}{q(x)}dx,
\]

\[
\nu_V^{(q)}
=
\frac{\rho_V^{(q)}(x)\,dx}{M_2(q)},
\]

以及 H3 已冻结的 finite-sample / topology / legality interface。

---

## 1.2 H3 theory references

必须阅读：

```text
H3_Frozen/theory/
├── H3_Theory_Consolidation_Variance_Leakage.md
├── H3_Theory_Audit_Proof_Boundary_Refinement.md
└── GEOMETRY_IS_VARIANCE_THEOREM_PROOF_PACK (1).md
```

用途：

- second-moment decomposition；
- probability mass 与 variance contribution 脱钩；
- Gaussian leakage kernel；
- theorem scope；
- support / unbiasedness / integrability boundary。

---

## 1.3 H3 empirical references

必须阅读：

```text
H3_Frozen/reports/current/
├── H3_2_experiment_freeze_final.md
├── H3_2_C1_stability_audit.md
├── H3_3A_set_valued_variance_geometry.md
├── H3_3B_Final_Summary.md
└── H3_3B_Real_VRF_Audit.md
```

以及 frozen experiment packages：

```text
H3_Frozen/experiments/
├── h3_1_variance_leakage/
├── h3_2_adaptive_geometry_is/
├── h3_3a_set_valued_geometry/
├── h3_3b_synthetic_pilot/
├── h3_3b_multi_system_validation/
├── h3_3b_phase1_curvature_scan/
├── h3_3b_phase2_threshold/
├── h3_3b_phase3_joint_map/
├── h3_3b_p2r/
└── h3_3b_real_vrf_audit/
```

M1 的第一个主 benchmark 应优先复用：

```text
h3_1_variance_leakage
h3_2_adaptive_geometry_is
```

而不是先重新设计新的 benchmark。

---

# 2. Scientific Background Frozen by H3

## 2.1 Event / topology decomposition

设 failure set：

\[
A=\bigsqcup_{k=1}^{K}A_k,
\]

其中 \(A_k\) 是互斥 topology modes。

H3 已证明：

\[
\boxed{
M_2(q)=\sum_{k=1}^{K}L_k(q)
}
\]

其中：

\[
L_k(q)
=
\int_{A_k}\frac{p(x)^2}{q(x)}dx.
\]

因此：

\[
\omega_k^V(q)
=
\frac{L_k(q)}{M_2(q)}
\]

可用于描述 mode \(k\) 对 second moment 的 variance share。

---

## 2.2 H3-1 key mechanism

H3 已经明确：

\[
P_k \ll P_j
\]

不推出：

\[
L_k \ll L_j.
\]

即：

> 一个概率极小的 topology mode 可以成为 estimator variance 的主要来源。

因此 M1 的 missing-mode discovery 不能只按 topology probability \(P_k\) 排序。

---

## 2.3 H3-2 capability already completed

H3-2 已经完成：

```text
single Geometry-IS
topology-aware mixture
leakage-point mixture
synthetic adaptive recovery
```

因此 M1 的 novelty **不是**：

```text
use mixture IS
```

也不是：

```text
move proposal toward a leakage point
```

M1 必须新增：

\[
\boxed{
\text{online estimate}
\rightarrow
\text{automatic diagnosis}
\rightarrow
\text{automatic proposal update}
\rightarrow
\text{re-estimate}
}
\]

并且初始时不得向算法提供完整的 secondary-mode oracle 信息。

---

## 2.4 H3-3A / H3-3B output

H3 已经把单点 leakage geometry 升级为 proposal-dependent variance measure / region。

M1 优先使用：

```text
Tier 1: weighted empirical nu_V^(q)
Tier 2: mode-wise L_k / omega_k^V
Tier 3: C_eta / R_eta / G_eta
Tier 4: point descriptors
```

不得假设：

\[
(C_\eta,R_\eta,G_\eta)
\]

对所有系统构成充分统计量。

---

# 3. Scope of M1

## 3.1 Primary research question

\[
\boxed{
\text{Can proposal-dependent variance geometry be used to construct a
closed-loop adaptive importance sampler without prior oracle knowledge
of all variance-important topology modes?}
}
\]

更具体地：

给定当前 proposal \(q_t\)，仅通过合法 pilot samples、exact event/topology labels 和已知 densities，估计：

\[
\widehat{\nu}_V^{(q_t)},
\quad
\widehat M_2,
\quad
\widehat L_k,
\quad
\widehat\omega_k^V,
\]

然后决定是否：

```text
HOLD
ADD_COMPONENT
UPDATE_WEIGHTS
```

形成：

\[
q_{t+1}.
\]

第一版 M1 暂不开放 arbitrary covariance optimization、component deletion 或 ML policy。

---

# 4. Explicit Non-Goals

本 Task 明确 **不做**：

1. 不修改 `RareTopo-H3-v1.0` 中任何 frozen artifact；
2. 不重新证明或扩大 H3 theorem scope；
3. 不把 H3-2 mixture 重新包装成 M1 novelty；
4. 不直接训练 ML predictor；
5. 不先追求真实 Sanger rare-event performance headline；
6. 不在第一版同时自由优化：
   \[
   m_k,\Sigma_k,\pi_k,K;
   \]
7. 不声称得到 globally optimal IS；
8. 不声称得到 universal regime taxonomy；
9. 不使用旧 Real VRF 数据恢复“real variance-reduction gain”叙事；
10. 不用 final evaluation samples 反向调阈值。

---

# 5. Preregistered M1 Hypotheses

所有 hypothesis 必须在看到 M1 final evaluation 结果之前锁定。

## H-M1.1 — Variance-important missing-mode discovery

在 H3-1 leakage benchmark 中，从只覆盖 primary mode 的初始 proposal 开始，有限 pilot 应能够识别：

> probability-small but variance-important 的未覆盖 topology mode。

成功不要求准确恢复真实 \(L_k\) 的每个数值，但要求 mode ranking / trigger 足够稳定。

---

## H-M1.2 — Leakage reduction

对被识别 missing mode 添加 proposal component 后：

\[
L_{k,\mathrm{new}}
<
L_{k,\mathrm{old}}
\]

应在独立 evaluation 中稳定成立。

---

## H-M1.3 — Second-moment reduction

closed-loop proposal 更新后：

\[
M_2(q_{\mathrm{final}})
<
M_2(q_0)
\]

应稳定成立。

---

## H-M1.4 — Oracle-gap closure

在不提前提供 H3-2 M3 的完整 leakage-point oracle 信息时，M1 应能够接近或超过 hand-designed H3-2 M3 的 second-moment performance。

这里 M3 被视为：

> **strong oracle/reference baseline**

而不是要求 M1 在所有 seed 上必须严格击败 M3。

---

## H-M1.5 — No catastrophic regression on simple geometry

在 affine / half-space sanity benchmark 上，closed-loop machinery 不应因为错误 mode birth 或不稳定 reweighting 导致显著退化。

---

## H-M1.6 — Robustness

核心结论不能只依赖单 seed。

必须报告 preregistered seed set 下的：

- median；
- range；
- success count；
- bootstrap / repeated-run uncertainty。

---

# 6. M1 Mathematical State

每轮 \(t\) 的最小状态：

\[
\boxed{
\mathcal S_t
=
\left[
q_t,
\widehat{\nu}_V^{(q_t)},
\widehat M_2,
\{
\widehat L_k,\widehat\omega_k^V
\}_k,
\{
\widehat C_{\eta,k},
\widehat R_{\eta,k},
\widehat G_{\eta,k}
\}_{k,\eta},
\mathcal U_t
\right]
}
\]

其中 \(\mathcal U_t\) 保存：

```text
sample count
sampling source
sampling density
mode sample count
variance-mass ESS
bootstrap uncertainty
legality metadata
event definition version
topology partition version
```

---

# 7. Finite-Sample Variance-Measure Estimation

设 pilot sample：

\[
x_i\sim r_i.
\]

必须保留每个 sample 的实际 sampling density。

variance-mass weight：

\[
\boxed{
\widetilde\omega_i^V
=
\mathbf 1_A(x_i)
\frac{p(x_i)^2}
{q_t(x_i)r_i(x_i)}
}
\]

归一化：

\[
\widehat\omega_i^V
=
\frac{\widetilde\omega_i^V}
{\sum_j\widetilde\omega_j^V}.
\]

于是：

\[
\boxed{
\widehat{\nu}_V^{(q_t)}
=
\sum_i
\widehat\omega_i^V\delta_{x_i}
}
\]

禁止：

```text
把 raw sample count 当 variance mass
把不同 pilot source 混合后忽略 r_i
直接按 q sample density 估计 nu_V
```

---

## 7.1 Main eta convention

继承 H3 frozen regression convention：

```text
eta_main = 0.8
eta_sensitivity = [0.5, 0.8, 0.9]
```

M1 v0 不修改该设置。

---

# 8. Proposal Family

## 8.1 Initial proposal

\(q_0\) 必须直接复用 frozen H3 baseline 中的 primary single Geometry-IS proposal。

禁止根据 M1 final result 重新调 \(q_0\)。

---

## 8.2 Adaptive family

M1 v0 使用 Gaussian mixture：

\[
\boxed{
q_t(x)
=
\sum_{j=1}^{J_t}
\pi_{t,j}
\mathcal N(x;m_{t,j},\Sigma_{t,j})
}
\]

满足：

\[
\pi_{t,j}>0,
\qquad
\sum_j\pi_{t,j}=1.
\]

---

## 8.3 Covariance freeze for v0

第一版：

```text
component covariance is fixed
```

新 component 的 covariance 继承 frozen H3-2 / primary baseline 的合法 base covariance。

原因：

H3-3B 已知 covariance 是独立 variance-spread lever。第一版若同时优化 mean、covariance、weight、component number，将无法做干净机制归因。

因此 M1 v0 只开放：

```text
component birth
component mean from variance geometry
mixture-weight reallocation
```

covariance adaptation 留给后续 M1-Covariance Extension。

---

# 9. Proposal Legality Gate

在 standard-normal / Gaussian scope 内，必须记录：

```text
proposal.legality_checked
proposal.min_eig_Sigma_minus_halfI
```

并检查适用的 integrability / support 条件。

禁止：

> proposal 已经运行，所以一定合法。

任何 legality failure：

```text
=> INVALID RUN
```

不得进入 performance comparison。

---

# 10. M1-v0 Closed-Loop Algorithm

第一版算法固定为：

\[
\boxed{
\text{Discover}
+
\text{Add}
+
\text{Reweight}
}
\]

不包含 deletion 和 covariance adaptation。

---

## 10.1 Iteration skeleton

```text
Input:
    q_t

1. Draw pilot samples from declared r_t
2. Run exact event / topology oracle
3. Evaluate p, q_t, r_t
4. Estimate nu_V^(q_t)
5. Estimate M2, L_k, omega_k^V
6. Compute mode-level uncertainty diagnostics
7. Search for unrepresented variance-important mode

If no stable candidate:
    action = HOLD
    stop / continue according to stop rule

If candidate exists:
    action = ADD_COMPONENT
    center new component using mode-specific variance-region centroid
    action = UPDATE_WEIGHTS
    obtain q_(t+1)

8. Repeat pilot diagnosis using q_(t+1)
9. Stop according to preregistered rule
10. Freeze q_final
11. Evaluate q_final on completely independent samples
```

---

# 11. Missing-Mode Definition

“missing mode” 在 M1 中不是：

> pilot 中第一次看到的新字符串 label。

而是：

> 当前 proposal component set 没有针对该 topology mode 的 representation，同时该 mode 在 estimated second-moment measure 中具有不可忽略的 variance share。

每个 mode 保存：

```text
mode_id
represented_by_component: true/false
P_k_hat
L_k_hat
omega_k_V_hat
n_observed
variance_mass_ESS
CI / bootstrap metadata
```

---

# 12. Preregistered Mode-Birth Trigger

M1 v0 固定：

```text
tau_birth_main = 0.10
tau_birth_lower_confidence = 0.05
min_mode_observations = 5
eta_main = 0.8
```

候选 mode \(k\) 仅当以下条件同时满足才允许 birth：

1. `represented_by_component == false`;
2. \(\widehat\omega_k^V \ge 0.10\);
3. bootstrap 95% lower confidence bound of \(\omega_k^V\) ≥ 0.05；
4. 至少有 5 个独立 pilot observations 属于该 mode；
5. 该 mode 的 event/topology label 通过合法 partition 检查。

即：

\[
\boxed{
\text{birth}(k)
=
\mathbf 1
\left[
\widehat\omega_k^V\ge0.10
\land
LCB_{95\%}(\omega_k^V)\ge0.05
\land
n_k\ge5
\right]
}
\]

这些阈值是：

> **M1 v0 preregistered engineering choices**

不是 H3 theorem，也不能在论文中写成 universal constants。

如实际 pilot 规模导致该 gate 数值上不可用，必须在查看 final evaluation 前提交 `M1_PREREG_AMENDMENT.md`，不得事后静默改阈值。

---

# 13. New Component Center

对被 birth 的 mode \(k\)，在：

\[
\mathcal L_{\eta,k}^{(q_t)}
\]

内计算 variance-mass weighted centroid：

\[
\boxed{
m_{\eta,k}
=
\mathbb E_{\nu_V^{(q_t)}}
[
X
\mid
X\in\mathcal L_{\eta,k}^{(q_t)}
]
}
\]

有限样本使用 normalized variance-mass weights。

M1 v0 固定：

\[
\boxed{
m_{\mathrm{new}}
=
\widehat m_{\eta=0.8,k}
}
\]

这只是 M1 algorithm choice，不声称为 optimal update。

---

# 14. Mixture-Weight Theory Task

在进入完整 closed-loop benchmark 前，先完成一个独立 theory / numerical validation subtask。

设固定 component densities \(q_j(x)\)，定义：

\[
q_\pi(x)
=
\sum_{j=1}^{J}\pi_jq_j(x),
\qquad
\pi\in\Delta_J.
\]

目标：

\[
\boxed{
\min_{\pi\in\Delta_J}
M_2(\pi)
}
\]

其中：

\[
M_2(\pi)
=
\int_A
\frac{p(x)^2}
{\sum_j\pi_jq_j(x)}
dx.
\]

---

## 14.1 Candidate theorem to formally verify

在 denominator 正且积分有限的 regularity 条件下，要求正式推导并验证：

\[
\frac{\partial M_2}{\partial\pi_j}
=
-
\int_A
\frac{p(x)^2q_j(x)}
{q_\pi(x)^2}
dx,
\]

以及：

\[
\frac{\partial^2M_2}
{\partial\pi_j\partial\pi_\ell}
=
2
\int_A
\frac{
p(x)^2q_j(x)q_\ell(x)
}{
q_\pi(x)^3
}
dx.
\]

因此 Hessian 应为 positive semidefinite：

\[
v^\top\nabla^2M_2v
=
2\int_A
\frac{p(x)^2
(\sum_jv_jq_j(x))^2
}{
q_\pi(x)^3
}dx
\ge0.
\]

若 proof audit 通过，可建立：

> fixed-component mixture second moment is convex in mixture weights on the legal simplex.

注意：

该 theorem 在 M1 proof 审计完成前不得写进 frozen claim set。

---

## 14.2 Finite-sample optimization objective

若 optimization sample \(x_i\sim r\)，使用：

\[
\widehat M_2(\pi)
=
\frac1N
\sum_i
\mathbf1_A(x_i)
\frac{p(x_i)^2}
{q_\pi(x_i)r(x_i)}.
\]

实现必须：

- 使用 log-density / logsumexp；
- 保证 simplex constraints；
- 记录 solver convergence；
- 保留 minimum weight floor 仅用于数值稳定时必须显式声明。

---

# 15. Weight Update

M1 v0 每次 component birth 后：

```text
1. keep component means/covariances fixed
2. optimize pi on simplex
3. freeze pi_new
4. do not jointly retune means using the same final evaluation samples
```

允许优化器：

```text
projected gradient
SLSQP / constrained optimizer
mirror descent
```

但主实现只能选择一种并冻结。

推荐主实现：

```text
SLSQP or equivalent deterministic simplex-constrained solver
```

并用 analytic gradient + finite-difference regression test。

---

# 16. HOLD Action

M1 必须允许：

```text
action = HOLD
```

出现以下情况之一必须 HOLD：

- 没有 mode 通过 birth gate；
- variance-mass estimate ESS 太低；
- bootstrap uncertainty 过大；
- legality / topology partition 有问题；
- optimizer 未收敛；
- 新 proposal 未通过 validation。

不得强制每轮修改 proposal。

---

# 17. Stop Rule

M1 v0 固定最大：

```text
max_adaptation_iterations = 3
```

满足任一条件即停止：

1. 当前没有 missing mode 通过 birth gate；
2. 所有已观察 variance-important modes 都已 represented；
3. 连续一轮 proposal update 后，独立 diagnostic pilot 上：
   \[
   \frac{\widehat M_2(q_t)-\widehat M_2(q_{t+1})}
   {\widehat M_2(q_t)}
   <0.02;
   \]
4. 达到 3 次 adaptation；
5. validity / legality gate failure。

第 3 条是停止更新的 engineering threshold，不是成功判据。

---

# 18. Data-Splitting / Adaptation Bias Firewall

这是强制要求。

每个 seed 的 sample roles 必须分离：

```text
adaptation pilot
optimization / weight-fit sample
final evaluation sample
```

final evaluation sample 必须在 `q_final` 完全冻结之后生成。

禁止：

```text
看 final evaluation
→ 调 birth threshold
→ 重跑同一 final seed
```

若需要修改 preregistered hyperparameter：

```text
先写 amendment
再生成新的 final evaluation
```

---

# 19. Preregistered Synthetic Budget

M1 v0 首先只做 synthetic / controlled benchmark。

主预算：

```text
pilot_per_iteration = 20,000 simulator calls
weight_fit_samples   = included in pilot unless a separate declared split is used
max_iterations       = 3
final_eval_samples   = 100,000
```

因此每个 adaptive method / seed 最大 nominal call budget：

```text
<= 160,000 simulator calls
```

实际少于 max iteration 时必须记录真实调用数。

Preregistered seed set：

```text
[2026, 2027, 2028, 2029, 2030, 2031, 2032, 2033]
```

共 8 个 seeds。

若 debug 阶段使用其他 seed：

> debug run 不进入 final statistics。

---

# 20. Benchmark Ladder

严格按 gate 顺序运行。

---

## Benchmark A — Affine / Half-Space Sanity

目的：

- 验证 unbiasedness；
- 验证 \(M_2\) estimator；
- 验证 mixture-weight optimizer；
- 验证 closed-loop 在没有 missing mode 时能 HOLD；
- 防止 adaptation machinery 在简单情形下自发制造错误 component。

该 benchmark 不用于 headline performance claim。

---

## Benchmark B — H3-1 Variance-Leakage Benchmark

这是 M1 第一主战场。

必须复用 frozen H3-1 benchmark definition / script semantics，不改变 event 定义来帮助新算法。

核心测试：

> primary mode proposal 是否能通过 pilot 自动发现 probability-small but variance-dominant secondary topology mode。

这里不向算法输入 H3-1 frozen result 中的真实 leakage fraction 或 secondary mode location。

那些 frozen data 只能用于：

```text
post-run validation / ground-truth comparison
```

不能作为 online algorithm oracle。

---

## Benchmark C — H3-2 / Curved Multi-Mode Controlled Cases

只有 Benchmark B 通过后才启动。

目标：

- 对比现有 H3-2 M2 / M3；
- 检查 set-valued geometry；
- 检查 closed-loop 是否不仅在单一 crafted leakage case 成立。

---

## Benchmark D — H3-3B Broader Synthetic Geometry

只有 A/B/C 通过后才进入：

- curvature family；
- proposal-dependent variance geometry；
- multi-mode / regime cases。

这里仍然不做真实性能 headline。

---

# 21. Baselines

必须至少报告：

1. **Crude Monte Carlo**
2. **Single Geometry-IS / \(q_0\)**
3. **H3-2 M2 topology-aware mixture**
4. **H3-2 M3 leakage-point mixture**
5. **Fixed variance-aware mixture**
   - component set 已给定；
   - 只优化 mixture weights；
6. **M1 closed-loop Discover + Add + Reweight**
7. **Cross-Entropy Method (CEM)**，在公平 call budget 下实现

可选后续 baseline：

```text
classical adaptive mixture IS
subset simulation
```

但不能延迟主实验只为了无限添加 baseline。

---

# 22. Oracle Levels Must Be Labeled

每个 baseline 必须标注 oracle level：

| Method | Secondary mode known in advance? | Leakage geometry known? | Online adaptation? |
|---|---:|---:|---:|
| MC | No | No | No |
| Single Geometry-IS | No | No | No |
| H3-2 M2 | Yes / topology-informed | No | No |
| H3-2 M3 | Yes | Yes / hand-designed | No |
| Fixed variance-aware mixture | Yes | geometry fixed | Weight only |
| **M1 closed-loop** | **No** | **No** | **Yes** |
| CEM | No | No | Yes |

这张 oracle table 必须进入最终 report。

---

# 23. Primary Metrics

## 23.1 Second moment

主优化指标：

\[
\boxed{
M_2(q)
}
\]

而不是只看 VRF。

---

## 23.2 Estimator variance

\[
\operatorname{Var}_q[\widehat P_N]
=
\frac{M_2(q)-P(A)^2}{N}.
\]

---

## 23.3 Mode-wise leakage

报告：

\[
L_k(q),
\qquad
\omega_k^V(q).
\]

特别记录：

```text
missed-mode L_k
missed-mode omega_k^V
```

在 adaptation 前后的变化。

---

## 23.4 Probability consistency

报告：

\[
\widehat P
\]

及其 uncertainty。

任何 proposal 改进不能靠产生 biased estimator 达成。

---

## 23.5 Geometry diagnostics

保留：

```text
C_eta
R_eta
G_eta
full weighted empirical nu_V
```

但 geometry improvement 不能替代 estimator performance gate。

---

## 23.6 Compute / simulator cost

必须记录：

```text
pilot calls
adaptation calls
final evaluation calls
total simulator calls
wall time
optimizer time
```

---

# 24. Budget-Adjusted Efficiency

因为 M1 需要 pilot，不能把 adaptation cost 隐藏掉。

在固定总调用预算 \(B\) 下，定义：

\[
N_{\mathrm{eval}}
=
B-N_{\mathrm{adapt}}.
\]

预算调整后方法 variance：

\[
V_{\mathrm{budget}}
=
\frac{
M_2(q_{\mathrm{final}})-P(A)^2
}{
N_{\mathrm{eval}}
}.
\]

相对 MC：

\[
\boxed{
VRF_{\mathrm{budget}}
=
\frac{
(P(A)-P(A)^2)/B
}{
[M_2(q_{\mathrm{final}})-P(A)^2]/N_{\mathrm{eval}}
}
}
\]

同时报告传统、不计 adaptation overhead 的 proposal-level VRF，二者不得混写。

---

# 25. Success / Failure Gates

采用分层 verdict，而不是只靠单个 VRF 数字。

---

## Gate 0 — Validity Gate

所有主结果必须满足：

- event definition 正确；
- topology partition 合法；
- support / density evaluation 正确；
- proposal legality 通过；
- estimator implementation 无 bias bug；
- pilot source density \(r_i\) 正确保存；
- final evaluation 独立于 adaptation；
- all required tests pass。

失败：

```text
INVALID RUN
```

不进入科学结论。

---

## Gate 1 — Discovery Gate

Benchmark B：

在 8 个 preregistered seeds 中：

```text
>= 7 / 8
```

必须成功识别 frozen ground truth 中的 variance-important missing topology mode。

定义“识别成功”：

- 正确 mode 通过 birth gate；
- 在错误 mode 上不得出现同等频率的 false birth。

若 `< 6/8`：

```text
M1 missing-mode mechanism FAIL
```

`6/8`：

```text
BORDERLINE
```

`>=7/8`：

```text
PASS
```

---

## Gate 2 — Leakage Gate

独立 final evaluation 中：

要求至少：

```text
>= 7 / 8 seeds
```

满足：

\[
L_{k,\mathrm{final}}
<
L_{k,0}.
\]

并且 median：

\[
\boxed{
\frac{L_{k,\mathrm{final}}}
{L_{k,0}}
\le0.5
}
\]

即 target missed-mode second-moment contribution 中位数至少下降 50%。

---

## Gate 3 — Global Second-Moment Gate

Benchmark B 中：

\[
M_2(q_{\mathrm{final}})
<
M_2(q_0)
\]

至少 `7/8` seeds 成立。

同时要求 median：

\[
\boxed{
\frac{M_2(q_{\mathrm{final}})}
{M_2(q_0)}
\le0.5
}
\]

如果只能降低 mode leakage，却不能降低总 \(M_2\)，不得称为 algorithmic success。

---

## Gate 4 — H3-2 Reference Competitiveness

M3 是 strong oracle baseline。

定义：

### Competitive Pass

\[
\operatorname{median}
\left[
\frac{M_2(\text{M1})}
{M_2(\text{H3-2 M3})}
\right]
\le1.10.
\]

解释：

> M1 在没有提前获得完整 leakage-point oracle 的情况下，second moment 达到 M3 的 10% 范围内。

### Strong Pass

\[
\operatorname{median}
\left[
M_2(\text{M1})
\right]
<
\operatorname{median}
\left[
M_2(\text{M3})
\right].
\]

### Failure

如果：

\[
M_2(\text{M1})
\]

持续显著差于 M2/M3，且优势只能来自更多 simulator calls，则不能进入方法论文主 claim。

---

## Gate 5 — Budget-Adjusted Gate

至少要求：

```text
median VRF_budget > 1
```

并报告 8-seed success count。

如果 proposal-level \(M_2\) 很好但计入 pilot 后：

\[
VRF_{\mathrm{budget}}\le1,
\]

结论必须写成：

> geometry adaptation works mechanistically but is not yet cost-effective.

不得隐藏该结果。

---

# 26. Statistical Reporting

每个主 metric 必须至少报告：

```text
8 individual seed values
median
mean
standard deviation
min / max
bootstrap 95% CI for median or paired difference
```

优先使用 paired comparison：

```text
same benchmark
same seed index
same final evaluation budget
```

若使用 common random numbers，必须在 report 中声明。

不允许只展示最好的 seed。

---

# 27. Required Ablations

在主方法通过 Benchmark B 后运行。

## Ablation A — No variance geometry

只按 topology probability \(P_k\) 做 mode birth / weighting。

回答：

> probability signal 是否足以替代 variance signal？

---

## Ablation B — Add without reweight

```text
Discover + Add
```

但 mixture weights 固定。

回答：

> improvement 来自 component coverage 还是 variance-aware weight optimization？

---

## Ablation C — Reweight without birth

component set 固定，只更新 \(\pi\)。

回答：

> 权重优化能否解决真正 missing mode？

---

## Ablation D — Point vs set-valued center

比较：

```text
leakage point / max-weight point
vs
m_eta variance-region centroid
```

回答：

> H3-3A set-valued geometry 是否真正改善 closed-loop stability？

---

## Ablation E — eta sensitivity

只使用 frozen：

```text
eta = [0.5, 0.8, 0.9]
```

主结论以 0.8 为准。

---

# 28. Explicitly Deferred Ablations

以下不进入 M1-v0 main experiment：

```text
free covariance optimization
component deletion
ML policy
neural proposal
high-dimensional benchmark
real rare-Sanger optimization
```

这些只有在 v0 core gate 通过后才能单独 preregister。

---

# 29. Unit / Regression Test Requirements

在 scientific run 前必须实现并通过测试。

## 29.1 Density / mixture

- mixture weights sum to one；
- all weights non-negative；
- logsumexp implementation stable；
- `q(x)>0` on required support；
- component ordering does not change density。

## 29.2 Variance mass

对 crafted toy case：

- MC source \(r=p\) 时 weight formula 正确；
- proposal source \(r=q\) 时 \(w^2\) formula 正确；
- mixed pilot sources 的 \(\rho_V/r_i\) pooling 正确。

## 29.3 Mode decomposition

数值验证：

\[
\widehat M_2
\approx
\sum_k\widehat L_k.
\]

## 29.4 Mixture-weight objective

在低维 toy model：

- analytic gradient vs finite difference；
- Hessian PSD numerical check；
- optimizer result independent of initialization within tolerance；
- simplex constraints maintained。

## 29.5 HOLD behavior

无 missing mode 的 half-space case 必须 HOLD。

## 29.6 Birth behavior

crafted 2-mode case：

- secondary variance-dominant mode 能触发；
- low-variance nuisance mode 不应触发。

## 29.7 Freeze protection

测试 / script 不允许写入：

```text
RareTopo-H3-v1.0/
H3_Frozen/
```

---

# 30. Implementation Layout

推荐在 repository 中新增独立 M1 namespace：

```text
docs/phase_m1/
    M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md
    M1_Theory_Mixture_Weight_Convexity.md
    M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Report.md

configs/
    m1_closed_loop_v0.json

scripts/
    run_m1_weight_theory_check.py
    run_m1_halfspace_sanity.py
    run_m1_closed_loop_leakage.py
    run_m1_ablations.py

src/
    ... existing package ...
    m1/
        variance_measure.py
        mode_discovery.py
        mixture_weights.py
        proposal_update.py
        closed_loop.py

tests/
    test_m1_variance_measure.py
    test_m1_mixture_weights.py
    test_m1_mode_discovery.py
    test_m1_closed_loop.py

results/
    phase_m1/
        ...
```

若现有 repo package layout 不适合 `src/m1/`，允许按项目现有 module convention 放置，但不要破坏 H3 frozen paths。

---

# 31. Machine-Readable Result Schema

每个 seed / method 至少保存：

```json
{
  "schema_version": "raretopo-m1-v0",
  "method": "closed_loop_variance_geometry_is",
  "benchmark": "string",
  "seed": 2026,
  "h3_frozen_tag": "RareTopo-H3-v1.0",
  "initial_proposal": {},
  "iterations": [
    {
      "iteration": 0,
      "pilot_n": 20000,
      "M2_hat": null,
      "mode_stats": [],
      "geometry": {},
      "action": "HOLD|ADD_COMPONENT|UPDATE_WEIGHTS",
      "proposal_before": {},
      "proposal_after": {},
      "validity": {}
    }
  ],
  "final_proposal": {},
  "evaluation": {
    "n": 100000,
    "P_hat": null,
    "M2_hat": null,
    "variance_hat": null,
    "VRF": null,
    "VRF_budget": null,
    "mode_L": {},
    "mode_omega_V": {}
  },
  "cost": {
    "pilot_calls": 0,
    "evaluation_calls": 0,
    "total_calls": 0,
    "wall_time_s": null
  },
  "gates": {}
}
```

---

# 32. Required Figures

第一版 report 至少生成：

## Figure M1-1 — Closed-loop schematic

```text
q_t
→ pilot
→ nu_V
→ missing-mode diagnosis
→ add / reweight
→ q_(t+1)
```

---

## Figure M1-2 — Mode probability vs variance share

展示 H3-1 target benchmark 中：

\[
P_k
\quad\text{vs}\quad
\omega_k^V.
\]

同时显示 closed-loop 识别的 mode。

---

## Figure M1-3 — Adaptation trajectory

横轴 iteration：

```text
t = 0,1,2,3
```

纵轴至少：

- \(M_2\)；
- target \(L_k\)；
- \(\omega_k^V\)。

---

## Figure M1-4 — Baseline second-moment comparison

比较：

```text
MC
Single
H3-2 M2
H3-2 M3
Fixed variance-aware
M1 closed-loop
CEM
```

---

## Figure M1-5 — Oracle gap

展示：

\[
M_2(\text{M1})/M_2(\text{M3})
\]

跨 8 seeds。

---

## Figure M1-6 — Cost-adjusted efficiency

展示：

```text
proposal-level VRF
vs
budget-adjusted VRF
```

避免隐藏 pilot overhead。

---

# 33. Run Order / Stop-Go Decisions

严格按顺序：

```text
M1-0  Task freeze
  ↓
M1-1  mixture-weight proof + unit tests
  ↓
M1-2  half-space sanity
  ↓
M1-3  H3-1 missing-mode discovery
  ↓
M1-4  closed-loop Benchmark B
  ↓
M1-5  H3-2 / curved benchmark
  ↓
M1-6  ablations + robustness
  ↓
M1-7  decide next extension
```

---

## Stop condition after M1-3

若 Discovery Gate FAIL：

```text
STOP
```

优先研究 finite-sample diagnosis，不允许直接靠加入 oracle mode 修补。

---

## Stop condition after M1-4

若：

```text
Discovery PASS
but
Leakage / M2 Gate FAIL
```

说明：

> diagnosis 成立，但 proposal action mapping 失败。

下一步研究 action design，不进入 ML。

---

## Go condition after M1-4

只有：

```text
Discovery Gate PASS
Leakage Gate PASS
M2 Gate PASS
```

才进入 Benchmark C / D。

---

# 34. Interpretation Matrix

最终结果按以下逻辑解释：

| Discovery | Leakage | M2 | Cost | Interpretation |
|---|---|---|---|---|
| Fail | — | — | — | variance geometry 尚不能稳定驱动 mode discovery |
| Pass | Fail | Fail | — | diagnosis 有效，action design 无效 |
| Pass | Pass | Fail | — |局部 leakage 被修复，但 variance 被转移到其他 region/mode |
| Pass | Pass | Pass | Fail |机制成立，但 adaptation overhead 暂不经济 |
| Pass | Pass | Pass | Pass |核心 M1 方法链成立 |
| Pass | Pass | Pass | Pass + beats M3 | strong method result |

这个表必须进入最终 report，避免只挑一个漂亮指标。

---

# 35. Real-System Policy

M1-v0 不以当前 Sanger C1/C2 做 performance headline。

H3 frozen authority 已明确：

> 当前 real experiments 只支持 geometry-response validation，不能支持 rare-event variance-reduction gain。

因此：

```text
M1 synthetic core gate first
```

只有核心方法通过后，才单独 preregister：

```text
M1-Real-Rare
```

要求：

- genuinely rarer event；
- correct nominal topology；
- clean provenance；
- sufficiently large N；
- preferably multi-mode；
- no seed/config cherry-picking。

---

# 36. ML Policy

在 M1 closed-loop core gate 通过前：

```text
ML-H4 / learned proposal policy = NOT STARTED
```

后续 ML 若启动，推荐学习：

\[
(\text{system features},q)
\rightarrow
\text{variance-geometry representation}
\]

或：

\[
(\text{system},q)
\rightarrow
\widehat\nu_V^{(q)},
\]

而不是直接：

```text
features -> VRF
```

但这不属于当前 Task。

---

# 37. Preregistration Lock

以下内容从本 Task freeze 后不得依据 final outcome 静默修改：

```text
primary research question
q0 definition
eta_main
birth thresholds
min_mode_observations
max adaptation iterations
pilot sample count
final evaluation sample count
seed list
baseline list
primary metrics
Gate definitions
oracle labeling policy
data splitting policy
```

确需修改时必须创建：

```text
docs/phase_m1/M1_PREREG_AMENDMENT_<date>.md
```

至少记录：

```text
old value
new value
reason
whether final outcomes had been inspected
expected impact
```

若已看 final result 后才修改：

> 新配置必须使用新的 untouched evaluation seeds / data，不能覆盖原 prereg result。

---

# 38. Deliverables

M1-v0 完成时至少产生：

```text
docs/phase_m1/
├── M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md
├── M1_Theory_Mixture_Weight_Convexity.md
└── M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Report.md

configs/
└── m1_closed_loop_v0.json

results/phase_m1/
├── m1_halfspace_sanity_v0.json
├── m1_closed_loop_leakage_v0.json
├── m1_baseline_comparison_v0.json
├── m1_ablation_v0.json
└── m1_summary_v0.json

figures/phase_m1/
└── M1 figures

tests/
└── M1 regression tests
```

所有结果文件必须包含：

```text
git commit
H3 frozen tag
config hash
seed
timestamp
event definition
proposal metadata
sampling source
simulator-call count
```

---

# 39. Completion Checklist

## Preregistration

- [ ] Task committed before final M1 runs
- [ ] H3 frozen tag recorded
- [ ] q0 locked
- [ ] seed list locked
- [ ] thresholds locked
- [ ] budget locked
- [ ] baseline list locked
- [ ] gates locked

## Theory / implementation

- [ ] mixture-weight convexity proof audited
- [ ] analytic gradient implemented
- [ ] finite-difference gradient test passes
- [ ] mixture density stable
- [ ] variance-mass estimator tests pass
- [ ] HOLD action test passes
- [ ] mode birth test passes
- [ ] no H3 frozen file modified

## Benchmark A

- [ ] unbiasedness sanity pass
- [ ] M2 sanity pass
- [ ] no false mode birth
- [ ] optimizer pass

## Benchmark B

- [ ] 8 prereg seeds complete
- [ ] Discovery Gate evaluated
- [ ] Leakage Gate evaluated
- [ ] M2 Gate evaluated
- [ ] oracle-gap comparison complete
- [ ] cost-adjusted gate complete

## Reporting

- [ ] all seeds retained
- [ ] failed runs retained with reason
- [ ] no cherry-picking
- [ ] all figures reproducible
- [ ] machine-readable summary generated
- [ ] interpretation matrix filled

---

# 40. Final Scientific Firewall

M1 开始后必须始终保持：

```text
H3 FROZEN FACT:
q changes variance geometry.

M1 RESEARCH QUESTION:
Can estimated variance geometry be used to improve q in a closed loop?

NOT YET A FACT:
variance geometry always yields an optimal adaptive proposal.
```

M1 若成功，允许形成的最强候选结论是：

> **In the preregistered controlled RareTopo benchmarks, a closed-loop sampler that estimates proposal-dependent variance geometry, discovers variance-important missing topology modes, and adapts a Gaussian-mixture proposal can reduce estimator second moment without requiring prior oracle knowledge of all variance-dominant modes.**

只有 Benchmark / robustness / cost gates 真正支持时才能使用这句话。

不得自动升级为：

> universal optimal adaptive IS for hybrid systems.

---

# 41. Immediate Execution Instruction

完成本 Task freeze 后，下一步只做：

```text
M1-1:
Mixture-weight convexity proof
+
finite-sample objective
+
analytic gradient
+
unit tests
```

不要直接开始大规模 M1 benchmark。

M1-1 通过后执行：

```text
M1-2:
Affine / Half-Space Sanity
```

之后才进入：

```text
M1-3:
H3-1 variance-important missing-mode discovery
```

---

# 42. One-Line Project State After This Task

```text
RareTopo-H3-v1.0 = scientifically frozen
M1 = preregistered
M1 experiments = not started
next gate = mixture-weight theory + implementation sanity
```

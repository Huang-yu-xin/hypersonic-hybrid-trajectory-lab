# H3-1 — Variance Leakage Driven Geometry-IS Validation

> 项目：RareTopo — Rare Topology Transition Estimation in Hybrid Dynamical
> Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab`
> 分支：`feature/phase-h-uncertainty-risk`
> 上游：H2R ACCEPTED（`7895712c`）· ML-B1 COMPLETE（`78ecfb8`）·
> H3-0 COMPLETE / FROZEN（`127ce0c`）
> 状态：**H3-1 COMPLETE / READY FOR REVIEW**（2026-08-20）
> 执行 brief：`H3-1_Variance_Leakage_Driven_Geometry_IS_Validation_Task.md`
> dataset：`tests/data/h3_variance_leakage_dataset_v1.json`
> （`schema_version = h3-variance-leakage-dataset-v1`，确定性可复现）
> 代码：`src/hyptraj/uncertainty/variance_leakage.py` ·
> `scripts/run_h3_variance_leakage.py`
> 测试：`tests/test_h3_variance_leakage.py`
> figures：`results/phase_h3/fig1_* .. fig4_*`（gitignored 输出）

---

## 0. Scientific objective

回答 H3 的核心问题：

$$
\boxed{\;\text{When does hybrid topology geometry preserve Geometry-IS variance reduction?}\;}
$$

前序原型实验发现：**Geometry-IS 的失效不由 local geometry error 主导**，
主导失效机制是

$$
\boxed{\;\text{Variance Leakage from uncovered topology modes}\;}
$$

即：hybrid topology 系统的 VRF 不仅由 `ε_geo` 决定，还（甚至主要）由
**proposal 对 rare topology modes 的覆盖**决定。

H3-1 因此从 "generate topology transition dataset" 重新设计为：

> Construct a variance leakage benchmark and quantify why Geometry-IS
> fails or succeeds in hybrid topology systems.

关键量（mode k 的二阶矩贡献）：

$$
\mathrm{leak}_k = \int_{A_k} \frac{\varphi(x)^2}{q(x)}\,\mathrm dx,
\qquad
A_k = \{Z = k\},\quad A = \bigcup_k A_k,
$$

其中 `φ` 为目标密度（whitened 标准高斯）、`q` 为 Geometry-IS proposal、
`A_k` 为 topology mode k 的事件区域。

## 1. Scope boundary

### Implement in H3-1

- topology mode decomposition（`A = ∪_k A_k`，`P(N0→N1)`, `P(N0→N2)`, …）
- variance leakage metric（`leak_k`、`leak_fraction_k`）
- coverage analysis（`Q(A_k)/Φ(A_k)`）
- Geometry-IS baseline evaluation（单 design-point，非优化）

### Do NOT implement（属于 H3-2+）

- ❌ adaptive mixture proposal
- ❌ CEM
- ❌ Flow model
- ❌ residual learning
- ❌ second-order covariance adaptation

## 2. Variance leakage 定义与估计

### 2.1 为什么 leakage 决定 IS variance

IS estimator `Î = (1/N) Σ_i w_i 1_A(u_i)`，`w = φ/q`，其方差：

$$
\operatorname{var}(\hat I) = \frac{1}{N}\left[\int_A \frac{\varphi^2}{q}\,\mathrm du - P(A)^2\right]
= \frac{1}{N}\left[\sum_k \mathrm{leak}_k - P(A)^2\right].
$$

因此 **IS 方差的驱动量正是总 leakage `Σ_k leak_k`**。一个 mode 即使
`P_k` 很小，若 proposal 未覆盖（`w` 在其中巨大），其 `leak_k` 仍可主导
方差 —— 这就是 variance leakage。

### 2.2 估计（proposal samples）

$$
\widehat{\mathrm{leak}}_k = \frac{1}{N}\sum_{i:\,u_i\in A_k} w_i^2,
\qquad
\mathrm{leak\_fraction}_k = \frac{\mathrm{leak}_k}{\sum_j \mathrm{leak}_j}.
$$

### 2.3 Coverage

$$
\mathrm{coverage\_score}_k = \frac{Q(A_k)}{\Phi(A_k)}
= \frac{\hat P_k^{q}}{\hat P_k},
$$

`> 1`：proposal 相对 target 过度覆盖该 mode（variance 友好）；
`< 1`：欠覆盖（leak 来源）。

## 3. Topology mode decomposition（Task 2）

对每个 rare topology event，不再只记录 `Z ≠ Z_0`，而是分解：

$$
A = \bigcup_k A_k,\qquad A_k = \{Z = k\},
$$

每个 mode 保存：

```text
nominal topology      Z_0 = T(x̄_0)
transition topology   k
transition channel    atmosphere_exit (Sanger atm-exit family)
mode index            k
```

输出 topology probability distribution：

```text
P(N0->N1), P(N0->N2), P(N0->N3), ...
```

（MC pass 边际估计 `P_k = P(Z = k)`，附条件概率 `P(Z=k | Z≠Z0)`。）

## 4. Geometry-IS baseline（Task 3）

单 design-point Geometry-IS：

$$
q(u) = \mathcal N(u^{*},\, I),\qquad u^{*} = -\beta\,\alpha,
$$

- `α`：frozen ML-B1 whitened design direction（`u_star`）；
- `β`：local reliability parameter（`β_local`，ML-B1 frozen）。

在标准化设计空间 `z ~ N(0, I)`（`δx = S_A (α_p z)`）中实现：

$$
z^{*} = -\beta_{\rm eff}\,\alpha,\qquad
\beta_{\rm eff} = \frac{\beta_{\rm local}}{\alpha_p},
$$

记录：`sample count`、`accepted rare events`、`estimated probability`、
`sample variance`、`ESS`、`VRF`。

> H3-1 不是优化 proposal —— 只建立 baseline。每个 config 固定一个
> design point（nominal mode 的几何 design point）。

## 5. Experiment levels（Task 6）

| Level | configs | 目标 |
|---|---|---|
| **L0** Smooth synthetic | `L0_smooth_synthetic`（解析 half-space，d=4，β=2） | 验证 `leak ≈ 0`（相对）、theorem 成立（VRF 高） |
| **L1** Single hybrid transition | `L1_B0_N_side`（α_p = 2\|β\|） | single topology mode（N0↔N1） |
| **L2** Multi-topology hybrid | `L2_synthetic_multi_mode`（双 mode 解析，机制演示）· `L2_B1_N1_side`（3\|β\|）· `L2_B2_N_side`（4\|β\|） | 主要实验：观察 secondary modes leakage |
| **L3** Grazing dominated | `L3_B2_N1_side`（2\|β\|） | geometry failure vs coverage failure |

方法：

- 每 config：MC pass 与 IS pass 各 256 samples（128 antithetic pairs）；
- 真实 configs：`run_exact_topology`（frozen REF-0.1，max_time=3000）；
- config 级 `ε_geo`：16 samples 的 nominal-branch margin batch
  （`|b(x) − ĝ(x)|` 的中位数）；
- 全部确定性（seed 2026）。

## 6. Results

### 6.1 Config summary

| config | level | P_mc | P_is | VRF | ESS | ε_geo (med) | total leak | modes |
|---|---|---|---|---|---|---|---|---|
| `L0_smooth_synthetic` | L0 | 0.0391 | 0.0216 | **31.9** | 18.8 | 0 | 1.64e-3 | S1 |
| `L1_B0_N_side` | L1 | 0.3203 | 0.3007 | 2.05 | 188.9 | 5.6e-7 | 1.97e-1 | N1 |
| `L2_synthetic_multi_mode` | L2 | 0.0711 | 0.0718 | **0.54** | 21440 | 0 | 1.23 | S1, S2 |
| `L2_B1_N1_side` | L2 | 0.3555 | 0.3693 | 1.55 | 227.3 | 1.6e-6 | 2.84e-1 | N1 |
| `L2_B2_N_side` | L2 | 0.4219 | 0.4136 | 1.39 | 245.2 | 9.9e-6 | 3.47e-1 | N3 |
| `L3_B2_N1_side` | L3 | 0.2969 | 0.3054 | 1.98 | 201.5 | 5.2e-7 | 1.99e-1 | N2 |

P_mc / P_is 一致性良好（|P_is − P_mc| ≤ 0.02；L0 的 MC 仅 256 samples，
标准误 ~0.009）。全部 6 configs 的 IS 与 MC 事件概率互相印证。

### 6.2 Mode-level leakage（Task 4）

| config | mode | P_k | cond P | leak_k | leak_fraction | coverage | β_k |
|---|---|---|---|---|---|---|---|
| L0 | S1 | 0.0391 | 1.000 | 1.64e-3 | 1.000 | 12.8 | 2.37 |
| L1 | N1 | 0.3203 | 1.000 | 1.97e-1 | 1.000 | 1.55 | 1.17 |
| L2-synth | S1 | 0.0653 | 0.919 | 1.28e-2 | 0.010 | 7.66 | 1.94 |
| L2-synth | **S2** | **0.00575** | 0.081 | **1.22** | **0.990** | **≈0.00** | −2.85 |
| L2-B1N1 | N1 | 0.3555 | 1.000 | 2.84e-1 | 1.000 | 1.41 | −1.01 |
| L2-B2N | N3 | 0.4219 | 1.000 | 3.47e-1 | 1.000 | 1.19 | 0.86 |
| L3 | N2 | 0.2969 | 1.000 | 1.99e-1 | 1.000 | 1.68 | −1.17 |

**Task 4 核心发现（L2 synthetic multi-mode）**：

$$
P_{S2} = 0.00575 \;\ll\; P_{S1} = 0.0653\quad(\times 11),
\qquad
\mathrm{leak}_{S2} = 1.22 \;\gg\; \mathrm{leak}_{S1} = 0.0128\quad(\times 95).
$$

rare probability small, **variance contribution dominant** —— 机制直接成立。
S2 的 `leak_fraction = 0.99`：IS 方差的 99% 来自一个概率仅 0.6% 的
未覆盖 mode，导致 **VRF = 0.54 < 1**（IS 比 MC 更差）。

**Silent leakage 实证**：S2 解析真值 `leak = 1.505`（quadrature），IS
估计 `1.221`（仅 5 个 proposal samples 落入 A2 / 200000）——估计偏低
19% 且完全依赖极少数大权重样本；N 减小将彻底测不到（n_events → 0）。
S1（100000 samples）估计与解析一致（1.2835e-2 vs 1.2807e-2）。
**ESS 掩盖问题**：该 config ESS = 21440（看似健康），但 VRF = 0.54
——全样本 ESS 被被覆盖的 A1 主导，对 secondary-mode leakage 不敏感。

真实系统 configs（L1/L2/L3）在 v1 alpha 选择下 transition 全部落在最近
相邻边界（单 mode），proposal 覆盖充分（coverage 1.2–1.7），
VRF = 1.4–2.1（事件概率 ~0.3–0.4，IS 增益有限但为正）。

### 6.3 Correlation（Task 5）

| 指标 | Pearson | Spearman |
|---|---|---|
| `corr(ε_geo, VRF)` | −0.267 | −0.232 |
| `corr(leak, VRF)` | **−0.459** | **−1.000** |

**结论**：variance degradation 与 `leak`（总 leakage）的相关性在
Pearson（|−0.459| > |−0.267|）与 Spearman（−1.0 完美单调 vs −0.232）
两种度量下都显著强于与 `ε_geo` 的相关性。

> 6 个 configs 的样本量小（Pearson 对极端点敏感，如 L2-synth 的
> VRF = 0.54）；Spearman（单调序）更稳健，其差距（−1.0 vs −0.23）
> 是本实验最清晰的定量证据。

## 7. Failure mechanism analysis

基于 §6 数据，Geometry-IS 在 hybrid topology 系统中的失效机制：

1. **Primary mode（proposal 设计对准）**：coverage 1.2–12.8，`w ~ O(1)`，
   leak 小 → VRF 正常或高（L0 VRF=31.9；真实单 mode configs 1.4–2.1）；
2. **Secondary mode（未覆盖）**：coverage ≈ 0，`w` 在远区巨大 →
   `leak_k` 主导 IS 方差（fraction 0.99），VRF 崩塌至 **0.54**；
3. **`ε_geo` 不是主导**：几何非线性（ε_geo 跨 0 到 9.9e-6）与 VRF 的
   相关性弱（Pearson −0.27），而 leakage 强（−0.46 / Spearman −1.0）；
   这证实了原型实验的发现：**Geometry-IS 失效主要由 uncovered topology
   modes 的 variance leakage 解释，而非 local geometry error**；
4. **ESS 局限性**：全样本 ESS 对 secondary-mode leakage 不敏感
   （L2-synth ESS=21440 而 VRF=0.54），不能作为 coverage 健康度指标；
5. **真实系统观察**：v1 alpha（2–4|β|）下 Sanger anchors 的 transition
   均为最近相邻 mode；多 mode 竞争机制由 synthetic multi-mode 精确
   演示。真实系统 multi-mode（同时 N→N+1 与 N→N−1 或更远）的观测
   需要 adaptive proposal（H3-2）或更大 alpha 扫描（H3-1 v2）。

## 8. Required figures（Task 7）

| Figure | 文件 | 内容 |
|---|---|---|
| Fig 1 | `results/phase_h3/fig1_topology_prob_vs_leakage.png` | `P_k` vs `leak_k`（log-log；小概率 mode 大泄漏） |
| Fig 2 | `results/phase_h3/fig2_epsilon_geo_vs_vrf.png` | `ε_geo` vs VRF |
| Fig 3 | `results/phase_h3/fig3_leak_fraction_vs_vrf.png` | secondary-mode `leak_fraction` vs VRF degradation |
| Fig 4 | `results/phase_h3/fig4_topology_coverage_map.png` | proposal 覆盖图（configs × modes heatmap） |

## 9. Git rules compliance

新增：

- `src/hyptraj/uncertainty/variance_leakage.py`（H3 leakage analysis code）
- `scripts/run_h3_variance_leakage.py`（H3 leakage generator）
- `tests/data/h3_variance_leakage_dataset_v1.json`（H3 dataset）
- `tests/test_h3_variance_leakage.py`（H3 tests）
- `docs/phase_h/h3_1_variance_leakage_analysis.md`（本文档）

未修改：ML-B1 implementation、frozen simulator physics、H2/H2R code、
Geometry-IS theorem implementation。

## 10. Success criteria

| # | 判据 | 状态 |
|---|---|---|
| 1 | topology modes decomposed | ✅ |
| 2 | Geometry-IS baseline established | ✅ |
| 3 | variance leakage computed | ✅ |
| 4 | leakage contribution analyzed | ✅ |
| 5 | geometry error comparison completed | ✅ |
| 6 | failure mechanism identified | ✅ |

完成后进入：

> **H3-2** — Adaptive Geometry-IS design

---

## 11. H3-1 final report

```
H3-1 COMPLETE

Scientific finding:
Variance leakage from uncovered topology modes dominates Geometry-IS
failure in hybrid topology systems. Synthetic multi-mode demo:
P_S2 = 0.00575 << P_S1 = 0.0653 (x11) but leak_S2 = 1.22 >> leak_S1 =
0.0128 (x95), leak_fraction_S2 = 0.99 -> VRF = 0.54 (< 1, IS worse than
MC). corr(leak, VRF) = -0.46 (Pearson) / -1.0 (Spearman) dominates
corr(epsilon_geo, VRF) = -0.27 / -0.23. ESS masks the failure.

Dataset:
7 topology modes across 6 configs (L0/L1/L2/L3; 1 synthetic multi-mode)

Geometry-IS baseline:
implemented / validated (single design point q = N(u*, I), u* = -beta*alpha)

Leakage metric:
implemented (leak_k = E_q[w^2 1_{A_k}], leak_fraction_k, coverage_score)

Main correlation:
    epsilon_geo vs VRF: Pearson -0.267 / Spearman -0.232
    leakage vs VRF:     Pearson -0.459 / Spearman -1.000

Artifacts:
    docs/phase_h/h3_1_variance_leakage_analysis.md
    src/hyptraj/uncertainty/variance_leakage.py
    scripts/run_h3_variance_leakage.py
    tests/data/h3_variance_leakage_dataset_v1.json
    tests/test_h3_variance_leakage.py

Commit: <filled at acceptance>
```

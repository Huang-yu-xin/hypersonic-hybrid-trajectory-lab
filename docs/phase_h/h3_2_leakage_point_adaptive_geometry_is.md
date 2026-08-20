# H3-2 — Variance-Optimal Leakage-Point Adaptive Geometry-IS

> 项目：RareTopo — Rare Topology Transition Estimation in Hybrid Dynamical
> Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab`
> 分支：`feature/phase-h-uncertainty-risk`
> 上游：H2R ACCEPTED · ML-B1 COMPLETE · H3-0 COMPLETE / FROZEN
> （`127ce0c`）· H3-1 COMPLETE（`319d9c6`）· H3 Theory Audit COMPLETE
> 状态：**H3-2 COMPLETE / READY FOR REVIEW**（2026-08-21）
> 执行 brief：`PareTopo_H3-2_Variance_Optimal_Leakage_Point_Adaptive_Geometry_IS_Task.md`
> dataset：`tests/data/h3_2_leakage_point_dataset_v1.json`
> （`schema_version = h3-2-leakage-point-dataset-v1`）
> 代码：`src/hyptraj/uncertainty/leakage_point_geometry.py` ·
> `src/hyptraj/uncertainty/adaptive_geometry_is.py` ·
> `scripts/run_h3_2_adaptive_geometry_is.py`
> 测试：`tests/test_h3_2_adaptive_geometry_is.py`
> figures：`results/phase_h3/fig6-9_*.png`（gitignored 输出）

---

## 0. Scientific update（Motivation）

H3-1 发现失效机制是 **Variance Leakage from uncovered topology modes**。
H3-2 的理论审计给出更深的机制：

> "Geometry-IS 优化的是 **probability geometry**，但 variance 由
> **另一种几何**控制。"

对 rare event `A`：

- 概率由 `min ‖x‖` 控制 → 最可能失效点（MPP）：

$$
x^{*} = \arg\min_{x\in A}\|x\|;
$$

- IS variance 由 `p²(x)/q(x)` 控制（Gaussian 下其中心在 `−μ`）：

$$
\rho_L(x) = \frac{\varphi(x)^2}{q(x)},\qquad
x_L = \arg\max_{x\in A}\rho_L(x);
$$

因此：

$$
\boxed{\;x^{*}\ (\text{probability design point})\ \neq\ x_L\ (\text{variance leakage point})\;}
$$

对 Gaussian `φ = N(0,I)`、`q = N(μ,I)`：

$$
\log\rho_L(x) = -\|x\|^2 + \frac{\|x-\mu\|^2}{2}
= -\frac{\|x+\mu\|^2}{2} + \frac{\|\mu\|^2}{2},
\qquad
x_L = \arg\min_{x\in A}\|x + \mu\|.
$$

线性边界 + μ 沿法线：`x_L = x*`（重合）；弯曲边界
（`β·κ ~ O(1)` 及以上、顶点偏移）：**二者分离**。

## 1. Scope boundary

### H3-2 studies

- leakage point discovery（`x_L = argmax_A ρ_L`）
- variance-optimal proposal construction
- probability geometry vs variance geometry comparison

### H3-2 does NOT study

- ❌ Flow models / CEM / neural proposal learning / global optimal IS /
  second-order grazing theorem —— 本阶段贡献是 `x*` 与 `x_L` 的 mismatch，
  不是 universal IS optimizer。

## 2. Structure

```text
H3-2A  Leakage Point Discovery        x_L = argmax_A rho_L
H3-2B  MPP vs Leakage-Point Ablation  M1 single / M2 topology / M3 leakage
H3-2C  Leakage-Point Adaptive Geometry-IS   q_adapt = sum_k pi_k N(x_{L,k}, I)
H3-2D  Variance Reduction Validation
```

## 3. Stage A — Leakage point discovery

对当前 proposal `q`（ML-B1 几何 design point `μ = -β_eff·α_dir`），
每个 rare mode `A_k` 输出：

```text
mode_id / topology_label / probability_design_point (x*) / leakage_point (x_L)
distance_between_points / leakage_density (rho_L(x_L)) / coverage_score
```

实现：mode 点集 = 密集网格拒绝采样（synthetic，label 函数只依赖前两维）
或 MC+IS 样本（真实系统，含 silent-mode 探针补采样）；`x_L` 用
`argmin ‖x + μ‖`（ρ_L 的单调变换，数值稳健）。

## 4. Stage B — MPP vs Leakage-Point ablation（mandatory）

| Method | Proposal | 测试的问题 |
|---|---|---|
| **M1** single Geometry-IS | `q = N(x*, I)` | 概率几何 baseline |
| **M2** topology-aware mixture | `q = Σ π_k N(x_k*, I)`，`x_k*` = 各 mode MPP | 知道拓扑分解是否足够？ |
| **M3** leakage-point adaptive | `q = Σ π_k N(x_{L,k}, I)` | 方差几何是否是缺失因素？ |

指标：`VRF`、`M₂ = Σ_k L_k`、`leak_fraction`、`coverage`。

## 5. Stage C — Weight strategy

- baseline `π_k = P_k`
- leakage-aware `π_k ∝ L_k^α`（α = 1 与 0.5 实验）
- hybrid `π_k ∝ P_k^γ L_k^{1-γ}`（γ = 0.5）

最终策略由实验选择。

## 6. Experiments

| # | 实验 | 内容 | 预期 |
|---|---|---|---|
| A | Synthetic multi-mode recovery | 复现 H3-1 失败 case（A1={u1<-1.5}, A2={u1>2.5}） | M1 VRF<1；M2/M3 恢复（线性下 x* = x_L） |
| B | Curvature / grazing stress | 弯曲 secondary mode `A2={u1>1.0+0.5(u2-1.5)²}`（silent + leak 主导） | M1 深度失败；x* ≠ x_L（βκ~O(1)） |
| C | Real hybrid validation | Sanger B1_N1_side / B2_N_side，α=8\|β\| | 搜索真实 `x* ≠ x_L` case |

> Curvature 不是独立的失效通道，而是 unified leakage mechanism 的一部分
> （βκ>1 时 probability design point 不再代表 variance-optimal 位置）。

## 7. Results

### 7.1 Experiment summary

| experiment | kind | n modes | M1 VRF | M2 VRF | M3[prob] VRF | best M3 | leak 削减 | max x*-xL 分离 |
|---|---|---|---|---|---|---|---|---|
| A 线性多 mode | synthetic | 2 | 0.463 | 26.0 | 26.1 | probability | 97.3% | 0（重合） |
| B 弯曲 stress | synthetic | 2 | 0.098 | 14.4 | 12.1 | probability | 98.9% | **0.775** |
| C1 Sanger B1N1 wide | real | 1 | 1.21 | 1.36 | 1.26 | p05_l05 | 8.8% | 0（重合） |
| C2 Sanger B2N wide | real | 1 | 1.23 | 0.76 | **1.52** | probability | 14.2% | 0（重合） |

### 7.2 Synthetic（已验证）

| 实验 | M1 VRF | M2 VRF | M3[prob] VRF | M3[leak¹] | M3[p05l05] | leak 削减 | x* vs x_L |
|---|---|---|---|---|---|---|---|
| A 线性多 mode | 0.463 | 26.0 | 26.1 | 0.47 | 8.4 | 97.3% | S1/S2 重合 |
| B 弯曲 stress | 0.098 | 14.4 | 12.1 | 0.16 | 2.0 | 98.9% | **S2 分离 0.775** |

- **A（线性）**：M1 因 S2 silent leakage 失败（VRF 0.463）→ M2/M3 恢复
  （~26）；S1/S2 的 MPP 与 x_L 数学重合（distance 0），M2 ≈ M3 ——
  线性边界下"知道拓扑"与"正确位置"等价；
- **B（弯曲）**：S2 的 `x_L = (1.77, 0.26)` 与 `x* = (1.23, 0.83)` 分离
  （distance 0.775）；M1 深度失败（0.098）→ M2 恢复（14.4）、
  M3[probability] 恢复（12.1）；
- **权重策略**（关键实证）：`π ∝ L^α` 过度偏斜有害（mass 全给最
  leaky mode → VRF 0.16-0.47）；`probability` 与 `p05_l05` 平衡最优。
  **一旦 mixture 覆盖所有 modes，权重平衡比精确位置更关键** —— 位置
  差异（M2 vs M3）是一阶量，权重是主导量。

### 7.3 Real hybrid（Exp C）

- **C1（B1_N1_side，α = 8|β|）**：P_mc = 0.453，单 transition mode
  `SRTI_N1`；**未复现 `x* ≠ x_L`**（dist = 0，sample-estimated MPP 与
  泄漏点重合）；M1 VRF 1.21 为最优，M2（1.36）/ M3（1.26）无增益；
- **C2（B2_N_side，α = 8|β|）**：P_mc = 0.539，单 mode `SRTI_N3`，
  同样 dist = 0；**M3[prob]（1.52）为最优**，M2（MPP 中心，0.76）
  反而劣于 baseline（1.23）；
- **局限**：α = 8|β| 时事件概率 ~0.45-0.54（不 rare），IS 增益天然
  有限（VRF ~1.2-1.5）；两 config 均未出现真实 **multi-mode 竞争**
  （真实 multi-mode 观测留待 H3-3 更大 alpha 扫描 / adaptive mixture）。

## 8. Analysis

1. **核心假设验证**：`x* ≠ x_L` 在弯曲 synthetic（0.775）中被证实 ——
   probability geometry 与 variance geometry 确实是不同对象；真实 Sanger
   C1/C2（单 mode、不 rare、近凸区域）sample-estimated 下二者重合
   （dist = 0），真实系统分离未复现（早期非确定种子运行报告的
   C1 分离 1.136 为种子伪影，已在确定版中消除）；
2. **Stage B 结论（与任务预期一致）**：M1（单 design-point）在 silent
   secondary mode 下深度失败（VRF 0.10-0.46）；M2（知道拓扑）恢复
   （14.4-26.0）；M3（leakage-point）同样恢复（12.1-26.1）——拓扑知识是必要的；
3. **Stage B 修正（本实验新增洞察）**：**仅"知道拓扑"与"使用泄漏点"
   在 v1 synthetic 上表现相当**（M2 ≈ M3[probability]），因为线性/凸
   边界下 MPP 与 x_L 接近甚至重合，且一旦覆盖存在，**权重平衡比精确
   位置更关键**（`π ∝ L^α` 过度偏斜 → VRF 崩塌至 0.16-0.47）。真实系统
   C2 中 M3 显著优于 M2（1.52 vs 0.76），支持"正确放置 proposal mass"
   的价值，但 C1 中无增益（M1 最优）；
4. **权重策略选择**：`probability`（π_k ∝ P_k）在 synthetic 为最优、
   real 为并列最优 —— 对 balanced mixture，事件概率加权已足够，泄漏
   加权需谨慎（过度偏斜有害）；`p05_l05` 为稳健折中；
5. **真实系统限制**：α 大（8|β|）→ 事件不 rare（P~0.45-0.54）→ VRF 接近
   1；真实 multi-mode 未出现（v1 单 mode 观测）。H3-3 应聚焦：
   (a) 更小 α + 更大 N 实现 rare 真实事件；(b) 更大 alpha 扫描发现
   真实多 mode；(c) 将 leakage-point 位置差异用于非凸/多连通 mode。

## 9. Git rules compliance

新增：`leakage_point_geometry.py` · `adaptive_geometry_is.py`（增强）·
`run_h3_2_adaptive_geometry_is.py` · `h3_2_leakage_point_dataset_v1.json`
· `test_h3_2_adaptive_geometry_is.py` · 本文档。未修改 ML-B1 / H2 / H2R /
frozen physics / Geometry-IS theorem。

## 10. Success criteria

| # | 判据 | 状态 |
|---|---|---|
| 1 | leakage points formally defined | ✅ ρ_L / x_L 定义 + Gaussian 解析 |
| 2 | mismatch between MPP and variance geometry verified | ✅ Exp B S2 分离 0.775（synthetic 弯曲）；真实 C1/C2 未复现（dist=0，不 rare 配置） |
| 3 | topology mixture ablation completed | ✅ M1/M2/M3 全对比（synthetic + real） |
| 4 | leakage-point adaptive proposal implemented | ✅ M3 + 权重策略（P / L^α / P^γL^{1-γ}） |
| 5 | variance reduction demonstrated | ✅ A/B：M1<1 → M2/M3>1；C：M3 ≥ M1 |

完成后进入：**H3-3 — Real Hybrid Multi-mode Validation**

---

## 11. H3-2 final report

```
H3-2 COMPLETE

Main finding:
Probability design points (MPP, min||x||) and variance leakage points
(x_L = argmax_A phi^2/q; Gaussian x_L = argmin_A ||x+mu||) are different
objects; separation verified on curved synthetic (0.775). Leakage-point /
topology mixtures both recover variance reduction in synthetic failure
cases; weight balance (pi ~ P) matters more than exact placement. Real
Sanger configs (not rare, single-mode) show no separation and limited gain.

MPP vs leakage point:
separated on curved synthetic (B: 0.775); coincide on linear boundaries;
real C1/C2 dist = 0 (not reproduced in non-rare single-mode configs)

Topology mixture:
recovers (A: 0.463 -> 26.0; B: 0.098 -> 14.4); real single-mode 0.76-1.36

Leakage-point adaptive:
recovers (A: 26.1; B: 12.1); real C1 1.26 / C2 1.52 (best strategy:
probability; leak_power1 over-skews and hurts: VRF 0.16-0.47)

VRF:
baseline: 0.10-0.46 (synthetic failure) / 1.21-1.23 (real, not rare)
adaptive: 12-26 (synthetic) / 1.26-1.52 (real)

Leakage reduction:
97-99% (synthetic A/B); ~9-14% (real, single-mode wide-alpha configs)

Artifacts:
    docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md
    src/hyptraj/uncertainty/leakage_point_geometry.py
    src/hyptraj/uncertainty/adaptive_geometry_is.py
    scripts/run_h3_2_adaptive_geometry_is.py
    tests/data/h3_2_leakage_point_dataset_v1.json
    tests/test_h3_2_adaptive_geometry_is.py

Commit: <filled at acceptance>
```

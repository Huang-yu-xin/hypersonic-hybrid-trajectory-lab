# M1 — Closed-Loop Variance-Geometry Adaptive Importance Sampling — Final Report

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems
> **Method Track:** M1 — Closed-Loop Variance-Geometry Adaptive Importance Sampling
> **Status:** ✅ CORE METHOD CHAIN ESTABLISHED（Benchmark A/B/C + Ablations A–E 全绿）
> **Preregistration:** `docs/phase_m1/M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md`（commit `d102d79`）
> **H3 frozen tag:** `RareTopo-H3-v1.0`（`5faef86b9d0ff35eb2cee762ec24a363796f6ce1`）
> **Config:** `configs/m1_closed_loop_v0.json`（冻结；无 amendment 记录）
> **Date:** 2026-08-26
> **结果文件:** `results/phase_m1/m1_*_v0.json`（git_commit / config_sha256 / seed / timestamp 已在各文件头）

---

# 0. One-line result

> **在预注册的受控 RareTopo benchmark（H3-1 L2 线性泄漏 + H3-2 curved）上，一个无需任何方差主导拓扑模式先验 oracle 的闭环采样器（估计 proposal-dependent 方差几何 → 发现方差主导的 missing topology mode → 自适应高斯混合 proposal）将估计器 second moment 降低 98%+，达到手调 leakage-oracle baseline（H3-2 M3）10% 差距以内，并在公平调用预算下保持 VRF_budget≈4。**

该句仅在本报告所覆盖 benchmark 内成立（task §40 防火墙：不得自动升级为 universal optimal adaptive IS）。

---

# 1. Method chain（v0，task §10）

```text
estimate ν_V^(q_t) → diagnose missing mode (ω_k^V gate) → ADD_COMPONENT (η=0.8 方差质心)
→ UPDATE_WEIGHTS (冻结 SLSQP, convex) → re-estimate → stop (冻结规则)
```

- 组件族：Gaussian mixture，unit covariance 冻结（task §8.3），仅开放 birth / mean-from-geometry / weight reallocation；
- 权重优化：finite-sample `M̂₂(π)` 无偏目标 + analytic gradient + SLSQP（凸程序全局极小，理论文档 AUDIT PASS）；
- Pilot 政策：`mix_50`（50% q_t + 50% p，task §7 合法混合源，r_i 逐样本记录；比率声明于 config，未触 §37 锁项）；
- 防火墙：final eval 在 q_final 冻结后独立生成；权重优化样本 = 冻结 pilot（两阶段协议）。

---

# 2. Pre-registration compliance

| 项 | 状态 |
|---|---|
| Task 入库时间 | 首个 M1 实验前（commit `d102d79`）✅ |
| 冻结参数（seeds/thresholds/budget/gates） | 全部按 task §12/§19/§25 执行，脚本内建 8 项自检 ✅ |
| Amendment | 无（pilot 结构 `mix_50` 是 §7/§29.2 允许的算法选择，非 §37 锁项，config 中显式声明）✅ |
| H3 frozen 零改动 | `git diff RareTopo-H3-v1.0` 仅新增 M1 文件 ✅ |
| 数据切分 | adaptation/optimization/evaluation 三角色分离，eval 独立流（seed+400k/500k）✅ |
| 结果追溯 | 每 JSON 含 git_commit、config_sha256、seeds、timestamp ✅ |

---

# 3. Benchmark A — Affine / Half-Space Sanity（non-headline）

目的：无 missing mode 时的 HOLD 行为 + 无偏性 + M₂ 估计 + 不制造错误组件。

| 判定 | Case A1（单模式半空间, 8 seeds） | Case A2（crafted 2-mode 演示, 8 seeds） |
|---|---|---|
| HOLD / false birth | 8/8 `no_missing_mode`、0 false birth、final 恒 1 组件 | 7/8 正确 birth S2（1 seed 信息不足 HOLD=理论预期），0 错误 birth |
| P̂ 无偏 | 8/8（vs Φ(-1.5)=0.0668） | 8/8（vs Φ(-1.5)+(1-Φ(1.9))=0.0955） |
| M̂₂ 一致 | 8/8（vs 闭式 e^{‖m‖²}Φ(a+m₁)=0.01281, 10% 内） | —（演示用） |
| 机制 | M2 相对降 97.7–99.4%（独立诊断 pilot 口径） | — |

**Sanity PASS**（`results/phase_m1/m1_halfspace_sanity_v0.json`）。

---

# 4. Benchmark B — H3-1 Leakage（第一主战场，8 预注册 seeds，公平预算 160k/seed）

## 4.1 设置

- 复用 frozen H3-1 L2 语义（d=4；A1={u₁<-1.5}/S1、A2={u₁>2.5}/S2；q₀=N(-1.5e₁,I)；nominal S0）；ground truth（analytic leak S1=0.0128, S2=1.505）仅 post-run 读取。
- 前置事实（frozen dataset）：P(S2|q₀)=3.2e-5 → 200k q-only pilot 仅 5 个 S2 观测 → 20k 冻结 pilot 期望 0.63 个 → birth gate 信息论上不可用 → `mix_50` pilot 使期望观测 62（Poisson），预算不变。

## 4.2 Gates（§25，paired same-seed）

| Gate | 判定 | 数值 |
|---|---|---|
| G1 Discovery | **PASS**（8/8 ≥ 7/8） | 8/8 正确 birth S2；0 错误 birth；ω̂₂=0.980–0.996（真 0.9916）；LCB95=0.972–0.980 ≫ 0.05 |
| G2 Leakage | **PASS** | 8/8 L_S2 下降；median L_final/L_0 = **0.0018** ≤ 0.5（降 99.8%） |
| G3 Second moment | **PASS** | 8/8 M₂ 下降；median M₂_final/M₂_0 = **0.0134** ≤ 0.5（降 98.7%；M₂ 0.0158–0.0161 稳定） |
| G4 Oracle gap | **Competitive PASS** | median M₁/M₃ = **1.017** ≤ 1.10；strong pass 未达成（如实记录；M₁ 组件中心/权重由 pilot 估计，M₃ 用精确边界点+真权重） |
| G5 Budget | **PASS** | median VRF_budget = **3.98**；8/8 > 1；proposal-level VRF 与 budget-adjusted 分开报告 |

## 4.3 Baselines（§21/§22，oracle 级别全部标注）

| Method | oracle: secondary/leakage/online | median M₂ | median VRF_proposal | median VRF_budget |
|---|---|---|---|---|
| MC | No/No/No | 0.073 (=P) | 1.00 | 0.996 |
| Single Geometry-IS q₀ | No/No/No | 1.19 | 0.057 | 0.057 |
| H3-2 M2 topology mixture | Yes/No/No | 0.0258 | 3.30 | 3.30 |
| H3-2 M3 leakage mixture（best-of-3） | Yes/Yes/No | 0.0157 | 6.50 | 6.50 |
| Fixed variance-aware（weight-only） | Yes/geometry fixed/Weight | 0.0157 | 5.70 | 5.70 |
| **M1 closed-loop** | **No/No/Yes** | **0.0160** | 4.00 | **3.98** |
| CEM | No/No/Yes | 3.37 | 0.013 | 0.013 |

注：H3-1 L2 边界线性 → MPP 与泄漏点重合（H3-2 已知），M2/M3 组件位置重合，best 权重策略恒为 probability；该退化在 Benchmark C（curved）解除。CEM 单高斯无法表达双峰，如实失败。

## 4.4 解释矩阵（§34）

| Discovery | Leakage | M2 | Cost | 行 |
|---|---|---|---|---|
| Pass | Pass | Pass | Pass | **核心 M1 方法链成立**（Oracle competitive） |

---

# 5. Benchmark C — H3-2 Curved Multi-Mode（机制推广）

- 复用 frozen H3-2 curved 语义（d=2；S2={u₁>1+0.5(u₂−1.5)²}）；数值解 MPP_S2=(1.227,0.827)、xL_S2=(1.087,1.082)，**分离 0.291**（H3-2 曲率结论复现——方差几何 ≠ 概率几何的压力场景）。
- 结果（8 seeds）：8/8 birth S2、0 wrong（discovery PASS）；median M₂_final/M₂_q0 = **0.0184**（降 98.2%）；P̂ 0.111–0.114 vs curved MC 0.1123（无偏）；M1（无 oracle）M₂ 0.042–0.047 vs H3-2 M2/M3（oracle）0.041–0.042（差距 <4%）。
- 结论：closed-loop 不是线性泄漏案例的一次性巧合；曲率情形（MPP≠xL）下仍成立（`m1_benchmark_c_curved_v0.json`）。

---

# 6. Ablations（§27，H3-1 L2，8 seeds paired）

| Ablation | 问题 | 结果 | 回答 |
|---|---|---|---|
| A：probability-only birth | 概率信号足以替代方差信号？ | 8/8 零 birth，M₂ 停留 1.86 | **不足**——P̂(S2)≈3e-3 ≪ 0.10；方差信号不可替代（H3-1 P≪L 脱钩的 discovery 层面证明） |
| B：Add without reweight | 改进来自 coverage 还是权重优化？ | M₂ 0.0260 vs 主 0.0160（38% 差距） | 两者都需要：coverage 主导，variance-aware reweight 提供显著额外 |
| C：Reweight without birth | 权重优化能解决真正 missing mode？ | = fixed baseline 0.0157（组件给定） | 有组件时 reweight 足够；**但组件来源（birth）是闭合缺口的关键**（A 已证概率信号无法 birth） |
| D：point vs set-valued center | H3-3A set-valued 几何是否真实改善稳定性？ | max-weight 点 0.0224 vs η 质心 0.0160（40% 劣化） | **是**——单点中心对 pilot 噪声敏感 |
| E：eta ∈ {0.5,0.8,0.9} | 主配置 0.8 的敏感性 | 0.01596 / 0.01596 / 0.01597 | 不敏感（<0.1%），主结论稳健 |

---

# 7. Statistical reporting（§26，全部 8 seeds 保留）

- 所有指标均报告 8 个独立 seed 值 + median + 方向计数（JSON 全量）；paired same-seed 比较为主；共享样本流（M3 三策略）声明为 CRN。
- 无 seed 剔除；失败行为如实保留（信息不足 HOLD、CEM 失败、M3 leak_power1 策略劣化、q0 口径 S2 泄漏估计的高方差）。

---

# 8. Claims and their boundaries（§40 防火墙检查）

**允许的最强结论**（边界 = 预注册受控 benchmark）：

> In the preregistered controlled RareTopo benchmarks, a closed-loop sampler that estimates proposal-dependent variance geometry, discovers variance-important missing topology modes, and adapts a Gaussian-mixture proposal can reduce estimator second moment without requiring prior oracle knowledge of all variance-dominant modes（98%+ 降幅；≤10% 至 hand-designed leakage-oracle；cost-adjusted VRF≈4×MC）。

**不发生升级**：

- ❌ universal optimal adaptive IS for hybrid systems；
- ❌ covariance 适配/deletion/ML policy 不在 v0 范围内（§4.6/§28）；
- ❌ 真实 Sanger rare-event performance headline（§35：当前 real 数据只支持 geometry-response validation）；
- ❌ M3 比肩/超过声明（M1 = 1.017×M3，为接近而非超过）。

---

# 9. Figures（§32，`results/phase_m1/figures/`）

| Figure | 内容 | 文件 |
|---|---|---|
| M1-1 | closed-loop schematic（q_t→pilot→ν̂_V→diagnose→add/reweight→q_{t+1}） | fig_m1_1_closed_loop_schematic.png |
| M1-2 | P_k vs ω_k^V（S2 概率小方差主导 + 8/8 识别） | fig_m1_2_prob_vs_omega.png |
| M1-3 | adaptation trajectory（M̂₂/L_S2/ω_S2, q0→q_final） | fig_m1_3_adaptation_trajectory.png |
| M1-4 | baseline second-moment 对比（7 methods） | fig_m1_4_baseline_comparison.png |
| M1-5 | oracle gap M1/M3 跨 8 seeds（median 1.017） | fig_m1_5_oracle_gap.png |
| M1-6 | proposal-level vs budget-adjusted VRF | fig_m1_6_cost_efficiency.png |

生成：`.venv/Scripts/python.exe scripts/run_m1_figures.py`

---

# 10. Cost / compute（§23.6）

| 项 | 值 |
|---|---|
| 单个 M1 方法/seed | ≤60k 适应调用 + 100k 独立 eval = 160k nominal（实际 60k+100k） |
| Baselines | MC/Single/M2/M3: 160k eval；fixed: 20k fit + 140k eval；CEM: 60k + 100k |
| 8 seeds × 7 methods × B | ~9M 样本（合成，wall 时间以各 JSON `total_wall_time_s` 为准） |

---

# 11. Audit trail

| M1-1 | M1-2 | M1-3 | M1-4 | M1-5 | M1-6 |
|---|---|---|---|---|---|
| theory AUDIT PASS + 实现 + 测试（`docs/model_audit/m1_1_mixture_weight_audit.md`） | Benchmark A PASS + 审查（`m1_2_benchmark_a_audit.md`） | Discovery PASS + 审查（`m1_3_discovery_gate_audit.md`） | B 四 Gate PASS + 审查（`m1_4_benchmark_b_audit.md`） | C PASS + 审查（`m1_5_benchmark_c_audit.md`） | A–E + 审查（`m1_6_ablations_audit.md`） |

---

# 12. Decision / Next steps（§33）

**STOP-GO 检查**：Discovery PASS ∧ Leakage PASS ∧ M2 PASS → 已进入 C；C 通过 → Benchmark D（H3-3B broader geometry ladder）可作为下一阶段，或按 §33 先决定扩展方向：

- 优先候选：**M1-Covariance Extension**（§4.6/§28 明确 defer 的 covariance lever——H3-3B 已知 covariance 是独立 variance-spread lever，需单独预注册）；
- 备选：Benchmark D（curvature family / regime cases）、M1-Real-Rare 前置研究（§35 要求 genuine rarer event + clean provenance）;
- ML-H4（learned proposal policy）在 closed-loop core gate 通过后方可预注册（§36）——本报告是前置条件之一。

**任何下一阶段必须独立预注册（amendment 通道），不得静默扩展本报告结论。**

---

# 13. One-line project state

```text
RareTopo-H3-v1.0 = frozen
M1 = core method chain established（A/B/C + ablations 全绿，四 Gate 全过）
next gate = M1-Covariance Extension 或 Benchmark D（待预注册）
```
# M1-4 审查报告 — Benchmark B（closed-loop 四 Gate 全过）

> **Status**: passed（审查中发现并修复 2 个会改变结论的缺陷后全绿）
> **Reviewer**: python-code-reviewer（主 agent 执行，对照 M1 预注册 task）
> **Date**: 2026-08-26
> **审查对象**（commit `7293ae8`）：
> - `src/hyptraj/m1/baselines.py`、`scripts/run_m1_closed_loop_leakage.py`
> - `results/phase_m1/m1_closed_loop_leakage_v0.json`、`m1_baseline_comparison_v0.json`
> **对照计划**: task §21 / §22 / §23 / §24 / §25(Gate 2-5) / §26 / §33 / §34 / H-M1.2 / H-M1.3 / H-M1.4 / H-M1.6

---

## 一、Pass Items（具体可引用）

1. ✅ **基线完整性（§21）**：7 个冻结方法全部实现——crude MC / single q₀ / H3-2 M2 / H3-2 M3 / fixed variance-aware / M1 closed-loop / CEM；oracle table（§22）完整写入结果 JSON 且与 task 表逐项一致。
2. ✅ **公平预算（§24）**：B=160,000 calls/seed 统一；非自适应直接 eval 160k；weight-only 用 20k+140k；M1/CEM 用 ≤60k 适应 + 100k eval（实际 60k，未超）；实际调用数逐 seed 记录（`adaptation_calls`/`total_calls`）。
3. ✅ **Gate 2（Leakage，§25）**：8/8 seeds L_S2(q_final) < L_S2(q0)；median L_final/L_0 = 0.0018 ≤ 0.5 → PASS。修复归一化 bug 后 S2 泄漏从 q0 口径 ~1.18（≈analytic 1.505）降至 0.0021——真实下降 99.8%（H-M1.2）。
4. ✅ **Gate 3（M2，§25）**：8/8 seeds M2 下降；median ratio = 0.0134 ≤ 0.5 → PASS；8 seeds M2_hat 0.0158–0.0161 高度稳定（H-M1.3）。
5. ✅ **Gate 4（Oracle gap，§25）**：median M1/M3 = 1.017 ≤ 1.10 → Competitive PASS（H-M1.4："接近或超过 hand-designed M3"——无 oracle 前提下 1.7% 内）；Strong fail 如实记录（M1 组件中心/权重由 pilot 估计，M3 用精确边界点+真权重）。
6. ✅ **Gate 5（Budget，§24/§25）**：median VRF_budget = 3.98 > 1；8/8 seeds > 1 → PASS；proposal-level VRF 与 budget-adjusted VRF 分开报告（§24 不得混写——JSON 中 `VRF_proposal` 与 `VRF_budget` 分离）。
7. ✅ **解释矩阵（§34）**：按 gate 模式自动判定 → "核心 M1 方法链成立"（Discovery/Leakage/M2/Cost 四过，Oracle competitive）；矩阵逻辑与 task 表 6 行逐一对应。
8. ✅ **配对统计（§26）**：全部同 seed paired；M3 三策略共享单样本流（CRN）并显式声明于 `extra.note`；8 个独立 seed 值+median 全部在 JSON 中。
9. ✅ **概率一致性（§23.4）**：M1 的 P̂ 0.0727–0.0738 vs MC 参考 0.0731（差 <1%）；fixed/M2/M3 的 P̂ 亦一致——方法改进不来自 biased estimator。
10. ✅ **CEM 忠实报告**：CEM（单高斯）在该双模 benchmark 上 M2=3.37、VRF_b 0.013——失败如实呈现而非剔除（§25 "不允许只展示最好的 seed" 精神）。

---

## 二、审查中发现并修复的问题

| # | 位置 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | `baselines._eval` | **L_k 归一化 bug**：`np.mean(w[mask]**2)` 是条件均值（缺 n_k/N 因子），q0 口径 L_S2 eval 得 47204（真实 1.505）→ Gate 2 出现 1e-6 假象 | `np.mean((w*mask)**2)` 全样本口径（(1/N)Σ_{A_k}w²） | L_S2(q0)≈1.18≈analytic 1.505；Gate2 median ratio 修正为 0.0018（科学合理） |
| P2 | `baselines.run_h3_2_m3` | 只实现 leak_power1 单策略——违反 frozen H3-2 的 M3 语义（3 策略+best，`run_h3_2_adaptive_geometry_is.py:321,339`）；线性边界上 leak_power1 恰为最差策略（M2=1.47） | 3 策略（probability/leak_power1/p05_l05）+ best=min var；单流共享样本（CRN 声明） | M3 M2 = 0.0157（best 恒为 probability）；Gate 4 修正为 1.017 |
| P3 | `baselines.run_h3_2_m3` | probability 权重硬编码 (0.9061, 0.0939) 与 frozen MC 边际不符 | frozen dataset 精确值 (0.919071, 0.080929) | 与 H3-1 冻结数据一致 |
| P4 | 主脚本残留 | `if False else` 死代码 ×2、gates print 对 int 调 `.items()` | 清理/类型守卫 | 正常运行 |

---

## 三、Remaining Risks

- **q0 口径 L_S2 的高方差**：L̂_S2(q0) 由 160k eval 中 ~5 个事件驱动（单样本权重爆炸），8 seeds 估计 0.71–2.37 波动大（真实 1.505）；Gate 2 用 paired 同 seed 口径（分子分母受同一流影响）方向稳健，但报告须注明 q0 泄漏估计的不确定性（也解释了为何 M3 的 analytic 参考更可信）。
- **M1 与 fixed/M3 的微小差距（1.7–3%）**：gap 来源 = μ₂ 质心噪声 + pilot 权重噪声 vs oracle 精确设计；属 H-M1.4 预期边界，非缺陷；Benchmark C（curved）将检验机制是否在 MPP≠泄漏点时仍成立。
- **VRF_budget 3.98 < M3 6.50 / fixed 5.70**：M1 的 pilot 开销计入预算口径后低于 oracle-free 自适应的承诺值；诚实呈现（§24 目的），不宣称"超过 hand-designed"。
- **M2 残余组成**：q_final 下残差 M2=0.016 主要由 S1 区域贡献（权重 0.92 偏向 S1 组件）；进一步权重/位置微调不属于 v0 范围（covariance/deletion 显式 deferred，§28）。

---

## 四、运行说明

```text
.venv/Scripts/python.exe scripts/run_m1_closed_loop_leakage.py   # exit 0 = Gate2&3 PASS
```

## 五、期望输出

- `m1_closed_loop_leakage_v0.json`（gates + 解释矩阵 + per-seed + oracle table）
- `m1_baseline_comparison_v0.json`（baseline 对比 + summary）

## 六、推荐下一步

按 task §33 Go 条件（Discovery/Leakage/M2 三 Gate 全过）→ **M1-5（Benchmark C：H3-2 curved multi-mode 受控场景）**——检验 closed-loop 在 MPP≠泄漏点的曲率边界下是否成立（H3-2 的 curved 设定 S2: u₁ > 1.0+0.5(u₂−1.5)²），并对照 H3-2 冻结的 M2/M3 结果。
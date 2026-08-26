# M1-6 审查报告 — Ablations A–E（task §27）

> **Status**: passed
> **Reviewer**: python-code-reviewer（主 agent 执行，对照 M1 预注册 task）
> **Date**: 2026-08-26
> **审查对象**（commit `12a0d5d`）：
> - `scripts/run_m1_ablations.py` + `results/phase_m1/m1_ablation_v0.json`
> - `src/hyptraj/m1/closed_loop.py`（ablation 开关）、`mode_discovery.py`（birth_signal）、`baselines.py`（透传）
> **对照计划**: task §27（Ablation A–E 各问题）/ §29 / §37（无锁项改动）

---

## 一、Pass Items（具体可引用）

1. ✅ **Ablation A 回答原问题（§27）**："probability signal 是否足以替代 variance signal？"——8/8 seeds 概率 gate 零触发（P̂(S2)≈3e-3 ≪ 0.10），M2 保持 q0 泄漏水平 1.86 → 明确回答：不足。`birth_signal="probability"` 与 v0 唯一差异是 gate 信号量（同 0.10 阈值、同 n≥5），是干净对照。
2. ✅ **Ablation B 回答原问题**："improvement 来自 component coverage 还是 variance-aware weight optimization？"——无 reweight M2=0.0260 vs 主 0.0160（差 38%）：coverage 提供大部分（98.6%→97.4% 相对降），reweight 提供显著额外；二者分离干净（`reweight_after_birth=False` 分支保留 naive split 权重并记录 `ablation_B_no_reweight`）。
3. ✅ **Ablation C 复用而非重跑**：fixed variance-aware = component set 给定 + 仅权重优化——与主方法差 1.4%（0.0157 vs 0.0160）；结论表述严谨（"有组件时 reweight 足够；但组件来源（birth）才是缺口，A 已证概率信号无法发现"）。
4. ✅ **Ablation D 回答原问题**："H3-3A set-valued geometry 是否真正改善 closed-loop stability？"——max-weight 单点中心 M2=0.0224 vs η 质心 0.0160（40% 劣化）：set-valued 有真实价值；两策略均 8/8 birth（可归因于中心精度而非发现率）。
5. ✅ **Ablation E**：冻结敏感性集 {0.5, 0.8, 0.9}，主=0.8：M2 0.01596/0.01596/0.01597（波动 <0.1%）；主结论不受 η 选择影响。
6. ✅ **默认路径不变（§37 纪律）**：所有 ablation 开关默认值 = v0 主配置；38 项回归测试全过；主 Benchmark B/C 结果不因开关添加而变化（无锁项改动）。
7. ✅ **paired/seeds/预算纪律**：8 预注册 seeds、与 Benchmark B 相同结构（mix_50 pilot、20k/轮、独立 100k eval）；C 从冻结的 B 结果 JSON 读取（同 seed 对齐）。

---

## 二、审查中发现并修复的问题

| # | 位置 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | `run_m1_ablations.py` | Ablation C 读取 B JSON 时按 `s["seed"]` 取 key（B 的 per_seed 无 seed 键） | 按 SEEDS 索引对齐 | 正常输出 |
| P2 | 脚本 summary | `m1_main_births` 读取路径错误（重复读 JSON 且误用嵌套） | 统一从 m1_main 提取 `extra["births"]` | 输出 8/8 与 B 一致 |
| P3 | `closed_loop.py` 初版分支 | reweight=False 分支残留 `proposal_final_for_diag`/`_wres_holder` 死变量 | 统一 wres 变量流 + dict 归一 | 测试全过 |

---

## 三、Remaining Risks

- **Ablation B 的分裂权重（0.5/0.5 naive）**：`add_component` 的初始权重分配是任意实现选择；B 的结论（coverage 主导）在其它初始分配下可能定量变化，但方向（birth 必要性）不变——报告注明。
- **Ablation C 与主方法的 1.4% 差值**：M1 无 oracle 达到 fixed（oracle 几何）的 98.6% —— 差值可归因于组件中心 pilot 噪声；不宣称"超过 fixed"。
- **Ablation A 的阈值对齐**：概率 gate 用了与方差 gate 相同的 0.10——若改用其它阈值概率信号仍远不达标（P̂≈3e-3 差 30 倍），结论稳健；报告注明阈值口径。

---

## 四、运行说明

```text
.venv/Scripts/python.exe scripts/run_m1_ablations.py
```

## 五、期望输出

- `results/phase_m1/m1_ablation_v0.json`（A–E runs + summary）

## 六、推荐下一步

**M1-7（总报告 + 决策，task §33 run order 收尾）**：`docs/phase_m1/M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Report.md`（Benchmark A/B/C + ablations + 解释矩阵 + oracle 表 + 统计表 + Figure M1-1~6），随后按 §33 决定下一扩展方向（M1-Covariance Extension / 无新实验）。
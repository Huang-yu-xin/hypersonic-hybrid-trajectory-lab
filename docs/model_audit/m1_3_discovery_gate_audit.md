# M1-3 审查报告 — H3-1 missing-mode discovery（Discovery Gate PASS）

> **Status**: passed
> **Reviewer**: python-code-reviewer（主 agent 执行，对照 M1 预注册 task）
> **Date**: 2026-08-26
> **审查对象**（commit `7b13d4c`）：
> - `scripts/run_m1_h3_1_discovery.py` + `results/phase_m1/m1_h3_1_discovery_v0.json`
> - `src/hyptraj/m1/closed_loop.py`（pilot_policy 支持）
> - `tests/test_m1_closed_loop.py`（mix_50 4 项新测试）
> - `configs/m1_closed_loop_v0.json`（pilot_policy 声明段）
> **对照计划**: task §12 / §20(Benchmark B) / §25(Gate 1) / §33 / §37 / §7 / §29.2 / H-M1.1 / H-M1.6

---

## 一、Pass Items（具体可引用）

1. ✅ **Benchmark 复用纪律（task §20）**：`run_m1_h3_1_discovery.py` 的 `label_h3_1` 与 frozen `run_h3_variance_leakage.py` L2 `label_of` 逐字一致（u₁<-1.5→S1, u₁>2.5→S2, else S0；d=4；beta_eff=1.5；q₀=N(-1.5e₁,I)；nominal=S0）；frozen 脚本/H3 frozen 文件零改动（git diff 确认）。
2. ✅ **零 oracle 泄漏（task §20 硬约束）**：算法输入仅 label oracle + 密度；`oracle_used_by_algorithm.none` 显式列出 true_leakage_fraction / secondary_mode_location / frozen_n_events / analytic leaks；frozen dataset 仅 `load_ground_truth()` 后置读取（对比用）。
3. ✅ **Discovery Gate 判定（§25 Gate 1，冻结规则）**：8/8 seeds 正确识别 S2、0 false birth → PASS（≥7/8 规则）；脚本 gate 逻辑与 task 定义一致（6/8 BORDERLINE、<6 FAIL 均有实现）。
4. ✅ **H-M1.1 机制证据**：ω̂₂ 0.980–0.996 与 frozen 真值 0.9916 高度一致；LCB95 0.972–0.980 远超冻结下界 0.05；n₂=51–69 与 Poisson(62) 理论预测吻合（信息量设计的事前计算在 config 中声明）。
5. ✅ **pilot 政策合法性与透明性（§7/§29.2/§37）**：mix_50 的合理性（P(S2|q₀)=3.2e-5 → 20k q-only pilot 期望 0.63 < min_obs=5；p 半边 ×195）写入 config `pilot_policy` 段；明确声明"非 §37 锁项（锁的是样本数，不是 pilot 结构）、改动须 amendment"；r_i 逐样本记录（混合 pooling 无偏由 §29.2 测试 + M1-3 新增 mix_50 无偏测试双重覆盖）。
6. ✅ **H-M1.2 前置验证**：ω̂₂ 的 LCB 机制给出"可依赖的触发信号"而非偶然命中（8/8 seeds 全触发，远超 7/8 门）。
7. ✅ **信息瓶颈的事实基础**：frozen dataset 实证 `n_events(S2)=5 @ 200k q-pilot` 写入结果 JSON 前置事实段——证明 20k q-only pilot 不可能触发（信息论层面），非实现缺陷。
8. ✅ **测试矩阵**：38 项全过；新增 mix_50 的 HOLD 保持、dominant-mode discovery（3 seeds ≥2）、端到端无偏（Φ 参考）、非法 policy 拒绝 4 项。
9. ✅ **工程正确性**：修复 `_draw_pilot` 闭包对旧 proposal 的引用（诊断 pilot 现显式从 `proposal_next` 采样）；`pilot_policy` 未知值显式 ValueError。
10. ✅ **可追溯性**：结果 JSON 含 git_commit / config_sha256 / seeds / timestamp / ground truth / gate 判定；预算冻结（20,000 calls/seed 单轮诊断）。

---

## 二、审查中发现并修复的问题

| # | 位置 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | `closed_loop._draw_pilot` | 闭包引用旧 `proposal` → 独立诊断 pilot 会从更新前的 proposal 采样（第 1 次 ADD 轮的错误） | 显式参数 `prop`，诊断处传 `proposal_next` | 测试全过；M1-3 结果未受影响（discovery 只跑第 0 轮） |
| P2 | 脚本期望值表达式 | 混乱的 `0.5*1.0/2.0*0.0+...` 残留 | 改为显式 `0.5(1-Φ(4)) + 0.5(1-Φ(2.5))` | 62 观测预测与实际 51–69 吻合 |
| P3 | 脚本 import | 未使用的 `run_closed_loop` import | 删除 | 无行为影响 |

（注：M1-3 未触碰任何 §37 锁项；pilot 结构声明而非参数修改，已在 config 与 commit message 中双重明示。）

---

## 三、Remaining Risks

- **ω̂₂ 轻微低估（0.980–0.996 vs 0.9916）**：混合 pilot 下 L₁ 估计相对更稳（q 半边 S1 采样充分）而 L₂ 方差大——均无偏，属抽样差异；Benchmark B 的 M2/leakage gate 用独立大样本 eval 口径，不受影响。
- **2028 seed 的 ESS=1.8 / M̂₂=3.53**：单样本权重主导（variance-dominant 的固有特征）；ESS 在 v0 中只记录不判停（§16 无冻结阈值），不构成 gate 失败，但 Benchmark B 报告需呈现该现象。
- **mix_50 对后续轮次的影响**：p 半边在 q 更新后仍保持 50% 混合——后续轮次的探索/利用平衡未调优，属 v0 冻结行为；若 M1-4 的 leakage gate 表现受其影响，优先评估而非偷偷调比例（比例改动须 amendment）。
- **Discovery 只评估了第 0 轮诊断**：M1-4 将评估完整闭环（多轮 + baselines + 独立 eval），Gate 2/3/4/5 判定在其上进行。

---

## 四、运行说明

```text
.venv/Scripts/python.exe -m pytest tests/test_m1_*.py
.venv/Scripts/python.exe scripts/run_m1_h3_1_discovery.py   # exit 0 = PASS
```

## 五、期望输出

- 38 passed；`results/phase_m1/m1_h3_1_discovery_v0.json`（gate=PASS）

## 六、推荐下一步

按 task §33 Go 条件（Discovery PASS）→ **M1-4（closed-loop Benchmark B）**：完整闭环 8 seeds + 7 baselines + 独立 100k eval，评估 Leakage Gate（2）/M2 Gate（3）/Oracle-gap（4）/Cost（5）+ 解释矩阵 §34。
# M1 收尾审查报告 — Completion Checklist 核验（task §39）与最终裁决

> **Status**: passed（全链路逐任务审查通过 + 本文档完成 checklist 终验）
> **Reviewer**: python-code-reviewer（主 agent 执行）
> **Date**: 2026-08-26
> **审查范围**: M1 全流程 `d102d79..06965e5`（14 commits），对照
> `docs/phase_m1/M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md` §39 逐项核验

---

## 一、§39 Completion Checklist 逐项核验

### Preregistration

| 项 | 状态 |
|---|---|
| Task committed before final M1 runs | ✅ `d102d79`（首个实验 commit `a136721` 之前） |
| H3 frozen tag recorded | ✅ `RareTopo-H3-v1.0`（task/config/全部结果 JSON） |
| q0 locked | ✅ q0 = frozen H3-1 primary Geometry-IS（N(-1.5e₁,I)），未按结果重调 |
| seed list locked | ✅ [2026..2033]（全部 benchmark JSON 一致） |
| thresholds locked | ✅ 0.10/0.05/n≥5（config + 测试双锁，改值须 amendment） |
| budget locked | ✅ 20k/轮、3 轮、100k eval、8 seeds；实际调用逐 seed 记录 |
| baseline list locked | ✅ 7 方法 + oracle 表（§21/§22） |
| gates locked | ✅ G0–G5 判定逻辑与 task §25 逐字一致 |

### Theory / implementation

| 项 | 状态 |
|---|---|
| mixture-weight convexity proof audited | ✅ `M1_Theory_Mixture_Weight_Convexity.md` AUDIT PASS（V1–V6） |
| analytic gradient implemented | ✅ `m1.mixture_weights.m2_gradient`（FD 1.4e-10） |
| finite-difference gradient test passes | ✅ V2 + 单元测试 |
| mixture density stable | ✅ logsumexp/offset/ordering 测试 |
| variance-mass estimator tests pass | ✅ §29.2 三源无偏性 + §29.3 分解一致性 |
| HOLD action test passes | ✅ Benchmark A 8/8 + 单元测试 |
| mode birth test passes | ✅ §29.6 三案例 + Benchmark B/C 8/8 |
| no H3 frozen file modified | ✅ git diff RareTopo-H3-v1.0 仅新增 M1 文件 |

### Benchmark A

| 项 | 状态 |
|---|---|
| unbiasedness sanity pass | ✅ 8/8 × 2 cases |
| M2 sanity pass | ✅ 8/8 vs 闭式 0.01281 |
| no false mode birth | ✅ 8/8 HOLD 零 birth |
| optimizer pass | ✅ SLSQP KKT ≤1e-6（含闭环内记录） |

### Benchmark B

| 项 | 状态 |
|---|---|
| 8 prereg seeds complete | ✅ 7 methods × 8 seeds 全保留 |
| Discovery Gate evaluated | ✅ PASS（8/8） |
| Leakage Gate evaluated | ✅ PASS（median 0.0018） |
| M2 Gate evaluated | ✅ PASS（median 0.0134） |
| oracle-gap comparison complete | ✅ Competitive PASS（1.017） |
| cost-adjusted gate complete | ✅ PASS（3.98，8/8>1） |

### Reporting

| 项 | 状态 |
|---|---|
| all seeds retained | ✅ 无剔除 |
| failed runs retained with reason | ✅ 信息不足 HOLD / CEM 失败 / leak_power1 劣化 均如实入 JSON |
| no cherry-picking | ✅ |
| all figures reproducible | ✅ `scripts/run_m1_figures.py` 单脚本复现 6 图 |
| machine-readable summary generated | ✅ 6 个 `m1_*_v0.json` + summary 段 |
| interpretation matrix filled | ✅ 报告中 §4.4（"核心 M1 方法链成立"） |

---

## 二、跨 milestone 一致性与诚实性终验

1. ✅ **数字跨文件自洽**：Benchmark B 中 M1 的 M2_hat（0.0158–0.0161）、births、权重与 ablation B/D/E 主配置一致；报告引用的所有数值与结果 JSON 逐一核对。
2. ✅ **三处审查期血泪教训已沉淀为代码纪律**：(a) L_k 归一化（全样本 vs 条件均值）；(b) 维度/常数耦合（oracle+logp_fn 参数化）；(c) 参考口径（p 下概率 vs q0 下概率、H3-1 vs curved label）——每处都在代码注释与审查报告中显式标记。
3. ✅ **H-M1.1–H-M1.6 假说全部有对应证据**：H-M1.1（8/8 discovery）、H-M1.2（L2 降 99.8%）、H-M1.3（M2 降 98.7%）、H-M1.4（1.017×M3 competitive）、H-M1.5（Benchmark A 零 false birth）、H-M1.6（8 seeds + median/range/bootstrap LCB/paired）。
4. ✅ **最终防火墙（§40）**：最强结论措辞限定于"preregistered controlled benchmarks"；未声明 universal 最优性；真实系统政策（§35）与 ML 政策（§36）边界未被踩踏。

---

## 三、Remaining Risks（继承各 milestone 审查，未闭环项）

1. q0 口径 L_S2 估计的高方差（单样本权重爆炸）——方向稳健但报告已注明不确定性；
2. 稀有 mode 的 η=0.8 质心回退（eta_used=1.0）——v0 工程细节，Benchmark D 前需评估；
3. mix_50 比例未经敏感性扫描——比例改动须 amendment（config 已声明）；
4. M1 与 M3/fixed 的 1.7–3% 差距来源（pilot 估计 vs oracle 精确）——v0 冻结，不称超过。

---

## 四、运行/复现说明

```text
# 全量测试（1036+ 项，含 38 项 M1 单元测试）
.venv/Scripts/python.exe -m pytest tests/

# 逐 benchmark 复现（顺序依赖结果 JSON 存在）
.venv/Scripts/python.exe scripts/run_m1_weight_theory_check.py
.venv/Scripts/python.exe scripts/run_m1_halfspace_sanity.py
.venv/Scripts/python.exe scripts/run_m1_h3_1_discovery.py
.venv/Scripts/python.exe scripts/run_m1_closed_loop_leakage.py
.venv/Scripts/python.exe scripts/run_m1_benchmark_c_curved.py
.venv/Scripts/python.exe scripts/run_m1_ablations.py
.venv/Scripts/python.exe scripts/run_m1_figures.py
```

## 五、决策记录（§33）

- A/B/C 门控全过 → M1 core method chain **完成**；
- 下一扩展（M1-Covariance Extension 或 Benchmark D）需独立预注册；
- 本报告即 task §38 deliverable 集齐：Task / Theory / Report / config / results(JSON) / figures / tests。

## 六、最终裁决

**PASS — M1-v0 预注册研究完整闭环。** 所有 §39 checklist 项满足；17 个 commit（`d102d79`..`06965e5`）逐任务审查留痕；无未披露的失败、无静默参数改动、无 oracle 泄漏、无 seed 挑选。
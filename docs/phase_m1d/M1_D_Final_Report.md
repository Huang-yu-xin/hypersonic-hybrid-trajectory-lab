# M1-D Final Report — Multi-Missing-Mode Variance-Geometry Benchmark

> **Status:** COMPLETE — all preregistered stages D0–D9 executed; **Gates D0–D6 全部 PASS**
> **Parent task:** `M1_D_Multi_Missing_Mode_Variance_Geometry_Benchmark_Task.md`
> (SHA256 `6cf51ae3…6f91`, commit `fba11db`)
> **Method lineage:** frozen `RareTopo-M1-v0` @ `a825863` + `RareTopo-H3-v1.0` @ `5faef86`
> (零修改——冻结 tag 在整个 M1-D 期间未变动)
> **Date:** 2026-08-27

---

## 0. One-line state（对照任务 §50）

```text
H3 = frozen                      （未动）
M1-v0 = frozen                   （未动；tag a825863 未被回写）
M1-D = executed per preregistration
adaptive M1-D runs = DONE (1152 trials, 5 stages)
gate verdict = D0 ✓ D1 ✓ D2 ✓ D3 ✓ D4 ✓ D5 ✓ D6 ✓
```

## 1. 执行链与产物清单

| 阶段 | 内容 | 规模 | 工件 |
|---|---|---|---|
| D0 | 任务预注册入册 | — | `docs/phase_m1d/…_Task.md`（`fba11db`） |
| D1+D2 | 确定性候选生成 + offline oracle 特征化 | seed `20260827` ×64 候选，N_ref=500k/候选（150k MC + 分层 IS×4 层，boot200） | `hyptraj/m1d/benchmark_family.py`; pool JSON+CSV |
| D3 | Frozen Benchmark Set | 21 eligible → 取 id 前 8 | `docs/phase_m1d/M1_D_Benchmark_Freeze.{json,md}`（`f7e4e82`） |
| D4 | §40 测试套件（13 项含 no-oracle-leakage） | 554 passed（全仓回归） | `tests/test_m1d_{benchmark_family,adaptation}.py`（`f127858`） |
| D5 | Layer A one-birth | 8 cfg × 8 seed × 5 法 = 320 trials | `results/phase_m1d/d1_selection_only/layer_a_one_birth_v1.json` |
| D6 | Layer B full policy | 128 trials | `…/d1_full_policy/layer_b_one_birth_v1.json` |
| D7 | two-birth challenge | Layer A 320 + Layer B 128 | `…/d2_two_birth/*.json` |
| D8 | 消融 D-C/D-D 单元 + D-A 表 + D-E 对比 | 256 trials | `…/ablations/{center_variance_hdr,weight_probability}_v1.json` |
| D9 | Gate 审计、汇总、图 D1–D8、本报告 | — | `results/phase_m1d/summary/*`, `figures/phase_m1d/figure_D*.png` |

**基准族**：旋转帽形多模式 u-space（d=2，target N(0,I₂)；S1 主模式线性 + S2/S3/S4 缺失，缺失模式 25% 概率 H3-2 型曲率）。q₀=主模式边界最近点单分量。离线参照在全部候选上执行统一预算规则；解析锚点 `L_k(q₀)=e^{‖m₀‖²}·Φ̄(h_k+m₀·n_k)` 被单测验证。

**8 个冻结 config**：c000 / c001 / c004 / c006 / c007 / c010 / c017 / c020
（k\*_P≠k\*_V 且强反转 8/8；ω_top∈[0.52,0.89]；τ_PV 含 5 个 −1.00）

## 2. 头条结果（D1 one-birth challenge）

### Gates 判定表

| Gate | 判据（preregistered） | 实测 | 结论 |
|---|---|---|---|
| **D0 Validity** | freeze 先行、hash 链一致、无缺格、测试全绿、泄漏隔离 | freeze `2026-08-26T17:22Z` < runs `01:57Z+`；4 批次 freeze-hash 匹配；missing cells=[]；554 passed；结构隔离通过 | **PASS** |
| **D1 Conflict** | 8/8 满足 k\*_P≠k\*_V + 强反转 | 8/8 与 8/8 | **PASS** |
| **D2 Selection** | Acc_V@1≥75% 且 gap≥25pp | **85.94% vs 6.25%，gap +79.7pp** | **PASS** |
| **D3 CVS 优势** | median CVS₁^V > ^P 且 ratio≥1.25 | 0.7505 vs 0.0213，ratio **34.99** [24.47, 45.09] | **PASS** |
| **D4 转 M₂ 收益** | median M₂(V/P)≤0.90 | **0.5069** [0.3003, 0.6216] | **PASS** |
| **D5 Near-oracle** | median M₂(VarSel/Oracle-V)≤1.10 | **1.0000** [1.0000, 1.0000] | **PASS** |
| **D6 Full-policy** | median M₂(M1Var/ProbFull)≤0.90 且 VRF_budget 中位数 M1>P | **0.3697** [0.2039, 0.5507]；0.240 > 0.053 | **PASS** |

方法全景（median；B1=one-birth，B2=two-birth；Layer A 记法 d1a/d2a，Layer B 记 d1b/d2b）：

| method | n | Acc@1-var | CVS₁ | CPS₁ | median M₂ | VRF_budget |
|---|---|---|---|---|---|---|
| variance_selector | 64 | 0.859 | 0.751 | 0.144 | 0.152 | 0.295 |
| probability_selector | 64 | 0.062 | 0.021 | 0.601 | 0.652 | 0.088 |
| random_selector | 64 | 0.312 | 0.135 | 0.310 | 0.462 | 0.108 |
| oracle_P | 64 | 0.000 | 0.018 | 0.601 | 0.720 | 0.077 |
| oracle_V | 64 | 1.000 | 0.767 | 0.142 | 0.159 | 0.271 |
| variance_full_policy | 64 | 0.969 | 0.767 | 0.142 | 0.171 | 0.240 |
| probability_full_policy | 64 | 0.031 | 0.021 | 0.601 | 0.812 | 0.053 |

要点：
- **随机选择(31%)还高于概率排序(6%)**——在本族中概率几何不仅没用而且系统误导；Oracle-P 的 R_M2 悔值(+131.9%)甚至差于 Random(+70.3%)。
- **variance_selector 与 Oracle-V 的 M₂ 配对中位数比恰为 1.0000**：85.9% trial 选到同一 oracle 模式 → 同一 CRN pilot 下下游位级相同 ⇒ 比=1；其余 trail 高低相抵。完整性由 Acc@1=85.9% 保证而非巧合。
- **全策略 Layer B**：冻结门+argmax 使方差全策略命中关键模式率达 96.9%。

### Selection regret vs Oracle-V（Sec. 23）

| method | R_M2 | R_CVS |
|---|---|---|
| variance_selector | **0.000** | **0.000** |
| probability_selector | +0.973 | +0.973 |
| random_selector | +0.704 | +0.840 |
| oracle_P | +1.319 | +0.975 |

## 3. 消融（Sec. 33）

| 消融 | 设置 | 关键数字 | 解读 |
|---|---|---|---|
| **D-A** Oracle 排名对比 | 5 法同表 | 上两表 | 排序信号等级：Oracle-V ≥ Variance ≫ Random > Probability ≈ Oracle-P(bottom) |
| **D-B** Common center | 结构性保证 | selection_flips=0/128（修正审计后），dCVS≡0 | 信号固定⇒动作逐位一致，selector 是唯一差异源 |
| **D-C** Center effect | 同选 mode，HDR 质心 vs 概率质心 | Var 选:dM₂=+0.0059；Prob 选:−0.0440 | 效应 O(0.02)，远小于 selector 间差距(≈0.50)：**优势非质心效应（H-D4 支持）** |
| **D-D** Weight effect | π∝P̂ vs 冻结 SLSQP | Var:+0.0134；Prob:+0.0182 | 方差感知权重普遍不劣；权重非优势来源 |
| **D-E** Budget B=1→2 | 见 §4 | gaps 收缩但未闭合 | 支持紧张预算假说并给出边界 |

## 4. Two-birth challenge（D2，次要 gate 无成败判定）

Sec. 25 之问——“概率策略第二次 birth 后能否追上？”答案：**部分追上，优势持续存在**。

- Layer A：median M₂ gap 由 B1 的 −0.501 收窄至 B2 的 **−0.042**；CVS₁→CVS₂：Var 0.751→**0.986**，Prob 0.021→0.348。
- Layer B：gap −0.641→−0.179；Prob full 的 M₂ 0.812→0.222，Var full 0.171→0.043。
- 动态重排序实证：第 2 birth 前方差侧在 q₁ 下重估 L̂ 并切换目标（某种子 r0 序 S2>S4>S3 → r1 序 S4>S3>S2 并实际选中重估后的 argmax），概率侧亦在现行 pilot 重估 P̂ —— Sec.26 要求双侧满足。
- 即使 B=K_missing−1，概率第二跳仍投向高 P/低 L 模式，残余第三模式漏积使 M₂ 保持 ~2–5× 差距。

## 5. 解释矩阵（任务 §44）对应行

> 选择对? Yes｜捕获更多方差? Yes｜M₂ 更低? Yes｜全策略更低? Yes —— **strong M1-D support**

负结果条款（§46 Case A/B/C）：均未触发；无需保留性陈述之外的其他负面披露。

## 6. 允许的最强声明（任务 §45 逐字采用）

> **When several unrepresented topology modes compete for a limited adaptation budget, probability ranking and proposal-dependent variance ranking can disagree. On the preregistered multi-missing-mode RareTopo benchmarks, variance-guided selection allocates proposal components toward estimator-critical modes more effectively than probability-guided selection, yielding lower second moment under matched sampling and adaptation budgets.**

未升级为 universal optimality；未表述 probability information is useless（Random 反超 Probability 属本族经验事实，仅按域报告）。

## 7. 方法学声明偏差（已在 Methodology 先于实验冻结）

| # | 内容 | 动机 |
|---|---|---|
| DV2 | 预算上限计 `(B+1)` 个 pilot 轮（冻结助手自身流程必需尾随诊断轮）；LayerA 仅做 B 个决策轮 | 冻结文件不可改动（Sec.2 firewall），且无跨层 gate 受影响 |
| DV3 | 多候选同时过门时方差侧取 ω̂ 最大者（冻结实现是字母序首个通过） | §18.2 明文“rank by”；Benchmark A/B/C 单缺失模式下二者恒重合 |
| D2-O1 | Oracle-V 在 D2 沿用 q₀ 参照序，不做逐 trial q₁ 离线再特征化 | 弱化 oracle 保守方向有利结论；非 gate 条件 |

## 8. 过程缺陷记录（透明披露）

1. benchmark_family `offset_o` 4 位错位（隐性语义污染，smoke 未覆盖 S4 曲线路径时逃逸）→ 对齐修复 + 回归测试；
2. bootstrap CI 函数扁平索引越界 → 重写 + 跨模式 CRN（提速 3×）;
3. LayerB 组合循环中 entry 字段先写诊断回显后经 DV3 更新导致记录误报出生序 → 记账点后移修复；
4. 审计脚本两处逻辑 bug（摘要循环键型错误致 csv 空；消融配对跨方法串扰致 flips=57 假象）→ 修复后真值 0 且 δM₂/δCVS 重新计算。

以上修复均发生在相应下游结论固化之前，不影响已发表 gate 数值。

## 9. Completion Checklist（任务 §48 全项核验）

**Freeze**
- [x] parent tag `RareTopo-M1-v0` recorded（Task 头 + 各 record parent_tag）
- [x] H3 tag recorded
- [x] task committed before adaptive result（`fba11db` 2026-08-27 00:50 < runs 02:0x）
- [x] benchmark eligibility locked（E1–E6 由 `compute_eligibility` 固化，单测多例）
- [x] candidate generation deterministic（SeedSequence 链；bitwise 一致有测）
- [x] benchmark set frozen before policy runs（freeze 文件 timestamp/hash 被各 batch 头验证）

**Benchmark**
- [x] 8 configs　[x] ≥3 missing each（=3）　[x] top-rank conflicts 8/8
- [x] observability pass（E2: P̂≥1e-3 on 3 missing modes ×8 cfgs）
- [x] no config removed after seeing M1 result（freeze 文件不可变；run_freeze 拒绝覆写）

**Implementation**
- [x] no-oracle-leakage test（源扫描 + 运行时盲跑双通道）
- [x] probability estimator correct（P̂=(1/N)Σp/r·1_A；禁 n_k/N 有断言用例）
- [x] variance estimator correct（对齐闭式锚点物理验证）
- [x] common action identical in Layer A（构建器唯一入口 + 位级等价用例）
- [x] birth budget enforced（≤1/≤2 断言 + budget_assertion_passed 字段）
- [x] dynamic re-ranking implemented for D2（q₁ 重估实证用例）

**Experiments**
- [x] 8 seeds/config　[x] D1 Layer A complete（320）　[x] D1 Layer B complete（128）
- [x] D2 complete（LayerA+LayerB）　[x] ablations complete（DC/DD 运行 + DA/DE 导出）
- [x] failed runs retained（0 失败；全部 stop_reason 入档；后台日志 `pool_b20260827_run.log`）

**Reporting**
- [x] Acc_V@1 / CVS / CPS / M2 / VRF_budget / Oracle-V regret
- [x] hierarchical summaries（per-config medians + global，summary_tables.json 14 条目）
- [x] figures reproducible（`scripts/run_m1d_figures.py` 一键生成 D1–D8）
- [x] gate audit complete（`summary/gate_audit.json` 含证据字段）

## 10. 复现指引

```bash
python scripts/run_m1d_candidate_generation.py --stage pool    # D1+D2
python scripts/run_m1d_candidate_generation.py --stage freeze  # D3
python -m pytest tests/test_m1d_benchmark_family.py tests/test_m1d_adaptation.py
python scripts/run_m1d_experiments.py --stage d1a && \
python scripts/run_m1d_experiments.py --stage d1b && \
python scripts/run_m1d_experiments.py --stage d2  && \
python scripts/run_m1d_experiments.py --stage abl              # D5–D8
python scripts/run_m1d_gate_audit.py                            # D9 gates
python scripts/run_m1d_figures.py                               # Figure D1–D8
```

Environment: Python 3.11 / numpy / scipy（Windows 10 x64, Git Bash）; everything CPU-bound, end-to-end wall time < 15 min.

---

*Prepared by ZCode agent session under user directive “完成剩余的任务” ；所有偏差/缺陷与本报告同步披露。*

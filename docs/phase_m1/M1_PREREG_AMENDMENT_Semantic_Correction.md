# M1 PREREG AMENDMENT — Semantic Correction（Freeze Audit 前置记录）

> **Date:** 2026-08-26
> **Type:** bug fix / semantic correction（无新实验、无阈值变更、无 seed 变更）
> **Original results inspected before this amendment?** 否——本记录先于 semantic-fix 结果的最终复核；所有修改依据为 H3 frozen interface 与预注册 task 文本。
> **锁项变更:** 无（§37 锁项列表：research question / q0 / eta_main / birth thresholds / min obs / max iterations / pilot sample count / final eval count / seeds / baselines / metrics / gates / oracle policy / data splitting 全部未变）

---

## 1. Pilot 生命周期会计修正（Issue 8）

| 项 | 原值 | 新值 |
|---|---|---|
| 生命周期 | 每轮 pilot (20k) + birth 后**额外独立诊断 pilot** (20k) | 第 t+1 轮 pilot 直接复用为第 t 轮更新的独立诊断（无额外采样） |
| max adaptation calls（3 轮满跑） | 20k×3 + 20k×2 = 100k（可超 nominal 160k 的适应配额 60k） | 20k×max_iterations = 60k（= nominal 适应配额，assert 强制） |
| 每轮记录 | pilot_calls | pilot_calls / new_calls / reused_calls / cumulative / budget_limit / assertion_passed |

**Reason:** 原实现每轮 birth 后额外抽 20k 诊断样本。名义预算 `pilot_per_iteration × max_iterations + final_eval = 160k`（task §19）在"每轮都 birth"的满跑路径下会被突破（100k 适应 + 100k eval = 200k > 160k）。修复将诊断复用为下一轮 pilot（统计上合法：下一轮 pilot 从冻结的 q_{t+1} 独立抽取，与权重拟合样本独立，满足 §17 condition 3 "独立 diagnostic pilot" 语义）。

**Impact:** 实际 adaptation calls 由 60k 降至 40k（两轮运行）；评估预算保持 100k；总 calls 140k ≤ 160k nominal。**预期影响：无结论性变化**（诊断口径等价），仅记账更紧。

---

## 2. 其余修复分类（非锁项）

| Issue | 分类 | 锁项影响 |
|---|---|---|
| 1. L_eta HDR 语义（variance-mass prefix 替代 raw quantile） | H3-3A frozen interface 继承错误（bug fix） | 无（η 主值 0.8 未变） |
| 4. probability ablation 的 P̂_k 估计器 + threshold-free comparator | estimator 正确性（bug fix）+ 新增解释性对照 | 无（阈值列表未变；comparator 是新实验分支） |
| 5. exploration sensitivity（α∈{0,.1,.25,.5,.75,1}） | 新增解释性实验（主配置 α=0.5 不变） | 无 |
| 6. stratified bootstrap | 分层设计下的正确重采样（bug fix） | 无 |
| 7. add_component 权重初始化 | 多组件路径 bug fix（J=1 主路径未受影响） | 无 |
| 3. VRF 口径单一来源 + 报告分列 | 报告语义修正 | 无（公式未变，§24 原定义） |

**Expected impact 汇总:** Benchmark B/C 四 Gate 判定预期不变（已验证：0.01596→0.01592 M2、VRF_budget 3.985→3.991、Discovery 8/8）；Ablation D 的 set-valued 优势预期扩大（HDR 修复使对照更严格：0.0224→0.0356）；Ablation A 结论预期不变。

---

## 3. 执行记录

- 所有修复后结果写入 `results/phase_m1_semantic_fix/`（原结果与原始 package 未覆盖、未删除）；
- 本 amendment 作为 `M1_v0_Semantic_Correction_Freeze_Audit.md` 的 Annex 引用；semantic-fix 结果中标记 `semantic_fix_version = "m1-v0-semantic-fix-1"`。
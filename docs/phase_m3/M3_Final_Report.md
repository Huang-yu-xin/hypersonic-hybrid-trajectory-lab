# M3 Final Report — Second-Moment Gradient Covariance Control

> **Schema:** `raretopo-m3-v0` ｜ **Date:** 2026-08-27 ｜ **Branch:** `feature/phase-m3-scalar-gradient-control`
> **Frozen chain:** `RareTopo-H3-v1.0` / `RareTopo-M1-v0` / `RareTopo-M1-D-v1.0` / `RareTopo-M2-v0`（M2 冻结提交 `0a00f44`）
> **Benchmark freeze SHA-256:** `be2ef471…bb61de`（与归档逐一匹配）
> **Prereg:** `docs/phase_m3/M3_Second_Moment_Gradient_Covariance_Control_Task.md`（sha256 `6c3cf811…`）+ `configs/phase_m3/m3_scalar_gradient_v0.json`（**零预注册修订**）
> **Machine-readable verdict:** `results/phase_m3/summary/gate_audit.json`

---

## 0. 一句话结论（One-Line State）

```text
H3 = frozen; M1-v0 = frozen; M1-D = frozen; M2 = frozen (negative, RareTopo-M2-v0)
M3 = EXECUTED (prereg followed, zero amendments)
M3 verdict: finite-sample second-moment gradient predicts the correct WIDEN
direction, its step reduces independent-evaluation M2, and it beats the
opposite perturbation -- BUT Gate M3-3 overall FAIL: the preregistered
+25pp adaptive-advantage clause delivers 0 pp vs the fixed Always-Widen rule
  - Gate M3-3 = FAIL
      accuracy subcriterion           PASS   (Acc_dir 0.790 >= 0.75)
      adaptive-advantage subcriterion FAIL   (+0 pp < +25 pp required)
    Gates M3-0/1/2/4/5/6 PASS; Strong Gate NOT PASSED
  - 62/64 trials confident WIDEN; active-set direction accuracy 79.0%
  - predicted-step success rate 93.5%; median M2(pred)/M2(base) 0.846
  - median M2(pred)/M2(opposite) 0.721 (strong ordering)
  - frozen identity M2 = sum_j L_j closes at machine precision
    (max rel err 3.9e-16 over 192 arm evaluations): the improvement comes
    from off-target mode leakage dropping (median sum-off-target ratio
    0.846), which dwarfs the small selected-mode rise (+9.9% on a ~1.4%
    loss share)
  - deployable budget VRF median 0.326 (< 1): Strong Gate NOT PASSED
Supported: numerically validated local descent signal that correctly
predicts beneficial widening and beats the opposite perturbation.
NOT supported: any directional advantage over fixed Always-Widen, adaptive
covariance-control value, full-matrix escalation, cost efficiency vs crude MC.
next gate = M3-D sign-diverse scalar covariance-control benchmark;
full-matrix M3-v1 stays blocked (M3-3 advantage clause FAIL + Strong FAIL,
so task Sec.34 preconditions are unmet)
```

## 1. 执行顺序（任务 §33）与完成证据

| 阶段 | 状态 | 证据 |
|---|---|---|
| Step 0 M2 冻结 | ✅ | 标签 `RareTopo-M2-v0`@`0a00f44` 推送；pytest 1113 passed exit 0；`docs/phase_m2/M2_Freeze_Summary.md` |
| M3-0 预注册锁 | ✅ commit `be51c57` | 任务文档落盘 + 双配置 json（§36 全常数）+ M1-D hash 交叉验证 |
| M3-1 推导 + FD 门 | ✅ commit `384bd15` | 推导文档九项；理论校验 49/49、符号 100%、rel err 1.064e-3 ≤ 5e-3 |
| M3-2 估计器 + sanity | ✅ commit `098fbc1` | S1/S2/S3 全过（符号/ESS 硬门）；§29 单测 15/15 |
| M3-3/4 Layer A 主格 | ✅ | 64 试验（~28 s）+ Always-Widen/Shrink 对照 + §17 诊断 + 双口径记账 |
| M3-5/6 门数据 + 对照审计 | ✅ | 见 §2/§3（Gate M3-3 整体 FAIL：accuracy 条 PASS、优势条 FAIL 如实判定） |
| M3-7 Layer B | ✅ 64 试验 | 决策 64/64 与 A 层一致（重加权不改变方向结论） |
| M3-8 步长敏感性 | ✅ 64 试验 | 剂量-反应单调（pred/opp 中位 0.864→0.728→0.544） |
| M3-9 门审计 + 图 + 文档 | ✅ 本文档 | `gate_audit.json` + 8 图 + Methodology/Validity Audit/Final Report |

总运行：主格 28 s + B 层 ~1.5 min + 敏感性 ~44 s + 图/审计秒级。全预注册预算（64×20k pilot + 192×100k 评估 + B 层 192×100k + 敏感性 448×100k），**梯度估计零额外 simulator 调用**。

## 2. 有效性（Gate M3-0 — PASS）

- 四个父标签全部未变（H3/M1 对 `M2_Freeze_Summary.md` 记录、M1-D/M2 对预注册配置 frozen HEAD）；M2 标签为当前 HEAD 祖先；
- benchmark hash `be2ef471…` 与归档一致；任务 sha256 溯源一致；
- selection lock：64/64 与归档 M1-D `variance_selector` 记录一致（`selected_modes` 交叉核验，0 mismatch、0 不可得）；
- mean lock 双算偏差恒 0.0；全部 192 臂过冻结合法性检查器（0 失败）；
- Layer A 全部记录 `layer = fixed_weights`；双口径记账 0 缺失（恒 320,000/120,000）；
- 估计器输入路径无最终评估访问权（结构签名 + rng 标签分离测试）。

## 3. 科学 Gate 判定（Layer A，64 配对试验）

### Gate M3-1 — PASS（理论/数值）
详见 Validity Audit §2；一次因"探针落在假设 A3 窗外"的 FAIL 被门捕获、修正测试点后 PASS，定理本身未改动。

### Gate M3-2 — PASS
活跃率 **62/64 = 96.9%**（≥50%）；仅 2 例 `HOLD_LOW_ESS`（ESS_grad<20），0 例 HOLD_INVALID、0 例 HOLD_UNCERTAIN。ESS_grad 中位 189。

### Gate M3-3 — **FAIL（两条款合成判定，按预注册无部分通过）**
```text
Gate M3-3 — FAIL
  accuracy subcriterion           PASS   (active-set Acc_dir = 0.790 >= 0.75)
  adaptive-advantage subcriterion FAIL   (+25pp vs best fixed rule required,
                                           observed +0.0 pp)
    (ALWAYS-WIDEN 0.790 / ALWAYS-SHRINK 0.032)
```
62/64 决策为 WIDEN ⇒ GRADIENT 的活跃集预测与 ALWAYS-WIDEN 逐试验相同 ⇒ **梯度在方向准确率上不提供任何可测增值**（任务 §21 预言成立）。机器判定 `gate_audit.json → gates.M3_3_direction_accuracy.verdict = FAIL`（clause_a=true / clause_b=false），本文档与后续所有文字以该 FAIL 为准；该差异按 §27 如实保留并主导 §5 措辞与最终冻结结论。

### Gate M3-4 — PASS（强）
活跃集内 `M2(pred)<M2(base)` 成功率 **93.5%**（≥75%）；`median M2(pred)/M2(base) = 0.846 ≤ 0.90`。

### Gate M3-5 — PASS（强）
`median M2(pred)/M2(opposite) = 0.721 ≤ 0.85`；配对 CRN 下排序稳健（四分位 [0.565, 0.897]）。

### Gate M3-6 — PASS
8/8 config 的 `median_seed max_{j≠k} L_j(pred)/L_j(base) ≈ 1.000`（固定权重 + CRN 结构下方差质量未向非目标模式再分布）。

### Strong — NOT PASSED
```text
median deployable VRF(gradient path) = 0.326  (> 1 required)
(ALWAYS-WIDEN 路径同值 0.326：决策=动作)
```
独立评估口径下，预算调整 VRF 低于粗 MC 边界——M3 不获成本效率宣称。

### §23 指标清单完备性（summary_tables.json）
```text
selected-mode leakage : median L_k(pred)/L_k(base) = 1.099 (max 1.227, n=62)
off-target leakage    : median trial-max L_j(pred)/L_j(base) = 1.000
                        (global max 1.035)  -> M3-6 PASS, 无灾难性再分布
proposal-level VRF    : recorded per arm (`_arms.*.VRF_proposal`)
deployable budget VRF : recorded per trial (`evaluation.VRF_budget_grad_path`)
gradient sign & CI    : `gradient.g_hat / g_ci_low / g_ci_high`
WIDEN/SHRINK/HOLD 频次: 62 / 0 / 2 (HOLD_LOW_ESS)
方向准确率 / 步长成功率 / pred-base / pred-opposite：见上表
```

### §23.1 冻结恒等式闭合与改进机制：M₂ = Σ_j L_j（freeze-audit 补充）

由**未改动的 raw Layer A records** 重新聚合（`scripts/run_m3_leakage_decomposition.py`；机器可读结果 `results/phase_m3/summary/m2_leakage_decomposition.json`，源 batch sha256 `2ab02882…581f30`）：

- **闭合**：全部 192 个臂评估中 `max |Σ_j L_j − M̂₂| = 2.2e-16`（相对误差 ≤ 3.9e-16），恒等式在机器精度内成立——selected-mode 泄漏比 ~1.099 与 off-target ~1.00 的两个表面矛盾数字本身并不冲突，它们度量的是不同对象（选定模式的 L_k 比率 vs trial-max off-target 比率的 seed 中位）。
- **分解表（active 集 n=62，BASE/PREDICTED 各自聚合四种拓扑模式的中位数泄漏）**：

| mode | median L_base | median L_pred | pred/base |
|---|---:|---:|---:|
| S1（未被任何 trial 选为目标模式） | 0.004033 | 0.004033 | 1.000 |
| S2 | 0.056623 | 0.054211 | 0.974 |
| S3 | 0.034611 | 0.031137 | 0.989 |
| S4 | 0.006469 | 0.006497 | 0.958 |
| **Σ_j L_j（合计）** | **0.178103** | **0.156525** | — |
| direct M̂₂（独立评估） | 0.178103 | 0.156525 | 0.846 |

- **机制（由数据决定，非猜测）**：加宽使**选定缺失模式自身**的泄漏小幅上升（median ratio **1.099**，max 1.227），但使**每个 off-target 模式**的泄漏下降（sum-over-off-target median ratio **0.846**）；由于选定模式仅承载基线方差的很小份额（占总损失的中位 share **1.4%**，且 64 试验中仅 1 例是最大损失模式；绝对增量 +0.00012 vs off-target 绝对减量 −0.0282，净 −0.0288/试验中位），off-target 的下降主导整体 `M2(pred)/M2(base)=0.846`。选定的"missing mode"在方差质量意义上不是主要模式——改进几乎全部来自共享全局混合密度提升给其它模式带来的分母增益。

## 4. §17 M2 诊断（描述性 vs 梯度）

60/64 试验发生 `hdr_isotropic_scale ≪ s²_base=1` 而梯度判定 WIDEN 的显式冲突——**M2 教训在最干净的尺度上复现：top-η HDR 描述性散布指向收窄（0.06–0.3 量级），二阶矩导数指向放宽**，且放宽确实降低 M₂（Gate M3-4/5 全数据）。

## 5. 解释与允许措辞（§26/§35）

```text
FD 有效 | 方向准确 | 预测步降 M2 | 击败反向 | (自适应增值/VRF)
  Yes   |   Yes   |    Yes     |   Strong |  +0pp 且 VRF 0.326<1
→ 解释矩阵第 4/5 行边界：局部下降有效、排序强劲，
  但方向价值不优于固定放宽规则，成本效率未获支持。
```

本阶段**冻结结论**（区分已支持 / 未支持，取代此前单独引用的 §35 variant 措辞——该 variant 措辞以"core gates pass"为前提，而 Gate M3-3 整体 FAIL 使此前提不成立）：

已支持：

```text
gradient derivation / implementation numerically validated
local covariance descent direction supported
predicted widening reduces M2
predicted direction beats opposite perturbation
M2 descriptive HDR covariance != valid control target
```

未支持：

```text
gradient policy beats Always-Widen（Gate M3-3 优势条款 FAIL, +0 pp）
adaptive covariance-control value established
full-matrix extension justified
absolute cost efficiency vs crude MC（Strong 门 VRF 0.326 < 1）
```

> **M3-v0 establishes a numerically validated local second-moment covariance descent signal. On the frozen M1-D benchmark, this signal correctly predicts beneficial widening and outperforms the opposite perturbation, but it provides no measurable directional advantage over the fixed Always-Widen rule because the benchmark is overwhelmingly widening-dominant. Adaptive covariance-control value therefore remains unresolved.**

禁止写：`M3 proves an adaptive covariance controller`、`gradient is universally superior`、`covariance should always widen`、`full matrix control is now validated`。§35 的 primary 与 variant 措辞均在本阶段不可引用。

## 6. Layer B / 敏感性 / 稳健性

- **Layer B**：每臂冻结 SLSQP 重加权后独立评估，决策 64/64 与 A 层一致；活跃集成功率 80.6%、`median M2(pred)/M2(base) = 0.834`、`median M2(pred)/M2(opposite) = 0.722`（与 A 层 0.721 几乎同值——重加权不改变方向结论，也不拯救方向假设失败，符合 §12 设计）。
- **敏感性（解释性）**：主步长 0.20 全网格不变；剂量单调：δ=0.10/0.20/0.40 下 `median pred/base = 0.923/0.846/0.730`、`median pred/opp = 0.864/0.721/0.544`（一步到位的放宽对偏移质量收益更大）。无怪异非线性，不作主判据修订。
- 泄漏、合法性、选择/均值锁在全三层数据中无异常。

## 7. 全量测试证据

- 正式 freeze 口径为完整 `python -m pytest -q`（裸 `pytest` 曾因 sys.path 注入差异误报，不作为回归口径）。**freeze-audit 复跑（2026-08-27）：1128 passed / 0 failed / skipped 0 / deselected 0（collected 即全部 1128 项，含 M3 新增 15 项），exit code 0，331.42 s**——在本次理论假设修正与文字审计之后运行，科学代码与原始结果未触碰。首次全量运行（347.70 s）同口径亦为 1128 passed / exit 0。

## 8. 完成清单（任务 §37）核对

| §37 项 | 证据 |
|---|---|
| M2 冻结（报告/pytest/负结论/标签/推送/摘要） | ✅ 全文已核，见 Step 0 |
| M3 理论（矩阵+各向同性推导/假设审计/平稳性审计/无过度宣称） | ✅ `M3_Covariance_Gradient_Derivation.md` |
| M3 实现（责任估计/分层梯度估计/ESS_grad/分层 bootstrap/WIDEN-SHRINK-HOLD/固定权重层/反事实评估） | ✅ `src/hyptraj/m3/` 四模块 |
| 验证（S1/S2/S3/FD/全量 pytest） | ✅ sanity + theory_checks + 1128 passed |
| 基准（8×8/HOLD-WIDEN-SHRINK-GRADIENT/Layer A/Layer B/敏感性保留） | ✅ 三层批次 JSON |
| 门（M3-0..M3-6/Strong 独立报告） | ✅ `gate_audit.json` + 本文档 §2–3 |

## 9. 限制与后续（§27/§28）

- 62/64 = 96.9% 的活跃率与方向可辨识均受基准几何驱动（方差质量普遍位于单位尺度之外）；不同基准上梯度/固定规则的相对价值需重估（见 M3-D 方向多样性基准）；
- 步长 0.20 未事后调整；若未来研究信任区间/曲率，需新预注册；
- 标量成功不蕴含全矩阵成功；**M3-v1 全矩阵控制被本节明确延后**——先决条件"核心门全过"中 Gate M3-3（整体）与 Strong 门未过，故按 §34 不得进入全矩阵实现；下一阶段为 M3-D 符号多样性标量基准，用于在 widening-dominant 几何之外重新检验自适应价值。
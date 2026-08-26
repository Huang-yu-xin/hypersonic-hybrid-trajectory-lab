# M2 Covariance Legality Audit — 合法性审计报告

> **Scope:** M2 全部 covariance candidate（C0–C4 × Layer A/B × 64 主试验 + λ∈{0.25,0.75} × 64 × Layer B 消融）
> **Evidence:** `results/phase_m2/**`（records 内嵌 Sec.17 投影元数据）＋ `results/phase_m2/summary/gate_audit.json`
> **Status:** 2026-08-27，全部检查完成

---

## 1. 结论一览

| 检查项 | 结果 |
|---|---|
| 冻结合法性常数复用（`LEGALITY_MIN_EIG=0.5`，未重定义） | ✅ `hyptraj.m2.covariance_projection` 逐字 import |
| Σ_base 元数据驱动读出（§13，禁止硬编码） | ✅ 64/64 试验经 `base_covariance_from_frozen_metadata` 证明性重构 `I₂` |
| 每次使用前 symmetrize（§11） | ✅ `symmetrize_matrix` 为 estimator/投影公共入口；单测覆盖 |
| 投影后 frozen legality | ✅ **0 / 704** 变体试验违规 |
| SPD / NaN / Inf | ✅ 0 例非法输入；0 例非有限 Σ_final 进入 policy（进入前 RuntimeError 护栏） |
| 裁剪披露（§17"不得隐藏 raw 不稳定"） | ✅ 低侧裁剪 581/704（82.5%），高侧 0；Frobenius 范数全量入库 |

## 2. 投影统计（全量变体试验，n=704 = 5 方法×64×2层 − C0×128 + λ 消融 192）

- **eigen clip [0.55, 4.00]**：`clipped_low > 0` 占 82.5%（方差区域二阶矩特征值普遍 < 0.55，源于 η-HDR 前缀的空间集中性）；`clipped_high > 0` 占 **0%**（无上溢）。
- **投影幅度**（活跃试验）：‖Σ_proj − Σ_pre‖_F 中位 0.282、最大 0.582。该值**不大但不可忽略**：C4 预矩阵特征值常落入 [0.51, 0.56]，floor 裁剪把它抬到 ≥0.55。
- **机制含义**（审计中性陈述，供 Final Report 引用）：C_η 特征值远小于 1（区域中位 A_C≈7.6，最大 1540），C4 的净效应是把新分量协方差从 I **收窄**到 ≈diag(0.55–0.66) 的量级——这是后续观察到的 M₂ 恶化的几何根源之一，与"裁剪救不回 spread 缺失"一致。

## 3. HOLD（HOLD_BASE_COVARIANCE）清单

- 主试验变体格 held = **172/256（67.2%）**；per-config：c010、c017 100%；c006 87.5%；c007 75%；c000/c001 62.5%；c020 37.5%；c004 12.5%。
- 触发原因分解：**100% 为 `ESS_V_region < 20`**；0 例 `n_region < d+2`；0 例非有限估计。
- HOLD 语义正确性：held 变体 `Σ_final` 与 Σ_base 逐位相等；Layer A CRN 下 held 变体与 C0 的评估输出**逐位一致**（单测 `test_m2_covariance_hold_low_ess`）；C0 自身永不触发 HOLD。
- 记录合规：全部 held 行携带 `hold=True` + 人类可读 `hold_reason`，计入 Gate M2-1 的合法 HOLD 通道，而非 failed trial。

## 4. Estimator 语义合法性（§10 禁令逐条）

- 权重来源：`variance_mass_weights`（1_A·p²/(q_t·rᵢ)，逐样本记录 rᵢ，fixed-stratified pooling）——**raw/unweighted/probability-weight covariance 均未充当 C_η**（代码路径唯一）。
- 无 Bessel correction（§9 明示不做）；ESS 在区域内重归一化计算（§12 公式逐字）。
- 区域成员 = frozen HDR 最小前缀（非分位数）；<2 样本回退语义与冻结实现一致（`eta_used=1.0`）。本批 64 个区域最小样本数 n_region=19，回退 0 次触发。

## 5. Proposal 家族合法性

- 新分量协方差经投影后 min-eig ≥ 0.55 > 0.5（frozen 门限），混合权重恒在单纯形上（SLSQP `floor=0`；0 次求解失败——64×(5B+2λB) 次调用全部 `success=True`）。
- 密度正值性探测（sanity S2）：所有候选 proposal 在 2 万探测点上 `log q` 有限。
- 逐分量 `min_eig(Σ_j − I/2)` 元数据按冻结纪律随 proposal 记录。

## 6. 概率一致性（§29 双腿，详见 Methodology §8）

- **paired-C0 判定腿**：所有 method×config×layer 的 median|t_pair| ≤ **0.41**（阈值 4）→ 无偏置证据，0 例 flag；
- vs-ref 诊断腿：含 C0 在内全方法一致膨胀（中位 6.6–29.5）→ 归因于 P_ref 分母误差（参考文献 MC 交叉偏差 ≤5.3%），按声明仅作诊断，不构成 INVALID；
- 结论：**没有任何协方差方法以"有偏但低 M₂"的方式制造伪收益**——所有 M₂ 变动均来自无偏估计器的真方差结构变化。

## 7. 审计留痕

- 逐 trial 投影元数据位于 `results/phase_m2/*/*.json` 每条 record 的 `covariance` 块（eig_pre/post、clipped_low/high、frobenius、legality_passed、min_eig_final、hold、hold_reason）。
- 汇总判定：`results/phase_m2/summary/gate_audit.json`（`gates.M2_0_validity` 等）。
- 再现命令：
  ```bash
  python scripts/run_m2_sanity.py
  python scripts/run_m2_covariance_experiments.py --stage main_plus_lambda
  python scripts/run_m2_gate_audit.py --pytest-line "<pytest tail>"
  python scripts/run_m2_figures.py
  ```

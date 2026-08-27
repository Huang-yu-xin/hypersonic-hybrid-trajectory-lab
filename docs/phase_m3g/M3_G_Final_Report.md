# M3-G Final Report — Gain-Aware HOLD Decision

> **Stage:** M3-G v0 ｜ **Status:** SEALED EVALUATION COMPLETE — **FREEZE AUDIT VERDICT: NOT FREEZE READY**
> **Authoritative preregistration:** `docs/phase_m3g/M3_G_Gain_Aware_HOLD_Decision_Task.md` @ commit `9720456`
> **Executed policy:** GA2, ρ = 0.0025（冻结提交 `48fe50b`，其后未变）
> **Parent tags:** `RareTopo-M3-v0 @ 32b2856…`、`RareTopo-M3-D-v0 @ 7bd58c5…`（未变）
> **协议偏差审计:** `M3_G_Protocol_Deviation_Audit.md`（Deviation A 实质、Deviation B 在选定 rho 下无害）
> **Sealed runs:** 192 配对试次（24 态 × 8 种子）；重放奇偶校验 192/192 位一致

---

## 0. 执行摘要（必读）

对已执行（评估-M2 操作化）策略，权威预注册门下五门 PASS、一门 FAIL（M3G-3 HOLD 恢复）；但 **freeze-audit 的 exact-proxy 标定重放（预注册原义 agent 代理：pilot M2_hat 分母 + 逐 replicate 传播）选择了不同策略（GA1-0.02）**，封闭策略 GA2-0.0025 下 9/192 动作分歧——**操作化替代（Deviation A）实质改变标定选择与结论**。因此：

> **M3-G-v0 = NOT FREEZE READY**（作为预注册一阶增益门的科学检验未成立；已执行批次的描述性结果如实保留，不作冻结、不重跑、不掩盖）。

## 1. Table A — Authoritative preregistered gates（commit `9720456` 原阈值）

| 门 | 预注册定义 / 阈值 | 已执行策略实测 | 判定 |
|---|---|---|---|
| M3G-0 有效性 | 双父 tag 验证；任务先提交；无基准突变（freeze sha `b613f45d…`）；无 oracle 泄漏结构测试；全量 pytest 通过 | 全项满足 | **PASS** |
| M3G-1 基线奇偶 | 重放基线行集与冻结 M3-D layer_a 记录逐位相等 | 192/192 单元，0 失配 | **PASS** |
| M3G-2 非回归 | Acc3_gain ≥ 0.75 且 WIDEN ≥ 0.90 且 SHRINK ≥ 0.90 | 0.7604；1.000；1.000 | **PASS** |
| M3G-3 HOLD 恢复 | HOLD recall ≥ 0.50 且 act-but-indifferent 相对下降 ≥ −30% | 0.28125（<0.50）；48→46（−4.2%，>−30%） | **FAIL** |
| M3G-4 价值方向 | R_fixed(GA) ≤ R_fixed(baseline CI-sign)（同一聚合） | 1.0000 ≤ 1.0000 | **PASS** |
| M3G-5 near-oracle | 中位 R_M2 ≤ 0.05 | 0.0000 | **PASS** |
| Strong（诊断） | deployable 会计中位 VRF_budget > 1；**不代表优越性** | 1.0304 | **PASS（诊断）** |

解释分支（任务文档 Sec. 6）：M3G-2..5 未全过（M3G-3 FAIL）→ 非分支 A；HOLD 未恢复且类别未退化 → 非分支 B；**分支 C：一阶增益信号未恢复任何实质性 HOLD 行为，标量一阶门策略就此关闭**。另见 §5 偏差审计裁决（NOT FREEZE READY 叠加于分支 C 之上）。

## 2. Table B — Secondary / Strengthened Audit Criteria（非原始预注册官方门）

以下为执行任务（handoff）中的更严格指标，仅作强化审计参考，**明确不属于 commit `9720456` 的原始预注册门**：

| 强化准则 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| 方向保持 | W/S recall ≥ 0.90（硬） | 1.000 / 1.000 | PASS |
| HOLD 强恢复 | HOLD ≥ 0.70 且 ≥ +30pp | 0.28125（+3.125pp） | FAIL |
| 均衡质量 | 均衡精度 ≥ 0.80 且 macro-F1 ≥ 0.80 | 0.7604 / 0.7117 | FAIL |
| M2 非劣性 | 中位 M2(M3G)/M2(M3D) ≤ 1.00（优选 ≤ 0.98） | 1.0000（优选未达） | PASS（硬）/ 优选未达 |
| 自适应价值 | 中位商 ≤ 0.95 且 ≥ 16/24 态胜出 | 1.0000；9/24 | FAIL |

## 3. 分类性能（已执行策略，192 试次池化，in-sample）

| 指标 | 冻结 M3-D | M3-G（执行策略） | Δ |
|---|---|---|---|
| Acc3 | 0.7500 | 0.7604 | +0.0104 |
| WIDEN recall | 1.000 | 1.000 | 0 |
| SHRINK recall | 1.000 | 1.000 | 0 |
| HOLD recall | 0.2500 | 0.2813 | +0.0313 |
| 均衡精度 | 0.7500 | 0.7604 | +0.0104 |
| macro-F1 | 0.6948 | 0.7117 | +0.0169 |

混淆矩阵（oracle × 预测）：

```text
M3-D:                      M3-G:
        WIDEN SHRINK HOLD          WIDEN SHRINK HOLD
WIDEN     64     0     0      WIDEN     64     0     0
SHRINK     0    64     0      SHRINK     0    64     0
HOLD      22    26    16      HOLD      20    26    18
```

**独立性披露（强制）**：标定与密封重放评估共用同一冻结 (state, seed) 单元（24×8），因此上述提升为 **in-sample calibrated performance**，**不建立任何 out-of-sample 泛化**。Acc3 增量配对 bootstrap 区间（n=10,000，种子 [20260827]）定名为 **descriptive paired bootstrap interval after policy selection**：均值 +0.0104，95% 区间 [0.0000, 0.0260]（含 0，不具独立验证含义）。

## 4. Strong VRF 措辞（修正后）

```text
M3-G retained the M3-D crossing of the crude-MC budget-efficiency boundary.
```

中位 deployable VRF_budget = **1.0304**，与冻结 M3-D 同值（1.0304，仅 2/176 动作变更且 VRF 中位数不变）。**禁止**：M3-G newly achieved cost efficiency；M3-G is adaptively superior because VRF>1。

## 5. Freeze-audit 裁决（NOT FREEZE READY）

`M3_G_Protocol_Deviation_Audit.md` 全文记录，核心事实：

```text
exact-proxy 标定重放（原义代理：pilot M2_hat + 逐 replicate CI）
  选择 (GA1, 0.02)  ≠  冻结选择 (GA2, 0.0025)
封闭策略 GA2-0.0025 逐 trial 动作分歧：9/192（5×HOLD/SHRINK, 4×HOLD/WIDEN）
因素归因：Deviation A（M2 分母）独家 9/9；Deviation B（CI 传播）0/192
原义网格下 GA1-0.02 样本内 Acc3=1.000（HOLD recall 1.000，48 个过激动作全部正确折叠）
```

即：**分母估计器（pilot M2_hat vs 评估 M2，极端相对差 ~215×）的决定性选择，使同一预注册公式产生完全相反的标定结论**。已执行批次作为「评估-M2 操作化策略」的描述性研究成立（有效性/位一致/泄漏事实不变），但作为对预注册一阶增益门的检验**不成立**；**由此撤销原报告中「结论对操作化替代稳健」的表述**。

## 6. 核心负结果（如实保留，不弱化）

```text
HOLD recall 0.250 → 0.281（约 +3.1pp）
W/S recall 1.00 / 1.00（已执行策略下方向完整保持）
M2 严格非劣（中位比 1.0000）
adaptive-value improvement unsupported
```

已执行策略的机制诊断：2/176（1.14%）W/S 折叠为 HOLD_GAIN（100% 正确，false-HOLD=0）；act-but-indifferent 48→46。

## 7. 权威结论

> **M3-G-v0 作为一种以「评估-M2」操作化执行的增益门策略：保留冻结方向控制器、正确抑制少量有限步无差异动作、M2 严格非劣；但一阶增益门控在已执行形式下仅恢复一小部分 HOLD 行为、无可测自适应价值提升。**
> **同时，协议偏差审计判定该执行未实现预注册原义：在预注册原义代理下标定选择不同（GA1-0.02）且封闭策略存在 9/192 动作分歧，因此本结论不构成对预注册增益门的有约束力检验。M3-G-v0 = NOT FREEZE READY。**

修正方向（本阶段不执行）：预注册实现必须直接使用 pilot M2_hat 与逐 replicate 传播（或先行修改预注册文档明确分母估计器并持久化对应标定量），随后重新走完整预注册周期。

## 8. 禁止声明清单（逐字遵守）

❌ 全局最优性；❌ 全矩阵控制；❌ 跨基准迁移；❌「梯度被证明」；❌ 阈值事后调参叙事；❌ Strong VRF>1 作为自适应优越性/新增成本效率；❌ 以 in-sample 提升宣称泛化；❌ 将 Table B 称为原始预注册门。
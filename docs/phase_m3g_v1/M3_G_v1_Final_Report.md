# M3-G-v1 Final Report — Exact-Proxy Recovery (Confirmatory)

> **Stage:** M3-G-v1 ｜ **Status:** CONFIRMATORY VALIDATION COMPLETE
> **Prereg:** commit `55fb5ec` ｜ **Candidate:** GA1 / rho=0.02 / pilot M2_hat（冻结于科学前）
> **Seeds:** [3031..3038]（unseen，与 discovery 零重叠） ｜ **Trials:** 192（24 态 × 8 种子）
> **泛化域:** out-of-sample over Monte-Carlo / pilot randomness only（同一 24 proposal states 复用；无 state-level 泛化声明）

---

## 1. 官方门控判决（确认性）

| 门 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| V1-0 validity | 全项 | 全项满足（prereg 先于科学、种子不相交、基准哈希不变、pilot-M2-only、无泄漏、奇偶 PASS、192 完整） | **PASS** |
| V1-1 direction | W/S recall ≥ 0.90 | **0.9531 / 1.0000** | **PASS** |
| V1-2 hold recovery（主） | HOLD ≥ 0.70 且对同批新种子 M3-D ≥ +30pp | **1.0000**（M3-D 0.2344；**+76.56pp**） | **PASS** |
| V1-3 balanced | 均衡精度/macro-F1 ≥ 0.80 | **0.9844 / 0.9844** | **PASS** |
| V1-4 M2 非劣（硬） | 中位 M2(v1)/M2(M3D) ≤ 1.00 | **1.0000**（优选 0.98 未达，单独报告） | **PASS** |
| V1-5 adaptive value | 中位商 ≤ 0.95 且 ≥16/24 态 | 1.0000；**10 胜 / 8 负 / 6 平** | **FAIL** |
| Strong（诊断） | 中位 deployable VRF > 1 | 1.0304 | **PASS（仅成本效率）** |

## 2. 分类性能（192 试次，新种子）

| 指标 | M3-D baseline（同种子重评） | M3-G-v1 GA1/0.02 | Δ |
|---|---|---|---|
| Acc3 | 0.7292 | **0.9844** | +0.2552 |
| WIDEN recall | 0.9531 | 0.9531 | 0 |
| SHRINK recall | 1.0000 | 1.0000 | 0 |
| HOLD recall | 0.2344 | **1.0000** | +0.7656 |
| 均衡精度 | 0.7292 | 0.9844 | +0.2552 |
| macro-F1 | 0.6740 | 0.9844 | +0.3104 |

混淆矩阵（oracle × 预测）：

```text
M3-D baseline:                    M3-G-v1:
        WIDEN SHRINK HOLD                WIDEN SHRINK HOLD
WIDEN     61     0     3        WIDEN     61     0     3
SHRINK     0    64     0        SHRINK     0    64     0
HOLD      21    28    15        HOLD       0     0    64
```

## 3. 动作价值

| 指标 | 值 |
|---|---|
| 中位 M2(v1)/M2(M3D)（池化 = 层级） | 1.0000（硬门 PASS；优选 ≤0.98 未达） |
| 最优固定规则（同种子） | ALWAYS_WIDEN（0.05922 < ALWAYS_HOLD 0.05951 < ALWAYS_SHRINK 0.06165） |
| 中位 M2(v1)/M2(best fixed) | 1.0000（需 ≤ 0.95 → **FAIL**） |
| 逐态种子中位胜场 vs best fixed | 10 / 24（需 ≥ 16） |
| 中位后悔 R_M2 vs oracle | 0.0000 |
| Strong VRF_budget（deployable） | 1.0304 > 1（成本效率；不构成优越性，且不声称新增穿越） |

## 4. 门控机制诊断（确认性）

- **49/176 激活试次折叠为 HOLD_GAIN，正确率 100%**（全部为 HOLD 类 oracle）；act-but-indifferent 基本清零（HOLD 类 64 试次全 HOLD）。
- **false-HOLD：WIDEN 上 3/64（0.047），SHRINK 上 0**——方向保持硬门仍过（0.953 ≥ 0.90），3 个 WIDEN 类试次的折叠是确认性数据上与 discovery 样本（W 1.0）的唯一差异，如实报告。
- discovery 候选 GA1-0.02（in-sample Acc3 1.0 / HOLD 1.0）在未见种子上**复现**：HOLD recall 1.0、整体 Acc3 0.9844（差异来自上述 3 个 WIDEN 假折叠）。

## 5. 权威结论（claim boundary，逐字）

> **Exact first-order gain gating generalizes HOLD recovery across unseen Monte-Carlo trials on the frozen proposal states, but adaptive superiority over the best fixed action remains unsupported.**

（V1-1..V1-4 PASS + V1-5 FAIL → 采用 Sec.26 第二条 claim 文本。）

补充如实报告：
- M2 严格非劣（中位 1.0000）而非「改善」；V1-5 中位商 1.0000 与 10/24 胜场表明：在 tau 无差异带内，门将 M2 对齐到 best-fixed 的中位水平，但未形成系统性超越。
- Strong VRF_budget = 1.0304 仅支持「本冻结合成基准、匹配预算下的成本效率」；与 M3-D 同值，不声称 v1 新增穿越（v0 审计措辞沿用）。

## 6. 禁止声明（逐字遵守）

❌ out-of-sample proposal-state 泛化；❌ 跨配置泛化；❌ 全矩阵有效性；❌ 全局最优性；❌ 以 VRF>1 或 V1-4 非劣性表述自适应优越性；❌ 阈值/种子事后调参叙事。

## 7. 决策（预注册 Sec. 28）

- v1 HOLD 恢复**强复现**（0.234 → 1.0，+76.6pp，unseen seeds）→ 继续标量线，下一步评估自适应价值声明（自适应优越性仍须在强度更高的值域条件下建立——例如与 best-fixed 的逐态胜场与中位商，或新预注册的值域假设）。
- M3-Q（曲率感知有限步动作价值）**不自动启动**；其启动以 v1 结论封存为先决条件。本阶段不创建任何 tag（任务未要求；v0/v1 均保持不可变记录）。

## 8. 单行状态

```text
M3-G-v1 confirmatory validation COMPLETE: HOLD recovery replicates on unseen
seeds (V1-2 PASS), direction preserved (V1-1 PASS), M2 noninferior (V1-4
PASS), adaptive superiority UNSUPPORTED (V1-5 FAIL); M3-Q not started
```
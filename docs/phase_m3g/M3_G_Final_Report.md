# M3-G Final Report — Gain-Aware HOLD Decision

> **Stage:** M3-G v0 ｜ **Status:** SEALED EVALUATION COMPLETE — gate audit finalized
> **Locked policy:** GA2, ρ = 0.0025（冻结提交 `48fe50b`，此后不可变）
> **Parent tags:** `RareTopo-M3-v0 @ 32b2856…`、`RareTopo-M3-D-v0 @ 7bd58c5…` ｜ **Benchmark freeze:** `b613f45d…`
> **Sealed runs:** 192 配对试次（24 态 × 8 种子）；重放奇偶校验 192/192 位一致

---

## 1. 官方门控判决

| 门 | 阈值（预注册） | M3-G 实测 | 判决 |
|---|---|---|---|
| M3G-0 有效性 | 全项 | 全项满足 | **PASS** |
| M3G-1 方向保持 | W/S recall ≥ 0.90 | 1.000 / 1.000 | **PASS** |
| M3G-2 HOLD 恢复 | HOLD recall ≥ 0.70 且 ≥ +30pp | 0.28125（+3.125pp） | **FAIL** |
| M3G-3 均衡质量 | 均衡精度 ≥ 0.80 且 macro-F1 ≥ 0.80 | 0.7604 / 0.7117 | **FAIL** |
| M3G-4 M2 非劣性 | 中位 M2(M3G)/M2(M3D) ≤ 1.00 | 1.0000（优选 0.98 未达） | **PASS** |
| M3G-5 自适应价值 | 中位商 ≤ 0.95 且 ≥ 16/24 态胜出 | 1.0000；9 胜 / 5 负 / 10 平 | **FAIL** |
| STRONG（预算 VRF） | 中位 deployable VRF > 1 | 1.0304 | **PASS（不作优势表述）** |

## 2. 分类性能（192 试次池化）

| 指标 | 冻结 M3-D | M3-G (GA2, 0.0025) | Δ |
|---|---|---|---|
| Acc3 | 0.7500 | 0.7604 | +0.0104（配对 bootstrap 95% CI [0.0000, 0.0260]） |
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

## 3. 动作价值

| 指标 | 值 |
|---|---|
| 中位 M2(M3G) / M2(M3D)（池化 = 层级聚合） | 1.0000（门 PASS：非劣；优选 ≤0.98 未达成） |
| 最优固定规则（层级聚合） | ALWAYS_WIDEN（0.05991 < ALWAYS_HOLD 0.06081 < ALWAYS_SHRINK 0.06224） |
| 中位 M2(M3G) / M2(best fixed) | 1.0000（需 ≤ 0.95 → FAIL） |
| 逐态种子中位胜场 vs best fixed | 9 / 24（需 ≥ 16） |
| 中位后悔 R_M2 vs oracle | 0.0000（near-oracle 交叉引用：≤ 0.05 ✓） |
| R_fixed(GA) vs R_fixed(baseline) | 1.0000 vs 1.0000（value-direction ✓：不劣于） |
| STRONG VRF_budget（deployable） | 1.0304 > 1（仅成本效率，非优越性） |

## 4. 门控机制诊断

- 原始激活动作 176 个中 **2 个（1.14%）被 HOLD_GAIN 折叠**；这 2 个全部正确（oracle 类 = HOLD，正确率 100%）；**false-HOLD 率在 WIDEN 与 SHRINK 上均为 0**。
- act-but-indifferent（HOLD 类上仍执行 W/S）：48 → 46（−4.2%；需 −30%）。
- 折叠试次均为 HOLD 类 s2=2.5 状态上的「自信 WIDEN」：点估计幅度增益 0.071/0.096 很大，但保守 CI 上端仅 −0.0011/−0.0014 ∈ 无差异带 → GA2 正确拦下；其余 46 个过激试次的保守端大于带阈值 → 未拦。
- **GA1 机制性失效**：本基准上所有冻结激活决策的 \|Δ_rel\| 远大于 0.02（量级 0.1–45），纯幅度代理在全部四档 rho 下与基线完全同值（零转换）——幅度信号对该基准的动作无差异剖面无区分力。
- ρ 灵敏度平坦：四档 GA2 行完全相同（无试次保守端落在 (0.0025, 0.02) 区间），选择由预注册 tie-break（更小 ρ）确定。
- 标定-在线保真度：176/176 激活试次门决策一致（评估臂 M2 vs pilot M2_hat 归一化互替检验）；GA2 线性传播 vs 真逐 replicate CI：0/192 决策分歧。

## 5. 负结果判定（预注册分支）

M3-G v0 命中执行任务 **Case B**：

```text
W/S 保持（M3G-1 PASS）且值非劣（M3G-4 PASS），
但 HOLD recall 仍差（M3G-2 FAIL，+3.1pp 远低于 +30pp 要求）
→ 一阶增益幅度（含保守 CI 变体）不足以解决有限步动作无差异问题。
```

任务文档分支图对应 **Branch C**（nothing recovers / scalar policy closed as-is）：动作价值必须来自不同信号（曲率 / 二阶量 / 其他动作价值估计器）；标量一阶增益门策略就此关闭。

## 6. 权威结论（claim boundary，逐字）

> **在密封的 M3-D 符号多样基准上，预注册的增益感知 HOLD 门（GA2，ρ=0.0025）在零方向性能损失（W/S recall 保持 1.00）与严格 M2 非劣（中位比 1.0000）的前提下将 2/176 个过激有限步动作转为 HOLD_GAIN（全部正确），但 HOLD recall 仅从 0.250 提升到 0.281（+3.1pp），远低于预注册的 0.70/+30pp 恢复门；**一阶增益门控不足以恢复动作无差异行为**，自适应优越性未获支持。**

补充如实报告：
- 分类改善不具统计显著性（配对 95% CI 含 0：[0.0000, 0.0260]）。
- Strong VRF_budget = 1.0304 > 1 表明在冻结合成基准与匹配预算下实现成本效率，**不构成任何适应性/优越性声明**（M3-D 教训逐字执行）。

## 7. 禁止声明清单（逐字遵守）

- ❌ 全局最优性；❌ 全矩阵控制；❌ 跨基准迁移；❌「梯度被证明」；❌ 阈值事后调参叙事；❌ Strong VRF>1 作为自适应优越性。

## 8. 后续（仅允许预注册路径）

- 若继续：动作价值信号必须换源（如曲率/二阶有限步代理、或逐步动作价值估计），需新预注册文档（M3_G_PREREG_AMENDMENT 或新阶段）后方可运行；v0 阈值与结论如实封存。
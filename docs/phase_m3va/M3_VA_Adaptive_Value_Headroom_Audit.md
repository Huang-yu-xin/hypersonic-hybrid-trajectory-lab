# M3-VA — Adaptive-Value Headroom Audit

> **Stage:** M3-VA（纯分析，只读） ｜ **Date:** 2026-08-27
> **数据源（只读）:** `results/phase_m3g_v1/layer_a/m3g_v1_confirmatory_v1.json`（192 试次，seeds 3031..3038）、`results/phase_m3d/layer_a/m3d_layer_a_v1.json`（supplementary，seeds 2026..2033）
> **机器可读镜像:** `results/phase_m3va/summary/m3va_headroom_audit.json`
> **裁决:** **A — benchmark adaptive headroom 不足；优先重设计 benchmark**
> **M3-G-v1 现有 claim 与全部既有结果不变（本审计未修改任何已有文件）**

---

## 0. 防火墙声明

```text
new simulator scientific calls = 0
controller changed? NO    benchmark changed? NO    rho changed? NO
existing results modified? NO    v1 claim unchanged? YES
```

本审计只对存储的臂评估 M2 做配对算术与聚合（试次单元 (state, seed)；逐态 8 种子中位数；全局 24 态中位数），另含一个只读算术反事实（无门致 false-HOLD 时重算 V1-5 聚合）。

## 1. Oracle vs Globally Best Fixed Rule

**Best fixed（同种子确认集，预注册聚合）= ALWAYS_WIDEN**（全局中位数 0.059225；ALWAYS_HOLD 0.059506 极其接近；ALWAYS_SHRINK 0.061646）。

| 对照 | median_state[median_seed M2(·)/M2(rule)] | wins / losses / ties (24 态) |
|---|---|---|
| Oracle vs ALWAYS_WIDEN | **1.0000** | **10 / 6 / 8** |
| Oracle vs ALWAYS_SHRINK | 0.9343 | 15 / 1 / 8 |
| Oracle vs ALWAYS_HOLD | 0.9722 | 15 / 1 / 8 |
| Oracle vs v1（参考） | 1.0000 | 2 / 0 / 22 |

**分 class（vs ALWAYS_WIDEN）：**

| class | ratio | wins / losses / ties | 解读 |
|---|---|---|---|
| WIDEN | 1.0000 | 0 / 0 / 8 | Oracle 的动作为 widen 臂 = AW 同臂，构造性全平 |
| SHRINK | **0.9130** | 8 / 0 / 0 | 唯一存在真实 headroom 的类（≈ −8.7%） |
| HOLD | **1.0372** | 2 / 6 / 0 | 试次级评估下 Oracle 的 base 臂在 6/8 态比 AW 的 widen 臂**更差** |

**Oracle 自己能否过 V1-5？→ 不能（双条件均败）：**

```text
ratio = 1.0000 > 0.95      wins = 10 < 16
```

且在**每个**固定规则定义下均失败：vs AW ratio>0.95；vs AS/AH wins=15<16（WIDEN 类 8 个构造性平局使任何 fixed rule 都拿不到 ≥16 胜）。**discovery 种子集（supplementary）复现同一结构**：Oracle vs AW ratio 1.0000、9 胜/7 负/8 平 → 亦失败。结论为 benchmark 级（与种子集无关）。

## 2. v1 相对 M3-D 的值分解（dM2 = M2(M3D) − M2(v1)，192 试次）

| 组 | n | dM2 总和 | dM2 中位数/均值 | 说明 |
|---|---|---|---|---|
| corrected HOLD | 49 | **+0.08838** | +0.0018 / +0.0018 | 全部收益来源（均为 HOLD 类 oracle；v1 持基臂优于 M3-D 的动作臂） |
| false HOLD on WIDEN | 3 | **0.0000** | 0 | 3 个均为冻结方向层继承的 passthrough（HOLD_UNCERTAIN/LOW_ESS），**门致 false-HOLD = 0** |
| false HOLD on SHRINK | 0 | 0 | — | — |
| unchanged correct WIDEN | 61 | 0.0000 | 0 | 同臂同行，完全相等 |
| unchanged correct SHRINK | 64 | 0.0000 | 0 | 同臂同行，完全相等 |
| other unchanged | 15 | 0.0000 | 0 | passthrough HOLD |
| **overall** | 192 | **+0.08838**（sum 闭合 ✓） | 0.0000 / +0.00046 | 143/192 试次 dM2≡0 |

**归因**：总收益 100% 来自 corrected HOLD（+0.0884）；总损失 0（无门致 false-HOLD、无其他负贡献）。v1 对 M3-D 在**求和**意义上严格不劣、略优；但 16/24 态逐位全平（同臂），中位比值恰为 1.0000。

## 3. 四个专项问题的量化回答

**Q1：HOLD accuracy 0.234→1.0，为什么整体 M2 几乎不变？**
(i) 全部分类收益都落在 **tau=1% 无差异带内**：corrected-hold 试次的每试次边际 (M2(动作臂)−M2(基臂))/M2(基臂) 均值 +0.36%、中位 +0.92%，P95 +9.5%、最大 +16%——对 M2 的贡献是**带内噪声级**，49 试次合计仅 +0.088（约每试次 M2 的 2–3%）。(ii) 聚合结构：16/24 态（W/S 类）v1 与 M3-D 映射到**同一臂、同一 CRN**，比值恰为 1.0000 的硬平局把全局中位数钉在 1.0000；只有 8 个 HOLD 类态的微小非平局在动。(iii) M3-D 在 HOLD 类上的动作臂平均只比基臂差 ≈0.4–0.9%，且符号正负交错（±≤16% 的 realized straddle），v1 的「全部正确折叠」同时拿走了「折叠了好的动作」的代价——净收益为正但小于中位数分辨率。

**Q2：corrected HOLD 的 action-value margin 本来就小？**
**是，结构性地。** Oracle 仅在 ±Δθ 两步相对基臂改善均 ≤1%（参考预算 500k）时才标 HOLD；而 100k 试次级 CRN 评估的 realized 效果在 ±3–5% 间跨带（最大 16%）。所以 HOLD 类上「动作与否」的 M2 差异天生在 ~1% 带内 ±跨带噪声——分类收益（recall +76.6pp）与值收益（+0.36%/试次）数量级不匹配，这正是「direction/classification 成功 ≠ action-value 成功」的机制来源。

**Q3：少量 false-HOLD 是否抵消收益？**
**本数据集中没有。** 3 个 WIDEN 类假 HOLD 全部是冻结方向层（CI 不确定性/低 ESS）的继承行为，**gate-caused false-HOLD = 0**；相对 M3-D 的 dM2 精确为 0。反事实「v1 无门致 false-HOLD」（该操作本身无效果）重算 V1-5 仍失败（ratio 1.0000，10 胜）→ 排除裁决 C。

**Q4：BestFixed 是否已经接近 Oracle？**
**在聚合中位数上完全齐平（ratio Oracle/bf = 1.0000，反向 1.0000）**：Oracle 在 8 个 WIDEN 态与 AW 构造性同臂（平），在 8 个 SHRINK 态有 −8.7% 真实优势，但在 6/8 个 HOLD 态**输给 AW**（+3.7% 劣势）。Oracle vs v1 的逐态对照：22/24 平局。即：该基准上 oracle-动作与全局最优固定动作在 M2 值域的分辨率内几乎不可区分。

## 4. 裁决：A

```text
Oracle 自己过不了 V1-5（ratio 1.0000 > 0.95，wins 10 < 16；
  每个固定规则定义下均失败；双种子集一致）
=> benchmark adaptive headroom 不足 -> 优先重设计 benchmark
```

结构性根因（供 benchmark 重设计参考）：**tau=1% 的动作无差异标签（参考预算判定）与 100k 试次级 M2 评估存在 ±3–5%（最大 16%）的 realized straddle**，使 HOLD 标签在试次级并非 M2 最优——Oracle 自己在 6/8 HOLD 态输给 ALWAYS_WIDEN、对 WIDEN 类构造性全平，导致无论哪种对照都无法满足「ratio ≤0.95 且 ≥16/24 胜」。分类层面（action-indifference）与值层面（M2 ratio）在本基准上系统性不一致。

## 5. 边界与后续建议

- M3-G-v1 的 claim 维持原样：**HOLD 恢复在未见 Monte-Carlo 试次上复现、方向保持、M2 非劣、自适应优越性未获支持**。
- 本审计不授权任何新科学实验；M3-Q（曲率）**不因本审计自动启动**——v1 值域失败的根因在 benchmark 头寸，而非一阶 vs 二阶建模（裁决 A 优先重设计 benchmark）。
- 重设计方向建议（仅陈述，不实施）：需使 oracle-action 与最优固定动作在试次级 M2 评估下具有超带（>5%）且超-win 阈（≥16/24）的分离，或改用与标签同参考预算的值度规。
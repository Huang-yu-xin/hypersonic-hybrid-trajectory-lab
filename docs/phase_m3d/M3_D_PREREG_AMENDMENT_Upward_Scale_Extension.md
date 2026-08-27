# M3-D Preregistration Amendment 1 — Upward Scale Extension

> **Schema:** `raretopo-m3d-v0` ｜ **Date:** 2026-08-27 ｜ **Type:** benchmark-construction amendment（非 controller 调参）
> **Amends:** `M3_D_Sign_Diverse_Scalar_Covariance_Control_Task.md`（canonical sha256 `f90f8b10…`）+ `configs/phase_m3d/m3d_candidate_state_grid.json`
> **Commit discipline:** 本文件与配置追加块先于任何新 reference characterization 提交（task §10/§42 与本修正案条款 8）

---

## 0. 状态快照（outcome-inspection，提交本修正案时点）

### 0.1 已查看的结果

来自 **已完成的** D1/D2/D3（批次 `m3d_candidate_pool.json` sha256 `50b48ddf…398607`、STOP 记录 `d3_sign_diversity_stop.json` sha256 `02d50eaf…9269e`）：

```text
oracle labels over 56 legal states (N_ref = 500k/arm, CRN, tau=0.01):
  WIDEN                = 43
  REFERENCE_AMBIGUOUS  = 13
  SHRINK               = 0
  HOLD                 = 0
task Sec.10 gate (>=8/8/8 across multiple configs) => FAIL => STOP fired
```

归因（数据驱动）：13 个 ambiguous 态全部位于网格宽端且必需对比全部统计成立——s²=2.00 处加宽仍降 M₂(−1.4%~−4.5%)、收窄仍升(+2.8%~+7.6%)；加宽收益对尺度单调贯穿原网格 [0.55, 2.00]，SHRINK 最优域位于原网格之外。

### 0.2 尚未运行的实验

```text
M3-D online Gradient-vs-fixed-rule trials executed = 0
benchmark freeze documents created                 = 0   (D4 not entered)
Layer B / ablations / replay runs                  = 0
```

D5 及以后的所有阶段从未启动。

## 1. 变更原因（reason）

原预注册 s²∈[0.55, 2.00] 候选网格未能跨越 stationary / SHRINK 区域：在全部 8 个冻结 config 上，整个网格内加宽持续改善 M₂。这使 sign-diverse 基准的构造前提（WIDEN/SHRINK/HOLD 三类各自 ≥8 态）无法满足，属于**基准构造缺陷**而非控制器问题。

## 2. 变更内容（new）

### 2.1 仅向上扩展候选 s² 网格

```text
s2_grid_extension_locked = [2.50, 3.20, 4.00, 5.00, 6.40, 8.00]
有效搜索空间 = 原 s2_grid_locked ∪ 上式
新增候选态上限 = 8 configs × 6 = 48（总池 ≤ 104）
```

只增不减：原 7 个网格值与其 56 个已表征态**保留原样**（不删除、不覆盖、不重算）。

### 2.2 bracket 内 log-space refinement（仅当 HOLD 不足 8 个时）

```text
触发:     同一 config 内出现相邻 WIDEN→SHRINK 标签 bracket 且全局 eligible HOLD < 8
候选生成: s²_mid = sqrt(s²_W * s²_S)   （几何中点，log-space）
范围:     仅同 config、仅相邻异标签对之间；不外推
轮数上限: 2 轮（round 1 中点 → 若仍不足则 round 2 在新 bracket 内再取中点）
禁止:     放宽 HOLD ±3% / margin=0.05 / tau=0.01 任何阈值；任何事后换值
```

refinement 生成的每个候选态同样先过合法性检查器，参考表征协议与主扩展完全一致（N_ref=500k/臂、CRN、tau=0.01、margin≥0.05、HOLD±3%、支持规则 |对比|≥2×配对 SE）。

### 2.3 永久 STOP 条款（hard commitment）

```text
若 扩展(48 态) + ≤2 轮 refinement 后 eligible 标签仍 < 8 WIDEN 或 < 8 SHRINK 或 < 8 HOLD：
  M3-D-v0 永久 STOP——不再扩网格、不再 refinement、不进入在线。
  记录为负结果：「在冻结 M1-D 事件族与 delta_theta=0.20 下，
  proposal-state 尺度轴上不存在满足 8/8/8 的符号多样性。」
```

## 3. 明确不变项（untouched-rerun 承诺）

以下全部**逐字保持不变**：

```text
gradient controller        hyptraj.m3 三模块 + DirectionRule（verbatim reuse）
delta_theta_main           0.20（含 refinement 中点态与所有 arm 构造）
N_ref                      500,000 per arm（CRN batched, 20 batches）
tau                        0.01
direction margin           ≥ 0.05
HOLD neighborhood          ±3%（两扰动臂同时落入才可 HOLD）
ESS_grad threshold         20
seeds                      [2026..2033]（在线；装配锚 2026 不变）
pilot_n / alpha            20,000 / 0.5，rng=[seed,101]
bootstrap                  固定分层 500 复本 rng=[seed,424243], 95% CI 符号规则
全部 gates                 M3D-0..6 + Strong 阈值逐字不动
双口径记账                 scientific 320k / deployable 120k per trial
oracle 隔离                offline 字段永不进入 online API（结构性测试照旧）
```

## 4. 性质声明

这是 **benchmark-construction amendment**：只改变 proposal-state 的搜索空间（把尺度轴向合法 SPD 区域上方延伸），不改控制器的任何公式、阈值或决策逻辑。它与「controller 调参」的区别由本节与 §3 清单共同界定；未来任何触碰 §3 清单的请求不属于本修正案授权范围。

## 5. 工件管理

- 新扩展态的合法性判定与参考表征写入**独立新文件** `results/phase_m3d/reference/m3d_candidate_pool_extension1.json`（及其 refinement 轮次文件 `…_ext_round{1,2}.json`），原始 `m3d_candidate_pool.json` 保持 byte-exact；
- 配置文件 `m3d_candidate_state_grid.json` 仅追加 `amendments` 数组记录本修正案（原键 `s2_grid_locked` 等一律不动）；
- 每步运行前记录既有工件 sha256、运行后复核不变；
- 未来 D4 冻结文件须同时引用两代池文件的哈希。

## 6. 时序承诺核对表

| 项 | 状态 |
|---|---|
| amendment 先于任何新 reference characterization 提交 | 本修正案随本次 commit 落盘 ✅ |
| 原 56 态与 D0–D3 工件不被删除/覆盖/重算 | §5 独立文件 + 哈希指纹机制 ✅ |
| online adaptive runs 保持 0 直至新基准重新冻结 | §0.2 现状 + task §42 纪律 ✅ |

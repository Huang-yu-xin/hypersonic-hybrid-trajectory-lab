# H3-2 C1 Stability Audit

> **Status: COMPLETE — Case A (separation unstable)** (2026-08-21)
> Branch: `feature/phase-h-uncertainty-risk`
> Frozen H3-2 dataset: `tests/data/h3_2_leakage_point_dataset_v1.json` (SHA-256 `29e09cb6...`)
> Audit script: `scripts/run_h3_2_c1_stability_audit.py` (NEW, read-only reuse of frozen pipeline)
> Audit data: `results/phase_h3/c1_audit_multiseed_v1.json` · `c1_audit_convergence_v1.json`
> Related: `docs/phase_h/H3_2_experiment_freeze.md` · `docs/phase_h/h3_2_result_analysis.md`

---

## 1. Motivation

H3-2 freeze 前发现一个需要裁决的问题：

| 运行 | seed 机制 | $\lVert x^{\ast} - x_L \rVert$（C1） |
|---|---|---|
| 旧随机种子（pre-freeze） | `SEED + hash(eid) % 1000`（`hash()` 进程随机化） | **1.136** |
| deterministic crc32（frozen） | `SEED + crc32(eid) % 1000` | **0** |

该变化影响 H3-2 的科学解释（real-system mismatch claim 是否成立），因此对
C1（Sanger B1_N1_side）执行 stability audit。

**Audit 问题**：C1 的 leakage point separation 是真实现象，还是随机采样 /
seed instability 的伪影？

## 2. Experiment Settings

### 2.1 Audit scope

仅检查 **`C1_sanger_b1n1_wide`**。不修改 H3-0 / H3-1 / H3 Theory / H3-2 A / B / C2。
不重新设计方法 —— 审计 harness **逐位复刻** frozen C1 分支（相同 dynamics /
topology / uncertainty / proposal / leakage search / estimator / sample size），
只改变 random seed。

### 2.2 Fixed configuration（与 frozen 一致）

| 字段 | 值 |
|---|---|
| anchor | `B1_N1_side`（Sanger 混合动力学） |
| alpha_factor | 8.0（α = 8·\|β_ref\|） |
| design point | μ = −β_eff·α_dir（ML-B1 frozen 几何） |
| solver | `REF-0.1`，max_time = `DEFAULT_MAX_TIME` |
| N (MC explore / IS) | 128 / 128（convergence 增为 4N=512、16N=2048） |
| leakage candidate search | `point_geometry`：x* = argmin‖x‖，x_L = argmin‖x+μ‖（同一 mode 点集） |
| estimator | `_eval_proposal`（importance + total_leakage + decompose_modes） |

### 2.3 Seeds under test

| label | seed 值 | 说明 |
|---|---|---|
| `seed_old` | 1（legacy proxy） | 旧 hash 种子不可复现（`hash()` 进程随机化即审计缺陷本身），用固定替代种子代表旧风格 |
| `seed_crc32` | 2120 | frozen 确定版种子（`2026 + crc32(eid) % 1000`）—— harness 有效性锚点 |
| `seed_3` | 3 | 独立种子 |
| `seed_4` | 4 | 独立种子 |

### 2.4 Harness validity check（必须先通过）

审计 harness 在 `seed_crc32` 下必须复现 frozen dataset：

| 指标 | frozen dataset | audit harness | 匹配 |
|---|---|---|---|
| M1 VRF | 1.205492 | 1.205492 | ✅ |
| d_L | 0.0 | 0.0 | ✅ |
| ρ_L(x_L) | 2.3016e-2 | 2.3016e-2 | ✅ |
| p_mc | 0.453125 | 0.453125 | ✅ |

（实际运行验证通过后方可信任其它 rows。）

## 3. Multi-seed Results

（实际运行数字；`seed_crc32` 行 = frozen 锚点，已验证复现）

| seed | x* | x_L | d_L | M1 VRF | ρ_L max | n mode points |
|---|---|---|---|---|---|---|
| seed_old (1) | $(-0.44,\ -0.21,\ -0.33,\ 0.06)$ | $(-0.59,\ -0.13,\ -0.07,\ 0.11)$ | **0.3183** | 1.2315 | 2.07e-2 | 129 |
| seed_crc32 (2120) | $(-0.16,\ -0.02,\ -0.30,\ -0.15)$ | 同左（重合） | **0.0000** | 1.2055 | 2.30e-2 | 122 |
| seed_3 (3) | $(0.36,\ -0.56,\ -0.18,\ 0.04)$ | 同左（重合） | **0.0000** | 1.1975 | 1.97e-2 | 120 |
| seed_4 (4) | $(-0.21,\ -0.44,\ -0.14,\ -0.06)$ | 同左（重合） | **0.0000** | 1.2469 | 2.20e-2 | 122 |

**关键观察**：4 个 seed 中 **3 个 d_L = 0，仅 seed_old (seed=1) 出现 0.318**。
旧 pre-freeze 声称的 1.136 未被任何 seed 复现（最大观测 0.318）。

## 4. Convergence Analysis

（N / 4N / 16N 前缀评估，同一种子 crc32 = 2120，同一批 iid 样本的前缀）

| N | x_L | d_L | ‖x_L(N)−x_L(16N)‖ | M1 VRF | n mode points |
|---|---|---|---|---|---|
| 128 | $(-0.06,\ 0.02,\ -0.24,\ 0.33)$ | 0.0000 | 0.2468 | 1.216 | 120 |
| 512 | $(0.13,\ -0.04,\ -0.10,\ 0.35)$ | 0.0000 | 0.0000 | 1.225 | 503 |
| 2048 | $(0.13,\ -0.04,\ -0.10,\ 0.35)$ | **0.4721** | — | 1.211 | 1955 |

**关键观察**：
- x_L 随 N 收敛（N=512 与 16N 相同），但 **d_L 不收敛**：N=128/512 时
  x* 与 x_L 落在同一点（d_L=0），N=2048 时更大样本集暴露了 MPP 与
  leakage point 落在不同样本（d_L=0.47）；
- **d_L 不随 N 单调下降**（排除了纯有限样本 bias 单调趋势 Case C），
  而是先 0 后 0.47 —— 说明 x* 与 x_L 的分离在平坦景观上由样本噪声决定；
- 最大观测 d_L(16N) = 0.472 仍远小于旧声称的 1.136。

## 5. Leakage Landscape Comparison

（每 seed 的 max candidate、top-5 ranking、density gap、candidate location）

| seed | max candidate (z) | ρ_L max | ρ_L 2nd | gap (max/2nd) | ρ_L median |
|---|---|---|---|---|---|
| seed_old (1) | $(-0.59,\ -0.13,\ -0.07,\ 0.11)$，norm 0.620 | 2.07e-2 | 2.05e-2 | 1.011 | 3.96e-3 |
| seed_crc32 (2120) | $(-0.16,\ -0.02,\ -0.30,\ -0.15)$，norm 0.369 | 2.30e-2 | 2.19e-2 | 1.051 | 4.33e-3 |
| seed_3 (3) | $(0.36,\ -0.56,\ -0.18,\ 0.04)$，norm 0.690 | 1.97e-2 | 1.88e-2 | 1.050 | 4.69e-3 |
| seed_4 (4) | $(-0.21,\ -0.44,\ -0.14,\ -0.06)$，norm 0.513 | 2.20e-2 | 1.82e-2 | 1.207 | 4.12e-3 |

**判定 → 情况 B 特征（多峰/平坦 leakage structure）**：
- 最大 leakage candidate **位置跨 seed 大幅漂移**（norm 0.369 → 0.690，
  坐标在不同象限），不同 seed 的 argmax ρ_L 选中不同样本；
- density gap 极小（max/2nd = 1.01~1.21）：**ρ_L 景观在候选区域内近乎平坦**，
  top-5 候选的 ρ_L 相差 < 20% —— argmax 由样本噪声决定；
- 结论：C1 的 leakage landscape 是**宽峰（flat/plateau）**而非尖锐单峰，
  x* 与 x_L 的"分离"只是有限样本下两个 argmin 在平坦区域选中不同样本
  的伪影。

## 6. Scientific Interpretation

**判定：Case A（separation 不稳定）为主，附带 Case B 的 landscape 特征。**

| 证据 | 结果 | 支持 |
|---|---|---|
| §3 multi-seed | d_L ∈ {0, 0, 0, 0.318}（4 seed 中 3 个为 0） | Case A：跨 seed 不稳定 |
| §4 convergence | d_L(N) = {0, 0, 0.472} 不随 N 单调收敛，先 0 后 0.47 | 非 Case C 单调 bias；有限样本噪声 |
| §5 landscape | max candidate 位置漂移（norm 0.37-0.69），gap 1.01-1.21 近平坦 | Case B 特征：flat/plateau 景观 |
| 历史对比 | 旧 1.136 未被任何 seed/N 复现（最大观测 0.472） | 旧值为采样伪影 |

**机理解释**：
1. C1（Sanger B1_N1_side，α=8|β|）的 mode 区域是**近凸宽峰**，ρ_L 在
   $\lVert z \rVert \in [0.37, 0.69]$ 区域内近乎平坦（max/2nd gap < 1.21）；
2. x* = argmin‖x‖ 与 x_L = argmin‖x+μ‖ 在同一有限点集上取两个不同
   目标的最小值 —— 在平坦区域，哪个样本点"胜出"完全由采样位置决定，
   seed 一变或 N 一增就可能翻转（d_L ∈ {0, 0.32, 0.47}）；
3. **旧 1.136 是有限样本 + 不稳定 hash seed 的极端采样组合**，不是
   C1 系统的稳定属性；
4. 与 synthetic curved（Exp B，d_L = 0.775 稳定、ρ_L 峰值尖锐、MPP≠xL
   有解析支撑）形成鲜明对比：**synthetic 的分离是几何真实，real C1 的
   分离是采样伪影**。

**对 H3-2 claim 的影响**：real C1 不支持稳定的 $x^{\ast}\neq x_L$。

## 7. Freeze Recommendation

**C1 separation 不稳定 → 冻结规则（§8 Case A 路径）**：

1. **H3-2 claim 更新**（保留 synthetic、明确 real 限制）：

   保留：
   - Synthetic curved regime（Exp B）：$x^{\ast} \neq x_L$（d_L = 0.775
     稳定，ρ_L 峰值尖锐，有解析支撑）；
   
   明确说明：
   - **Real C1（Sanger B1_N1_side）：未观察到稳定 separation** ——
     d_L 跨 seed ∈ {0, 0.32}、跨 N ∈ {0, 0.47}，landscape 平坦
     （gap 1.01-1.21），旧 1.136 为采样伪影；
   - real-system mismatch claim **不恢复**（Case A 判定）。

2. **后续建议（H3-3）**：真实系统验证 x*≠xL 需要更 rare 配置
   （更小 α）使 mode 边界曲率显著（βκ≫1），或直接使用解析边界
   已知曲率的工况；在平坦景观上不应再以"样本 argmin 距离"作为
   mismatch 证据。

3. **本审计不修改任何 frozen 文件**：仅新增
   `scripts/run_h3_2_c1_stability_audit.py` 与本文档；frozen dataset
   （SHA-256 `29e09cb6...`）与 H3-2 数值保持不变（其 C1 d_L = 0 恰好是
   审计的稳定结论之一）。

## 8. Constraints Compliance

- ✅ 不修改实验参数（仅 seed / N 变化，且 N 变化仅用于 convergence 诊断）
- ✅ 不调整 proposal 使结果更好
- ✅ 不删除异常 seed
- ✅ 不选择有利结果：所有数字来自实际运行
- ✅ 不修改 frozen 文件（审计脚本为新增文件，只读复用 frozen 函数）

# H3-2 Experiment Freeze — FINAL

> **Status: H3-2 = FROZEN** (2026-08-21)
> Branch: `feature/phase-h-uncertainty-risk`
> This record supersedes `docs/phase_h/H3_2_experiment_freeze.md`（初版冻结，不含 C1 audit）
> 论文引用仅允许本文件所列 frozen 结果。

---

## 1. Commits

```
3bfc63f docs: H3-2 核心文档添加 C1 stability audit 交叉引用（claim 不变，frozen 保持）
7d013f6 H3-2 C1 stability audit：4 seeds + N/4N/16N convergence 判定 separation 不稳定（Case A）
49d86a9 docs: 补录 freeze marker commit 65dba42 到冻结报告
65dba42 H3-2 实验冻结（FROZEN）：生成 freeze 报告，添加 FROZEN 状态标记
a03b364 docs: 更新报告 commit 引用为确定版 fa7c476
fa7c476 H3-2 确定版重跑（稳定 crc32 种子 + 增量落盘）
2171795 完成 H3-2 variance-optimal leakage-point 自适应 Geometry-IS
```

- **实验确定版**：`fa7c476`（crc32 稳定种子 + 增量落盘）
- **C1 stability audit**：`7d013f6`
- **audit 文档交叉引用**：`3bfc63f`

## 2. Dataset Hash

| 字段 | 值 |
|---|---|
| Path | `tests/data/h3_2_leakage_point_dataset_v1.json` |
| Schema | `h3-2-leakage-point-dataset-v1` |
| **SHA-256** | **`29e09cb69d0642730e660b84614918cdbb6e4b43c615812b66177aa9fb2c9f4b`** |
| Experiments | 4（A synthetic multi-mode · B synthetic curvature · C1 Sanger B1N1 · C2 Sanger B2N） |
| Seed scheme | `SEED=2026 + zlib.crc32(experiment_id) % 1000`（确定、可复现；禁用内置 `hash()`） |

> 论文如需复现：`./.venv/Scripts/python.exe scripts/run_h3_2_adaptive_geometry_is.py --resume`
> 任何修改 dataset 的操作将使 SHA-256 失配，即偏离冻结状态。

## 3. Final Experiment Numbers (deterministic)

### 3.1 VRF 对比（frozen dataset）

| experiment | P_mc | M1 VRF（$x^{\ast}$） | M2 VRF（$x_k^{\ast}$） | M3[prob] VRF（$x_{L,k}$） | leak reduction | x*–xL 分离 |
|---|---|---|---|---|---|---|
| A synthetic multi-mode | 0.0725 | 0.4631 | 26.041 | 26.125 | 0.0267（97.3%） | S1: 0, S2: 0 |
| **B synthetic curvature** | 0.1127 | 0.0975 | 14.355 | 12.114 | 0.0110（98.9%） | **S2: 0.7751** |
| C1 Sanger B1N1 | 0.4531 | 1.2055 | 1.361 | 1.257 | 0.9121 | SRTI_N1: 0 |
| C2 Sanger B2N | 0.5391 | 1.2314 | 0.758 | 1.519 | 0.8586 | SRTI_N3: 0 |

### 3.2 关键科学数字（B：probability vs variance geometry）

$$
x^{\ast}_{\text{S2}} = (1.23,\ 0.83), \qquad
x_{L,\text{S2}} = (1.77,\ 0.26), \qquad
d(x^{\ast}, x_L) = 0.7751
$$

$$
\rho_L(x_L) = 2.24\times 10^{-1} \;>\; \rho_L(x^{\ast}) = 1.65\times 10^{-1}
$$

（$\rho_L = \varphi^2/q$ 最大值定位在 $x_L$ 附近 —— variance geometry 假设验证）

### 3.3 权重策略（synthetic A/B，M3 内部）

| 策略 | A: VRF | B: VRF |
|---|---|---|
| $\pi \propto P_k$（probability） | **26.1** | **12.1** |
| $\pi \propto L_k$（leak_power1） | 0.47 | 0.16 |
| $\pi \propto \sqrt{P_k L_k}$（p05_l05） | 8.4 | 2.0 |

## 4. C1 Stability Audit Conclusion（Case A）

**裁决：real C1 不支持稳定的 $x^{\ast}\neq x_L$；旧 pre-freeze 报告的 1.136 为 sampling artifact。**

### 4.1 Multi-seed（4 seeds，N=128，配置与 frozen 逐位一致）

| seed | x* | x_L | d_L | M1 VRF | ρ_L max |
|---|---|---|---|---|---|
| seed_old (1) | (−0.44, −0.21, −0.33, 0.06) | (−0.59, −0.13, −0.07, 0.11) | **0.3183** | 1.2315 | 2.07e-2 |
| seed_crc32 (2120) | (−0.16, −0.02, −0.30, −0.15) | 同左（重合） | **0.0000** | 1.2055 | 2.30e-2 |
| seed_3 (3) | (0.36, −0.56, −0.18, 0.04) | 同左（重合） | **0.0000** | 1.1975 | 1.97e-2 |
| seed_4 (4) | (−0.21, −0.44, −0.14, −0.06) | 同左（重合） | **0.0000** | 1.2469 | 2.20e-2 |

→ 4 seed 中 3 个 d_L = 0；旧 1.136 未被任何 seed 复现（最大观测 0.318）。

### 4.2 Convergence（seed 2120，N/4N/16N 前缀评估）

| N | x_L | d_L | ‖x_L(N)−x_L(16N)‖ | M1 VRF |
|---|---|---|---|---|
| 128 | (−0.06, 0.02, −0.24, 0.33) | 0.0000 | 0.2468 | 1.216 |
| 512 | (0.13, −0.04, −0.10, 0.35) | 0.0000 | 0.0000 | 1.225 |
| 2048 | (0.13, −0.04, −0.10, 0.35) | **0.4721** | — | 1.211 |

→ **d_L 不收敛**（0 → 0 → 0.47）：x_L 收敛稳定，但 **x*（MPP）随 N 翻动**
—— 平坦区域内两个 argmin 的样本竞争。最大观测 0.472 仍远小于旧 1.136。

### 4.3 Leakage landscape

| seed | max candidate norm | ρ_L max / 2nd gap |
|---|---|---|
| seed_old (1) | 0.620 | 1.011 |
| seed_crc32 (2120) | 0.369 | 1.051 |
| seed_3 (3) | 0.690 | 1.050 |
| seed_4 (4) | 0.513 | 1.207 |

→ max candidate 位置大幅漂移（norm 0.37–0.69），**density gap 仅 1.01–1.21
（近平坦宽峰）** —— argmax ρ_L 由样本噪声决定。

### 4.4 机理解释

C1（α=8|β|）mode 区域 βκ≈0（无曲率），ρ_L 在 ‖z‖∈[0.37, 0.69] 内平坦；
x* 与 x_L 是**同一有限点集上两个不同 argmin 的样本竞争**，seed/N 一变即翻转。
对比 synthetic B（d_L=0.775 稳定、峰值尖锐、有解析支撑）——
**synthetic 分离是几何真实，real C1 分离是采样伪影**。

## 5. Final Claims (FROZEN)

### Claim（保留）

1. **Synthetic curved regime**（Exp B）中：

$$
x^{\ast} \neq x_L, \qquad d(x^{\ast}, x_L) = 0.7751
$$

且 leakage-point adaptive proposal（M3）在该 leakage-dominated regime 中
降低 variance：M1 VRF 0.098 → M2/M3 VRF 12–26，leakage 削减 98.9%。

2. **C2 real system**（Sanger B2N）中 adaptive proposal 有收益：
   M3[probability] VRF **1.519** 为最优，优于 M1（1.231）与 M2（0.758）。

3. **C1 real system**（Sanger B1N1）：**不支持稳定** $x^{\ast}\neq x_L$；
   旧 1.136 separation 判定为 sampling artifact（Case A，audit `7d013f6`）。

### Claim boundary

**Claim**：
- variance geometry 与 probability geometry 在特定 leakage-dominated regime
  （弯曲边界、βκ≫1）下分离；
- leakage-point proposal 可以恢复部分 Geometry-IS 失效（silent secondary
  mode / 未覆盖 mode 场景）。

**Not claimed**：
- ❌ 所有 hybrid system 都存在 mismatch（real C1/C2 未复现稳定分离）；
- ❌ adaptive proposal 对所有系统均提升（C1 中 M1 即最优）；
- ❌ 已解决高维 general case（d=4 standardized 空间 + Sanger 单/双 mode）。

## 6. Known Limitations

| # | 限制 | 影响 | 后续 |
|---|---|---|---|
| L1 | real C1/C2 α=8\|β\| 事件不 rare（P~0.45–0.54） | real VRF 仅 1.2–1.5，leakage 削减 9–14% | H3-3: 更小 α + 更大 N |
| L2 | real 仅单 transition mode | multi-mode 竞争未在真实系统观测 | H3-3: 更大 α 扫描 |
| L3 | real x_L 由 128 样本估计 | real 几何估计粗糙（audit 已证平坦景观噪声主导） | H3-3: 解析/大样本验证 |
| L4 | 固定 $\Sigma_k = I$（v1 协议） | 单位协方差近似，限制 real 增益 | 后续允许自适应 Σ |
| L5 | $\rho_L$ 在平坦区域区分度低（gap 1.01–1.21） | 有限样本下 argmax 不可靠 | 需要解析边界或 βκ≫1 工况 |
| L6 | C1 旧 hash-seed 运行不可复现 | 1.136 为采样伪影（已裁决） | 已禁用 `hash()`，crc32 稳定 |

## 7. Frozen Deliverables

| 文件 | 状态 |
|---|---|
| `tests/data/h3_2_leakage_point_dataset_v1.json` | **FROZEN**（SHA-256 `29e09cb6...`） |
| `docs/phase_h/h3_2_result_analysis.md` | FROZEN（模板结果报告，含 audit 引用） |
| `docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md` | FROZEN（权威文档，含 audit 引用） |
| `scripts/run_h3_2_adaptive_geometry_is.py` | FROZEN（crc32 seed + 增量落盘 + --resume） |
| `docs/phase_h/H3_2_C1_stability_audit.md` | FROZEN（audit 报告，Case A） |
| `scripts/run_h3_2_c1_stability_audit.py` | FROZEN（audit 脚本，workers≤4 约定） |
| `results/phase_h3/fig[6-9]*.png` | FROZEN（数据来源 = frozen dataset + audit） |
| `docs/phase_h/H3_2_experiment_freeze_final.md` | 本文档（最终冻结记录） |

## 8. Post-Freeze Allowed Operations

**仅允许**：
- Figure 制作（用 frozen dataset 数据重新绘图）
- 论文写作（引用 frozen 结果）
- caption 修改

**禁止**：
- ❌ 修改实验结果 / frozen dataset 数值
- ❌ 重新选择 seed（seed 固定为 crc32 方案）
- ❌ 扩展实验范围（新工况须开新 stage，H3-3+）
- ❌ 修改实验参数 / proposal 方法 / estimator 定义

---

**H3-2 = FROZEN** ✅

```
SHA-256: 29e09cb69d0642730e660b84614918cdbb6e4b43c615812b66177aa9fb2c9f4b
Commits: 3bfc63f → 7d013f6 → 49d86a9 → 65dba42 → a03b364 → fa7c476 → 2171795
Tests:   145 passed
Seeds:   crc32-stable
C1 audit: Case A (separation unstable) — 1.136 = sampling artifact
```

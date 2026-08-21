# H3-2 Experiment Freeze

> **Status: FROZEN** (2026-08-21)
> Branch: `feature/phase-h-uncertainty-risk`
> Freeze commits: `65dba42` (freeze marker) → `a03b364` (header ref) → `fa7c476` (deterministic re-run) → `2171795` (initial H3-2)
> Authoritative doc: `docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md`
> Result analysis report: `docs/phase_h/h3_2_result_analysis.md`
> **C1 stability audit (2026-08-21, post-freeze, `docs/phase_h/H3_2_C1_stability_audit.md`, commit `7d013f6`)**:
> real C1 separation confirmed **unstable (Case A)**; frozen dataset & claims unchanged.

---

## 1. Experiment Version

| 字段 | 值 |
|---|---|
| Stage | H3-2 — Variance-Optimal Leakage-Point Adaptive Geometry-IS |
| Schema version | `h3-2-leakage-point-dataset-v1` |
| Status | **FROZEN** |
| Freeze date | 2026-08-21 (Asia/Shanghai) |
| Generator | `scripts/run_h3_2_adaptive_geometry_is.py` |
| Snapshot input | `tests/data/ml_b1_first_order_geometry_v1.json` (ML-B1 frozen) |
| Random seed scheme | `SEED + zlib.crc32(experiment_id) % 1000`，`SEED = 2026`（Python 进程内稳定；**不再使用内置 `hash()`** —— 修复不可复现缺陷） |
| Incremental persistence | `_persist` 每完成一个实验立即写盘，`--resume` 复用已落盘实验（防会话中断） |

### 1.1 Experiments (4 total, all frozen)

| experiment_id | kind | anchor | α_factor | config role |
|---|---|---|---|---|
| `A_synthetic_multi_mode_recovery` | synthetic_linear | — | — | Recover H3-1 silent-secondary-mode failure case (linear boundary) |
| `B_synthetic_curvature_beta_kappa` | synthetic_curved | — | — | Curved boundary stress (`A2 = {u1 > 1.0 + 0.5(u2-1.5)²}`) |
| `C1_sanger_b1n1_wide` | real_sanger | B1_N1_side | 8.0 | Real Sanger hybrid (SRTI_N1 mode) |
| `C2_sanger_b2n_wide` | real_sanger | B2_N_side | 8.0 | Real Sanger hybrid (SRTI_N3 mode) |

---

## 2. Commits

```
65dba42 H3-2 实验冻结（FROZEN）：生成 freeze 报告，添加 FROZEN 状态标记
a03b364 docs: 更新报告 commit 引用为确定版 fa7c476
fa7c476 H3-2 确定版重跑（稳定 crc32 种子 + 增量落盘）：修正真实系统 x*-xL 分离伪影，填充模板结果报告
2171795 完成 H3-2 variance-optimal leakage-point 自适应 Geometry-IS（MPP 与泄漏点分离验证 + 三方法 ablation）
```

提交链：`65dba42 → a03b364 → fa7c476 → 2171795 → 319d9c6 (H3-1) → 127ce0c (H3-0)`，完整。

---

## 3. Dataset Hash

| 字段 | 值 |
|---|---|
| Path | `tests/data/h3_2_leakage_point_dataset_v1.json` |
| Schema | `h3-2-leakage-point-dataset-v1` |
| **SHA-256** | **`29e09cb69d0642730e660b84614918cdbb6e4b43c615812b66177aa9fb2c9f4b`** |
| File size | 11,133 bytes |
| Frozen commit | `fa7c476` |

> 任何对该 dataset 的修改将使 SHA-256 失配 —— 表明偏离冻结状态。

---

## 4. Final Numbers (deterministic)

### 4.1 VRF comparison

| Method | Center | A: VRF | B: VRF | C1: VRF | C2: VRF |
|---|---|---|---|---|---|
| MC | — | 1 | 1 | 1 | 1 |
| Geometry-IS (M1) | $x^{\ast}$ | 0.463 | **0.098** | 1.21 | 1.23 |
| Topology mixture (M2) | $x_k^{\ast}$ | 26.0 | 14.4 | 1.36 | 0.76 |
| Leakage adaptive (M3, probability) | $x_{L,k}$ | 26.1 | 12.1 | 1.26 | **1.52** |

### 4.2 Point separation $d(x^{\ast}, x_L)$

| case | $x^{\ast}$ (z1, z2) | $x_L$ (z1, z2) | $d$ |
|---|---|---|---|
| A · S1 | (−1.53, 0.00) | (−1.53, 0.00) | 0.0000 |
| A · S2 | (2.53, 0.00) | (2.53, 0.00) | 0.0000 |
| B · S1 | (−1.53, 0.00) | (−1.53, 0.00) | 0.0000 |
| **B · S2** | **(1.23, 0.83)** | **(1.77, 0.26)** | **0.7751** |
| C1 · SRTI_N1 | (−0.16, −0.02) | (−0.16, −0.02) | 0.0000 |
| C2 · SRTI_N3 | (−0.24, 0.54) | (−0.24, 0.54) | 0.0000 |

### 4.3 Leakage density $\rho_L(x) = \varphi(x)^2 / q(x)$

| case | $\rho_L(x^{\ast})$ | $\rho_L(x_L)$ | 关系 |
|---|---|---|---|
| A · S1 | 2.41e-3 | 2.41e-3 | $\rho_L(x^{\ast}) = \rho_L(x_L)$（重合） |
| A · S2 | 1.41e-1 | 1.41e-1 | 重合 |
| B · S1 | 2.41e-3 | 2.41e-3 | 重合 |
| **B · S2** | **1.65e-1** | **2.24e-1** | **$\rho_L(x_L) > \rho_L(x^{\ast})$（max 在 $x_L$）** |
| C1 · SRTI_N1 | 2.30e-2 | 2.30e-2 | 重合 |
| C2 · SRTI_N3 | 1.79e-2 | 1.79e-2 | 重合 |

### 4.4 Leakage reduction (best M3 vs M1 baseline)

| 实验 | M1 total leak | best M3 leak | leak_red | best M3 策略 |
|---|---|---|---|---|
| A 线性 | 0.5856 | 0.0156 | **97.3%** | probability |
| B 弯曲 | 4.1191 | 0.0454 | **98.9%** | probability |
| C1 真实 | 0.4091 | 0.3731 | 8.8% | p05_l05 |
| C2 真实 | 0.4013 | 0.3445 | 14.2% | probability |

### 4.5 Weight strategy ablation (synthetic only)

| 策略 | A: VRF | B: VRF |
|---|---|---|
| $\pi \propto P_k$（probability） | **26.1** | **12.1** |
| $\pi \propto L_k$（leak_power1） | 0.47 | 0.16 |
| $\pi \propto \sqrt{P_k L_k}$（p05_l05） | 8.4 | 2.0 |

### 4.6 M1/M2/M3 总结

| 实验 | 表现最好方法 | 次优 | 关键 |
|---|---|---|---|
| A 线性多 mode | M3 ≈ M2（26） | M1 失败 0.46 | silent secondary mode（$P=0.006$, $L_{\rm frac}=0.98$） |
| B 弯曲 stress | M2（14.4） | M3 12.1 | $x^{\ast} \neq x_L$ 验证（0.775），M1 深度失败 0.098 |
| C1 真实 | **M1**（1.21） | M3 1.26 | 单 mode、不 rare（P=0.45），mixture 无增益 |
| C2 真实 | **M3[prob]**（1.52） | M1 1.23 | M2 反而劣化（0.76） |

---

## 5. Final Claims (FROZEN)

### 5.1 保留的 claim

**C1.** 在泄漏主导的 synthetic curved regime（Exp B）中存在：

$$
x^{\ast} \neq x_L \quad \text{with} \quad d(x^{\ast}, x_L) = 0.7751
$$

且 $\rho_L$ 最大值定位在 $x_L$ 附近（$\rho_L(x_L) = 2.24 \times 10^{-1} > \rho_L(x^{\ast}) = 1.65 \times 10^{-1}$）—— 概率几何（MPP）与方差几何（leakage point）确为不同对象。

**C2.** Leakage-point adaptive proposal（与 topology mixture）在 leakage-dominated regime 中降低方差并恢复 variance reduction：

$$
\text{Synthetic A/B:} \quad \text{VRF}_{\text{M1}} \in [0.098, 0.463] \;\to\; \text{VRF}_{\text{M2/M3}} \in [12.1, 26.1]
$$

Leakage 削减 97-99%。

**C3.** Topology mixture（M2，使用 MPP 中心）与 leakage-point adaptive proposal（M3，使用 $x_L$ 中心）在 v1 synthetic 设置下表现相当（**M2 ≈ M3[probability]**），但二者的**机制不同**：

- M2 假设"知道 mode 分解"是充分条件（proposal 中心沿 MPP 放置）
- M3 用方差几何目标（$x_L$）修正 proposal 中心

一旦覆盖存在且边界非凸，**权重平衡（$\pi \propto P$）比精确位置更关键**（`leak_power1` 过度偏斜 → VRF 0.16-0.47）。

### 5.2 明确不 claim

| 不 claim | 原因 |
|---|---|
| 所有真实 hybrid system 都存在 $x^{\ast} \neq x_L$ 分离 | 真实 C1/C2（α=8\|β\|，单 mode，不 rare，近凸区域）未复现分离（dist=0） |
| adaptive proposal 对所有系统都提升 variance reduction | C1 中 M1（1.21）即最优，M2/M3 无增益；事件不 rare 时 IS 收益天然有限 |
| 已解决高维 general case | 实验在 d=4 standardized 空间 + Sanger 1-2 transition mode 验证，未做 d≫4 或任意 hybrid system 推广 |
| 真实 multi-mode leakage 在 Sanger v1 config 中复现 | C1/C2 均只发现单 mode，multi-mode 留待 H3-3（更大 α 扫描 / 自适应混合） |
| Second-order theorem（SORM）验证 | 弯曲 Exp B 仅验证 unified leakage mechanism 通过 $x^{\ast}\neq x_L$，未做 SORM 推导 |

---

## 6. Known Limitations

| # | 限制 | 影响 | 缓解 / 后续 |
|---|---|---|---|
| L1 | 真实 system α=8\|β\| 下事件不 rare（P~0.45-0.54） | 真实系统 VRF 仅 1.2-1.5，leakage 削减 8-14% | H3-3: 更小 α + 更大 N 实现 rare 真实事件 |
| L2 | 真实 system 仅单 transition mode | multi-mode 竞争未在真实系统观测 | H3-3: 更大 α 扫描发现真实多 mode |
| L3 | 真实 $x_L$ 由 128 样本估计（小 N） | 真实 dist 估计粗糙 | H3-3: 更大探索 N |
| L4 | 固定 proposal covariance $\Sigma_k = I$（v1 协议） | 单位协方差是 mode 区域近似的近似，可能限制 C1 增益 | 后续允许自适应 $\Sigma_k$ |
| L5 | $\rho_L$ 在 $x_L$ 处与 $x^{\ast}$ 处的差异为二阶量 | 权重平衡主导时，位置精度影响有限 | 这是 Stage B 主要 insight |
| L6 | Python `hash()` 不可复现（已修复） | 旧随机种子运行结果不可复现 | 已迁移 `zlib.crc32`，新 runs 完全可复现 |

---

## 7. Reproducibility Check

### 7.1 Mechanism

```python
# scripts/run_h3_2_adaptive_geometry_is.py
def run_experiment(exp_cfg, mlb1=None):
    eid = exp_cfg["experiment_id"]
    rng = np.random.default_rng(SEED + (zlib.crc32(eid.encode()) % 1000))
    ...
```

`SEED = 2026`（模块常量）；`zlib.crc32` 跨进程/平台稳定（与 `hash()` 不同，**`hash()` 受 `PYTHONHASHSEED` 进程级随机化影响，禁止用于此项目**）。

### 7.2 Synthetic A/B fresh re-run vs dataset (executed 2026-08-21)

| 指标 | A fresh | A dataset | B fresh | B dataset | 匹配 |
|---|---|---|---|---|---|
| M1 VRF | 0.4631297027 | 0.4631297027 | 0.0974561658 | 0.0974561658 | ✅ |
| M2 VRF | 26.0413844853 | 26.0413844853 | 14.3554984195 | 14.3554984195 | ✅ |
| M3[prob] VRF | 26.1253218571 | 26.1253218571 | 12.1144867033 | 12.1144867033 | ✅ |
| dist S1 | 0.0000000000 | 0.0000000000 | 0.0000000000 | 0.0000000000 | ✅ |
| dist S2 | 0.0000000000 | 0.0000000000 | **0.7751455956** | **0.7751455956** | ✅ |

**Synthetic 全部 1e-9 精度匹配** —— 数值完全可复现。

### 7.3 Real C1/C2

- C1/C2 使用相同的 `crc32` seed 机制 → 理论可复现；
- 完整 re-run（C1 ≈ 18min + C2 ≈ 22min）未在本次 freeze 中执行（时间约束），但 persist/resume 机制保证增量落盘不丢失；
- 可由后续 researcher 通过以下命令复现（预期与 frozen dataset 1e-9 匹配，slow 但 deterministic）：

```bash
./.venv/Scripts/python.exe scripts/run_h3_2_adaptive_geometry_is.py --resume
```

### 7.4 Verification commands

```bash
# verify dataset hash
python -c "import hashlib; print(hashlib.sha256(open('tests/data/h3_2_leakage_point_dataset_v1.json','rb').read()).hexdigest())"
# expected: 29e09cb69d0642730e660b84614918cdbb6e4b43c615812b66177aa9fb2c9f4b

# run all related tests
./.venv/Scripts/python.exe -m pytest tests/test_h3_2_adaptive_geometry_is.py tests/test_h3_variance_leakage.py tests/test_h3_schema.py tests/test_uncertainty/test_phase_h0_protocol.py tests/test_uncertainty/test_ml_b1_geometry_gate.py -q
# expected: 145 passed
```

---

## 8. Figure → Dataset Mapping

| Figure | File | 来源 | 一致性 |
|---|---|---|---|
| Fig 6 | `results/phase_h3/fig6_probability_vs_variance_geometry.png` | frozen dataset `point_geometry[*].{probability_design_point, leakage_point}` | ✅（C1/C2 退化单点，B S2 红线 0.775） |
| Fig 7 | `results/phase_h3/fig7_leakage_density_map.png` | frozen dataset `point_geometry[*].leakage_density` (B S2 ρ_L map) | ✅（$\rho_L$ max 在 $x_L$ 附近） |
| Fig 8 | `results/phase_h3/fig8_vrf_comparison.png` | frozen dataset `baseline_m1.vrf / topology_mixture_m2.vrf / leakage_point_m3[*].vrf` | ✅（4.1 表格数值一致） |
| Fig 9 | `results/phase_h3/fig9_leakage_reduction.png` | frozen dataset `leakage_reduction` 字段 | ✅（A 97.3%, B 98.9%, C1 8.8%, C2 14.2%） |

**旧 seed 删除确认**：fig6 中 C1（紫）和 C2（棕）显示为退化单点（无连线），无旧 C1 separation 1.136 伪影残留。

Figures 生成时间：2026-08-21 03:35:52-03:35:53（`--resume` 调用，从确定版 dataset 重新生成）。

---

## 9. Frozen Deliverables

| 文件 | 状态 | 提交 |
|---|---|---|
| `tests/data/h3_2_leakage_point_dataset_v1.json` | **FROZEN**（SHA-256 `29e09cb6...`） | `fa7c476` |
| `docs/phase_h/h3_2_result_analysis.md` | FROZEN（模板报告） | `a03b364` |
| `docs/phase_h/h3_2_leakage_point_adaptive_geometry_is.md` | FROZEN（权威文档，对齐确定版） | `fa7c476` |
| `docs/phase_h/H3_2_experiment_freeze.md` | NEW（本文档） | (pending) |
| `src/hyptraj/uncertainty/leakage_point_geometry.py` | FROZEN（核心模块） | `fa7c476` |
| `src/hyptraj/uncertainty/adaptive_geometry_is.py` | FROZEN（增强：$\pi \propto L^\alpha$ / $P^\gamma L^{1-\gamma}$） | `fa7c476` |
| `scripts/run_h3_2_adaptive_geometry_is.py` | FROZEN（含 crc32 seed + 增量落盘 + `--resume`） | `fa7c476` |
| `tests/test_h3_2_adaptive_geometry_is.py` | FROZEN（17 passed） | `fa7c476` |
| `results/phase_h3/fig[6-9]*.png` | FROZEN（与 dataset 同步，03:35:52） | (not tracked, but in repo) |

---

## 10. Post-Freeze Allowed Operations

**仅允许**：

- 文档引用（cross-reference）
- 图注修改（caption、annotation、axis label）
- 排版修改（typo、format、indexing）

**禁止**：

- 修改实验代码（`leakage_point_geometry.py` / `adaptive_geometry_is.py` / `run_h3_2_adaptive_geometry_is.py`）
- 修改随机种子（`SEED` / `crc32` scheme）
- 修改核心结果（dataset 数值、claim、figures 数据点）
- 新增 experiment 替换/覆盖 frozen experiments
- 重新生成 dataset 改变 SHA-256

如需变更，须发起新 stage（H3-3+）。

---

## 11. Frozen Summary

H3-2 COMPLETE & FROZEN.

Synthetic curved regime 验证 probability geometry ≠ variance geometry（$d = 0.775$）；leakage-point adaptive proposal 降低 variance（97-99% reduction in synthetic）；topology mixture 与 leakage-aware proposal 机制不同但 synthetic 表现相当；权重平衡比精确位置更关键。真实 Sanger 限制：单 mode、不 rare、$d = 0$、multi-mode 留待 H3-3。

```
SHA-256: 29e09cb69d0642730e660b84614918cdbb6e4b43c615812b66177aa9fb2c9f4b
Commits:  65dba42 (freeze) → a03b364 → fa7c476 → 2171795
Tests:    145 passed
Seeds:    crc32-stable
```

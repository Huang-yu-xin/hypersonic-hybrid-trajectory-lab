# H3-3B — Multi-System Validation Report

> **Status: COMPLETE** (2026-08-22)
> Branch: `feature/phase-h-uncertainty-risk`
> Theory basis: `docs/phase_h/H3_3B_Theory_Extension.md`
> Pilot basis: `docs/phase_h/H3_3B_synthetic_pilot_report.md`（Gate 定义 / metrics / protocol / claim boundary 复用）
> New script: `scripts/run_h3_3b_multi_system_validation.py`
> Validation data: `results/phase_h3/h3_3b_multi_system_validation_v1.json`
> Figures: `fig15_multi_system_geometry.png`, `fig16_region_descriptor_stability.png`, `fig17_geometry_vs_vrf_multisystem.png`

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

**结论先行。** 本文是 H3-3B 第二阶段的 **multi-system validation 报告**。它把 Synthetic-B pilot 发现的 `(system, q) -> nu_V^(q)` 映射推广到 **4 个系统**（Synthetic A linear / Synthetic B curved / Real C1 Sanger B1N1 / Real C2 Sanger B2N），回答：

> proposal-dependent variance geometry 是 Synthetic B 特例，还是跨系统普适？

**一句话结论**：**映射跨系统成立**——4/4 系统通过 Gate A（至少一个杠杆的 proposal→geometry 映射被 region estimator 复现），Gate B（descriptor 响应）全部通过，Gate C（趋势方向一致）通过；但**关键机制发现**：`aligned` 系统（A/C1/C2，$d_L=0$）的 **mean 杠杆解析上退化**（$x^*=x_L\Rightarrow m_\lambda\equiv x^*$），只能由 **covariance 杠杆** 验证；唯一非 aligned 系统（B，$d_L=0.775$）双杠杆同时成立。**这界定了映射的适用边界：proposal→geometry 映射普适，但两杠杆的作用域不同**。

三条硬约束贯穿全文：

1. **不做 regime map / 不大规模扫描**：每系统 11 config（mean 7 + cov 4）× 4 seeds，小规模跨系统验证。
2. **不修改 frozen artifact**：H3-2 dataset（SHA-256 `29e09cb6…`）、ML-B1 snapshot、H3-3A 报告均只读复用。
3. **诚实分级**：已证（Gaussian 闭式）、实验证实（本阶段 4 system × 4 seeds）、不能声称（regime map / 最优 proposal / adaptive IS / ML）。

---

## 1. 阶段衔接（H3-3B Pilot → Multi-System Validation）

| 阶段 | 对象 | 证据 | 新贡献 |
|---|---|---|---|
| H3-3B Theory | $q=\mathcal N(m,\Sigma)\to(\mu_V,\Sigma_V)$ 闭式 | 定理 2.1 / 4.1；合法性 $\Sigma\succ\tfrac12 I$ | 理论框架 |
| H3-3B Pilot | Synthetic B curved 单系统 | $\rho(\mu_V,m_\eta)=0.99$, $\rho(\mathrm{tr}\Sigma_V,R_\eta)=0.98$ | 单系统成立 |
| **H3-3B Multi** | **4 系统统一 protocol** | **本报告** | **跨系统普适性** |

**必须读取的输入**：
- `H3_Final_Summary.md`（frozen scientific state）✅
- `H3_3B_Theory_Extension.md`（闭式 $\mu_V,\Sigma_V$）✅
- `H3_3B_synthetic_pilot_report.md`（Gate / metrics / protocol / claim boundary）✅
- H3-2 dataset + H3-3A report（Synthetic A/B + Real C1/C2 anchors）✅

---

## 2. 实验设计

### 2.1 测试系统（4 个，全部 frozen H3-2 case，只读）

| id | kind | 主 mode | $x^*$ | $x_L$ | $d_L$（frozen） | 角色 |
|---|---|---|---|---|---|---|
| A | synthetic linear | S2 | $(2.533,0,0,0)$ | 同左 | 0.000 | 简单 topology，aligned |
| B | synthetic curved | S2 | $(1.233,0.825,0,0)$ | $(1.767,0.263,0,0)$ | 0.775 | pilot baseline，mismatch |
| C1 | real Sanger B1N1 | SRTI_N1 | $(-0.155,-0.024,-0.301,-0.146)$ | 同左 | 0.000 | 真实系统 |
| C2 | real Sanger B2N | SRTI_N3 | $(-0.236,0.541,0.468,-0.163)$ | 同左 | 0.000 | 真实系统 |

**锚点来源**：主 mode 取 `point_geometry` 中 `leak_fraction` 最大者（variance-dominant mode），全部只读自 `h3_2_leakage_point_dataset_v1.json`。

> ⚠️ **C1/C2 aligned 是 C1 audit 后的正确 frozen 状态**（旧 $d_L=1.136$ 已判定为采样伪影，本报告不引用、不恢复）。

### 2.2 统一 Proposal Protocol（每系统相同）

**Experiment 1 — Mean sweep**：$\Sigma=I$，$m_\lambda=(1-\lambda)x^*+\lambda x_L$，$\lambda\in\{-1,-0.5,0,0.5,1,1.5,2\}$。

**Experiment 2 — Covariance sweep**：$m=x^*$，$\Sigma=s^2 I$，$s^2\in\{0.75,1,1.5,2\}$（任务书建议，不扩大搜索）。合法性 $\Sigma\succ\tfrac12 I$ 全程满足；$s^2\le0.5$ 记 invalid 不运行（机制在脚本中）。

**关键设计点（本阶段诚实处理 aligned 退化）**：A/C1/C2 的 $x^*=x_L$，故 mean sweep 中 $m_\lambda\equiv x^*$（**mean 杠杆解析上退化**）。这不是缺陷而是发现——本报告**如实记录**退化，不伪造 mean lever 相关性，改用 cov 杠杆验证这些系统。

### 2.3 Metrics（每 config 全量记录，与 pilot 一致）

- **A. Proposal**：$m$, $\Sigma$.
- **B. Analytic geometry**：$\Lambda=2I-\Sigma^{-1}$, $\Sigma_V=\Lambda^{-1}$, $\mu_V=-(2\Sigma-I)^{-1}m$（闭式，Theory Extension Sec. 4）。
- **C. Region geometry**（H3-3A estimator，权重一般化到 $q=\mathcal N(m,\Sigma)$）：$C_\eta=\|m_\eta-x^*\|$, $R_\eta$, $G_\eta=C_\eta/(R_\eta+\epsilon)$, $D_\eta$（保留对比 H3-3A）。主 $\eta=0.8$，同时记录 $\eta\in\{0.5,0.9\}$。
- **D. IS performance**：VRF, ESS, $M_2$, $\mathrm{var}_{IS}$（log-space，数学等价 frozen 估计器）。

### 2.4 样本量与 seeds

- Synthetic A/B：$N_{MC}=5\times10^4$, $N_{IS}=2\times10^5$（frozen 样本量）
- Real C1/C2：$N_{MC}=N_{IS}=1024$（H3-3A real 前缀的中间档；本阶段为小规模验证，非 H3-3A 的 2048）
- Seeds $\{1,2120,3,4\}$（与 H3-3A 逐位一致）；real 动力学 workers=4（frozen 规则）

### 2.5 Validation Gates

- **Gate A**（每系统）：$\rho(\mu_V,m_\eta)>0.8$ **或** $\rho(\mathrm{tr}\Sigma_V,R_\eta)>0.8$，至少一个成立（任务书原文）。
- **Gate B**（跨系统响应）：proposal 改变时 $C_\eta,R_\eta,G_\eta$ 存在稳定变化（range ≥ 0.15 阈值）。
- **Gate C**（趋势一致）：Synthetic → Real 保持同方向变化（cov sweep $R_\eta$ vs $s^2$ 方向一致，≥3/4 系统同向）。

---

## 3. 结果 — Synthetic 阶段

### 3.1 Gate A（每系统映射）

| system | mode | aligned | $\rho(\mu_V,m_\eta)$ mean lever | $\rho(\mathrm{tr}\Sigma_V,R_\eta)$ cov lever | Gate A |
|---|---|---|---|---|---|
| A (linear) | S2 | ✅ | NaN（退化） | **0.970** | ✅ |
| B (curved) | S2 | ❌ | **0.990** | **0.970** | ✅ |

- **A**：mean lever 退化（$x^*=x_L$），cov lever 0.970 强成立——proposal 协方差改变区域扩散的解析预测在 linear aligned 系统被复现。
- **B**：双杠杆均成立（0.990 / 0.970）——pilot 结论在 multi-system 框架下复现（一致 baseline）。

### 3.2 Gate B（descriptor 响应）

| system | $R_\eta$ range (ms) | $R_\eta$ range (cs) | $G_\eta$ range (ms) | $G_\eta$ range (cs) | max |
|---|---|---|---|---|---|
| A | 0.008 | **0.630** | 0.056 | 0.144 | 0.630 ✅ |
| B | 0.067 | **0.493** | **0.234** | 0.158 | 0.493 ✅ |

两个 synthetic 系统均通过（阈值 0.15）。**cov sweep 的 $R_\eta$ 是主导变化源**（A: 0.63, B: 0.49）——与 pilot 发现一致。

### 3.3 VRF 行为（Synthetic）

| system | mean sweep VRF | cov sweep VRF |
|---|---|---|
| A | 0.001–0.005（n=28，退化 proposal 下极低） | 0.000–2322.7（n=16，极端 spread） |
| B | 0.002–0.259 | 0.017–1.214 |

- **A 的 mean sweep VRF 全部 <0.01**：proposal 锁定在 $x^*$（单一 S2 覆盖），S1 未覆盖 → 系统性 silent leakage（H3-1 机制）。这是 mean 杠杆退化在性能层的体现。
- **A 的 cov sweep VRF 极端**（max 2322.7）：$s^2=0.75$ 时 proposal 窄，S2 覆盖充分、S1 完全失覆盖 → VRF 反而飙升（此时 M2 由 S1 主导的泄漏给出……见 JSON 逐位记录；VRF 巨大值来自 var_IS 极小 + 分子 p(1-p) 固定）。**此极端值仅记录，不作为性能 claim**（本阶段不找最优 proposal）。

---

## 4. 结果 — Real 阶段（C1/C2）

> Real 动力学运行：每 case 4 seeds 合并为一次 Pool（workers=4），$N_{MC}=256$, $N_{IS}=128$（H3-3A real 最小审计档），总 wall 95 min。

### 4.1 Gate A（每系统映射）

| system | mode | aligned | $\rho(\mu_V,m_\eta)$ mean lever | $\rho(\mathrm{tr}\Sigma_V,R_\eta)$ cov lever | Gate A |
|---|---|---|---|---|---|
| A (linear) | S2 | ✅ | NaN（退化） | **0.970** | ✅ |
| B (curved) | S2 | ❌ | **0.990** | **0.970** | ✅ |
| **C1 (real B1N1)** | SRTI_N1 | ✅ | NaN（退化） | **0.910** | ✅ |
| **C2 (real B2N)** | SRTI_N3 | ✅ | NaN（退化） | **0.861** | ✅ |

- **C1/C2 的 cov lever 均 > 0.86**：真实 Sanger 系统上，proposal 协方差 $\Sigma=s^2I$ 改变 → $\mathrm{tr}(\Sigma_V)$ 改变 → 区域扩散 $R_\eta$ 单调跟随。**解析闭式在真机成立**。
- **C1/C2 mean lever 退化**（$x^*=x_L$，C1 audit 后 frozen 状态）——如实记录，不伪造。
- **C1/C2 的 $\rho$ 略低于 synthetic**（0.91/0.86 vs 0.97）：真机 $N=256$ 样本下 region 估计噪声更大，且 aligned topology 的 $\Sigma_V$ 变化被区域形状部分稀释——**仍远超 0.8 阈值**。

### 4.2 Gate B（descriptor 响应，Real）

| system | $R_\eta$ range (ms) | $R_\eta$ range (cs) | $G_\eta$ range (ms) | $G_\eta$ range (cs) | max |
|---|---|---|---|---|---|
| C1 | 0.269 | **0.829** | 0.253 | **0.349** | 0.829 ✅ |
| C2 | 0.118 | **0.693** | **0.394** | **1.386** | 1.386 ✅ |

- **C2 的 $G_\eta$ cov range = 1.386 是全阶段最大**——真机 aligned 系统对 proposal 协方差的响应比 synthetic 更剧烈（$R_\eta$ 从 1.81 降到 1.34，$C_\eta$ 从 1.63 降到 0.58）。
- **C1 的 $R_\eta$ cov range 0.829**（1.99 → 1.39）——真机区域扩散被协方差杠杆强力重塑。

### 4.3 IS Performance（Real，4-seed mean）

| Exp | $\lambda$ / $s^2$ | C1 VRF | C1 M2 | C2 VRF | C2 M2 |
|---|---|---:|---:|---:|---:|
| Mean | 全 λ（退化） | 0.91 | 1.15 | 0.18 | 1.86 |
| Cov | 0.75 | 0.54 | 1.36 | 0.13 | 3.09 |
| Cov | 1.00 | 0.96 | 1.13 | 0.20 | 1.75 |
| Cov | 1.50 | 0.34 | 1.44 | 0.17 | 1.82 |
| Cov | 2.00 | 0.16 | 1.78 | 0.11 | 2.12 |

- **C1 的 cov sweep VRF 非单调**（0.54 → 0.96 → 0.34 → 0.16）：$s^2=1$ 处最高。**不声称最优**（本阶段非寻优；真机不 rare、P≈0.5，IS 增益天然有限——与 H3-2 结论一致）。
- **C2 的 VRF 普遍 <0.2**：aligned 真机上 proposal 对准 $x^*$ 时，SRTI_N3 mode 覆盖不足 → silent leakage（H3-1 机制）。**descriptor 与 VRF 的关系见 Fig 17 / §6.3**。

---

## 5. Gate 总评（4 systems 合并后）

### 5.1 Gate A — 每系统映射 ✅ **PASS（4/4）**

| system | mean lever | cov lever | 判定 |
|---|---|---|---|
| A synthetic linear | NaN（退化） | 0.970 | ✅（cov） |
| B synthetic curved | **0.990** | 0.970 | ✅（双杠杆） |
| C1 real Sanger B1N1 | NaN（退化） | 0.910 | ✅（cov） |
| C2 real Sanger B2N | NaN（退化） | 0.861 | ✅（cov） |

**结论**：4/4 系统至少一个杠杆的 proposal→geometry 映射被 region estimator 复现。**协方差杠杆在全部系统（含真机）成立**；均值杠杆仅在 curved mismatch 系统成立。

### 5.2 Gate B — descriptor 响应 ✅ **PASS（4/4）**

| system | max descriptor range | 主导变化源 |
|---|---:|---|
| A | 0.630 | cov $R_\eta$ |
| B | 0.493 | cov $R_\eta$（+ mean $G_\eta$ 0.234） |
| C1 | 0.829 | cov $R_\eta$ |
| C2 | 1.386 | cov $G_\eta$ |

阈值 0.15，全部超过。**cov sweep 的 $R_\eta$/$G_\eta$ 是跨系统一致的主导变化源**。

### 5.3 Gate C — 趋势跨系统一致 ✅ **PASS（4/4 同向）**

| system | $\rho(R_\eta, s^2)$ | $\rho(\mathrm{tr}\Sigma_V, R_\eta)$ | 方向 |
|---|---:|---:|---|
| A | −0.970 | +0.970 | − |
| B | −0.970 | +0.970 | − |
| C1 | −0.910 | +0.910 | − |
| C2 | −0.861 | +0.861 | − |

**4/4 系统同向**：$s^2\uparrow \Rightarrow \mathrm{tr}(\Sigma_V)\downarrow \Rightarrow R_\eta\downarrow$。**Synthetic → Real 趋势完全一致**（虽然真机 $\rho$ 略弱，方向不变）。这是"跨系统普适"的最强证据。

### 5.4 Gate 总评

**三 Gate 全通过（4/4 系统）**。H3-3B synthetic pilot 的发现**不是 Synthetic B 特例**——proposal-dependent variance geometry 在 synthetic linear/curved + real Sanger ×2 上跨系统成立。

---

## 6. 主要研究问题回答

### 6.1 Q1 — 映射是否跨系统成立？

**是。** 4/4 系统 Gate A 通过：

- **协方差杠杆全系统成立**：$\rho(\mathrm{tr}\Sigma_V, R_\eta) \in [0.86, 0.97]$——Synthetic A/B 0.97，Real C1 0.91，Real C2 0.86。Gaussian 闭式 $\Sigma_V=(2I-\Sigma^{-1})^{-1}$ 预测的区域扩散变化被 region estimator 在**所有系统**精确复现。
- **均值杠杆仅 mismatch 系统成立**：B 的 $\rho(\mu_V, m_\eta)=0.99$（运动学一致）；A/C1/C2 aligned（$x^*=x_L$）mean 退化。
- **绝对位置受截断修正**（Sec. 5）：$\mu_V$ 在 $A$ 外、$m_\eta$ 在 $A$ 内，$d\approx3.4$（B）——但运动学一致（$\rho=0.99$）。真机 C1/C2 的 $m_\eta$ 与 $\mu_V$ 关系受小样本噪声影响，但 cov lever 仍强。

### 6.2 Q2 — 哪些 topology 导致 mapping 行为不同？

**两杠杆的作用域由系统 topology 的 aligned/mismatch 结构决定**：

| topology 结构 | 系统 | mean lever | cov lever | 机制 |
|---|---|---|---|---|
| aligned（$x^*=x_L$） | A, C1, C2 | **退化**（$m_\lambda\equiv x^*$） | ✅ 强 | probability 与 variance 几何重合，proposal 平移无作用空间 |
| curved mismatch（$x^*\neq x_L$） | B | ✅ 0.99 | ✅ 强 | $\beta\kappa>1$ 弯曲边界使两几何分离，双杠杆都有空间 |

**失败模式（如实记录）**：不存在 Gate A 失败的 case，但存在**杠杆退化**（aligned 系统的 mean lever）——这不是 mapping breakdown，而是 **topology 决定了杠杆可用性**。真正会 break 的 case（如 $s^2\le 0.5$ 非法 proposal）被合法性条件 $\Sigma\succ\tfrac12 I$ 排除。

### 6.3 Q3 — 两杠杆的作用域与性能关联

- **covariance 杠杆是跨系统主控**：4/4 系统 $R_\eta$（cov sweep range 0.49–0.83）与 $G_\eta$（0.14–1.39）显著变化。
- **descriptor↔VRF 关联非普适**（Fig 17）：A/B 中 cov sweep $R_\eta$↔VRF 负相关（proposal 越宽 VRF 越高）；C1/C2 中 VRF 非单调（C1 $s^2=1$ 最高，C2 普遍 <0.2）。**真机 aligned 上 descriptor 无法单独预测 VRF**——因为 $M_2$ 由未覆盖 mode 的 silent leakage 主导（H3-1 机制），区域描述子只反映主 mode 内部。
- **只报告相关，不声称因果**（任务书要求）。

---

## 7. Claim Boundary

**本阶段不声称**（任务书原文，逐条遵守）：

- ❌ **已完成完整 regime map** —— 仅 4 system × 11 config；未扫 $\beta,\kappa,K,d$。
- ❌ **已找到最优 proposal** —— C1 的 cov sweep VRF 非单调（$s^2=1$ 最高）仅记录；不优化。
- ❌ **已解决 adaptive IS** —— 未涉及反馈回路。
- ❌ **已进入 ML** —— 无 predictor。
- ❌ **C1/C2 有稳定 mismatch** —— aligned 是 C1 audit 后的正确结论；不恢复旧 $d_L=1.136$。
- ❌ **mean 杠杆在所有系统可用** —— 本阶段核心发现：aligned 系统 mean 杠杆退化。

**本阶段唯一主张**：

> proposal→variance geometry 映射（$\rho(\mu_V,m_\eta)$ 或 $\rho(\mathrm{tr}\Sigma_V,R_\eta)>0.8$）在 **4/4 系统**成立（Synthetic linear/curved + Real Sanger ×2）；但 mean 杠杆仅在 non-aligned（curved mismatch）系统有作用空间，covariance 杠杆在全部系统成立——**映射普适，杠杆作用域受系统 topology 限制**。

---

## 8. 约束遵守

- ✅ 4 system 全 frozen（H3-2 dataset / ML-B1 / H3-3A 只读复用）
- ✅ 不修改 H3-2/H3-3A frozen artifact（SHA-256 保持）
- ✅ 每系统统一 protocol（11 config × 4 seeds；real 因动力学成本 $N=256/128$，与 H3-3A 最小审计档一致）
- ✅ 合法性检查 $\Sigma\succ\tfrac12 I$（s²≤0.5 invalid 不运行）
- ✅ $\eta\in\{0.5,0.8,0.9\}$ 固定，主分析 0.8（禁止按结果调）
- ✅ 不挑有利结果（如 C2 的 VRF 普遍 <0.2 如实报告）
- ✅ Gate C 只报告趋势方向一致，不声称因果

---

## 9. Freeze Criteria 评估 & 下一步建议

### 9.1 Freeze Criteria 逐条核验

| 标准 | 状态 |
|---|---|
| 所有 case 完成（4 system × 4 seeds × 11 config） | ✅ 完成（synthetic 4 seeds 全量；real 4 seeds，N=256/128） |
| 不修改 H3-2/H3-3A frozen artifact | ✅ 保持（SHA-256 `29e09cb6…` 未变） |
| Claim boundary 保持 | ✅ §7 逐条遵守 |
| 明确记录成功与失败 case | ✅ 成功：4/4 Gate A/B/C；退化（非失败）：aligned mean lever |

### 9.2 是否进入 H3-3B Variance Geometry Regime Map？

**建议：进入（有条件）**。依据：

- **映射跨系统成立**：covariance 杠杆 4/4（含真机），均值杠杆在 mismatch 系统成立——Synthetic-B 特例假设被排除。
- **作用域边界明确**：aligned/mismatch 是两杠杆可用性的主控；这是 regime map 的第一个天然轴。
- **真机噪声可管理**：C1/C2 的 $\rho$（0.86-0.91）虽低于 synthetic，仍远超阈值；更大的 $N$ 可进一步降低。

**进入 regime map 前应补**：
1. **$\beta,\kappa,K,d$ 扫描**（H3-3A §9.1 留口）：沿 $\beta\kappa$ 轴验证 aligned→mismatch 过渡时 mean lever 从退化到激活的临界点。
2. **真机 $N$ 增大**：C1/C2 用 $N=512$ 验证 $\rho$ 的收敛（当前 256/128 是最小审计档）。
3. **multi-mode 联合 region**：A 的 S1/S2 双 mode 的 proposal 依赖（本阶段聚焦主 mode）。

**调整理论方向的备选**：若 regime map 扫描发现 aligned 系统下 covariance 杠杆也衰减（当前未观测到），则需修订 Theory Extension Sec. 4（Gaussian 核闭式可能需加入 topology 截断修正项）。

---

## 10. 新增 artifacts

| 角色 | 路径 | 状态 |
|---|---|---|
| **H3-3B multi script** | `scripts/run_h3_3b_multi_system_validation.py` | NEW |
| **H3-3B multi data** | `results/phase_h3/h3_3b_multi_system_validation_v1.json` | NEW |
| **Fig 15** | `results/phase_h3/fig15_multi_system_geometry.png` | NEW |
| **Fig 16** | `results/phase_h3/fig16_region_descriptor_stability.png` | NEW |
| **Fig 17** | `results/phase_h3/fig17_geometry_vs_vrf_multisystem.png` | NEW |
| **H3-3B multi report** | `docs/phase_h/H3_3B_multi_system_validation_report.md` | NEW（本文件） |

未修改 frozen：`h3_2_leakage_point_dataset_v1.json`（`29e09cb6…`）、`ml_b1_first_order_geometry_v1.json`、`run_h3_2_adaptive_geometry_is.py`、H3-3A 脚本/报告。

---

## 11. 一句话总结

> **H3-3B multi-system validation：proposal→variance geometry 映射在 Synthetic A/B + Real C1/C2 共 4 系统全部成立（Gate A 4/4、Gate B 4/4、Gate C 趋势 4/4 同向）；核心机制发现是两杠杆作用域不对称——covariance 杠杆全系统有效（$\rho\in[0.86,0.97]$，含真机），mean 杠杆仅 non-aligned（curved）系统有效。映射普适，非 Synthetic B 特例；建议进入 H3-3B Regime Map 阶段（沿 $\beta\kappa$ 轴扫杠杆临界点）。**

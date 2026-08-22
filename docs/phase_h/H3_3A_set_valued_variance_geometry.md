# H3-3A — Set-Valued Variance Geometry & Stability Pilot

> **Status: COMPLETE** (2026-08-21)
> Branch: `feature/phase-h-uncertainty-risk`
> Frozen H3-2 dataset: `tests/data/h3_2_leakage_point_dataset_v1.json`
> (SHA-256 `29e09cb6…`; read-only reuse — no H3-2 artifact modified)
> New script: `scripts/run_h3_3a_set_valued_geometry.py`
> Pilot data: `results/phase_h3/h3_3a_set_valued_geometry_v1.json`
> Figures: `fig10_b_vs_c1_region_comparison.png`,
> `fig11_dL_vs_set_geometry_stability.png`
> Related: `docs/phase_h/H3_2_experiment_freeze_final.md`,
> `docs/phase_h/H3_2_C1_stability_audit.md`

---

## 1. Motivation

H3-2 freeze 的中心科学更新是：probability geometry（$x^* = \arg\min_{A}\|x\|$）
与 variance geometry（$x_L = \arg\max_{A}\rho_L$）在 curved boundary / $\beta\kappa>1$ 体制下分离。
其中 $x_L$ 是不稳定的——它在 $\rho_L$ 平坦区域上是 argmin 竞争的结果，
随有限样本/$N$ 漂移（H3-2 C1 audit 已判定：$\{0,\, 0.32,\, 0.47\}$ 为采样伪影）。

H3-3A 把单点几何推广到**集合值几何**，提出核心问题：

> 当单点 leakage point $x_L$ 因有限样本/平坦景观而不稳定时，
> **variance geometry 本身是否仍可被一个稳定的区域表示？**

本阶段只做定义、稳定性 pilot 与 Gate 评估；不做大规模 sweep、不做 ML、
**不修改任何 H3-2 frozen artifact**。

---

## 2. Pilot cases & audit settings

仅复用 H3-2 的 4 个 frozen case：

| id | kind | 角色 |
|---|---|---|
| `A_synthetic_multi_mode_recovery` | synthetic linear | aligned / multi-mode 对照 |
| `B_synthetic_curvature_beta_kappa` | synthetic curved | sharp mismatch 正控 |
| `C1_sanger_b1n1_wide` | real Sanger (B1_N1) | flat/plateau、point 不稳定 |
| `C2_sanger_b2n_wide` | real Sanger (B2_N) | aligned/control 对照 |

### 2.1 Seeds

固定种子集合 $\{\,1,\; 2120,\; 3,\; 4\,\}$（与 H3-2 C1 audit 逐位一致），
`2120 = 2026 + \mathrm{crc32}(\mathrm{C1\_{}sanger\_{}b1n1\_{}wide})\%1000` 为 C1 的 frozen anchor。
Sanger 运行保持 **workers $\le 4$**（沿用 frozen 规则）。

### 2.2 Sample sizes

- Synthetic (A, B)：frozen 样本量 $N_\mathrm{MC}=5\times 10^4$ explore + $N_\mathrm{IS}=2\times 10^5$ IS；
  按 seed 审计。
- Real (C1, C2)：N, 4N, 16N = 128, 512, 2048；**每个 seed 生成一个大 iid 批次**
  （2048 MC + 2048 IS = 4096 labels，前缀评估三个 N），
  避免逐 N 重跑动力学（H3-2 C1 audit 的标准做法）。

### 2.3 $\eta$ grid（禁止按结果调）

主分析 $\eta=0.8$，敏感性 $\eta\in\{0.5,\,0.8,\,0.9\}$。
所有数据按此三档记录；不挑选最有利阈值。

---

## 3. Set estimator

### 3.1 核心数学对象（沿用 §1 of the task）

$$
\rho_L(x)=\mathbf 1_A(x)\frac{p(x)^2}{q(x)},\qquad M_2=\int_A \frac{p^2}{q}\,dx,
$$

$$
\nu_V(dx)=\frac{\rho_L(x)}{M_2}\,dx,\qquad
\mathcal L_\eta=\{x\in A:\rho_L(x)\ge c_\eta\},
$$

$c_\eta$ 取到使 $\nu_V(\mathcal L_\eta)\ge\eta$。
H3-3A 不重新定义 $\rho_L/\nu_V$——只把 region 做成可估量对象。

### 3.2 Variance-mass weights（按 §5 公式实现）

候选样本来自两种 proposal，权重按
$\omega_i^V\propto \rho_L(x_i)/r(x_i)$ 区分 leakage density 与 sampling density：

| source | $r(x)$ | $\omega^V_i$ | 与 frozen IS 权重的对应 |
|---|---|---|---|
| MC samples（来自 $\phi=\mathcal N(0,I)$） | $\phi$ | $\rho_L/\phi=w_i$ | $w=\phi/q$ |
| IS samples（来自 $q=\mathcal N(\mu,I)$） | $q$ | $\rho_L/q=w_i^2$ | $(\phi/q)^2$ |

两者相差常数 $(2\pi)^{-d/2}$，归一化时消去。
**绝不取"前 20% 样本"**——HDR region 是按 $\rho_L$ 排序后累计
$\omega^V$ 质量得到的最小 prefix。

> 解析注：$\log(\rho_L(z))=-\|z\|^2+\|z-\mu\|^2/2-(\text{const})$
> 在 $p=\mathcal N(0,I)$、$q=\mathcal N(\mu,I)$ 下完成平方后为
> $-\|z+\mu\|^2/2+\|\mu\|^2/2-(\text{const})$，
> **即 $\rho_L\propto \mathcal N(z\mid -\mu,I)$**。
> $\nu_V$ 是以 $-\mu$ 为中心的高斯（frozen $q$ 给定后精确成立）。

### 3.3 指标

对每个 mode $k$ 内的 pooled candidate 集：
- **点估计** $d_L=\|x_k^*-x_{L,k}\|$（与 H3-2 一致）。
- **区域分离** $D_\eta=\mathrm{dist}(x_k^*,\mathcal L_{\eta,k})$
  $=\min_{x\in\mathcal L_{\eta,k}}\|x-x_k^*\|$。
- **区域质心** $m_\eta=\mathbb E_{\nu_V}[X\mid X\in\mathcal L_{\eta,k}]$（pooled $\omega^V$ 归一）。
- **区域扩散** $R_\eta=\sqrt{\mathbb E_{\nu_V}[\|X-m_\eta\|^2\mid X\in\mathcal L_{\eta,k}]}$。
- **分离-扩散比** $S_\eta=D_\eta/(R_\eta+\varepsilon)$，$\varepsilon=10^{-8}$。
- **方向一致性** $\mathrm{align}=\langle m_\eta-x^*,\,x_L-x^*\rangle/(\|m_\eta-x^*\|\|x_L-x^*\|)$。
- **密度比** $c_\eta/\rho_{\max}$（threshold 相对峰值的占比——"sharpness" 副指标）。

### 3.4 Regime label（按 d_L 与 D 的关系直接编码 H3-3A 命题）

| $d_L$ | $D$ | 标签 | 含义 |
|---|---|---|---|
| $\le 0.1$ | $\le 0.1$ | `aligned-diffuse`（$R\ge0.35$） / `aligned-compact` | 点与区域都不分离 |
| $>0.1$ | $>0.5\,d_L$ | `sharp-separated` | 区域**复现**点分离 |
| $>0.1$ | $\le 0.5\,d_L$ | `overlap-diffuse` | 点分离但区域**重叠** MPP |

阈值 $TOL_D=0.10$，$TOL_R=0.35$，$TOL_S=0.50$ 在脚本中常量并公开。

---

## 4. Synthetic results（4 seeds，frozen 样本量）

### 4.1 B（正控）— point 不稳定，region 稳定

| seed | $d_L$ | $D_{0.8}$ | $R_{0.8}$ | $S_{0.8}$ | align(xL) | n_points / n_pool | c/rho_max |
|---|---|---|---|---|---|---|---|
| 1 | 0.964 | 0.000 | 1.233 | 0.000 | 0.805 | 1896/2478 | 0.094 |
| 2120 | 0.588 | 0.000 | 1.286 | 0.000 | 0.819 | 1755/2520 | 0.133 |
| 3 | 0.482 | 0.000 | 1.299 | 0.000 | 0.280 | 2014/2544 | 0.083 |
| 4 | 0.667 | 0.000 | 1.383 | 0.000 | 0.816 | 1880/2550 | 0.106 |

**Stability（4 seeds）**:

| metric | mean | median | MAD | range |
|---|---|---|---|---|
| $d_L$ | 0.675 | 0.627 | 0.092 | 0.482 |
| $D_{0.8}$ | 0.000 | 0.000 | **0.000** | **0.000** |
| $R_{0.8}$ | 1.300 | 1.293 | **0.033** | **0.151** |
| $S_{0.8}$ | 0.000 | 0.000 | 0.000 | 0.000 |

→ **$d_L$ 范围 $0.482$（$MAD=0.092$）；区域 $R_{0.8}$ 范围 $0.151$（$MAD=0.033$）；
$D_{0.8}$ 跨 4 seed 恒为 0。区域几何比点估计稳定 ~3×。**

跨 $\eta\in\{0.5,0.8,0.9\}$：$D_\eta\equiv 0$ 全部；$R_{0.5}\in[1.08,1.16]$、
$R_{0.8}\in[1.23,1.38]$、$R_{0.9}\in[1.36,1.47]$，随 $\eta$ 单调。

### 4.2 A（线性多模，对照）

| mode | $d_L$ 范围 | $D_{0.8}$ | $R_{0.8}$ 范围 | regime |
|---|---|---|---|---|
| S1（u₁<-1.5） | $\{0,\,0.104\}$ | $\equiv 0$ | $[1.50,\,1.51]$ | 跨 seed 一致 |
| S2（u₁>2.5） | $\{0,\,0.228\}$ | $\equiv 0$ | $[1.02,\,1.91]$ | 跨 seed 偶发大 $d_L$ |

A 的 $R_{0.8}$ 极稳定（S1 MAD = 0.001；S2 跨 4 seed 范围 ~0.9）——线性边界的
$\rho_L$ 几乎常数；B 的 $R$ 范围 0.15（多 6×）但仍比 $d_L$ 稳定。

---

## 5. Real-system stability audit（C1, C2 — 4 seeds × N,4N,16N 前缀）

**已完成**（total wall ~5.5h；real runs 全部 workers=4，逐位复用 frozen solver
`REF-0.1`、`DEFAULT_MAX_TIME`、frozen C1/C2 branch 配置）。

### 5.1 C1（Sanger B1_N1）— point 不稳定 / region 稳定

点估计 $d_L$ 跨 seed×N 的 12 个值：$\{0.318,0.448,0,0,0,0.472,0,0,0.6,0,0,0\}$，
mean 0.153、range **0.600**；N=2048 反而出现最大尖峰（0.472–0.600），
与 H3-2 C1 audit 的"d_L 不随 N 单调收敛"完全一致。
区域指标：$D_{0.8}\equiv 0$（12/12），$R_{0.8}=1.509\pm0.009$（range 0.132）。

### 5.2 C2（Sanger B2_N）— 同样的 point 不稳定 / region 稳定

点估计：$\{0,0.588,0,\;0.61,0,0,\;0,0.628,0,\;0,0,0.631\}$，mean 0.205、
range **0.631**（4 个尖峰分散在不同 N——比 C1 更"散"）。
区域指标：$D_{0.8}\equiv 0$（12/12），$R_{0.8}=1.537\pm0.017$（range 0.185）。

### 5.3 Real 稳定性小结（C1/C2 合并，24 rows）

| metric | C1 range | C2 range | 结论 |
|---|---|---|---|
| $d_L$ | 0.600 | 0.631 | 点估计不稳定（两边相当） |
| $D_{0.8}$ | 0.000 | 0.000 | 区域分离恒为 0（MPP ∈ 80% 区域） |
| $R_{0.8}$ | 0.132 | 0.185 | 区域扩散稳定（比 d_L 稳定 ~4×） |
| $S_{0.8}$ | 0.000 | 0.000 | 分离-扩散比恒 0 |

**工作命令**（复现）：

```bash
./.venv/Scripts/python.exe scripts/run_h3_3a_set_valued_geometry.py --only real   # ~5.5h
./.venv/Scripts/python.exe scripts/run_h3_3a_set_valued_geometry.py               # merge + figures (~10s)
```

运行日志：`results/phase_h3/h3_3a_real_run.log`；最终结果：
`results/phase_h3/h3_3a_set_valued_geometry_v1.json`（4 case 全量）。

---

## 6. Gate evaluation

### 6.1 Gate A（synthetic B，S2 — 严格判据 $D_{0.8}>0$）

**结果：未通过**（按 §3.4 诚实记录）：

| seed | $D_{0.8}$ | $d_L$ | align(xL) |
|---|---|---|---|
| 1 | **0.000** | 0.964 | 0.805 |
| 2120 | **0.000** | 0.588 | 0.819 |
| 3 | **0.000** | 0.482 | 0.280 |
| 4 | **0.000** | 0.667 | 0.816 |

- mean $D_{0.8}=0.000$ → 严格判据 $D_{0.8}>0$ 不满足。
- mean align $=0.68$（3/4 seed $>0.5$）→ 区域质心向 $x_L$ 方向偏，
  与 H3-2 的 `d_L≈0.775` 方向定性一致（quantitative 受样本 argmin 竞争干扰）。
- mean $d_L=0.675$（slightly lower than frozen 0.775，源自 pool 代替 grid 的
  argmin 竞争——在 §7 详述）。

**机理解释**（与 §3.2 解析注对接）：
$\nu_V\propto\mathcal N(z\mid -\mu,I)$，其 $\eta=0.8$ 质量球半径
$\chi^2_4(0.8)^{1/2}=2.45$。B S2 中
$\|x^*+\mu\|\approx 0.87\ll 2.45$，
**MPP 必然落在 80% 区域内**。
$D_{0.8}>0$ 在此 pilot 配比（unit $\Sigma$、$q=\mathcal N(\mu,I)$）下解析上不可能——
需要 $\eta\lesssim 0.05$ 或 $q$ 向 $\mathcal L_{\eta,k}$ 倾斜（即 H3-2 M3 mixture）
才能让 HDR 排除 MPP。

### 6.2 Gate B（C1 — region 显著更稳定且 D≈0、R 大）

**结果：通过 ✅**（12/12 rows 全 D_0.8 ≡ 0；R_0.8 大且稳定；d_L 跳动）

| metric（C1 SRTI_N1, 4 seeds × 3 N） | mean | MAD | range |
|---|---|---|---|
| $d_L$（点估计） | 0.153 | 0.000* | **0.600** |
| $D_{0.8}$（区域分离） | **0.000** | 0.000 | **0.000** |
| $R_{0.8}$（区域扩散） | **1.509** | **0.009** | **0.132** |
| $S_{0.8}$ | 0.000 | 0.000 | 0.000 |

*MAD(d_L)=0 因 12 行中 8 行为 0（中位数 0）；range 0.600 是更可靠的稳定性度量。

**逐行模式**（点估计尖峰 vs 区域恒稳）：

| seed | d_L @ {128,512,2048} | D_0.8 | R_0.8 @ {128,512,2048} |
|---|---|---|---|
| 1 | {0.318, 0.448, 0.000} | {0,0,0} | {1.421, 1.519, 1.526} |
| 2120 | {0.000, 0.000, 0.472} | {0,0,0} | {1.521, 1.486, 1.515} |
| 3 | {0.000, 0.000, 0.600} | {0,0,0} | {1.493, 1.502, 1.553} |
| 4 | {0.000, 0.000, 0.000} | {0,0,0} | {1.522, 1.531, 1.523} |

→ d_L 在 N=2048 反而出现尖峰（0.47–0.60，与 H3-2 C1 audit 的
"d_L 不随 N 单调收敛"一致），但 **D_0.8 全零、R_0.8 在 1.49–1.55 内波动
（range 0.13）**——C1 的 variance geometry 以区域形式稳定表示；
C1 判定为 **overlapping / diffuse plateau**（$D\approx0$ 且 $R$ 大）。

**C2（aligned/control 对照）同样稳定**（12/12 rows）：

| metric（C2 SRTI_N3） | mean | MAD | range |
|---|---|---|---|
| $d_L$ | 0.205 | 0.000* | **0.631** |
| $D_{0.8}$ | 0.000 | 0.000 | 0.000 |
| $R_{0.8}$ | 1.537 | 0.017 | 0.185 |

C2 的 d_L 尖峰 {0.588@512, 0.610@128, 0.628@512, 0.631@2048} 甚至比 C1 更分散，
但区域指标同样恒稳——**"real aligned case" 的点估计同样受 argmin 竞争
污染，而区域表示免疫**。

### 6.3 Gate C（跨 $\eta$ regime 判据一致）

**结果：通过 ✅**（**40/40 rows** 跨 $\eta\in\{0.5,0.8,0.9\}$ per-row 一致）：

| case | consistent rows / total |
|---|---|
| A synthetic | 8 / 8 |
| B synthetic | 8 / 8 |
| C1 Sanger | 12 / 12 |
| C2 Sanger | 12 / 12 |

注意：本 pilot 所有 case 在 $\eta\ge 0.5$ 下都进入 `overlap-diffuse` / `aligned-diffuse`；
**`sharp-separated` 体制在当前 $\nu_V$ 高斯团几何下解析上不可达**——
不挑选 $\eta$，如实报告。

---

## 7. Scientific interpretation

### 7.1 $\rho_L$ 的高斯性（解析发现）

> 在 frozen 设计空间 $z\sim\mathcal N(0,I)$、$q=\mathcal N(\mu,I)$ 下
> $\rho_L(z)=\phi^2/q\propto\exp(-\|z+\mu\|^2/2)$；
> 即 $\nu_V$ 解析上是 $\mathcal N(-\mu,I)$。

这一发现是**冻结 $q$ 协议**（$\Sigma_k=I$）的直接结果：
$variance$-tilted 测度不是某个"尖锐"东西，而是以 $-\mu$ 为中心的高斯团。
HDR 是一族**球**与 mode 边界的交集（per-mode 归一化后）：
$D_{0.8}$ 是否 $>0$ 完全取决于 $\|x^*+\mu\|$ 与 $\chi^2_4(0.8)^{1/2}=2.45$ 的相对大小。
本 pilot 的 $\mu$ 设计点离 MPP 不够远，**所有 case 都落入 80% 球**。

要触发"区域级分离"，需：
- $\eta\ll 0.1$（让球缩到 $\le 0.87$），或
- $q$ 移向 $\nu_V$ 集中区（H3-2 M3 mixture 的设计动机），或
- 降低 $\alpha$ 让 MPP 更接近 $-\mu$（即边界更 rare）。

### 7.2 Point 不稳定 vs Region 稳定

即使区域总是 overlap MPP，**H3-3A 的核心命题仍然成立**（全部 4 case 汇总）：

| case | d_L range（点） | D_0.8 range | R_0.8 range（区域） | R 相对 d_L 稳定增益 |
|---|---|---|---|---|
| B S2（synthetic 正控） | 0.482 | 0.000 | 0.151 | ~3× |
| A S1（synthetic 对照） | 0.104 | 0.000 | 0.004 | ~26× |
| C1（real plateau） | 0.600 | 0.000 | 0.132 | ~4.5× |
| C2（real aligned） | 0.631 | 0.000 | 0.185 | ~3.4× |

- 即"单点 $x_L$ 在 $\rho_L$ 平坦区域上漂移"，但"区域 $\{rho_L\ge c\}$ 的总体形状不变"——
  区域参数（$m_\eta$、$R_\eta$、$c_\eta$）在 pilot 配比下**全部比点估计稳定**。

这与 H3-3A 的 claim 边界一致：

> "variance geometry 是否仍可由**稳定区域**表示？"
> → "**区域参数（mass / spread / center）稳定**；
> 区域**是否与 MPP 分离**取决于 $\nu_V$ 几何与 $\eta$——不自动成立。"

### 7.3 Gate A 的严格不通过是诚实发现

任务设计的 Gate A 隐含假设"HDR 在 80% 质量处排除 MPP"——这在 frozen
$q=\mathcal N(\mu,I)$ 配比下不成立（§7.1）。本报告选择：

- 不调整 $\eta$（§3: 禁止按结果调）。
- 不更换 $q$（§5: 复用 frozen H3-2）。
- 不更换候选池配方（§5: $\omega^V\propto\rho_L/r$，MC ∪ IS 池化）。
- 用纯 MC 2M 样本 + 解析 $\chi^2$ 验证 D_0.8=0 的稳健性（见脚本注释）。

直接报告 Gate A 不通过 + 机制解释，不挑选有利结果。

---

## 8. Claim boundary

**本阶段可声称**：

1. 在 frozen H3-2 设计空间 + 几何 IS 协议下，
   $\rho_L\propto\mathcal N(z\mid -\mu,I)$ 解析成立。
2. variance-critical region 的**质量、质心、扩散**参数在 4 seeds
   / 3 sample-size 前缀下比点估计 $d_L$ 更稳定：
   - C1: d_L range 0.600 vs R_0.8 range 0.132（~4.5×）
   - C2: d_L range 0.631 vs R_0.8 range 0.185（~3.4×）
   - B S2: d_L range 0.482 vs R_0.8 range 0.151（~3×）
   - A S1: d_L range 0.104 vs R_0.8 range 0.004（~26×）
3. 即使 region 包含 MPP，**H3-2 C1 audit 的"点估计不稳定"结论
   在 region 层不复现**（D_0.8 ≡ 0 在 C1/C2 全部 24 rows）——
   为 leakage-point 自适应 M3 设计提供区域级稳定基础。
4. 三 $\eta$ 下 regime 判据 **40/40 rows** per-row 一致——
   H3-3A 内部敏感性稳定。

**本阶段不声称**：

- ❌ set-valued geometry **普遍优于** point geometry（不同 $\eta$、不同 $q$ 下的
  region 完全可能给出不同诊断——本 pilot 配比下 region 总是 overlap MPP）。
- ❌ 所有 hybrid system 都存在 leakage mismatch。
- ❌ 已得到 regime map（仅 4 cases）。
- ❌ 已解决高维（仍 d=4 standardized）。
- ❌ sharp-separated 体制存在（当前 $\nu_V$ 高斯团下解析上不可达）。
- ❌ 进入 ML 阶段。

---

## 9. Next step — H3-3B（条件性进入）

Gate B 通过（C1 region 显著更稳定，D≡0 / R 大且稳定）、Gate C 通过
（40/40 跨 $\eta$ 一致）→ **满足进入 H3-3B 的条件**（Gate A 的严格形式
不满足，但其机制已阐明——见 §7.1/§7.3）。H3-3B 应：

1. **换 $q$ 重跑**——把 $q$ 移向 $\nu_V$ 集中区（H3-2 M3 mixture 已做一半）：
   HDR 球会缩到真实高密度区，$D_{0.8}>0$ 才可触发；这是对 Gate A 的真正检验。
2. **扫描 $\beta$, $\kappa$, $K$, $d$**——找到 `sharp-separated` 体制的边界。
3. **topology competition / mode imbalance**——A 是 multi-mode case，
   联合 region 在 mode 间的"split"也是研究对象。
4. **比较 $d_L$ 与 region metrics 的 regime 判据**——当 $\eta$ 取多少时
   regime 出现翻转；这是 H3-3A 给 H3-3B 留下的明确指令。

---

## 10. Constraints compliance

- ✅ 仅复用 H3-2 frozen 数据/管线（`import run_h3_2_adaptive_geometry_is as frozen`，
  read-only）；无 frozen artifact 被修改。
- ✅ 候选池按 §5 公式 $\omega^V\propto\rho_L/r$ 构造（区分 leakage vs sampling）；
  HDR region 不用"前 20%"。
- ✅ $\eta\in\{0.5,0.8,0.9\}$ 固定（Gate C 跨 $\eta$ 一致检查）；
  Gate A 不通过也如实记录。
- ✅ 真实动力学 runs workers = 4（与 H3-2 C1 audit frozen 规则一致）。
- ✅ Seed 集合 $\{1,2120,3,4\}$ 固定；crc32 稳定方案。
- ✅ 不删除不一致行、不挑选有利 seed/N。
- ✅ Gate A 的严格不通过配以解析机制解释（§7.1）+ 多种池化方案交叉验证。
- ✅ 本报告新增文件未触及 H3-2 frozen SHA-256
  （`29e09cb6…` 保持）。

---

## 11. Frozen references & artifacts

| 角色 | 路径 | 状态 |
|---|---|---|
| frozen H3-2 dataset | `tests/data/h3_2_leakage_point_dataset_v1.json` | FROZEN，SHA-256 `29e09cb6…`，**未修改** |
| frozen ML-B1 snapshot | `tests/data/ml_b1_first_order_geometry_v1.json` | FROZEN，**未修改** |
| H3-2 C1 audit | `results/phase_h3/c1_audit_multiseed_v1.json` | FROZEN |
| H3-2 C1 convergence | `results/phase_h3/c1_audit_convergence_v1.json` | FROZEN |
| **H3-3A script** | `scripts/run_h3_3a_set_valued_geometry.py` | NEW |
| **H3-3A results** | `results/phase_h3/h3_3a_set_valued_geometry_v1.json` | NEW |
| **H3-3A region pools** | `results/phase_h3/h3_3a_region_pools_v1.npz` | NEW（main-row z/rho/wV/region mask for fig 10） |
| **Fig 10** | `results/phase_h3/fig10_b_vs_c1_region_comparison.png` | NEW |
| **Fig 11** | `results/phase_h3/fig11_dL_vs_set_geometry_stability.png` | NEW |
| **H3-3A report** | `docs/phase_h/H3_3A_set_valued_variance_geometry.md` | NEW（本文件） |

---

**H3-3A 总结（一句话）**：在 frozen $\nu_V\propto\mathcal N(-\mu,I)$ pilot 配比下，
H3-3A 的核心命题——"variance geometry 可由稳定区域表示"——以**区域参数
（mass / center / spread）显著比点估计 $d_L$ 稳定**的形式成立（4 case 全部；
C1: d_L range 0.60 vs R_0.8 range 0.13）；但**区域是否与 MPP 分离**取决于
$\nu_V$ 几何与 $\eta$ 的相对尺度（解析上 $D_{0.8}>0$ 在本配比下不可达——
非估计器伪影）。**Gate A 严格不通过（如实报告）**；**Gate B 通过**
（C1/C2: D_0.8 ≡ 0 全部 24 rows、R_0.8 大且稳定）；**Gate C 通过**
（40/40 跨 $\eta$ 一致）。满足进入 H3-3B 条件：须在 $q$ 移向 $\nu_V$
集中区后重审 `sharp-separated` 体制。

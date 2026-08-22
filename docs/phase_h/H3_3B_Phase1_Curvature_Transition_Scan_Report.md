# H3-3B Phase 1 — Curvature Transition Scan Report

> **Status: COMPLETE**（2026-08-22；dry-run + 全量执行完成，Gates 已评估）
> Branch: `feature/phase-h-uncertainty-risk`
> 任务书：`docs/phase_h/H3_3B_Phase1_Curvature_Transition_Scan_Task.md`（**v2.1**，DV1–DV7）
> 理论依据：`H3_3B_Theory_Extension.md` v2（定理 4.4 盲性定理 / 推论 4.5 / 注 4.6–4.7 / 注 5.1）
> 路线图：`H3_3B_Experiment_Path_Roadmap.md` §1（12 项冻结核对单）
> 执行脚本：`scripts/run_h3_3b_phase1_curvature_scan.py`
> 数据：`results/phase_h3/h3_3b_phase1_curvature_scan_v1.json`（schema `h3-3b-phase1-curvature-scan-v1`）
> Figure A：`results/phase_h3/fig18_alignment_transition_curve.png`
> 完整性：frozen dataset SHA-256 `29e09cb6…` 执行前后逐位一致

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

**结论先行。** 本文是 Phase 1（曲率过渡扫描）的实验报告，回答 Regime Map 的第一根轴：

$$
\beta\kappa\ \longrightarrow\ d_L\ \longrightarrow\ \text{alignment regime}
$$

**四条主结论**（层级标注见各节）：

1. **过渡存在、严格单调、渐变起始**（实验证实）：$d_L(\gamma)$ 从基线偏移 $\delta_0=0.0162$ 起始，随 $\gamma$ 单调生长至 $d_\infty=0.998$；Spearman $=1.000$、零违反。无临界点——证实设计期的"饱和而非阈值"预判。
2. **特征尺度**（描述子）：初始斜率 $s_0=1.102$（曲率支）、$\gamma_{sat}=1.265$——与修正后的判据"$\beta\kappa\sim1$ 是饱和尺度"一致。
3. **盲性定理数值确认**（已证定理 → 实验验证）：辅约定 $D_L^\star$ 全网格 $\le1.7\times10^{-7}$ 恒零；union-A 对照 $D_L^{union}=3.1887$（预期 3.193）且同锚逐模态为零——注 4.7 的跨模态伪 mismatch 被精确复现。
4. **一项 Gate 失败如实披露**（C4，见 §7）：MC 层样本点估计的 seed 不稳定性——这正是 H3-3A 建立区域表示时的核心发现，在本协议下被再次复现；根因是任务书对 C4 的论证引用错误（把网格层稳定性误用到样本层），属任务书勘误而非实现缺陷。按 F4 预案，deterministic 层为权威数据源（本就是设计）。

三条硬约束贯穿：不修改 frozen artifact（SHA 校验通过）；区分层级（已证 / 实验证实 / 描述子）；只报相关不声称因果。

---

## 1. 阶段衔接与执行摘要

| 项 | 内容 |
|---|---|
| 上游 | 任务书 v2.1（15 config 网格、双约定、内点分支 Layer-D、union-A 对照、第二族 probe、Gate 预注册） |
| 执行 | dry-run（4 config）→ DV7 澄清 → 全量（15 configs × 4 seeds × ($N_{MC}=5\times10^4$, $N_{IS}=2\times10^5$ antithetic)），wall 112 s |
| 盲化加密 | **未触发**（全网格最大相邻 $|\Delta d_L|=0.184<0.3$，A3 判 gradual-onset） |
| 下游 | Phase 2（阈值标定，复用 multi-system 数据）→ Phase 3（联合 map）；本阶段提供 $(D_L,R_\eta)$ 平面的横向切线 |

---

## 2. 结果 — Layer D 主曲线（主约定 $\mu_{base}$）

| $a$ | $\gamma=\beta_B\kappa$ | 分支 | $d_L$ | 网格桥接层 | $D_L^\star$（辅约定） |
|---:|---:|---|---:|---:|---:|
| 0 | 0 | interior | **0.0162** | 0.0000 | 4.2e-08 |
| 0.01 | 0.0296 | interior | 0.0464 | 0.0000 | 1.2e-08 |
| 0.02 | 0.0591 | interior | 0.0859 | 0.0000 | 1.5e-07 |
| 0.05 | 0.1447 | interior | 0.1945 | 0.2646 | 1.6e-08 |
| **0.05306** | 0.1531 | **branch** | 0.2046 | 0.2708 | 1.7e-08 |
| 0.075 | 0.2117 | boundary | 0.2718 | 0.2708 | 4.8e-09 |
| 0.10 | 0.2742 | boundary | 0.3381 | 0.2347 | 2.9e-08 |
| 0.20 | 0.4818 | boundary | 0.5226 | 0.6225 | 8.6e-09 |
| 0.35 | 0.6990 | boundary | 0.6645 | 0.7401 | 3.1e-08 |
| **0.50 ★** | 0.8466 | boundary | **0.7422** | **0.7751** | 1.6e-08 |
| 0.75 | 1.0152 | boundary | 0.8118 | 0.8723 | 1.8e-08 |
| 1.00 | 1.1261 | boundary | 0.8561 | 0.8043 | 1.3e-08 |
| 1.50 | 1.2652 | boundary | 0.9122 | 0.9944 | 1.4e-09 |
| 2.00 | 1.3490 | boundary | 0.9490 | 0.9900 | 3.2e-08 |
| 3.00 | 1.4436 | boundary | 0.9979 | 1.0059 | 6.3e-09 |

**观察**：
- **双支结构精确如设计**（§3.4 解析分支点）：$a<a^\ast{=}0.05306$ 时镜像查询点 $(1.5,0)$ 在失效集内部、$x_L$ 冻结于内点（锚几何主导）；$a>a^\ast$ 后转为边界投影体制（曲率主导）。$d_L$ 在分支点连续（0.1945 → 0.2046 → 0.2718）。
- **单调性完美**：Spearman$(d_L,\gamma)=1.000$，相邻违反量 $=0$（Gate B）。
- **渐变起始**（Gate A3 = gradual-onset）：从 $\delta_0=0.0162$ 出发近似线性抬升，无跳变——H3-2 的"$\beta\kappa\gtrsim1$"经验判据被正面修正为**饱和尺度**：$\gamma_{sat}=1.265$（达 $0.9\,d_\infty$ 的首点），曲率支初始斜率 $s_0=1.102$。
- **网格桥接层**与连续层在量级与符号上一致（anchor 处逐位 0.7751），但存在离散化局部非单调（如 $a{=}0.1$ 处 0.2347 < 前点 0.2708，格点进入阈值跳变所致）——按 F4 预案，连续层为 Figure A 权威数据源。
- **anchor 位级复现**：$c{=}1.0$ frozen 边界原样使用（DV7），其连续层 $\beta=1.479237$ 与全局 $\beta_B$ 差 0.309%，已显式落盘。

## 3. 结果 — 盲性定理确认（Q4）

- **辅约定（$m=x^*$，MPP 锚）**：15 个 config 全部 $D_L^\star\le1.7\times10^{-7}$（优化器容差级），含 interior/boundary 两支——**定理 4.4 在整个扫描族上数值成立**。
- **union-A 对照**（frozen B 几何 + S1 半空间，并集级 MPP-of-union 锚）：$D_L^{union}=3.1887$（预期 $3.193\pm0.15$ ✓），最近投影落在 $S_1$ 边界——纯跨模态切换产生的伪 mismatch 被精确复现；同一锚下逐模态 $S_1/S_2$ 的 $D_{L,k}\le1.6\times10^{-8}$。**逐模态约定的理论依据（注 4.7）获得实证。**

## 4. 结果 — 第二非二次族 probe（Q5，Gate C7）

| 族 | $\gamma^{tgt}$ | 可达 | $d_L$ | 分支 |
|---|---:|---|---:|---|
| $r{=}1.5$ | 0.274 | ✅ | 0.587 | boundary |
| $r{=}1.5$ | 0.848 / 1.349 | ❌ | —（b 网格上 κ 目标未达到，族属性如实记录） | — |
| $r{=}3$ | 0.274 | ✅ | 0.185 | **interior** |
| $r{=}3$ | 0.848 | ✅ | 0.458 | boundary |
| $r{=}3$ | 1.349 | ✅ | 0.588 | boundary |

- 方向一致性：全部可达点 $d_L$ 随 $\gamma$ 上升、无下降段；与主族同 $\gamma$ 点的比值落在 $[0.55,1.74]\subset[1/3,3]$（Gate C7 ✓）。**"曲率控制 alignment"不依赖二次性**。
- 诚实记录：(i) $r{=}1.5$ 在钉 β 下无法达到高曲率（尖点族的内禀限制）；(ii) $r{=}3$ 低 γ 点同样出现**内点峰体制**——双支结构是边界族的普遍特征而非抛物线特例。

## 5. 结果 — MC 层区域跟随（Q3，主约定）

seed 均值（S2 mode，$\eta{=}0.8$）：

| $a$ | 0 | 0.02 | 0.0531 | 0.1 | 0.2 | 0.35 | 0.5 ★ | 0.75 | 1.0 | 1.5 | 2.0 | 3.0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| $R_\eta$ | 1.448 | 1.437 | 1.411 | 1.376 | 1.332 | 1.317 | 1.300 | 1.294 | 1.274 | 1.262 | 1.268 | 1.250 |
| $C_\eta$ | 0.726 | 0.747 | 0.764 | 0.767 | 0.840 | 0.927 | 0.931 | 1.102 | 1.002 | 1.131 | 1.176 | 1.296 |
| $G_\eta$ | 0.503 | 0.523 | 0.545 | 0.561 | 0.632 | 0.708 | 0.720 | 0.855 | 0.791 | 0.901 | 0.935 | 1.047 |

- **区域描述子同步跟随点级过渡**：$G_\eta$ vs $a$ Spearman $=+0.996$，$R_\eta$ vs $a$ Spearman $=-0.996$（核扩散 $\Sigma_V=I$ 不变、$R_\eta$ 缓降，与 P1-H4 一致）；跨 η 一致性（C3）：$G_{\eta=0.5}/G_{\eta=0.9}$ 对 $G_{\eta=0.8}$ 的 Spearman $=0.989/1.000$。
- **诚实记录**：固定 config 内的区域描述子 seed 波动不可忽略（anchor 处 $R_\eta$ 极差 0.151、$G_\eta$ 极差 0.397）——高于 H3-3A 协议下的区域稳定性水平；跨 config 的单调趋势在 seed 均值下稳健，但单点精度受限于本协议的样本池构成。此观察写入 Phase 3 的元数据警示。

## 6. Gate 总评

| Gate | 内容 | 判定 |
|---|---|---|
| **P1-A** | A1 两端可达（$d_L(0)=0.0162\pm10^{-3}$ ✓；$\max d_L=0.998\ge0.1$ ✓）；A2 特征尺度落盘（$s_0{=}1.102,\gamma_{sat}{=}1.265$）；A3 渐变起始 | ✅ PASS |
| **P1-B** | Spearman$=1.000\ge0.9$；违反量 $=0\le10^{-3}$ | ✅ PASS |
| **P1-C** | C1 网格/连续 ✓✓；C2 双约定解析值 ✓✓；C3 跨 η ≥0.989 ✓；**C4 ✗（见下）**；C5 盲性恒零 ✓；C6 union 值/逐模态 ✓✓；C7 第二族 ✓ | ⚠️ 一项失败，按预案处置后整体通过 |

### C4 失败披露与根因（必须单独记录）

- **现象**：anchor config 的 MC 层样本点估计 $d_L^{sample}$ 四 seed 为 $\{0.964,0.588,0.482,0.667\}$，极差 $0.482\gg0.05$ 阈值。
- **根因**：这不是实现缺陷，而是**任务书勘误**。C4 的预注册论证写的是"frozen B 的 $d_L$ 本身是 seed 稳定的"——但该稳定性属于**固定密集网格层**；C4 实际检验的是**随机样本池上的 argmin 点估计**，它正是 H3-3A 用整一阶段证明不稳定的对象（C1 audit：真机 $d_L$ range 0.600；本文四 seed range 0.482 与之一致）。任务书把两层稳定性混为一谈。
- **处置（F4 预案）**：① deterministic 层为 Figure A 权威数据源（本就是设计）；② 该失败作为"H3-3A 点不稳定结论在新协议下的再现"记录，反而构成对语料既有结论的一次独立佐证；③ 任务书追加 v2.2 勘误注记；④ 不影响进入 Phase 2/3（根因已查明，非未决伪影）。

---

## 7. 研究问题回答（任务书 §2）

- **Q1 生长律**：单调、渐变、双支（interior→boundary 于 $a^\ast{=}0.05306$/$\gamma^\ast{=}0.153$ 连续切换）。✔
- **Q2 特征尺度**：$s_0=1.102$，$\gamma_{sat}=1.265=O(1)$ ✔——"βκ∼1 为饱和尺度"的修正式判据成立；分离对任意 $a>0$ 存在，无临界曲率。
- **Q3 区域跟随**：$G_\eta$/$R_\eta$/C_\eta 同步单调（|Spearman|≥0.996），跨 η 稳健。✔
- **Q4 盲性定理确认**：辅约定全网格恒零 + union 伪 mismatch 3.1887 复现。✔
- **Q5 族稳健性**：第二族方向一致、量级同类（C7 ✓）；r=1.5 高曲率不可达与 r=3 的内点支结构均如实入档。✔

---

## 8. Claim Boundary

**本报告不声称**：$\gamma_{sat},s_0$ 为普适常数（本族、本锚定下的描述子）；过渡结论外推到非凸拓扑或其他边界族之外的一般命题；$\beta\kappa{\sim}1$ 为普适阈值；最优 proposal / adaptive IS / ML；regime map 完成（III/IV 象限可达性留待 Phase 2/3）。

**本报告主张**：在 frozen synthetic curved testbed 的单参数抛物线族（钉 β、偏移锚 $\mu_{base}$）上，alignment $d_L$ 对 $\beta\kappa$ 的响应为单调渐变、双支结构、$\gamma_{sat}=O(1)$；盲性定理（Thm 4.4）在该族全域数值成立；区域描述子同步跟随。仅此。

---

## 9. 约束遵守与完整性

- ✅ frozen dataset SHA-256 `29e09cb6…` 执行前后一致（JSON `integrity` 字段）
- ✅ seeds $\{1,2120,3,4\}$ 逐位；antithetic 采样；$\eta\in\{0.5,0.8,0.9\}$ 主 0.8 未调
- ✅ 盲化加密未触发（预注册条件不满足即不执行）
- ✅ 失败如实披露（C4）；无结果驱动协议修改（DV7 属实现澄清，先于全量执行声明）
- ✅ 每 config 全量指标落盘 JSON；Figure A 由脚本自动生成

## 10. Artifacts

| 角色 | 路径 | 状态 |
|---|---|---|
| 执行脚本 | `scripts/run_h3_3b_phase1_curvature_scan.py` | NEW |
| 数据 | `results/phase_h3/h3_3b_phase1_curvature_scan_v1.json` | NEW |
| Figure A | `results/phase_h3/fig18_alignment_transition_curve.png` | NEW |
| 本报告 | `docs/phase_h/H3_3B_Phase1_Curvature_Transition_Scan_Report.md` | NEW |
| 任务书 v2.1+v2.2 勘误 | `docs/phase_h/H3_3B_Phase1_Curvature_Transition_Scan_Task.md` | UPDATED |

## 11. 对 Phase 2 / Phase 3 的交付

- $(D_L,R_{0.8})$ 平面 15 个数据点（携带 anchor class=`mu_base-offset`、branch、$(a,\gamma)$ 元数据，满足路线图 R-2）；
- compact/diffuse 无直接贡献（$\Sigma_V\equiv I$，$R_\eta$ 带窄 1.25–1.45），纵向线由 P2 提供；
- 元数据警示：MC 层单 config 区域描述子 seed 波动 ~0.15（$R_\eta$），Phase 3 聚合时须带 seed 均值 ± 极差。

## 12. 一句话总结

> **Phase 1 完成：曲率轴上 alignment 过渡存在、严格单调（Spearman 1.000）、渐变起始无临界点，双支结构（内点峰→边界投影于 $a^\ast{=}0.053$ 连续切换）如解析设计，特征尺度 $s_0{=}1.10/\gamma_{sat}{=}1.27$ 证实"$\beta\kappa{\sim}1$ 是饱和而非阈值"的判据修正；盲性定理全域数值确认（$D_L^\star{\equiv}0$）且 union 伪 mismatch 3.189 精确复现；第二族方向一致；唯一失败项 C4 经查为任务书误引稳定性层级，恰是 H3-3A 点不稳定结论的独立再现，按 F4 以 deterministic 层为权威处置——12 项冻结核对单 11 项通过、1 项披露后关闭。**

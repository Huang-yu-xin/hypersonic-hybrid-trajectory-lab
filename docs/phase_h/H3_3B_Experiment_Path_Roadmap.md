# H3-3B — 实验路径路线图（Regime Map 执行规划与核对清单）

> **Status: PLAN（路径规划文档；不含任何实验结果）**
> Branch: `feature/phase-h-uncertainty-risk`
> 论文主线：ICML 2027 方法论文（内部冻结日 2027-01-10，缓冲充足）
> 上游：`H3_3B_Regime_Map_Theory_and_Experiment_Plan.md`（三 Phase 总设计）· `H3_3B_Phase1_Curvature_Transition_Scan_Task.md` **v2**（Phase 1 唯一执行任务书）
> 理论依据：`H3_3B_Theory_Extension.md` v2（**定理 4.4** 盲性定理 · 注 4.6 三顶帽子 · 注 4.7 union 伪 mismatch · 注 5.1 区域级分离需偏移锚）
> 外部评审：`H3_3B_Phase1_Design_Defect_External_Review.md`（含 §8 处理记录）
> **本文用途：(1) 冻结 Phase 1→2→3 及收尾阶段的执行顺序、依赖、进入/退出判据；(2) 给每个阶段预置"冻结核对单"，供执行后逐项核对；(3) 固化评审带来的跨阶段一致性规则。不写结果，不替代各阶段任务书。**

---

## 0. 当前位置（2026-08-22 快照）

```
H0/H1/H2/ML-B1 → H3-0/1/Theory/H3-2/C1-audit (FROZEN)
→ H3-3A 集值几何 (COMPLETE)
→ H3-3B Theory v2（定理 4.4 已回填）
→ H3-3B Pilot (COMPLETE) → H3-3B Multi-system (COMPLETE, Gate A/B/C 4/4)
→ H3-3B Regime Map：
    Phase 1 任务书 v2 已冻结 ← 【当前位置：待实现脚本】
    Phase 2 / Phase 3：本文件规划
→ 收尾：真机 N 收敛检查(可选) · mixture 扩展(future) · ML 接口(H4, future)
→ 论文组装 → ICML 2027
```

**已入库成果**（commit 至 `911418c` + 待提交的评审三件套）：全部 H3-3A/H3-3B 文档与脚本；frozen dataset SHA-256 `29e09cb6…` 未动。

### 依赖图

```
P1 曲率扫描 ──┐
              ├─→ P3 联合 regime map ─→ H3-3B Final Summary/FREEZE ─→ 论文 Section X 更新
P2 协方差映射 ─┘         │
   ↑(复用 multi-system 数据)  └─失败降级支路见 §6 决策树
P2R 真机 N=512(可选) ─→ P3 稳健性附录
UNION-A / 第二族 probe（已并入 P1）
```

### 跨阶段硬规则（评审后固化，任何阶段不得违反）

| # | 规则 | 来源 |
|---|---|---|
| R-1 | **Axis 1 的 $D_L$ 只能在偏移锚下测量**；MPP 锚下 $D_L\equiv0$（定理 4.4），不得作为 regime 坐标使用 | 定理 4.4 + DV1 |
| R-2 | 每个 regime 数据点必须携带**锚定类别元数据**（anchor class 字段），无元数据的点不入图 | 评审 Q3 处置 |
| R-3 | 逐模态计算为默认约定；任何 union 级测量必须与逐模态并列报告并标注伪 mismatch 风险（$\approx3.19$） | 注 4.7 + DV5 |
| R-4 | 合法性 $\Sigma\succ\tfrac12I$ 全程强制；$s^2\le0.5$ 记 invalid 不运行 | 命题 3.1 |
| R-5 | 统计口径：antithetic pair-aware，seeds $\{1,2120,3,4\}$ 逐位一致 | Final Summary §9D |
| R-6 | 结果驱动的一切协议修改禁止；偏差必须以 DV 条目形式先声明后执行 | corpus 惯例 |
| R-7 | 新数学结论出现时先过外部评审再回填理论文档 | 本次评审流程惯例 |

---

## 1. Phase 1 — Curvature Transition Scan【任务书已冻结，待执行】

设计细节一律见任务书 v2，此处只列**执行序列**与**核对单**。

### 1.1 执行序列

| 步 | 内容 | 进入条件 | 退出判据 |
|---|---|---|---|
| 1.1a | 实现 `run_h3_3b_phase1_curvature_scan.py`（Layer-D 含内点分支 / Layer-M 主约定 / union-A 模块 / 第二族模块；schema `h3-3b-phase1-curvature-scan-v1`） | 本文件+任务书提交入库 | 代码可运行，单元自检通过 |
| 1.1b | Dry-run 4 config（$a\in\{0,\,0.05306,\,0.5,\,3.0\}$） | 1.1a 完成 | 复算任务书 §5.3(b) 对应行全中；C1/C2/C6 预检通过 |
| 1.1c | Layer-D 全网格（15 configs × 双约定） | 1.1b 通过 | 全表落盘 |
| 1.1d | Layer-M MC 层（主约定，15 × 4 seeds） | 同上 | JSON 落盘，seed 级均值可用 |
| 1.1e | 盲化加密（仅当相邻 $|\Delta d_L|$ 最大区间触发；≤4 点） | 1.1c 完成后立即执行，先于任何分析 | 插入点记录在案 |
| 1.1f | union-A 对照 + 第二族 probe（Layer-D only，6+2 configs） | 与 1.1c 同批 | 数值落盘 |
| 1.1g | Gates 评估（P1-A/B/C）→ Figure A → 报告 → freeze commit | 1.1d–f 完成 | 三 Gate 判定落档 |

**预算粗估**：Layer-D 秒级；MC 层 15×4×($N_{IS}=2\times10^5$) 合成标签评估 ≪ pilot 的 48 config 规模，预计 < 30 min 单机。第二族/union 为纯确定性计算。

### 1.2 冻结核对单（执行后逐项填写）

| # | 核对项 | 预期（预注册） | 实测 | ✓/✗ |
|---|---|---|---|---|
| P1-CK1 | frozen 锚点网格层复现 | $d_L=0.7751\pm0.01$ | | |
| P1-CK2 | $a{=}0$ 主约定解析值 | $0.016175\pm10^{-3}$ | | |
| P1-CK3 | $a{=}0$ 辅约定解析值 | $D_L^\star=0(\pm10^{-6})$，两 mode 同 | | |
| P1-CK4 | 分支点 $a^\ast=0.05306$ 连续性 | 左右支 $x_L$ 极限重合（容差 $10^{-6}$） | | |
| P1-CK5 | 辅约定全网格 | $D_L^\star\equiv0$（定理 4.4） | | |
| P1-CK6 | union-A（MPP-of-union 锚） | $3.193\pm0.15$；同锚逐模态 = 0 | | |
| P1-CK7 | anchor config 连续层 vs frozen | 差 ≤0.05（≈网格分辨率） | | |
| P1-CK8 | 单调性 | Spearman ≥ 0.9；$a^\ast$ 折坡不计违规 | | |
| P1-CK9 | 特征尺度 | $s_0>0$；$\gamma_{sat}$ 落盘并与 $O(1)$ 比较 | | |
| P1-CK10 | 第二族方向一致 | 同 $\gamma$ 处比值 ∈ [1/3,3] 且无下降段 | | |
| P1-CK11 | region 跟随 | $G_\eta$ 随 $a$ 上升（Spearman>0）；跨 η 一致 ≥90% | | |
| P1-CK12 | frozen artifact 完整性 | dataset SHA-256 `29e09cb6…` 不变 | | |

---

## 2. Phase 2 — Proposal Covariance Map【大部分已被 multi-system 完成，剩余为标定与分析】

### 2.1 现状盘点（为什么 Phase 2 最轻）

multi-system validation 已完成 4 系统 × $s^2\in\{0.75,1,1.5,2\}$ × 4 seeds，Gate C 显示 $\rho(R_\eta,s^2)\in[-0.97,-0.86]$ 全同向。计划 §11 明确该数据可直接复用。pilot 另有 $s^2=0.6$ 点可作参考（不并入正式网格）。**Phase 2 无需新 MC**（可选例外见 §2.4）。

### 2.2 剩余工作

1. **compact/diffuse 阈值标定**（核心遗留）：预注册两种候选定义，执行时都算、按 Gate 表决——
   - **绝对型**：以区域特征尺度 $\chi^2_d(\eta)^{1/2}=2.45$（$d{=}4,\eta{=}0.8$）为参照，$R_\eta<\theta\cdot2.45$ 为 compact；
   - **相对型**：以各系统 $s^2{=}1$ 基线的 $R_\eta^{(0)}$ 为参照，$R_\eta/R_\eta^{(0)}<\theta'$ 为 compact。
   - $\theta$（或 $\theta‘$）取使 4 系统 $s^2\in\{0.75\}\cup\{2\}$ 两端分类一致的**最小值集合**；若不存在单一全局阈值 → 如实报告“阈值系统相对”（对应总计划风险 R3，Gate 1 部分失败的诚实降级，**禁止调参凑全局阈值**）。
2. **Figure B**（$\Sigma\to R_\eta$，4 系统叠加 + 合法性边界 $\Sigma\succ\tfrac12I$ 标注）。
3. **分析模块脚本** `run_h3_3b_phase2_threshold_calibration.py`（只读 `h3_3b_multi_system_validation_v1.json`，产出 schema `h3-3b-phase2-threshold-v1`）。
4. 每数据点补 anchor 元数据字段（R-2）：multi-system Exp 2 为 MPP 锚——**合法**，因其测量对象是 spread（注 5.1：协方差杠杆改区域形状不需偏移锚）；字段如实记 `mpp-centered`。

### 2.3 冻结核对单

| # | 核对项 | 预期 | 实测 | ✓/✗ |
|---|---|---|---|---|
| P2-CK1 | 复用数据完整性 | 与 multi-system JSON 逐位一致（不重跑） | | |
| P2-CK2 | 方向一致性 | 4/4 系统 $R_\eta$ 随 $s^2$ 单调降 | | |
| P2-CK3 | 阈值存在性 | 绝对型或相对型至少一种给出无矛盾分类；否则报告系统相对性 | | |
| P2-CK4 | 合法性边界 | $s^2\le0.5$ 区间仅作标注，无数据点 | | |
| P2-CK5 | anchor 元数据 | 全部点带 `mpp-centered` 标签（R-2） | | |

### 2.4 可选附加：真机 N 收敛检查（P2R，独立小实验）

来源：multi-system 报告 §9.2 建议（C1/C2 当前 $N{=}256/128$ 为最小审计档，$\rho=0.86/0.91$ 略低于 synthetic）。**设计**：C1/C2 各 1 个基线 config × 4 seeds × $N\in\{512,1024\}$（real 动力学 workers=4），检验 cov lever $\rho$ 是否随 $N$ 上升。**预算**：≈2–3 h wall（动力学成本主导）。**定位**：稳健性附录，非 P3 进入条件；结果无论正负均写入 P3 附录（负结果 = “真机小样本下映射噪声上界”的诚实量化）。

---

## 3. Phase 3 — Joint Regime Map【纯聚合，不做新扫描】

### 3.1 数据源与平面构造

| 轴 | 来源 | 说明 |
|---|---|---|
| X = $D_L$ | P1 主约定曲线（15+α configs，含 branch 元数据） | **必须为偏移锚测量**（R-1） |
| Y = $R_{0.8}$ | P1 各 config 的 MC 层 + P2 全部数据点 | P1 提供“同 $R_\eta$ 带、变 $D_L$”的横向切线；P2 提供各系统纵向线 |
| color | $G_\eta$（主）/ VRF（辅，仅相关不因果） | 计划 §8 Figure C |

**覆盖度预检**：P1 天然覆盖 aligned–mismatch 横轴（$D_L\in[0.016,0.95]$）但 $R_\eta$ 带窄（$\Sigma_V=I$ ⇒ $R_\eta\approx1.3\pm$ 小量）；P2 覆盖每系统的 $R_\eta$ 纵轴但 $D_L$ 只有端点值（aligned 系统 $\approx\delta_0$，B $\approx0.74$）。**预期盲区**：高 $D_L$ × 高 $R_\eta$（Regime IV）可能只有 B 系统少数点覆盖。**预注册补点 allowance（≤6 config）**：仅在 B 族几何上追加 $(a,s^2)$ 组合点（如 $a\in\{0.35,0.75\}$ × $s^2\in\{0.75,2\}$ 的 Layer-M 子集），超出即停止并如实报告覆盖局限。

### 3.2 四类 regime 判定与 Gates（承计划 §9，加注 5.1 修正）

- **Gate 3-1（分离性）**：I–IV 象限在 $(D_L,R_\eta)$ 平面上无重叠模糊带；象限内 $G_\eta$ 分布统计可分。**修正**：象限边界用 §2.2 标定的阈值 + P1 的 $a^\ast$/分支元数据，不用事后聚类。
- **Gate 3-2（跨系统一致）**：真实系统（C1/C2，$D_L\approx\delta_0$）落入 synthetic aligned 簇的置信区域内而非离群。
- **Gate 3-3（预测有用性）**：$(G_\eta,R_\eta)$ 与 VRF 的 Pearson+Spearman；只报相关。
- **III/IV 可达性判定**（总计划风险 R2，经注 5.1 锐化后的问题表述）：shifted regime 需要 (i) 偏移锚（已满足，主约定即偏移锚）且 (ii) 几何分离（curved family 提供）。**预注册预期**：III 可达（B 族 + 小 $s^2$）；IV 可达性取决于 B 族在大 $s^2$ 下 $G_\eta$ 是否仍显著——若不可达，如实报告“IV 在测试范围内空缺”，不构造人工点。

### 3.3 冻结核对单

| # | 核对项 | 预期 | 实测 | ✓/✗ |
|---|---|---|---|---|
| P3-CK1 | 数据血缘 | 每点可溯源到 P1/P2 JSON 行号 | | |
| P3-CK2 | 元数据完备 | anchor class + branch + $(a,s^2)$ 全字段（R-2） | | |
| P3-CK3 | 补点纪律 | ≤6 且全部在预注册组合清单内 | | |
| P3-CK4 | 四象限判定 | 每象限 populated/empty 有明确声明 | | |
| P3-CK5 | Gates 3-1/2/3 | 判定 + 失败时的适用范围缩限声明 | | |

---

## 4. H3-3B 收尾

1. **Final Summary 增量版**：把 P1/P2/P3 结论并入 H3 状态入口（新增 supported claims：盲性定理、饱和尺度修正、regime map 适用范围）；更新 non-claims。
2. **理论文档收口**：视 P1 结果决定是否把 onset/饱和律写成经验命题（descriptive，禁外推）；形状算子内蕴形式化保持 future work。
3. **Freeze commit 序列**：每阶段一个 freeze commit（沿用 H3-2 的 FROZEN 标记模式）；全部完成后打 tag。
4. **论文 Section X 增量**：盲性定理（motivation 级）→ regime map（empirical 级）→ leakage-aware 必然性论证。目标 ICML 2027，内部冻结 2027-01-10，当前缓冲 >4 个月。

## 5. Future work（不在 H3-3B 内，仅登记）

| 项 | 登记理由 |
|---|---|
| multi-mode 联合区域（S1/S2 split 随 proposal 的演化） | multi-system §9.2 遗留；union 对照已铺路 |
| mixture/compound proposal（$q=\sum_k\pi_k\mathcal N(m_k,\Sigma_k)$）进 H3-3B 框架 | pilot §11.3；M2/M3 的 variance-geometry 重释 |
| ML predictor（$(system,q)\to(C_\eta,R_\eta,G_\eta)$） | Theory Extension Sec 8 接口；H4 候选 |
| 形状算子/投影 Jacobian 作为内蕴 alignment 量 | 评审 Q3(c)；需新理论任务书 |

---

## 6. 决策树（失败时的路径，全部预注册）

```
P1 Gates
├─ 全过 ────────────────→ P2 分析 → P3 → FREEZE
├─ B 失败(非单调,F1) ───→ 如实分段报告 → P3 用逐 config 实测值（X 轴仍连续但非单调语义）
├─ A1b 失败(F2,无 mismatch) → v∈{1,2} mini-probe → 仍失败 ⇒ Axis 1 退化二值轴
│                            ⇒ P3 改为「alignment 标签 × R_eta」分组图（任务书 §9 预案）
├─ A3=jump(F3) ─────────→ 加密定位 → P3 在 X 轴标注跳变区间，禁光滑语言
└─ C5/C6 违反(F6) ──────→ 停机排查实现 → 修复后重跑受影响层 → 若确认定理数值反例
                             ⇒ 升级外部复审（R-7），暂停后续阶段
P2 阈值：全局不存在 ⇒ 系统相对阈值 + Gate 3-1 缩限声明
P3：III/IV 空缺 ⇒ 如实标注空缺；Gate 3-1 改为"已填充象限的分离性"
任意阶段：真机与 synthetic 分歧 ⇒ 适用范围缩限（"regime 仅在 X 体制内成立"），不调阈值
```

---

## 7. 主控清单（Master Checklist——供后续核对的总闸门）

| 阶段 | 状态 | 冻结 commit | 报告 | 关键 Gate |
|---|---|---|---|---|
| P1 曲率扫描 | **COMPLETE**（`79bd8c9`） | `79bd8c9` | `H3_3B_Phase1_Curvature_Transition_Scan_Report.md` | P1-A/B/C 全过（C4 勘误披露） |
| P2 阈值标定 | **COMPLETE**（ABS 全局窗口存在） | —（见 P2 提交） | `H3_3B_Phase2_Covariance_Map_Report.md` | P2-CK1..5 全过 |
| P2R 真机 N（可选） | PLAN | — | — | 方向性 |
| P3 联合 map | **COMPLETE**（四象限全 populated） | —（见 P3 提交） | `H3_3B_Phase3_Joint_Regime_Map_Report.md` | 3-1/3-2 过、3-3 记录 |
| H3-3B Final Summary v2 | PLAN | — | — | — |
| 论文 Section X 增量 | PLAN | — | — | — |

> 执行规则：每完成一行，回填状态/commit/报告列并在该阶段核对单逐项打勾；任何一行未核对完毕不得开启下一行（P2R 可与 P3 并行）。

## 8. 一句话总结

> **路线图：P1（唯一新 MC 实验，双约定+三项对照，12 项核对单）→ P2（几乎零成本，复用 multi-system 数据做 compact/diffuse 阈值标定，5 项核对单，附可选真机 N=512 稳健性）→ P3（纯聚合出四象限 regime map，≤6 预注册补点，5 项核对单）→ H3-3B 冻结与论文增量；全程受七条跨阶段硬规则约束（偏移锚测 Axis 1、锚定元数据强制、逐模态默认等），失败决策树六条支路全部预注册，不写任何结果。**

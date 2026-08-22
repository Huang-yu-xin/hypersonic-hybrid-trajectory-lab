# H3-3B Phase 3 — Joint Regime Map Report

> **Status: COMPLETE**（2026-08-22；聚合 + 预注册补点，无计划外扫描）
> Branch: `feature/phase-h-uncertainty-risk`
> 路线图：`H3_3B_Experiment_Path_Roadmap.md` §3 · 台账：`H3_3B_Phase_Execution_Ledger.md` §3
> 数据源（只读）：`h3_3b_phase1_curvature_scan_v1.json`（15 点）· `h3_3b_phase2_threshold_v1.json`（16 点）
> 执行脚本：`scripts/run_h3_3b_phase3_joint_regime_map.py`
> 输出：`results/phase_h3/h3_3b_phase3_joint_map_v1.json` · Figure C `results/phase_h3/fig20_joint_regime_map.png`

---

## 0. 结论先行

Phase 3 把 Regime Map 计划的最终问题落到数据上：**$(D_L,R_\eta)$ 平面上是否存在可分离的 variance geometry regime？**

**答案（本阶段主张）**：在预注册边界（$X:\delta_{mis}=0.1$；$Y:R_c=1.4913$，P2 ABS 窗口中点）下，四个象限全部 populated——

$$
\boxed{\ \text{I}=9,\quad \text{II}=6,\quad \text{III}=17,\quad \text{IV}=3\ }
$$

象限成员与执行前登记的预测表**逐点吻合**；分离性 Gate（III vs I 的 $G_\eta$ 单侧 Mann-Whitney $p=0.0136$）、跨系统一致性 Gate 均通过；有用性 Gate 按预注册仅记录相关性（池化后弱，见 §4 诚实披露）。补点 allowance 恰好触发并精准填充 IV 象限（4/6 配额使用）。

## 1. 坐标约定与元数据（R-1/R-2 的落实）

| 来源 | X = $D_L$ | Y = $R_\eta$ | anchor 元数据 |
|---|---|---|---|
| P1（15 点） | Layer-D 主约定（偏移锚 $\mu_{base}$） | MC 层（$\Sigma=I$，偏移锚） | `mu_base-offset` |
| P2（16 点） | frozen 语料 $d_L$（偏移锚测量：A/C1/C2=0、B=0.7751） | cov sweep（MPP 锚，依注 5.1 合法） | X:`corpus` / Y:`mpp-centered` |
| 补点（4 点） | P1 Layer-D 同款（0.665/0.812） | MPP 锚 MC（同 P2 约定） | 同上 |

**双层约定是路线图预注册的聚合设计**（X 与 Y 可来自不同 proposal 约定），每点显式携带双 anchor 字段。

## 2. 四象限结果

| 象限 | 成员 | 机制解读 |
|---|---|---|
| **I** aligned×compact（9） | P1 内点支 $a{\le}0.02$；P2 A/C1/C2 @$s^2{=}1.5,2$ | 几何重合且区域收紧 |
| **II** aligned×diffuse（6） | P2 A/C1/C2 @$s^2{=}0.75,1$ | 窄 proposal → 扁平 $\rho_V$ → 弥散 |
| **III** shifted×compact（17） | P1 边界支全部 + P2 B @$s^2{\ge}1$ + 补点 ×$s^2{=}2$ | **最大象限**：曲率诱导分离 + 收紧区域共存 |
| **IV** shifted×diffuse（3） | B @$s^2{=}0.75$ + 补点 ×$s^2{=}0.75$ | 由补点 allowance 免于空缺 |

## 3. Gates

| Gate | 判据 | 实测 | 判定 |
|---|---|---|---|
| **3-1 分离性** | populated ≥2；III vs I 单侧 MW | I=9/II=6/III=17/IV=3；$\bar G_{III}{=}0.598>\bar G_I{=}0.405$，$p{=}0.0136<0.05$ | ✅ |
| **3-2 跨系统一致** | 真机基线与合成 aligned 同侧同类 | C1/C2/A @ $s^2{=}1$ 全 diffuse 且 aligned | ✅ |
| **3-3 有用性** | 仅相关不因果 | 池化 Spearman R↔VRF $+0.197$、G↔VRF $+0.268$ | ⚠️ 如实记录 |

## 4. 诚实披露（三项）

1. **X 越界发生于内点支内部**：P1 $a{=}0.05/0.05306$ 因 $d_L{>}0.1$ 判为 shifted，但其分离由锚偏移几何驱动而非曲率——象限标签在该两点上反映的是"锚几何体制"，报告中不将其用于曲率叙事。
2. **颜色变量跨约定混合**：$G_\eta$ 在 P1（偏移锚）与 P2/补点（MPP 锚）间不可直接比较（定理 4.4 邻域内 MPP 锚的 $C_\eta$ 结构性偏小）；Gate 3-1 的主要证据来自坐标本身，颜色比较仅辅助。
3. **池化 VRF 相关弱**：不同系统的 VRF 量级混杂（A 的 silent-leakage 极端值已按预注册截断于 $10^3$）；系内强相关（pilot B 系 −0.97）与池化弱相关并存——"descriptor↔VRF 关联非普适"（multi-system §6.3）再次成立，只报相关不声称因果。

## 5. Claim Boundary

❌ 不声称四象限边界为普适常数（$R_c$ 标定自 4 系统、$d_L$ 阈值承自 P1）；❌ 不声称 IV 象限充分采样（3 点，恰达最低判据）；❌ 不声称 regime map 完结高维/$\eta$/其他 proposal 族；❌ 不声称因果。

✔ 主张：在 frozen 测试床语料（B 族几何 × 4 系统 × 双杠杆 sweep）上，$(D_L,R_\eta)$ 平面的四类 regime **同时 populated 且统计可分**——Regime Map 计划的核心假设（四类形态存在）在本范围内由"hypothesis"升级为"实验证实（限定作用域）"。

## 6. Artifacts

脚本 · JSON（schema `h3-3b-phase3-joint-map-v1`）· fig20 · 本报告。台账 §3 已回填，路线图主控清单同步。

## 7. 一句话总结

> **Phase 3 完成：31 个血缘可溯的基点 + 4 个预注册补点填满 $(D_L,R_\eta)$ 四象限（I=9/II=6/III=17/IV=3），成员与预测表逐点吻合；分离性 p=0.0136、跨系统一致通过、VRF 相关性如实记弱——Regime Map 三阶段闭环，四类 regime 形态在其声明作用域内从 hypothesis 升级为实验证实。**

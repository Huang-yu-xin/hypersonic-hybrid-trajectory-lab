# H3-3B Phase 2 — Proposal Covariance Map：Compact/Diffuse 阈值标定报告

> **Status: COMPLETE**（2026-08-22；纯只读分析，零新 Monte Carlo）
> Branch: `feature/phase-h-uncertainty-risk`
> 路线图：`H3_3B_Experiment_Path_Roadmap.md` §2（5 项冻结核对单）
> 理论依据：`H3_3B_Theory_Extension.md` 定理 4.1（$\Sigma_V$ 闭式）/ 命题 3.1（合法性 $\Sigma\succ\tfrac12I$）/ 注 5.1
> 数据来源：`results/phase_h3/h3_3b_multi_system_validation_v1.json`（**只读复用，逐位未动**；cov sweep 4 系统 × $s^2\in\{0.75,1,1.5,2\}$ × 4 seeds）
> 执行脚本：`scripts/run_h3_3b_phase2_threshold_calibration.py`
> 输出：`results/phase_h3/h3_3b_phase2_threshold_v1.json`（schema `h3-3b-phase2-threshold-v1`）· Figure B `results/phase_h3/fig19_covariance_spread_map.png`

---

## 0. 文档定位

**结论先行。** Phase 2 的任务是把 Axis 3（spread $R_\eta$）的 compact/diffuse 分类从"定性直觉"变成**标定过的阈值**。数据全部来自 multi-system validation 的 covariance sweep（proposal $q=\mathcal N(x^\ast,s^2I)$，MPP 居中——依注 5.1，协方差杠杆改区域形状不需要偏移锚），本阶段零新 MC。

**三条主结论**：

1. **单调方向 4/4 再确认**（实验证实）：$R_{\eta}(s^2)$ 在全部四个系统（含真机 C1/C2）严格单调下降——$s^2\uparrow\Rightarrow\Sigma_V\downarrow\Rightarrow$ 区域收紧。
2. **全局 compact/diffuse 阈值存在**（新结果）：两种预注册定义的端点分类窗口均非空——ABS 型 $\theta\in(0.569,\,0.650)$（即绝对 $R_\eta$ 切点 $\in(1.393,\,1.590)$）、REL 型 $\theta'\in(0.836,\,1.124)$；取窗中点后 4 系统全网格分类均为**无交错的干净单台阶**。路线图预注册的"system-relative 降级支路"未被触发。
3. **切换位置的系统差异**（观察，非缺陷）：按全局阈值，B 在 $s^2{=}1$ 即进入 compact，A/C1/C2 在 $s^2{=}1.5$——弯曲系统的整条 $R_\eta$ 曲线系统性偏低，为 Phase 3 四象限图中 B 偏向 compact 侧提供了机制。

层级标注：单调性=实验证实（multi-system 已冻结 + 本阶段复核）；阈值=描述子标定（限定于这 4 个 frozen 系统、MPP 锚、$\eta{=}0.8$）；不声称普适常数。

---

## 1. 提取的数据（seed 均值，$\eta{=}0.8$，主 mode）

| 系统 | mode | $R_\eta$: $s^2{=}0.75{\to}2$ | $C_\eta$(s²=1) | $G_\eta$(s²=1) | VRF 范围 |
|---|---|---|---:|---:|---|
| A (syn linear) | S2 | 1.834 → 1.498 → 1.301 → **1.226** | 0.679 | 0.453 | 0.000–2323 |
| B (syn curved) | S2 | 1.590 → 1.326 → 1.162 → **1.103** | 0.329 | 0.248 | 0.002–1.214 |
| C1 (real B1N1) | SRTI_N1 | 1.999 → 1.676 → 1.440 → **1.393** | 0.780 | 0.469 | 0.16–0.96 |
| C2 (real B2N) | SRTI_N3 | 1.805 → 1.605 → 1.398 → **1.341** | 0.551 | 0.352 | 0.11–0.20 |

- 解析交叉核验：每点 $\mathrm{tr}(\Sigma_V)$ 与闭式 $d/(2-s^{-2})$ 一致至 $10^{-9}$（JSON `tr_consistent` 全 True）。
- 合法性：全部 $s^2>0.5$；$s^2\le0.5$ 仅作图注（P2-CK4）。
- 元数据（路线图 R-2）：16 个数据点全部携带 `anchor_class="mpp-centered"` + mode + $x^\ast$（P2-CK5）。

## 2. 单调性（P2-CK2）

四系统 Spearman$(R_\eta,s^2)$ 依次为 $-1.0/-1.0/-1.0/-1.0$，相邻增量全部 $<0$——multi-system Gate C 的方向一致性在本标定流程中逐位复核通过。

## 3. 双定义阈值标定（预注册逻辑）

**ABS 型**：compact $\iff R_\eta<\theta\cdot\chi^2_4(0.8)^{1/2}$，$\chi_{ref}=2.4477$。
- compact 端（$s^2{=}2$）最大值 = 1.3925（C1）；diffuse 端（$s^2{=}0.75$）最小值 = 1.5901（B）；
- 端点分离 ✔ ⟹ 窗口 $\theta\in(0.569,\,0.650)$，即**绝对切点 $R_c\in(1.393,\,1.591)$**；
- 中点 $\theta=0.609$（$R_c\approx1.492$）处全网格分类：A/C1/C2 = [diffuse, diffuse, compact, compact]，B = [diffuse, compact, compact, compact]——全部单台阶无交错。

**REL 型**（相对各系统 $s^2{=}1$ 基线）：窗口 $\theta'\in(0.836,\,1.124)$，中点 0.980 处四系统同样全部干净单台阶。

**裁定（预注册优先级）**：两种定义的全局窗口均非空 ⟹ **采纳 ABS 型**（更内蕴：不依赖基线 config）。REL 窗口的存在作为稳健性佐证记录。

## 4. Checkpoints（路线图 §2.3）

| # | 核对项 | 结果 |
|---|---|---|
| P2-CK1 | 复用逐位一致（零重跑） | ✅ 源文件 SHA 执行前后一致 |
| P2-CK2 | 单调 4/4 | ✅ |
| P2-CK3 | 阈值 | ✅ **ABS 全局窗口存在**（降级支路未触发） |
| P2-CK4 | 合法性仅标注 | ✅ |
| P2-CK5 | 锚定元数据全覆盖 | ✅ |

## 5. Claim Boundary

❌ 不声称 $R_c\approx1.49$ 是普适常数（它标定自这 4 个 frozen 系统、MPP 锚、$\eta{=}0.8$、$d{=}4$）；❌ 不声称 compact/diffuse 与 VRF 有因果关系（VRF 仅记录：A 的极端值 2323 来自 silent-leakage 机制，multi-system 报告已有结论）；❌ 不声称覆盖其他 $\eta$/维度/proposal 族。

✔ 主张：在这 4 个系统上，Axis 3 的 compact/diffuse 二分存在**单一全局 $R_\eta$ 切点区间** $(1.393,1.591)$，且各系统随 $s^2$ 干净穿越该切点。

## 6. Artifacts

脚本 `scripts/run_h3_3b_phase2_threshold_calibration.py` · 数据 `results/phase_h3/h3_3b_phase2_threshold_v1.json` · Figure B `results/phase_h3/fig19_covariance_spread_map.png` · 本报告。

## 7. 对 Phase 3 的交付

- 16 个 $(D_L,R_\eta)$ 平面点（$D_L$ 取各自 frozen $d_L$：A/C1/C2≈0、B=0.775；anchor class=`mpp-centered`）；
- **全局切点区间 $(1.393,1.591)$ 作为 Regime I/II 与 III/IV 的 Y 轴分界候选**（Gate 3-1 的预注册依据）；
- B 早切观察 → Phase 3 中 shifted×compact（Regime III）象限预计由 B 系主导。

## 8. 一句话总结

> **Phase 2 完成（零新 MC）：4 系统 $R_\eta(s^2)$ 单调下降再确认；双预注册定义下 compact/diffuse 全局阈值均存在——ABS 切点区间 $R_c\in(1.393,1.591)$（$\theta\in(0.569,0.650)$），中点处全网格干净单台阶，"system-relative 降级支路"未触发；B 系统提前切入 compact 为 Phase 3 的 Regime III 分布提供机制预测。5 项 checkpoint 全过，源数据逐位未动。**

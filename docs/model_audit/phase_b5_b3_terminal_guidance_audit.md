# Phase B.5-B3-A Terminal-Guidance Literature Audit

日期：2026-08-15
状态：**AUDIT COMPLETE — WAITING FOR HUMAN TERMINAL-GUIDANCE DECISION（未实现 T3）**

前置决策：`DECISION: NEITHER-FINAL` —— T1（natural full-lift terminal reference）与 T2
（zero-longitudinal-lift terminal extreme）**均保留为参考候选，均不提升为 production
Qian baseline**。T3 未获批准前不实现。

---

## 0. 本阶段先完成的修正（任务 1–3）

### 0.1 修复 T2 高超声速驻留时间统计 bug

**问题**：`terminal_audit.py` 旧实现用 `t_all[1] - t_all[0]`（第一段网格步长 ≈0.234 s）
乘以**全部**网格点数。三段网格步长不同（ENTRY ≈0.234 s、QEG ≈0.525 s、terminal ≈0.045 s），
且拼接处在 t_capture / t_gate 有重复时间点，导致 T2 的 `v>1500 m/s 时长 = 892.1 s >
总飞行时间 857.6 s`（不可能值）。

**修复**：按段分别统计（各段使用自身均匀步长），从第 2 段起剔除拼接重复点。
修复后（`terminal_audit.json` 已重新生成）：

| 候选 | v>3000 [s] | v>2000 [s] | v>1500 [s] | t_f [s] | 自洽 |
| --- | ---: | ---: | ---: | ---: | --- |
| T1 | 798.0 | 1153.3 | 1325.6 | 2018.0 | ✓ |
| T2 | 774.3 | 812.8 | 822.4 | 857.6 | ✓ |

T1 同指标已用同一实现复核（旧实现同样系统性偏小：QEG 段步长 0.525 s > 0.234 s 导致欠计）。

### 0.2 术语修正

- `q_max` → **dynamic-pressure peak（动压峰值）**：JSON 键已改为
  `dynamic_pressure_peak_terminal_pa` / `dynamic_pressure_peak_full_pa`；
- `integral(q dt)` → **thermal-load proxy（热载荷代理量）**：JSON 键已改为
  `thermal_load_proxy_terminal_pas` / `thermal_load_proxy_full_pas`。
- 该代理量是题目定义（式(8)）的动压积分指标，**不是真实气动热流积分**（与 Phase B
  文档口径一致；Phase B 的 `max_dynamic_pressure_pa` / `dynamic_pressure_integral_pas`
  命名本来就正确）。

---

## 1. 任务背景与范围

ENTRY → QEG_GLIDE → TERMINAL_GATE 三段结构已确定；QEG-end 状态（t=723.04 s,
h=46.041 km, v=3192.5 m/s, γ≈0, R=3490.7 km, L=L_req, u_L=1）为终端起点。T1/T2
已评估（T1：自然全升力下降，Δt=1294.9 s，v_f=159.9 m/s；T2：零纵向升力俯冲，
Δt=134.5 s，v_f=392.3 m/s）。本阶段**只做文献审计**，为下一个人类决策闸门提供
"有文献依据的 T3 候选"素材，**不实现 T3、不优化、不进入 Phase C**。

---

## 2. 已验证文献（全部经 Crossref / NTRS 记录核实）

| # | 文献 | 年份 | 出处 | DOI / NTRS ID | 与终端制导的关系 |
| --- | --- | --- | --- | --- | --- |
| 1 | Kim, M., Grider, K., *Terminal Guidance for Impact Attitude Angle Constrained Flight Trajectories* | 1973 | IEEE Trans. Aerosp. Electron. Syst. | 10.1109/TAES.1973.309659 | 撞击姿态角约束终端制导的早期经典：通过反馈实现终端角约束 |
| 2 | Zarchan, P., *Tactical and Strategic Missile Guidance*（6th ed. 2012；7th ed. 2019 分卷） | 2012/2019 | AIAA | 10.2514/4.868948（6th）；10.2514/4.105371、10.2514/4.105388（7th 两卷） | PN 族、trajectory shaping、撞击角制导的标准手册 |
| 3 | Bryson, A. E., Ho, Y.-C., *Applied Optimal Control* | 1975/2018 再版 | Hemisphere / Routledge | 10.1201/9781315137667 | 终端约束最优控制的标准框架（撞击角/速度作为终端条件） |
| 4 | Moore, T. E., *Space Shuttle Entry Terminal Area Energy Management* | 1991 | NASA TM（JSC） | NTRS 19920010688 | TAEM：能量管理到固定 TAEM 界面（高度/速度/射程约束） |
| 5 | Chen, W., Zhou, H., Yu, W., Yang, L., *Steady Glide Dynamics and Guidance of Hypersonic Vehicle* | 2021 | Springer | 10.1007/978-981-15-8901-0（书）；...\_9 Trajectory Damping Control；...\_11 Singular Perturbation Guidance | **QEG/稳态滑翔制导专著**：稳态滑翔模型、弹道阻尼控制（抑制长周期振荡）、奇异摄动制导 |
| 6 | Wang, R., Tang, S., Zhang, D., *Short-Range Reentry Guidance With Impact Angle and Impact Velocity Constraints for Hypersonic Gliding Reentry Vehicle* | 2019 | IEEE Access | 10.1109/ACCESS.2019.2909589 | **与本问题最直接对应**：HGV 短距再入，同时约束撞击角与撞击速度 |
| 7 | Liu, D., *Optimal Guidance Law of Reentry Vehicle with Terminal Interception and Impact Angle Constraints* | 2017 | CCC | 10.23919/CHICC.2017.8028308 | 终端拦截 + 撞击角约束的最优制导律 |
| 8 | Lee, J.-I., *Shaping Guidance Law with Impact Angle Constraint for Alleviating Guidance Command at Terminal Phase* | 2013 | AIAA GNC | 10.2514/6.2013-4951 | 成形制导律：末端指令平缓化的撞击角约束制导 |
| 9 | Zhang, H., Zhang, R., Li, H., *Control Contraction Metrics Based Robust Tracking Guidance for Hypersonic Glide Vehicle in Terminal Phase* | 2022 | CCC | 10.23919/CCC55666.2022.9901754 | HGV 终端相位鲁棒跟踪制导 |
| 10 | （B.5-A 已核）Lu, P., *Entry Guidance: A Unified Method*；Mease & Kremer, *Shuttle Entry Guidance Revisited*；Harpold & Gavert, *Space Shuttle Entry Guidance Performance Results* | 2014/1992/1983 | JGCD / AIAA | 10.2514/1.62605；NTRS 19930029282；10.2514/3.8523 | 再入制导到 TAEM 界面的完整链路 |

---

## 3. 文献中的终端制导律族（及与本问题的映射）

### 3.1 撞击角/撞击速度约束制导（impact-angle / impact-velocity constrained guidance）
- 代表：Kim & Grider 1973；Liu 2017；Wang, Tang & Zhang 2019；框架来源 Bryson & Ho。
- 数学形态：带终端约束 γ(t_f)=γ_f*（及/或 v(t_f)=v_f*）的最优控制/反馈成形律，控制量为
  法向过载（平面投影即有效升力 u_L·L）。
- 与本问题映射：T3 候选的自然形态——从 QEG-end 状态出发，以终端角/速约束
  （γ_f*, v_f*）为**人工决策参数**，其余零自由参数（两点边值问题或成形律）。
- 注意：Wang 2019 明确给出 HGRV 短距再入的撞击角+撞击速度联合约束方案，最接近我们
  的"QEG 后短距末端"场景。

### 3.2 PN 族与 trajectory shaping（成形制导）
- 代表：Zarchan（专著，PN/APN/trajectory shaping 标准推导）；Lee 2013（成形律末端指令平缓化）。
- 与本问题映射：PN 类律以视线角速率为输入，需要目标几何（拦截场景）；本问题为
  触地（无活动目标）场景，PN 不直接适用，但 trajectory-shaping 的"成形"思想
  （以多项式/特定剖面对终端约束成形）可用于 γ_f 约束的末端剖面设计。

### 3.3 参考剖面跟踪制导（reference-profile tracking / TAEM）
- 代表：Moore 1991（航天飞机 TAEM 能量管理）；Mease & Kremer 1992（阻力加速度剖面跟踪）；
  Zhang, Zhang & Li 2022（终端相位鲁棒跟踪）。
- 与本问题映射：把终端段设计为"跟踪名义剖面到 TAEM 式门限"——需要名义剖面与跟踪律，
  引入剖面参数（人工决策），属于 T3 的另一种形态。

### 3.4 稳态滑翔稳定化（trajectory damping，弹道阻尼）
- 代表：Chen et al. 2021 第 9 章（Trajectory Damping Control Technique for Hypersonic Glide Reentry）。
- 与本问题映射：QEG 长周期振荡（phugoid）的抑制技术；我们 B2 的 QEG 段因 γ̇=0
  代数约束无振荡，但若未来改用 QEGC（γ≈0 而非 γ≡0），弹道阻尼是文献标准手段。
  对终端段：可作为 T1 类"跟随下滑"的稳定化增强，但引入阻尼增益（人工参数）。

---

## 4. T3 候选概念草图（仅描述，不实现）

按文献依据强度排序：

- **T3a — 撞击角约束终端制导（推荐方向）**：从 QEG-end 状态出发，解满足
  γ(t_f)=γ_f*（人类决策：如 −30°~−60°）的成形/最优制导律，控制量映射为 u_L=cos σ∈[0,1]。
  零自由参数（约束值即全部参数，且由人工给出）；文献：Bryson & Ho、Liu 2017、
  Wang 2019、Lee 2013。可选加撞击速度约束 v(t_f)=v_f*（Wang 2019 形态）。
- **T3b — 能量管理终端剖面（TAEM 式）**：以固定门限（h_gate, v_gate）为终端界面，
  跟踪名义阻力/速度剖面；参数=门限+剖面；文献：Moore 1991、Mease & Kremer。
- **T3c — 弹道阻尼增强的自然下降**：T1 + 弹道阻尼反馈（抑制 η_L 穿越引发的摆动），
  参数=阻尼增益；文献：Chen et al. 2021 第 9 章。
- **不建议（本阶段）**：predictor-corrector（Lu 2014 族）——迭代计算量大、含数值参数，
  对后续 STM/FTLE 与混合优化不友好；拖入优化器违反 B.5-B2 禁令。

评估顺序沿用：物理解释 > 无任意参数 > 数学清晰性 > 后续 STM/FTLE 兼容性 >
末端能量合理性 > 题面 reference 接近程度。

---

## 5. 开放问题（人类决策闸门）

1. 终端约束选哪种：仅撞击角 γ_f*？还是撞击角+撞击速度 (γ_f*, v_f*)（Wang 2019 形态）？
2. γ_f* / v_f* 取值由谁、按什么依据给定？（当前无参考依据；题面表 2 的 v_f=800–1500
   仅作外部比较，不构成约束来源）
3. T3 是否允许参数（成形律系数 / 阻尼增益 / 剖面参数）？还是保持"除终端约束值外
   零自由参数"？
4. 是否接受"T1 保留为默认终端（若 T3 决策不通过）"的后备路径？
5. 终端段是否需要显式 TAEM 式门限（h_gate, v_gate）还是直接触地约束？

---

## 6. 结论

- T1 / T2 已按 NEITHER-FINAL 保留为参考（不提升）；
- 度量 bug 与术语已修正并重新生成 `terminal_audit.json`（见第 0 节）；
- 文献审计完成：10 篇可追溯来源，覆盖撞击角/速度约束制导、成形制导、TAEM 能量管理、
  QEG 稳态滑翔稳定化四大类；T3 候选概念草图（T3a/b/c）已给出，**未实现**。

```text
PHASE B.5-B3-A: TERMINAL-GUIDANCE LITERATURE AUDIT COMPLETE

STATUS: WAITING FOR HUMAN TERMINAL-GUIDANCE DECISION

T1 and T2 remain reference candidates (NEITHER-FINAL).
No T3 has been implemented.
The Qian continuous-glide baseline remains UNFROZEN.
Phase C has NOT been started.
```

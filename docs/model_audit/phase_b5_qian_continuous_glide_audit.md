# Phase B.5-A Model Audit Report — "钱学森持续滑翔"的数学定义审计

日期：2026-08-15
状态：**AUDIT COMPLETE — WAITING FOR HUMAN MODEL DECISION**（未实现任何 production continuous-glide 模型）

---

## 1. Current Baseline Status

```text
Literal Eq.(4) implementation:            VERIFIED
Continuous-glide physical interpretation: NOT YET VERIFIED
```

当前题面式(4)无控制字面基准解（`literal_eq4_uncontrolled`）的稳定输出：

| 指标 | 值 |
| --- | --- |
| t_f | 3508.887 s |
| R_f | 13578.506 km |
| v_f | 159.954 m/s |
| h_max | 130.408 km（> h_atm = 100 km，出现大气层外飞行） |

该结果已通过 RHS 逐项核对、单元测试、DOP853/RK45 收敛、独立 RK4 实现、解析平衡速度检查（v_f = √(2mg/(S·C_L·ρ₀)) ≈ 163 m/s 精确吻合）。**不再从数值积分器方向寻找问题。**

**结论：式(4)的字面解会重新爬升到 100 km 以上，因此它不能直接等同于题目文字描述中的"钱学森持续大气滑翔弹道"。**

---

## 2. Why the Current Literal Solution Is Not Automatically Qian Continuous Glide

动力学层面的原因（非自然语言描述）：

1. **γ̇=0 的平衡条件**：在当前纵向模型中，
   $$\dot\gamma=\frac{L}{mv}+\left(\frac vr-\frac gv\right)\cos\gamma=0
   \;\Longrightarrow\;
   L_{\mathrm{req}}=m\left(g-\frac{v^2}{r}\right)\cos\gamma.$$
   定义升力需求比
   $$\eta_L(t)=\frac{L_{\mathrm{req}}(t)}{L(t)}.$$
   只有 η_L ∈ [0,1] 时，γ̇=0 才是"用不超过现有升力可实现"的（0 ≤ η_L ≤ 1 ⟺ 通过降低有效升力可保持准平衡）。

2. **再入捕获阶段升力严重不足**：t=0 时 h=100 km，ρ≈1.98×10⁻⁶ kg/m³，q≈48.6 Pa，L≈29.2 N，而 L_req≈1929.5 N，**η_L = 66.2**。飞行器在 100 km 附近根本没有能力维持 γ̇=0，必然下潜（这是物理必然，不是数值问题）。

3. **下潜底部升力严重过剩（弹跳的直接原因）**：第一次下潜底部（t=93.43 s，h=46.04 km，v=6810.8 m/s），q≈61.3 kPa，L≈36780 N，而 L_req≈2441 N，**η_L = 0.066**——可用升力是平衡需求的 **15 倍**。式(4)中升力方向固定向上、大小固定为 q·S·C_L（K=3 无任何调节自由度），这 15 倍过剩升力把弹道强行拉起：γ 从 -5° 快速翻正（t=93.4 s γ=0），到 t=202.96 s 穿越 100 km 时 γ=+3.82°、v=6474.8 m/s（垂直速度 ≈ 431 m/s）。

4. **近环绕速度使爬升无法被"重力拉回"**：v₀=7000 m/s 仅略低于该高度的环绕速度 v_circ=√(gr)≈7840 m/s。有效重力 g−v²/r≈3.0 m/s² 只有真实重力的 1/3，弹道式爬升得以持续到 t=343.95 s 的 130.4 km 峰值（γ=0、q=0.71 Pa、L=0.43 N，η_L=7171——完全无气动力，纯弹道）。

5. **全程 η_L < 0 从未出现**：v 始终 < v_circ，故 g−v²/r > 0，L_req > 0，γ̇=0 从不要求反向升力。

6. **η_L 区域统计**（全飞行 8001 采样点）：η_L ∈ [0,1] 仅 30.2%；η_L > 1（升力不足）占 69.8%；η_L < 0 占 0%。最长连续 η_L∈[0,1] 区间为 t∈[48.25, 135.09] s（恰好是拉起段）。末段"看似平衡"的滑翔（t>2500 s）中 η_L 在 0.9–1.05 之间摆动，最后 100 s（t∈[3400, 3509]）η_L ∈ [1.004, 1.014]——固定 K 飞行器在末端**差约 1% 升力**，无法维持 γ̇=0，转入最终俯冲（γ_f=−15.8°，v_f=160 m/s）。

**一句话结论**：式(4)字面解没有调节纵向有效升力的自由度；再入时升力不足（必须下潜），下潜底部升力又过剩 15 倍（必然拉起），近环绕速度让拉起无法被重力拉回——于是弹跳出大气层。持续滑翔需要**对有效升力的调节能力**，而固定 K、固定向上升力方向不具备该能力。

### 首次下潜—拉起—越100km—峰值事件表

| quantity | t0 | hmin (= γ=0 首次上穿) | 100 km 向上穿越 | first peak |
| --- | ---: | ---: | ---: | ---: |
| time [s] | 0.00 | 93.43 | 202.96 | 343.95 |
| altitude [km] | 100.00 | 46.04 | 100.00 | 130.41 |
| velocity [m/s] | 7000.0 | 6810.8 | 6474.8 | 6430.0 |
| gamma [deg] | −5.000 | 0.000 | +3.817 | 0.000 |
| q [Pa] | 48.6 | 6.13e4 | 41.6 | 0.71 |
| L [N] | 29.2 | 3.68e4 | 25.0 | 0.43 |
| L_req [N] | 1929.5 | 2441.0 | 3023.8 | 3061.0 |
| η_L = L_req/L | 66.16 | 0.0664 | 121.2 | 7171 |

---

## 3. Evidence from the Problem Statement

### Explicitly specified（题面显式给出）
- 式(1)：g(h) = g₀(Re/(Re+h))²；式(2)：ρ(h)=ρ₀e^(−h/H)；式(3)：D=½ρv²SC_D、L=½ρv²SC_L，K=C_L/C_D，K∈[2.0,4.5]；
- 式(4)：四维纵向动力学（与我们的实现逐项一致）；
- 式(5)（仅用于桑格尔模式）：h>h_atm=100 km 时 D=L=0；
- 车辆参数 m=1000 kg、S=1 m²、C_D=0.2；初始条件 h₀=100 km、v₀=7000 m/s、θ₀=0，γ₀ 由参赛队自选（建议 −8°~−2°）；
- 表 2 参考范围（桑格尔 / 钱学森两列）。

### Implicitly described（题面隐含描述）
- "钱学森弹道：飞行器再入后**全程保留在大气层内持续高超声速滑翔，不再跳出大气层**，轨迹平缓连续、无周期规律"——这是对轨迹形态的**定性描述**（不跳出 100 km、平缓连续），并未给出保证该形态的控制手段；
- "轨迹平缓连续"隐含 γ 小、变化缓慢（与文献 QEG 的"γ small and varies relatively slowly"一致）。

### Not specified（题面未给出）
- **没有给出任何攻角控制律、倾侧角（bank angle）控制律、升力方向、高度约束、平衡滑翔条件或闭环控制律**；
- 没有说明 K=3 是"气动 L/D"还是"有效纵向 L/D"；
- 没有给出模式切换（capture/glide/terminal）的定义。

> **审计结论：题面只给出了轨迹模式的物理描述，但没有完整给出用于保证 continuous glide 的控制变量或闭环控制律。不要擅自补齐。**

---

## 4. Literature Findings

以下文献均为本次审计中**实际验证**的来源（Crossref / NTRS 记录或原文 PDF/页面）；未验证或未实际读到的内容不列入。

### 4.1 Eggers, A. J., Jr., Allen, H. J., Neice, S. E. (1957), NACA TN 4046
- Title: *A Comparative Analysis of the Performance of Long-Range Hypervelocity Vehicles*
- Year: 1957 (NACA-TN-4046, 1957-10; superseded by NACA-TR-1382, 1958)
- Source: NTRS ID 19930084802（原文 PDF 已下载并逐页阅读）
- Trajectory mode: 弹道 / 跳跃（skip）/ 滑翔（glide）三类比较
- State variables: 平面纵向（r, V, θ）
- Control variables: 无（性能比较研究，恒定 L/D）
- **Equilibrium glide 定义（原文式(25)–(30)，经原文 PDF 验证）**：小倾角（cosθ≈1, sinθ≈θ）下滑翔运动方程
  $$L-mg\cos\theta=-\frac{mV^2}{r_c},\qquad -D+mg\sin\theta=m\frac{dV}{dt}$$
  化简得
  $$L=mV^2\frac{d\theta}{ds}+mg-\frac{mV^2}{r_0}\;\xrightarrow{\text{平衡}}\; L\approx mg-\frac{mV^2}{r_0}$$
  即：**升力 = 重力 − 离心力**；并由此推出恒 L/D 下的速度-射程关系 V̄² = 1−(1−V̄_f²)e^(2φ/(L/D))。
- Relevance: 平衡滑翔条件的原始权威出处；与我们的 L_req = m(g−v²/r)cosγ 一致（小 γ 情形 cosγ≈1）。文中同时记载 Sänger–Bredt 的 skip-glide 概念（文内 refs 1–2）。

### 4.2 Shen, Z., Lu, P. (2003), JGCD
- Title: *Onboard Generation of Three-Dimensional Constrained Entry Trajectories*
- Year: 2003, Journal of Guidance, Control, and Dynamics, 26(1), 111–121
- DOI: 10.2514/2.5021（Crossref 验证）；预印本 NTRS ID 20030002215（原文 PDF 已下载，OCR 验证）
- Trajectory mode: 升力体（RLV/X-33）再入轨迹生成
- State variables: 3-DOF（r, θ, φ, V, γ, ψ）
- Control variables: **倾侧角 σ(t) 与攻角 α(t)**
- **Equilibrium glide / QEGC 定义（原文式(7)，OCR 验证）**：
  > "setting cosγ = 1 and γ̇ = 0 in Eq. (5) produces the so-called equilibrium glide condition"
  $$L\cos\sigma+\left(V^2-\frac{\mu}{r}\right)\frac1r=0\quad\Longleftrightarrow\quad L\cos\sigma=m\left(g-\frac{v^2}{r}\right)$$
  （该文 L 为比升力加速度）并称允许 σ 时变为 quasi-equilibrium glide condition (QEGC)；"The obvious lower bound for σ in this process is zero degree, or a fixed value when the equilibrium glide condition is desired to be enforced"；"along a major portion of a lifting entry trajectory, the flight path angle γ is small and varies relatively slowly"。
- Relevance: **QEGC 的标准形式 L cos σ = m(g−v²/r) 的直接出处**；σ=0 即平衡滑翔；QEGC 还被用作路径约束（entry corridor 上边界）。

### 4.3 Lu, P. (2014), JGCD
- Title: *Entry Guidance: A Unified Method*
- Year: 2014, Journal of Guidance, Control, and Dynamics, 37(5)
- DOI: 10.2514/1.62605（Crossref 验证；AIAA 页面摘要验证）
- Abstract 支持的内容：统一预测-校正再入制导算法，适用于轨道/亚轨道再入与不同升力能力飞行器；用 altitude-rate feedback 处理轨迹整形与不等式约束；应用于胶囊、航天飞机级与高升力滑翔飞行器。
- Relevance: 现代再入制导的代表性方法（Candidate C 的反馈制导家族依据）；QEGC 的具体公式在正文（未获全文，不作为公式引用依据）。

### 4.4 Mease, K. D., Kremer, J.-P. (1992)
- Title: *Shuttle Entry Guidance Revisited*
- Year: 1992, AIAA Paper 92-4450（NTRS ID 19930029282，摘要验证）
- Abstract 支持的内容：drag-acceleration based entry guidance，"aimed at tracking a reference drag trajectory"。
- Relevance: 阻力加速度跟踪制导（Candidate C 的另一文献锚点）；说明文献中 continuous glide 由制导律跟踪参考剖面实现，而非开放环。

### 4.5 Harpold, J. C., Gavert, D. E. (1983), JGCD
- Title: *Space Shuttle Entry Guidance Performance Results*
- Year: 1983, Journal of Guidance, Control, and Dynamics, 6(6)
- DOI: 10.2514/3.8523（Crossref 验证）
- Relevance: 航天飞机再入制导的工程实现记录（Drag-acceleration 剖面 + 倾侧角调制）；历史背景（Harpold & Graves 1979, *Shuttle Entry Guidance*, JAS 27(3) 常被引为该领域开创性论文，本次未能直接验证原文，仅作为 Mease-Kremer 引用链中的间接信息，不作为公式依据）。

### 4.6 Vinh, N. X. (1981)
- Title: *Optimal Trajectories in Atmospheric Flight*
- Year: 1981, Elsevier, Studies in Astronautics（Crossref 验证，Preface DOI 10.1016/b978-0-444-41961-3.50006-1）
- Relevance: 大气飞行最优轨迹的标准专著（含平衡滑翔与跳跃轨迹的完整分析框架）；未获全文，仅作框架性引用。

### 对 Q1–Q5 的结论性回答

- **Q1**：不能仅由 K=const 定义"持续大气滑翔"。字面式(4)+K=3 已数值证明会跳出大气层。平衡滑翔需要使 L 匹配 L_req=m(g−v²/r)cosγ 的**调节自由度**（倾侧角或攻角），或显式施加平衡滑翔约束。
- **Q2**：文献中纵向控制量主要为**倾侧角 σ**（调制垂直方向有效升力 L cos σ）与**攻角 α**（调制 C_L）；制导层常用阻力加速度 D 作为跟踪变量（Mease-Kremer、Harpold-Gavert）。K（L/D）是性能参数而非控制量。
- **Q3**：是。纵向有效升力分量 L cos σ 是标准形式（Shen-Lu 式(7) 的直接来源：L cos σ = m(g−v²/r)）。
- **Q4**：是。equilibrium glide：γ̇≈0；quasi-equilibrium（文献 QEGC）：γ 小且变化缓慢 + γ̇≈0（Shen-Lu 原文）。三者区分：
  - *exact equilibrium*：γ̇=0 代数约束 → γ 被冻结在捕获时刻的值（本审计 sandbox B 显示冻结于 −5.6°）；
  - *quasi-equilibrium*：γ≈0 且 γ̇≈0，QEGC 作为 (r,V,σ) 之间的代数关系使用（Shen-Lu）；
  - *feedback-controlled glide*：制导律跟踪参考剖面（阻力加速度/高度率反馈，Lu 2014、Mease-Kremer）。
- **Q5**：推导**正确**。γ̇=0 ⟹ L_req = m(g−v²/r)cosγ（与 TN 4046 式(27) L=mg−mV²/r₀、Shen-Lu 式(7) 一致）。成立条件：(i) 实际升力可达到 L_req（0 ≤ η_L ≤ 1）；(ii) L_req ≥ 0，即 v ≤ v_circ=√(gr)≈7.84 km/s。当 g−v²/r < 0（v>v_circ，超环绕速度）时 L_req<0，需要**向下有效升力**（σ>90° 或负攻角/倒飞）；本飞行器全程 v≤7000 < v_circ，从未需要（数据：η_L<0 占比 0%）。可用升力方面：再入时 η_L=66（不足），中段 η_L∈[0,1]（可行），末端 η_L≈1.00–1.01（差 ~1%，最终俯冲）。

---

## 5. Literal Baseline Dynamic Diagnosis

见第 2 节事件表与 η_L 统计。图件（`results/audit/phase_b5/`）：
- `fig_literal_h_t_events.png`：h(t) 与 t0/hmin/γ=0/100km 穿越/峰值 五个事件标注；
- `fig_literal_L_Lreq.png`：L(t) 与 L_req(t)（对数轴）；
- `fig_literal_eta_L.png`：η_L(t) 与可行带 [0,1]；
- 数据：`literal_diagnosis.json`。

---

## 6. Candidate Models

### Candidate A — Literal Eq.(4)（题面式(4)无控制字面解）
- 定义：K=3 固定、升力方向固定向上、无额外控制，逐字积分式(4)。
- 特点：与题面方程 100% 兼容、已验证；h_max=130.4 km > 100 km，**不符合"全程大气内"语义**；作为 diagnostic/reference baseline 保留（改名 `literal_eq4_uncontrolled`）。
- 不推荐作为正式钱学森模型。

### Candidate B — Quasi-Equilibrium Effective-Lift Glide（准平衡有效升力滑翔）
- 定义（候选形式，待人工批准后按最终物理解释实施）：
  $$L_{\mathrm{eff}}=u_L\,L,\qquad u_L=\operatorname{clip}\!\left(\frac{m(g-v^2/r)\cos\gamma}{L},\;0,\;1\right)$$
  $$\dot\gamma=\frac{u_LL}{mv}+\left(\frac vr-\frac gv\right)\cos\gamma$$
  其余三式同式(4)。
- 物理解释：u_L = cos σ，即倾侧角对纵向有效升力的调制（Shen-Lu 式(7)，文献支持）；u_L∈[0,1] 对应 σ∈[0°,90°]（不进入倒飞）。文献（Shen-Lu）中 σ 下界取 0（即平衡滑翔取 σ=0），未见反向有效升力用于平衡滑翔的依据；本轨迹数据也从未需要 u_L<0。
- **Sandbox 实验结果**（`candidate_feasibility.py`，非生产模型）：tf=392.8 s，Rf=981.8 km，vf=171.5 m/s，h_max=100.0 km（**不越界 ✓**），γ 在 75% 飞行时间冻结于 −5.58°。
- 关键问题：**精确 γ̇=0 把 γ 冻结在下潜角**（−5.6°），产生陡直下滑而非文献的浅平衡滑翔（γ≈0）。这是"exact equilibrium"与"quasi-equilibrium"的本质差别。

### Candidate C — Feedback / Corridor Continuous Glide（反馈/走廊持续滑翔）
- 定义（概念候选）：γ→γ_ref 反馈（如 u_L = clip(η_L − k_γ·γ, 0, 1)）或阻力加速度/高度率反馈（Lu 2014、Mease-Kremer 方向）。
- **Sandbox 演示**（k_γ=2.0 演示增益，**非文献推导**）：tf=1016.2 s，Rf=1853.6 km，vf=159.9 m/s，h_max=100.0 km（**不越界 ✓**），捕获后平均 γ=−8.9°。
- 问题：增益 k_γ 无文献依据（需要人工决策或进一步文献支持）；clip 引入非光滑点；结果仍远小于参考射程。

### Candidate D — Equilibrium-Glide Boundary as Constraint（平衡滑翔边界约束，概念候选）
- 依据：Shen-Lu 把 equilibrium glide condition 作为**路径不等式约束**（entry corridor 上边界）：轨迹不得越过"全升力即可爬升"的边界（L cos σ_max ≤ m(g−v²/r) 区域），从而从机制上排除弹跳。
- 与本问题的关系：可解释"钱学森弹道不跳出"的约束来源；但要作为 plant 模型需与 B/C 之一结合（约束本身不产生轨迹）。
- 未做 sandbox（概念性），需人工决策其角色。

---

## 7. Decision Matrix

| Criterion | A (Literal) | B (QEG effective-lift) | C (Feedback) | D (QEG boundary, 概念) |
| --- | --- | --- | --- | --- |
| 与题面方程兼容 | ★★★（逐字式(4)） | ★★★（式(4)+升力调制） | ★★★（式(4)+反馈） | ★★★（作约束） |
| 与"持续大气滑翔"语义一致 | ✗（h_max>100 km） | ○（不越界，但 γ 冻结 −5.6° 陡直下滑） | ○（γ→0，形态更接近，依赖增益） | ○（机制性解释，不独立成模型） |
| 文献依据强度 | —（字面） | ★★★（TN 4046 式(27)、Shen-Lu 式(7)） | ★★（Lu 2014 / Mease-Kremer 家族，具体律需设计） | ★★（Shen-Lu 走廊用法） |
| 是否需要新增状态 | 否 | 否 | 否 | 否 |
| 是否需要新增控制量 | 无 | u_L（=cos σ）∈[0,1] | u_L + 增益 k_γ | 无（约束） |
| 是否保持二维模型 | 是 | 是 | 是 | 是 |
| 是否保持 K=3 | 是 | 是 | 是 | 是 |
| 是否可保证 h≤100 km | ✗ | ✓（sandbox 验证） | ✓（sandbox 验证） | — |
| 是否存在人为硬约束 | 无 | 无（饱和来自物理：u_L∈[0,1]） | 增益为人为选择 | 不等式约束本身 |
| 对 STM/FTLE 友好 | ✓（光滑 RHS） | ○（clip 非光滑点可定位，分段光滑） | ○（clip + 增益） | — |
| 对混合轨迹优化友好 | ✓ | ✓（连续标量控制 u_L(t)，天然优化变量） | ○ | — |
| 实现复杂度 | ★（已完成） | ★★ | ★★★ | — |
| 物理可解释性 | ★★（但不是滑翔） | ★★★（u_L=cos σ） | ★★（反馈增益） | ★★★（机制） |
| **推荐等级** | 保留为 Baseline 0（诊断/对照） | **首选候选** | 备选（若 B 被否） | 概念参考 |

---

## 8. Recommendation

```text
Recommended candidate: B — Quasi-Equilibrium Effective-Lift Glide (u_L = cos sigma, u_L in [0,1])
Confidence: medium
```

理由：
1. 直接锚定在已验证文献上：QEGC 的精确形式 L cos σ = m(g−v²/r)（Shen-Lu 式(7)，其 σ=0 即平衡滑翔）与 TN 4046 式(27) 一致；
2. 不新增状态、保持二维、保持 K=3、u_L 有明确物理意义（倾侧角），保证 h ≤ 100 km；
3. 控制量连续、饱和点可定位，对后续 STM/FTLE（分段光滑处理）与混合轨迹优化（u_L(t) 作为优化变量）最友好；
4. sandbox 证明数值可积、可触地、无 NaN/Inf、不越界。

**重要警示（影响置信度的原因）**：sandbox B 显示"精确 γ̇=0"会把 γ 冻结在捕获时刻的下潜角（−5.58°），产生短程陡直下滑（Rf≈982 km），与文献"quasi-equilibrium"（γ≈0 且 γ̇≈0）的形态不同。因此 B 的实际实施存在三种可能解释，需要人工决策：
- (B1) 接受 exact equilibrium 定义（γ̇=0 冻结 γ）——最简单，但形态是"定角下滑"；
- (B2) 采用文献 QEGC 的 γ≈0 版本（L cos σ = m(g−v²/r)，γ 视为小量），配合显式 capture 段；
- (B3) 与 C 结合：capture 段用反馈把 γ 拉平后再进入平衡滑翔（文献中 entry guidance 的典型结构）。

推荐顺序：文献依据 > 物理定义 > 数学可解释性 > 未来兼容性 > 参考表拟合。**推荐不等于批准。**

---

## 9. Open Questions Requiring Human Decision

1. **是否允许引入 bank angle / effective lift factor u_L = cos σ？**（文献支持：Shen-Lu 式(7)）
2. **正式模型是否严格保持二维？**（u_L 隐含忽略侧向动力学——文献中平面纵向研究常见，但需确认）
3. **K=3 应理解为固定气动 L/D，还是实际有效纵向 L/D（K_eff = K·cos σ）？** 若 u_L<1，纵向有效升阻比下降，阻力不变——需明确语义。
4. **是否接受 quasi-equilibrium glide（γ̇≈0，γ 小）作为 Qian 模式定义？** 若接受，采用 B1（冻结 γ）、B2（γ≈0 + capture 段）还是 B3（反馈捕获）？
5. **是否保留题面 reference ranges 仅作外部比较（不再作为硬验收）？**（Phase B 已证明参考表与题面模型不自洽；B/C sandbox 均未落入 6000–8500 km / 1200–1800 s / 800–1500 m/s）
6. **capture / glide / terminal 分段是否需要显式建模？**（题面未定义；文献中 entry guidance 常显式分段）
7. **u_L 上界**：是否限制 u_L∈[0,1]（σ∈[0,90°]，无倒飞）？本轨迹数据从未需要 u_L<0。

---

## 10. Proposed Implementation Plan After Approval（仅描述，不执行）

- **files to add**：
  - `src/hyptraj/controls/continuous_glide.py`（按批准的模型实现控制律，如 u_L(t) 计算 + saturation）；
  - `src/hyptraj/modes/continuous_glide.py`（若需显式 capture/glide/terminal 分段与模式语义）；
  - `experiments/02_qian_continuous_glide/`（run + plot，输出 `results/baseline/qian_continuous_glide/`）；
  - `tests/test_models/test_qian_continuous_glide.py`。
- **files to modify**：
  - 保留 `src/hyptraj/models/dynamics.py` 四维 RHS 数学含义不变；
  - `simulation/trajectory.py`：若控制律需要额外输入（u_L 时间序列），扩展 `TrajectoryResult`（新增 control 字段，不破坏现有字段）；
  - 输出目录迁移：`results/baseline/literal_eq4_uncontrolled/`（现有）与 `results/baseline/qian_continuous_glide/`（新）并存。
- **tests**：`test_literal_eq4_baseline.py`（现有 regression 改名保留）+ `test_qian_continuous_glide.py`（新）；验收含：h_max ≤ 100 km + ε_h、控制量边界、无 state clipping、ground event 正常、无 NaN/Inf、pytest 全量 PASS、Phase A/B 既有测试不破坏。
- **baseline outputs**：trajectory.csv（含 u_L 或 σ 时间序列列）、metrics.json、metadata.json、figures/（原 5 图 + 控制历史图 + literal vs Qian 对比图）。
- **regression migration**：冻结新 Qian baseline 数值需满足"人工批准模型 + 物理 sanity 通过 + 人工确认结果"三个条件后执行。
- **comparison with literal baseline**：h–R 与 v–t 对比图；与题面表 2 重新比较，并如实标注差异类型（model-definition / parameter / reference-table discrepancy）。

---

## 附：本次审计生成的文件

```text
docs/model_audit/phase_b5_qian_continuous_glide_audit.md      （本文档）
experiments/01_baseline_dynamics/audit/analyze_literal_baseline.py
experiments/01_baseline_dynamics/audit/candidate_feasibility.py
results/audit/phase_b5/literal_diagnosis.json
results/audit/phase_b5/candidate_b_feasibility.json
results/audit/phase_b5/fig_literal_h_t_events.png
results/audit/phase_b5/fig_literal_L_Lreq.png
results/audit/phase_b5/fig_literal_eta_L.png
results/audit/phase_b5/fig_candidateB_uL_star.png
results/audit/phase_b5/fig_candidateB_trajectory_compare.png
```

未修改任何 production 代码（`src/hyptraj/models/dynamics.py`、`simulation/trajectory.py`、现有 baseline、regression 均保持不变）。

# Phase B.5-B3-B Drag–Energy / Terminal-Interface Derivation Report

日期：2026-08-15
状态：**DERIVATION COMPLETE — WAITING FOR HUMAN T3b ARCHITECTURE DECISION**

前置决策：`DECISION: T3b-DERIVATION` —— 不实现 T3a；本阶段为推导/审计；不实现
production 终端控制器；不冻结 Qian baseline；不进入 Phase C。T1/T2 保留为终端包络参考。

---

## 1. Current Model Status

三段结构已定：ENTRY →（γ=0, direction=+1 捕获事件）→ QEG_GLIDE →（u_L\*=1 可行性
丧失事件）→ TERMINAL_GATE。QEG-end 状态（全部 B.5-B2/B.5-B3 共用起点）：

| 量 | 值 |
| --- | ---: |
| t | 723.038 s |
| h | 46.041 km |
| v | 3192.533 m/s |
| γ | ≈0 |
| R | 3490.7 km |
| E = v²/2 − μ/r | −5.6955×10⁷ J/kg |
| 能量高度 e = h + v²/(2g₀) | 566.2 km |
| a_D = D/m | 2.6938 m/s² |
| da_D/dt（状态决定） | −4.55×10⁻³ m/s³ |

控制语义：u_L = cos σ ∈ [0,1]（纵向升力投影）；K = L/D = 3 为气动升阻比（K_eff = K·u_L）；
无攻角控制自由度。

## 2. Literature Basis（全部经 Crossref / NTRS 核实；沿用 B.5-A/B.5-B3-A 已核清单）

拖拽–能量制导架构的直接来源：

| 文献 | 支撑内容 |
| --- | --- |
| Harpold & Gavert 1983（JGCD, 10.2514/3.8523）；Mease & Kremer 1992（NTRS 19930029282） | 航天飞机**阻力加速度剖面制导**：以阻力加速度为参考量、能量为自变量、倾侧角为控制量 |
| Lu 1997（JGCD, 10.2514/2.4008） | RLV 再入制导与轨迹控制（拖拽跟踪 + 反馈） |
| Moore 1991（NASA TM, NTRS 19920010688） | **TAEM**：终端能量管理到固定界面（高度/速度/射程门限） |
| Shen & Lu 2003（JGCD, 10.2514/2.5021） | QEGC 约束轨迹生成（走廊与路径约束） |
| Lu 2014（JGCD, 10.2514/1.62605） | 统一预测-校正再入制导（含高度率反馈） |
| Kluever 2007（JGCD, 10.2514/1.24864） | **无动力 RLV 带倾侧角约束的终端制导**（u_L∈[0,1] 类约束的文献先例） |
| Chen, Zhou, Yu & Yang 2021（Springer, 10.1007/978-981-15-8901-0） | 稳态滑翔动力学与制导（弹道阻尼、奇异摄动=能量状态法） |
| Bryson & Ho（10.1201/9781315137667）；Kim & Grider 1973（10.1109/TAES.1973.309659）；Wang et al. 2019（10.1109/ACCESS.2019.2909589） | 终端约束（撞击角/速度）最优制导背景（T3a 已按 DECISION 排除为 production） |

**方程来源标注约定**：下文每式标注
`[LIT]`=直接来自文献、`[DER]`=由本模型显式推导、`[DESIGN]`=拟议设计选择。

## 3. Energy-State Derivation

取比机械能（精确，非旋转球对称模型）：
$$E=\frac{v^2}{2}-\frac{\mu}{r},\qquad \mu=g_0R_e^2.\qquad [DER]$$

能量高度（文献常用近似形式，Shuttle 拖拽–能量制导的自变量）：
$$e=h+\frac{v^2}{2g_0},\qquad \frac{E+g_0R_e}{g_0}=e+O\!\left(\frac{h^2}{R_e}\right).\qquad [LIT: 制导文献惯例] / [DER: 与 E 的关系]$$

## 4. Verification of dE/dt

**推导**（严格）：v̇=−D/m−g sinγ，ṙ=v sinγ，g=μ/r²：
$$\frac{dE}{dt}=v\dot v+\frac{\mu}{r^2}\dot r
=-\frac{Dv}{m}-gv\sin\gamma+\frac{\mu}{r^2}v\sin\gamma
=-\frac{Dv}{m}-v\sin\gamma\left(g-\frac{\mu}{r^2}\right)
=-\frac{Dv}{m}.\qquad [DER，精确恒等式]$$

**数值验证**（`drag_energy_derivation.py`）：沿 QEG 段与 T1 终端段，中心差分 dE/dt
与 −Dv/m 比较，最大相对误差 2.1×10⁻³（QEG）、9.5×10⁻⁴（T1）——有限差分精度量级，
恒等式代数严格成立（g=μ/r² 精确抵消）。

**结论**：`dE/dt = −D v / m` 在当前球对称非旋转模型下**精确成立**（非近似）。

## 5. Dynamics Parameterized by Energy

由 dx/dE = (dx/dt)/(dE/dt)，在 dE/dt ≠ 0 区域（后 QEG 段全程满足）：
$$\frac{dh}{dE}=-\frac{m\sin\gamma}{D},\qquad
\frac{d\theta}{dE}=-\frac{m\cos\gamma}{D\,r},\qquad [DER]$$
$$\frac{d\gamma}{dE}=-\frac{u_LL}{m a_D v^2}
-\frac{\cos\gamma}{a_D}\left(\frac1r-\frac{g}{v^2}\right),\quad a_D=D/m.\qquad [DER]$$

数值验证（u=1 与 u=0 探针，2001 点均匀网格）：

| 量 | T1 (u=1) | T2 (u=0) |
| --- | --- | --- |
| dθ/dE 最大绝对误差 | 3.2×10⁻¹¹ | 3.2×10⁻¹² |
| dγ/dE 最大绝对误差 | 3.7×10⁻¹⁰ | 6.3×10⁻⁹ |
| dh/dE 最大绝对误差 | 2.4×10⁻⁵ | 5.8×10⁻⁵ |

**奇异/数值困难区域**（必须显式记录）：
- dE/dt = −Dv/m → 0 当 **D→0**：ENTRY 段高空（约 80 km 以上，跳跃顶点 D≈0.1 N）能量
  局部冻结，dh/dE 发散 → **能量参数化在再入初始段无效**（时间参数化仍有效）；
- **v→0**：γ̇ 含 1/v 项趋于奇异（本模型 v_f ≥ 160 m/s，未到达；低空低速段为 T1 的
  弱强迫平衡跟随下滑，能量参数化仍有效但敏感度结构变化）。
- 后 QEG 段：a_D ≥ 2.69 m/s²、v ≥ 160 m/s → dE/dt ≤ −430 W/kg，能量参数化全程有效。

## 6. Drag-Reference Formulations（三种表示比较，不做优化）

后 QEG 段参考剖面 a_D,ref(E)（或 D_ref(E) = m·a_D,ref）：

| 准则 | A. 分段线性 D(E) | B. 低阶多项式 D(E) | C. QEG 派生/自然参考 |
| --- | --- | --- | --- |
| 边界条件 | D(E_gate)=D_gate（状态给定）；D(E_TI)=D_TI（由 TI 定） | 同左 + 单调性/形状约束 | 无（由平衡滑翔本身定义） |
| 自由参数数 | k 节点 → k 个值（2 端点已知，k−2 内点待定） | 二次：3 系数（2 端点 + 1 形状） | **0** |
| 终端条件能否定参数 | 端点条件确定端点，内点仍为任务输入 | 端点 + 单调性约束下 1 个形状自由度 | 不适定（见下） |
| 光滑性 | C⁰（节点处 kink，分段可微） | **C∞** | C∞ |
| STM/FTLE 兼容 | kink 面（E 依赖状态）可定位，需跨面处理 | 最优（无额外奇性） | 最优 |
| 后续最优控制兼容 | 线性段友好 | 友好 | 约束型参考 |
| 可行性 | ✓（走廊内） | ✓（走廊内） | **不可行**：QEG 可行性丧失后实际阻力必然高于平衡值（a_D ≥ a_D,eq=2.69 m/s² 且单调上升）；仅作为走廊下界/锚点 |

**结论**：C 不能作为可跟踪参考（只能作下界锚点）；A/B 参数可被 TI 端点条件部分确定，
其余形状自由度属**任务输入**；B（二次多项式 + 单调约束）在 STM/FTLE 与数学清晰性上最优。

## 7. Required External Terminal Inputs

**必须由人工/任务给定（REQUIRED HUMAN / MISSION INPUTS）**：
1. 研究终端界面（TI）的定义形式与参数（见第 8 节：TI-A/B/C/D 之一及其数值）；
2. 剖面表示类（A/B）与形状约束；
3. （若采用）地面续接律（建议 T1 全升力自然下降）。

**可以推导（DERIVED QUANTITIES）**：D_gate（门状态）、D_TI（由 TI + 车辆气动/约束）、
E_gate、全部终端段轨迹量、走廊边界、η_v、热载荷代理等。

**禁止**：单独手选 γ_f\*、v_f\*、h_f\*、E_f\*、q_f\*——它们只能通过 TI/剖面定义
间接进入模型（避免从题面表 2 直接取值）。

## 8. Terminal-Interface Candidates

| 准则 | TI-A: v−v_TI=0 | TI-B: E−E_TI=0 | TI-C: 联合 (h,v) 曲面（TAEM 式） | TI-D: 物理派生（q=q_TI） |
| --- | --- | --- | --- | --- |
| 物理意义 | 高速研究速度界 | 能量界（拖拽–能量制导自然自变量） | 制导交接门限（高度+速度同定，Moore 1991 TAEM 形态） | 热防护动压上限（走廊下界约束的物理来源，Shen-Lu 路径约束族） |
| 文献支持 | 一般 | 强（Shuttle D(E) 制导） | 强（TAEM 界面） | 强（进入走廊由 q/热约束界定） |
| 任意常数依赖 | v_TI（任务输入） | E_TI（任务输入） | 曲线 (h_TI, v_TI)（任务输入） | q_TI（由飞行器热防护能力导出，非随意） |
| 事件可检测性 | 光滑横截 ✓ | 光滑横截 ✓ | 见下方 codim-2 更正注 | 光滑横截 ✓ |
| 敏感性分析友好 | 易 | 易 | 需 g(h,v)=0 标量流形 | 易 |
| 高速研究相关性 | 高（高速域截止） | 高 | 高 | 高（热载荷界） |
| 地面续接兼容 | 易 | 易 | 易（续接点状态完整） | 易 |

**codim-2 更正注（DECISION 第 13 条）**：TI-C 若表达为"同时固定 h=h_TI 且 v=v_TI"，
是两个独立等式的交集，在状态空间中构成 **codimension-2 集合**，不是单个标量
solve_ivp 事件曲面。若未来采用联合 (h,v) 界面，必须表达为单个标量流形
g(h,v)=0（或显式采用多条件界面定义）。本报告中的 TI-C 候选按"以单标量流形
g(h,v)=0 定义的界面曲线"理解；探索性实现未使用 TI-C，不涉及该实现问题。

**说明**：TI-D 与"物理派生"最接近——q_TI 由工程热防护假设导出（题目 3.4 节
"Q_max 具体数值由参赛队伍根据合理工程假设确定"同构），非凭空常数。TI-C 与 TI-D
可组合（以 q 界定义界面曲线的一部分）。

## 9. T1/T2 Reachable-Envelope Analysis（沙盒结果）

从 QEG-end 状态出发，恒定 u_L ∈ {0, 0.25, 0.5, 0.75, 1.0} 探针族（T2=u_L=0、T1=u_L=1
为包络两端）：

| u_L | t_f [s] | a_D 范围 [m/s²] | v_f [m/s] | q_max [kPa] |
| --- | ---: | --- | ---: | ---: |
| 0.00 (T2) | 857.6 | 2.69 → 18.85 | 392.3 | 279.5 |
| 0.25 | 1068.1 | 2.69 → 8.54 | 264.1 | 98.3 |
| 0.50 | 1356.4 | 2.69 → 5.66 | 214.9 | 43.1 |
| 0.75 | 1676.9 | 2.69 → 4.06 | 182.0 | 23.1 |
| 1.00 (T1) | 2018.0 | 2.69 → 3.13 | 159.9 | 15.7 |

- D–E 走廊：门处包络宽度 0（同起点）→ 低能端 52.9 m/s²，漏斗形展开；
- h–v、q–v 走廊同构展开（u 增大 → 飞行更长、q 更低、v_f 更低，族内单调）；
- **注意**：恒定 u_L 族仅是可达走廊的**探针采样**；内部状态的可达性未逐一验证
  （时变 u_L 的可达集 ≥ 该族包络），不作"走廊内处处可达"的推断。

## 10. Can u_L Alone Track a Drag-Energy Reference?

**关键推导**（在本模型下）：a_D = q·S·C_D/m = ½ρ(h)v²·S·C_D/m，
$$\frac{da_D}{dt}=a_D\left[-\frac{\dot h}{H}+\frac{2\dot v}{v}\right]
=a_D\left[-\frac{v\sin\gamma}{H}
-\frac{2a_D+2g\sin\gamma}{v}\right].\qquad [DER]$$
**在固定状态下，a_D 与 da_D/dt 均与 u_L 无关**（只含 h, v, γ）；u_L 仅通过 γ̇
进入**未来**路径 → 阻力控制是**间接的路径级控制**，与航天飞机阻力剖面制导架构一致
（Harpold & Gavert 1983；Lu 1997：倾侧角调制 → 垂直力平衡 → 路径 → 阻力）。

可行性结论（诚实报告）：
- **可行**：u_L∈[0,1] 提供的走廊宽度充分（a_D 可达范围 2.69→52.9 m/s²），
  路径整形可跟踪单调 D_ref(E)；
- **约束**：(i) 门处 a_D=2.69 是走廊**下界** → D_ref(E) 必须单调不减（先下降再回升
  的剖面不可达）；(ii) 阻力速率权限是二阶的（经 γ̇），高空/低 q 区响应慢；
  (iii) u_L∈[0,1] 限制在正升力侧（无倒飞）；(iv) 不引入攻角自由度（本阶段禁止）。
- 若未来要求"直接阻力驱动"或瞬时高带宽跟踪，u_L 单独不充分——需攻角或其它自由度
  （超出 B.5 范围，如实报告）。

## 11. Ground Endpoint vs Research Terminal Interface

- **Q1**（同一高速模型应否作为 h=0 主研究模型？）：**否**。固定 C_D + 指数大气的
  植物模型是高速再入/滑翔模型；T1 末段 v<1500 m/s 持续 ~693 s、v_f=160 m/s，已离开
  高超声速气动有效域（真实飞行器在亚声速段改变配平/构型）；且 γ̇∝1/v 使低速段
  敏感度结构改变。h=0 端点只应作题面兼容用途。
- **Q2**（FTLE 含低速尾损失什么？）：低速尾是弱强迫平衡跟随下滑（γ̇≈0、长时标、
  近可积）——拉长积分区间、稀释高速段 FTLE 统计，把"末端低速爬行敏感度"与
  "高超声速可预测性"混为一谈；突防/拦截分析（80 km 以上雷达、120 s 延迟）只关心
  高速段。
- **Q3**（Research TI + 单独地面续接更干净？）：**是**。STM/FTLE/可预测性/突防指标
  定义在 [0, t_TI]（模型有效高速域）；地面续接（TI→h=0，建议 T1 律）单独报告
  t_f/R_f/v_f 作为题面兼容指标。**推荐采纳该双端点架构（尚未实施）。**

## 12. STM / FTLE Implications

- 剖面表示：A（分段线性）→ C⁰ kink 面（E 依赖状态，位置可定位，需跨面
  saltation/雅可比跳变处理）；B（多项式）→ C∞ 无额外奇性（**最优**）；C → C∞ 但不可跟踪。
- TI 事件（A/B/C/D 均为光滑横截事件面）：v−v_TI、E−E_TI、曲面符号距离、q−q_TI ——
  对 STM/FTLE 的事件处理无特殊困难。
- 模式切换：QEG→终端门仍为唯一固有切换（T1 连续 / T2 不连续已文档化）；T3b 若采用
  光滑反馈（a_D−a_D,ref 的线性项）不新增不连续；唯一分段光滑源为剖面 kink（若选 A）。
- 设计原则（第 13 节架构按此）：状态连续、控制尽量连续、模式边界为显式事件面、
  参考剖面可微（或分段可微且 kink 记录在案）、全部不连续点文档化。

## 13. Recommended T3b Architecture（拟议，未批准）

1. **参数化**：后 QEG 段以 E 为自变量（精确 E=v²/2−μ/r；第 4-5 节已验证）；
2. **参考剖面**：D_ref(E) 取二次多项式 + 单调不减约束（类别 B，C∞），端点
   (E_gate, D_gate) 由状态给定、(E_TI, D_TI) 由 TI 决定——参数完全由 TI 确定；
3. **终端界面**：推荐 TI-C（TAEM 式 (h,v) 门，Moore 1991）或 TI-D（q=q_TI 热防护界）
   或二者组合（门处同时给 h、v，且 q ≤ q_TI 由走廊保证）；
4. **跟踪律**：a_D − a_D,ref 的反馈 → u_L（航天飞机阻力控制器结构，Harpold & Gavert /
   Lu 1997），饱和限幅 u_L∈[0,1]，不引入攻角；
5. **地面续接**：TI 之后用 T1 律（u_L=1）自然下降至 h=0，仅作题面兼容输出；
6. **研究指标域**：[0, t_TI] 为 STM/FTLE/突防分析主域（第 11 节）。

## 14. Open Questions Requiring Human Decision

1. 研究终端界面选 TI-A/B/C/D（或组合）？参数值及其依据？
2. D_ref(E) 类别：B（二次多项式，C∞，推荐）还是 A（分段线性）？
3. 跟踪律允许反馈增益（有参数）还是严格零参数？
4. 地面续接是否固定用 T1 律（u_L=1）？
5. 研究阶段是否正式以 TI 为终点（指标域 [0,t_TI]）？
6. 是否将 q=q_TI 作为走廊硬约束并入 T3b 定义？

## 15. Proposed Implementation Plan After Approval（仅描述）

- **files to add**：`src/hyptraj/controls/drag_energy_terminal.py`（D_ref 生成 + 跟踪律 +
  TI 事件判定）；`src/hyptraj/simulation/events.py` 增 TI 事件（按批准形式）；
  `experiments/03_qian_terminal_t3b/`（run/plot）；`tests/test_models/test_t3b_terminal.py`。
- **files to modify**：`simulation/trajectory.py` 仅扩展（TI 事件、u_L 时间序列记录、
  control 字段），不破坏现有字段；输出目录新增
  `results/baseline/qian_continuous_glide/`（TI 段 + 地面续接段分列）。
- **tests**：TI 事件检测、D_ref 端点/单调性、u_L∈[0,1]、走廊内约束、ground 续接、
  pytest 全量 PASS、Phase A/B 既有测试不破坏。
- **baseline outputs**：trajectory（含 u_L/D_ref/a_D 列）、metrics（TI 段 + 全程分列）、
  metadata、figures（走廊 + 剖面 + 跟踪误差）。
- **regression**：仅在"模型批准 + 物理 sanity + 人工确认"后冻结；literal_eq4_uncontrolled
  永不删除。

---

## 附：本阶段生成的文件

```text
experiments/01_baseline_dynamics/audit/drag_energy_derivation.py
results/audit/phase_b5/drag_energy_derivation.json
results/audit/phase_b5/fig_b3b_D_E_corridor.png
results/audit/phase_b5/fig_b3b_h_v_corridor.png
results/audit/phase_b5/fig_b3b_q_v.png
results/audit/phase_b5/fig_b3b_dEdt_verify.png
docs/model_audit/phase_b5_b3b_drag_energy_derivation.md  （本文档）
```

未修改任何 production 代码；pytest 24/24 通过；literal_eq4_uncontrolled、T1/T2、
全部 B.5 产物原样保留。

# F2 — Coarse gamma0-K Hybrid-Regime Map

状态：**COMPLETE**（2026-08-16，F2.1 amendment 后完成）

历史：初始运行 BLOCKED（Sanger SRTI-qualification 表达边界，见 §12）；
F2.1 grazing-event observability amendment 解决后 canonical rerun
COMPLETE（见 "Blocker resolution" 节）。原 blocker 历史保留不删。

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `417b2a4`（F1）
Artifacts: `results/gamma_k_sensitivity/coarse_map/`（untracked）

## 1. Purpose

在 F0 主域 gamma0 ∈ [-7,-3] deg × K ∈ [2,4] 上执行 17×17 = 289-point
deterministic Cartesian paired（Qian + Sanger）分类，识别 hybrid regimes、
skip-count 区域分布、coarse topology-boundary candidate cells，并按 F0 §9
条件扩域。**不是** derivative / optimization / Protocol B/C/D 研究。

## 2. Frozen protocol / baseline

- 协议：`docs/phase_f/sensitivity_protocol.md`（F0 + F0.1）
- Anchor：p0 = (-5 deg, 3)，`phase-e-v1.0`（44a99119…）
- 执行 API：`run_parameter_point`（F1 复用，零复制）+ structured
  classifiers；`PRODUCTION_SOLVER_CONFIG`；Qian max_time=5000 s；Sanger
  max_time=5000 s、max_segments=50。
- 可恢复 cache：`point_cache.jsonl`（逐点原子 append；中断恢复；provenance
  验证：schema / Phase E anchor / F0 / F0.1 / F1 commit / solver / domain
  自洽）。

## 3. Grid and numerical configuration

| 项 | 值 |
|---|---|
| 初始域 | gamma0 ∈ [-7,-3] deg，K ∈ [2,4] |
| spacing | Δgamma = 0.25 deg，ΔK = 0.125（np.linspace 精确构造）|
| 初始 grid | 17×17 = 289 points |
| 每点 | Qian + Sanger paired（578 次积分目标）|
| 扩域增量 | gamma ±1.0 deg/step，K ±0.5/step（spacing 保持）|
| guardrails | gamma0 ∈ [-9,-1] deg，K ∈ [1,5] |

## 4. Baseline anchor

**PASS**（与 F1 相同 10 项检查，diff = 0.0）：Qian = QIAN_RTI（capture
93.42878537129322 s / RTI 723.0379653550676 s / RTI range
3490698.335988048 m）；Sanger = SRTI_N2（terminal 1119.5459841174863 s /
range 6872895.31994491 m / skip=2 / 5-segment modes）。

## 5. Qian regime map

主域 289/289 = **QIAN_RTI**（F2 正式结果：Qian topology is uniform over D0
at coarse resolution；不外推 D0 之外）。扩展点 38/38 同样 QIAN_RTI。
Qian exact topology 全采样域仅 1 种。

## 6. Sanger regime map

**主域 289 点出现 4 个物理 regime**：

| regime | count | 分布（主域）|
|---|---|---|
| SRTI_N0 | 11 | 左下角：gamma0 ≥ -3.25 deg 且 K ≤ 2.5（浅入角 + 低 K → 无完整 skip）|
| SRTI_N1 | 137 | 左上–中左大块：低 K 或浅入角 |
| SRTI_N2 | 110 | 中央对角带 |
| SRTI_N3 | 31 | 右下角：陡入角 + 高 K |

扩展域（38 点，部分）：SRTI_N1 12 / N2 14 / N3 7 / **N4 5**
（gamma0=-8 行 K ≥ 4.0 出现 skip=4）。

17×17 主域矩阵（行 gamma0 [deg]，列 K）：

```
        2.00  2.12  2.25  2.38  2.50  2.62  2.75  2.88  3.00  3.12  3.25  3.38  3.50  3.62  3.75  3.88  4.00
 -7.00   N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3    N3    N3    N3    N3
 -6.75   N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3    N3    N3    N3    N3
 -6.50   N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3    N3    N3    N3
 -6.25   N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3    N3    N3
 -6.00   N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3    N3    N3
 -5.75   N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3    N3
 -5.50   N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N2    N3    N3
 -5.25   N1    N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N2    N3
 -5.00   N1    N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N2    N2
 -4.75   N1    N1    N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2    N2
 -4.50   N1    N1    N1    N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2    N2    N2
 -4.25   N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2    N2
 -4.00   N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N2    N2    N2    N2    N2
 -3.75   N0    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N2    N2    N2
 -3.50   N0    N0    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N2
 -3.25   N0    N0    N0    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1
 -3.00   N0    N0    N0    N0    N0    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1    N1
```

## 7. Joint regime structure

Qian 全域 QIAN_RTI → joint 变化完全由 Sanger 驱动：

```
(QIAN_RTI, SRTI_N0) × 11, (QIAN_RTI, SRTI_N1) × 149,
(QIAN_RTI, SRTI_N2) × 124, (QIAN_RTI, SRTI_N3) × 38,
(QIAN_RTI, SRTI_N4) × 5（扩展域）
```

（计数含扩展域 38 点；主域 289 点：N0×11, N1×137, N2×110, N3×31。）

## 8. Coarse topology-boundary candidates

- 主域 256 cells：candidate = 50（P1 compact transition），exact-only = 0，
  multiskip = 0。
- N1/N2、N2/N3、N0/N1 三条候选带均为**斜向 band**（非单值函数），与
  "gamma0 越陡 + K 越高 → skip 越多" 的总体趋势一致。
- 无 |Δskip| > 1 的相邻跳变（coarse resolution 下相邻 regime 差一步）。

## 9. Topology margins

- **global min M_A = 139.7 m** @ (gamma0=-8.0, K=4.0, SRTI_N4)：扩展域
  N3→N4 边界附近第二个 VAC apogee 贴近大气边界。
- **global min M_S = 88.3 m** @ (gamma0=-6.25, K=3.5, SRTI_N2)：主域内
  N2→N3 边界 N2 侧 —— 比 F1 的 K=4.0 记录（777 m）更接近 0；M_S → 0 与
  SRTI-qualification 边界方向一致。
- edge minima：gamma_lower M_A=139.7 m / M_S=265.7 m（gamma=-8 边界）；
  K_lower M_A≈20.0 km；K_upper M_A≈8.6 km / M_S≈5.6 km；
  gamma_upper = None（gamma=-2 行未采样，blocker 后停止）。
- one-sided pattern：**N2 侧 M_S → 0（如 88.3 m @ (-6.25, 3.5)）与
  N3 侧 M_A → 0（如 139.7 m @ (-8.0, 4.0)）在 coarse 数据中普遍可见**
  —— 支持 "N2/N3 boundary 一侧 M_S→0、另一侧某 M_A→0" 的结构假设，
  **未经 F3 refinement 不得表述为已证明的 boundary equation**。

## 10. Domain-edge audit

主域四边均被 candidate cells 接触（N0/N1 于 gamma upper + K lower；
N1/N2、N2/N3 于 gamma lower + K upper）→ **四边扩域按 F0 §9 自动触发**
（正确触发，非 margin 驱动）。

## 11. Conditional domain expansion

```
round 1: directions = [gamma_lower, gamma_upper, K_lower, K_upper]
         [-7,-3]×[2,4]  ->  [-8,-2]×[1.5,4.5]
         新增 336 个 grid points（spacing 保持 0.25 / 0.125）
```

- 扩展 strip 完成 38 点后停止（见 §12 blocker）。
- OPEN_BOUNDARY：**无**（未到达 guardrail）。
- 由于 blocker，扩域未完成：gamma=-2 行、gamma=-7.5/-7.25 行、
  gamma=-7.75 行 K≥3.125 等未采样。

## 12. Numerical/event health + HARD STOP GATE（blocker）

- 主域 289 点 + 扩展 38 点：Qian/Sanger 全部 structured 分类成功；无
  censored / failure / ambiguous / invalid / chatter / bad ordering /
  NaN-Inf；event 时间严格递增；segment duration > 0；exit transversality
  全部 PASS；skip-count ↔ 段数一致性全部 PASS。
- **HARD STOP GATE（frozen API 表达边界）**：

```
point      = (gamma0 = -7.75 deg, K = 3.125)   [扩展 strip]
model      = Sanger
exception  = RuntimeError（frozen sanger_trajectory.py SRTI qualification）
message    = "SRTI candidate above the atmosphere boundary:
              h = 100016.949 m > h_atm = 100000.0 m."
```

  物理含义：该点 SRTI 候选事件（gamma +→− root）出现在大气边界上方约
  17 m —— 即 terminal pass 的 SRTI 高度贴近 h_atm（M_S → 0⁻ 方向），
  属于 N-skip 过渡带的退化情形。frozen 状态机将之判定为非法并 raise，
  **当前 Sanger API 无法为该情形返回结构化 terminal**（表达缺口）。
- 处理（按 F2 契约 §75）：不修改 frozen source；停止新增 points；保留
  已完成 cache（327 点）与全部 artifacts；生成 stop_gate_report.json；
  不伪造 F2 COMPLETE。**这是 BLOCKER，不是科学结论失败** —— 它本身是
  有价值的发现：Sanger SRTI 语义在大气边界附近存在表达边界，F3 前需要
  协议级决策（新增 "SRTI-qualification 边界" 处理策略或限定 refinement
  域）。
- F1 consistency：**PASS**（K=3 gamma slice 与 gamma0=-5 K slice 的
  compact regimes 与 F1 报告逐点一致；Qian 全 QIAN_RTI）。

## 13. Diagnostic figures

`results/gamma_k_sensitivity/coarse_map/figures/`（untracked）：

| figure | programmatic audit |
|---|---|
| F2_sanger_regime_map.png | exists / loadable / 1650×1050 / 60.7 KB / PASS |
| F2_joint_regime_map.png | exists / loadable / 1650×1050 / 49.2 KB / PASS |
| F2_topology_margins.png | exists / loadable / 1650×1500 / 95.1 KB / PASS |

Visual inspection（zai-mcp 已执行）：Sanger map 5 个离散 regime 色块清晰、
candidate cell 方框沿分界带分布、无插值无连续色阶；margin 图深色区集中在
N3/N4 扩展域与 N2→N3 边界；缺失区 = blocker 后未采样点（如实呈现）。

## 14. Scientific interpretation（coarse 限定）

- 主域 coarse 分辨率下存在 **4 个 Sanger hybrid regimes（N0/N1/N2/N3）**
  形成斜向带状结构；Qian 保持单一采样 topology（QIAN_RTI）。
- "candidate cells form a coarse transition band"（N0/N1、N1/N2、N2/N3
  三条带）✓。
- "one-sided topology margins approach the atmosphere interface"
  （N2 侧 M_S → 0；N3 侧 M_A → 0）—— coarse 数据一致，**F3 前不声称
  边界方程**。
- 禁止表述：bifurcation curve 精确位置、"critical K/gamma"、range
  sensitivity、winner、optimal region。

## 15. Limitations

- 扩展域因 blocker **不完整**（38/336 点）；最终域 [-8,-2]×[1.5,4.5] 的
  boundary 统计仅基于已采样子集。
- F1 主域结论不受影响（289/289 完整 + F1 consistency PASS）。
- Simultaneous-event caveat（F0.1）：本 map 未触发
  AMBIGUOUS_SIMULTANEOUS_EVENT；F3 前需重新审计 terminal=True 双重 root
  observability（无论是否出现）。

## 16. F3 handoff

`F3_priority_cells.json`（refinement queue，非 boundary proof）：

- **P0（multiskip）：0**
- **P1（compact transition）：50 cells**（N0/N1、N1/N2、N2/N3 三带）
- P2（exact-only）：0
- P3（margin hint，按最小 margin 排序）：218 cells

预期边界分支：**3 条**（N0/N1、N1/N2、N2/N3）+ 扩展域 N3/N4（若 F3 前
解决 blocker）。domain-edge caveats：gamma 下边界（N3→N4 方向，M_A→0）、
K 上边界（N2→N3 方向，M_S→0）—— **F3 前必须处理 Sanger
SRTI-qualification 表达边界**（协议 amendment 或 refinement 域限定）。

## 17. F2 acceptance（BLOCKED 状态下如实报告）

    [x] baseline anchor PASS
    [x] initial 17×17 grid complete（289/289 分类成功）
    [x] Qian regime available for every point
    [x] Sanger regime available for every point（主域）
    [x] exact topology signature available every point（主域）
    [x] joint regime available every point（主域）
    [x] no unknown terminal kinds / no censored / no failure（主域+已采样扩展点）
    [x] no invalid input / no boundary ambiguous / no chatter / no bad order / no NaN-Inf
    [x] skip-count consistency PASS / exit transversality PASS
    [x] candidate cells extracted（50 P1）
    [x] exact-only candidates checked（0）/ multiskip jumps checked（0）
    [x] gamma-row brackets extracted（31）/ K-column brackets extracted（25）
    [x] topology margins summarized / edge-touch audit performed
    [x] domain expansion policy executed automatically（四边，round 1）
    [ ] 扩域完成 —— **BLOCKED**（Sanger SRTI-qualification 表达边界）
    [x] guardrails respected（未触 guardrail；OPEN_BOUNDARY = 无）
    [x] no label interpolation / no derivative / no B/C/D surfaces / no optimization
    [x] diagnostic figures generated + programmatic PASS + visual inspected
    [x] checkpoint/resume functional（中断恢复验证：327 点 reuse，无重复积分）
    [x] F1 slice regimes reproduced（PASS）
    [x] Phase E regression unchanged / all tests PASS

**F2 = BLOCKED（主域 COMPLETE；扩域受阻）**

## Blocker 决策请求（F3 前需要协议级决策）

1. Sanger SRTI-qualification 边界（h_SRTI 略高于 h_atm 的点）：选项
   (a) 协议 amendment 定义新 regime（如 `SRTI_BOUNDARY` 或将该情形归类
   为 censored/`BOUNDARY_AMBIGUOUS` 类似物）；(b) F3 refinement 限定于
   M_S 不越过该边界的子域；(c) 冻结主域 D0 为最终 F2 域（四边带开放）。
2. 是否按 F0 §9 继续扩展 gamma lower / K upper 以 bracket N3/N4 与
   N2/N3 边界（需先解决 blocker 1）。

---

## Blocker resolution（F2.1 amendment 后 canonical COMPLETE）

### 18. Original blocker → F2.1 diagnosis

原 blocker（gamma0=-7.75, K=3.125，frozen `integrate_sanger_hybrid`
RuntimeError "SRTI candidate above the atmosphere boundary"）经 F2.1 审计：

- **strict reference self-stable**：REF-0.1 与 REF-0.05 均返回
  srti / skip=3 / 7 modes / t_term=1534.399531 s（一致到 1e-6 s）；
- **机制**：production max_step=20 s 的一个 step 跨过第三个极浅 VAC 弧
  （apogee 仅高于 h_atm 16.9 m、VAC 持续约 5 s）：atmosphere_exit root
  端点同号漏检；gamma 下穿 root（物理 = vacuum apogee）被 SRTI candidate
  捕获 → h > h_atm → frozen qualification RuntimeError；
- 真实拓扑 = **SRTI_N3**（非硬编码，以 reference 为 source of truth）。

### 19. Research recovery（F2.1 API）

`integrate_sanger_research_trajectory` 在 candidate-above-boundary 且
pullout 合法时，用已计算 dense interpolant 以 brentq 重建缺失的上穿
interface root，验证 transversality 后按 frozen SANGER_VAC 继续
（x_plus = x_minus，严格连续；event_resolution="DENSE_RECOVERED"）。

### 20. Canonical rerun（v2 cache，research sweep executor）

- cache schema：`f2-coarse-map-point-v2`（provenance 增加
  `phase_f_f21_commit` + `sanger_research_event_resolution_version=v1`）；
  旧 v1 cache 全部 reject（327 条），全量重跑。
- **最终域**：guardrails [-9,-1] deg × [1,5]（33×33 = 1089 points，
  2 轮自动扩域）。
- **recovered points = 5**，全部 REF-0.1 verification 通过
  （topology_equal=True）：(-8.5, 3.0) N3、(**-7.75, 3.125**) N3、
  (-5.25, 1.5) N1、(-4.25, 4.625) N3、(-2.0, 4.125) N1。
- grazing_or_unresolved = 0；SANGER_GRAZING_BOUNDARY markers = 0。
- **D0 289-point equivalence：PASS**（v1 audit vs v2 canonical：
  qian_regime / sanger_regime / skip_count 逐点一致）。
- **F1 consistency：PASS**（gamma/K slice 与 F1 报告逐点一致）。

### 21. Final canonical statistics（33×33 = 1089 points）

| model | counts |
|---|---|
| Qian | QIAN_RTI × 1089（全域单 topology）|
| Sanger | SRTI_N0 × 322，N1 × 306，N2 × 211，N3 × 153，N4 × 85，N5 × 12 |

最终域出现 **6 个 Sanger hybrid regimes（N0–N5）**，形成**一族近似
平行/有序的斜向 grazing-transition bands**（N0/N1、N1/N2、N2/N3、
N3/N4、N4/N5 五条 coarse 候选带；179 candidate cells，无 multiskip
jump，无 exact-only）。**不拟合 boundary equation，不给 critical
K/gamma**（F3 才 refinement）。

### 22. Final margins & domain-edge

- global min M_A / M_S 与 recovered 点见 `coarse_map_summary.json`；
  N2→N3 边界 one-sided margin 结构（N 侧 M_S→0 / N+1 侧 M_A→0）在
  多条 branch 上反复出现 → coarse evidence supports a repeated
  grazing-transition mechanism（非 "mathematically proven for all
  branches"）。
- **OPEN_BOUNDARY（guardrail 处仍开放，F0 §9 规则停止）**：
  `gamma_lower`（gamma0=-9 行 N0–N5 全带接触）、`K_lower`
  （K=1.0 列 N0/N1 带接触）、`K_upper`（K=5.0 列 N4/N5 带接触）。
  gamma_upper（-1 deg）未列入（N0 单 regime 覆盖该行，无 transition
  接触）。
- guardrails respected：未越 [-9,-1]×[1,5]。

### 23. Final F2 acceptance（canonical COMPLETE）

    [x] F2.1 strict reference stable（REF-0.1 == REF-0.05：SRTI_N3）
    [x] blocker physical topology resolved（SRTI_N3，reference-confirmed）
    [x] grazing mechanism documented（f21_sanger_grazing_amendment.md）
    [x] frozen Sanger source unchanged（零修改）
    [x] dense recovery validated（brentq + transversality + x_plus=x_minus）
    [x] every recovered point reference verified（5/5 REF-0.1 PASS）
    [x] D0 289 topology unchanged（PASS）；Qian D0 保持 QIAN_RTI
    [x] canonical F2 rerun complete（1089 points）
    [x] conditional expansion completed（2 rounds 至 guardrail）
    [x] guardrails respected；OPEN_BOUNDARY recorded（gamma_lower/K_lower/K_upper）
    [x] no unverified numerical failures / no censored / no chatter / no NaN-Inf
    [x] candidate cells rebuilt（179）；brackets rebuilt；F3 priority queue rebuilt
    [x] no derivative / no B/C/D surfaces / no optimization
    [x] diagnostic figures rebuilt（programmatic + visual PASS）
    [x] Phase E unchanged / F1 unchanged / all tests PASS

**F2 = COMPLETE（canonical；OPEN_BOUNDARY 已记录）**

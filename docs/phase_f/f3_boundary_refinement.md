# F3 — Adaptive Grazing-Boundary Refinement

状态：**COMPLETE**（2026-08-16）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `35c6637`（F2 canonical）
Artifacts: `results/gamma_k_sensitivity/boundary_refinement/`（untracked）

## 1. Purpose

将 F2 coarse skip-count transition cells 以二维 dyadic cell refinement
精化到 F0 冻结分辨率（Δgamma ≤ 0.01 deg 且 ΔK ≤ 0.01），对每条
N→N+1 branch 正式定义并验证 branch-conditioned signed grazing diagnostic
Phi_N，验证 N 侧 SRTI local maximum 从下方接近大气边界、N+1 侧新 VAC
apogee 从上方接近边界、以及新 atmosphere exit 的 dh/dt → 0+，
建立最终 refined boundary boxes（不拟合虚假精确曲线），记录 guardrail
OPEN_BOUNDARY，并为 F4 生成 boundary-exclusion geometry。

## 2. F2 handoff

- 输入：F2 canonical map（33×33=1089 coarse points）+ F3_priority_cells
  （P1 compact transition cells = 179，P0=0，P2=0）。
- 域：guardrails gamma0 ∈ [-9,-1] deg × K ∈ [1,5]（**不再扩域**）。
- 执行器：`run_parameter_point` + F2.1 `integrate_sanger_research_trajectory`
  （PRODUCTION_SOLVER_CONFIG）；每点 paired（Qian + Sanger）。

## 3. Refinement algorithm

- 坐标：binary dyadic lattice（整数索引；0.25/2^d 与 0.125/2^d 精确
  表示）；禁止 `while x += delta` 浮点累积。
- 每 cell 二分：5 个新点（gamma-mid/K-low、gamma-mid/K-high、
  gamma-low/K-mid、gamma-high/K-mid、center），全局 cache 去重；
  guardrail cell 只采样域内。
- child candidate 规则（F3 §21）：Sanger compact regime 不同 / exact
  signature 不同 / Qian 变化 / 同 B_N 邻域内 Phi_N 两侧出现 /
  grazing marker → candidate；uniform child 停止。
- center discovery：subdivision 自动计算 center，center 与四角不同 →
  相应 children 保留（实现 F0 center-vs-corners 语义）。
- 终止：Δgamma ≤ 0.01 且 ΔK ≤ 0.01 → REFINED_BOUNDARY_CELL（不要求
  uniform）；max_depth = 6 safety limit；multiskip 到 max_depth 仍存在
  → UNRESOLVED_MULTISKIP_CELL（本轮 0 个）。
- 科学对象 = enclosing parameter rectangle；cell center 仅
  `visualization_center_only`。

## 4. Signed branch-conditioned grazing diagnostic（Phi_N 正式冻结）

对 branch B_N（SRTI_N ↔ SRTI_{N+1}）：

- **N side**（regime = SRTI_N）：`Phi_N = h_SRTI - h_atm = -M_S`（< 0，
  SRTI local maximum 从下方接近边界）。
- **N+1 side**（regime = SRTI_{N+1}）：`Phi_N = h_apogee,new - h_atm`，
  其中 h_apogee,new 是 **newly-created LAST VAC apogee**（VAC arc index
  N，zero-based）—— 明确禁止 `min(M_A_clearance_m)` 替代（一个
  SRTI_N4 有 4 个 VAC apogees，对 B3 只有第 4 个与 topology creation
  相关）。
- 其他 regime：Phi_N = None（不跨 N-1 / N+2 延拓）。
- limiting geometry：`h = h_atm ∧ gamma = 0`（`G_h = 0`，
  `dG_h/dt = v sin(gamma) = 0`）。

## 5. Exit transversality diagnostic（T_N）

N+1 侧：`T_N = dh/dt` at the newly-created atmosphere exit（exit index
N，zero-based = 第 N+1 个 ATM→VAC exit）。预期 T_N > 0 且随 refinement
向 grazing 边界趋近 0+。**不是 boundary locator，不是 saltation
magnitude**。

## 6. Reference verification policy

- 所有 `DENSE_RECOVERED` 点：REF-0.1 即时 verify（topology mismatch →
  HARD STOP）；本轮 **3298/3298 verified**。
- GRAZING_OR_UNRESOLVED 点：strict-reference decision 优先于 recovered
  mismatch 检查（production 未解决是设计内状态；REF 明确 N →
  reference-confirmed side + `production_event_resolution_recovered`；
  REF 无法稳定 → SANGER_GRAZING_BOUNDARY marker）。
- branch extremal points（每 branch 两侧 closest-to-zero）：REF-0.1 +
  REF-0.05 双 reference certification（拓扑一致 + Phi 数值一致）。
- sign anomaly（N 侧 Phi ≥ 0 或 N+1 侧 Phi ≤ 0）：REF queue（本轮 0）。

## 7. B0 — N0/N1

- terminal cells = 1939；gamma extent [-9.0, -1.70] deg；K extent
  [1.07, 5.0]；open = {gamma_lower, K_upper}。
- closest N-side：(-2.047, 3.984) SRTI_N0，Phi = **-0.081 m**
  （REF-0.1 -0.08093 / REF-0.05 -0.08093，dual stable）。
- closest N+1-side：(-1.742, 4.875) SRTI_N1，Phi = **+0.048 m**
  （REF 0.04796 一致），T_N = 0.479 m/s。

## 8. B1 — N1/N2

- terminal cells = 1563；gamma [-9.0, -2.73]；K [2.02, 5.0]；
  open = {gamma_lower, K_upper}。
- closest N-side：(-3.242, 4.195) SRTI_N1，Phi = **-0.128 m**。
- closest N+1-side：(-7.297, 2.234) SRTI_N2，Phi = **+0.169 m**，
  T_N = 1.329 m/s。

## 9. B2 — N2/N3

- terminal cells = 1188；gamma [-9.0, -3.86]；K [2.93, 5.0]；
  open = {gamma_lower, K_upper}。
- closest N-side：(-5.727, 3.703) SRTI_N2，Phi = **-0.155 m**。
- closest N+1-side：(-4.031, 4.824) SRTI_N3，Phi = **+0.102 m**，
  T_N = 0.866 m/s。
- 注：F2 blocker 点 (-7.75, 3.125) 位于 B2 带内（reference-confirmed
  SRTI_N3）。

## 10. B3 — N3/N4

- terminal cells = 776；gamma [-9.0, -5.31]；K [3.81, 5.0]；
  open = {gamma_lower, K_upper}。
- closest N-side：(-6.125, 4.574) SRTI_N3，Phi = **-0.135 m**。
- closest N+1-side：(-8.055, 3.980) SRTI_N4，Phi = **+0.036 m**
  （REF 0.03603 一致），T_N = 0.642 m/s —— **全图最小的正侧 Phi**。

## 11. B4 — N4/N5

- terminal cells = 269；gamma [-9.0, -7.55]；K [4.67, 5.0]；
  open = {gamma_lower, K_upper}。
- closest N-side：(-8.875, 4.691) SRTI_N4，Phi = **-0.408 m**。
- closest N+1-side：(-7.930, 4.898) SRTI_N5，Phi = **+0.419 m**，
  T_N = 2.188 m/s。

## 12. Open guardrail intersections

- **gamma_lower（-9 deg）**：7 个 refined cells 接触（B0–B4 全部；
  B4 最显著）—— N0/N1 与 N4/N5 带在 gamma=-9 方向仍开放。
- **K_upper（5.0）**：9 个 refined cells 接触（B0–B4 全部）——
  所有 branch 在高 K 方向仍开放。
- gamma_upper / K_lower：0（无接触）。
- guardrail 内已 refine 到目标分辨率；域外不采样（F0 §9 已冻结）。

## 13. Grazing-margin convergence（signed Phi，按 depth）

| branch | depth0 neg/pos [m] | depth6 neg/pos [m] |
|---|---|---|
| B0 | -17.81 / +3.78 | **-0.081 / +0.048** |
| B1 | -38.21 / +14.95 | **-0.128 / +0.169** |
| B2 | -19.92 / +1.65 | **-0.155 / +0.102** |
| B3 | -3.14 / +11.24 | **-0.135 / +0.036** |
| B4 | -63.74 / +161.71 | **-0.408 / +0.419** |

两侧 |Phi| 随 depth 单调收敛（数值 grazing evidence；不要求严格单调，
adaptive geometry 可能局部不单调 —— 本轮实际单调）。全图最小
boundary-localized 距离：**负侧 8.1 cm（B0）、正侧 3.6 cm（B3）**。

## 14. Numerical/event health

- 23349 unique points（fresh=14052 + cache=8208；Qian 23349/23349
  QIAN_RTI —— **无 Qian topology discovery**）。
- recovered = 3298（14%），全部 REF-0.1 verified；sign anomalies = 0；
  exact-only cells = 0；multiskip unresolved = 0；grazing markers = 0。
- 无 censored / numerical failure / chatter / invalid ordering / NaN-Inf。
- F2.1 API 修复（本轮）：degenerate zero-duration VAC arc（recovered
  exit 后 grazing 极限）结构化 GRAZING_OR_UNRESOLVED_EVENT（替代 frozen
  monotonicity RuntimeError 崩溃）；GRAZING 点由 strict reference 决策
  （本轮全部 reference-confirmed，无 marker）。

## 15. Boundary-exclusion geometry for F4

`boundary_exclusion_cells.json`：5735 个 REFINED_BOUNDARY_CELL（全部
terminal boxes）+ 0 UNRESOLVED + 0 GRAZING marker。F4 finite-difference
stencil 跨越这些 boxes 或端点落在不同 exact topology → derivative
undefined（协议 §27）。

## 16. Relation to future saltation / FTLE

standard transversal saltation formulas contain an event-normal
denominator `n^T f_minus`；对 atmosphere interface：
`n = [1,0,0,0]^T`，`n^T f_minus = dh/dt`。F3 观测到 newly-created exit
的 `dh/dt → 0+`（最小 0.48 m/s 于 B0、0.64 m/s 于 B3）→ grazing 极限处
transversality 丧失，standard saltation formula 病态 —— 未来 phase 需
单独处理。**本轮不计算 saltation matrix**。

## 17. Limitations

- multiplicity（row=5 / column=5）= 5 条 branch 带在 sampled domain 内的
  empirical 结构。**F4 的 per-branch multiplicity audit 澄清**：每条
  B_N 自身的 max row / column multiplicity 均为 1 —— 即
  "five branch families coexist; per-branch multiplicity = 1"
  （每条 branch 在 fixed-gamma row 与 fixed-K column 上均单值；
  不冻结全局 K=f(gamma) 假设，因为 5 条 branch 共存且斜向排列）。
- Phi_N 收敛是 numerical grazing evidence，非解析 bifurcation proof。
- OPEN_BOUNDARY 三个方向的域外拓扑未采样（F0 guardrail 规则）。
- 3298 个 recovered 点仅 REF-0.1 verified（双 REF 仅用于 extremal
  points，符合 §31/§51）。

## 18. F3 acceptance

    [x] F2 artifacts source verified（1089 coarse + 179 P1 cells）
    [x] all P0/P1/P2 candidate cells processed（179/179）
    [x] no domain expansion beyond guardrails
    [x] dyadic target resolution achieved（depth 5: 0.0078 deg × 0.0039 K）
    [x] all final adjacent branch cells ≤ 0.01 deg × 0.01 K（5735 cells）
    [x] B_N branch identity assigned（B0–B4）
    [x] Phi_N formally implemented（N 侧 -M_S；N+1 侧 newly-created LAST apogee）
    [x] no min-M_A substitution（index N 显式）
    [x] new-exit dhdt implemented（T_N；全正且趋近 0+）
    [x] recovered events reference verified（3298/3298）
    [x] branch extremal points dual-reference certified（10/10）
    [x] OPEN edges refined and recorded（gamma_lower 7 cells；K_upper 9 cells）
    [x] no hidden Qian topology discovered（23349/23349 QIAN_RTI）
    [x] multiskip audit complete（0 unresolved）
    [x] exact-topology audit complete（0）
    [x] row/column multiplicity audited（5/5，sampled-domain empirical）
    [x] boundary exclusion geometry generated（5735 boxes）
    [x] no boundary fit / no derivative / no B/C/D / no optimization / no STM
    [x] figures generated（3，programmatic + visual PASS）
    [x] all tests PASS / Phase E unchanged / F1 unchanged / F2 canonical unchanged

**F3 = COMPLETE；Ready for F4 = YES**

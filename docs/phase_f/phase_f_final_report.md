# Phase F — gamma0-K Sensitivity and Hybrid-Topology Analysis

状态：**COMPLETE / FROZEN**（2026-08-17）

Branch: `feature/phase-f-gamma-k-sensitivity`
Frozen tags: `phase-f-v1.0`、`gamma-k-sensitivity-v1.0`
Source of truth: `docs/phase_f/sensitivity_protocol.md`（F0–F6 Amendments）、
`tests/data/phase_f_gamma_k_sensitivity_v1.json`（regression snapshot）、
`docs/phase_f/f0_…_f6_*.md` 各阶段报告。

## 1. Purpose and research questions

Phase F 系统表征 QIAN 连续滑翔与 SANGER 大气跳跃混合轨迹对初始弹道倾角
gamma0 与气动升阻比 K 的结构性响应：hybrid regimes 的空间分布、skip-count
transition 的 grazing 几何、fixed-topology 内的局部参数灵敏度、以及
Phase-E common-condition comparison 指标的参数空间结构。

## 2. Frozen Phase-E baseline and scope

- Phase-E（phase-e-v1.0 = 44a99119）physics / comparison protocols /
  regression snapshot / figures 全部保持 frozen，Phase F 零修改。
- 计算域（project-local computational sensitivity window，**非**飞行认证
  包线）：gamma0 ∈ [-9,-1] deg × K ∈ [1,5]，33×33 = 1089 canonical
  centers。
- 生产数值：PRODUCTION_SOLVER_CONFIG（DOP853 rtol=1e-9 state-scaled
  atol max_step=20 s）；F2.1 dense recovery 属于 Phase-F observability
  layer（production max_step 未修改）。

## 3. Parameter domain and protocol

参数语义（F0 冻结）：gamma0 = 初始弹道倾角（内部 rad / 报告 deg）；
K = aerodynamic L/D（无量纲，K > 0）。扰动仅限 (gamma0, K)；其余
configuration 全部 frozen。

## 4. Structured research trajectory APIs

### Qian regime classification（F0.1）

`integrate_qian_research_trajectory`：结构化 terminal kind（RTI /
GROUND_BEFORE_CAPTURE / GROUND_AFTER_CAPTURE_BEFORE_RTI / MAX_TIME /
SOLVER_FAILURE / AMBIGUOUS_SIMULTANEOUS_EVENT），替代 frozen
RuntimeError 单通道；`classify_qian_regime` 纯映射。

### Sanger grazing observability（F2.1）

`integrate_sanger_research_trajectory`：对 production max_step 漏检的
浅 atmosphere excursion 做 dense-output interface-root recovery
（brentq + transversality 验证，x_plus=x_minus）；recovered events 全部
strict-reference verified。

## 5. Coarse hybrid-regime map

F2 canonical map（1089 点，v2 cache）：

- **Qian：1089/1089 QIAN_RTI**（single sampled topology）。
- **Sanger：SRTI_N0 ×322、N1 ×306、N2 ×211、N3 ×153、N4 ×85、
  N5 ×12** —— 6 个 skip-count regimes，斜向带状分布。
- OPEN_BOUNDARY：gamma_lower / K_lower / K_upper（guardrail 处，F0 §9
  停止扩展）。

## 6. Grazing-transition geometry

### Phi_N

branch-conditioned signed diagnostic：N 侧（SRTI_N）
`Phi_N = h_SRTI - h_atm = -M_S < 0`；N+1 侧（SRTI_{N+1}）
`Phi_N = h_apogee,new - h_atm > 0`（newly-created LAST VAC apogee，
显式 index N，非 min M_A）。

### N-side / N+1-side structure

5 条 branch（B0 N0/N1 … B4 N4/N5）全部呈现 one-sided margin 结构：
N 侧 M_S → 0（closest Phi 小至 -0.08 m @ B0）、N+1 侧新 apogee → 0
（closest Phi 小至 +0.036 m @ B3）—— 两侧向 h=h_atm ∧ gamma=0 的
limiting grazing geometry 收敛。

### exit transversality

newly-created exit 的 `T_N = dh/dt → 0+`（最小 0.48 m/s @ B0、
0.64 m/s @ B3）—— transversal-event saltation formula 的
`n^T f_minus = dh/dt` 分母在 grazing limit 病态（未来阶段单独处理）。

## 7. Adaptive boundary refinement

F3：二维 dyadic cell refinement（integer lattice）将 179 个 P1 候选
cells 精化到 Δgamma ≤ 0.0078 deg × ΔK ≤ 0.0039 K（5735 refined boxes、
max_depth 6、零 UNRESOLVED_MULTISKIP）；10 个 branch-extremal points
全部 REF-0.1 + REF-0.05 dual-certified；recovered points 3298 全部
REF-0.1 verified；grazing margin 随 depth 单调收敛（depth 0 → 6：
B0 -17.8 → -0.08 m）。

## 8. Fixed-topology derivative definition

ordinary parameter derivatives 仅在 fixed exact topology interior 定义：
central FD，`D_gamma` per radian（per-degree 显式报告）、`D_K` per unit
K；stencil gate（guardrail + F3 segment-rect exclusion + exact topology
identity + recovered/grazing exclusion）；这是 parameter-output
Jacobian（非 STM / saltation）。

## 9. FD convergence and numerical derivative reference

- GLOBAL_STEP_POLICY：**h_gamma = 0.1 deg、h_K = 0.025**
  （O(h²) 收敛，REF-0.1/0.05 self-stable）；adaptive
  largest-safe-converged fallback 已冻结备用。
- production vs reference 绝对误差按维度远低于 1% 参考值。

## 10. Structural sensitivity maps

F5（1089 centers）：

- Qian：全域单 topology、derivative 平滑（field health 0 jumps）、
  dR/dgamma 全正（median 2.30e7 m/rad）。
- Sanger：piecewise smooth、regime-dependent：
  - **dR/dgamma：N0 全正（285 点）→ N1/N2/N3 混合 → N4/N5 全负**；
  - dR/dK 全域正且随 regime 单调增强（N0 1.8e5 → N5 2.0e6 m/unitK）；
  - dT/dgamma：N0 正 → N≥1 负（magnitude 递增）。
- within-regime sign changes：dR/dgamma 在 N1/N2/N3 内。
- grazing 带（F3 boxes）沿线 ordinary derivative deliberately undefined。

## 11. Phase-E common-condition comparison surfaces

F6（corrected，1089 centers，Phase-E Protocol B/C/D 原样复用）：

- Protocol B：DeltaR_time 全域正（median 765 km）；common-time Sanger
  checkpoint ATM 812 / VAC 277。
- Protocol C：time_saving 全域正（median 137.8 s）；range monotonicity
  1089/1089；residuals < 1e-6 m。
- Protocol D：**UNIQUE 1089、AMBIGUOUS 0**（canonical 域无 VAC-plateau
  ambiguity；21 个 endpoint float-edge 经 Phase-F numerical hardening
  resolve，strict references 确认 UNIQUE）。

## 12. Dynamic limiter structure

Phase-E baseline 三个 limiter 均 Qian，但 parameter map 中**全部切换**：

| limiter | QIAN | SANGER |
|---|---|---|
| time | 651 | 438 |
| range | 733 | 356 |
| exposure | **376** | **713**（Sanger 主导）|

limiter 高度 regime 依赖（N0 全 Sanger、N3–N5 全 Qian）。limiter
transition 是 comparison-semantic transition，不是 hybrid topology
transition（314→269 个 signature-transition cells 单独记录）。

## 13. Numerical / regression audit

F7A：float-edge 21/21 resolve（Phase-F-only endpoint snapping，
Phase-E source 零修改）；REF-0.1 36 点 + REF-0.05 27 点
self-stability，0 categorical mismatch；dimension-specific 误差全部
在 E6 scale 内（range worst 1.2 m @ grazing extremal，相对 1.7e-7）；
regression snapshot 冻结（`tests/data/phase_f_gamma_k_sensitivity_v1.json`，
schema `phase-f-gamma-k-sensitivity-regression-v1`）。

## 14. Integrated scientific interpretation

三层结论：

- **Layer 1 — hybrid topology**：Sanger parameter space 被 repeated
  grazing transitions（B0–B4，5 条）分割为 N0–N5 skip-count regimes；
  Qian 保持单一 sampled hybrid topology。
- **Layer 2 — local sensitivity**：fixed regimes 内 ordinary
  derivative fields piecewise smooth 且 regime-dependent
  （dR/dgamma 从 N0 全正过渡到 N4/N5 全负）。
- **Layer 3 — common-condition performance structure**：Protocol B/C/D
  metrics 与 limiting-side semantics 随参数空间系统变化（差异幅度随
  skip regime 单调增强；limiter 身份动态切换）。

## 15. Claim boundaries and limitations

- 计算域是 project-local computational window，非飞行认证包线。
- grazing 结论是 numerical refined hybrid grazing transition
  （Phi_N 收敛 + REF certification），**非解析 bifurcation proof**。
- ordinary derivatives 不跨 topology；grazing 邻域
  （3298 recovered + 10 certified extremals + boxes 内）留给未来
  saltation/FTLE。
- common-condition 指标全正为 descriptive sign distribution，**非
  winner / superiority claim**。
- 不做：optimization、uncertainty、Monte Carlo、STM/saltation/FTLE、
  thermal/TPS 结论。

## 16. Phase F acceptance

    [x] baseline anchor 精确复现（capture/RTI/SRTI diff = 0）
    [x] 1089 canonical centers 全部分类（Qian 单 topology、Sanger N0-N5）
    [x] 5 条 grazing branches 数值认证（5735 boxes、10 extremal certified）
    [x] FD policy 冻结（0.1 deg / 0.025）+ structural maps（F5）
    [x] Protocol B/C/D comparison surfaces（F6 corrected）
    [x] float-edge resolved numerically + REF self-stability
    [x] regression snapshot 冻结 + 426 tests PASS + Phase-E 12 PASS
    [x] frozen physics / Phase-E protocol source / Phase-E JSON 零修改
    [x] Phase-E 旧 tags 未移动

## 17. Implications for future predictability research

F3 已观察 atmosphere-interface grazing：
`n^T f_minus = dh/dt → 0+` → standard transversal saltation formulas
near grazing 需专门处理。未来阶段可研究 STM、saltation、FTLE、
finite-time predictability —— Phase F 未计算这些量；exact event
metadata（F2.1 recovered events、F3 certified extremals、F7A audit
anchors）已为这些研究保留必要输入。

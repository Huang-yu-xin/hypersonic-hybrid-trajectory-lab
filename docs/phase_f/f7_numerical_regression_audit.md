# F7 — Numerical and Regression Freeze Audit

状态：**COMPLETE**（F7A，2026-08-17）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `a1e2fe9`（F6）
Artifacts: `results/gamma_k_sensitivity/final_audit/`（untracked）
Snapshot: `tests/data/phase_f_gamma_k_sensitivity_v1.json`（tracked）

## 1. Purpose

Phase F 最终数值与回归冻结审计：解决 F6 common-condition 的
endpoint float-edge 数值语义问题、补齐 REF-0.1/REF-0.05
self-stability、验证全部跨阶段 anchors、建立 Phase-F production
regression snapshot，并确认 frozen physics 与 Phase-E protocol source
零修改。

## 2. Frozen Phase-F chain

F0 1cd0bd5 → F0.1 81b3a99 → F1 417b2a4 → F2.1 6d6ee7f → F2 35c6637 →
F3 255490f → F4 79f39a5 → F5 fdba521 → F6 a1e2fe9。Phase-E anchor
44a99119（phase-e-v1.0 / qian-sanger-comparison-v1.0）。

## 3. F6 float-edge audit

- 原 F6 记录：Protocol C 15 FLOAT_EDGE、Protocol D 21 FLOAT_EDGE。
- corrected canonical map：**Protocol C float-edge = 0**（旧 15 个在
  corrected 运行中不再出现 —— 旧数字来自早期运行的数据语义）；
  **Protocol D float-edge = 21**，全部集中在 SRTI_N1 regime
  （gamma0 ∈ [-6.5, -2.25] deg，K ∈ [2.25, 4.75]）。
- 根因（§5 分类 C/D 组合）：Protocol D 的 exposure inverse
  （`time_at_atmospheric_exposure`）在 Sanger 为 exposure limiter 时
  数学上恰等于 stored terminal endpoint，但 reconstruct 的
  `t_s = terminal + 2.3e-13 s`（几 ulp）；`_check_time_in_domain` 的
  严格 `t > terminal` 比较 → ValueError。这是 floating arithmetic
  reconstructs `t = terminal + epsilon`（C 类），**非物理 undefined、
  非 plateau ambiguity、非 API bug**。

## 4. Endpoint numerical hardening

- Phase-E B/C/D source **零修改**（comparison.py / comparison_protocols.py
  / comparison_mechanisms.py source-wise 不变）。
- Phase-F-only 方案：`SnappedComparisonTrajectory`（comparison_mapping.py）
  在 `_check_time_in_domain` 层做 exact-endpoint snapping —— 查询时间
  与 stored endpoint 差 ≤ `ENDPOINT_SNAP_TOL_S = 1e-6 s`（Phase-E
  `_TIME_TOL_S`）时 canonicalize 到该 endpoint。
- 满足 F7 §9 全部 8 条：只在 Phase-E tolerance 内、snap 到真实 stored
  endpoint、不改 metric formulas、不平均 endpoint、非 nearest sample、
  不扩 domain、不吸 interior 点（interior 查询远离 endpoint 毫秒级）、
  metadata 记录。
- 覆盖 `_check_time_in_domain`（而非仅 `state_at_time`）→ 所有查询路径
  （state_at_time / mode_at_time / atmospheric_exposure_at_time / range
  inversion / Protocol-D tau consistency）都经 canonicalization。
- **21/21 float-edge points resolve 为 UNIQUE**；baseline 逐位不变。

## 5. REF-0.1 / REF-0.05 self-stability

- dual-reference audit（production + REF-0.1 + REF-0.05）对原 21 个
  float-edge 点：19 个 REF 双稳定 UNIQUE；2 个边界情形
  （(-3.50, 3.875) 双 REF float-edge、(-3.00, 4.500) REF-0.1 float-edge
  / REF-0.05 UNIQUE）在 hardening 后全部 UNIQUE，strict references
  确认 UNIQUE semantics。
- **F7A final audit：36 点 REF-0.1 + 27 点 REF-0.05 subset
  （baseline + 5 recovered + 10 F3 extremals + per-regime deep interior
  + per-limiter），categorical mismatches = 0，REF-0.05 mismatches = 0。**
- 修正后 F6 正式状态：**Protocol D UNIQUE = 1089、AMBIGUOUS = 0、
  FLOAT_EDGE = 0** —— "FLOAT_EDGE resolved numerically"。

## 6. Hybrid topology audit

- Qian：1089/1089 QIAN_RTI（single sampled topology）。
- Sanger：N0 ×322、N1 ×306、N2 ×211、N3 ×153、N4 ×85、N5 ×12。
- 5 条 grazing branches B0–B4（F3 refined cells = 5735，max box
  ≤0.0078125 deg × 0.00390625 K）；OPEN edges = gamma_lower /
  K_lower / K_upper（guardrail 处）。

## 7. Grazing-boundary anchors

- Phi_N sign consistency = 100%（N 侧 < 0、N+1 侧 > 0）。
- 10 个 branch-extremal anchors 全部 dual-reference certified
  （REF-0.1 + REF-0.05 topology equal + Phi 一致），snapshot 记录
  production/REF Phi。
- recovered canonical centers = 5，全部 strict-reference audited。

## 8. FD/Jacobian anchors

- GLOBAL_STEP_POLICY：h_gamma = 0.1 deg、h_K = 0.025（F4 不变）。
- baseline Jacobians 冻结：Qian 5×2、Sanger 7×2（per radian / per
  unit K），snapshot 记录全值。

## 9. F5 structural-map anchors

- Qian gamma/K：GLOBAL 1023 + guardrail 66。
- regime sign classes（categorical regression）：
  - dR/dgamma：N0 全正、N1/N2/N3 混合、N4/N5 全负；
  - dR/dK 全域正；Qian dR/dgamma 全域正。

## 10. F6 comparison-map anchors（corrected）

- 1089 centers；Protocol B 1089 VALID、C 1089 VALID（range monotonicity
  Qian/Sanger 1089/1089）、D UNIQUE 1089。
- limiters：time QIAN 651/SANGER 438、range 733/356、
  exposure 376/**713**（Sanger 主导）。
- checkpoint modes：common-time ATM 812/VAC 277、common-range
  ATM 647/VAC 442、common-exposure ATM 1068。
- comparison signatures = **15**（float-edge resolve 后 19→15）；
  signature-transition cells = **269**（314→269）by reason
  （MULTIPLE/EXPOSURE_LIMITER/PROTOCOL_D_STATUS/SANGER_TOPOLOGY/
  TIME_LIMITER/RANGE_LIMITER）。
- metric sign classes：DeltaR_time / time_saving / DeltaR_tau 全域正
  （descriptive sign distribution）。
- baseline B/C/D anchors 与 Phase-E 参考 diff = 0.0。

## 11. Dimension-specific numerical errors

F7A final audit（36 点 production vs REF-0.1）：

| dimension | max error | median | worst point |
|---|---|---|---|
| time [s] | 9.9e-7 | 2.7e-8 | interior |
| range [m] | 1.20 | 3.5e-4 | B3 extremal (-8.055, 3.980)，相对 1.7e-7 |
| velocity [m/s] | 2.8e-6 | 6.6e-7 | interior |
| energy [J/kg] | 0.54 | 2.1e-3 | interior |
| exposure [s] | 8.5e-5 | 1.2e-7 | interior |

（range worst 1.2 m 位于 grazing 邻域 certified extremal，为
production/REF solver 差异的自然结果，相对误差 1.7e-7；所有 categorical
语义 exact 一致。无 mixed-unit 全局误差。）

## 12. Regression snapshot

`tests/data/phase_f_gamma_k_sensitivity_v1.json`：

- schema `phase-f-gamma-k-sensitivity-regression-v1`；
- source_commit：phase_e_anchor + F0–F6 SHAs；
- domain / topology / grazing anchors / FD policy + baseline Jacobians /
  F5 sign classes + availability / corrected F6 semantics（status
  counts、limiters、checkpoint modes、signatures、transitions、metric
  sign classes、baseline B/C/D）；
- categorical 字段 exact equality、numeric 字段 dimension-specific
  tolerance（E6 scale：time/exposure 1e-3 s、range/altitude 1 m、
  velocity 1e-2 m/s、energy 0.1 J/kg）。
- 测试：`tests/test_phase_f_numerical_regression.py`（17 tests，
  快速稳定，不跑完整 canonical runners）。

## 13. Cross-phase regressions

- pytest 全套（409 + 17 新增）PASS；Phase-E numerical regression
  12 passed；Qian historical PASS；F1 PASS；F2 COMPLETE（1089 点不
  变）；F3 5735 boxes / 5 branches / 10 extremal certified 不变；
  F4 GLOBAL_STEP_POLICY 0.1/0.025 不变；F5 结构 sign classes 不变；
  F6 corrected（UNIQUE 1089）为 final source of truth。

## 14. Production configuration retained

- PRODUCTION_SOLVER_CONFIG 保留（DOP853 rtol=1e-9 state-scaled atol
  max_step=20 s）—— 未因 recovered points 修改；F2.1 dense recovery
  继续属于 Phase-F observability layer（audit 未发现灾难性失败）。

## 15. F7 acceptance

    [x] F6 float-edge semantics resolved/frozen（21/21 → UNIQUE，REF 双确认）
    [x] C/D formal status counts internally consistent（C 1089 VALID、D 1089 UNIQUE）
    [x] REF-0.1/REF-0.05 self-stability complete（36 + 27 点，0 mismatch）
    [x] no categorical reference mismatch
    [x] topology N0-N5 frozen
    [x] 5 grazing branches frozen（B0-B4，5735 cells）
    [x] F3 regression anchors frozen（Phi 100% 一致、10 extremal certified）
    [x] F4 FD policy frozen（0.1 deg / 0.025）
    [x] F5 structural patterns frozen（N0 正/N4-N5 负、dR/dK 全正）
    [x] corrected F6 comparison semantics frozen（UNIQUE 1089、15 signatures）
    [x] Phase-F regression snapshot frozen（tests/data/...v1.json）
    [x] full tests PASS（426）
    [x] Phase E regression PASS（12）
    [x] frozen physics unchanged
    [x] Phase-E B/C/D source unchanged
    [x] F7A audit runner PASS（final_audit artifacts 完整）

**F7A = COMPLETE；进入 F7B（Phase F final freeze）**

# F4 — Fixed-Regime Local Sensitivity and FD Convergence

状态：**COMPLETE**（2026-08-17）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `255490f`（F3）
Artifacts: `results/gamma_k_sensitivity/fd_convergence/`（untracked）

## 1. Purpose

在 F3 boundary-exclusion geometry 内，对 fixed exact topology 代表点安全
计算 ordinary parameter derivatives（dy/dgamma0, dy/dK），研究 central
finite-difference 的 step convergence，构建 high-precision numerical
derivative reference（REF-0.1/0.05），量化 production 与 reference 的
导数误差，冻结 global 或 adaptive FD step policy，并生成 Qian 5×2 /
Sanger 7×2 局部 parameter-output Jacobians。

**不是**：STM / variational matrix / saltation matrix / FTLE /
optimization / Phase-E B/C/D surfaces / elasticity / composite score。

## 2. F3 boundary-exclusion handoff

- 输入：F3 `boundary_exclusion_cells.json`（5735 个 refined boxes，
  ≤0.0078 deg × 0.0039 K）+ F2 canonical coarse points（1089）。
- 硬几何 gate：stencil 的 center→minus / center→plus 线段与任一
  exclusion box 相交 → derivative 不存在（不只检查端点 label ——
  线段可能穿过窄 box 再回到同 label）。

## 3. Ordinary derivative definition

- 仅定义在 fixed exact topology interior：
  - `D_gamma(h) = [y(g+h) - y(g-h)] / (2 h_rad)`，`h_rad = h_deg·π/180`；
    canonical 存储单位 **per radian**；per-degree 版本显式报告
    （= per-rad · π/180）。
  - `D_K(h) = [y(K+h) - y(K-h)] / (2h)`，单位 **per unit K**。
- 这是 **parameter-output Jacobian** `J = ∂y_terminal/∂(gamma0, K)`，
  不是 STM、不是 variational matrix、不是 saltation matrix。
- skip_count 是离散 topology label，**永不微分**；max-based 非光滑
  observable 不入 vector。

## 4. Representative fixed-topology points

自动从 F2 coarse points 选择（排除 exclusion box 内 / recovered /
grazing / health anomaly / 无法支持最大候选 stencil 的 guardrail 点；
`selection_clearance` 仅为选点诊断，非科学 metric）：

| label | gamma0 | K | Sanger regime | baseline | clearance |
|---|---|---|---|---|---|
| baseline | -5.0 | 3.0 | SRTI_N2 | YES | 0.094 |
| regime-SRTI_N0 | -1.25 | 1.125 | SRTI_N0 | — | 1.586 |
| regime-SRTI_N1 | -4.5 | 2.375 | SRTI_N1 | — | 0.481 |
| regime-SRTI_N2 | -8.75 | 2.5 | SRTI_N2 | — | 0.406 |
| regime-SRTI_N3 | -8.25 | 3.5 | SRTI_N3 | — | 0.371 |
| regime-SRTI_N4 | -7.0 | 4.875 | SRTI_N4 | — | 0.465 |
| regime-SRTI_N5 | -8.75 | 4.875 | SRTI_N5 | — | 0.133 |

6 个 Sanger regimes 全部获得 safe FD representative（无
REGIME_NO_SAFE_FD_REPRESENTATIVE）。

## 5. Stencil eligibility

- 70 个候选 stencils（7 reps × 2 params × 5 steps）：**70/70 eligible**
  （Qian 与 Sanger 均通过）；boundary-intersection rejected = 0、
  topology-change rejected = 0、recovered rejected = 0、
  guardrail rejected = 0。
- 模型特定 gate：Qian 导数只要求 Qian exact topology 一致；Sanger
  导数要求 Sanger topology + F3 exclusion geometry safe。

## 6. Gamma-step convergence

候选 steps：0.1 / 0.05 / 0.025 / 0.0125 / 0.00625 deg。

典型（baseline，Sanger srti_range，per radian，reference 序列）：

| h [deg] | D_ref [m/rad] | |D(h)-D(h/2)| |
|---|---|---|---|
| 0.1 | -5.305e6 | — |
| 0.05 | -5.306e6 | 4020 |
| 0.025 | -5.306e6 | 978 |
| 0.0125 | -5.306e6 | 243 |
| 0.00625 | -5.306e6 | 61 |

successive diffs 每层 ~4 倍收缩（**O(h²) central-difference 收敛**，
observed order p_obs ≈ 2，仅作 numerical diagnostic）。所有 7 个代表
点、所有 primary non-negligible outputs 在 h = 0.1 deg 即进入相对
plateau（|D(h)-D(h/2)| ≤ 1% |D_ref|，连续两层）。

## 7. K-step convergence

候选 steps：0.05 / 0.025 / 0.0125 / 0.00625 / 0.003125。

- h = 0.05：部分代表点/输出的 successive diff 仍 > 1% |D_ref|；
- **h = 0.025 起**：全部代表点、全部 non-negligible primary outputs
  进入相对 plateau（O(h²) 收敛同样成立）。

## 8. High-precision derivative reference

- REF-0.1（DOP853, rtol=1e-12, atol=[1e-7,1e-14,1e-10,1e-14],
  max_step=0.1）在同样 topology-safe stencils 上计算 central FD 序列；
  这是 numerical finite-difference reference（非 analytic derivative）。
- **REF-0.1 vs REF-0.05 self-stability：PASS**（finest-h 导数：
  topology identical 全部 TRUE；baseline max abs diff = 0.022
  [m/rad 维度]，相对 10^6 量级为 1e-8 级）。
- reference topology gate：reference plus/minus 与 center 同 exact
  topology（全部通过；无 REFERENCE_TOPOLOGY_MISMATCH）。
- unresolved components：**0**。

## 9. Production-vs-reference derivative accuracy

按 output dimension 分别报告绝对误差（近零导数不报巨大相对 %）：

| 方向 | 模型 | 最大 abs err 示例 |
|---|---|---|
| gamma | Qian range [m/rad] | ~0.02（相对 2.5e7 ≈ 1e-9）|
| gamma | Qian time [s/rad] | ~1.5e-6 |
| gamma | Sanger range [m/rad] | ~0.57（相对 10^6 量级 ≈ 1e-6）|
| gamma | Sanger time [s/rad] | ~1.1e-4 |
| K | Qian/Sanger 各输出 | 全部 ≤ 1e-1（相对同量级）|

production derivative 与 reference 的绝对误差在各维度均远低于该维度
参考值 1% —— 数值 floor 记录于 `production_vs_reference.json`。

## 10. Approved FD step policy

**冻结：GLOBAL_STEP_POLICY（两个参数分别全局）**

- **h_gamma = 0.1 deg**（per-radian canonical）：最大候选 step 即达
  全局相对 plateau（O(h²) 收敛非常干净；更小 step 无 material 改善）。
- **h_K = 0.025 per unit K**：0.05 未全局达标，0.025 起全局 plateau。
- 判据（dimension-aware，已文档化）：plateau = 连续两层
  |D(h)-D(h/2)| ≤ 0.01 · |D_ref|；negligible output 阈值
  gamma 1e-3/rad、K 1e-2/unitK 不参与 policy 判据。
- 若未来 F5 某点无法满足 gate/plateau → 按 F4 §24
  ADAPTIVE_STEP_POLICY（largest-safe-converged）回退（本轮不需要）。

## 11. Baseline local Jacobian（production，approved steps）

**Qian（5×2；d/dgamma0 per rad，d/dK per unit K）**：

| output | d/dgamma0 | d/dK |
|---|---|---|
| qian_rti_time_s [s] | +2926.9 | +216.5 |
| qian_rti_range_m [m] | +2.550e7 | +9.988e5 |
| qian_rti_altitude_m [m] | +1.158e5 | +2.653e3 |
| qian_rti_velocity_mps [m/s] | +2.054e4 | +26.1 |
| qian_energy_loss_jpkg [J/kg] | -6.669e7 | -1.089e5 |

**Sanger（7×2）**：

| output | d/dgamma0 | d/dK |
|---|---|---|
| sanger_srti_time_s [s] | -2010.2 | +140.4 |
| sanger_srti_range_m [m] | -5.305e6 | +1.101e6 |
| sanger_srti_altitude_m [m] | -1.056e5 | +1.477e4 |
| sanger_srti_velocity_mps [m/s] | +9275.9 | +486.5 |
| sanger_energy_loss_jpkg [J/kg] | +1.239e7 | -1.238e6 |
| sanger_atm_duration_s [s] | -1.787e3 | +176.7 |
| sanger_vac_duration_s [s] | +1.677e3 | -102.2 |

解释（**仅 local**，不外推）：baseline 处 gamma0 更浅 → Qian RTI 更晚/
更远（正导数）、Sanger SRTI 更早/更近（负导数）；K 增大 → 两者 RTI/SRTI
时间均延后、射程增大。

## 12. Cross-regime representative Jacobians（Sanger）

| regime | dT/dgamma [s/rad] | dR/dgamma [m/rad] | dv/dgamma [(m/s)/rad] | dT/dK [s/unitK] | dR/dK [m/unitK] | dv/dK [(m/s)/unitK] |
|---|---|---|---|---|---|---|
| N2 (baseline) | -2010 | -5.31e6 | +9276 | +140 | +1.10e6 | +486 |
| N0 | +2439 | +1.75e7 | +3296 | +36 | +3.31e5 | +923 |
| N1 | -865 | -1.05e6 | +8045 | +101 | +7.93e5 | +498 |
| N2 (deep) | -1166 | +1.91e6 | +10679 | +244 | +1.79e6 | +842 |
| N3 | -2410 | -2.32e6 | +10551 | +237 | +1.75e6 | +564 |
| N4 | -4559 | -1.33e7 | +10065 | +195 | +1.47e6 | +344 |
| N5 | -3982 | -4.78e6 | +10890 | +270 | +1.98e6 | +440 |

观察（local only）：dR/dgamma 的符号在 regime 间变化（N0 正、多数
N≥1 负、deep-N2 正）—— **明确展示局部导数的 regime 依赖性**，禁止
外推（F4 §29）。所有导数均为 raw physical derivatives；无 elasticity /
normalized index / composite score。

## 13. Per-branch multiplicity clarification

F3 报告的 row/column multiplicity = 5/5 是"一条 row 穿过 5 条 branch
带"。**per-branch audit**：

| branch | max row multiplicity | max column multiplicity |
|---|---|---|
| B0 | 1 | 1 |
| B1 | 1 | 1 |
| B2 | 1 | 1 |
| B3 | 1 | 1 |
| B4 | 1 | 1 |

即每条 B_N 在 fixed-gamma row 与 fixed-K column 上均**单值**：
"five branch families coexist; per-branch multiplicity = 1"。F3 文档
已做 minimal wording correction（boxes/Phi/certification 数值不变）。

## 14. Limitations

- 导数是 local（representative points），非全域 map（F5）。
- Reference 是 numerical FD reference，非 analytic/exact。
- 7 个代表点覆盖 6 regimes；N5 的 clearance 最小（0.133）—— 其导数
  最接近 exclusion geometry，F5 需保留 gate。
- production/reference 误差按维度记录；不合成 mixed-unit 全局误差。

## 15. F5 handoff

- 冻结执行器：`sensitivity_fd` 的 stencil gate + GLOBAL_STEP_POLICY
  （gamma 0.1 deg / K 0.025）。
- F5 全域 sensitivity map 必须 mask topology boundaries（5735 exclusion
  boxes）+ recovered/grazing 点 + guardrail 越界 stencils；
  跨 exact topology 的差分为 undefined（协议 §27）。
- 每个采样点使用 `evaluate_stencil` gate 后执行 central FD；
  ADAPTIVE 回退规则已冻结备用。

## 16. F4 acceptance

    [x] baseline local derivatives available（Qian 5×2 + Sanger 7×2）
    [x] gamma derivative per-radian canonical（per-degree 显式报告）
    [x] K derivative per unit K
    [x] boundary-exclusion geometry enforced（segment-rect gate，70/70 stencils）
    [x] exact-topology gate enforced（0 topology-change rejection）
    [x] recovered points excluded（0 recovered stencils）
    [x] candidate step convergence studied（5+5 steps，O(h²) 观察）
    [x] high-precision numerical derivative reference constructed（REF-0.1）
    [x] reference derivative self-stability audited（REF-0.05，PASS）
    [x] production-vs-reference derivative errors quantified（各维度）
    [x] no mixed-unit global error
    [x] GLOBAL_STEP_POLICY frozen（gamma 0.1 deg / K 0.025）
    [x] Qian 5×2 Jacobian built（每 eligible representative）
    [x] Sanger 7×2 Jacobian built（每 eligible representative）
    [x] no discrete topology derivative（skip_count 排除）
    [x] no normalized composite sensitivity / no elasticity
    [x] per-branch multiplicity clarified（全部 1/1）
    [x] no STM/saltation/FTLE / no Phase-E B/C/D surface
    [x] all tests PASS

**F4 = COMPLETE；Ready for F5 = YES**

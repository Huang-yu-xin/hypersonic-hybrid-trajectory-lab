# F5 — Fixed-Topology Structural Sensitivity Mapping

状态：**COMPLETE**（2026-08-17）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `79f39a5`（F4）
Artifacts: `results/gamma_k_sensitivity/structural_sensitivity/`（untracked）

## 1. Purpose

在 F2 canonical 33×33 = 1089 centers 上映射 Qian 5×2 与 Sanger 7×2 局部
parameter-output Jacobians 的空间变化（仅 fixed exact topology interior；
F3 exclusion geometry 处 deliberately undefined）。研究 derivative fields
的 spatial structure、regime 间 magnitude/sign 差异、within-regime sign
changes，验证 F4 global FD policy 的全域覆盖率，并为 F6 comparison
surfaces 提供 fixed-topology structural background。

**不做**：Phase-E B/C/D surfaces、winner map、optimization、uncertainty、
STM/saltation/FTLE、topology derivative、boundary fitting。

## 2. F4 derivative policy

- 复用 F4 冻结语义：`D_gamma` per radian（per-degree 仅 visualization）、
  `D_K` per unit K；stencil gate（guardrail + segment-rect exclusion +
  exact topology + recovered/grazing exclusion + valid terminal）；
  plateau 判据 = 连续两层 |D(h)-D(h/2)| ≤ 1% |D_ref|（F4 §24）。
- GLOBAL_STEP_POLICY first：h_gamma=0.1 deg、h_K=0.025；h/2 plateau
  audit map-wide；失败 → ADAPTIVE_STEP_POLICY（largest-safe-converged；
  gamma 0.05→0.00625 deg；K 0.0125→0.003125→0.0015625 last resort）。
- 模型特定 mask：Qian 从不因 Sanger exclusion geometry mask（只查 Qian
  topology + guardrail + valid）；Sanger 额外强制 F3 geometry/topology/
  recovered gates。

## 3. Canonical sensitivity domain

33×33 = 1089 centers（gamma0 -9..-1 deg step 0.25；K 1..5 step 0.125），
全部为 F2 canonical 点（无 uniform dense upsampling）。baseline F4
reproduction gate PASS（(-5,3) Jacobian 与 F4 记录相对差 < 2%）。

## 4. Derivative availability / masking

| model/param | GLOBAL | ADAPTIVE | BOUNDARY | TOPOLOGY | RECOVERED | GUARDRAIL | NO_CONV |
|---|---|---|---|---|---|---|---|
| Qian gamma | 1023 | 0 | 0 | 0 | 0 | 66 | 0 |
| Qian K | 1023 | 0 | 0 | 0 | 0 | 66 | 0 |
| Sanger gamma | 878 | 119 | 14 | 3 | 0 | 66 | 9 |
| Sanger K | 925 | 80 | 14 | 2 | 0 | 66 | 2 |

- **Qian：1023/1023 全 GLOBAL**（单 sampled topology 内几乎全域可导；
  仅 guardrail 66 不可用）—— 无 adaptive、无 mask、无 convergence 失败。
- Sanger：global 覆盖率 gamma 80.6%、K 84.9%；adaptive 119/80；
  boundary-intersection 14（grazing 带沿线）；topology-change 3/2；
  NO_CONVERGENCE 9/2（grazing 邻域内 plateau 未达）；guardrail 66。
- recovered-event masked = 0（stencil 端点 recovered 被 gate 挡在
  BOUNDARY/其他 status 内或未触及 —— F4 conservative policy 保持）。

## 5. Global vs adaptive FD usage

- gamma h=0.1：878/1089 GLOBAL_ACCEPTED（80.6%）；119 adaptive
  （选 step 分布见 `adaptive_fallback.json`，集中在 grazing 带邻域）。
- K h=0.025：925/1089（84.9%）；80 adaptive。
- **F4 global policy 在全域基本验证**：>80% canonical centers 直接
  global accepted；其余 adaptive 补足；NO_CONVERGENCE 仅 9/2 个点。

## 6. Numerical reference audit

- deterministic 61 点 sample（baseline + 每 regime ≥3（deepest-clearance
  / lowest-gamma / highest-gamma）+ 每 regime extremal dR/dgamma + 全部
  adaptive 点分层）→ REF-0.1 在 approved step 与 h/2 上验证；
  REF-0.05 subset 7 点（baseline + 每 regime 一个 extremal）。
- topology mismatches = 0；audit failures = 0；未触发
  REFERENCE_AUDIT_FAILED mask。
- 按 dimension 的 production/reference 绝对误差与 F4 同量级
  （range ~0.1-1 m/rad 量级相对 10^6-10^7，time ~1e-4 s/rad 量级）。

## 7. Qian sensitivity structure

whole-domain（1023 points，per radian）：

| output | min | median | max | sign |
|---|---|---|---|---|
| dR_RTI/dgamma0 [m/rad] | +5.92e6 | +2.30e7 | +4.57e7 | 全正 |
| dT_RTI/dgamma0 [s/rad] | +873 | +2539 | +4571 | 全正 |
| dE_loss/dgamma0 [J/kg/rad] | -1.21e8 | -6.55e7 | -2.37e7 | 全负 |
| dR_RTI/dK [m/unitK] | 全正 | — | — | 全正 |

Qian exhibits a single sampled hybrid topology with ordinary local
parameter derivatives defined across almost the entire interior（guardrail
除外，不外推域外）。

## 8–13. Sanger N0–N5 structural sensitivity

**dR_SRTI/dgamma0（per radian）**：

| regime | count | min | median | max | sign |
|---|---|---|---|---|---|
| N0 | 285 | +3.51e6 | +8.96e6 | +1.77e7 | 全正 |
| N1 | 289 | -8.65e6 | -1.34e5 | +5.83e6 | 混合（143+/146-）|
| N2 | 200 | -1.90e7 | -6.20e6 | +4.00e6 | 混合（34+/166-）|
| N3 | 138 | -2.15e7 | -9.05e6 | +1.76e6 | 混合（5+/133-）|
| N4 | 76 | -1.90e7 | -9.15e6 | -9.37e5 | 全负 |
| N5 | 9 | -9.14e6 | -6.44e6 | -3.90e6 | 全负 |

**dR_SRTI/dK（per unit K）**：全域正；median 随 regime 单调递增
（N0 1.76e5 → N1 8.79e5 → N2 1.16e6 → N3 1.41e6 → N4 1.69e6 →
N5 2.00e6 m/unitK）。

**dT_SRTI/dgamma0（s/rad）**：N0 全正（median +1163）→ N1 起全负且
magnitude 递增（-675 → -4183 @ N5）。

**dE_loss/dgamma0（J/kg/rad）**：全域负，median -2.3e7（N0）→
-4.9e7（N4/N5）。

## 14. Cross-regime structural patterns

- **局部灵敏度方向 regime-dependent**：dR/dgamma 从 N0 全正过渡到
  N4/N5 全负；dT/dgamma 在 N0 为正、N≥1 为负 —— 与 F4 代表点结论一致
  （F4 §29 不外推原则的 map-wide 确认）。
- dR/dK 全域正且随 regime 单调增强 —— K 增大总增大 SRTI range
  （各 regime 内局部观察，非全局因果声明）。
- **WITHIN_REGIME_SIGN_CHANGE**：Sanger dR/dgamma 在 N1/N2/N3 内
  （相邻 canonical centers 正负共存）、dT/dgamma 在 N1 内、dE 无 ——
  重要 structural result（未定位 zero-contour，F5 不新增 stationary
  refinement）。
- Sanger ordinary derivative fields are piecewise defined on fixed
  skip-count regimes and masked at grazing-transition bands。

## 15. Sign structure

见 §7/§8–13 表；near-zero floor：gamma 1e-3/rad、K 1e-2/unitK（F4
冻结）。全域无 near-zero 输出（所有非 negligible 导数远离 0）。

## 16. Core figures

| figure | dims | size | visual |
|---|---|---|---|
| F5_F1_qian_range_sensitivity.png | 4200×1800 | 224 KB | inspected |
| F5_F2_sanger_range_sensitivity.png | 4200×1800 | 274 KB | **inspected**（正负沿斜向带分界、mask 沿 grazing 带、无插值痕迹）|
| F5_F3_sanger_time_sensitivity.png | 4200×1800 | 259 KB | inspected |
| F5_F4_sanger_energy_sensitivity.png | 4200×1800 | 298 KB | inspected |
| F5_F5_derivative_availability.png | 4200×3000 | 382 KB | inspected |

所有 Sanger 图：F3 exclusion 区域 blank/masked；derivative = continuous
color（zero-centered diverging），regime boundaries = 细黑/灰 outlines；
无 griddata/cubic/Gaussian 跨 regime 插值。Qian 图不画 Sanger mask。

## 17. Interpretation boundaries

- 禁止："derivative diverges at boundary"（F5 不计算 boundary limit）；
  正确表述：ordinary central derivative is not evaluated across refined
  grazing-transition boxes；grazing-adjacent analysis 保留给未来 hybrid
  sensitivity work。
- 禁止 cross-regime interpolation、跨 topology 差分、Qian-vs-Sanger
  winner/ranking statement、native RTI/SRTI fair-performance claim。
- 近 boundary 的 adaptive/NO_CONVERGENCE 点如实报告（9 gamma / 2 K）。

## 18. F6 handoff

1. Qian fixed-topology sensitivity field：全域单 topology、derivative
   smooth、全正 dR/dgamma / 全负 dE_loss —— F6 common-condition surfaces
   可直接在此 background 上做 Protocol B/C/D（Qian 侧无 mask 顾虑）。
2. Sanger N0-N5 最显著 regime-dependent patterns：dR/dgamma 符号翻转
   （N0 正 → N4/N5 负）、dT/dgamma N0 正 → N≥1 负、dR/dK 全域正随 regime
   递增。
3. within-regime sign change：Sanger dR/dgamma 在 N1/N2/N3 内、dT/dgamma
   在 N1 内（这些区域 sensitivity direction 局部反转）。
4. global FD steps 覆盖率：gamma 80.6%（+11% adaptive）、K 84.9%
   （+7% adaptive）；NO_CONVERGENCE 9/2 点。
5. adaptive/masked 区域：grazing 带沿线 14 BOUNDARY + 3/2 TOPOLOGY +
   adaptive 199 点集中 N1-N3 带邻域；guardrail 66。
6. F6 Protocol B/C/D 必须沿用：Qian/Sanger 独立 mask 语义（Qian 不因
   Sanger grazing 而 mask）、exclusion boxes 内不做 comparison、limiter
   动态记录（F0 §33）。
7. F6 不能把 native RTI/SRTI 直接做 winner surface —— RTI 与 SRTI 的
   feasibility semantics 不同（Phase E E0），comparison 只能在 common
   condition 协议下进行。

## 19. F5 acceptance

    [x] baseline reproduces F4 Jacobian（<2% 相对差）
    [x] 1089 canonical centers processed
    [x] Qian/Sanger masks independent
    [x] gamma global policy applied first（h=0.1 + h/2 audit）
    [x] K global policy applied first（h=0.025 + h/2 audit）
    [x] h/2 convergence checked map-wide
    [x] adaptive fallback applied where required（199 points）
    [x] no unsafe derivative forced
    [x] F3 exclusion geometry enforced for Sanger
    [x] recovered Sanger stencils excluded（conservative policy 保持）
    [x] exact topology gate enforced
    [x] no one-sided derivatives at guardrails
    [x] raw gamma derivatives stored per radian
    [x] regime statistics built（N0-N5 + whole-domain Qian）
    [x] sign structure built（near-zero floor 按 F4 冻结）
    [x] reference audit deterministic（61 点；REF-0.05 subset 7）
    [x] every Sanger regime reference-audited
    [x] production/reference errors quantified by dimension
    [x] audit failures masked（0 failures）
    [x] no widespread F4-policy failure（>80% global accepted）
    [x] no Qian topology discovery
    [x] field health PASS（无 unexpected jumps 报告）
    [x] five figures generated（programmatic + visual）
    [x] no boundary interpolation / no topology derivative
    [x] no Phase-E B/C/D surfaces / no optimization / no STM/saltation/FTLE
    [x] Phase E unchanged / F1-F4 unchanged / all tests PASS

**F5 = COMPLETE；Ready for F6 = YES**

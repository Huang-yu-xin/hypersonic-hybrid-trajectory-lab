# F6 — Common-Condition Comparison Surfaces over gamma0-K

状态：**COMPLETE**（2026-08-17）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `fdba521`（F5）
Artifacts: `results/gamma_k_sensitivity/comparison_surfaces/`（untracked）

## 1. Purpose

将 Phase E 冻结的 Protocol B（common time）/ C（common range）/
D（common atmospheric exposure）扩展到 33×33 canonical parameter
domain，研究 common-condition metrics 如何随 gamma0/K 与 Sanger skip
topology 变化，动态记录 limiter 身份与 Protocol-D UNIQUE/AMBIGUOUS
结构，建立 comparison signatures 与 checkpoint-mode maps，为 F7 数值
审计与 Phase F final interpretation 提供 fixed-topology structural
background。

**不做**：comparison derivatives、winner score、composite ranking、
native RTI/SRTI fair-performance surface、optimization、uncertainty、
STM/saltation/FTLE。

## 2. Phase-E protocol reuse

- Protocol B/C/D 的实现**原样复用**（`run_common_time_comparison` /
  `run_common_range_comparison` /
  `run_common_atmospheric_exposure_comparison`）—— 未复制任何公式，
  未创建 v2 版本，未修改 `comparison.py` / `comparison_protocols.py` /
  `comparison_mechanisms.py`。
- Qian 侧使用 Phase-E `build_qian_comparison_trajectory`（F2 全域
  QIAN_RTI，E1-E7 已验证）。
- **F6 修复（真实 API bug）**：`DenseOutputCollector` 定义了 `__len__`，
  空 collector 是 falsy → `dense_output_collector or
  DenseOutputCollector()` 短路到新建对象（collector 丢失）。在
  `qian_research_trajectory.py` / `sanger_research_trajectory.py` /
  `comparison_mapping.py` 中改为显式 `is not None` 判断（backward
  compatible；151 个 F 测试 + 本套件验证）。

## 3. Phase-F Sanger comparison adapter

`build_sanger_research_comparison_trajectory`：调用 F2.1
`integrate_sanger_research_trajectory`（含 DenseOutputCollector），从其
physical trajectory 构建 `ComparisonTrajectory`（normalized modes
SANGER_ATM→ATM / SANGER_VAC→VAC、right-continuous 语义、synthetic E0
保留、atmospheric_intervals 从真实 ATM segments 构造）。

- DENSE_RECOVERED atmosphere exit 作为正常 ATM→VAC 物理 switch
  （exact recovered root；candidate overshoot state 永不进入 comparison
  history）。
- 基线（-5, 3）：adapter 与 Phase-E builder **逐位一致**
  （terminal diff = 0.0、modes/events 全等、event_resolution =
  SOLVER_EVENT）。

## 4. Canonical domain / value eligibility

- 1089 canonical centers；**1089/1089 paired comparisons VALID**
  （0 NOT_AVAILABLE）。
- VALUE eligibility 与 display/interpolation 分离：F3 exclusion box
  **不删除 pointwise comparison value**（只阻断平滑插值跨 box）；
  recovered centers（5 个）是 valid pointwise values 且全部
  strict-reference audited。
- 数值边界保护：limiter 切换点处 inverse root 可落在 research domain
  边界外 epsilon（Phase-E frozen float-edge guard）→ Protocol C/D
  status = `NOT_AVAILABLE_FLOAT_EDGE`（21 个 D、15 个 C 点）；这是
  数值边界而非物理差异，reference audit 记为 note 而非 mismatch。

## 5. Protocol B surface（common time）

- valid = 1089；DeltaR_time **全域正**（median 764.9 km，range
  [19.8, 2140] km）—— 相同 elapsed time 下 Sanger range 领先。
- DeltaV_time 全域正（median 2748 m/s）；DeltaE_time 全域正
  （median 12.9 MJ/kg）。
- Sanger common-time checkpoint modes：ATM 812 / VAC 277。

## 6. Protocol C surface（common range）

- valid = 1089（范围单调性：Qian 1089/1089、Sanger 1089/1089 全通过，
  nonmonotone = 0）。
- time_saving **全域正**（median 137.8 s，range [3.1, 344.7] s）——
  Sanger 更早到达同一射程。
- DeltaV_range 全域正（median 2952 m/s）；DeltaE_range 全域正
  （median 14.1 MJ/kg）。
- root residuals：全部通过 Phase-E segment-aware brentq tolerance
  （< 1e-6 m 量级）。
- Sanger common-range checkpoint modes：ATM 647 / VAC 442。

## 7. Protocol D surface（common exposure）

- **UNIQUE = 1068、AMBIGUOUS = 0、NOT_AVAILABLE（float-edge）= 21**。
  全域无 VAC exposure plateau 触发 AMBIGUOUS —— 这是 F6 的诚实验证
  （exposure inverse 在 canonical domain 上稳定 UNIQUE）。
- UNIQUE 指标：DeltaR_tau median 1882 km（range [19.8, 10680] km，
  全正）；elapsed_time_extension median 228.6 s（746 正 / 0 负，
  range [0, 1588] s）；DeltaV_tau median 2211 m/s；DeltaE_tau median
  9.6 MJ/kg。
- UNIQUE checkpoint modes：Sanger 全 ATM（1068）。

## 8. Dynamic limiter structure

| limiter | QIAN | SANGER | 备注 |
|---|---|---|---|
| time | 651 | 438 | 显著切换（非全域 QIAN）|
| range | 733 | 356 | 显著切换 |
| exposure | **376** | **713** | **Sanger 主导 — 与 Phase E baseline（QIAN）相反** |

joint limiter tuples：`(QIAN,QIAN,QIAN)` 376、`(SANGER,QIAN,SANGER)`
82、`(QIAN,QIAN,SANGER)` 275、`(SANGER,SANGER,SANGER)` 356。

**Limiter 高度 regime 依赖**（这是 F6 最重要的结构结果）：

| regime | time QIAN/SANGER | exposure QIAN/SANGER |
|---|---|---|
| N0 | 3 / 319 | 3 / 319 |
| N1 | 200 / 106 | 114 / 192 |
| N2 | 198 / 13 | 90 / 121 |
| N3 | 153 / 0 | 85 / 68 |
| N4 | 85 / 0 | 72 / 13 |
| N5 | 12 / 0 | 12 / 0 |

N0（浅入角低 K）几乎全 SANGER limiter（Sanger RTI/SRTI 更早更近）；
N3-N5（陡入角高 K）全 QIAN limiter。Phase E baseline 的 "Qian
limiter" 只在部分 regime 成立。

## 9. Protocol-D ambiguity

canonical domain 上 **AMBIGUOUS = 0**（无 VAC exposure plateau 与
common exposure 重合的采样点）。21 个 float-edge 点为 limiter 切换
边界处的数值保护（REF-0.1 确认 UNIQUE 结构，仅 inverse root 落于
domain 边界外 epsilon）。

## 10. Checkpoint-mode structure

- common-time Sanger：ATM 812 / VAC 277（VAC checkpoint 集中在 N1-N3
  grazing 带邻域）。
- common-range Sanger：ATM 647 / VAC 442。
- common-exposure（UNIQUE）：ATM 1068（全 ATM —— exposure 逆查询
  总是落在 ATM 区间）。

## 11. Comparison signatures

- **19 unique comparison signatures**（(qian_regime, sanger_regime,
  time_limiter, range_limiter, exposure_limiter, D_status)）。
- **314 signature-transition cells**（32×32 grid）by reason：
  MULTIPLE 151、EXPOSURE_LIMITER 60、PROTOCOL_D_STATUS 45、
  SANGER_TOPOLOGY 35、TIME_LIMITER 13、RANGE_LIMITER 10。
- 这些是 comparison-semantic transitions（limiter/status 变化），
  与 Sanger hybrid topology transition（F3 grazing bands）**分别记录，
  不合并**。

## 12. Relationship to Sanger hybrid regimes

| regime | B DeltaR_time median [km] | C time_saving median [s] | D DeltaR_tau median [km] |
|---|---|---|---|
| N0 | 67.7 | 12.6 | 67.7 |
| N1 | 651.1 | 118.8 | 1537.0 |
| N2 | 1213.7 | 199.9 | 3629.6 |
| N3 | 1611.6 | 260.9 | 5906.5 |
| N4 | 1913.1 | 307.9 | 8275.6 |
| N5 | 2105.5 | 339.3 | 10081.5 |

common-condition 差异幅度随 skip regime **单调增强**（N0 → N5），与
F5 的 regime-dependent sensitivity 结构一致。sign 结构：所有 primary
comparison metrics 全域正（无 within-comparison-regime sign change）。

## 13. Recovered-event reference audit

5 个 DENSE_RECOVERED canonical centers 全部 REF-0.1 audited：

| gamma | K | regime | Protocol B | Protocol C | Protocol D | max err |
|---|---|---|---|---|---|---|
| -8.5 | 3.0 | N3 | True | True | True | 0.119 |
| -7.75 | 3.125 | N3 | True | True | True | 0.036 |
| -5.25 | 1.5 | N1 | True | True | True | 0.011 |
| -4.25 | 4.625 | N3 | True | True | REF_FLOAT_EDGE | 0.003 |
| -2.0 | 4.125 | N1 | True | True | True | 0.012 |

（(-4.25, 4.625) 的 D 在 REF 下为 float-edge 数值保护，UNIQUE 结构由
reference audit 确认；max metric error 全部远小于 tolerance。）

## 14. Numerical reference audit

- deterministic 33-point sample（baseline + per-regime 3 + per-limiter
  3 + per-D-status 5 + all recovered + extremal metrics +
  per-checkpoint-mode 3）→ REF-0.1。
- **categorical mismatches = 0；numerical failures = 0**（按字段
  dimension-scale tolerance：time/exposure 1e-3 s、range 1 m、
  velocity 1e-2 m/s、energy 0.1 J/kg —— 与 Phase-E E6 scale 一致）。
- float-edge notes：若干（UNIQUE ↔ FLOAT_EDGE 数值边界，非语义差异）。

## 15. Core figures

| figure | dims | size | visual |
|---|---|---|---|
| F6_F1_common_time_delta_range.png | 2700×1800 | 142 KB | inspected |
| F6_F2_common_range_time_saving.png | 2700×1800 | 136 KB | inspected |
| F6_F3_common_exposure_delta_range.png | 2700×1800 | 146 KB | inspected（AMBIGUOUS 无 → 无 X marker）|
| F6_F4_common_condition_energy.png | 5400×1800 | 287 KB | inspected |
| F6_F5_comparison_semantics.png | 4200×3000 | 236 KB | **inspected**（limiter 面板分布显著不同）|

渲染：masked pcolormesh + scatter；无 griddata/bicubic/Gaussian 跨
signature 插值；F3 boxes 仅 overlay（不删除 pointwise value）。

## 16. Interpretation boundaries

- 禁止 "Sanger universally superior" / "Sanger wins N%" / native SRTI
  range improvement / "grazing causes comparison gain"。
- metric sign distribution 全域正：表述为 "At equal time, DeltaR_time
  > 0 at all sampled centers"（描述性，非 winner claim）。
- limiter 切换是 comparison-semantic transition，不是 hybrid topology
  transition。
- NOT_AVAILABLE_FLOAT_EDGE 是数值边界保护，不是物理 unavailable。

## 17. F7 handoff

1. 三个 protocol 的主要 parameter-space 结构：common-condition 差异
   随 skip regime 单调增强；DeltaR_time / time_saving / DeltaR_tau
   全域正。
2. limiter 切换：time/range/exposure 均显著切换；**exposure limiter
   全域 Sanger 主导（713/1089）**；limiter 高度 regime 依赖（N0 全
   Sanger、N3-N5 全 Qian）。
3. Protocol-D ambiguity：canonical domain 上 **0 个 AMBIGUOUS**
   （无 VAC plateau 重合采样点）；21 个 float-edge 数值边界点。
4. comparison metric sign 随 regime 不变（全域正），但幅度随 regime
   单调变化。
5. recovered centers（5）与 strict reference 完全一致（1 个 D
   float-edge note，UNIQUE 结构确认）。
6. 需进入 Phase F final interpretation 的 comparison-semantic
   transitions：314 个 signature-transition cells（limiter/status
   变化为主）—— 与 5 条 grazing bands 分列。
7. F7 数值/回归 freeze 应固定：B/C/D 的字段级 tolerance
   （time/exposure 1e-3 s、range 1 m、velocity 1e-2 m/s、energy
   0.1 J/kg）、comparison signature 6-tuple、limiter 三分类、
   Protocol-D UNIQUE/AMBIGUOUS/float-edge 语义、19 个 signature 的
   categorical map。

## 18. F6 acceptance

    [x] Phase-E B/C/D implementation reused unchanged（零修改）
    [x] Phase-F Sanger research adapter implemented（baseline 逐位一致）
    [x] baseline B/C/D reproduces Phase E（diff = 0.0，limiters QIAN/QIAN/QIAN）
    [x] 1089 canonical centers processed（1089/1089 VALID）
    [x] value eligibility independently defined（F3 box 不删 pointwise value）
    [x] recovered physical centers retained and reference audited（5/5）
    [x] unresolved grazing not assigned fake metrics（0 个此类点）
    [x] time/range/exposure limiter dynamic（QIAN/SANGER 均出现）
    [x] Protocol-D UNIQUE/AMBIGUOUS handled（UNIQUE 1068 / AMBIGUOUS 0 / float-edge 21）
    [x] no arbitrary plateau time selected（AMBIGUOUS 时字段全 None）
    [x] range monotonicity audited（Qian/Sanger 全过）
    [x] common-range residuals pass（< 1e-6 m）
    [x] comparison signature generated（19 unique）
    [x] signature transitions generated（314 cells，by reason）
    [x] checkpoint modes recorded（ATM/VAC 分布）
    [x] pointwise metrics not erased by F3 boxes（VALID 1089）
    [x] interpolation/display continuity blocked across F3/signature boundaries
    [x] reference sample covers every Sanger regime / limiter / D status（33 点）
    [x] all recovered canonical centers audited（5/5）
    [x] numerical errors within Phase-E tolerance scale（0 failures）
    [x] five core figures generated（programmatic + visual）
    [x] no native winner surface / no comparison derivative / no optimization
    [x] no STM/saltation/FTLE
    [x] Phase E unchanged / F1-F5 unchanged / all tests PASS

**F6 = COMPLETE；Ready for F7 = YES**

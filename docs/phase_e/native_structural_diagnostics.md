# E4 — Native Endpoint, Structural and Aerodynamic Diagnostics

## 1. Purpose

Phase E 最后一轮新增 scientific diagnostics：完成 **Protocol A（Native
Endpoint Comparison，E0 §5）**、结构轨迹诊断、气动诊断（dynamic
pressure q、drag deceleration D/m），并将气动诊断放在 native /
common-time / common-range 三种明确语义窗口下。不进入 E5（figures）、
E6（numerical audit）、E7（freeze）。

## 2. Protocol A semantics

两个 research endpoint 的 feasibility semantics 不同（E0 §4）：

- **Qian RTI** = QEG feasibility loss（`u_L* ≤ 1`）
- **Sanger SRTI** = skip-capability loss（γ: +→− + 状态机 qualification）

因此 Protocol A 只回答"各自模式持续到什么时候/哪里"（
**TRAJECTORY-MODE PERSISTENCE COMPARISON**），不是 fair
common-condition performance ranking（后者属 E2/E3）。描述性差异
（T/R/h/v/E 之差）绝不称为 range gain / performance improvement；
不提供 native-endpoint 百分比。

## 3. Native endpoint comparison

| Metric | Qian @ RTI | Sanger @ SRTI | Difference |
|---|---|---|---|
| research duration [s] | 723.037965 | 1119.545984 | +396.508019 |
| research range [km] | 3490.698336 | 6872.895320 | +3382.196984 |
| terminal altitude [km] | 46.040886 | 86.138741 | +40.097856 |
| terminal velocity [m/s] | 3192.533 | 5482.946 | +2290.413 |
| terminal specific energy [MJ/kg] | −56.954955 | −46.634412 | +10.320543 |
| total energy loss [MJ/kg] | 19.921285 | 9.600743 | — |
| normalized mode | ATM | ATM | — |
| source mode | QEG_GLIDE | SANGER_ATM | — |

**Native Research-Endpoint / Mode-Persistence Comparison**（表格标题语义）：
RTI and SRTI have different feasibility semantics; this table is not a
common-condition performance ranking.

## 4. Structural trajectory diagnostics

| Metric | Qian | Sanger |
|---|---|---|
| research duration [s] | 723.037965 | 1119.545984 |
| ATM duration [s] | 723.037965 | 771.181427 |
| VAC duration [s] | 0.0 | 348.364558 |
| ATM fraction | 1.000000 | 0.688834 |
| VAC fraction | 0.000000 | 0.311166 |
| min altitude [km] | 46.040886（QEG_GLIDE） | 45.510562（SANGER_ATM） |
| max altitude [km] | 100.000000（t=0） | 130.352121（SANGER_VAC apogee） |
| min velocity [m/s] | 3192.533（RTI） | 5482.946（SRTI） |
| normalized segment count | 2 | 5 |

高度/速度极值由 **solver dense solution 连续精化**获得（每段 256 点
scan + `minimize_scalar` bounded refinement，含端点与 exact event
states），不使用 plotting grid。Sanger max altitude = 130352.121 m
与冻结参考 `sanger_baseline_v1.json` 的 `maximum_altitude_m` 一致
（< 1e-3 m）。

## 5. Qian-specific structure

| 量 | 值 |
|---|---|
| capture time | 93.428785 s |
| capture altitude / velocity | 46.040886 km / 6810.796 m/s |
| QEG_GLIDE duration | 629.609180 s |
| RTI time | 723.037965 s |

（metadata 形式保留；不与 Sanger 事件强行一一对应）

## 6. Sanger-specific structure

| 量 | 值 |
|---|---|
| skip_count（= completed atmosphere entries） | 2 |
| VAC arc count | 2 |
| VAC arc durations | 281.676218 s / 66.688339 s |
| VAC arc ranges | 1780.485 km / 391.248 km |
| VAC apogee altitudes | 130352.121 m / 102232.576 m（与冻结参考 cycles 一致） |
| ATM / VAC segment counts | 3 / 2 |

## 7. Aerodynamic diagnostic definitions

```
q  = 0.5 * rho * v^2        [Pa internal, kPa reporting]
a_D = D / m                 [m/s^2]  (drag deceleration magnitude)
```

- rho 来自 frozen `atmospheric_density(h, env)`；D、q 来自 frozen
  `aerodynamic_forces(...)`（q·S·CD 等）；未复制任何 atmosphere /
  drag 模型（E4 §14）。
- **Sanger VAC 语义（硬性规则，E4 §15）**：normalized mode = VAC 时
  `rho_eff = q = D = a_D = 0`（frozen hybrid `L = D = 0`）。这是 frozen
  hybrid-mode semantic quantity，不是对外层稀薄大气的高保真建模；
  不因 h > 100 km 的指数外推微小 rho 重新启用气动力。
- a_D 是 drag deceleration magnitude，不是 total acceleration /
  load factor / g-load。

## 8. Native-window maxima

| Quantity | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| max dynamic pressure [kPa] | 61.386611 | 61.386611 | 0.000000 |
| max drag deceleration [m/s²] | 12.277322 | 12.277322 | −0.000000 |

峰值位置：t = 92.646 s，h = 46.051 km，mode = ENTRY_CAPTURE /
SANGER_ATM。两条轨迹在入场段（~93 s 前）受相同冻结动力学/大气/气动
控制，因此 q 与 a_D 峰值逐位一致——这是结构事实，如实报告
（Δ = 0），不作任何性能宣称。semantics：native trajectory structural
diagnostic（时间/射程窗口不同，不能据此宣称公平 aerodynamic
advantage）。

## 9. Common-time-window maxima

窗口 `[0, t_common]`（t_common = 723.037965 s，复用 E2 Protocol B）：

| Quantity | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| max dynamic pressure [kPa] | 61.386611 | 61.386611 | 0.000000 |
| max drag deceleration [m/s²] | 12.277322 | 12.277322 | −0.000000 |

## 10. Common-range-window maxima

窗口分别截止到首次到达 R_common = 3490.698336 km（Qian t_Q =
723.037965 s；Sanger t_S = 540.720236 s，复用 E2 Protocol C；两侧
elapsed time 不同）：

| Quantity | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| max dynamic pressure [kPa] | 61.386611 | 61.386611 | 0.000000 |
| max drag deceleration [m/s²] | 12.277322 | 12.277322 | −0.000000 |

**瞬时 checkpoint 诊断**（与窗口最大值严格区分）：common-time 处
q_Q = 13.469 kPa、q_S = 0.065 kPa（Sanger 位于 ~95 km 高空稀薄 ATM1）；
common-range 处 q_Q = 13.469 kPa、q_S = 1.951 kPa。

峰值算法：每 ATM 段 128 点 scan 定位候选 + bounded
`minimize_scalar(-quantity)` 精化（xatol=1e-9 s），并检查段端点与
exact event states；最终峰值经过独立 512 点密集扫描审计（相对
1e-6 内一致，E4 §35）。VAC 恒零，无需优化。

## 11. Link to E2/E3

- E2 common-time：Sanger 更远/更快/更高机械能（差异已由 E2 报告）。
- E3 结构身份：common-range exposure difference
  `DeltaTau_range = 463.993948 s` = `time_saving (182.317730 s)` +
  `Sanger VAC duration before R_common (281.676218 s)`——"共同射程处
  大气暴露减少"同时包含更短的到达时间与 VAC coast 区间（数值由
  E3 artifacts/API 动态读取，此处仅为引用）。
- 本轮的 q/a_D 诊断补充气动环境视角：峰值窗口内两者气动峰值一致
  （入场段同方程），而瞬时 checkpoint 处 Sanger 暴露于更低动压环境。

## 12. Interpretation boundaries

Under the frozen baseline configuration：

- 允许：`the Sanger mode remains viable for a longer elapsed duration
  under its SRTI semantics`（1119.5 s vs 723.0 s）；`the Sanger
  trajectory contains 31.1% VAC coast`；`within the common-time window,
  the peak dynamic pressure is identical`；`at the common-range
  checkpoint the instantaneous dynamic pressure is lower`。
- 禁止：native SRTI range 证明 X% better range；lower q 证明 lower
  thermal load（**q ≠ heat flux，NO THERMAL MODEL**）；lower D/m 证明
  lower total g-load；robust superiority；statistically significant；
  optimal。
- 无任意阈值指标（time-above-10kPa 等）、无 composite aero score、
  无 overall winner score（E0 §16）。

## 13. Limitations

- 全部为 **E4 CANDIDATE** 数值：E6 将执行 regression / numerical
  audit；不创建 Phase E tag；不写入 frozen regression JSON。
- 峰值优化为 optimizer sanity check（含 512 点独立审计），非完整
  E6 convergence study。
- 未包含 thermal model、load factor、E5 figures、parameter sweep、
  STM / saltation / FTLE、optimization。

## 14. E4 acceptance

- [x] Protocol A implemented（exact terminal states，semantics =
  trajectory_mode_persistence）
- [x] RTI/SRTI asymmetry documented
- [x] no native endpoint performance-gain claim（无 gain 字段/百分比）
- [x] structural diagnostics implemented（dense-solution 精化极值）
- [x] continuous altitude extrema（scan + minimize_scalar，非 grid）
- [x] mode durations/fractions consistent（ATM+VAC = research；fractions 和 = 1）
- [x] Qian-specific structure retained（capture/QEG/RTI metadata）
- [x] Sanger-specific structure retained（skip_count=2、VAC arcs、apogees 与冻结参考一致）
- [x] q definition correct（0.5·rho·v²，frozen helpers）
- [x] D/m definition correct（frozen aerodynamic_forces）
- [x] frozen atmosphere/aero reused（未复制模型）
- [x] Sanger VAC aero = 0（rho_eff = q = D = a_D = 0）
- [x] native / common-time / common-range maxima computed
- [x] E2 windows reused exactly（t_common、t_Q/t_S(R_common)）
- [x] formal maxima refined continuously（minimize_scalar + audit）
- [x] optimizer sanity check PASS（512 点独立审计一致）
- [x] instantaneous checkpoint diagnostics separated（非最大值）
- [x] no thermal inference / no total-g-load inference / no arbitrary
  thresholds / no composite score
- [x] E1 unchanged / E2 unchanged / E3 unchanged / historical
  regressions unchanged
- [x] all tests PASS

**Artifacts**（`results/qian_sanger_comparison/diagnostics/`，不跟踪）：
`native_endpoint.json`、`structural_diagnostics.json`、
`aerodynamic_diagnostics.json`（native / common_time / common_range /
instantaneous_checkpoints 分区，含 max 的时间/位置/mode 与优化信息）、
`diagnostics_summary.json`（schema_version、git_commit、
comparison_protocol=E0）。

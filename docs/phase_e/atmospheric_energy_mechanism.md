# E3 — Atmospheric Exposure and Energy Mechanism

## 1. Purpose

回答 E2 差异的结构来源：在当前 frozen baseline 下，Sanger 在同时间更远/
更快/更高机械能的差异，与 atmospheric-mode exposure、VAC coast、
mechanical-energy dissipation 之间是什么结构关系。

本轮正式完成：**Protocol D（Common Atmospheric Exposure，E0 §11）**、
**segment-level mechanical-energy accounting**、**VAC-coast 结构诊断**，
并为 E2 结果附加 mechanism diagnostics。不进入 E4（native-endpoint /
aerodynamic q、D/m）、E5（figures）、E6（numerical audit）。

## 2. Protocol D definition

严格按 E0 §11：

```
tau_ATM(t) = sum of lengths(ATM_interval ∩ [t0, t])     (exact interval arithmetic)

tau_common = min(tau_ATM,Q(T_Q), tau_ATM,S(T_S))
```

通过 E1 `time_at_atmospheric_exposure` 求逆。**正式 checkpoint 要求两边
inverse 均为 UNIQUE**；任一 PLATEAU 时返回显式 `AMBIGUOUS` 结果并附
plateau interval（禁止 earliest/latest/midpoint 自动选择，E0 §23-§24）。

一致性验证（E0 §6）：`tau_Q(t_Q) ≈ tau_common` 且 `tau_S(t_S) ≈
tau_common`（不盲信 inverse）。

## 3. Common atmospheric-exposure checkpoint

| Metric | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| atmospheric exposure [s] | 723.037965 | 723.037965 | 0 |
| elapsed time [s] | 723.037965 | 1071.402523 | **+348.364558**（elapsed-time extension） |
| range [km] | 3490.698336 | 6612.247975 | **+3121.549639** |
| altitude [km] | 46.040886 | 80.617174 | +34.576288 |
| velocity [m/s] | 3192.533 | 5494.955 | +2302.422 |
| specific energy [MJ/kg] | −56.954955 | −46.621272 | **+10.333684** |
| energy loss [MJ/kg] | 19.921285 | 9.587602 | — |
| normalized mode | ATM | ATM | — |
| source mode | QEG_GLIDE | SANGER_ATM | — |

inverse statuses：Qian UNIQUE、Sanger UNIQUE。`tau_common` 恰等于
Qian 总暴露（Qian 全程 ATM），Sanger 侧位于 ATM2 内。

**结构恒等式（E3 §19）**：
`t_S(tau_common) − tau_common = 348.364557502 s`
`= VAC duration accumulated before the Sanger checkpoint`（逐位一致）。
Qian：`t_Q − tau_common ≈ 0`。

## 4. Same-time atmospheric-exposure diagnostic

读取 E2 common-time checkpoint（t_common = 723.037965 s）：

| 量 | 值 |
|---|---|
| tau_Q(t_common) | 723.037965 s |
| tau_S(t_common) | 441.361747 s |
| **DeltaTau_time = tau_Q − tau_S** | **+281.676218 s**（Sanger 同 elapsed time 下大气暴露更少） |
| Loss_Q / Loss_S（E2 checkpoint） | 19.921285 / 6.718990 MJ/kg |

机制身份：`(t_common − t0) − tau_S(t_common) = 281.676218 s = VAC0
duration`（Sanger 在 t_common 前已完成首个 VAC coast）；Qian 侧
`(t_common − t0) − tau_Q(t_common) ≈ 0`。这解释了为什么同样 723 s
elapsed time，两条轨迹经历的 ATM-mode time 不同。

## 5. Same-range atmospheric-exposure diagnostic

读取 E2 common-range checkpoint（R_common = 3490.698336 km；
t_Q = 723.037965 s，t_S = 540.720236 s）：

| 量 | 值 |
|---|---|
| tau_Q(t_Q) | 723.037965 s |
| tau_S(t_S) | 259.044017 s |
| **DeltaTau_range = tau_Q − tau_S** | **+463.993948 s**（Sanger 到达同一 downrange 时大气暴露更少） |
| Loss_Q / Loss_S | 19.921285 / 3.572032 MJ/kg |

注：common-range 两侧 elapsed time 不同（723.0 s vs 540.7 s），
DeltaTau 不是同一时刻的暴露差。

## 6. Segment-level mechanical-energy accounting

每条 ComparisonTrajectory 的每个 dense segment 使用 **exact endpoints**
（state_start / state_end），计算 E_start、E_end、raw_energy_loss =
E_start − E_end、delta_range、duration。不使用 plotting samples。

| Trajectory / Mode | Duration [s] | Range accumulated [km] | Raw mechanical-energy loss [MJ/kg] |
|---|---|---|---|
| Qian ATM | 723.037965 | 3490.698336 | 19.921285 |
| Qian TOTAL | 723.037965 | 3490.698336 | 19.921285 |
| Sanger ATM | 771.181427 | 4701.161419 | 9.600743 |
| Sanger VAC | 348.364558 | 2171.733901 | −1.5e-08（raw，保留符号） |
| Sanger TOTAL | 1119.545984 | 6872.895320 | 9.600743 |

telescoping 验证：`sum(segment raw loss) − (E0 − E_T) = 0.0`（float
level）。Qian 的 VAC 聚合由 segment aggregation 自动产生（0），非硬编码。

Sanger 逐段明细：

| seg | mode | duration [s] | dR [km] | raw loss [J/kg] | relative ΔE |
|---|---|---|---|---|---|
| 0 | SANGER_ATM | 202.964136 | 1352.050536 | +3.5386e+06 | 9.555e-02 |
| 1 | SANGER_VAC | 281.676218 | 1780.485406 | −7.0e-09 | −1.836e-16 |
| 2 | SANGER_ATM | 263.473444 | 1616.144187 | +3.1819e+06 | 7.842e-02 |
| 3 | SANGER_VAC | 66.688339 | 391.248495 | −7.0e-09 | −1.703e-16 |
| 4 | SANGER_ATM | 304.743847 | 1732.966696 | +2.8803e+06 | 6.583e-02 |

## 7. Sanger VAC coast

- **total VAC duration = 348.364558 s**（VAC interval 直接求交集累计，
  不依赖 elapsed − exposure 作为唯一实现；两者交叉验证一致）。
- **total VAC range = 2171.733901 km**：结构 accounting 量——"downrange
  accumulated while aerodynamic force is disabled under the frozen VAC
  semantics"。
- 明确边界：这不是 "VAC 对总优势的因果贡献"（VAC 还改变后续 ATM 的进入
  状态）；`DeltaR_atm_exposure ≠ sum(VAC range)`（3121.5 km vs 2171.7 km，
  两者作为不同量并列报告，不作因果归因，E3 §18/§22）。

## 8. Energy conservation in VAC

- max absolute VAC energy drift = **7.451e-09 J/kg**
- max relative VAC energy drift = **1.836e-16**
- 全部 VAC 段 `delta_range > 0`。
- raw drift 保留真实符号（微负值，E0 §12：不 clipping）；处于 D6
  numerical behavior 合理尺度内，E3 PASS。

## 9. Link to E2 common-condition results

| Checkpoint | Qian tau_ATM [s] | Sanger tau_ATM [s] | Delta tau [s] | Qian energy loss [MJ/kg] | Sanger energy loss [MJ/kg] |
|---|---|---|---|---|---|
| Common time | 723.037965 | 441.361747 | +281.676218 | 19.921285 | 6.718990 |
| Common range | 723.037965 | 259.044017 | +463.993948 | 19.921285 | 3.572032 |

（Common range 两侧 elapsed time 不同，Delta tau 非同时刻差。）

## 10. Interpretation boundaries

Under the frozen baseline configuration：

1. 在 E2 common-time checkpoint，Sanger 累计的 atmospheric-mode exposure
   更少（−281.7 s），机械能损失更少（−13.2 MJ/kg）。
2. 在 E2 common-range checkpoint，Sanger 以更少 atmospheric-mode
   exposure（−464.0 s）到达同一 downrange，且保留更高机械能（+16.3
   MJ/kg）。
3. Sanger VAC 段内 downrange 持续增长，而比机械能守恒至数值精度
   （max drift 7.5e-09 J/kg）。
4. 在相同累计 atmospheric-mode exposure 下，Sanger 轨迹通过 VAC coast
   获得额外 elapsed time（+348.4 s）与 downrange（+3121.5 km）。

禁止措辞：universal / optimal / statistically significant /
"caused exactly by X km" / thermal advantage。tau_ATM 仅是
atmospheric-mode exposure time，不是 heat load / heat flux / TPS load
（E3 §10）。无 composite efficiency score（E0 §16）。

## 11. Limitations

- 结果均为 **E3 CANDIDATE**：E6 仍将执行 regression / numerical audit，
  本轮数值不写入 frozen regression JSON，不创建 Phase E tag。
- Protocol D 的 `tau_common` 当前由 Qian 总暴露定义（min endpoint =
  Qian）；若未来 endpoint ordering 改变，min 定义逻辑同样适用。
- 未包含：E4 native-endpoint structural report、aerodynamic q / D/m
  正式分析（E0 §13 留待 E4）、E5 figures。
- 曲线 CSV（`qian_energy_curve.csv` / `sanger_energy_curve.csv`）为
  visualization-only 采样（每段 50 点，边界去重、exact state 优先、
  right-continuous mode），仅供 E5 R-vs-energy-loss 绘图，不驱动任何
  正式 checkpoint。

## 12. E3 acceptance

- [x] Protocol D implemented（tau_common = min terminal exposure）
- [x] exposure inverse ambiguity respected（AMBIGUOUS + plateau interval）
- [x] formal checkpoint requires UNIQUE（两侧均 UNIQUE）
- [x] exact continuous states used（tau 复现一致性 PASS）
- [x] same-time exposure diagnostic（DeltaTau_time = +281.676218 s）
- [x] same-range exposure diagnostic（DeltaTau_range = +463.993948 s）
- [x] segment energy accounting（exact endpoints，无 plotting samples）
- [x] endpoint energy telescoping PASS（residual = 0.0）
- [x] Qian ATM-only aggregate（VAC 聚合自动为 0）
- [x] Sanger ATM/VAC aggregate
- [x] Sanger VAC range positive（全部 VAC 段 dR > 0）
- [x] Sanger VAC energy conserved numerically（max drift 7.5e-09 J/kg）
- [x] raw VAC drift not clipped（保留真实符号）
- [x] VAC duration accounting（interval 算术 + elapsed−exposure 交叉验证）
- [x] elapsed/exposure/VAC identity PASS（t_S − tau_common ≡ VAC duration）
- [x] Protocol D DeltaR convention correct（R_S − R_Q = +3121.549639 km）
- [x] no causal overclaim（DeltaR_atm_exposure 与 sum(VAC range) 并列报告）
- [x] no thermal claim（tau_ATM 定义为 atmospheric-mode exposure time）
- [x] no q/Dm analysis（留 E4）
- [x] plotting samples separated from formal checkpoints
- [x] E1 unchanged / E2 unchanged / historical regressions unchanged
- [x] all tests PASS

**Artifacts**（`results/qian_sanger_comparison/mechanism/`，不跟踪）：
`common_atmospheric_exposure.json`、`energy_budget.json`、
`mechanism_summary.json`（schema_version、git_commit、Protocol D、
E2 diagnostics、energy budgets、VAC diagnostics）、
`qian_energy_curve.csv`、`sanger_energy_curve.csv`（visualization-only）。

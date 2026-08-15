# Phase E — Qian vs Sanger Baseline Comparison Results

## 1. Scope and frozen configuration

本文件汇总 Phase E（E2–E5）的最终 deterministic baseline comparison
结果。全部数值在 frozen baseline configuration 下产生：

- 比较对象：`qian-baseline-v1.0`（Qian frozen physics/control，research
  domain `[0, RTI]`）与 `sanger-baseline-v1.0`（Sanger frozen
  physics/control，research domain `[0, SRTI]`）；
- 共同配置：h0 = 100 km、v0 = 7000 m/s、γ0 = −5°、θ0 = 0、K = 3；
  相同 EnvironmentParams / VehicleParams / state / range convention；
- 数值统一：`PRODUCTION_SOLVER_CONFIG`（DOP853 / rtol=1e-9 /
  state-scaled atol / max_step=20 s / dense_output=True，E0 §3）；
- 连续求值：真实 solver dense output（E0.1 hook）+ segment-aware
  root inversion（E1）；无 sampled-grid checkpoint。

结果语义：deterministic comparisons，非 uncertainty/statistical 结果，
非 native-endpoint ranking（E0 §4、§20）。

## 2. Comparison protocol overview

| Protocol | 定义 | 阶段 |
|---|---|---|
| A Native endpoint | Qian@RTI 与 Sanger@SRTI 各自模式持久性 | E4 |
| B Common time | t_common = min(T_Q, T_S) 同时间比较 | E2 |
| C Common range | R_common = min(R_Q, R_S) 同射程比较 | E2 |
| D Common atmospheric exposure | tau_common = min 累计 ATM 暴露 | E3 |
| Energy mechanism | R vs ΔE + segment accounting | E3 |
| Aerodynamic | q、D/m 三窗口诊断 | E4 |

## 3. Common-time result

**Table 1A. Common-condition deterministic comparison — Common time**
（t_common = 723.037965 s = min(T_Q_RTI, T_S_SRTI)，Qian RTI 为限制端点）

| Metric | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| time [s] | 723.037965 | 723.037965 | 0 |
| range [km] | 3490.698336 | 4601.398708 | **+1110.700372** |
| altitude [km] | 46.040886 | 95.386912 | +49.346026 |
| velocity [m/s] | 3192.533 | 5970.747 | **+2778.213** |
| specific energy [MJ/kg] | −56.954955 | −43.752660 | **+13.202295** |
| energy loss [MJ/kg] | 19.921285 | 6.718990 | −13.202295 |
| normalized mode | ATM | ATM | — |
| source mode | QEG_GLIDE | SANGER_ATM | — |

## 4. Common-range result

**Table 1B. Common-condition deterministic comparison — Common range**
（R_common = 3490.698336 km = min(R_Q_RTI, R_S_SRTI)）

| Metric | Qian | Sanger | Difference |
|---|---|---|---|
| range [km] | 3490.698336 | 3490.698336 | 0 |
| arrival time [s] | 723.037965 | 540.720236 | −182.317730 |
| altitude [km] | 46.040886 | 71.223555 | +25.182669 |
| velocity [m/s] | 3192.533 | 6511.963 | **+3319.430** |
| specific energy [MJ/kg] | −56.954955 | −40.605702 | **+16.349254** |
| energy loss [MJ/kg] | 19.921285 | 3.572032 | −16.349254 |
| normalized mode | ATM | ATM | — |
| source mode | QEG_GLIDE | SANGER_ATM | — |

**Arrival-time saving (Qian − Sanger) = +182.317730 s**（positive:
Sanger 更早到达共同射程；root residuals = 0 m，E1 §18 策略内）。

## 5. Atmospheric-exposure mechanism

**Table 2. Exposure / energy mechanism**

| 量 | 值 |
|---|---|
| **Protocol D** tau_common [s] | 723.037965（= Qian 总暴露） |
| Qian elapsed time [s] | 723.037965 |
| Sanger elapsed time [s] | 1071.402523 |
| elapsed-time extension [s] | **+348.364558** |
| DeltaR_atm_exposure [km] | **+3121.549639** |
| DeltaV_tau [m/s] | +2302.422 |
| DeltaE_tau [MJ/kg] | +10.333684 |
| E2 common-time: tau_Q / tau_S / DeltaTau [s] | 723.037965 / 441.361747 / **+281.676218** |
| E2 common-range: tau_Q / tau_S / DeltaTau [s] | 723.037965 / 259.044017 / **+463.993948** |
| Sanger VAC duration [s] | 348.364558 |
| Sanger VAC accumulated range [km] | 2171.733901 |
| Sanger VAC energy drift [J/kg] | max abs 7.451e-09（数值守恒） |

明确：VAC accumulated range（2171.7 km）**≠** causal range advantage；
`DeltaR_atm_exposure` 与 `sum(VAC range)` 是两个不同量，并列报告
（E3 §18/§22）。tau_ATM 是 atmospheric-mode exposure time，不是
heat load / TPS load（E3 §10）。

结构恒等式：`t_S(tau_common) − tau_common ≡ VAC duration before
checkpoint = 348.364557502 s`（逐位一致）。

## 6. Mechanical-energy mechanism

- 统一 E0（|E0_Q − E0_S| < 1e-3 J/kg），`energy_loss = E0 − E`（无
  abs、无 clipping）。
- Segment accounting（exact endpoints）：Qian ATM 段 loss 19.921285
  MJ/kg（TOTAL 同）；Sanger ATM 9.600743 / VAC −1.5e-08 J/kg（raw，
  保留符号）/ TOTAL 9.600743 MJ/kg；telescoping residual = 0.0。
- Sanger VAC 段：downrange 持续增加（1780.5 km / 391.2 km）而比机械
  能守恒至数值精度（max relative drift 1.836e-16）。

## 7. Native endpoint / structural context

**Table 3A. Native research endpoint / mode persistence**
（RTI and SRTI have different feasibility semantics; this table is not
a common-condition performance ranking.）

| Metric | Qian @ RTI | Sanger @ SRTI |
|---|---|---|
| research duration [s] | 723.037965 | 1119.545984 |
| research range [km] | 3490.698336 | 6872.895320 |
| terminal altitude [km] | 46.040886 | 86.138741 |
| terminal velocity [m/s] | 3192.533 | 5482.946 |
| terminal specific energy [MJ/kg] | −56.954955 | −46.634412 |
| total energy loss [MJ/kg] | 19.921285 | 9.600743 |
| semantics | QEG feasibility loss (RTI) | skip-capability loss (SRTI) |

**Table 3B. Structural diagnostics**

| Metric | Qian | Sanger |
|---|---|---|
| ATM fraction | 1.000000 | 0.688834 |
| VAC fraction | 0.000000 | 0.311166 |
| min altitude [km] | 46.040886 | 45.510562 |
| max altitude [km] | 100.000000 | 130.352121 |
| min velocity [m/s] | 3192.533 | 5482.946 |
| normalized segments | 2 | 5（3 ATM + 2 VAC，skip_count=2） |

## 8. Aerodynamic context

**Table 3C. Aerodynamic maxima**（q = 0.5·rho·v²；a_D = D/m；
VAC: rho_eff = q = D = a_D = 0）

| Window | Qian q_max [kPa] | Sanger q_max [kPa] | Δ | Qian aD_max [m/s²] | Sanger aD_max [m/s²] | Δ |
|---|---|---|---|---|---|---|
| Native | 61.386611 | 61.386611 | 0.000000 | 12.277322 | 12.277322 | −0.000000 |
| Common-time [0, 723.04 s] | 61.386611 | 61.386611 | 0.000000 | 12.277322 | 12.277322 | −0.000000 |
| Common-range | 61.386611 | 61.386611 | 0.000000 | 12.277322 | 12.277322 | −0.000000 |

峰值均位于 t = 92.646 s、h = 46.051 km 的公共初始入场段（两条轨迹
入场段受相同冻结方程控制）。瞬时 checkpoint（非最大值）：common-time
q_Q = 13.469 kPa / q_S = 0.065 kPa；common-range q_Q = 13.469 kPa /
q_S = 1.951 kPa。a_D(t) ≡ q(t)·(S·CD/m) 为固定比例（2.0e-4），故不设
冗余 a_D 曲线图（E5 §25）。

## 9. Core figures

**Figure E1 — Trajectory geometry**（`E5_F1_trajectory_geometry.png`）
上下两 panel：高度-射程（km/km）与高度-时间（km/s）。蓝色实线为
Qian 连续大气滑翔（100 km 起点 → 46 km RTI）；橙色实线/虚线为
Sanger ATM/VAC 交替跳跃轨迹，可见两次 VAC 外抛（apogee 130 km /
102 km）。星形标记 Qian RTI 与 Sanger SRTI；空心圆/方为 common-time
与 common-range checkpoint；点线为 100 km 大气界面。

**Figure E2 — State and energy retention**
（`E5_F2_state_energy_retention.png`）上 panel 速度-时间（km/s），下
panel 比机械能损失-时间（MJ/kg）。t_common 垂直虚线处空心圆标记显示
同时间下 Sanger 速度与机械能保留更高；浅橙 shading 标记 VAC 段，其
中能量损失呈近似水平平台（数值精度内守恒）。

**Figure E3 — Range–energy mechanism**
（`E5_F3_range_energy_mechanism.png`）x=射程（km）、y=比机械能损失
（MJ/kg）。Sanger VAC 段（橙色虚线）表现为"射程增加而能量损失近似
不变"的近水平平台（VAC 1、VAC 2 标注）；三类 checkpoint（圆/方/三角）
与 RTI/SRTI 星形端点均取 exact JSON 状态。说明：VAC 段内 downrange
持续积累而机械能损失近似不变；`sum(VAC range)` 不是总射程优势的
因果分解（数值留表格）。

**Figure E4 — Atmospheric exposure**
（`E5_F4_atmospheric_exposure.png`）x=elapsed time（s）、y=累计
atmospheric-mode exposure（s）。Qian 为 tau=t 对角线；Sanger 为
对角-平台-对角-平台-对角阶梯（两个 VAC plateau 清晰可见）。
tau_common 水平虚线：Qian 在 723.0 s 到达、Sanger 在 1071.4 s 到达
——相同累计大气暴露下 Sanger 经 VAC coast 获得更长 elapsed time。

**Figure E5 — Dynamic pressure**（`E5_F5_dynamic_pressure.png`）
q(t)（kPa）。初始 ~93 s 内两条曲线完全重叠（共同 q 峰值 61.4 kPa）；
之后历史分化；Sanger VAC 段严格 q = 0；common-time 标记显示瞬时
q_Q = 13.5 kPa vs q_S = 0.07 kPa。q 峰值相同不表示整个气动历史相同。

## 10. Integrated deterministic interpretation

Under the frozen baseline configuration:

1. 同一 elapsed time（723.0 s）下，Sanger 飞行更远（+1110.7 km）且
   保留更高速度（+2778.2 m/s）与更高比机械能（+13.20 MJ/kg）。
2. 同一 downrange（3490.7 km）下，Sanger 更早到达（−182.3 s）且保留
   更高机械能（+16.35 MJ/kg）。
3. Sanger 轨迹含 VAC coast 区间：downrange 持续积累而比机械能守恒至
   数值精度（max drift 7.5e-09 J/kg）。
4. 因此同一 elapsed-time / common-range checkpoint 对应 Sanger 更少的
   累计 atmospheric-mode exposure（−281.7 s / −464.0 s）。
5. 共同暴露协议显示：相同累计大气暴露下，Sanger 经 VAC coast 获得
   额外 elapsed time（+348.4 s）与 downrange（+3121.5 km）。
6. 峰值动压/减速度在当前 baseline 下完全相同——全局峰值发生在共同
   初始入场段；此后气动历史仍分化（Sanger VAC q=0、checkpoint 瞬时
   q 更低）。

## 11. Claim boundaries

禁止措辞：Sanger universally outperforms Qian；"Sanger range improves
X%"；statistically significant；robust superiority；optimal
trajectory；thermal advantage；lower TPS requirement；lower total
g-load；VAC causes exactly X km advantage。当前只能说：under the
frozen deterministic baseline configuration。无 thermal model、无
composite score、无任意阈值指标（E0 §14、§16、§20）。

## 12. E5 acceptance

- [x] no new scientific metric introduced（仅组织 E2-E4 已验证结果）
- [x] E2 / E3 / E4 values unchanged（runners 复跑数值一致）
- [x] Figure E1–E5 generated（300 dpi PNG，程序化审计 + zai 视觉检查 5/5 PASS）
- [x] exact checkpoint markers used（JSON exact states；无 nearest-row）
- [x] visualization samples not used for formal checkpoints
- [x] units consistent（km / s / km/s / MJ/kg / kPa，逐图审计 PASS）
- [x] native endpoint asymmetry preserved（RTI/SRTI semantics 标注）
- [x] VAC semantics visually correct（虚线 + shading + q=0）
- [x] q peak interpretation correct（峰值相同 + 历史分化均可见）
- [x] no thermal claim / no causal overclaim / no composite score
- [x] three scientific result tables created（Table 1A/1B、2、3A/3B/3C）
- [x] captions created（Figure E1-E5，论文可用）
- [x] programmatic PNG audit PASS / zai visual inspection PASS
- [x] all regressions unchanged / all tests PASS

**Artifacts**：`results/qian_sanger_comparison/figures/`
（E5_F1–F5 + contact sheet，results/ 不跟踪）；本文档数据源为
E2/E3/E4 各 summary JSON。

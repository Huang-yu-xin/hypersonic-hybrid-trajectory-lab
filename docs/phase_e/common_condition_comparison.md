# E2 — Common-Time and Common-Range Comparison

## 1. Purpose

第一次生成正式的 Phase E common-condition deterministic comparison
candidate：在**相同飞行时间**与**相同 downrange** 下比较两条 frozen
research trajectories（Qian@RTI、Sanger@SRTI）的 range、altitude、
velocity、specific mechanical energy。

本轮不执行：Protocol D（common atmospheric exposure）、
energy-mechanism R-vs-ΔE curve、native-endpoint performance
interpretation、aerodynamic exposure、最终论文 figures（分属 E3/E4/E5）。

## 2. Frozen comparison protocol

依据 `docs/phase_e/comparison_protocol.md`（E0，commit 02fed87）：

- **Protocol B — Common-Time**（E0 §7）：`t_common = min(T_Q_RTI, T_S_SRTI)`，
  在同一时间连续评价两条轨迹；
- **Protocol C — Common-Range**（E0 §8）：`R_common = min(R_Q_RTI, R_S_SRTI)`，
  用 segment-aware root solving 求两条轨迹首次到达该射程的连续状态；
- 符号约定（E0 §18）：`DeltaR_time = R_S - R_Q`（positive: Sanger 同时间
  更远）、`DeltaV_time = v_S - v_Q`（positive: Sanger 保留更大速度）、
  `time_saving = t_Q - t_S`（positive: Sanger 更早到达共同射程）、
  `DeltaE_time/DeltaE_range = E_S - E_Q`（positive: Sanger 保持更高比机械能）。

## 3. Numerical realization

两边统一使用 `PRODUCTION_SOLVER_CONFIG`（DOP853 / rtol=1e-9 /
state-scaled atol / max_step=20 s / dense_output=True，E0 §3），连续评价
经由 E0.1 dense-output hook（`DenseOutputCollector`）暴露的真实 solver
dense interpolant 完成，checkpoint **不使用** sampled grid / nearest row /
400-point reconstruction。

Range 约定：`R = R_E * theta`（frozen convention）。比机械能：
`E = v²/2 − mu/r`，`mu` 由 frozen environment 导出（E0 §6）。

## 4. Common-time checkpoint

```
t_common = min(T_Q_RTI, T_S_SRTI) = 723.037965 s   (Qian RTI 为限制端点)
```

端点恒等性（条件式结构断言，E0 §7）：`t_common == Qian terminal time`，
故 Qian checkpoint state 与 exact RTI terminal state 一致（production
precision）；Sanger 状态为该时刻的连续 ATM1 段状态。

## 5. Common-time results

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

## 6. Common-range checkpoint

```
R_common = min(R_Q_RTI, R_S_SRTI) = 3490.698336 km   (Qian RTI 为限制端点)
```

前置：两条 research trajectories 的 downrange 单调性均 PASS
（Qian min dR/dt = 3.170e+03 m/s；Sanger min dR/dt = 5.410e+03 m/s，
E0 §9/§11）。求根：`first_time_at_range`（segment-aware brentq，
xtol=1e-10 s / rtol=1e-12，E1 §18）；root residuals 均为 0
（`R_common` 恰为 Qian 终端射程，边界精确返回）。

## 7. Common-range results

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

**Arrival-time saving (Qian − Sanger) = +182.317730 s**
（positive: Sanger 更早到达共同射程；E0 §18 符号约定，与普通
Sanger − Qian difference 不混淆）

## 8. Mechanical-energy comparison

统一初始比机械能（E0 §6/§25）：`E0_Q ≈ E0_S`（|ΔE0| 处于 numerical
zero，< 1e-3 J/kg），`energy_loss = E0 − E`（不使用 abs，不 clipping）。
结果中所有能量 loss 均为正且有限。

共同时刻下：`DeltaE_time = +13.202295 MJ/kg`（Sanger 保留更高比机械能；
对应 loss 少 13.202295 MJ/kg）。共同射程下：`DeltaE_range = +16.349254
MJ/kg`。数值一致性：`Loss_Q − Loss_S == DeltaE`（同 E0 下恒等）。

## 9. Mode context

两个 checkpoint 处 Sanger 均处于 ATM 段（t_common = 723.0 s ∈ ATM1；
R_common 到达时刻 540.7 s ∈ ATM1），Qian 处于 QEG_GLIDE。两者 normalized
mode 均为 ATM；source mode 分别为 SANGER_ATM / QEG_GLIDE。VAC coast 的
结构性贡献不在本轮量化（属 E3 Protocol D）。

## 10. Deterministic interpretation

以下解释均限定于 frozen baseline configuration（E0 §20/§22）：

- 同一时刻 t_common = 723.0 s 下，Sanger 比 Qian 多飞行约 1110.7 km
  downrange（约 +31.8%，相对 Qian 同时间射程 3490.7 km）。
- 同一时刻下 Sanger 保留约 2778.2 m/s 更高速度（约 +87.0%，相对
  Qian 同时间速度 3192.5 m/s）。
- 同一 downrange R_common = 3490.7 km 下，Sanger 比 Qian 早约 182.3 s
  到达（约 −25.2%，相对 Qian 到达时间 723.0 s）。
- 同一 downrange 下 Sanger 到达时比机械能高约 16.35 MJ/kg。

所有百分比均伴随 absolute quantity；接近 0 的差异不计算百分比
（E0 §23）。这些是 deterministic baseline comparisons，不是
uncertainty / statistical results，也不是 native-endpoint ranking
（E0 §4、§20）。

## 11. Limitations

- 结果是 **E2 CANDIDATE**：physics 与 numerical realization 已冻结并对齐，
  但 E6 仍将执行 regression / numerical audit；本轮不创建 Phase E tag，
  数值未写入任何 frozen regression JSON。
- 两个 checkpoint 均由 Qian RTI 定义（min endpoint = Qian）；若未来
  endpoint ordering 改变，protocol 的 min 定义逻辑同样适用（不硬编码）。
- 未包含 Protocol D（大气暴露）、native-endpoint 语义解释（E4）、
  气动暴露（E3）、figures（E5）。
- native endpoint ranges（Qian RTI vs Sanger SRTI）不得解释为直接公平
  性能增益（E0 §4）。

## 12. E2 acceptance

- [x] common-time protocol implemented（min terminal time）
- [x] common-time uses continuous state evaluation（dense output）
- [x] common-time difference conventions correct（E0 §18）
- [x] common-range protocol implemented（min terminal range）
- [x] range monotonicity checked（两条均严格单调）
- [x] common-range uses `first_time_at_range`（无第二套求根逻辑）
- [x] common-range root residual small（0 ≤ 1e-3 m policy）
- [x] time-saving sign convention correct（t_Q − t_S = +182.317730 s）
- [x] common initial energy verified（|E0_Q − E0_S| 数值零）
- [x] energy loss calculated without clipping
- [x] normalized/source mode retained
- [x] full-precision artifacts generated（JSON double precision）
- [x] display units correct（s / km / m/s / MJ/kg，表格内统一）
- [x] no nearest sample / grid checkpoint
- [x] no native-endpoint gain claim
- [x] no Protocol D result
- [x] no final figures（E5 统一设计）
- [x] no frozen numerical constants added to tests
- [x] historical Qian regression unchanged
- [x] Sanger regression unchanged
- [x] E1 alignment unchanged
- [x] all tests PASS

**Artifacts**（`results/qian_sanger_comparison/common_conditions/`，
results/ 不跟踪）：`common_time.json`、`common_range.json`、`summary.json`
（含 schema_version、git_commit、comparison_protocol=E0、alignment、
continuous_evaluation{dense_output=true, sample_grid_used=false}）。

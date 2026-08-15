# Phase E — Qian vs Sanger Baseline Comparison

## 1. Purpose and scope

Phase E 在 frozen baselines 与 production numerics 下完成钱学森连续滑翔
（Qian）与桑格尔混合跳跃（Sanger）两条 research trajectories 的
deterministic baseline comparison：common-time、common-range、
common-atmospheric-exposure 三种共同条件比较，VAC coast 与
mechanical-energy 机制，native endpoint / structural / aerodynamic
diagnostics，5 张核心图，以及 7-case numerical / regression audit。

本报告是 Phase E 的 source-of-truth summary；详细数值与推导见
`docs/phase_e/` 各阶段文档。Phase E 不产生任何 uncertainty /
statistical 结果，不进行 gamma0-K sweep / STM / saltation / FTLE /
Monte Carlo / optimization。

## 2. Frozen comparison objects

| 对象 | 冻结锚点 |
|---|---|
| Qian | `qian-baseline-v1.0`（frozen physics/control） |
| Sanger | `sanger-baseline-v1.0`（frozen physics/control） |

共同 frozen configuration：h0 = 100 km、v0 = 7000 m/s、γ0 = −5°、
θ0 = 0、K = 3；相同 EnvironmentParams / VehicleParams / range
convention（R = R_E·θ）/ state convention（[r, θ, v, γ]）。

Phase E comparison realization 两边统一使用
`PRODUCTION_SOLVER_CONFIG`（DOP853 / rtol=1e-9 /
atol=[1e-4, 1e-11, 1e-7, 1e-11] / max_step=20 s / dense_output=True）。
**Qian Phase-E production realization 不替换 historical
qian-baseline-v1.0 regression**（E0 §3）。

## 3. Comparison protocol

E0 `comparison_protocol.md`（FROZEN）定义：

- **Protocol A** — Native endpoint（Qian@RTI、Sanger@SRTI，mode
  persistence）
- **Protocol B** — Common time（t_common = min 终端时间）
- **Protocol C** — Common range（R_common = min 终端射程，
  segment-aware root inversion）
- **Protocol D** — Common atmospheric exposure（tau_common = min 累计
  ATM 暴露；inverse 必须 UNIQUE）
- Energy mechanism（R vs ΔE + segment accounting）、aerodynamic
  diagnostics（q、D/m 三窗口）

连续求值规则（E0 §10 + E0.1 amendment）：全部 checkpoint 使用真实
solver dense output + segment-aware interpolation + root finding；
禁止 sampled grid / nearest row。

## 4. Numerical realization and alignment

- 连续解可访问性：E0.1 在 frozen integrators 上增加 opt-in
  dense-output observation hook（`DenseOutputCollector`），无第二套
  积分器、无插值近似、无 monkeypatch。
- E1 统一抽象：`ComparisonTrajectory`（state_at_time / range_at_time /
  specific_energy_at_time / is_range_monotone / first_time_at_range /
  atmospheric_exposure_at_time / time_at_atmospheric_exposure），
  Qian/Sanger 上层接口完全一致；right-continuous mode 语义；
  ground continuation 排除。
- Alignment 验证：initial state、environment、vehicle、K、solver
  全部相等（E1 §9）。

## 5. Common-time comparison

t_common = **723.037965 s**（= min(T_Q_RTI, T_S_SRTI)，Qian RTI 为限制
端点；production snapshot 读取）

| Metric | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| range [km] | 3490.698336 | 4601.398708 | **+1110.700372** |
| altitude [km] | 46.040886 | 95.386912 | +49.346026 |
| velocity [m/s] | 3192.533 | 5970.747 | **+2778.213** |
| specific energy [MJ/kg] | −56.954955 | −43.752660 | **+13.202295** |
| energy loss [MJ/kg] | 19.921285 | 6.718990 | −13.202295 |
| source mode | QEG_GLIDE | SANGER_ATM | — |

**DeltaR_time = +1110.700 km、DeltaV_time = +2778.213 m/s、
DeltaE_time = +13.202 MJ/kg**（E0 §18 符号约定）。

解释（frozen baseline configuration 限定）：at equal elapsed time,
the Sanger trajectory is farther downrange and retains higher velocity
and specific mechanical energy.

## 6. Common-range comparison

R_common = **3490.698336 km**（= min(R_Q_RTI, R_S_SRTI)；两条轨迹
downrange 严格单调，min dR/dt > 0）

| Metric | Qian | Sanger | Difference |
|---|---|---|---|
| arrival time [s] | 723.037965 | 540.720236 | −182.317730 |
| altitude [km] | 46.040886 | 71.223555 | +25.182669 |
| velocity [m/s] | 3192.533 | 6511.963 | **+3319.430** |
| specific energy [MJ/kg] | −56.954955 | −40.605702 | **+16.349254** |
| energy loss [MJ/kg] | 19.921285 | 3.572032 | −16.349254 |
| source mode | QEG_GLIDE | SANGER_ATM | — |

**time saving (t_Q − t_S) = +182.318 s**；DeltaV_range = +3319.430
m/s；DeltaE_range = +16.349 MJ/kg。Root residuals = 0 m（E1 §18 策略）。

解释：At equal downrange, Sanger reaches the checkpoint earlier and
retains more velocity / specific mechanical energy.

## 7. Common atmospheric-exposure comparison

Protocol D：tau_common = **723.037965 s**（= Qian 总暴露；inverse
UNIQUE/UNIQUE）

| Metric | Qian | Sanger | Sanger − Qian |
|---|---|---|---|
| elapsed time [s] | 723.037965 | 1071.402523 | **+348.364558**（elapsed-time extension） |
| range [km] | 3490.698336 | 6612.247975 | **+3121.549639** |
| velocity [m/s] | 3192.533 | 5494.955 | +2302.422 |
| specific energy [MJ/kg] | −56.954955 | −46.621272 | **+10.333684** |
| energy loss [MJ/kg] | 19.921285 | 9.587602 | — |
| source mode | QEG_GLIDE | SANGER_ATM | — |

结构恒等式：`t_S(tau_common) − tau_common ≡ VAC duration before
checkpoint = 348.364557502 s`（逐位一致）。术语必须为
**cumulative atmospheric-mode exposure**，不是 thermal exposure /
heat exposure（E3 §10）。

## 8. Mechanical-energy mechanism

- 统一 E0（|E0_Q − E0_S| < 1e-3 J/kg）；energy_loss = E0 − E（无 abs、
  无 clipping）。
- Segment accounting（exact endpoints）：Qian TOTAL loss =
  19.921285 MJ/kg（ATM-only）；Sanger ATM 9.600743 MJ/kg + VAC
  −1.5e-08 J/kg（raw，保留符号）= TOTAL 9.600743 MJ/kg；
  telescoping residual = 0.0。
- **Sanger total VAC duration = 348.364558 s；VAC accumulated range =
  2171.733901 km；VAC mechanical-energy relative drift ≈ machine
  precision（1.8e-16）**。

正确表述：During VAC segments, downrange continues to accumulate while
specific mechanical energy is conserved to numerical precision under
the frozen VAC dynamics。**VAC accumulated range 不是 total Sanger
advantage 的 causal decomposition**（E3 §18/§22）。

结构身份（time/exposure accounting identity，非因果分解）：

```
Delta tau_R = (t_Q - t_S) + T_VAC,before-Rc
463.993948 s = 182.317730 s + 281.676218 s
```

## 9. Native endpoint / mode persistence

**Native Research-Endpoint / Mode-Persistence Comparison**
（RTI and SRTI have different terminal semantics. The differences are
descriptive, not a fair common-condition gain.）

| Metric | Qian @ RTI | Sanger @ SRTI |
|---|---|---|
| research duration [s] | 723.037965 | 1119.545984 |
| research range [km] | 3490.698336 | 6872.895320 |
| terminal velocity [m/s] | 3192.533 | 5482.946 |
| total energy loss [MJ/kg] | 19.921285 | 9.600743 |
| semantics | QEG feasibility loss | skip-capability loss |

## 10. Structural trajectory diagnostics

| Metric | Qian | Sanger |
|---|---|---|
| ATM fraction | 1.000000 | 0.688834 |
| VAC fraction | 0.000000 | 0.311166 |
| min altitude [km] | 46.040886 | 45.510562 |
| max altitude [km] | 100.000000 | 130.352121 |
| min velocity [m/s] | 3192.533 | 5482.946 |
| segments | ENTRY_CAPTURE → QEG_GLIDE | 3 ATM + 2 VAC（skip_count=2） |

Qian 不给伪对称的 skip_count=0（E4 §33）。

## 11. Aerodynamic context

| Quantity | Qian | Sanger |
|---|---|---|
| q_max [kPa] | 61.386611 | 61.386611 |
| aD_max [m/s²] | 12.277322 | 12.277322 |

两者 global 峰值相同——**global maxima occur during the shared initial
entry segment before the trajectories diverge**（t = 92.646 s、h =
46.051 km）。此后气动历史强烈分化（如 common-time 瞬时 q：Qian
13.469 kPa vs Sanger 0.065 kPa）。注意：**q ≠ heat flux、a_D ≠ total
g-load**；禁止 thermal / TPS / total-load inference（E0 §14、E4 §24）。

## 12. Core figures

| Figure | 内容 |
|---|---|
| Figure E1 | Trajectory Geometry |
| Figure E2 | State and Energy Retention |
| Figure E3 | Range–Energy Mechanism |
| Figure E4 | Cumulative Atmospheric Exposure |
| Figure E5 | Dynamic Pressure History |

Captions 见 `docs/phase_e/phase_e_results.md` §9。Visual review:
**5 / 5 PASS**（zai-mcp-server 逐图检查，E5 完成；E7 未修改 figures）。

## 13. Numerical and regression validation

- High-precision reference：DOP853 / rtol=1e-12 / tight state-scaled
  atol / max_step=0.1 s（REF-0.1）+ 0.05 s（REF-0.05 self-stability
  companion）。**numerical reference 不是 analytic solution**（E6 §1）。
- Cross-phase 独立检查：Qian REF-0.1 与 Phase C reference 逐位一致；
  Sanger REF-0.1 与 Phase D D6 reference 逐位一致（topology 相同）。
- 7-case audit matrix（REF-0.1/0.05、P8-20、P9-20、P10-20、P9-40、
  P9-10）：全部 derived metrics 稳定；production 处于 tolerance-side
  与 max-step-side 平台。

## 14. Integrated deterministic interpretation

Under the frozen baseline configuration:

1. Sanger travels farther and retains more velocity/energy at equal
   elapsed time（ΔR = +1110.7 km、ΔV = +2778.2 m/s、ΔE = +13.20
   MJ/kg）。
2. At equal downrange, Sanger reaches the checkpoint earlier while
   retaining more mechanical energy（saving = +182.3 s、ΔV = +3319.4
   m/s、ΔE = +16.35 MJ/kg）。
3. Sanger VAC intervals allow downrange accumulation with specific
   mechanical energy conserved to numerical precision（drift 1.8e-16）。
4. Accordingly, Sanger accumulates less atmospheric-mode exposure at
   the E2 checkpoints（−281.7 s / −464.0 s），and at equal cumulative
   atmospheric exposure can accumulate additional elapsed time /
   downrange（+348.4 s / +3121.5 km）。
5. The global aerodynamic peaks are identical because they occur in
   the shared initial entry segment; the later aerodynamic histories
   diverge.

## 15. Claim boundaries

禁止：universal superiority；statistical significance；robust
superiority；optimal trajectory；native endpoint range gain as fair
performance gain；thermal-load claims；TPS claims；total-g-load claims；
exact causal range decomposition；composite winner score（E0 §14-§16、
§20）。Phase E 是 deterministic frozen-baseline comparison。

## 16. Phase E acceptance

- [x] E0 comparison protocol — **FROZEN**（02fed87）
- [x] E0.1 dense-output access amendment — **FROZEN**（4fe7895）
- [x] E1 comparison alignment infrastructure — **FROZEN**（7fb91e7）
- [x] E2 common-condition comparison — **APPROVED**（8e81980）
- [x] E3 atmospheric/energy mechanism — **APPROVED**（8747fd1）
- [x] E4 native/structural/aerodynamic diagnostics — **APPROVED**
  （947a11d）
- [x] E5 figures/tables/interpretation — **APPROVED**（d3b70fa，
  figures 5/5 visual PASS）
- [x] E6 numerical/regression audit — **APPROVED**（f7aa53d，7/7
  semantic stability，production numerics APPROVED）
- [x] Production Phase E regression snapshot — **FROZEN**
  （tests/data/qian_sanger_comparison_v1.json，source =
  PRODUCTION_SOLVER_CONFIG）
- [x] Production numerical configuration — **FROZEN / VALIDATED**
- [x] 全部 regressions：pytest 229 passed；Qian / Sanger historical
  baselines unchanged；E1-E5 reproducibility PASS

## 17. Scope of subsequent phases

Phase E establishes the deterministic baseline against which later
sensitivity / predictability work will be evaluated。后续阶段可进入
gamma0-K sensitivity、parameter uncertainty、predictability、STM、
saltation、FTLE、Monte Carlo、optimization——本轮均不实现。

**Phase E: COMPLETE。**

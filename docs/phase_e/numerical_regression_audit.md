# E6 — Numerical and Regression Audit

## 1. Purpose

建立 Phase E derived-comparison 的 high-precision numerical reference，
验证 reference 自稳定、production（P9-20）相对 reference 的 numerical
error、comparison protocol 的 limiting endpoint / topology / mode
semantics 不随合理数值配置变化，并冻结 production Phase E regression
reference。不增加新的 scientific metric；不进入 E7。

## 2. Production configuration

```
PRODUCTION_SOLVER_CONFIG（保持不变，Phase C 冻结）：
DOP853 / rtol=1e-9 / atol=[1e-4, 1e-11, 1e-7, 1e-11] / max_step=20 s /
dense_output=True
```

Phase E production comparison 继续定义为 Qian frozen physics + Sanger
frozen physics + PRODUCTION_SOLVER_CONFIG。生产结果保存在
`tests/data/qian_sanger_comparison_v1.json` 作为官方 regression
reference；high-precision reference 仅用于 numerical error estimation
（numerical reference ≠ analytic solution ≠ physical truth）。

## 3. High-precision numerical reference

```
REFERENCE_SOLVER_CONFIG（与 Phase D D6 reference 同哲学）：
DOP853 / rtol=1e-12 / atol=[1e-7, 1e-14, 1e-10, 1e-14] / max_step=0.1 s /
dense_output=True
REF-0.05：相同 tolerance，max_step=0.05 s（self-stability companion）
```

未写入 PRODUCTION_SOLVER_CONFIG。实现方式：builders 增加可选
`solver_config` 参数（默认 PRODUCTION_SOLVER_CONFIG，无参数调用
bit-equivalent，E6 前行为逐位保留）；ComparisonTrajectory semantics /
state_at_time / inversion / exposure / mode / events 全部未改。

## 4. Reference self-stability

REF-0.1 vs REF-0.05（30 项 key metrics：Protocol B/C/D、energy、
structural、aerodynamic）：

- **max key metric difference = 1.395e-05**（单位随 metric：m / s / J/kg；
  远小于 production-vs-reference error 与 reporting precision）
- semantic topology equal = **True**（terminal kinds、skip_count、mode
  sequence、limiting identities、Protocol D status 全部相同）

self-stability error 明显小于 production-vs-reference error 与 Phase E
reporting precision → 自稳定平台成立。

## 5. Audit matrix

| Case | Qian term | Sanger term | skip | t-lim | R-lim | exp-lim | PD status | DeltaR_time [km] | time_sav [s] | DeltaR_tau [km] |
|---|---|---|---|---|---|---|---|---|---|---|
| REF-0.1 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700372 | 182.317730 | 3121.549633 |
| REF-0.05 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700372 | 182.317730 | 3121.549633 |
| P8-20 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700374 | 182.317730 | 3121.549712 |
| P9-20 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700372 | 182.317730 | 3121.549639 |
| P10-20 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700372 | 182.317730 | 3121.549634 |
| P9-40 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700372 | 182.317730 | 3121.549638 |
| P9-10 | RTI | SRTI | 2 | qian | qian | qian | UNIQUE/UNIQUE | 1110.700372 | 182.317730 | 3121.549633 |

这是 derived-metric numerical audit，不是 scientific parameter sweep。
tolerance-side（P8→P9→P10）与 max-step-side（P9-40/20/10）均显示
production 处于稳定平台（DeltaR_time 变化 ≤ 2e-6 km）。

## 6. Common-time convergence

P8/P9/P10 的 t_common、DeltaR_time、DeltaV_time、DeltaE_time 随
tolerance 收紧单调逼近 reference；production 与 reference 的
DeltaR_time 误差 = **4.3e-4 m**、DeltaV_time = 1.2e-6 m/s、
DeltaE_time = 2.8e-3 J/kg。

## 7. Common-range convergence

time_saving 误差 = **5.5e-8 s**、DeltaV_range = 1.1e-6 m/s、
DeltaE_range = 4.5e-3 J/kg。common-range root residuals 全部 case
≤ **9.3e-10 m**（远小于 trajectory numerical error → continuous range
inversion 不是 derived-error 主来源）。

## 8. Common-exposure convergence

DeltaR_atm_exposure 误差 = **5.6e-3 m**、elapsed_time_extension =
9.4e-7 s、DeltaV_tau = 4.7e-7 m/s、DeltaE_tau = 9.7e-4 J/kg。
Protocol D inverse 在全部 7 个 case 保持 **UNIQUE/UNIQUE**（无
PLATEAU 数值语义事件）。

## 9. Energy / structural diagnostic convergence

- Qian total loss 误差、Sanger total loss 误差、Sanger VAC duration /
  range 误差均 ≪ 1e-3 量级（J/kg、s、m）。
- h_min/h_max 误差 ≤ 5e-5 m；fractions 误差 ~1e-12。
- Sanger VAC max relative energy drift 全部 case ≤ 1e-16 量级
  （数值守恒不变）。

## 10. Aerodynamic peak convergence

q_max 误差 = **8.9e-5 Pa**、aD_max 误差 = **1.8e-8 m/s²**；peak time /
altitude 稳定（同一次公共初始入场峰值）。Qian/Sanger 初始共享峰值
相等性在 numerical precision 内继续成立（两轨迹入场段同方程）。
production 峰值不是 optimizer/sample artifact。

## 11. Protocol-semantic stability

- 三个 limiting identities（time/range/exposure）在全部 7 个 case 均为
  **qian**（与 production candidate 一致；无离散语义切换）。
- Qian terminal_kind = RTI、Sanger terminal_kind = SRTI、skip_count =
  2、mode sequence = ATM/VAC/ATM/VAC/ATM、checkpoint source modes 全部
  一致。
- 任何 case 无拓扑/模式变化。

## 12. Regression-reference definition

`tests/data/qian_sanger_comparison_v1.json`（tracked）：

- reference_name = `qian-sanger-comparison-v1`、source_protocol =
  Phase E E0、qian_baseline = qian-baseline-v1.0、sanger_baseline =
  sanger-baseline-v1.0；
- solver = **PRODUCTION_SOLVER_CONFIG**（硬性 gate：非 reference
  config）；
- semantic_fields：terminal kinds、skip_count、source structure、
  mode sequence、三个 limiter、Protocol D statuses、checkpoint
  source modes（exact equality 回归）；
- production_values：66 个数值字段（Protocol B/C/D、mechanism、
  structural、aerodynamic；不含 visualization curve）。

由 P9-20 production realization 生成（runner `--write-snapshot`），
不从 Markdown 手抄。

## 13. Regression tolerances

per-dimension tolerance（= observed production-vs-reference error 的
2–4 个数量级以上余量，且远低于 reporting precision）：

| Dimension | Tolerance | Observed error |
|---|---|---|
| time / exposure | 1e-3 s | ~5e-8 / 1e-6 s |
| range / altitude | 1.0 m | ~5e-3 / 5e-5 m |
| velocity | 1e-2 m/s | ~1e-6 m/s |
| energy | 0.1 J/kg | ~4.5e-3 J/kg |
| dynamic pressure | 0.1 Pa | ~9e-5 Pa |
| drag deceleration | 2e-5 m/s² | ~1.8e-8 m/s² |
| fractions | 1e-8 | ~1e-12 |
| dimensionless drift | 1e-12 | — |

semantic fields exact；numeric fields 按维度 tolerance。

## 14. Historical regression audit

- Qian historical baseline：unchanged（run_qian_glide.py sanity 全 PASS）。
- Sanger frozen baseline：unchanged（srti、skip_count=2）。
- E1–E5 全部 runner/summarizer 复跑结果 unchanged；E5 figures
  5/5 可重建（E6 未修改 plotting code/data/units → visual status
  inherited from E5: 5/5 PASS）。
- builders 的 solver override 默认路径 bit-equivalent（E6 前行为逐位
  保留）。

## 15. E6 acceptance

- [x] high-precision reference available（REF-0.1 / REF-0.05）
- [x] reference self-stability PASS（max diff 1.4e-05，语义相同）
- [x] Phase C Qian reference cross-check PASS（**逐位一致 0.000e+00**）
- [x] Phase D Sanger reference cross-check PASS（**逐位一致**，topology
  True）
- [x] production vs reference quantified（39 项全表）
- [x] derived comparison errors quantified（10 项 key derived errors）
- [x] tolerance-side audit PASS（P8/P9/P10 收敛）
- [x] max-step-side audit PASS（P9-40/20/10 平台）
- [x] limiting endpoint identities stable（7/7 qian/qian/qian）
- [x] Qian terminal semantics stable / Sanger topology stable
- [x] Protocol D UNIQUE stable（7/7）
- [x] common-range inversion stable（residual ≤ 9.3e-10 m）
- [x] energy accounting stable / VAC invariants stable
- [x] structural extrema stable / aero maxima stable
- [x] production solver retained（APPROVED，未替换）
- [x] production regression JSON created（tests/data/
  qian_sanger_comparison_v1.json）
- [x] regression JSON uses production values, not reference
- [x] semantic regression exact / numerical tolerances documented
- [x] E1–E5 unchanged / figures rebuild 5/5 / historical regressions
  unchanged / all tests PASS

**Artifacts**（`results/qian_sanger_comparison/numerical_audit/`，
不跟踪）：`reference_self_stability.json`、
`production_vs_reference.json`、`audit_matrix.csv` / `.json`、
`numerical_audit_summary.json`。

**结论**：Production comparison numerics: **APPROVED**。

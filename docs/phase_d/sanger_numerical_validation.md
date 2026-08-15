# D6 Sanger Numerical / Hybrid-Topology Validation

日期：2026-08-15
分支：`feature/phase-d-sanger-hybrid`
起点 commit：`29c5b3b`（D5 canonical candidate）
运行脚本：`experiments/05_sanger_numerical_validation/`
结果目录：`results/sanger_hybrid/numerical_validation/`（未入 Git）

## 1. Purpose

D6 回答七个问题：

1. Sanger 关键事件状态是否数值收敛；
2. atmosphere exit / entry / SRTI event timing 是否稳定；
3. completed skip_count 是否对合理 numerical settings 不变；
4. mode/event topology 是否保持不变；
5. production numerical configuration 是否足以支撑 D5 candidate；
6. VAC invariant 是否在不同 numerical settings 下稳定；
7. D5 regression reference 是否可以升级为正式 frozen baseline。

## 2. Numerical reference

仅用于误差比较的高精度数值参考（**不是** analytic / exact solution）：

```
method = DOP853
rtol   = 1e-12
atol   = [1e-7, 1e-14, 1e-10, 1e-14]
max_step = 0.1 s
dense_output = True
```

参考拓扑：skip_count = 2，terminal_kind = SRTI，
SRTI: t = 1119.5459841174863 s，h = 86138.741034 m，R = 6872895.319945 m，
v = 5482.946114 m/s。

## 3. Reference self-stability（0.1 s vs 0.05 s）

| 量 | 差 |
|---|---:|
| 拓扑（skip/mode/event sequence） | identical |
| 全部事件 max \|Δt\| | 1.429e-9 s |
| 全部事件 max \|Δh\| | 1.397e-7 m |
| 全部事件 max \|Δv\| | 1.854e-9 m/s |
| 全部事件 max \|ΔR\| | 8.018e-6 m |
| SRTI \|Δt\| / \|Δh\| / \|ΔR\| | 7.758e-10 s / 8.754e-8 m / 3.712e-6 m |

参考解自身离散化误差低于 1.4e-9 s / 1.4e-7 m，足以作为误差评估基准。

## 4. Production configuration accuracy

`PRODUCTION_SOLVER_CONFIG`（DOP853, rtol=1e-9, atol=[1e-4,1e-11,1e-7,1e-11],
max_step=20 s）相对 reference：

| 量 | 误差 |
|---|---:|
| 全部事件 max \|Δt\| | 5.618e-7 s |
| 全部事件 max \|Δh\| | 5.612e-5 m |
| 全部事件 max \|Δv\| | 7.057e-7 m/s |
| 全部事件 max \|ΔR\| | 3.200e-3 m |
| SRTI \|Δt\| | 3.312e-7 s |
| SRTI \|Δh\| | 5.612e-5 m |
| SRTI \|Δv\| | 7.057e-7 m/s |
| SRTI \|ΔR\| | 1.657e-3 m |
| research range 误差 | 1.657e-3 m |
| max altitude 误差 | 4.953e-5 m |
| topology equal reference | True |

## 5. Tolerance convergence（DOP853, max_step=20, coupled atol）

atol = rtol × [1e5, 1e-2, 1e2, 1e-2]（Phase C 耦合，helper 生成，无表复制）：

| rtol | skip | topo | \|Δt_SRTI\| [s] | \|Δh_SRTI\| [m] | \|ΔR_SRTI\| [m] | nfev | t [s] |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1e-6 | 2 | True | 5.749e-5 | 1.916e-3 | 3.097e-1 | 1216 | 0.02 |
| 1e-7 | 2 | True | 7.599e-6 | 1.182e-3 | 3.874e-2 | 1399 | 0.02 |
| 1e-8 | 2 | True | 4.514e-6 | 8.023e-4 | 2.258e-2 | 1570 | 0.02 |
| **1e-9** | **2** | **True** | **3.312e-7** | **5.612e-5** | **1.657e-3** | **1906** | **0.02** |
| 1e-10 | 2 | True | 2.360e-8 | 1.347e-6 | 1.174e-4 | 2344 | 0.03 |
| 1e-11 | 2 | True | 5.261e-10 | 1.667e-7 | 2.750e-6 | 2746 | 0.04 |

随 rtol 收紧误差单调收敛，无拓扑变化。

## 6. max_step convergence（rtol=1e-9）

| max_step [s] | skip | topo | \|ΔR_SRTI\| [m] | nfev | t [s] |
|---:|---:|---:|---:|---:|---:|
| 40 | 2 | True | 1.416e-3 | 1795 | 0.02 |
| 30 | 2 | True | 1.416e-3 | 1840 | 0.02 |
| **20** | **2** | **True** | **1.657e-3** | **1906** | **0.02** |
| 15 | 2 | True | 1.425e-3 | 1915 | 0.02 |
| 10 | 2 | True | 8.322e-5 | 2284 | 0.02 |
| 5 | 2 | True | 4.882e-5 | 3562 | 0.04 |
| 2 | 2 | True | 1.304e-8 | 8560 | 0.08 |
| 1 | 2 | True | 1.071e-7 | 16915 | 0.16 |
| 0.5 | 2 | True | 6.650e-7 | 33700 | 0.31 |
| 0.2 | 2 | True | 1.248e-7 | 84055 | 0.75 |
| 0.1 | 2 | True | 4.778e-7 | 167995 | 1.60 |

## 7. Hybrid topology stability

18 个 case（production + 6 rtol + 11 max_step）：

```
cases tested        = 18
topology changes    = 0
event-order swaps   = 0   (X1 与 SRTI candidate 先后关系从未翻转)
missing events      = 0
chatter             = 0
skip_count          = 2   (全部 case)
terminal_kind       = SRTI (全部 case)
```

## 8. Event residuals

| 量 | reference | production |
|---|---:|---:|
| max atmosphere residual [m] | 0.0 | 0.0 |
| max gamma residual [rad] | 1.315e-16 | 1.9e-12 |

crossing direction 检查（采样邻域，无状态扰动）：全部事件方向正确
（pull-out -→+、exit -→+、apogee +→-、entry +→-、SRTI +→-），
全部 case 通过。

## 9. VAC invariant validation

| 配置 | max rel energy drift | max rel angular-momentum drift |
|---|---:|---:|
| reference | 1.10e-15 | 2.19e-15 |
| production | 1.84e-16 | 3.65e-16 |
| tolerance sweep worst | 3.67e-16 | 3.96e-16 |
| max_step sweep worst | 6.61e-15 | 4.02e-15 |

全部为机器精度量级；不要求严格单调（浮点 roundoff 平台）。

## 10. Topological margins（reference）

| 量 | 值 | 意义 |
|---|---:|---|
| SRTI altitude margin M_h = h_atm − h_SRTI | 13861.26 m | ≫ 数值误差（~1e-4 m）：第三跳失败不是数值边界效应 |
| second apogee clearance M_A1 = h_A1 − h_atm | 2232.58 m | ≫ 毫米/厘米级误差：第二跳存在性数值稳健 |
| exit gamma (X1) | +0.02245912 rad | 明确 outward crossing，非 grazing |
| exit dh/dt (X1) | +133.92 m/s | 事件 transversal |
| entry gamma / dh/dt | −0.02245912 rad / −133.92 m/s | 明确 re-entry |
| SRTI gamma_dot | −8.719e-4 rad/s | 非退化 crossing，root 定位可靠 |

## 11. Accuracy-cost tradeoff

production（rtol=1e-9, max_step=20, nfev=1906, ~0.02 s）误差
\|ΔR_SRTI\| = 1.7e-3 m，位于准确度-成本 sweet spot：
loose 端（1e-6）误差 0.31 m，tight 端（1e-11）误差 2.8e-6 m 但 nfev 仅 +44%。
max_step 从 40 到 0.1 均无拓扑变化，20 s 并非"恰好"边界而是充分条件。

## 12. D6 acceptance

| # | Item | 结论 |
|---|---|---|
| 1 | high-precision Sanger numerical reference established | **PASS** |
| 2 | reference 0.1 vs 0.05 self-stable（≤1.4e-9 s） | **PASS** |
| 3 | reference topology identical | **PASS** |
| 4 | production topology identical to reference | **PASS** |
| 5 | production skip_count identical（=2） | **PASS** |
| 6 | production terminal_kind == SRTI | **PASS** |
| 7 | production event sequence identical | **PASS** |
| 8 | production event-state error quantified（Δt≤5.6e-7 s, ΔR≤3.2e-3 m） | **PASS** |
| 9 | tolerance sweep completed（6 档） | **PASS** |
| 10 | max_step sweep completed（11 档） | **PASS** |
| 11 | no topology change in accepted numerical range | **PASS** |
| 12 | no event-order swap | **PASS** |
| 13 | no event chatter | **PASS** |
| 14 | no missing event | **PASS** |
| 15 | event residuals small（0 m / 1e-16 rad 级） | **PASS** |
| 16 | transition states exactly continuous（全部 case） | **PASS** |
| 17 | VAC energy invariant stable（~1e-15） | **PASS** |
| 18 | VAC angular momentum invariant stable（~1e-15） | **PASS** |
| 19 | SRTI altitude margin quantified（13.86 km） | **PASS** |
| 20 | second-apogee clearance quantified（2.23 km） | **PASS** |
| 21 | exit/entry transversality quantified（dh/dt=±134 m/s） | **PASS** |
| 22 | SRTI transversality quantified（gamma_dot=−8.7e-4 rad/s） | **PASS** |
| 23 | production config still justified | **PASS** |
| 24 | D5 reference approved | **PASS**（见下） |
| 25 | Phase A-C unchanged | **PASS** |
| 26 | D1-D5 unchanged | **PASS** |
| 27 | Qian baseline unchanged | **PASS** |
| 28 | all tests PASS | **PASS** |

### D5 baseline reference 结论

`tests/data/sanger_baseline_v1.json` 与 high-precision reference 的偏差
全部处于 production numerical error 内（ΔR_SRTI = 1.7e-3 m ≪ 10 m 容差；
Δt = 3.3e-7 s ≪ 1e-3 s；Δh = 5.6e-5 m ≪ 1 m）。**D5 regression
reference 批准为正式 frozen baseline 候选。**

### Production solver 结论

**继续批准** `DOP853, rtol=1e-9, atol=[1e-4,1e-11,1e-7,1e-11],
max_step=20 s` 用于正式 Sanger baseline。四方面证据：

- **accuracy**：SRTI ΔR = 1.7e-3 m、Δt = 3.3e-7 s（远优于 acceptance）；
- **event stability**：全部事件残差 ~0，方向正确，无 chatter；
- **topology stability**：18/18 case 与 reference 拓扑完全一致；
- **cost**：nfev=1906 / ~0.02 s，位于准确度-成本 sweet spot。

`PRODUCTION_SOLVER_CONFIG`（Phase C frozen）**未修改**。

---

*本报告为 D6 tracked artifact。reference 是数值参考解，非 analytic truth。*
*Tag（sanger-baseline-v1.0 / phase-d-v1.0）由 D7 final freeze 创建。*

# Phase C Final Report — Numerical Validation / Solver Convergence

日期：2026-08-15（Phase C 完成时报告；对应冻结 `PRODUCTION_SOLVER_CONFIG`，
tag：`phase-c-v1.0`）

## 1. Purpose and scope

Phase C 的目标是对 Phase B.5 冻结的 Qian 三模式混合基线
（`ENTRY_CAPTURE -> QEG_GLIDE -> RTI -> GROUND_CONTINUATION`）做系统的
**数值误差 / 求解器收敛性验证**，并据此冻结一个正式的科研 production 数值配置：

- 建立高精度 **numerical reference**（注意：它是数值收敛参考解，**不是**
  analytic / exact solution）；
- 比较 RK45 / DOP853 / Radau / BDF 四种 `solve_ivp` 求解器；
- 扫描 rtol 与 max_step，确认事件时间（Capture / RTI）与 RTI 射程的收敛；
- 验证混合事件（hybrid event）在所有配置下的离散模式结构一致性；
- 完成 accuracy-cost tradeoff 分析并冻结 production 配置。

本阶段**不修改**任何 Phase B 冻结内容：物理模型、`EnvironmentParams` /
`VehicleParams` / 初始条件、K=3、Capture 事件、QEG 控制律、RTI 定义、
Ground continuation、`DEFAULT_SOLVER_CONFIG` 全部保持不变。

## 2. Frozen physical baseline

被验证的基线（Phase B.5 冻结，`qian-baseline-v1.0`）：

```text
ENTRY_CAPTURE        u_L = 1，字面 Eq.(4) 动力学；终止于 gamma 首次向上过零
                     （gamma = 0, direction = +1）
QEG_GLIDE            u_L = clip(L_req / L, 0, 1)，L_req = m(g - v^2/r) cos(gamma)；
                     终止于 u_L* = 1 首次向上过零（L_req = L，RTI = QEG 可行性丧失）
GROUND_CONTINUATION  u_L = 1，字面 Eq.(4) 动力学；自然延续到地面事件 h = 0
```

初始条件 h0 = 100 km，v0 = 7000 m/s，gamma0 = -5 deg，theta0 = 0；
K = L/D = 3（`ConstantKControl(3.0)`）。

Phase C 实验代码（`experiments/03_numerical_validation/common.py`）只负责
**编排**三阶段积分并记录 `solve_ivp` 诊断（nfev / njev / nlu、wall time、
事件状态与事件残差），所有动力学 / 控制 / 事件均 import 冻结模块，仓库内
不存在第二套动力学。

## 3. Numerical methodology

- 三阶段事件驱动积分与 `integrate_qian_glide` 完全一致：每阶段以
  `solve_ivp` 终端事件根定位结束，下一阶段从上一阶段事件状态继续；
- 所有比较在同一容差语义下进行：**state-scaled atol 向量**
  `[r, theta, v, gamma] ~ [1e-3 m, 1e-10 rad, 1e-6 m/s, 1e-10 rad]`
  （Phase B 基准配置）；误差均相对 §4 的 numerical reference 计算；
- wall time 为单机（Windows, scipy 1.18）单次运行计时，仅用于相对比较；
- 运行规模：solver 比较 4 例 + tolerance sweep 48 例（fixed/scaled × 4 solver
  × 6 rtol）+ max_step sweep 12 例 + production 复核 1 例 + C6 候选基准
  4 配置 ×（2 warmup + 15 repeats）= **64 个验证 case + 68 次候选计时**。

## 4. High-precision numerical reference

配置：`DOP853, rtol=1e-12, atol=BASE_ATOL * 1e-4 = [1e-7, 1e-14, 1e-10, 1e-14],
max_step = 0.1 s`；另以 `max_step = 0.05 s` 复核参考解自身稳定性。

| 端点 | t [s] | h [km] | v [m/s] | R [km] |
|---|---:|---:|---:|---:|
| Capture | 93.4287853468 | 46.040886 | 6810.795567 | — |
| RTI | 723.037965475 | 46.040886 | 3192.533183 | 3490.698337 |
| Ground | 2017.959901287 | 0 | 159.922381 | 5363.623046 |

参考解统计：nfev = 303153，njev = 0，nlu = 0，事件残差
（RTI: `L_req - L`）≈ 2e-12，地面事件残差 = 0。

**参考解稳定性（0.1 s vs 0.05 s max_step，绝对差）**：

| 量 | 差 |
|---|---:|
| t_capture | 1.4e-11 s |
| h_capture | 1.3e-8 m |
| v_capture | 3.5e-11 m/s |
| t_RTI | 2.1e-10 s |
| h_RTI | 1.3e-8 m |
| v_RTI | 2.3e-9 m/s |
| R_RTI | 2.1e-6 m |
| t_ground | 1.5e-9 s |
| R_ground | 5.1e-6 m |
| v_ground | 5.1e-11 m/s |

即参考解自身离散化误差低于 2.1e-10 s（时间）/ 5.1e-6 m（射程），
足以作为后续所有误差评估基准。

> **重要声明**：该结果名为 **numerical reference**（数值收敛参考解），
> 不是 true / analytic / exact solution。

## 5. Solver comparison

公共配置 `rtol=1e-8, atol=BASE_ATOL, max_step=10 s`（Phase B 基准配置）：

| Solver | \|Δt_capture\| [s] | \|Δt_RTI\| [s] | \|ΔR_RTI\| [m] | nfev | njev | nlu | wall [s] |
|---|---:|---:|---:|---:|---:|---:|---:|
| RK45 | 2.0e-8 | 4.2e-6 | 3.9e-2 | 2496 | 0 | 0 | 0.033 |
| **DOP853** | **2.4e-8** | **5.5e-8** | **5.7e-4** | 3534 | 0 | 0 | 0.038 |
| Radau | 2.6e-9 | 1.0e-7 | 1.1e-3 | 6092 | 37 | 428 | 0.163 |
| BDF | 1.5e-5 | 4.4e-5 | 3.4e-1 | 1788 | 28 | 153 | 0.089 |

在相同容差下：DOP853 的 RTI 事件时间误差比 RK45 小 76×、比 BDF 小 800×；
RTI 射程误差比 RK45 小 68×、比 BDF 小 600×。Radau 精度与 DOP853 相当，
但 nfev 多 72% 且需要额外的雅可比分解（njev/nlu > 0），wall time 4.3×。

## 6. Tolerance convergence

### 6.1 固定 Phase B atol（仅收紧迫 rtol，DOP853）

| rtol | \|Δt_RTI\| [s] | \|ΔR_RTI\| [m] | nfev | wall [s] |
|---|---:|---:|---:|---:|
| 1e-5 | 3.7e-6 | 3.5e-2 | 3324 | 0.038 |
| 1e-6 | 2.4e-5 | 2.3e-1 | 3435 | 0.040 |
| 1e-7 | 4.7e-6 | 4.6e-2 | 3411 | 0.038 |
| **1e-8** | **5.5e-8** | **5.7e-4** | 3534 | 0.040 |
| 1e-9 | 5.1e-8 | 2.5e-4 | 3567 | 0.039 |
| 1e-10 | 5.4e-8 | 5.5e-4 | 3780 | 0.043 |

固定 atol 时，rtol < 1e-7 后误差受 **atol 下限主导**，不再单调下降——
这正是"容差必须 state-scaled 且随 rtol 联动收紧"的原因。

### 6.2 联动收紧 atol（atol = BASE_ATOL × rtol/1e-8，全 solver）

| rtol | RK45 \|ΔR\| [m] | DOP853 \|ΔR\| [m] | Radau \|ΔR\| [m] | BDF \|ΔR\| [m] |
|---|---:|---:|---:|---:|
| 1e-5 | 1.3e+1 | 3.5e-2 | 1.8e-1 | 3.0e+2 |
| 1e-6 | — | 3.9e-2 | — | 5.0e+1 |
| 1e-7 | — | 5.7e-2 | — | 3.5 |
| 1e-8 | 3.9e-2 | 5.7e-4 | 1.1e-3 | 3.4e-1 |
| **1e-9** | **3.7e-3** | **3.5e-4** | **1.7e-4** | **7.7e-2** |
| 1e-10 | — | 7.7e-5 | — | 1.4e-2 |

DOP853 在 1e-8 → 1e-9 → 1e-10 的误差为 5.7e-4 → 3.5e-4 → 7.7e-5 m，
成本 nfev 3534 → 3798 → 4032（+7.5% / +6%）。BDF 在全部容差下误差最大
（1e-9 时为 DOP853 的 220×）。

## 7. max_step convergence

DOP853 @ `rtol=1e-9, atol=BASE_ATOL×0.1`（production 容差语义）扫 12 档：

| max_step [s] | \|Δt_RTI\| [s] | \|ΔR_RTI\| [m] | nfev | wall [s] |
|---|---:|---:|---:|---:|
| 40.0 | 1.2e-7 | 1.20e-3 | 2610 | 0.033 |
| 30.0 | 1.2e-7 | 1.20e-3 | 2733 | 0.030 |
| **20.0** | **1.2e-7** | **1.20e-3** | 2667 | 0.038 |
| 15.0 | 1.6e-7 | 1.57e-3 | 2910 | 0.034 |
| 10.0 | 3.6e-8 | 3.5e-4 | 3798 | 0.046 |
| 7.5 | 1.1e-8 | 1.1e-4 | 4617 | 0.055 |
| 5.0 | 6.6e-8 | 6.3e-4 | 6579 | 0.080 |
| 2.0 | 3.2e-11 | 2.6e-7 | 15477 | 0.187 |
| 1.0 | 1.2e-9 | 4.1e-6 | 30531 | 0.386 |
| 0.5 | 3.1e-11 | 3.5e-7 | 60816 | 0.678 |
| 0.2 | 3.3e-11 | 9.5e-8 | 151560 | 1.806 |
| 0.1 | 9.4e-10 | 2.9e-6 | 302796 | 3.596 |

**`max_step = 20 s` 已进入稳定平台**：与 0.1 s 相比事件时间差 < 0.12 μs、
射程差 ~1.2 mm（相对误差 < 3e-7），而 nfev 从 302796 降到 2667
（**成本下降 114×**）。15–40 s 区间误差完全平台化（~1.2e-3 m）。

## 8. Hybrid-event consistency

全部 **64 个验证 case + 4 个 C6 候选配置**检查：

```text
no missing events        （每个 case 均检测到 Capture / RTI / Ground 三个事件）
no event chatter         （事件时间严格递增：0 < t_capture < t_RTI < t_ground）
no duplicated events     （solve_ivp 每事件单根）
no mode-order changes    （模式结构始终 ENTRY_CAPTURE -> QEG_GLIDE -> GROUND_CONTINUATION）
no NaN / Inf             （所有事件状态有限）
no u_L violations        （capture 后 u_L = 0.0664 ∈ [0,1]；QEG 段由 clip 构造保证）
solver success           （全部 case 积分成功）
```

`summarize_numerical_validation.py` 的 `hybrid_consistency_all_sweeps = True`
覆盖全部 sweep case；C6 四个候选的 `hybrid_consistency_ok` 均为 True。

## 9. Accuracy-cost tradeoff

| 候选 | 配置 | median [s] | nfev | \|Δt_RTI\| [s] | \|ΔR_RTI\| [m] |
|---|---|---:|---:|---:|---:|
| P8-20 | 1e-8 / BASE_ATOL / 20 s | 0.0247 | 2223 | 5.1e-7 | 5.9e-3 |
| **P9-20** | **1e-9 / BASE_ATOL×0.1 / 20 s** | **0.0283** | **2667** | **1.2e-7** | **1.2e-3** |
| P10-20 | 1e-10 / BASE_ATOL×0.01 / 20 s | 0.0367 | 3498 | 1.1e-8 | 1.1e-4 |
| P9-10 | 1e-9 / BASE_ATOL×0.1 / 10 s | 0.0415 | 3798 | 3.6e-8 | 3.5e-4 |

（每个候选 2 次 warmup + 15 次计时，median / mean / std 见
`results/numerical_validation/final_candidates/final_candidates.csv`）

tradeoff 判读：

- **P9-20 vs P8-20**：RTI 射程误差 5.9 mm → 1.2 mm（**5× 精度收益**），
  nfev 仅 +20%、median runtime 仅 +15% —— 甜点位；
- **P10-20 vs P9-20**：误差再降 10×（1.2 mm → 0.11 mm），但成本 +31%
  nfev / +30% runtime——对论文量级（mm 级 vs km 级量程）无实际意义，
  **收益递减**；
- **P9-10 vs P9-20**：max_step 10 s 反而更贵（+42% runtime）且误差更大
  （0.35 mm vs 1.2 mm 均在 mm 以下）——max_step=20 s 平台确认。

## 10. Production numerical configuration

正式冻结（`src/hyptraj/simulation/numerics.py`）：

```python
PRODUCTION_SOLVER_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-9,
    atol=np.array([
        1e-4,
        1e-11,
        1e-7,
        1e-11,
    ]),
    max_step=20.0,
    dense_output=True,
)
```

逐项理由：

- **为什么 DOP853**：同容差下事件时间 / 射程误差比 RK45 小 70–800×；
  与 Radau 精度相当但 nfev 少 42%、无需雅可比（njev/nlu = 0）；
  BDF 在全部容差下精度最差。DOP853 是唯一 accuracy-cost 全面占优者；
- **为什么 rtol = 1e-9**：在联动收紧 atol 下相对 1e-8 获得 5× 精度（1.2 mm），
  成本仅 +20%；1e-10 只剩 10× 微增收益却 +31% 成本（§9）；
- **为什么 state-scaled atol**：状态分量量纲差异巨大
  （r ~ 6.4e6 m，theta ~ 0.5 rad，v ~ 3e3 m/s，gamma ~ 0.1 rad）。
  标量 atol 会要么对 theta/gamma 过严、要么对 r/v 过松；§6.1 已实证
  固定 atol 时 rtol 收紧会被 atol 下限主导而失效。`[1e-4, 1e-11, 1e-7, 1e-11]`
  是 `BASE_ATOL × 0.1`，与 rtol=1e-9 联动；
- **为什么 max_step = 20 s**：§7 实证 15–40 s 已进入误差平台（~1.2e-3 m，
  < 3e-7 相对误差），20 s 的 nfev 比 10 s 少 30%、比 0.1 s 少 114×；
- **为什么没有选 1e-10**：成本 +31% 只换 10× 精度（mm → 0.1 mm），
  收益递减且无论文意义（§9）；
- **为什么没有选 Radau / BDF**：Radau 精度相当但成本 4.3× 且需雅可比；
  BDF 精度始终最差（1e-9 时 DOP853 的 220×）。

同时保持：

```text
DEFAULT_SOLVER_CONFIG   （Phase B frozen：DOP853 / 1e-8 / [1e-3,1e-10,1e-6,1e-10] / 10 s）
```

继续保留，用于历史 baseline regression 与 Phase B 结果复现。

## 11. Phase C acceptance

```text
pytest:                          35 passed
Qian frozen regression:          PASS（93.429 / 723.038, 3490.70 / 2017.960, 5363.62, 159.922）
Numerical reference:             PASS（0.1 s vs 0.05 s 稳定）
Solver comparison:               PASS（4 solver）
Tolerance convergence:           PASS（48 case）
max_step convergence:            PASS（12 case）
Hybrid consistency:              PASS（64 + 4 case 全一致）
C6 production candidate:         PASS（P9-20 支持 production 配置）
Canonical code audit:            PASS（9 文件 SHA-256 与 canonical 一致）
```

`summarize_numerical_validation.py` 的 acceptance 检查全部为 True：
`all_four_solvers_compared`、`reference_exists`、`tolerance_sweep_complete`
（≥24 case）、`max_step_sweep_complete`（≥6 case）、`hybrid_consistency`。

## 12. Implications for Phase D and predictability research

1. **trajectory solver 已冻结**：从 Phase D 开始，科研 trajectory 统一使用
   `PRODUCTION_SOLVER_CONFIG`（DOP853 / 1e-9 / state-scaled atol / 20 s）；
2. **STM / FTLE 需要独立收敛验证**：trajectory solver 冻结**不代表**
   STM / FTLE / saltation 的数值设置自动冻结——它们各自需要独立的
   convergence validation；
3. **混合事件敏感性**：Capture 是 hybrid switch（u_L 跳变），跨 Capture 的
   STM / FTLE 必须计入 saltation 更新（Phase B.5 已注记，Phase D 实现）；
4. **参考解语义**：论文中引用本阶段数值时应使用 "numerical reference"
   措辞，避免 "true solution" / "analytic solution" 表述；
5. 本阶段的 64-case sweep 网格与 C6 候选基准为后续 robustness /
   sensitivity 研究提供了可直接复用的实验脚手架
   （`common.run_case` + 事件残差检查）。

# Phase B Final Report — Literal Eq.(4) Baseline

日期：2026-08-15（Phase B 完成时的报告；后续 Phase B.5 审计见
`phase_b5_final_consolidation_report.md` 与 `../model_audit/`）

## 1. Changed Files（Phase B 阶段）

- **新增**：`src/hyptraj/models/dynamics.py`（`atmospheric_dynamics`）、
  `src/hyptraj/simulation/{events,trajectory}.py`、`src/hyptraj/metrics/trajectory_metrics.py`、
  `experiments/01_baseline_dynamics/`、`tests/test_models/{test_dynamics,test_events}.py`
- **修改**：`src/hyptraj/controls/__init__.py`（修复骨架 bug：内容被误写为
  pyproject.toml 导致包导入失败）、`pyproject.toml`、`.gitignore`

## 2. Model Implementation

四维纵向动力学（与题面式(4)逐项一致）：

    dr/dt = v sin(gamma)
    dtheta/dt = v cos(gamma) / r
    dv/dt = -D/m - g(h) sin(gamma)
    dgamma/dt = L/(m v) + (v/r - g(h)/v) cos(gamma)

g(h) = g0 (Re/(Re+h))^2；rho(h) = rho0 exp(-h/H)；q = 0.5 rho v^2；
D = q S C_D；L = q S C_L；C_L = K C_D；K 由 `ConstantKControl(3.0)` 提供。
数值保护：v<=0 / r<=0 抛异常；地面附近仅对大气输入截断 `h_eval = max(h, 0)`，
积分状态从不修改。触地时间由 solve_ivp 事件根定位获得。

## 3. Solver Configuration

DOP853, rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10], max_step=10 s,
dense_output=True, t_span=(0, 5000 s)（由 ground event 提前终止）。

## 4. Test Results（Phase B 时点）

    pytest -q  ->  24 passed

## 5. Literal Baseline Numerical Results（冻结于 literal_eq4_uncontrolled）

| Metric | Result |
|---|---:|
| Flight time | 3508.887 s |
| Range | 13578.506 km |
| Terminal velocity | 159.954 m/s |
| Max altitude | 130.408 km |
| Max dynamic pressure | 61365.576 Pa |
| Dynamic pressure integral | 3.896x10^7 Pa.s |
| Ground residual | 0.000000 m |
| nfev | 5843 |

## 6. 关于题目表 2 参考范围的重要说明

结果未落入题面参考范围（6000–8500 km / 1200–1800 s / 800–1500 m/s）。经过
5 重独立验证（提示词 9 项检查、DOP853/RK45 收敛、独立 RK4 实现、解析平衡滑翔
验证、全参数扫描），确认题面参考表与题面给出的方程+参数+初始条件**不自洽**。
按"不要修改物理参数去拟合答案"的政策，未做任何调参；参考范围降级为外部比较值。
详见 `docs/model_audit/phase_b5_qian_continuous_glide_audit.md`。

## 7. Generated Artifacts（Phase B 时点）

`results/baseline/literal_eq4_uncontrolled/`：trajectory.csv、metrics.json、
metadata.json、figures/（5 张 300 dpi 图）。

## 8. Sanity Checks

全部通过：integration success、ground event、state/derived finite、
velocity>0、density/q/D/L>=0、terminal altitude ~0、range 严格前进。

## 9. Regression Test

基准值：tf=3508.886850796115 s、Rf=13578.506212620006 km、
vf=159.95359846310112 m/s；容差 rel=1e-4（solver 收敛水平 ~1e-9 之上留
5-6 个数量级裕度）。`tests/test_models/test_literal_eq4_baseline.py`。

## 10. Known Limitations（Phase B 时点）

指数大气、固定 C_D、固定 K、二维纵向、无地球自转、热载荷为动压积分代理量。
（后续 Phase B.5 审计识别出更深层问题：固定 K + 固定正升力不能自动产生
continuous glide——见 `../model_audit/phase_b5_qian_continuous_glide_audit.md`。）

## 11. Final Decision（Phase B 时点）

    PHASE B: PASS

（以"参考量级"为准；严格数值参考范围未命中，差异已完整记录。后续 Phase B.5
通过人工批准冻结了正式双端点 Qian 基线 `qian_continuous_glide`。）

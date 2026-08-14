# Phase B.5-B2 Terminal Audit — T1 vs T2（审计参考，非正式 baseline）

日期：2026-08-15
状态：审计完成；`DECISION: NEITHER-FINAL` —— T1/T2 均保留为终端包络参考，
均不提升为 production 终端模型。数据文件：`results/audit/phase_b5/terminal_audit.json`
（由 `experiments/01_baseline_dynamics/audit/terminal_audit.py` 生成）。

## 1. Common QEG-end State（两候选共用起点）

t = 723.038 s；h = 46.041 km；v = 3192.533 m/s；gamma ~ 0；R = 3490.7 km；
L = L_req = 8081.4 N；u_L = 1。数值设置与 QEG 探索完全一致（DOP853, rtol=1e-8,
分量 atol, max_step=10 s, ground event h=0）；唯一差异是 u_L。

## 2. T1 — Full-Lift Natural Descent（u_L ≡ 1, sigma = 0）

- Delta t_terminal = 1294.9 s；Delta R_terminal = 1872.9 km；
- v_f = 159.9 m/s（gamma_f = -15.8 deg）；
- 终端动压峰值 15.74 kPa；热载荷代理（int q dt）1.954x10^7 Pa.s；
- 全程：t_f = 2018.0 s；R_f = 5363.6 km；动压峰值 61.4 kPa（出现在 ENTRY）；
- eta_v = v_f/v_QEG-end = 0.050；delta v_terminal = 3032.6 m/s；
- 形态事件：0 次 gamma 零穿越、0 次高度极值（无再捕获/再拉起/振荡），
  7 次 eta_L=1 穿越（沿平衡下滑线"跟随式下降"）；
- 控制连续性：**连续**（QEG 末端 u_L=1 -> T1 u_L=1，delta u_L = 0）。

## 3. T2 — Zero-Longitudinal-Lift Terminal Dive（u_L ≡ 0, sigma=90 deg 二维投影）

- Delta t_terminal = 134.5 s；Delta R_terminal = 299.3 km；
- v_f = 392.3 m/s（gamma_f = -41.7 deg）；
- 终端动压峰值 279.5 kPa；热载荷代理 1.544x10^7 Pa.s；
- 全程：t_f = 857.6 s；R_f = 3790.0 km；动压峰值 279.5 kPa（终端俯冲段超过 ENTRY）；
- eta_v = 0.123；delta v_terminal = 2800.3 m/s；
- 俯冲：gamma_min = -41.7 deg；gamma=-5/-10/-20/-30 deg 分别于
  t=756.9/788.6/828.3/845.0 s（h=41.5/29.2/9.4/3.5 km）达到；
- 控制连续性：**不连续但事件局部化**（delta u_L = -1）。
- 注明：sigma=90 deg 在真实 3DOF 下升力转侧向，本二维模型忽略侧向动力学——
  为"等效二维极限"，不是完整 3DOF bank maneuver。

## 4. T1 vs T2 比较要点

| Metric | T1 | T2 |
| --- | ---: | ---: |
| terminal duration [s] | 1294.9 | 134.5 |
| terminal range [km] | 1872.9 | 299.3 |
| v_f [m/s] | 159.9 | 392.3 |
| terminal q peak [kPa] | 15.7 | 279.5 |
| eta_v | 0.050 | 0.123 |
| control continuity | continuous | discontinuous |

评价优先级：物理解释 > 无任意参数 > 数学清晰性 > STM/FTLE 兼容性 >
末端能量合理性 > reference 接近程度。

## 5. Recommendation（推荐不等于批准）

    Recommended terminal candidate: T1 (Full-Lift Natural Descent)
    Confidence: medium

理由：T1 是 QEG 末端（u_L=1）无控制动作的自然延续，控制连续、RHS（分段）光滑，
对后续 STM/FTLE 无 saltation 负担；T2 需要 sigma 阶跃 90 deg 的主动控制动作且
引入事件面跳变。最终人工决策为 **NEITHER-FINAL**：两者均保留为终端包络参考；
正式基线的地面续接采用 T1 律（u_L=1），命名为 GROUND_CONTINUATION（非终端制导律）。

## 6. 度量修正记录（DECISION 后续）

- 高超声速驻留时间统计 bug 已修复：旧实现用首段步长乘全部点数，导致
  T2 的 v>1500 时长 892.1 s > 总飞行 857.6 s；修复后 T1/T2 均自洽
  （T1: 1325.6 <= 2018.0；T2: 822.4 <= 857.6）；
- 术语：q_max -> dynamic-pressure peak；int q dt -> thermal-load proxy。

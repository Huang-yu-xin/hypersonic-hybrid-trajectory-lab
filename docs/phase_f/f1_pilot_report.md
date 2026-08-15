# F1 — Single-Parameter Pilot

状态：**COMPLETE**（2026-08-16，无 stop gate）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `81b3a99`（F0.1）
Artifacts: `results/gamma_k_sensitivity/pilot/`（untracked）
Sources: `docs/phase_f/sensitivity_protocol.md`（F0 + F0.1）

## 1. Purpose

运行 F0 冻结的两条 17-point one-dimensional slices（gamma slice + K slice），
验证 Phase-F structured regime APIs 在真实非-baseline 参数点工作，统计
Qian / Sanger 的 physical regimes，识别 topology-transition candidate
intervals，检查 censored / numerical failure / chatter / invalid sequence，
验证 baseline anchor，并判断 F2 17×17 coarse map 是否可以安全启动。

**不是**：正式二维 sensitivity map、derivative 计算、F2、adaptive
refinement、Phase-E Protocol B/C/D surfaces、optimization、uncertainty、
STM / saltation / FTLE。

## 2. Baseline anchor validation

p0 = (-5 deg, 3) 与 `tests/data/qian_sanger_comparison_v1.json` 全部检查
PASS（相对容差 1e-9，实测差值为 0.0）：

| 检查 | 结果 |
|---|---|
| Qian regime = QIAN_RTI | PASS |
| Qian capture time = 93.42878537129322 s | PASS（diff = 0.0）|
| Qian RTI time = 723.0379653550676 s | PASS（diff = 0.0）|
| Qian RTI range = 3490698.335988048 m | PASS（diff = 0.0）|
| Qian mode sequence = [ENTRY_CAPTURE, QEG_GLIDE] | PASS |
| Sanger regime = SRTI_N2 | PASS |
| Sanger terminal time = 1119.5459841174863 s | PASS（diff = 0.0）|
| Sanger terminal range = 6872895.31994491 m | PASS（diff = 0.0）|
| Sanger skip_count = 2 | PASS |
| Sanger mode sequence = 5-segment ATM/VAC 交替 | PASS |

## 3. Gamma slice（K = 3.0，17 points）

| gamma0 | Qian regime | Qian RTI range [km] | Sanger regime | skip | Sanger range [km] | M_S [km] |
|---|---|---:|---|---|---:|---:|
| -7.00 | QIAN_RTI | 2717.620 | SRTI_N2 | 2 | 7030.829 | 5.722 |
| -6.75 | QIAN_RTI | 2801.713 | SRTI_N2 | 2 | 7015.561 | 6.719 |
| -6.50 | QIAN_RTI | 2889.251 | SRTI_N2 | 2 | 6998.800 | 7.725 |
| -6.25 | QIAN_RTI | 2980.330 | SRTI_N2 | 2 | 6980.613 | 8.739 |
| -6.00 | QIAN_RTI | 3075.026 | SRTI_N2 | 2 | 6961.090 | 9.759 |
| -5.75 | QIAN_RTI | 3173.396 | SRTI_N2 | 2 | 6940.355 | 10.783 |
| -5.50 | QIAN_RTI | 3275.473 | SRTI_N2 | 2 | 6918.576 | 11.810 |
| -5.25 | QIAN_RTI | 3381.255 | SRTI_N2 | 2 | 6895.980 | 12.837 |
| -5.00 | QIAN_RTI | 3490.698 | SRTI_N2 | 2 | 6872.895 | 13.861 |
| -4.75 | QIAN_RTI | 3603.709 | SRTI_N2 | 2 | 6850.005 | 14.882 |
| -4.50 | QIAN_RTI | 3720.132 | SRTI_N1 | 1 | 4900.936 | 1.510 |
| -4.25 | QIAN_RTI | 3839.742 | SRTI_N1 | 1 | 4879.760 | 3.329 |
| -4.00 | QIAN_RTI | 3962.229 | SRTI_N1 | 1 | 4859.773 | 5.103 |
| -3.75 | QIAN_RTI | 4087.191 | SRTI_N1 | 1 | 4841.506 | 6.827 |
| -3.50 | QIAN_RTI | 4214.126 | SRTI_N1 | 1 | 4825.598 | 8.495 |
| -3.25 | QIAN_RTI | 4342.429 | SRTI_N1 | 1 | 4812.818 | 10.103 |
| -3.00 | QIAN_RTI | 4471.396 | SRTI_N1 | 1 | 4804.123 | 11.643 |

## 4. K slice（gamma0 = -5.0 deg，17 points）

| K | Qian regime | Qian RTI range [km] | Sanger regime | skip | Sanger range [km] | M_S [km] | min M_A [km] |
|---|---|---:|---|---|---:|---:|---:|
| 2.000 | QIAN_RTI | 2501.326 | SRTI_N1 | 1 | 4130.839 | 16.525 | 11.920 |
| 2.125 | QIAN_RTI | 2623.761 | SRTI_N1 | 1 | 4253.648 | 13.763 | 14.772 |
| 2.250 | QIAN_RTI | 2746.610 | SRTI_N1 | 1 | 4369.481 | 11.141 | 17.437 |
| 2.375 | QIAN_RTI | 2869.837 | SRTI_N1 | 1 | 4478.881 | 8.645 | 19.933 |
| 2.500 | QIAN_RTI | 2993.412 | SRTI_N1 | 1 | 4582.344 | 6.267 | 22.275 |
| 2.625 | QIAN_RTI | 3117.307 | SRTI_N1 | 1 | 4680.315 | 3.996 | 24.476 |
| 2.750 | QIAN_RTI | 3241.500 | SRTI_N1 | 1 | 4773.198 | 1.825 | 26.549 |
| 2.875 | QIAN_RTI | 3365.969 | SRTI_N2 | 2 | 6732.580 | 15.765 | **0.251** |
| 3.000 | QIAN_RTI | 3490.698 | SRTI_N2 | 2 | 6872.895 | 13.861 | 2.233 |
| 3.125 | QIAN_RTI | 3615.670 | SRTI_N2 | 2 | 7007.747 | 12.026 | 4.134 |
| 3.250 | QIAN_RTI | 3740.871 | SRTI_N2 | 2 | 7137.129 | 10.255 | 5.960 |
| 3.375 | QIAN_RTI | 3866.287 | SRTI_N2 | 2 | 7261.299 | 8.544 | 7.715 |
| 3.500 | QIAN_RTI | 3991.907 | SRTI_N2 | 2 | 7380.536 | 6.889 | 9.403 |
| 3.625 | QIAN_RTI | 4117.721 | SRTI_N2 | 2 | 7495.109 | 5.288 | 11.028 |
| 3.750 | QIAN_RTI | 4243.718 | SRTI_N2 | 2 | 7605.270 | 3.737 | 12.593 |
| 3.875 | QIAN_RTI | 4369.891 | SRTI_N2 | 2 | 7711.259 | 2.235 | 14.101 |
| 4.000 | QIAN_RTI | 4496.230 | SRTI_N2 | 2 | 7813.299 | **0.777** | 15.556 |

## 5. Qian regime observations

- 主域 D0 内 **33/33 全部 QIAN_RTI**：capture 与 QEG feasibility-loss RTI 在
  所有 pilot 点均正常发生，无 GROUND_BEFORE_CAPTURE /
  GROUND_AFTER_CAPTURE_BEFORE_RTI / CENSORED / NUMERICAL_FAILURE /
  BOUNDARY_AMBIGUOUS。
- Qian exact topology signature 全主域仅 1 种：
  `terminal=RTI;modes=ENTRY_CAPTURE > QEG_GLIDE;events=capture > rti`。
- Qian RTI range 随 gamma0 增大（-7 → -3 deg）单调上升 2717.6 → 4471.4 km；
  随 K 增大（2 → 4）单调上升 2501.3 → 4496.2 km。定性平滑，无异常跳变
  （raw adjacent change 仅作 smoothness diagnostic，**非** derivative）。

## 6. Sanger regime observations

- 主域出现 **2 个物理 regime**：`SRTI_N2`（19 点）与 `SRTI_N1`（14 点）。
- Gamma slice：gamma0 ≤ -4.75 deg → SRTI_N2；gamma0 ≥ -4.50 deg → SRTI_N1。
- K slice：K ≤ 2.75 → SRTI_N1；K ≥ 2.875 → SRTI_N2。
- Sanger exact topology signature 恰 2 种，与 skip count 一一对应（N1 为
  3 段 ATM/VAC/ATM，N2 为 5 段），同 skip count 内无结构异常
  （exact-topology-only 变化数 = 0）。
- Sanger terminal range：N1 侧 ~4800–4900 km（gamma slice）/~4130–4770 km
  （K slice）；N2 侧 ~6850–7030 km（gamma slice）/~6730–7813 km（K slice）。

## 7. Topology-transition hints

| Slice | Interval | Left regime | Right regime | Type |
|---|---|---|---|---|
| gamma0（K=3） | (-4.75, -4.50) deg | SRTI_N2 | SRTI_N1 | compact |
| K（gamma0=-5） | (2.75, 2.875) | SRTI_N1 | SRTI_N2 | compact |

- 两个 transition 均位于主域**内部**，不接触任何边界 → 无需 domain
  expansion。
- 无 exact-topology-only transition（skip count 相同的点内 event sequence
  完全一致）。
- F1 不在 interval 内 refinement —— 留给 F3 做 2D cell refinement。

## 8. Topology margins

- **min M_A observed = 250.9 m**，位于 K = 2.875（SRTI_N2 侧、transition
  边界点）：第二个 VAC apogee 仅高于大气边界 251 m —— 与 F0 §21 的预言
  "baseline 附近 second VAC apogee only modestly above the atmospheric
  boundary" 完全一致，且此处正是 N1/N2 transition 边界。
- **min M_S observed = 777.1 m**，位于 K = 4.0（主域上边界）：
  SRTI 高度 ≈ 99.22 km。M_S 在 K slice 中随 K 单调下降
  （15.8 km @ 2.875 → 0.78 km @ 4.0）—— 若 K 继续增大，terminal pass 可能
  形成新 exit → 预测 **SRTI_N3 可能出现在 K > 4（主域之外）**。这是 F2 的
  K 上边界 domain-edge hint（按 F0 §9，仅在 F2/F3 发现 topology-changing
  cell 接触边界时才扩展）。
- Gamma slice 中 M_S 在 transition 附近跳跃：N2 侧 14.9 km（-4.75）→ N1
  侧 1.5 km（-4.50），与 "M_S → 0 对应 skip-count transition" 的机制一致。
- 所有 atmosphere-exit 的 `dh/dt = v sin(gamma)` 均为正（transversality
  PASS，两 slice 全部 31 个 exit 事件）；SRTI transversality（gamma_dot）
  按 F1 §15 未实现（避免重写 frozen equation），记为 None。

## 9. Numerical / event-health audit

- event times：Qian 与 Sanger 全部严格递增，无 chatter、无重复 root、
  无 zero/negative segment duration（33 点 × 2 模型 audit 全 PASS）。
- 无 NaN / Inf。
- classifier 无未知 terminal kind（全部走 structured mapping）。
- CENSORED：0；NUMERICAL_FAILURE：0；INVALID_INPUT：0；
  BOUNDARY_AMBIGUOUS：0。
- Simultaneous-event caveat（F0.1）：本轮 pilot 未触发
  AMBIGUOUS_SIMULTANEOUS_EVENT；该状态当前仅视为 reserved/advisory
  boundary state，F3 boundary refinement 前需重新审计
  simultaneous-event observability（terminal=True 双重 root 返回能力）。

## 10. Domain adequacy

- D0 = gamma0 ∈ [-7,-3] deg × K ∈ [2,4] 足以 bracket 两个 Sanger
  skip-count transition（均位于内部），Qian 全主域单 regime。
- K 上边界（K = 4.0）处 M_S = 0.78 km 接近 0 —— 记录为 domain-edge
  hint：F2 coarse map 完成后若 topology-changing cell 接触 K 上边界，
  按 F0 §9 条件扩展（K increment 0.5/step，guardrail K ≤ 5.0）。
- 无需为 pilot 扩大 max_time / max_segments（无 censored 点）。

## 11. F1 stop-gate audit

| Gate（F1 §23） | 结果 |
|---|---|
| baseline anchor mismatch | 无（PASS）|
| NUMERICAL_FAILURE | 无 |
| unexpected INVALID_INPUT | 无 |
| CENSORED（5000 s / 50 segments）| 无 |
| event chatter | 无 |
| invalid event ordering | 无 |
| zero/negative segment duration | 无 |
| NaN / Inf | 无 |
| classifier KeyError / unknown kind | 无 |
| BOUNDARY_AMBIGUOUS（真实点）| 无 |

**stop_gate_triggered = False。**

## 12. Decision for F2

**READY_FOR_F2 = YES。**

- F2 17×17 = 289-point deterministic Cartesian coarse map 可安全启动：
  - Qian：预期主域内基本全 QIAN_RTI（一维 slice 未出现任何异常 regime）；
  - Sanger：预期出现 N1/N2 两块区域，边界曲线大致穿过
    (gamma0 ≈ -4.6 deg, K ≈ 2.8) 附近 —— 由 F3 做 2D refinement 精确定位；
  - K 上边界（4.0）附近的 M_S ≈ 0.8 km 需要 F2 重点观察，若 topology
    transition 接触 K 上边界则按 F0 §9 条件扩域。
- F2 必须保持 deterministic Cartesian grid、paired Qian/Sanger 运行、
  compact + exact 双签名记录（F0 §8、§13）。

## 附：执行信息

- 网格：gamma 17 + K 17 = 34 slice positions；unique points = 33；
  Qian integrations = 33；Sanger integrations = 33。
- 数值：PRODUCTION_SOLVER_CONFIG（DOP853, rtol=1e-9,
  atol=[1e-4,1e-11,1e-7,1e-11], max_step=20 s, dense_output=True）；
  Qian max_time = 5000 s；Sanger max_time = 5000 s, max_segments = 50。
- 全部 row 含 provenance（git_commit、phase_e_anchor_tag/commit、
  phase_f_protocol_commit、phase_f_f01_commit、solver config）。
- 未生成 diagnostic plots（F1 §31：数据表优先，plots 非硬性）。

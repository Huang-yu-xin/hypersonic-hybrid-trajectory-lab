# M3-G Calibration Freeze

> **Project:** RareTopo — Stage M3-G (Gain-Aware HOLD Decision)
> **Status:** CALIBRATION FREEZE — sealed; variant & rho immutable; **M3-G scientific sealed runs = 0**
> **Parent frozen tags:** `RareTopo-M3-v0 @ 32b285625494d9b3da08be3c559db3855df77667` 、 `RareTopo-M3-D-v0 @ 7bd58c5992615b8579b1814a3a3fcbea3cda9659` （均验证为 HEAD 祖先，annotated tag 解引用提交哈希与任务文档逐字一致）
> **Task commit:** `9720456` ｜ **Benchmark freeze sha:** `b613f45dc6645c6da26ab58b5185764f14d771ca6b996bffed88fea1f467a5f3`
> **Freeze timestamp:** 2026-08-27 ｜ 机器可读镜像：`M3_G_Calibration_Freeze.json`（self-sha `cdc1304c…`）
> **⚠ FREEZE-AUDIT 增注（2026-08-27 修正轮）:** 本冻结的选择（GA2, 0.0025）基于「评估-M2」操作化分母；exact-proxy 标定重放（预注册原义 pilot M2_hat + 逐 replicate CI）选择了 **GA1-0.02**，封闭策略 9/192 动作分歧 → **Deviation A 实质、非 result-preserving** → **M3-G-v0 = NOT FREEZE READY**。本文件记录的是实际执行过的冻结（描述性有效），不再给出后续科学授权；权威裁决见 `M3_G_Protocol_Deviation_Audit.md`。

---

## 1. 冻结对象

```text
variant = GA2   (conservative signed-gain CI-end rule)
rho     = 0.0025
```

- 该 (variant, rho) 由预注册标定协议选定，**已锁定，不可再调参**（handoff Sec. 9）。
- 在线评估只允许消费 `configs/phase_m3g/m3g_gain_gate_v0.json` 中的锁定值。

## 2. 标定数据防火墙

- 数据源：仅 `results/phase_m3d/layer_a/m3d_layer_a_v1.json`（192 试次完整，schema `raretopo-m3d-layer-a-batch-v0`，基准哈希自校验一致）。
- **`extra_simulator_calls = 0`**（结构测试 monkeypatch 守卫证明：标定路径中任何 pilot 抽取 / 臂评估入口均不可达）。
- 原始数据哈希：layer_a 批次文件 SHA-256 已记录于机器可读冻结 JSON 的 `raw_m3d_source_hashes`。

## 3. 候选定义（操作化登记）

预注册公式（task Sec. 3）：

\[
\widehat{\Delta}_{rel}=\frac{\widehat g\,\Delta\theta}{\widehat M_2}
\qquad(\Delta\theta=\pm0.20\ \text{in the acted direction})
\]

D6 记录模式未持久化 pilot `M2_hat` 与逐 replicate 数组，故按 task「final form locked in configs BEFORE online」条款，在冻结配置中锁定以下**操作化形式**（两阶段完全一致，保证被评估策略 == 被标定策略）：

| 项目 | 锁定形式 | 预注册形式 | 理由 |
|---|---|---|---|
| M2 归一化 | 基准臂评估 M2（n=100k，CRN [seed,900001]，当前协方差点） | pilot M2_hat | 两者估计同一泛函；存储批次仅有臂评估 M2。在线记录一并保存 pilot M2_hat 作诊断，审计量化替代影响 |
| GA1 | act iff \|g_hat·Δθ\|/M2 ≥ ρ | \|Δ_rel\| ≥ ρ | 逐字一致 |
| GA2 | 冻结 g-CI 经符号稳定因子 Δθ/M2 线性传播的上端 ≤ −ρ（WIDEN: g_ci_high·0.20/M2 ≤ −ρ；SHRINK: g_ci_low·(−0.20)/M2 ≤ −ρ） | 逐 replicate (g_r, M2_r) 传播 Δ_rel 的 CI | D6 未存逐 replicate；线性传播为 CI-sign 式保守规则。在线经 `bootstrap_gain_replicates` 可获得真实逐 replicate CI，作为审计诊断 |

## 4. 九个候选完整标定表（192 试次池化）

| 候选 | Acc3 | 均衡精度 | macro-F1 | rW | rS | rH | 动作变更 | HOLD_GAIN | med M2(最终)/M2(base) |
|---|---|---|---|---|---|---|---|---|---|
| GA1-0.0025 | 0.750 | 0.750 | 0.695 | 1.000 | 1.000 | 0.250 | 0 | 0 | 0.9543 |
| GA1-0.005 | 0.750 | 0.750 | 0.695 | 1.000 | 1.000 | 0.250 | 0 | 0 | 0.9543 |
| GA1-0.01 | 0.750 | 0.750 | 0.695 | 1.000 | 1.000 | 0.250 | 0 | 0 | 0.9543 |
| GA1-0.02 | 0.750 | 0.750 | 0.695 | 1.000 | 1.000 | 0.250 | 0 | 0 | 0.9543 |
| GA2-0.0025 | **0.7604** | **0.7604** | 0.712 | 1.000 | 1.000 | **0.28125** | 2 | 2 | 0.9570 |
| GA2-0.005 | 0.7604 | 0.7604 | 0.712 | 1.000 | 1.000 | 0.28125 | 2 | 2 | 0.9570 |
| GA2-0.01 | 0.7604 | 0.7604 | 0.712 | 1.000 | 1.000 | 0.28125 | 2 | 2 | 0.9570 |
| GA2-0.02 | 0.7604 | 0.7604 | 0.712 | 1.000 | 1.000 | 0.28125 | 2 | 2 | 0.9570 |
| baseline M3-D | 0.750 | 0.750 | 0.695 | 1.000 | 1.000 | 0.250 | 0 | 0 | 0.9543 |

逐 state / 逐 class 明细见机器可读冻结 JSON（`per_state_summary` / `per_class_summary`）。

## 5. 选择规则执行（预注册，无事后替换）

```text
合格条件: WIDEN recall >= 0.90 且 SHRINK recall >= 0.90（每类）
合格候选: 8 / 8                                   （全部 GA1×4、GA2×4 均满足）
不合格候选: 0
主准则  : 合格候选内最大化 accuracy (Acc3)
          -> GA2 组 0.7604 > GA1 组 / baseline 0.7500
并列处理: GA2 四档 rho 完全同值 -> 依次 tie-break 均衡精度、macro-F1（均相同）
          -> 更小 rho 优先 -> rho = 0.0025
选定    : (GA2, 0.0025)
```

机制说明：本基准上所有冻结激活决策的相对增益量级远高于 0.02，GA1 全档等于 baseline（零转换）；GA2 恰好转换 2 个过激试次（c004_s2_00250/seed2030、c006_s2_00250/seed2029，均为 HOLD 类状态上的自信 WIDEN，保守 CI 上端 ≈ −0.0011/−0.0014 落入无差异带），HOLD recall 0.25 → 0.28125，W/S recall 保持 1.000。四档 rho 结果相同（无试次的保守端落在 (−0.02, −0.0025) 区间），故 tie-break 定 ρ=0.0025。

## 6. 硬约束与停止规则

- **全部候选满足** W/S recall ≥ 0.90 → 不触发 STOP 分支（Case A 不成立）。
- 之后密封评估按 M3G-0..5 + Strong 门控执行；若 HOLD 恢复不足（预期），按预注册分支 B/C/D 如实报告，不修改任何阈值。

## 7. 冻结后不可变承诺

- 自本 commit 起：`variant=GA2`、`rho=0.0025` 不可变；
- 在线评估仅允许消费 `configs/phase_m3g/m3g_gain_gate_v0.json`；
- 不再进行任何调参 / 再选择；
- M3-G 科学密封运行数保持 0，直至下一步批准。
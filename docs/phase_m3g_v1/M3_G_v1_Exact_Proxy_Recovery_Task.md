# M3-G-v1 Exact-Proxy Recovery — Preregistered Confirmatory Validation Task

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation
> **Method Track:** M3-G-v1 — Exact-Proxy Recovery (confirmatory, scalar, first version)
> **Status:** **PREREGISTERED — CONFIRMATORY VALIDATION NOT STARTED**
> **Frozen scientific parent:** `RareTopo-M3-D-v0 @ 7bd58c5992615b8579b1814a3a3fcbea3cda9659`
> **v0 audit parent:** `feature/phase-m3g-gain-aware-hold` @ HEAD `1a31f8b`（M3-G-v0 = NOT FREEZE READY；本阶段不修改、不标记 v0）
> **Date:** 2026-08-27 ｜ **v1 confirmatory scientific runs = 0**

---

# 0. Scientific Status of M3-G-v0（discovery 属性声明）

M3-G-v0 **NOT FREEZE READY**。原因：Deviation A —— 标定使用了评估臂 M2 而非预注册的 pilot M2_hat，该替代**实质改变策略选择与结论**：

```text
frozen operationalization selected GA2 / rho=0.0025
exact intended proxy        selected GA1 / rho=0.02
9 / 192 final-action divergences（封闭策略 GA2-0.0025）
```

因此旧 24 state × seeds 2026..2033 的**全部结果（M3-D Layer-A、v0 标定、密封批、exact-proxy 重放）均为 DISCOVERY / AUDIT DATA**。其中观察到的：

```text
GA1 / rho=0.02 → Acc3 = 1.0, HOLD recall = 1.0（exact-proxy 重放，in-sample）
```

**不得报告为确认性成功**；它只是 v1 要检验的候选（由审计发现，来自既定发现数据；无新模型选择）。

# 1. v1 核心确认性问题

> **审计发现的精确一阶增益门 GA1 / rho=0.02（pilot M2_hat 分母）能否在未见过的 Monte-Carlo / pilot 试次上复现 HOLD 恢复，同时完整保持冻结的 WIDEN/SHRINK 方向控制器？**

不进行任何新模型选择（无标定网格、无 GA2、无交替 rho、无事后调参）。

# 2. 冻结候选（不可变）

```text
variant      = GA1
rho          = 0.02
delta_theta  = 0.20
denominator  = pilot M2_hat（冻结估计器管道内 mass/n，20k pilot）
```

候选在观察确认性结果前已经固定；此后任何阈值/种子/基准/变体变更均为违规。

# 3. 精确代理定义（当初意图）

\[
\widehat{\Delta}_{rel}
=
\left|
\frac{\widehat g\,\Delta\theta}{\widehat M_{2,\mathrm{pilot}}}
\right|
\qquad(\Delta\theta=+0.20\ \text{WIDEN},\ -0.20\ \text{SHRINK})
\]

决策（优先级自上而下，方向层逐字复用冻结 M3-D）：

```text
if frozen direction == HOLD_LOW_ESS : HOLD_LOW_ESS（原样保留）
elif frozen direction == HOLD_UNCERTAIN : HOLD_UNCERTAIN（原样保留）
elif Delta_rel_hat < 0.02 : HOLD_GAIN
else : EXECUTE frozen WIDEN / SHRINK
```

禁止：符号翻转；在线门中使用评估臂 M2；对方向层的任何重算/重释。

# 4. 冻结方向控制器（逐字复用）

```text
ESS_grad < 20  -> HOLD_LOW_ESS
CI upper < 0   -> WIDEN
CI lower > 0   -> SHRINK
otherwise      -> HOLD_UNCERTAIN
```

奇偶要求：对同一 pilot/state，v1 门前的方向记录 == 冻结 M3-D 方向记录（在线运行时逐位断言）。

# 5. Discovery / Confirmatory 防火墙

discovery-only（可用于机制描述、实现奇偶、回归测试；**不得**用于头条确认性指标、阈值/候选选择、门调参）：

```text
24 sealed M3-D states
seeds 2026..2033
all M3-G-v0 calibration results
all exact-proxy replay results
all audit-derived GA1-0.02 results
```

# 6. 确认性基准与泛化边界

复用同一冻结 24 proposal states（`RareTopo-M3-D-v0`，基准哈希 `b613f45d…`，零改动）。

```text
v1 headline = out-of-sample over Monte-Carlo / pilot randomness
NOT out-of-sample over proposal states / event geometries
```

此限制必须在报告中明确披露；也**不得**声称跨配置泛化。

# 7. 确认种子集（冻结于任何 v1 科学运行之前）

```text
confirmatory_seeds = [3031, 3032, 3033, 3034, 3035, 3036, 3037, 3038]
```

- 8 个种子；与 discovery seeds 2026..2033 **零重叠**；
- 提交于科学评估之前（`configs/phase_m3g_v1/m3g_v1_confirmatory_seeds.json`）；
- 观察结果后**禁止种子替换**。

# 8. 协议锁定（与 M3-D / v0 保持）

```text
24 frozen states / pilot_n=20,000 / alpha=0.5 / delta_theta=0.20 / ESS_grad=20
bootstrap 协议（固定分层，[seed,424243]）/ 95% CI 方向规则
final_eval_n=100,000 / eval rng [seed,900001] / CRN / 固定权重 Layer A
legality checker / VRF 定义 / 泄漏分解 / oracle 标签
```

唯一变更：增益门 = GA1 / rho=0.02 / pilot M2_hat 分母。

# 9. 指标

头条：WIDEN recall、SHRINK recall、HOLD recall、3 类 accuracy、balanced accuracy、macro-F1、混淆矩阵。

随报：HOLD_GAIN count / 正确 HOLD_GAIN 比例 / WIDEN 上 false-HOLD 率 / SHRINK 上 false-HOLD 率 / M2(v1)/M2(M3-D) / M2(v1)/M2(best fixed) / M2(v1)/M2(oracle) / VRF_proposal / VRF_budget / mode-wise leakage。均以 (state, seed) 试次单元、逐态 8 新种子中位数、全局 24 态中位数层级报告。

# 10. 门（阈值在此固定；放宽需 amendment）

```text
V1-0 validity : task/config/seeds committed before science；确认种子未见且不相交；
                sealed 24-state benchmark 不变；GA1/rho=0.02 运行前固定；在线门用
                pilot M2_hat；无 eval-M2 泄漏进门；无 oracle 泄漏；方向奇偶测试 PASS；
                全量 pytest PASS；192 试次完整。          FAILURE => STOP
V1-1 direction preservation : WIDEN recall >= 0.90 且 SHRINK recall >= 0.90（硬）
V1-2 hold recovery (PRIMARY) : HOLD recall >= 0.70 且对同批新种子重评的 M3-D baseline
                提升 >= +30 个百分点（两者均需；禁止仅对比旧 2026..2033 基线）
V1-3 balanced action quality : balanced accuracy >= 0.80 且 macro-F1 >= 0.80
V1-4 M2 noninferiority : median M2(v1)/M2(M3D) <= 1.00（优选 <= 0.98 单独报告）
V1-5 adaptive value : median_state[median_seed M2(v1)/M2(BEST FIXED)] <= 0.95
                且 v1 在 >= 16/24 态按 per-state seed median 胜过 best fixed
Strong : median deployable VRF_budget(v1) > 1（仅报告；除非 V1-5 过，否则不构成优越性）
```

解释分支：V1-1..5 全过 → 精确一阶增益门在未见 MC 试次上复现 HOLD 恢复并优于最优固定规则；HOLD 过但 V1-5 败 → 恢复泛化、自适应优越性未获支持；HOLD 恢复失败 → discovery 完美行为未复现，支持转向高阶有限步动作价值模型（M3-Q，不自动启动）。

# 11. 统计单元

```text
trial unit      = (state, seed)
state summary   = median across 8 new seeds
global summary  = median across 24 state summaries
```

同一 24 proposal states 复用 ⇒ 不声称 state-level 泛化。

# 12. 停止规则

```text
prereg 未在科学前提交 / 确认种子与 discovery 重叠 / 基准哈希变化
rho 变化 / GA1 变化 / eval-M2 进入在线门 / oracle 泄漏 / 全量 pytest 失败
=> 立即 STOP
观察结果后：无 rho 重调、无种子替换、无基准替换、无 GA2 救援、无事后阈值搜索
```

# 13. 执行顺序

```text
V0  create branch feature/phase-m3g-v1-exact-proxy
V1  write prereg task + config + unseen seed lock
V2  commit preregistration（任何确认性模拟调用之前）
V3  implementation audit + 13 项测试
V4  full pytest（exit 0）
--- 第一检查点（Sec.30 表；确认性 scientific runs = 0）---
V5  run 24 x 8 unseen-seed confirmatory evaluation（192 试次）
V6  gate / leakage / legality audit（V1-0..V1-5 + Strong）
V7  figures + reports（docs/phase_m3g_v1/）
V8  freeze-readiness decision
```

本文件提交即：v1 预注册锁定；任何确认性模拟调用先前置检查点汇报。

# 14. 单行状态

```text
H3=M1=M1D=M2=M3v0=M3Dv0 frozen；M3-G-v0 = NOT FREEZE READY (audited)
M3-G-v1 = preregistered, candidate GA1/rho=0.02 (pilot M2_hat), discovery-only data
next = commit prereg, then implementation audit + tests, then checkpoint
```
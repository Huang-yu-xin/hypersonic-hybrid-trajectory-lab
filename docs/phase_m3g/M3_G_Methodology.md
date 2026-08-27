# M3-G Methodology — Gain-Aware HOLD Decision

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation
> **Stage:** M3-G (scalar, v0) ｜ **Status:** SEALED EVALUATION COMPLETE — **FREEZE AUDIT: NOT FREEZE READY**（见 `M3_G_Protocol_Deviation_Audit.md`）
> **Parent frozen tags:** `RareTopo-M3-v0 @ 32b2856…` 、 `RareTopo-M3-D-v0 @ 7bd58c5…` （已验证）
> **Task doc:** `M3_G_Gain_Aware_HOLD_Decision_Task.md`（commit `9720456`） ｜ **Calibration freeze:** commit `48fe50b`
> **GATE 口径（修正）:** 权威门 = `9720456` 任务文档 M3G-0..5 + Strong；执行任务中的更严格指标一律称为 **Secondary / Strengthened Audit Criteria**（非原始预注册官方门）

---

## 1. Scientific objective

M3-D 冻结控制器（CI-sign 方向策略）在密封基准上 WIDEN/SHRINK recall 均 1.00，而 HOLD recall 仅 0.25（M3D-2 FAIL）。失败机制正式表述为：

```text
gradient-sign confidence != finite-step action-indifference
```

M3-G 检验的分离命题：**方向估计（冻结，逐字复用）与有限步动作价值（新的增益门预先决策层）是否可分**——即在预测有限步相对增益低于下限时将激活的 WIDEN/SHRINK 折叠为 HOLD_GAIN，是否能在不破坏完美方向性能的前提下恢复 oracle-HOLD 行为。

## 2. 科学防火墙与分层结构

M3-G 只能改变「预测的协方差动作是否被执行」；不得修改方向层任何成分（梯度公式、g_hat、责任、bootstrap、ESS_grad=20、95% CI 符号规则、WIDEN/SHRINK 逻辑、delta_theta=0.20、24 态密封基准、oracle 标签、事件配置、种子、pilot_n、alpha、final_eval_n、VRF 定义、合法性检查器）。

```text
M3-D direction controller (FROZEN, verbatim)
        ↓
WIDEN / SHRINK / HOLD_UNCERTAIN / HOLD_LOW_ESS
        ↓
gain-aware execution gate (GA2, rho=0.0025, LOCKED)
        ↓
EXECUTE frozen direction  |  HOLD_GAIN  |  HOLD_INVALID (legality fold)
```

结构测试（`test_m3g_gain_hold_does_not_flip_direction` 等）证明门绝不重分类方向。

## 3. 增益代理（锁定形式）

预注册一阶形式（theta = log s²）：

\[
\widehat{\Delta}_{rel}=\frac{\widehat g\,\Delta\theta}{\widehat M_2}
\qquad(\Delta\theta=+0.20\ \text{WIDEN},\ -0.20\ \text{SHRINK})
\]

| 变体 | 锁定规则 | 语义 |
|---|---|---|
| GA1 | act iff \|g_hat·Δθ\|/M2 ≥ ρ | 纯幅度 |
| GA2 | act iff 有符号增益 CI 上端 ≤ −ρ；WIDEN: g_ci_high·0.20/M2 ≤ −ρ；SHRINK: g_ci_low·(−0.20)/M2 ≤ −ρ | 保守：整个 CI 越过无差异带（与 CI-sign 同构） |

### 操作化登记（冻结于 `configs/phase_m3g/m3g_gain_gate_v0.json`，两阶段一致）

1. **M2 归一化 = 基准臂评估 M2**（n=100k，CRN [seed,900001]，当前协方差点）。预注册形式为 pilot M2_hat；D6 记录模式未持久化该量。两者估计同一泛函（当前协方差下的方差质量）；标定（存储数据）与在线（臂评估）使用同一归一化，保证被评估策略 == 被标定策略。pilot M2_hat 在每条在线记录中作为诊断保留。
2. **GA2 CI = 冻结 g-CI 经 Δθ/M2 线性传播**。预注册形式为逐 replicate (g_r, M2_r) 传播；D6 未存逐 replicate。事后诊断（`run_m3g_ga2_diagnostic.py`，192 单元重放 pilot+bootstrap，无臂评估）：线性上端 vs 真逐 replicate 上端（bootstrap_gain_replicates，与冻结 CI 位一致）——**决策分歧 0/192**，|gap| 中位数 0.001（P95 0.0146）。操作化对决策层完全忠实。

## 4. 标定协议（离线，零模拟调用）

- 数据：仅 `results/phase_m3d/layer_a/m3d_layer_a_v1.json`（192 试次；schema、基准哈希自校验）。
- 网格：ρ ∈ {0.0025, 0.005, 0.01, 0.02} × {GA1, GA2} + baseline；无额外阈值。
- 硬不变量 `extra_simulator_calls = 0`（monkeypatch 守卫测试 + 模块无抽样入口结构测试）。
- 选择规则（预注册，见冻结文档）：合格 = WIDEN recall ≥ 0.90 且 SHRINK recall ≥ 0.90（池化）；合格内最大化 Acc3；tie-break 均衡精度 → macro-F1 → 更小 ρ → GA1 在前。
- 选择结果：8/8 合格；GA1 全档 ≡ baseline（所有冻结激活决策 \|Δ_rel\| ≫ 0.02）；GA2 转换 2 个过激试次（c004_s2_00250/seed2030、c006_s2_00250/seed2029）→ Acc3 0.750→0.7604，HOLD recall 0.250→0.28125；GA2 四档相同 → tie-break 选 **rho=0.0025**。
- 冻结提交 `48fe50b`（密封评估之前；variant/rho 自此不可变）。

## 5. 密封评估设计（与 M3-D D6 逐字节同构）

- 24 冻结态 × seeds [2026..2033] = 192 配对试次；pilot rng [seed,101]（20k，α=0.5）；臂 CRN eval rng [seed,900001]（100k/臂）；三物理臂 BASE/WIDEN/SHRINK；冻结 g 估计 + 固定分层 bootstrap [seed,424243] + CI 符号规则 + ESS≥20。
- **重放守卫生效**：每条记录先断言冻结 gradient 块（g_hat/g_ci_low/g_ci_high/ESS_grad/action）与存储 M3-D Layer-A 逐位相等——192/192 单元 0 失配。
- 增益门只消费管道内冻结量（g_hat、g-CI、基准臂评估 M2、步协方差合法性），**零额外模拟调用**（各试次 call accounting 与 D6 相同：scientific 320k / deployable 120k）。
- 对照：M3-D baseline（存储行集）、ALWAYS_WIDEN/SHRINK/HOLD、ORACLE_ACTION（离线比较器）。
- 统计层级：not-IID；(state, seed) 配对单元；frame-level 池化分类指标 + 中位数-of-逐-state-逐-seed-中位数；配对 bootstrap n=10,000，种子 [20260827]，用于 Acc3 增量 CI。

## 6. 指标

- 分类：Acc3、各类 recall、macro-F1、均衡精度、混淆矩阵，均附带 vs 冻结 CI 策略的 Δ。
- 动作价值：M2(M3G)/M2(M3D)（池化中位数 + 层级聚合）、R_fixed（同一聚合 vs 三个固定规则）、中位后悔 R_M2 vs oracle。
- 诊断：每类增益代理分布；act-but-indifferent 前后计数；HOLD_GAIN 正确率；false-HOLD 率；W/S 转换份额；标定-在线代理保真度；GA2 传播诊断。
- **口径修正（freeze-audit）**：统计量定位为 in-sample calibrated performance；Acc3 增量区间为 descriptive paired bootstrap interval after policy selection；原报告中「结论对操作化替代稳健」表述因 exact-proxy 重放选择不一致而**撤销**（见 `M3_G_Protocol_Deviation_Audit.md` §4-5）。

## 7. 记录模式

`raretopo-m3g-v0`：M3-D 字段逐字保留（gradient 块位一致）+ 新增 `gain` 块（direction_before_gain / variant / rho / proxy / final_action / gain_hold_reason）、`arms.gate`（门策略映射臂）、`validity`（门字段、双账 call accounting）。

## 8. 产物

```text
docs/phase_m3g/
├── M3_G_Gain_Aware_HOLD_Decision_Task.md     (authoritative prereg, 9720456)
├── M3_G_Calibration_Freeze.md + .json        (48fe50b; sha cdc1304c…)
├── M3_G_Protocol_Deviation_Audit.md          (freeze-audit; NOT FREEZE READY)
├── M3_G_Methodology.md                       (this file)
├── M3_G_Validity_Audit.md                    (Table A authoritative gates)
└── M3_G_Final_Report.md                      (Table A/B + verdict)
configs/phase_m3g/m3g_gain_gate_v0.json       (executed policy LOCK GA2/0.0025)
configs/phase_m3g/m3g_protocol.json
src/hyptraj/m3g/{gain_proxy,gain_gate,metrics,calibration}.py
tests/test_m3g_covariance_pipeline.py         (22 tests)
scripts/run_m3g_{calibration,online,gate_audit,figures,ga2_diagnostic,
                 exact_proxy_replay}.py
results/phase_m3g/{calibration,layer_a,summary}/  (untracked per repo policy)
figures/phase_m3g/m3g1..m3g8.png              (untracked per repo policy)
```
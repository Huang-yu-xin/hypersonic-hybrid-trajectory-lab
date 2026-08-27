# M3-G-v1 Methodology — Exact-Proxy Recovery (Confirmatory)

> **Stage:** M3-G-v1 ｜ **Status:** CONFIRMATORY VALIDATION COMPLETE
> **Prereg:** `M3_G_v1_Exact_Proxy_Recovery_Task.md`（commit `55fb5ec`） ｜ **v0 audit parent:** `1a31f8b`（M3-G-v0 = NOT FREEZE READY，discovery 属性）
> **Candidate:** GA1 / rho=0.02 / delta_theta=0.20 / **pilot M2_hat 分母**（原始意图的精确代理）
> **Seeds:** confirmatory [3031..3038]（与 discovery 2026..2033 零重叠，观察结果前提交）

---

## 1. 目标与设计

v0 freeze-audit 发现：标定使用评估臂 M2 而非预注册的 pilot M2_hat（Deviation A, material），导致冻结选择 GA2/0.0025 ≠ 原义代理选择 GA1/0.02，且 9/192 动作分歧。v1 的确认性问题：

> **审计发现的精确一阶增益门 GA1 / rho=0.02（pilot M2_hat 分母）能否在未见过的 Monte-Carlo / pilot 试次上复现 HOLD 恢复，同时完整保持冻结的 WIDEN/SHRINK 方向控制器？**

设计要点：
- 候选在科学运行前冻结（无标定网格、无 GA2、无交替 rho、无事后调参）。
- 旧 24 态 × 2026..2033 数据仅用于机制描述/实现奇偶/回归测试（discovery 防火墙）；GA1-0.02 的 discovery Acc3=1.0 不是确认性成功。
- 泛化域明确限定：**out-of-sample over Monte-Carlo/pilot randomness only**（复用同一 24 proposal states；不声称 state-level 泛化）。

## 2. 代理与门（精确原义）

\[
\widehat{\Delta}_{rel}=\left|\frac{\widehat g\,\Delta\theta}{\widehat M_{2,\mathrm{pilot}}}\right|
\qquad(\Delta\theta=+0.20\ \text{WIDEN},\ -0.20\ \text{SHRINK})
\]

决策优先级：HOLD_LOW_ESS（原样）→ HOLD_UNCERTAIN（原样）→ Δ_rel < 0.02 → HOLD_GAIN → 否则 EXECUTE 冻结方向。方向层逐字复用冻结 M3-D（ESS≥20、CI 符号规则、95% 固定分层 bootstrap），在线门只接受 pilot M2_hat（签名白名单 + AST 结构测试，评估臂 M2 不可见）。

## 3. 协议（沿用 M3-D / v0 锁定）

pilot 20k/α=0.5（rng [seed,101]）、bootstrap 500（[seed,424243]）、eval 100k（[seed,900001] CRN）、ESS=20、三物理臂 BASE/WIDEN/SHRINK、合法性检查、VRF 定义、双账 call accounting（320k/120k per trial）、oracle 标签同为密封基准。唯一变更为增益门。

## 4. 统计单元与聚合

```text
trial unit = (state, seed)；state summary = median over 8 new seeds；
global summary = median over 24 state summaries
```

分类指标按 192 试次池化；M2 比值同时报告池化中位数与层级聚合中位数（V1-4）与 median_state[median_seed]（V1-5）。

## 5. 门（V1-0..V1-5 + Strong，预注册阈值）

| 门 | 定义 | 判定 |
|---|---|---|
| V1-0 validity | prereg 先于科学；种子未见且不相交；基准不变；GA1/0.02 固定；pilot M2_hat 在线；无 eval-M2/无 oracle 泄漏；方向奇偶 PASS；全量 pytest；192 完整 | **PASS** |
| V1-1 direction | W/S recall ≥ 0.90（硬） | **PASS**（0.9531 / 1.0000） |
| V1-2 hold recovery | HOLD recall ≥ 0.70 且对**同批新种子**的 M3-D baseline 提升 ≥ +30pp | **PASS**（1.0000；+76.56pp） |
| V1-3 balanced | 均衡精度 ≥ 0.80 且 macro-F1 ≥ 0.80 | **PASS**（0.9844 / 0.9844） |
| V1-4 M2 非劣 | 中位 M2(v1)/M2(M3D) ≤ 1.00（优选 0.98） | **PASS（硬）**（1.0000；优选未达） |
| V1-5 adaptive | median_state[median_seed M2(v1)/M2(best fixed)] ≤ 0.95 且 ≥16/24 态 | **FAIL**（1.0000；10/24） |
| Strong | 中位 deployable VRF_budget > 1 | **PASS**（1.0304；仅成本效率） |

## 6. 产物

```text
docs/phase_m3g_v1/
├── M3_G_v1_Exact_Proxy_Recovery_Task.md    (prereg, 55fb5ec)
├── M3_G_v1_Methodology.md                  (this file)
├── M3_G_v1_Validity_Audit.md
└── M3_G_v1_Final_Report.md
configs/phase_m3g_v1/{m3g_v1_protocol, m3g_v1_confirmatory_seeds}.json
src/hyptraj/m3g_v1/{gain_gate, metrics, pipeline}.py
tests/test_m3g_v1_confirmatory.py           (13 tests)
scripts/run_m3g_v1_{online, gate_audit, figures}.py
results/phase_m3g_v1/{layer_a, summary}/    (untracked per repo policy)
figures/phase_m3g_v1/m3g_v1_1..8.png        (untracked per repo policy)
```
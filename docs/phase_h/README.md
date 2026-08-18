# Phase H — Topology-Aware Uncertainty & Risk Propagation

状态：**H0 COMPLETE / ACCEPTED · H0R COMPLETE / ACCEPTED · H1 COMPLETE / ACCEPTED · H2 COMPLETE / READY FOR REVIEW · H3 PENDING**
（2026-08-19；H0/H0R/H1 经人工验收通过，H2 完成非线性 MC 验证与 alpha validity audit，等待人工验收后进入 H3）。

分支：`feature/phase-h-uncertainty-risk`
上游冻结基线：`phase-g-v1.0` = `predictability-v1.0` =
`6fb75c4a5f7b6460a5c9503c99fe2b2b2c96854c`（Phase G 最终冻结 commit）；
Phase F 上游：`phase-f-v1.0` = `gamma-k-sensitivity-v1.0` =
`96253f1ef7785764d8da3156d7d614d2b244b577`。

**Phase-G / Phase-F 全部 frozen tags 未移动、未删除、未重写。**

## 1. Phase H 总目标

当初始状态不再是一个确定点，而是具有有限不确定性的随机变量时，
Qian / Sanger hybrid trajectories 的 **fixed-time state、terminal time、
terminal state 与 hybrid topology** 如何形成概率分布？特别是 Phase-F
B0–B4 grazing boundaries 附近，**continuous uncertainty** 如何与
**discrete skip-count topology transition** 相互作用。

Phase H 的核心连接：

```text
Phase F: hybrid topology / B0-B4 grazing boundaries
        +
Phase G: Phi_H / eta / J / saltation / grazing conditioning / validity radius
        ↓
Phase H: continuous uncertainty + discrete topology uncertainty
```

Phase H **不是**（研究范围安全边界）：interception geometry、survival /
evasion probability、defense penetration、target-hit probability、
weapon effectiveness、engagement optimization、adversarial
interception analysis、robust optimization、control redesign。

## 2. Phase H roadmap（preliminary；后续可按实际结果增加 corrective stages）

| 阶段 | 内容 | 状态 |
|---|---|---|
| **H0** | Uncertainty / Risk Protocol Freeze（random-variable semantics · covariance convention · canonical-A scaling · synthetic family · linear formulas · topology RV · mixture · MC / RNG / CI protocol · grazing validity inheritance · risk taxonomy · claim boundaries · machine-readable schema） | **COMPLETE / ACCEPTED** |
| **H0R** | Frozen-State / Regression Contract Corrective Patch（修正 stale Phase-G0 live-tag absence 测试 → final-freeze manifest lifecycle semantics；`phase_h0_done = true`、`h1_started = false`；机器可读 manifest 仅 lifecycle 字段变更） | **COMPLETE / ACCEPTED** |
| **H1** | fixed-topology linear uncertainty：`P(T) = Phi P0 Phi^T`、terminal-time variance、terminal-state covariance、rank / eigenspectrum（per-alpha response coefficients；linear kernel `K_x = tilde Phi tilde Phi^T`；G5 SVD closure） | **COMPLETE / ACCEPTED** |
| **H2** | nonlinear Monte-Carlo validation（Qian/Sanger baseline T600 + deep fixed-topology Sanger cases；linear covariance vs nonlinear MC；antithetic/CRN；pair bootstrap；1% / 5% alpha validity brackets） | **COMPLETE / READY FOR REVIEW**（Qian 1% ~1e-2 / Sanger 1% ~3e-4；Sanger T600 首个 limiter 为 nonlinear mean shift） |
| **H3** | grazing / topology-transition risk（B0–B4 topology probability、`P(N)` / `P(N+1)`、uncertainty amplitude vs topology transition、linearization breakdown）—— Phase H 核心创新阶段 | PENDING |
| **H4** | topology-conditioned mixture uncertainty（within-topology covariance + between-topology separation；mixture mean/covariance；non-Gaussian output diagnostics） | future |
| **H5** | cross-model common-time uncertainty synthesis（Qian vs Sanger，same T / same input law / same canonical A；不做 optimization） | future |
| **H6** | final synthesis / regression / manifest / freeze / tags | future |

## 3. 文档与代码索引

- `docs/phase_h/h0_uncertainty_risk_protocol.md` —— **H0 权威协议**
  （human-readable source of truth，逐节对应 H0 规范 §0–§67）。
- `src/hyptraj/uncertainty/protocol.py` —— **H0 机器可读唯一真实来源**
  （enums / dataclasses / covariance validation / scaling conversion /
  frozen formula helpers / protocol constants / metadata）。
- `tests/data/phase_h_uncertainty_protocol_v1.json` —— **H0 machine-readable
  protocol manifest**（由 `protocol.machine_readable_protocol()` 生成，
  `schema_version = phase-h-uncertainty-risk-protocol-v1`）。
- `tests/test_uncertainty/test_phase_h0_protocol.py` —— H0 语义测试
  （upstream freeze / state order / scope / covariance / scaling /
  linear & terminal algebra / topology probability semantics / mixture /
  Gaussian semantics / risk boundary / MC protocol / representative
  cases / no-production guard）。
- `docs/phase_h/h1_fixed_topology_linear_uncertainty.md` —— **H1 权威文档**
  （fixed-topology linear uncertainty；per-alpha coefficients；G5 SVD closure）。
- `src/hyptraj/uncertainty/propagation.py` —— **H1 生产模块**
  （fixed-time / terminal linear covariance kernels、spectrum / rank /
  physical marginals；纯线性代数，无 RNG、无 trajectory integration）。
- `scripts/run_phase_h1_linear_uncertainty.py` —— **H1 确定性生成器**
  （读取 frozen G4/G5 artifacts，计算 kernels 与 G5 cross-check，写出
  `tests/data/phase_h1_linear_uncertainty_v1.json`；可重复）。
- `tests/data/phase_h1_linear_uncertainty_v1.json` —— **H1 machine-readable
  snapshot**（`schema_version = phase-h1-linear-uncertainty-v1`）。
- `tests/test_uncertainty/test_phase_h1_linear_uncertainty.py` —— H1 测试
  （kernel / alpha-scaling / SVD / rank / direction / marginals / terminal
  identities + 冻结回归 vs G5）。
- `docs/phase_h/h2_nonlinear_mc_validation.md` —— **H2 权威文档**
  （nonlinear MC validation；antithetic/CRN；sample-matched comparator；
  1% / 5% alpha validity brackets；structural-zero leakage；terminal；
  REF-0.1 subset；deep N0-N5 audit）。
- `src/hyptraj/uncertainty/distributions.py` —— **H2 Gaussian research law**
  （`Z0 ~ N(0, alpha^2 I)` 的 standardized↔physical 变换 + 校验）。
- `src/hyptraj/uncertainty/sampling.py` —— **H2 sampling engine**
  （antithetic master bank、nested prefixes、CRN identity、sample-bank hash；
  无全局 RNG）。
- `src/hyptraj/uncertainty/nonlinear_validation.py` —— **H2 统计模块**
  （sample classification、ensemble stats、sample-matched metrics、
  fixed-time/terminal discrepancies、pair bootstrap、1%/5% classification）。
- `scripts/run_phase_h2_nonlinear_mc.py` —— **H2 确定性生成器**
  （cache 于 `results/phase_h2/cache/`；`--pilot/--primary/--deep/--all`；
  snapshot byte-identical）。
- `tests/data/phase_h2_nonlinear_mc_validation_v1.json` —— **H2 machine-readable
  snapshot**（`schema_version = phase-h2-nonlinear-mc-validation-v1`）。
- `tests/test_uncertainty/test_phase_h2_nonlinear_mc.py` —— H2 测试
  （sampling/statistics + snapshot regression + 极小 live smoke）。
- `src/hyptraj/risk/interception_geometry.py` / `survival.py` —— 保持空占位，
  Phase H 不激活。

## 4. Phase H 继承链

> Phase H consumes frozen Phase-G derivatives. It does not redefine them.

- 状态顺序 `[r, theta, v, gamma]`（G0 §4）；
- canonical scale `A = diag(1e5, 1, 7e3, 0.1)`（G5 冻结；
  `CANONICAL_SCALE_NUMERIC_VALUES_FROZEN`）；
- `Phi_H` / `eta = d t_T/d x_0` / `J = d x_T/d x_0`（G4/G5）；
- G6R2 grazing validity radii（`r_1% ≈ 0.040 Phi_local`、
  `r_5% ≈ 0.185 Phi_local`，仅 tested controlled families）作为
  **local linearization-validity diagnostics**；
- 代表性 case：Qian/Sanger baseline（`gamma0=-5°`, `K=3`）、
  N0–N5 deep controls、B0–B4 10 dual-reference extremal anchors
  —— **全部复用 frozen source，不重新选点**。

## 5. H0 验收要点（详见 `h0_uncertainty_risk_protocol.md` §21–§23）

- **H0 科学协议 ACCEPTED**（人工验收通过）；H0R 修正 lifecycle / regression
  契约后 full pytest **ALL PASS**（0 failed / 0 errors，真实数量见最终报告）；
- 跨阶段回归基线记录（H0G 如实记录，不重写历史）：G7 最终 commit 后的 full
  pytest 在 final tags 创建前通过；Phase-G final tags 合法创建后，仅一个
  G0 stage-local live-tag absence 测试（`test_no_g0_final_tag_created`）
  变 stale——H0R 将该时态测试改为 **historical / final-freeze manifest
  lifecycle 断言**（`test_g0_final_tag_lifecycle_is_historical_not_live_state`，
  不再依赖运行时 git tag 状态）。**Phase-G tag 与任何科学 artifact 均未改变**；
- **`phase_h0_done = true`、`h1_started = false`** 同时成立（machine-readable
  manifest 同步更新，科学字段 bitwise 不变；`alpha` 仍 `PENDING_NUMERICAL_AUDIT`）；
- Phase-G / Phase-F tags 未移动；
- initial-state-only RV scope 冻结；
- `P0` covariance convention（(4,4) finite symmetric PSD）冻结；
- canonical-A covariance normalization 冻结；
- synthetic family `Z0 ~ N(0, alpha^2 R)`、`R=I` canonical 冻结；
- **`alpha` 数值 NOT frozen**（`PENDING_NUMERICAL_AUDIT`）；
- 线性公式冻结：`P(T)=Phi P0 Phi^T`、`sigma_t^2=eta P0 eta^T`、
  `P_T=J P0 J^T`、`Cov(X_T,t_T)=J P0 eta^T`；
- 拓扑随机变量 `Z=T(X0)` 与 `p_topo=P(Z!=Z0)` 定义冻结；
- mixture 语义（`p_k, mu_k, P_k` + law of total covariance）冻结；
- MC RNG / sequential sample-count / Wilson-CI / common-random-numbers /
  nonphysical-sample 规则冻结（**不产生任何生产 sample**）；
- risk taxonomy 冻结（仅统计研究风险）；
- **H1 COMPLETE / ACCEPTED**：固定拓扑线性 covariance 传播已完成
  （per-alpha response coefficients、G5 SVD closure 全部 PASS）；
- **H2 COMPLETE / READY FOR REVIEW**：非线性 MC 验证完成（antithetic/CRN、
  sample-matched comparator、pair bootstrap、REF-0.1 subset、deep N0-N5
  generality）——Qian T600 1% 有效至 ~1e-2、Sanger T600 1% 有效至 ~3e-4；
  **topology probability / P(N) / uncertainty maps 仍未被生产**（H3 未启动）。

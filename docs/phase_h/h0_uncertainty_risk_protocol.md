# H0 — Topology-Aware Uncertainty & Risk Protocol Freeze

> 权威协议（human-readable source of truth）。机器可读唯一真实来源：
> `src/hyptraj/uncertainty/protocol.py`（`machine_readable_protocol()`）与
> `tests/data/phase_h_uncertainty_protocol_v1.json`
> （`schema_version = phase-h-uncertainty-risk-protocol-v1`）。
>
> 原则：**Phase H consumes frozen Phase-G derivatives. It does not redefine them.**

状态：**COMPLETE / READY FOR REVIEW**。等待人工验收；**不得自动进入 H1**。

---

## 0. H0 HARD SCOPE

H0 允许：repository/source audit、uncertainty protocol、probability /
statistics conventions、covariance algebra definitions、topology-risk
taxonomy、sampling reproducibility protocol、Monte-Carlo convergence
protocol、validation policy、dataclasses / enums / protocol metadata、
semantic/unit tests、docs。

H0 禁止：actual Monte Carlo production runs、covariance propagation
production results、topology probability production results、
uncertainty maps、gamma0-K re-scan、optimization、robust optimization、
control redesign、new physical model、new atmosphere model、
new aerodynamic model、new trajectory dynamics、new Phase-G STM /
saltation calculation、new grazing threshold。

## 1. Research-scope safety boundary

Phase H 第一版只研究：model-prediction uncertainty、initial-state
uncertainty propagation、terminal-time uncertainty、terminal-state
uncertainty、hybrid topology-transition probability、linearization
validity、branch-conditioned mixture statistics。

明确不做：interception geometry、survival / evasion probability、
defense penetration、target-hit probability、weapon effectiveness、
engagement optimization、adversarial interception analysis。
（`src/hyptraj/risk/interception_geometry.py` / `survival.py` 保持空占位，
H0 不激活。）

## 2. 随机变量约定（H0 §6–§8）

状态为 `x = [r, theta, v, gamma]^T`。Phase H 第一版研究：

\[
X_0 = \bar x_0 + \delta X_0, \qquad
\mathbb E[\delta X_0] = 0, \qquad
P_0 = \operatorname{Cov}[\delta X_0], \qquad
\boxed{X_0 \sim (\bar x_0, P_0)}
\]

该 notation **不**意味着必须 Gaussian。必须区分 **mean / covariance /
full distribution**：`same covariance != same probability distribution`。

随机化量：`delta r0, delta theta0, delta v0, delta gamma0`。
暂不随机化：`K, mass, CD, reference area, atmospheric density,
scale height, Earth parameters, control law`（Phase-G 当前 derivative
foundation 是 initial-state-only，不偷偷加入无对应 sensitivity 的
parameter uncertainty）。

**Phase-F vs Phase-H 区分**：Phase F 研究参数空间结构敏感性
`d y/d gamma_0`（gamma0-K 域上的 parameter-output response）；Phase H 的
`delta Gamma_0` 是围绕单一 nominal initial state 的随机初始状态分量。
二者数值上对应同一 initial gamma coordinate，但对象不同，**禁止混用**。

## 3. Covariance validity contract（H0 §9）

任何输入 `P0` 必须满足：

- shape `(4,4)`；finite；symmetric；positive semidefinite。
- 数值上允许 roundoff 造成的 **tiny negative eigenvalue**，但必须使用
  明确 numerical tolerance（H0 冻结：`symmetry_rel_tol=1e-8`（相对
  max|entry|），`psd_rel_tol=1e-10`（相对 max eigenvalue），
  `psd_abs_tol=1e-12`）。
- 禁止 silent `abs(eigenvalues)` 或任意修正 covariance。
- materially non-PSD → `INVALID_COVARIANCE`。

实现：`validate_covariance(covariance, ...) -> CovarianceValidationResult`
（含 `valid / status / min_eigenvalue / max_eigenvalue / numerical_rank /
symmetry_residual / reasons`）。

## 4. Scientific coordinate normalization（H0 §10–§11）

Phase-G 冻结的 canonical scale（Candidate A）：

\[
S_A = \operatorname{diag}(10^5,\ 1,\ 7\times10^3,\ 0.1).
\]

Phase H 继续用它定义 dimensionless perturbation 与 covariance：

\[
Z_0 = S_A^{-1}\delta X_0, \qquad
\widetilde P_0 = S_A^{-1}P_0S_A^{-T}, \qquad
\widetilde P(t) = S_A^{-1}P(t)S_A^{-T}.
\]

继承 G5 scaling-geometry caveat：**predictability ranking 依赖 scaling
geometry**，因此 uncertainty comparison 只有在 input distribution /
covariance geometry 明确后才 meaningful。禁止无前提地说
"model A inherently has more uncertainty"。

## 5. Synthetic research uncertainty family（H0 §12–§15）

算法研究用 synthetic family：

\[
Z_0 \sim \mathcal N(0,\alpha^2 R), \qquad
P_0 = S_A(\alpha^2R)S_A^T.
\]

- `alpha` = dimensionless synthetic research uncertainty amplitude；
  **不是** sensor accuracy / manufacturing tolerance / flight dispersion /
  real-world probability calibration。
- `R` = correlation matrix（第一版 canonical：`R=I`，即
  `tilde P_0 = alpha^2 I`）；`R != I` 允许，但 **correlations 是用户 /
  研究输入，不宣称真实物理相关性**。
- **`alpha` 数值 NOT frozen**：状态 `ALPHA_STATUS =
  PENDING_NUMERICAL_AUDIT`，具体 alpha levels 由 H1/H2 pilot convergence /
  validity audit 决定。
- 分布种类区分：`GAUSSIAN` / `BOUNDED_ELLIPSOIDAL` /
  `DETERMINISTIC_SIGMA_POINTS` / `CUSTOM_SAMPLES`。Gaussian assumption
  不是物理定律。

## 6. 线性不确定性公式（H0 §16–§22）

在 topology-preserved fixed-time flow 上（`Phi_H` = Phase-G hybrid STM）：

\[
\delta X(T) \approx \Phi_H(T,0)\,\delta X_0
\qquad\Rightarrow\qquad
\boxed{P(T) \approx \Phi_H P_0 \Phi_H^T}
\]

scaled：

\[
\widetilde P(T) = \widetilde\Phi_H\,\widetilde P_0\,\widetilde\Phi_H^T.
\]

Covariance rank semantics（H0 §17）：若 `Phi_H` rank-deficient（如 Qian
post-Capture `rank Phi = 3`），propagated covariance 也可能 structural
rank-deficient。禁止解释为 "zero physical uncertainty / perfect
robustness"；应解释为 **first-order synchronized map projects one
perturbation direction out of the local image**。未来必须报告
`numerical rank / nullity / nonzero eigenspectrum`，而非只看 `det(P)`。

Fixed-time 描述性指标（H0 §18；DESCRIPTIVE，**不是** probability of
failure）：

\[
\sigma_{\rm RMS} = \sqrt{\operatorname{tr}(\widetilde P)},\qquad
\sigma_{\max} = \sqrt{\lambda_{\max}(\widetilde P)}
\]

+ principal directions（`tilde P` 特征向量）+ numerical rank
（沿用 frozen numerical rank convention，G5 §16）。

Linear-Gaussian interpretation（H0 §22）：若 `delta X0 ~ N(0, P0)` 且
一阶近似有效，则 `delta X(T) ~approx N(0, Phi_H P0 Phi_H^T)`。这是
**LINEAR-GAUSSIAN APPROXIMATION**，不是 nonlinear truth；H2 必须用 full
nonlinear sampling 验证。

## 7. Terminal-time / terminal-state uncertainty（H0 §19–§21）

Phase-G terminal derivatives：`eta_T = d t_T/d x_0`，`J_T = d x_T/d x_0`。

\[
\boxed{\sigma_{t_T}^2 = \eta_T P_0 \eta_T^T},\qquad
\boxed{P_T = J_T P_0 J_T^T},\qquad
\boxed{\operatorname{Cov}(X_T, t_T) = J_T P_0 \eta_T^T}.
\]

适用前提：same terminal branch、same terminal kind、topology preserved。

**Native terminal semantics 继承**：`Qian RTI != Sanger SRTI`。terminal-time
std 可以并排 descriptive，但不能直接解释为 fair performance superiority。
Cross-model probability 比较优先：same fixed elapsed time + same input
probability law + same canonical scaling。

## 8. 拓扑作为随机变量 & 拓扑转移概率（H0 §23–§25）

对每个 nonlinear uncertainty sample 至少分类（`SampleClassification`）：

```text
TOPOLOGY_PRESERVED | TOPOLOGY_CHANGED | EVENT_ORDER_CHANGED |
TERMINAL_KIND_CHANGED | GRAZING_CROSSED | LINEARIZATION_INVALID |
NONPHYSICAL_STATE | NUMERICAL_FAILURE
```

只有 `TOPOLOGY_PRESERVED` 的 sample 才允许直接作为单一 nominal linear
covariance 的 nonlinear validation population（**critical topology gate**，
继承并强化 Phase-G）。

定义 discrete topology variable：

\[
\boxed{Z = \mathcal T(X_0)}, \qquad p_k = P(Z=k), \qquad
\boxed{p_{\rm topo} = P(Z \neq Z_0)}.
\]

`p_k / p_topo` **MUST** 来自显式定义的 input distribution（nonlinear
samples / validated probabilistic approximation）。**不能**由
distance / FTLE / `|n^Tf|` / `Phi_local` 直接声称概率（H0 §45）。
可进一步分 `p_{N->N+1}`、`p_{N->N-1}`，但必须由 nonlinear samples 获得。
H0 不计算实际数值。

## 9. Fixed-topology vs topology-mixture uncertainty（H0 §26–§28）

- **Regime A — fixed topology**：`P(Z=Z0) ≈ 1` 且 linearization
  validation 成立 → 可使用 `P(T) ≈ Phi_H P0 Phi_H^T`。
- **Regime B — topology mixture**：`P(Z != Z0)` materially nonzero →
  单一 covariance 不再完整描述；必须报告 `(p_k, mu_k, P_k)`：
  即 topology probability / conditional mean / conditional covariance。

**Law of total covariance**（H0 §27）：

\[
\mu = \sum_k p_k\mu_k,\qquad
\boxed{P = \sum_k p_k\left[P_k + (\mu_k-\mu)(\mu_k-\mu)^T\right]}.
\]

必须区分 **within-topology covariance** 与 **between-topology
separation** —— 这正是 ordinary covariance propagation 无法表达的部分。

**不混合不兼容 terminal semantics**（H0 §28）：若不同 sample terminal
kinds 不同（`RTI / GROUND_BEFORE_CAPTURE / MAX_TIME` 或 Sanger
`srti / ground / grazing_or_unresolved`），不能把不同 terminal state
塞进一个普通 Gaussian covariance 后声称 "terminal uncertainty"；必须
**conditional-by-terminal-kind** 或使用 common fixed-time endpoint。

## 10. Grazing uncertainty policy & validity 继承（H0 §29–§32）

Phase-G 已冻结 `d = n^T f^- -> 0` 时 standard transverse first-order
conditioning 增长；G6R2（FINAL_AUTHORITY）在 tested controlled
grazing families 上：

\[
r_{1\%} \approx 0.040\,\Phi_{\rm local},\qquad
r_{5\%} \approx 0.185\,\Phi_{\rm local}.
\]

Phase H 把这些作为 **local linearization-validity diagnostics**（`rho_lin`
输入），**绝不是概率阈值**。Uncertainty-to-validity ratio：

\[
\rho_{\rm lin} = \frac{\text{characteristic uncertainty amplitude}}
{\text{validated local linearization radius}},\qquad
\rho_{\rm lin,r} = \frac{\sigma_r}{r_{1\%}}.
\]

不确定性对拓扑裕度比率（G6 actual-anchor directional topology radius
`epsilon_topo,j`）：

\[
\rho_{\rm topo,j} = \frac{\sigma_j}{\epsilon_{\rm topo,j}}.
\]

- `rho << 1`：linear covariance 很可能落在 validated local
  neighborhood；`rho ~ 1`：nonlinear validation essential；
  `rho > 1`：single first-order approximation 不应全局信任。
  这些只是 qualitative protocol classes，H0 不冻结任意数值 cutoff。
- `rho_topo` **不是** topology-change probability；真实概率取决于
  distribution shape / correlation / boundary geometry / nonlinearity。
- 继承 `NO_UNIVERSAL_NUMERIC_GRAZING_THRESHOLD_SUPPORTED`，禁止
  `if |d| < X: topology probability high`。

## 11. Monte-Carlo reproducibility & statistical protocol（H0 §33–§38）

- RNG：必须用 `numpy.random.Generator`（`default_rng`）；禁止 global
  `np.random` implicit state。仓库无统一全局 seed convention，H0 冻结
  **`REPRODUCIBILITY_SEED = 2026`**（仅 reproducibility，非物理参数）。
- Sample-count：禁止直接冻结 `N=10000` 而不给统计依据；未来用
  sequential convergence `{256, 512, 1024, 2048, 4096, ...}` 直到目标量
  稳定；至少监控 sample mean / sample covariance / topology probabilities /
  terminal-time moments。
- Probability CI：对 `hat p = k/N` 至少报告 binomial confidence
  interval，**推荐 Wilson interval 95%**；禁止默认使用 normal
  approximation（尤其 p near 0/1）。实现：`wilson_interval(k, n, z)`。
- Covariance convergence 报告：sample size / mean error / covariance
  matrix error / principal eigenvalue error / principal direction
  alignment（相对 `P_lin`）；structural singular cases 避免
  `det` relative error，优先 nonzero eigenspectrum / rank /
  principal subspace。
- Nonlinear MC validation decomposition（H2）：`xbar_lin`、`P_lin`、
  `hat mu_MC`、`hat P_MC` + mean bias / covariance material relative
  error / principal sigma error / subspace alignment / topology
  preservation fraction。
- **Mean shift policy**：nonzero MC mean bias 不能直接称 sampling
  error；必须区分 finite-sample noise vs nonlinear mean shift
  （`E[X(T)] - x_nominal = O(P_0)`）。
- **Statistical sample reuse**：Qian/Sanger fair paired comparison 建议
  common random numbers（同一 standardized sample 映射到两模型相同
  `delta x_0`）；H0 冻结 `PAIRED_COMMON_RANDOM_NUMBERS = preferred`，
  不生成生产 samples。
- **Deterministic sigma-point checks**：`± principal-axis sigma points`
  （`delta x_i^\pm = ± L e_i`, `L L^T = P0`）在 MC 前作为 deterministic
  sanity check——这不是 Monte Carlo。

## 12. Nonphysical samples & Gaussian tails（H0 §47–§48）

- sampling 与 topology classification 分离：sampling 只生成 `delta x0`；
  propagation/classification 负责传播与分类。sampling code 禁止偷偷
  clip / project / change topology / repair。
- Gaussian support 无界；若 sample 导致 `r <= R_E` / `v <= 0` 等 invalid
  initial state：**不静默 truncate**。选择并明确 protocol：
  A. record `NONPHYSICAL_SAMPLE` probability；或
  B. 显式定义 truncated distribution。第一版优先 A（protocol A），
  除非 amplitude 明显过大。H0 不实现。

## 13. Risk taxonomy（H0 §44）

H0 的 "risk" 只指研究模型中的统计风险：

```text
TOPOLOGY_TRANSITION_RISK | LINEARIZATION_BREAKDOWN_RISK |
TERMINAL_KIND_CHANGE_RISK | STATE_DISPERSION |
TERMINAL_TIME_DISPERSION | NUMERICAL_FAILURE_RATE
```

不要把 "risk" 自动解释成 vehicle survival / interception / mission
success / target effects。

## 14. Statistical error taxonomy（H0 §46）

```text
VALID_FIXED_TOPOLOGY_SAMPLE | TOPOLOGY_CHANGED | EVENT_ORDER_CHANGED |
TERMINAL_KIND_CHANGED | LINEARIZATION_DOMAIN_EXCEEDED | NONPHYSICAL_SAMPLE |
NUMERICAL_FAILURE | INVALID_COVARIANCE | INVALID_DISTRIBUTION |
INSUFFICIENT_MONTE_CARLO_CONVERGENCE
```

与 Phase-G numerical/physics taxonomy 对齐。

## 15. Cross-model fair comparison（H0 §39–§40）

Qian vs Sanger fixed-time uncertainty 比较必须：same nominal initial
state、same elapsed time（默认 **T = 600 s**，沿用 G5）、same physical
`P0` 或 same explicitly declared dimensionless covariance、same
canonical scaling `A`、same sampling law、same sample protocol。

`tilde P0 = alpha^2 I` 是 **research comparison convention**，不是真实
飞行分布。不能比较 `Qian RTI distribution vs Sanger SRTI distribution`
后宣称谁更 robust。

## 16. Representative H cases（H0 §41–§43，全部复用 frozen source）

- **H1/H2 fixed-topology baselines**：Qian `gamma0=-5°, K=3`；Sanger
  `gamma0=-5°, K=3`, `SRTI_N2`；primary fixed-time `T=600 s`。
- **Deep Sanger topology controls**：N0–N5 deep（复用 Phase-F，不重选）。
- **Grazing / topology-risk cases（H3）**：B0–B4 10 dual-reference
  extremal anchors（复用 Phase-F，不重新 boundary refinement）。每个
  branch 至少研究 N-side / N+1-side 两个 anchor，然后逐步增加
  dimensionless uncertainty amplitude；核心观察 `P(N)`、`P(N+1)`；
  必要时记录 `N-1 / N+2 / failure`，不得预设只有两个 topology。
- **Adaptive uncertainty amplitude**：靠近 grazing boundary 时固定绝对
  sigma 不科学；未来 amplitude 应与 topology margin / linearization
  radius / canonical scaling 共同审计。原则：**uncertainty amplitude
  must be reported relative to both the canonical state scale and the
  local topology/linearization margin**，H0 不给具体 alpha。

## 17. Claim boundaries（H0 §59）

文档明确禁止：`FTLE = probability`；`sigma_max = risk probability`；
`distance to grazing = topology-change probability`；`covariance alone =
complete hybrid uncertainty`；`Gaussian output assumption across
topology change`；`native RTI/SRTI uncertainty = fair cross-model
comparison`；`small variance = robust`；`large variance = unsafe`；
`MC sample fraction without CI = certified probability`；`synthetic
uncertainty = real-world calibrated uncertainty`。

## 18. Scientific language（H0 §60）

允许：
> Under fixed topology and sufficiently local uncertainty, the Phase-G
> hybrid STM provides a first-order covariance propagation model.

允许：
> Near a grazing topology boundary, a single Gaussian covariance may be
> insufficient because the nonlinear output distribution can become
> topology-conditioned or multimodal.

允许：
> Topology-transition probability is defined only relative to an explicit
> input probability law.

## 19. Frozen physics policy（H0 §61）

H0 不修改 `src/hyptraj/models/` `modes/` `simulation/` `controls/`
`predictability/`。Phase-G predictability 整个 scientific layer：
**READ ONLY**。若 H0 发现 Phase-G bug → **STOP, REPORT UPSTREAM PHASE-G
FREEZE BLOCKER**，不得直接修 frozen source。

## 20. H0 files & tests（H0 §63, §65）

- 新增：`docs/phase_h/README.md`、`docs/phase_h/h0_uncertainty_risk_protocol.md`、
  `src/hyptraj/uncertainty/protocol.py`、`tests/test_uncertainty/__init__.py`、
  `tests/test_uncertainty/test_phase_h0_protocol.py`、
  `tests/data/phase_h_uncertainty_protocol_v1.json`。
- 修改：`src/hyptraj/uncertainty/__init__.py`（light re-export）。
- `distributions.py / propagation.py / sampling.py` 保持空占位。
- **NO OTHER FILES**（root README 不更新）。

H0 semantic tests 覆盖：upstream freeze（不依赖 git runtime）、state
order、initial-state-only scope、covariance validation（symmetric PSD /
correlated PSD / rank-deficient PSD / nonsymmetric / materially negative
eigenvalue / NaN / Inf / wrong shape）、scaling round trip、covariance
propagation algebra（synthetic matrix）、terminal algebra、topology
probability semantics、mixture law、Gaussian semantics、risk boundary、
MC protocol、representative cases、no-production guard。

## 21. H0 acceptance matrix（H0 §64）

逐项检查（详见 final report）：

| 项目 | 状态 |
|---|---|
| branch 精确基于 `phase-g-v1.0` | ✅ |
| Phase-G 回归（基线 808→807 passed + 1 个 pre-existing 时态 tag-check；见 §22） | ✅（如实记录） |
| Phase-G / Phase-F tags 未移动 | ✅ |
| initial-state RV scope 冻结 | ✅ |
| covariance convention 冻结 | ✅ |
| canonical-A normalization 冻结 | ✅ |
| synthetic family 记录 | ✅ |
| 无 arbitrary alpha 冻结 | ✅ |
| fixed-topology formula / terminal formulas 冻结 | ✅（formula-only） |
| topology RV 与转移概率定义 | ✅ |
| mixture semantics 冻结 | ✅ |
| grazing validity 继承冻结 | ✅ |
| MC RNG / sample-count / CI policy 冻结 | ✅ |
| cross-model comparison protocol 冻结 | ✅ |
| risk taxonomy 冻结 | ✅ |
| interception/survival scope excluded | ✅ |
| machine-readable protocol | ✅ |
| semantic tests | ✅（40 passed） |
| full regression | ✅（见 §22） |
| Phase A–G frozen science untouched | ✅ |
| H1 scope leak absent | ✅ |

## 22. Baseline regression note（H0 §4 处理记录）

基线 `pytest -q` 实测为 **`1 failed, 807 passed`**（非规范所述的 808）。

唯一失败：`tests/test_predictability/test_phase_g0_protocol.py::
test_no_g0_final_tag_created`，该 Phase-G0 测试断言 final Phase-G tag
**不存在**（`assert "phase-g-v1.0" not in tags` / `predictability-v1.0`）。
G0 编写时（commit `9db3a35`）该断言成立；Phase G 完成并创建 final
tags 后该测试 inherently stale，与 frozen Phase-G 状态矛盾。最后一次
修改该 test 文件的是 G5 commit `bdc1265`，Phase G 最终冻结未更新它。

处理：
- 该失败是 **pre-existing、repo-state-dependent**（仅取决于本地 git tag
  是否存在），**非 H0 引入的回归**；
- 按 H0 §61 规定，**不修改任何 frozen Phase-G test/source**（修改 frozen
  test 也被 §4 禁止）；也**不删除/移动 Phase-G tags**（§62 禁止）；
- 作为 **upstream Phase-G freeze inconsistency** 在 Deviations 如实记录。
- H0 新增 40 个语义测试全部通过；full regression 在 807+1 基线上 +
  40 = **848 项，其中 847 passed + 1 pre-existing 时态 tag-check**
  （以最终 `pytest -q` 实测数为准）。

## 23. H0 status & next

```text
H1 NOT STARTED
production covariance propagation NOT performed
Monte Carlo NOT performed
topology probability NOT computed
uncertainty maps NOT generated
gamma0-K domain NOT rescanned
optimization NOT performed
robust optimization NOT performed
interception analysis NOT performed
survival/evasion analysis NOT performed
Phase-G tags NOT moved
```

**等待人工验收后再进入 H1。**

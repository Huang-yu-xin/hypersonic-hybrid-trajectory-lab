# H1 — Fixed-Topology Linear Uncertainty Propagation

> 状态：**H1 COMPLETE / READY FOR REVIEW**（2026-08-19；H0/H0R 已 ACCEPTED）。
> machine-readable snapshot：`tests/data/phase_h1_linear_uncertainty_v1.json`
> （`schema_version = phase-h1-linear-uncertainty-v1`）。
>
> 原则：**H1 consumes accepted Phase-G derivatives. H1 does not redefine or repair them.**

---

## 0. Scientific objective

H1 第一次真正把两条已验收链连接起来：

```text
Phase-G frozen derivatives  (Phi_H, eta, J)    +    Phase-H uncertainty geometry (X0, P0)
        ->   linear propagated uncertainty
```

在 **fixed-topology、first-order** 线性模型下：

\[
P(T) = \Phi_H P_0 \Phi_H^T,\qquad
\sigma_{t_T}^2 = \eta_T P_0 \eta_T^T,\qquad
P_T = J_T P_0 J_T^T,\qquad
\operatorname{Cov}(X_T,t_T) = J_T P_0 \eta_T^T.
\]

不研究 nonlinear probability；**不生成任何 random sample**。

## 1. Fixed-topology conditional interpretation（H1 §37）

本阶段没有任何 sample，因此**不得写** `P(topology preserved) = 1`。所有结果
只能表述为：

> linear covariance model **conditioned on the nominal frozen topology**
> (fixed-time flow 与 terminal 均继承 G4/G5 的 accepted topology signature)。

topology preservation probability 的估计属于 H2/H3。

## 2. Canonical input geometry（H1 §8, §10）

继承 H0：

\[
Z_0 = S_A^{-1}\delta X_0 \sim \mathcal N(0,\alpha^2 R),\qquad
S_A = \operatorname{diag}(10^5, 1, 7\times10^3, 0.1),
\]

第一版 canonical：

\[
\boxed{R = I, \qquad \widetilde P_0 = \alpha^2 I}.
\]

## 3. Why alpha stays symbolic（H1 §9, §11）

`alpha` 是 **synthetic dimensionless research amplitude**，
`ALPHA_STATUS = PENDING_NUMERICAL_AUDIT`。H1 是纯一阶模型，**没有资格**回答
"多大 alpha 落在 linear-covariance 有效域内" —— 那是 H2 nonlinear validation
的职责。因此 H1 的全部科学输出一律报告为 **PER-ALPHA RESPONSE COEFFICIENT**
（`sigma_rms/alpha`、`sigma_max/alpha`、`sigma_{x_i}/alpha`、
`sigma_{t_T}/alpha`、`Cov/alpha^2`……），**不冻结任何 alpha 数值**。

## 4. Fixed-time kernel derivation（H1 §10, §16）

\[
\widetilde\Phi_H = S_A^{-1}\Phi_H S_A,\qquad
K_x(T;R) = \frac{\widetilde P(T)}{\alpha^2} = \widetilde\Phi_H R \widetilde\Phi_H^T,
\]

canonical \(R=I\)：

\[
\boxed{K_x(T) = \widetilde\Phi_H \widetilde\Phi_H^T,\qquad
\widetilde P(T) = \alpha^2 K_x(T)}.
\]

**`K_x` 不是 alpha=1 物理不确定性的 covariance**，而是 per-alpha²
normalized covariance-response kernel。

## 5. Per-alpha spread metrics（H1 §12, §13, §18）

\[
\frac{\sigma_{\rm RMS}}{\alpha} = \sqrt{\operatorname{tr}(K_x)},\qquad
\frac{\sigma_{\max}}{\alpha} = \sqrt{\lambda_{\max}(K_x)},\qquad
\frac{\sigma_{x_i}}{\alpha} = s_i\sqrt{(K_x)_{ii}}.
\]

physical margins 单位：[r]=m，[theta]=rad，[v]=m/s，[gamma]=rad，全部为
**per-unit synthetic dimensionless alpha**（不是实际误差条）。

## 6. G5 SVD closure（H1 §14, §15, §22）

因为 \(K_x=\widetilde\Phi\widetilde\Phi^T\)：

\[
\boxed{\sqrt{\lambda_{\max}(K_x)} = \sigma_{\max}(\widetilde\Phi_H) = \sigma_{\max}^{G5}},
\]

且 covariance principal output directions = G5 left singular vectors
（up to sign）。这是 H1 的**强 regression invariant**，全部 3 个 fixed-time
case 均在 ~1e-10 相对误差内闭合（见 §11 表）。

## 7. Qian structural rank-loss covariance interpretation（H1 §16, §17）

Qian T600（post-Capture）：

```text
rank(K_x) = rank(tilde Phi_H) = 3,   nullity = 1
```

**解释**：这是 Qian Capture synchronized first-order map 继承的
**structural projection** —— 一个扰动方向被投影出局部像空间。
禁止解释为 `perfect robustness` / `zero real uncertainty`。
归一化输出 gamma 分量边际系数 ≈ 0 正是该投影的表现。

**numerical rank 约定**：H1 复用 **H0 frozen covariance rank convention**
（`protocol.validate_covariance`：`count(lambda > lambda_max * max(m,n) * eps)`）。
这与 accepted G5 rank 在每个 frozen case 上一致；不使用 map-SVD 阈值是因为
G4/G5 snapshot 将 Phi/J 存储为约 8 位有效数字，会在结构零方向注入 ~1e-9 的
spurious singular value（否则 Qian terminal rank 会被误报为 3）。

## 8. Fixed-time results（snapshot `fixed_time`）

| case | topology | rank/nullity | RMS/α | σmax/α | G5 σmax | closure err | REF-0.1/0.05 |
|---|---|---|---|---|---|---|---|
| **Qian T600** | `qian_capture`（QEG_GLIDE） | 3/1 | 1.793 | **1.608210** | 1.608210 | 2.3e-10 | PASS |
| **Sanger T600** | exit+entry（SANGER_ATM） | 4/0 | 85.878 | **85.871552** | 85.871552 | 3.0e-10 | PASS |
| **Sanger T900**（descriptive stress） | 4 switches（SANGER_ATM） | 4/0 | 22.123 | **22.090592** | 22.090592 | 2.3e-10 | PASS |

physical marginals per alpha：

```text
Qian T600:     sigma_r/a = 3.031e4 m,   sigma_theta/a = 1.266e0 rad,
               sigma_v/a  = 8.635e3 m/s, sigma_gamma/a = 0.0       rad (projected out)
Sanger T600:   sigma_r/a = 2.060e5 m,    sigma_theta/a = 1.220e0 rad,
               sigma_v/a  = 2.813e4 m/s, sigma_gamma/a = 8.575e0  rad
Sanger T900:   sigma_r/a = 1.416e6 m,    sigma_theta/a = 1.521e0 rad,
               sigma_v/a  = 6.490e3 m/s, sigma_gamma/a = 1.690e0  rad
```

Sanger T900 明确标注 `descriptive_stress_case = true`、`fair_cross_model_comparison
= false`（不可与已 RTI 终止的 Qian 做 fair T900 比较）。

## 9. Terminal-state covariance kernel（H1 §26, §29-§31）

\[
\widetilde J_T = S_A^{-1}J_T S_A,\qquad
\bar\eta_T = \eta_T S_A,\qquad
K_T = \widetilde J_T R \widetilde J_T^T,
\]

canonical `R=I`：

\[
\boxed{K_T = \widetilde J_T\widetilde J_T^T,\qquad
\frac{\sigma_{\max,T}}{\alpha} = \sigma_{\max}(\widetilde J_T) = \sigma_{\max}^{G5}},
\]

\[
\boxed{\frac{\sigma_{t_T}}{\alpha} = \sqrt{\bar\eta_T R \bar\eta_T^T}
= \|\eta_T S_A\|_2\quad(R=I)}.
\]

Terminal state-time joint first-order structure（scaled state 无量纲，因此
协方差异恒定单位为秒）：

\[
\boxed{\frac{\operatorname{Cov}(Z_T,t_T)}{\alpha^2}
= \widetilde J_T R \bar\eta_T^T}\qquad\text{(shape (4,)}.
\]

（可选）scaled state-time correlation `rho_{i,t}` = Cov / (sigma_Zi sigma_t)，
alpha 相互抵消；structural-zero 分量记 `null`，不除零。

## 10. Terminal results（snapshot `terminal`，native terminals）

| model | terminal kind | t_T (s) | σt/α (s) | terminal σmax/α | rank/nullity | G5 closures |
|---|---|---|---|---|---|---|
| **Qian** | `RTI` | 723.038 | **1093.302** | **1.915980** | 2/2 | PASS |
| **Sanger** | `srti` | 1119.546 | **3308.568** | **4.851141** | 3/1 | PASS |

reference status：两者均为 G5 `reference_stability.status = PASS`。

## 11. Native-terminal limitation（H1 §21, §35）

```text
Qian RTI != Sanger SRTI
```

`sigma_t/alpha at RTI` vs `sigma_t/alpha at SRTI` 可以**并排描述**，但**不是
fair cross-model performance ranking**。真正公平的 cross-model uncertainty
比较是 fixed-time（T=600、same input law、same scale A）—— 即 §8 的两个
fixed-time 主 case。

## 12. Reference convergence & production audit（H1 §23, §24）

每个 fixed-time case 报告 REF-0.1 vs REF-0.05：

```text
kernel_max_abs_diff / material_rel_diff / sigma_max_diff / sigma_rms_diff
principal_direction_alignment  (> 1 - 1e-9)
rank_01 == rank_05 == rank
reference_stability_status = PASS
```

以及 `production_kernel_error`（phi_production vs accepted phi_ref_01）：
K_x 的 material relative diff ~1e-9，验证 uncertainty propagation 继承了
Phase-G numerical convergence（不是重新调 solver）。

## 13. Mature cross-model interpretation（H1 §36, §64）

允许的核心表述：

> Under the frozen canonical-A isotropic dimensionless input covariance
> geometry, the T=600 branch-conditioned first-order uncertainty response
> of Sanger has a substantially larger largest principal standard-deviation
> coefficient (~85.9/α) than Qian (~1.6/α).

同时必须紧跟：

```text
This is scale/input-geometry dependent.
This is not a topology-transition probability.
This is not a real-world calibrated uncertainty claim.
This is not yet nonlinear Monte-Carlo validated for any finite alpha.
```

## 14. Claim boundaries（H1 §49）

snapshot 冻结：`first_order_only`、`fixed_topology_conditioned`、
`alpha_numeric_not_frozen`、`monte_carlo_not_performed`、
`topology_probability_not_computed`、`no_real_world_calibration`、
`native_terminal_not_fair_cross_model_ranking`、`canonical_A_only_for_primary_result`、
`scaling_sensitivity_inherited` —— 全部 `true`。

## 15. Deviations / provenance notes

- **Qian terminal rank 复现**：G5 把终端 J 存储为约 8 位有效数字；从存储值
  重构的 `tilde J` SVD 第三奇异值升至 ~1e-9，若用 map-SVD 阈值会把 rank 误报
  为 3。H1 改用 **H0 frozen covariance rank convention**（`lambda > lambda_max
  * max(m,n) * eps`），把该量化扰动分类为 `NUMERIC_ZERO`，精确复现 G5
  `rank=2 / nullity=2`（以及 Sanger terminal 3/1）。raw eigenvalues 与
  classification 原样保留在 snapshot。
- terminal `sigma_t/alpha` 与 G5 `scaled_event_time_norm_seconds` 的 closure
  差异 ~1e-5（来源同为 eta 的 ~8 位量化），相对闭合约 1e-8。

## 16. H2 handoff（H1 §62-§63）

H2 的核心手对象是 **linear prediction kernel** 及其 per-alpha coefficients
（不是某个 probability）。H2 将用 nonlinear Monte-Carlo 寻找使
mean / covariance / principal spreads 与 H1 预测一致可接受的 `alpha` 范围，
并监控 topology-preservation fraction。

**H1 不预选 H2 acceptance 阈值**（不冻结 `covariance error < 5%`、
`alpha_valid = ...`）；H2 将结合 MC sampling error、reference convergence、
nonlinear bias、topology preservation 再建立验收准则。

## 17. Scope confirmation

```text
H0/H0R ACCEPTED
H1 COMPLETE / READY FOR REVIEW
H2 NOT STARTED

alpha numeric magnitude NOT frozen
random samples NOT generated
Monte Carlo NOT performed
topology probability NOT computed
B0-B4 stochastic analysis NOT performed
uncertainty maps NOT generated
gamma0-K domain NOT rescanned
optimization NOT performed
robust optimization NOT performed
interception analysis NOT performed
survival/evasion analysis NOT performed
Phase-G tags NOT moved
Phase-F tags NOT moved
no Phase-H final tag created
```

**等待人工验收后再进入 H2。**

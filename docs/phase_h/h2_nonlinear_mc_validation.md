# H2 — Nonlinear Monte-Carlo Validation & Alpha Validity Audit

> 状态：**H2 COMPLETE / SCIENTIFICALLY VALIDATED · H2R COMPLETE / READY FOR REVIEW**
> （2026-08-19；H0/H0R/H1 已 ACCEPTED）。
> machine-readable snapshot：`tests/data/phase_h2_nonlinear_mc_validation_v1.json`
> （`schema_version = phase-h2-nonlinear-mc-validation-v1`，H2R 修正后重新聚合，
> 含 `h2r` corrective provenance 块）。
>
> 原则：**H2 validates H1 against the frozen nonlinear trajectory model.
> It does not modify either H1 linear theory or Phase-G derivatives.**

---

## 0. Scientific objective

H1 得到了 first-order 模型 `tilde P(T) = alpha^2 K_x`、`sigma_t/alpha = ‖η S_A‖₂`、
`K_T = Jb Jb^T`，但没有回答：

> 对有限非零 α，这些 first-order covariance 预测到底还能多准确？

H2 首次用 **full nonlinear ensemble**（frozen Qian / Sanger research
trajectory model）回答这个问题，并给出 **H1 linear uncertainty model 的
nonlinear validity range**。H2 不做 probability-risk map；那是 H3。

## 1. Input probability law（H2 §7）

严格使用 H0 canonical synthetic family：

\[
Z_0 = S_A^{-1}\delta X_0 \sim \mathcal N(0,\alpha^2I),\qquad
\delta X_0 = S_A(\alpha z),\quad z\sim\mathcal N(0,I),\qquad
S_A=\operatorname{diag}(10^5,1,7\times10^3,0.1).
\]

## 2. Antithetic / CRN sampling design（H2 §10-§13）

- RNG：`numpy.random.Generator`（`default_rng`），`REPRODUCIBILITY_SEED = 2026`；
  禁止全局 `np.random` 状态。
- **antithetic master bank**：2048 independent Gaussian base vectors + 镜像，
  行序固定 `z1, -z1, z2, -z2, ...`，因此每个合法嵌套前缀
  `N ∈ {256,512,1024,2048,4096}` 都是完整 antithetic pair，输入均值精确为零。
- **common random numbers**：所有 alpha × Qian/Sanger 共享同一 standardized
  sample IDs（`sample-bank SHA-256` 存入 snapshot，可重建）。
- **bootstrap**：pair resampling（`(z_j,-z_j)` 为不可拆分 unit），`B=1000`，
  `BOOTSTRAP_SEED = 2027`（仅 reproducible）。

## 3. Sample-matched comparator（H2 §19-§21, §40）

对同一 standardized sample：

\[
y_i^{NL} = S_A^{-1}[x_i(T)-x_{nom}(T)],\qquad
y_i^{LIN} = \widetilde\Phi_H u_i,\quad u_i=\alpha z_i.
\]

**NONLINEAR 与 LINEAR 使用完全相同 z_i。** 这使 finite-N Wishart 采样噪声
大幅抵消；analytic H1 `alpha^2 K_x` 仅作 secondary closure（`E_sampling`）。

## 4. Alpha numerical probe grid（H2 §8-§9）

```
alpha ∈ [1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1]     (NUMERICAL PROBES)
```

**不是物理不确定性水平**；`alpha` 仍是 synthetic dimensionless research
amplitude，`ALPHA_STATUS = PENDING_NUMERICAL_AUDIT`。全部结果按
**PER-ALPHA RESPONSE** 解读。

## 5. Fixed-topology / terminal domain gates（H2 §22-§24, §41-§42）

每个 sample 用 H0 `SampleClassification` 分类。若**任意 sample 非
TOPOLOGY_PRESERVED**，该 (model, alpha) 直接标 `DOMAIN_GATE_FAIL`：
**不删除 sample 求 conditioned covariance**（selection bias），仅记录
classification counts。H3 才研究这些 sample 的 topology probability。

## 6. Nonlinear error metrics（H2 §26-§31, §45-§48）

\[
E_\mu=\frac{\|\hat\mu_N-\hat\mu_L\|_2}{\max(\sqrt{\mathrm{tr}\hat P_L},\epsilon)},\quad
E_P=\frac{\|\hat P_N-\hat P_L\|_F}{\max(\|\hat P_L\|_F,\epsilon)},\quad
E_{\sigma_1}=\frac{|\sigma_{1,N}-\sigma_{1,L}|}{\max(\sigma_{1,L},\epsilon)},
\]

\[
E_{H2}=\max(E_\mu,E_P,E_{\sigma_1},E_{\text{marginal,max}},E_{\text{zero,max}}),
\]

principal-direction alignment `A1 = |u1N·u1L|` + angle 作为独立 geometric
diagnostic（不塞进 E_H2）。terminal 另加 terminal-time mean/std 与
state-time cross-cov 指标，复合为 `E_H2_terminal`。

## 7. 1% / 5% numerical-accuracy levels（H2 §32, §36）

`tau ∈ {0.01, 0.05}` 是 **linear-vs-nonlinear approximation-error levels**
（类比 G6R2 的 1%/5% linearization validity），不是物理/风险/任务阈值。
分类用 bootstrap 95% CI：

```text
upper95 <= tau          => PASS
lower95 > tau           => FAIL
CI straddles tau        => UNRESOLVED_MORE_SAMPLES
any domain-gate sample  => DOMAIN_GATE_FAIL   (different mechanism, NOT "5% failure")
```

## 8. Fixed-time results（primary，sequential N 至 4096）

### Qian T600（topology: `qian_capture`, QEG_GLIDE；σmax/α=1.608）

| α | N=4096 E_H2 | 1% | 5% | 说明 |
|---|---|---|---|---|
| 1e-4 | 0.000 | PASS | PASS | 线性锚点 |
| 1e-2 | 0.005 (CI [0.005,0.006]) | **PASS** | PASS | **最大 PASS_1%** |
| 3e-2 | ~0.016 (N≤2048) | FAIL | PASS | N=4096 时域门 fail（far tail 拓扑变化） |
| 1e-1 | — | DOMAIN_GATE_FAIL | DOMAIN_GATE_FAIL | 域门 |

**Qian T600 bracket：`α_1% ∈ [*, 1e-2]`（最大 tested PASS_1% = 1e-2；
first non-PASS_1% = 3e-2）；`α_5% ∈ [*, ~3e-2]`（3e-2 在 N≤2048 PASS_5%，
N=4096 时由 domain gate 限制）**。limiting：**NONLINEAR_MEAN_SHIFT**
（E_mu 主导：0.005@1e-2，0.016@3e-2）。

### Sanger T600（topology: exit+entry；σmax/α=85.87）

| α | N=4096 E_H2 | 1% | 5% | 说明 |
|---|---|---|---|---|
| 1e-4 | 0.002 | PASS | PASS | 线性锚点 |
| 3e-4 | 0.007 (CI [0.007,0.007]) | **PASS** | PASS | **最大 PASS_1%** |
| 1e-3 | 0.032 | FAIL | **PASS** | **最大 PASS_5%** |
| 3e-3 | 0.257 | FAIL | FAIL | 5% 失效 |
| 1e-2 | 1.247 | FAIL | FAIL | 严重偏离 |
| ≥3e-2 | — | DOMAIN_GATE_FAIL | DOMAIN_GATE_FAIL | 域门 |

**Sanger T600 bracket：`α_1% ∈ [*, 3e-4]`；`α_5% = 1e-3`**。

### Cross-model interpretation（H2 §88）

> Under the frozen canonical-A isotropic synthetic input law, the tested
> first-order uncertainty approximation remains accurate over a LARGER
> dimensionless alpha range for Qian (T600) than for Sanger (T600) —
> Sanger departs from first-order prediction much sooner
> (1e-3~3e-3 vs 1e-2-3e-2).

这**不是** "Sanger is less robust"（scale/input-law dependent；不是
topology-transition probability；不是 real-world calibrated claim）。

## 9. Sampling noise vs nonlinear departure（H2 §40, report §G）

sample-matched 设计使结论明显不是 finite-N covariance noise：

- Qian@1e-2：`E_sampling=0.031` vs `E_cov=2.4e-4` —— covariance nonlinear
  departure 比有限样本协方差噪声低 ~100×（Qian covariance 在 1% 界点仍
  本质线性）；`E_H2=0.005` 来自 **E_mu**（sample-matched 的 nonlinear
  mean shift，不受采样噪声污染）。
- Sanger@1e-3：`E_sampling=0.077` vs `E_cov=0.010`（covariance 仍低于采样
  噪声）；`E_H2=0.032` 来自 **E_mu**。
- Sanger@3e-3：`E_H2=0.257`，E_cov 刚越过采样噪声底 → 此时才是真正的
  covariance 非线性偏离。

即：**在这组 synthetic geometry 下，两个模型的第一个 limiter 都是 nonlinear
mean shift（E_mu），其次才是 covariance curvature；Qian 在两个指标上都保持
线性到更大的 α。**

## 10. Qian structural-zero leakage（H2 §30, §53）

Qian T600 的 H1 gamma 输出协方差 = 0（first-order projection out）。H2 实测
gamma 分量的 nonlinear 标准差：

```text
L_gamma(alpha) = sigma_gamma_NL / sigma_RMS_L
alpha=1e-4: ~1.2e-11     alpha=1e-2: ~1.2e-13
```

即 **没有可测的 higher-order leakage**（E_zero_max ≈ 0）。这确认了：
Qian post-Capture 的一阶同步映射把 gamma 方向投影出局部像空间，并且在 tested
α 范围内该方向保持结构性锁定（不是 Phase-G rank 结果错，也不是 "perfect
robustness" 声称）。

## 11. Terminal results（H2 §45-§48；native, DESCRIPTIVE）

### Qian RTI（t_T=723.04 s）

| α | E_H2_terminal | 1% | 5% |
|---|---|---|---|
| 1e-4 | 0.046 (CI[0.044,0.049]) | FAIL | PASS |
| 1e-3 | <0.01 | **PASS** | PASS |
| 3e-3 | <0.01 | **PASS** | PASS |
| 1e-2 | — | UNRESOLVED | PASS |
| 3e-2 | — | FAIL | PASS |
| 1e-1 | — | FAIL | FAIL |

**Qian terminal 5% 有效至 ~3e-2；1% 呈现 non-monotone profile**（1e-4 时受
terminal-state nonlinear mean-shift 小 α 底限制 FAIL，1e-3~3e-3 恢复 PASS，
1e-2 UNRESOLVED）。limiting：**TERMINAL_TIME_NONLINEARITY**。

### Sanger SRTI（t_T=1119.55 s）

| α | 1% | 5% |
|---|---|---|
| 1e-4 | FAIL | PASS |
| 3e-4 | **PASS** | PASS |
| 1e-3 | **PASS** | PASS |
| 3e-3 | FAIL | PASS |
| ≥1e-2 | DOMAIN_GATE_FAIL | DOMAIN_GATE_FAIL |

**Sanger terminal 5% 有效至 ~3e-3；1% 在 3e-4~1e-3 PASS**（同样 non-monotone
小 α 底）。

### Native-terminal warning（H2 §50）

```text
Qian RTI != Sanger SRTI
terminal alpha validity is DESCRIPTIVE,
not a fair native-endpoint cross-model performance ranking.
```

## 12. Fixed-time vs terminal remain separate（H2 §49）

Qian/Sanger 的 T600 与 RTI/SRTI alpha validity **分别报告**（不同 flow-map
对象、不同 horizon、不同 event semantics），不合成单一阈值。

## 13. Reference-solver subset（H2 §51-§52）

对每个 primary model 在最大 accepted α 用 frozen REF-0.1（DOP853, rtol=1e-12,
max_step=0.1）重算 8 antithetic pairs = 16 samples：

| model | α | T600 scaled state diff | terminal-time diff | terminal-state diff | normalized max err | 判定 |
|---|---|---|---|---|---|---|
| Qian | 1e-2 | 4.0e-10 | 1.77e-7 s | 7.0e-10 | **1.77e-7** | PASS (<1e-3) |
| Sanger | 1e-3 | 7.7e-9 | 3.66e-7 s | 7.0e-10 | **3.66e-7** | PASS (<1e-3) |

solver separation 比 1% 科学判据小一个数量级以上 → **观测到的 nonlinear
departure 不是 solver error**（无 H2 NUMERICAL REFERENCE BLOCKER）。

## 14. Deep Sanger N0-N5 generality audit（H2 §55-§60）

- **T_deep = 300 s**（{600,300,120,60} 中最大且满足全部 6 case：
  nominal 轨迹存在、无 research terminal、frozen hybrid-STM API 可构造
  derivative 到 T_deep 的公共值）。
- **alpha_deep = 3e-4**（primary Qian_T600 ∩ Sanger_T600 共同最大 PASS_1%）。
- N = 256，同一 master z bank；线性 reference 用 frozen Phase-G
  hybrid-STM live API 在 T_deep 生成（`H2_LIVE_FROZEN_API_LINEAR_REFERENCE`，
  非新 Phase-G result）。

| case | γ0° | K | 300s 前 switches | mode@T | term_t | gate | E_H2 | 5% |
|---|---|---|---|---|---|---|---|---|
| n0_deep | -1.25 | 1.125 | 0 | ATM | 347.7 | PASS | 1.4e-3 | PASS |
| n1_deep | -4.5 | 2.375 | 1 | VAC | 713.6 | PASS | 9.4e-5 | PASS |
| n2_deep | -8.75 | 2.5 | 1 | VAC | 1130.7 | PASS | 1.2e-4 | PASS |
| n3_deep | -8.25 | 3.5 | 1 | VAC | 1644.8 | PASS | 1.2e-4 | PASS |
| n4_deep | -7.0 | 4.875 | 1 | VAC | 2166.9 | PASS | 1.1e-4 | PASS |
| n5_deep | -8.75 | 4.875 | 1 | VAC | 2590.7 | PASS | 1.2e-4 | PASS |

**DEEP_FIXED_TOPOLOGY_GENERALITY_PASS**。解释（H2 §89）：baseline 派生的
H2 方法论在保守公共 α=3e-4 跨代表 deep topology 内部闭合；**不回答**
"skip count causes X% more risk"（那是 H3/H4）。

## 15. Reproducibility / cache（H2 §66-§68）

- 固定 sample ordering、seed 2026、bootstrap seed 2027、alpha/case/JSON
  ordering → 在 cache 完整时 snapshot **byte-identical**（已复验）。
- sample cache 位于 `results/phase_h2/cache/`，文件名包含 model/case/alpha/
  solver profile，fingerprint 含 sample-bank SHA-256 + solver 配置 + source
  commit → 改 seed/solver/model/alpha/sample-bank 必然 cache miss。
- cache 只是 runtime acceleration，不是 source of truth；支持中断续跑。

## 16. Limitations & H3 handoff

- `alpha` 数值仍未冻结（H1 的 linear kernel + per-alpha coefficients 是传给
  H2 的主对象；H2 的 1%/5% 只是 **numerical approximation accuracy** bracket，
  仍需人工判定是否与 H3 topology-risk 交叉）。
- terminal 1% 的 small-α non-monotone 底表明 native terminal 一阶模型在
  **极小 α** 下也受 terminal 非线性 mean-shift 底限制 —— 与 fixed-time
  行为不同，已如实记录，不做 select-point 解读。
- H3 handoff：topology-transition probability 由 H3 用 B0-B4 研究；
  H2 只给出 observed preservation counts（domain-gate diagnostic），
  **无 topology probability / P(N) estimate**。

## 17. H2R corrective provenance（H2R §36）

### Issue A — fixed-time gate was not fully endpoint-scoped

```text
fixed-time classification previously allowed future terminal semantics
to contaminate endpoint-T validity.
```

旧实现先检查 final terminal kind（grazing / solver failure / ground），再检查
`terminal_time <= T`，因此 `terminal_time > T` 的样本会被未来事件错误拒绝。
H2R 冻结规则（H2R §3）：

> Any event / terminal / numerical outcome strictly after T cannot
> retroactively invalidate an otherwise well-defined fixed-time state
> and topology at T.

### Fix A

```text
all fixed-time classification is endpoint-scoped to [0,T].
```

新判定顺序：① terminal/failure 是否在 `<= T` 已发生（是 → 按 pre-T 事件分类：
`RTI_BEFORE_T` / `SRTI_BEFORE_T` / `GRAZING_BEFORE_T` / `*_BEFORE_T` /
`NUMERICAL_FAILURE`）；② 否则忽略一切 future terminal semantics；③ `state_T`
不可得 → `NUMERICAL_FAILURE` / `NONPHYSICAL_STATE`（不 fabricate state）；
④ 比较 **true-switch signature through T** + mode at T
（`extract_sample_observations` 从 structured event records 读取；
cache-only reaggregation 由 `signature_from_observables` 依 frozen state
machine 确定性重建，两者一致）。相同 signature + 相同 mode →
`TOPOLOGY_PRESERVED`；同数量不同顺序 → `EVENT_ORDER_CHANGED`；数量不同 →
`TOPOLOGY_CHANGED`。snapshot 新增 `classification_detail_counts`（H2R §10）。

### Issue B — terminal composite omitted the cross covariance

```text
state-time cross-covariance mismatch was reported but omitted from the
terminal composite/bootstrap.
```

旧 `E_H2_terminal` 与 terminal pair-bootstrap statistic 的 max-list 不含
`E_cross_rel`。

### Fix B

```text
cross mismatch is now an explicit component of E_H2_terminal and its
pair-bootstrap statistic.
```

`cross_covariance_metrics` 新增 numerical-zero guard：natural scale
`c_scale = sigma_t,L * sqrt(tr(P_z,L))`、materiality
`c_zero = 100*eps*max(c_scale,1e-300)`；`||C_L|| > c_zero` →
RELATIVE（`E_cross_composite = E_cross_rel`），否则 ABSOLUTE_NORMALIZED
（`E_cross_composite = E_cross_absnorm`，`E_cross_rel = null`）。最终
`E_H2_terminal = max(E_t_mu, E_t_sigma, E_mu,T, E_P,T, E_sigma1,T,
E_marginal,T, E_zero,T, E_cross_composite)` —— **`composite_terminal_discrepancy`
为 single source of truth**；generator 与 bootstrap 都只调用它（H2R §16-§17）。

### H2R reaggregation audit（同一 sample bank / seed / alpha grid，cache-only）

- **Fixed-time reclassification**（N=256 pilot）：
  - Qian 0.1：旧 `NONPHYSICAL_STATE:23` → 新 `TOPOLOGY_CHANGED (RTI_BEFORE_T):23`
    （pre-T RTI，非 nonphysical）；gate 仍 DOMAIN_GATE_FAIL。
  - Sanger 0.03：`TOPOLOGY_CHANGED:13` 保持（detail
    `SWITCH_SIGNATURE_CHANGED ['atmosphere_exit']`）—— 13 个是**真实的
    pre-T600 signature change**，DOMAIN_GATE_FAIL 保留（H2R §23）。
  - Sanger 0.1：旧 `NONPHYSICAL:23 + NUMERICAL_FAILURE:8 + CHANGED:76` →
    新 `TOPOLOGY_CHANGED:107`（`SRTI_BEFORE_T:23` + `SWITCH_SIGNATURE_CHANGED:84`）
    —— 23 个 nonphysical 实为 pre-T SRTI；8 个 "failure" 不再计作 fixed-time
    failure（H2R §24）。
- **Primary fixed-time validity brackets：UNCHANGED**（Qian 1% ~1e-2 / 5% ~1e-2；
  Sanger 1% ~3e-4 / 5% ~1e-3）。
- **Terminal composite**：real cases 中 cross 项较小（`E_cross_rel`
  ~1e-6..1e-3，RELATIVE mode），**不改变 E_H2_terminal / brackets
  （UNCHANGED）**—— 但协议现已正确包含 joint 结构。旧 E_H2_terminal 与
  新 E_H2_terminal 逐 cell 相同，1%/5% status 相同。
- **Deep N0-N5：UNCHANGED AFTER ENDPOINT-SCOPE CORRECTION**
  （T_deep=300, alpha_deep=3e-4, N=256；全部 PASS，E_H2 逐位相同）。
- **Sample-bank SHA-256 逐位不变**（`99613cb2…`），alpha grid / seeds /
  nonlinear model 不变（snapshot `h2r` 块记录 `sample_bank_changed=false` 等）。
- Reaggregation determinism：cache 完整时 `--reaggregate-only --write`
  连续两次输出 byte-identical。

## 18. Scope confirmation

```text
H0/H0R ACCEPTED
H1 ACCEPTED
H2 CORRECTED (H2R)
H2R COMPLETE / READY FOR REVIEW

H3 NOT STARTED
B0-B4 stochastic grazing analysis NOT performed
topology probability curve NOT computed
P(N) / P(N+1) NOT estimated
Wilson topology-risk CI NOT produced
mixture uncertainty NOT modeled
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

**等待人工验收后再进入 H3。**

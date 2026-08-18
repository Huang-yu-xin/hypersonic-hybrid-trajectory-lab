# G5 — Finite-Time Predictability Metrics & Terminal Sensitivity

状态：**COMPLETE**（G5 accept，2026-08-18）
分支：`feature/phase-g-predictability`
G5 起点：`01f33a5`（G4R commit）
G0 依据：`docs/phase_g/predictability_protocol.md`（scaling / FTLE 约定）
G4 依据：`docs/phase_g/g4_hybrid_stm.md`（fixed-time hybrid STM）
Machine-readable artifact：`tests/data/phase_g5_predictability_metrics_v1.json`
（schema `phase-g5-predictability-metrics-v1`）

## 1. 科学问题与边界

G5 在 G4 已验证的 fixed-time hybrid STM `Phi_H(T,0)` 上建立 **dimensionless
scientific predictability metrics**（scaled SVD / FTLE / rank / condition /
dominant directions），完成 G0 遗留的 A/B/C scientific scaling audit 并
冻结 Phase-G v1 canonical numeric scale，建立相同 elapsed time 的
Qian–Sanger fixed-time comparison，并给出 Qian RTI 与 Sanger SRTI 的
event-conditioned terminal 敏感性。**不重写 hybrid STM**（复用 G4），
不做 grazing 分析（G6）、Monte Carlo、optimization、gamma0-K rescan、
asymptotic/chaos claims。

## 2. Metrics 定义（G0 §11/§13 + G5 §1）

```
tilde_Phi(T) = S^-1 Phi_H(T,0) S = U Sigma V^T
sigma_max = sigma_1
lambda_max(T) = (1/T) ln(sigma_1)      [1/s]
numerical rank = count(sigma_i > sigma_max * max(m,n) * eps_machine)   # SVD rank tol, 非 grazing
condition_policy: sigma_min 数值零 -> STRUCTURAL_SINGULAR（condition None）
sign convention: 每对 (u_i,v_i) 按 v_i 绝对最大分量翻转（保持 tilde_Phi v_i = sigma_i u_i）
行/列范数：coordinate-wise descriptive（≠ singular-vector worst direction）
unit invariance: 一致物理单位变换下 S_y^-1 Phi_y S_y == S_x^-1 Phi_x S_x
```

## 3. Canonical scientific scaling decision

| candidate | 物理意义 | model-neutral | terminal-neutral | 依赖工程假设 | Qian T600 σ_max | Sanger T600 σ_max | Qian T600 λ | Sanger T600 λ | 排序 | reference 稳定 |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** characteristic trajectory | 共享特征运动尺度 | 是 | 是 | 否 | 1.608 | 85.87 | 7.9e-4 | 7.4e-3 | Sanger 大 | 1e-14 |
| **B** perturbation tolerance | 工程扰动单元 | 是 | 是 | 是 | 22.91 | 19.14 | 5.2e-3 | 4.9e-3 | **Qian 大** | 1e-14 |
| **C** research-domain/terminal-geometry | 域/终端几何 | 部分 | 否 | 部分 | 1.541 | 211.4 | 7.2e-4 | 8.9e-3 | Sanger 大 | 1e-14 |

```
FINAL CANONICAL SCIENTIFIC SCALE = A
status_flag = CANONICAL_SCALE_NUMERIC_VALUES_FROZEN（scaling.py）
```

**选择理由**：A 是共享、terminal-independent、trajectory-characteristic 的
metric geometry，不嵌入 sensor/tolerance 模型；REF-0.1 vs REF-0.05 数值
（σ、λ、v1/u1 alignment=1.0）完全稳定，无 solver instability /
pathological conditioning。**不是为得到偏好排序而选**（A/B/C 下
Qian-vs-Sanger ordering 在 B 下翻转，见 §4）。B/C 保留作 scale-sensitivity /
robustness 汇报。

## 4. Scale sensitivity（$结论是 scale-sensitive$）

**Qian-vs-Sanger σ_max/λ_max ordering at T600 在 A/C 下为 Sanger 大，在 B 下翻转
为 Qian 大**。→ 必须报告：

>  predictab排名 depend on the declared metric geometry；所有 scientific
>  claim 必须指定 canonical scale（A）并给出 A/B/C scale-sensitivity audit。

raw dimensional SVD **只作 ANTI-EXAMPLE 保存，不用于科学 ranking**。

## 5. Fixed-time canonical results（scale A）

| model | T | topology | σ1 | σ2 | σ3 | σ4 | σ_max | λ_max [1/s] | rank | condition | dominant v1 (scaled) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Qian | 60 | () | 2.27 | 1.007 | 0.974 | 0.446 | 2.269 | 0.0137 | 4 | FINITE | [v, r] |
| Qian | 120 | (capture,) | 1.14 | 0.973 | 0.112 | 0.0 | 1.141 | 0.0011 | **3** | **STRUCTURAL_SINGULAR** | [v, θ] |
| Qian | 300 | (capture,) | 1.41 | 0.933 | 0.055 | 0.0 | 1.409 | 0.0011 | 3 | STRUCTURAL_SINGULAR | [v, θ] |
| Qian | 600 | (capture,) | 1.61 | 0.793 | 0.029 | 0.0 | 1.608 | 7.9e-4 | 3 | STRUCTURAL_SINGULAR | [v, θ] |
| Sanger | 60 | () | 2.27 | 1.007 | 0.974 | 0.446 | 2.269 | 0.0137 | 4 | FINITE | [v, r] |
| Sanger | 120 | () | 2.42 | 1.142 | 0.983 | 0.320 | 2.416 | 0.0073 | 4 | FINITE | [γ, v] |
| Sanger | 300 | (exit,) | 4.17 | 1.002 | 0.695 | 0.297 | 4.171 | 0.0048 | 4 | FINITE | [v] |
| Sanger | 600 | (exit,entry) | 85.9 | 1.007 | 0.245 | 0.037 | 85.87 | 0.0074 | 4 | FINITE | [v] |
| Sanger | 900 | (exit,entry,exit,entry) | 22.1 | 1.017 | 0.613 | 0.053 | 22.09 | 0.0034 | 4 | FINITE | [v] |

**关键结构**：Qian 在 Capture 后 rank 降至 3、σ4=0（STRUCTURAL_SINGULAR）——
Capture saltation（diag(1,1,1,0)）把 flight-path-angle normal 方向约束到
QEG manifold，是 event geometry 不是"数值退化/chaos/完美稳定"。Sanger
σ_max 在进入多 switch 后先增后减（T600 峰值 85.9 → T900 22.1），体现
hybrid factor 结构的非光滑演化（§56：`σ_max(T)/rank(T)` 不必是 T 的光滑
函数，禁止称 event-induced jump 为 numerical discontinuity）。

## 6. T600 cross-model comparison（same T, canonical A）

```
Qian σ_max = 1.608, λ = 7.9e-4；Sanger σ_max = 85.87, λ = 7.4e-3
dominant input (A scale): 两边都以 scaled v（速度）为主
```

严格限定解释：

> At T=600 under canonical scale A, Sanger 显示更强 local worst-direction
> finite-time amplification（λ_max Sanger ≈ 9× Qian）。这只是本 metric /
> 本 topology branch 的 local 描述；**不可**宣称 Sanger universally less
> predictable（ranking 在 scale B 下翻转）。

## 7. Reference convergence（REF-0.1 vs REF-0.05）

| endpoint | σ max diff | λ diff | v1 alignment | u1 alignment | status |
|---|---|---|---|---|---|
| Qian T600 | 4.5e-14 | 4.7e-17 | 1.0 | 1.0 | PASS |
| Sanger T600 | 1.0e-9 | 2.0e-14 | 1.0 | 1.0 | PASS |
| Sanger T900 | 1.1e-10 | 5.5e-15 | 1.0 | 1.0 | PASS |

（奇异向量先 canonicalize signs，方向用 `abs(dot)` 报告。）

## 8. Qian RTI terminal sensitivity

```
terminal       RTI（QEG feasibility loss，L_req - L = 0，RESEARCH_TERMINAL）
time/state     t=723.038 / 精确亚稳态（preterminal QEG interior 端）
normal         analytic n_RTI = grad(L_req - L) ≈ [1.075, 0, -6.058, 0]
               （独立 centered-FD oracle 误差 3.2e-9）
denominator    n^T f^- ≈ 16.32（nonzero；无 grazing threshold）
Phi_preterminal = C_QEG(Xi_capture C_ENTRY)（QEG 末段截断到 u_L*<=1-1e-9，
               boundary-o(1e-9)；NO RTI SALTATION）
eta_terminal   = -n^T Phi / (n^T f)；J_terminal = Phi + f eta
tangency n^T J ≈ 2.7e-11
theta: ∂t/∂θ0=0；J[:,θ0]=[0,1,0,0]（exact）
rank = 2, nullity = 2（Capture/QEG constraint + terminal event conditioning；
               未预设，实际计算）
scaled terminal σ_max = 1.916
||eta S||_2 = 1093.3 s；||eta S||_2 / t_RTI = 1.512（descriptive）
terminal-time FD material rel @ REF: 2.1e-8；J max-abs residual 1.6e-4
reference: eta/J/σ REF-0.1 vs 0.05 → PASS
```

## 9. Sanger SRTI terminal sensitivity

```
terminal       SRTI（skip-capability loss，gamma=0, direction -1，RESEARCH_TERMINAL）
normal         [0,0,0,1]^T；denominator = gamma_dot^- = -8.72e-4 < 0（与 direction 一致）
Phi_preterminal = C_final Xi_E2 C_VAC2 Xi_X1 C_ATM2 Xi_E1 C_VAC1 Xi_X0 C_ATM1
              （一切真实 switch；NO SRTI SALTATION）
eta/J/tangency/theta 同结构（theta 列 [0,1,0,0]；SRTI terminal gamma 行 = 0）
rank = 3, nullity = 1（gamma 行结构零）；scaled terminal σ_max = 4.851
||eta S||_2 = 3308.6 s；||eta S||_2 / t_SRTI = 2.955（descriptive）
terminal-time FD material rel @ REF: 1.5e-8；J max-abs residual 7.8e-4
reference → PASS
```

## 10. Native-terminal comparison limitation

```
Qian RTI（QEG feasibility loss） != Sanger SRTI（skip-capability loss）
```

RTI/SRTI 是不同 research terminal；native terminal metrics 是
DESCRIPTIVE（side-by-side **NATIVE TERMINAL DESCRIPTIVE METRICS**，
**NOT A FAIR CROSS-MODEL PERFORMANCE RANKING**）。真正的 cross-model
comparison 走相同 elapsed time（优先 T600，canonical A）。

## 11. 实现的 API

`ftle.py`：`scaled_svd` / `finite_time_metrics` / `canonicalize_svd_signs` /
`numerical_rank` / `condition_status` / `finite_time_lyapunov_exponent`（G0
复用）/ `unit_conversion_scaling_invariance`。
`metrics.py`：`FixedTimePredictabilityResult` / `compute_fixed_time_metrics`。
`terminal_sensitivity.py`：`build_terminal_sensitivity` /
`qian_rti_terminal_normal` / `qian_rti_event_surface_value` /
`srti_terminal_normal` / `terminal_fd_sweep` / `classify_terminal_side` /
`TerminalSensitivityResult`。
`scaling.py`：`CANONICAL_SCALE_NUMERIC_VALUES_FROZEN`（G5 冻结）。

## 12. Claim boundaries

禁止：positive FTLE = chaos；larger FTLE always = worse；smaller σ_max =
universally superior；Qian terminal 直接对 Sanger terminal；rank
deficiency = perfect robustness；condition infinity = instability；
scale A objectively unique；A/B/C 审计证明对任意 norm 不变；dominant
singular vector = causal physical parameter。
允许：dominant singular direction identifies the local worst-amplified
initial-state direction under the declared scaled Euclidean metric。

## 13. G6 handoff

G5 只用 normal baseline/deep topology cases；B0–B4 / 10 grazing anchors /
nTf→0 渐近 / saltation 增长 vs denominator / near-grazing validity radius /
topology-changing epsilon threshold / grazing-adjacent FTLE interpretation
全部留给 G6。G6 不应重复本报告 metric 定义，可在近 grazing 邻域复用
`finite_time_metrics`。

**G5 = COMPLETE；等待人工验收后再进入 G6。**
---

## 14. G5R — corrective patch（terminal contract & RTI trim convergence）

状态：**COMPLETE**（2026-08-18；commit "修正 Phase G5 终端敏感性契约与 RTI 极限验证"）。
G5 科学结果（scaled SVD/FTLE、A/B/C audit、canonical A freeze、fixed-time
Qian/Sanger metrics、T600 comparison、canonical scale、Qian RTI 与 Sanger
SRTI 数值敏感性、native-terminal limitation）全部保留；本轮只补
terminal-sensitivity infrastructure 的 defensive scientific contract 与
RTI trim 的 convergence evidence。

### Terminal eligibility contract（G5R §1-§4）

```
Qian  terminal sensitivity 只在 frozen terminal_kind == "RTI" 时定义
Sanger terminal sensitivity 只在 frozen terminal_kind == "srti" 时定义
```

`build_terminal_sensitivity` 现在先验证实际 frozen terminal kind；不匹配
（GROUND / MAX_TIME / SOLVER_FAILURE / grazing_or_unresolved …）→
`TerminalSensitivityEligibilityError`（不计算 eta / J / terminal-SVD）。
`model` 必须精确为 "qian"/"sanger"，异常字符串 → `ValueError`。只读 frozen
structured metadata，不解析文本。G5 现有数值不变（baseline 均为 RTI/srti）。

### Terminal transversality contract（G5R §5-§8）

标准一阶 terminal event-time 公式要求有限非零 `n^T f^-`。`validate_
terminal_transversality` / `terminal_event_time_gradient` 只拒绝：

```
nonfinite denominator（NaN/inf）-> NonTransverseTerminalError
exact-zero denominator          -> NonTransverseTerminalError
```

**任何 small finite denominator（如 1e-12）不被 threshold 拒绝** ——
G5R **没有冻结任何 grazing / transversality numerical threshold**；near-grazing
validity 属于 G6。

### Qian RTI interior-limit audit（G5R §9-§14）

科学对象为 `Phi^-_RTI = lim_{u_L*->1-} Phi(t,0)`（RTI 是 QEG clipping
boundary，G1 Jacobian 仅定义于严格 interior）。`build_terminal_sensitivity`
计算 `Phi(t_eps,0)`，`u_L*(t_eps) = 1 - u_eps`（keyword-only
`qian_trim_u_eps`，guard `0 < u_eps < 1`）。`qian_rti_trim_audit` 提供
convergence evidence（REF-0.1）：

| u_eps | t_RTI−t_trim [s] | Phi rel vs 1e-9 | eta rel vs 1e-9 | J rel vs 1e-9 | σ_max rel vs 1e-9 |
|---|---|---|---|---|---|
| 1e-6 | 4.95e-4 | 8.6e-7 | 1.8e-6 | 4.0e-7 | 1.5e-7 |
| 1e-7 | 4.95e-5 | 8.5e-8 | 1.8e-7 | 4.0e-8 | 1.4e-8 |
| 1e-8 | 4.95e-6 | 7.7e-9 | 1.6e-8 | 3.6e-9 | 1.3e-9 |
| **1e-9（default）** | 4.95e-7 | 0（基准） | 0 | 0 | 0 |
| 1e-10 | 4.95e-8 | 7.7e-10 | 1.6e-9 | 3.6e-10 | 1.3e-10 |

consecutive-pair `1e-8 vs 1e-9` Phi material rel = **7.7e-9 < reference
budget** → strict-interior-limit 近似在 G5 terminal-sensitivity 误差预算内
**numerically converged**；default `qian_trim_u_eps = 1e-9` 由 audit 支持而
保留。文档措辞：不再声称 "boundary contribution O(1e-9)"，改为
"strict-interior limit evaluated at u_eps=1e-9; trim-sensitivity audit
demonstrates convergence below the G5 numerical error budget"。

Qian terminal FD / Sanger SRTI FD 全部保留（TOPOLOGY_PRESERVED，
terminal-time material rel 1.5e-8–2.1e-8），canonical scale / metrics /
A/B/C audit 不变。

**G5 + G5R = COMPLETE；等人工验收后再进入 G6。**

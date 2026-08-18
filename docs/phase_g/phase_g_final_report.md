# Phase G Final Report — Finite-Time Local Predictability of Hybrid Trajectories

状态：**PHASE G COMPLETE / FROZEN**（2026-08-19）
分支：`feature/phase-g-predictability`
起始最终科学 commit：`d1ac723c6d0cf1ad50b4b679bbc3af8a0d889a45`（G6R2 = 已验收科学链末端）
上游冻结：Phase F `96253f1ef7785764d8da3156d7d614d2b244b577`（`phase-f-v1.0` / `gamma-k-sensitivity-v1.0`）
最终冻结 manifest：`tests/data/phase_g_final_freeze_v1.json`（schema `phase-g-final-freeze-v1`）
机器可读协议：`src/hyptraj/predictability/protocol.py` → `machine_readable_protocol()`
（schema `phase-g-predictability-protocol-v1`）
生成器：`scripts/build_phase_g_final_manifest.py`（README/HASH/SUMMARIZE/FREEZE，确定性）

本报告由 **已冻结的机器可读 artifacts 与已验收 source** 综合而成，不从记忆重建。
所有数值均可追溯到 G1–G6 snapshots（`tests/data/phase_g*_v1.json`）。

---

## 1. Executive summary

Phase G 建立了 frozen Qian 与 Sanger 混合轨迹的 **finite-time local
predictability** 的完整、一致、数值验证建模：从连续变分动力学出发，经
事件局域混合线化、整条轨迹固定时间混合 STM，到科学量纲尺度化 finite-time
指标、原生态终端敏感性与擦掠（grazing）横截性丧失邻域分析。

研究严格限定为：

```
finite-time（固定有限时长）
local（一阶 Taylor derivative，邻域内）
branch-conditioned（frozen representative trajectories / B0–B4 branches）
first-order（st 时刻 STM / saltation / event-time / terminal 一阶）
initial-state-only（δx0 = [δr0, δθ0, δv0, δγ0]）
```

Phase G 覆盖并验证的 derivative 对象：

```
continuous variational dynamics   A_m = ∂f_m/∂x
continuous STM                    Phi(t, t0)
hybrid event-time sensitivity     q_e, eta_k
saltation                         Xi
whole hybrid STM                  Phi_H(T, 0)
scientific scaled metrics         S^-1 Phi_H S  (SVD / FTLE / rank / condition)
terminal sensitivities            (Qian RTI) eta_T, J_T / (Sanger SRTI)
grazing / linearization validity  d = n^T f^- 邻域 conditioning + validity radius
```

四级验证证据全部独立于解析公式：非线性 centered-FD（multi-epsilon）、
production vs REF-0.1 vs REF-0.05 reference 自稳定、semigroup/split
组合一致性、拓扑保持双侧 gate、事件方向/物理性分类。Phase G **不**做
asymptotic chaos、全局稳定性证明、概率不确定性传播、优化、gamma0-K
重扫，不出 universal 物理排名。

## 2. Research question

> 对 frozen Qian 与 Sanger hybrid trajectories，在 initial-state
> perturbation 下，如何建立 mathematically consistent、numerically
> validated 的 finite-time local predictability description？

具体回答：

```
continuous dynamics 如何传播 perturbation？     A_m Φ 变化方程（G1/G2）
hybrid switch 如何改变 derivative？             q_e、Xi（G3）、Phi_H（G4）
fixed-time amplification 如何比较？             S^-1 Phi_H S 的 σ_max / λ_max（G5）
native terminal sensitivity 如何定义？          eta_T / J_T（G5/G5R）
grazing 附近 standard hybrid linearization 为何失效？
                                               d→0：conditioning 增长 + validity 域收缩（G6）
```

## 3. Scope & boundaries

Phase G 回答的是 "**What exactly has Phase G established, under which
mathematical conventions, with what validation evidence, and with what
limitations?**"。G7 不增加任何新科学实验、新参数扫描、新尺度选择、
新 FTLE 端点、新擦掠族、新扰动约定、新阈值、新优化、新 Monte Carlo、
新不确定性、新物理。若 final audit 暴露上游 material scientific
inconsistency，本期为 **FINAL FREEZE BLOCKER**（直接报告，不在 G7 静默
修科学模块）——本期审计未发现。

## 4. Mathematical conventions（G0 冻结）

```
x = [r, θ, v, γ]^T,   h = r - R_E,   R_E = 6 371 000 m
Phi(t, t0) = ∂x(t)/∂x0,   rows = output state, columns = initial perturbation,
              Phi(t0,t0) = I
delta x0 = [δr0, δθ0, δv0, δγ0]^T     （只研究 initial-state perturbation）
不包含：K / vehicle / atmosphere 参数灵敏度（那些是 Phase F 的
        d y / d gamma0, d y / d K —— 与 Phase G 严格区分）
reset：state continuity x+ = x-（DR = I）；vector field 一般 f+ ≠ f-
saltation：Xi = I + (f+ - f-) n^T / (n^T f-)（DR = I）
event-time：δt_e = - (n^T δx^-) / (n^T f^-)
scaled STM：tilde_Phi = S^-1 Phi S；λ_max(T) = (1/T) ln σ_max(tilde_Phi(T))
```

## 5. Continuous variational dynamics（G1）

```
x_dot = f_m(x),   A_m(x) = ∂f_m/∂x,   Phi_dot = A_m Phi
```

验证的 smooth modes + 结构结果：

| mode | 说明 | 关键结构 invariant |
|---|---|---|
| Qian ENTRY_CAPTURE | frozen atmospheric RHS（u_L=1） | theta 列 = 0 exact |
| Qian QEG_GLIDE (strict interior) | 0 < u_L* < 1，γ̇=0 | **行 4 = [0,0,0,0]** |
| Sanger SANGER_ATM | 同一 frozen atmospheric RHS | ENTRY_CAPTURE == SANGER_ATM |
| Sanger SANGER_VAC | L=D=0 | 与 rho/H/K/C_D/S 无关 |

解析 Jacobian 独立 FD 验证（4 modes × 4 real interior samples，
plateau multiplier）：best material relative error `2.4e-11 / 3.0e-9 /
8.4e-11 / 1.7e-11`（entry/qeg/atm/vac），全部 ≪ 1e-6。QEG interior
`γ̇ ≈ 1e-19 rad/s`（FP roundoff only）；QEG clipping boundary
（u_L*=0/1，含 RTI 邻域）不伪造唯一 smooth derivative（`QegBoundaryError`）。
constant-K semantics：`dK/dx = 0` 精确，任意 callable control 拒绝。

## 6. Continuous STM（G2）

20-D augmented variational integrator（DOP853；三层 production /
REF-0.1 / REF-0.05；state 4-atol + Φ 16-psi_atol）。single smooth mode、
fixed elapsed time、initial-state perturbation。验证（每 mode window）：

```
theta symmetry      Phi(:, θ0) = [0,1,0,0]^T   exact residual = 0
QEG gamma row       Phi[γ,:] = [0,0,0,1]        exact residual = 0 （连续 QEG）
semigroup           Phi(t1,t0)=Phi(t1,tm)·Phi(tm,t0)   material rel 1e-12~1e-15
reference self      REF-0.1 vs REF-0.05 Φ: material rel 8.2e-12 / 1.0e-14 /
                    5.4e-12 / 2.9e-15（entry/qeg/atm/vac）→ PASS
nonlinear FD        reference-grade material rel ≪ 1e-5（≈1e-6..1e-8）;
                    plateau 形态（roundoff-plateau → O(h²) truncation）
computational scaling representation invariance I/A/B/C < 1e-6（非科学尺度）
```

G2R 修正 validation gate：centered-FD 双侧 ± gate（任一 invalid →
column rejected）+ `MODE_WINDOW_INVALID` 真正检测（frozen true-switch
surface；diagnostic pullout/apogee 不 invalid）。G2 全部数值逐位不变。

## 7. Hybrid event calculus（G3）

对三个 frozen true hybrid switches：

```
event-time gradient   q_e = d t_e / d x^- = - n^T / (n^T f^-)     (4,)
saltation             Xi = I + (f+ - f-) n^T / (n^T f^-)
determinant lemma     det(Xi) = (n^T f+) / (n^T f-)
```

eligible true switches：

```
qian_capture           ENTRY_CAPTURE -> QEG_GLIDE
sanger_atmosphere_exit   SANGER_ATM   -> SANGER_VAC
sanger_atmosphere_entry  SANGER_VAC   -> SANGER_ATM
```

明确排除（无 saltation / 非物理 root）：

```
qian_rti / sanger_srti          RESEARCH_TERMINAL（terminal projection，非 saltation）
sanger_atmospheric_pullout      DIAGNOSTIC
sanger_vac_apogee               DIAGNOSTIC
synthetic_initial_entry         非物理 root crossing
```

validation event set（baseline 实测，全部 transversal，无 grazing 入选）：

| event | mode | time [s] | \|n^T f^-\| | q-FD material rel | Xi-FD material rel |
|---|---|---|---|---|---|
| Qian Capture | ENTRY→QEG | 93.4288 | 0.00504 | 2.2e-13 | 3.9e-13 |
| Sanger exit X0 | ATM→VAC | 202.964 | 430.99 | 3.1e-10 | 2.9e-11 |
| Sanger entry E1 | VAC→ATM | 484.640 | 430.99 | 5.4e-11 | 2.9e-11 |
| Sanger exit X1 | ATM→VAC | 748.114 | 133.92 | 1.5e-9 | 5.3e-10 |
| Sanger entry E2 | VAC→ATM | 814.802 | 133.92 | 1.4e-9 | 5.3e-10 |

reference 收敛 REF-0.1 vs 0.05 全 PASS；全部 event × 方向 × 双侧
`TRANSVERSE_LOCAL_VALID`。**未冻结任何数值 grazing threshold。**

## 8. Qian Capture — final interpretation

baseline Capture（`g_c = γ`，strict QEG interior `u_L* = 0.0664`）：

```
Xi_Capture = diag(1, 1, 1, 0)      （从一般 saltation formula 计算，非 hard-code）
post-Capture continuous QEG STM gamma row = [0,0,0,1]
post-Capture WHOLE hybrid STM gamma row   = [0,0,0,0]
```

区分（必须明确）：连续 QEG 的 `[0,0,0,1]` vs 含 Capture saltation 的
固定时间混合 STM 的 `[0,0,0,0]`。解释：Capture 的 event-time adjustment
与 QEG manifold constraint 消除了 synchronized hybrid first-order map 中
一个 normal direction。**禁止**：perfect global stability / γ uncertainty
physically disappears / infinite robustness。det=0 不是 grazing/numerical
failure，而是 post-Capture local QEG constraint 的 event-local first-order
结果（后续连续传播由 G4/G5 覆盖）。

## 9. Sanger atmosphere-interface — final interpretation

```
g_h = h - h_atm,   n = e_r
Xi = I + (f+ - f-) n^T / (n^T f-)，  theta/v/gamma 列恒等，仅首列改变
det(Xi) = 1（ordinary transverse switch）
```

`state continuity ≠ derivative continuity`：identity reset 并不意味着
`Xi = I`。v-row 系数 `Δv̇/ṙ > 0`、gamma-row 系数 `Δγ̇/ṙ < 0`（量级小，
因 100 km 处气动力极小）。

## 10. Whole hybrid STM（G4）

```
boxed:  Phi_H(T, t0) = C_{N+1} Xi_N C_N ... Xi_2 C_2 Xi_1 C_1   （顺序锁定）
global event-time sensitivity:  eta_k = q_k Phi_k^-
```

initial discrete mode 固定（Qian `ENTRY_CAPTURE`；Sanger
`synthetic_initial_entry → SANGER_ATM`，t=0 无 saltation）。validated
endpoints（从 snapshot 读取 exact true-switch signatures）：

| endpoint | T [s] | true-switch signature | endpoint mode | terminal margin [s] |
|---|---|---|---|---|
| Qian | 600 | (qian_capture,) | QEG_GLIDE | 123.0（RTI@723.04） |
| Sanger | 600 | (exit, entry) | SANGER_ATM | 519.5（SRTI@1119.55） |
| Sanger | 900 | (exit, entry, exit, entry) | SANGER_ATM | 219.5 |

reference 自稳定（REF-0.1 vs 0.05）Φ material rel：`2.3e-11 / 1.0e-10 /
4.6e-11`。全轨迹 nonlinear FD（ref-grade）：material rel `6.3e-7 /
2.2e-6 / 2.0e-6`，全部 ≪ 1e-5，双侧 `TOPOLOGY_PRESERVED`。结构
invariant：theta 全球列 `[0,1,0,0]` exact；Qian 全球 gamma 行 = 0。

## 11. Hybrid STM nonlinear validation（+Qian negative control）

- reference convergence、whole nonlinear fixed-time FD、
  topology-preserving gate、event-order gate、
  terminal-before-T endpoint-scoped semantics（G4R）、
  computational scaling representation invariant（I/A/B/C，恢复 raw 后
  ~1e-12）。
- **Qian no-saltation negative control**（snapshot 精确字段）：正确
  `C @ Xi_capture @ C` vs FD 误差 = `1.56e-4`（material rel 判据
  ~1e-6 PASS）；naive `C @ I @ C` vs FD 误差 = `8.61e+6`
  （**orders-of-magnitude failure**，比值 ≈ 5.5e10）；correct gamma 行 =
  [0,0,0,0]、naive gamma 行第 4 项 = −3.51（错误）、FD gamma 行 ≈ 0。

> continuous state does not jump at Capture, but the derivative of the
> synchronized hybrid flow map does.  → 必须使用 saltation。

## 12. Scientific scaling（G0 → G5 chain）

```
tilde_Phi = S^-1 Phi_H S
候选 A（characteristic trajectory）；B（perturbation tolerance）；C（research-domain/terminal）
FINAL CANONICAL = A
S_A = diag(10^5 m, 1 rad, 7×10^3 m/s, 0.1 rad)
status = CANONICAL_SCALE_NUMERIC_VALUES_FROZEN
```

### Scale sensitivity（必须保持 prominent）

无法回避的结论：**cross-model worst-direction amplification ranking 是
scale-sensitive 的**。

```
Qian T600: σ_max(A)=1.608, σ_max(B)=22.91, σ_max(C)=1.541
Sanger T600: σ_max(A)=85.87, σ_max(B)=19.14, σ_max(C)=211.4
A/C: Sanger > Qian；B: 翻转（Qian > Sanger）
```

绝对禁止最终结论写 "Sanger is universally less predictable than Qian"。
正确表述：

> At T=600 s under the frozen characteristic trajectory scaling A, Sanger
> exhibits greater local worst-direction finite-time amplification than
> Qian on the studied baseline branches.

（raw dimensional SVD 仅作 ANTI-EXAMPLE 保存，不用于科学 ranking。）

## 13. Fixed-time metrics & final baseline results（canonical A，snapshot-sourced）

```
tilde_Phi = U Σ V^T
σ_max, σ_min, numerical rank, condition status, dominant input/output
λ_max(T) = (1/T) log σ_max
```

| Model | T [s] | true-switch topology | σ_max | λ_max [1/s] | rank | status |
|---|---|---:|---:|---:|---:|---|
| Qian | 60 | () | 2.2691 | 0.013657 | 4 | FINITE |
| Qian | 120 | (capture,) | 1.1414 | 0.001102 | 3 | STRUCTURAL_SINGULAR |
| Qian | 300 | (capture,) | 1.4090 | 0.001143 | 3 | STRUCTURAL_SINGULAR |
| Qian | 600 | (capture,) | 1.6082 | 0.000792 | 3 | STRUCTURAL_SINGULAR |
| Sanger | 60 | () | 2.2691 | 0.013657 | 4 | FINITE |
| Sanger | 120 | () | 2.4156 | 0.007349 | 4 | FINITE |
| Sanger | 300 | (exit,) | 4.1711 | 0.004761 | 4 | FINITE |
| Sanger | 600 | (exit, entry) | 85.8716 | 0.007421 | 4 | FINITE |
| Sanger | 900 | (exit, entry, exit, entry) | 22.0906 | 0.003439 | 4 | FINITE |

结构：Qian 在 Capture 后 rank→3、σ4=0（STRUCTURAL_SINGULAR）——Capture
saltation 把 flight-path-angle normal 方向约束到 QEG manifold（event
geometry，非数值退化/chaos/完美稳定）。Sanger σ_max 多 switch 后先增后减
（T600 峰值 → T900 22.09）。reference 自稳定：σ_max diff
`4.5e-14 / 1.0e-9 / 1.1e-10`（qian/sanger T600/sanger T900），v1/u1
alignment = 1.0 → PASS。

## 14. Correct cross-model interpretation

- **T600 是优先 fair elapsed-time comparison**：same initial baseline
  state、same elapsed time、same canonical scaling A、different frozen
  dynamics。Sanger σ_max(A) ≈ 85.87 vs Qian ≈ 1.608 → λ_max 约 9×。
- RTI/SRTI **不是等效 endpoints**；Sanger T900 不与已终止的 Qian 作
  fair elapsed-time rank。

## 15. Terminal sensitivity（G5/G5R）

对 terminal surface `g_T(x_T)=0`、preterminal `Φ⁻`、normal `n_T`：

```
eta_T = ∂t_T/∂x0 = - n_T^T Φ⁻ / (n_T^T f⁻)
J_T   = Φ⁻ + f⁻ eta_T = (I - f⁻ n_T^T/(n_T^T f⁻)) Φ⁻
tangency:  n_T^T J_T = 0（terminal projection，NOT saltation，NO post-terminal mode）
```

| 量 | Qian RTI | Sanger SRTI |
|---|---|---|
| terminal / time [s] | RTI / 723.038 | srti / 1119.546 |
| normal | [1.0748, 0, −6.0577, ~0]（FD oracle err 3.2e-9） | [0,0,0,1] |
| n^T f⁻ | +16.318 | −8.72e-4 |
| ‖η S_A‖ [s] | 1093.30（/t_RTI = 1.512） | 3308.57（/t_SRTI = 2.955） |
| scaled terminal σ_max | 1.916 | 4.851 |
| rank / nullity | 2 / 2 | 3 / 1 |
| status | STRUCTURAL_SINGULAR | STRUCTURAL_SINGULAR |
| terminal-time FD material rel | ~2.1e-8 | ~1.5e-8 |
| tangency / θ invariant | n^T J ≈ 0；θ 列 [0,1,0,0] | γ 行 = 0 |

Qian RTI 在 QEG active-set boundary（`u_L* → 1⁻` strict-interior limit
构造；G5R trim audit：`u_eps = 1e-6…1e-10` 收敛，consecutive `1e-8 vs
1e-9` Φ relative = 7.7e-9 < numerical budget；default `u_eps=1e-9` 有据）。

## 16. Native-terminal limitation（必须进入 report/manifest/README）

```
Qian RTI（QEG feasibility loss） != Sanger SRTI（skip-capability loss）
native terminal metrics = DESCRIPTIVE
NOT A FAIR CROSS-MODEL PERFORMANCE RANKING
```

## 17. Grazing final synthesis（G6/G6R/G6R2）

Sanger interface `d = n^T f^- = v sin γ → 0`：

```
event-time conditioning   ‖q S_A‖₂ = s_r / |d|
saltation exact identity  |d| ‖S_A^-1 Xi S_A - I‖₂ = s_r ‖S_A^-1 (f+ - f-)‖₂
```

两条为 exact algebraic invariants（机器精度，非 asymptotic）；把
denominator conditioning（1/|d|）与 numerator dynamics 分开。
`exact n^T f^- = 0` 仍定义 GRAZING/NONTRANSVERSE，standard saltation
无定义。

## 18. Phase-F anchor continuity

G6 未创建第二套 boundary map；使用 Phase-F **B0–B4**（10 双参考
extremal anchors）作 source of truth。确认（snapshot
`frozen_anchor_audit` + `g6r.contract_audit`）：

```
10/10 regimes reproduced        10/10 grazing Phi_N signs reproduced
10/10 dual-reference stable     5/5 N-side no new excursion
5/5 N+1-side new excursion exists（含硬拓扑契约：时序/符号/正性/regime 全核对）
```

## 19. Controlled local grazing family

```
x_e(α) = [r_e, θ_e, v_e, α·γ_e]，α ∈ {1, 1/2, …, 1/64}
```

是 **event-state local family**（固定 r_e,θ_e,v_e，α·γ_e 向 tangency 压低）；
**不是** gamma0-K 空间 trajectory-backed；**不 refit** B0–B4。alpha
减半 → d_exit 减半、VAC duration 减半、apogee clearance ≈ /4。

## 20. Quadratic grazing geometry

```
Φ_local ∝ |d_exit|^2     （log-log slope ≈ 2，R² ≈ 1.0；5 branches，n=7）
→ Strong numerical support for smooth local quadratic tangency over the
  tested controlled families.（不是全局解析定理）
```

## 21. Individual vs paired factor

- individual exit saltation ~ 1/|d|；paired excursion

```
P_excursion = Xi_entry C_VAC Xi_exit
```

实测 **pair 不抵消 singular conditioning**，pair norm ~ 1/|d| trend
（H3 slope ≈ −1.0000x，R² ≈ 1.0）。继续区分 operator norm vs realized
cumulative gain。

## 22. Paired nonlinear validation（G6R）

```
B0 strong + B4 mild：full 4-column nonlinear FD closure（four_column_pass=True）
radial derivative plateau：clearance-normalized beta ∈ [1e-4, 3e-2]
max canonical-A scaled-relative error ≈ B0 1.08e-4 / B4 1.09e-4（≪ 1e-2）
⇒ DM_excursion(0) = P_excursion 在 tested transverse near-grazing cases
  得到独立 nonlinear closure。
```

tangent 列用 absolute scaled residual（radial 列 relative）；gamma 列
linear 域受 incidence cone 约束（`|Δγ| < |γ_exit|`；frac ∈ [0.01, 0.5]）。
事件方向/数值失败结构化分类：`WRONG_EXIT_DIRECTION /
WRONG_ENTRY_DIRECTION / NONPHYSICAL_STATE / VAC_EXCURSION_LOST`（topology）
vs `NUMERICAL_FAILURE`（integrator）。

## 23. Final operational validity radius — 权威为 G6R2

```
E_lin = ||S_A^-1 (ΔNL - ΔLIN)||₂ / max(||S_A^-1 ΔLIN||₂, 1e-15)
      = ERROR / LINEAR PREDICTION
r_τ = sup{ β φ : both sides valid 且 E_pair(βφ) ≤ τ }
```

| case | φ [m] | d_exit | r₁%/φ (G6R2) | r₅%/φ (G6R2) | 1% bracket |
|---|---|---|---|---|---|
| B0 a=1 | 0.0480 | 0.479 | **0.03998** | 0.18495 | [0.03, 0.1] |
| B0 a=0.5 | 0.0120 | 0.240 | 0.03997 | 0.18487 | [0.03, 0.1] |
| B3 a=1 | 0.0360 | 0.641 | 0.03947 | 0.18257 | [0.03, 0.1] |
| B4 a=1 | 0.4191 | 2.19 | 0.04034 | 0.18629 | [0.03, 0.1] |

→ 测试集上 `r₁% ≈ 0.040 φ`、`r₅% ≈ 0.185 φ`（**approximately across
the tested controlled families**，非 universal law）；10/10
`MONOTONE_REFINED_RADIUS`、monotone=True。authority chain：

```
G6 coarse 0.03 / 0.10        HISTORICAL（grid lower samples）
G6R ~0.040 / ~0.193          SUPERSEDED（refined but wrong nonlinear-increment normalization）
G6R2 ~0.040 / ~0.185         FINAL_AUTHORITY（protocol ERROR/LINEAR-PREDICTION）
```

## 24. Actual initial-state topology radius（G6）

沿 initial gamma 方向，在 frozen B0–B4 extremal anchors 附近：

```
一侧典型在 ~1e-7–1e-6 rad 量级发生 topology transition
（B0_N1 9.29e-8 … B4_N1 2.01e-6；N 侧一边 1.5e-7–2.4e-6）
另一侧多为 LOWER_BOUND_ONLY 到局部 cap（0.05 rad）
```

→ near Phase-F boundary anchors，initial-state gamma 方向的 topology-
preserving 邻域极窄。**不称** probability of topology change（无
uncertainty distribution）。

## 25. Final grazing threshold decision

```
NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED
```

理由综合：维度化 `|d|` 跨 branch 变化（0.48–2.19 m/s）、无量纲
incidence 不同、initial-state topology radii 不同；operational validity
更宜连续地以 `|n^T f⁻|` / `|sin γ|` / local clearance / validity radius /
topology gate / reference stability 刻画。`exact n^T f⁻ = 0` 仍定义
GRAZING/NONTRANSVERSE（standard saltation undefined）。小有限
denominator 从不自动拒绝。

## 26. Correct grazing interpretation

near-grazing 的 large `q / Xi` 第一解释是：

```
loss of transversality
ill-conditioning of standard transverse first-order linearization
shrinking nonlinear validity domain
```

不能写：infinite physical sensitivity / chaos / global instability。

## 27. Final scientific hierarchy（evidence levels 分层）

**Algebraically exact within frozen model**（严格恒等式）：

```
event-time formula    q_e = -nᵀ/(nᵀf⁻)
saltation formula     Xi = I + (f+-f⁻)nᵀ/(nᵀf⁻)
q scaling identity    ‖q S_A‖ = s_r/|d|
rank-one Xi identity  |d|‖S⁻¹XiS - I‖ = s_r‖S⁻¹(f+-f⁻)‖
matrix-chain convention Phi_H = C_{N+1}Xi_N C_N ... C_1
```

**Numerically validated first-order results**：

```
continuous STM        (G2 FD/semigroup/REF)
whole hybrid STM      (G4 FD/gate/negative control)
terminal eta/J        (G5/G5R native FD)
paired excursion derivative (G6R plateau + 4-column FD)
```

**Empirical local numerical findings**：

```
quadratic tangency slopes（H1 ≈ 2）
paired ~1/|d| trend（H3）
validity-radius proportionality（r₁%≈0.040φ, r₅%≈0.185φ, tested families）
no universal operational scalar threshold
```

三种 evidence level 不混用。

## 28. Claim boundaries

```
Phase G is NOT:
  asymptotic chaos analysis / global stability proof
  probabilistic uncertainty propagation / certified flight-envelope robustness
  optimization / control-policy design
  parameter-output sensitivity replacement for Phase F
  universal physical ranking of Qian vs Sanger
```

## 29. Corrective-history consolidation（provenance 保留，不隐藏）

| stage | issue | final resolution | scientific result changed? |
|---|---|---|---|
| G2R | centered-FD 只 gate 单侧；MODE_WINDOW_INVALID 未实现 | 双侧 ± gate + frozen-surface mode-window 检测 | 数值逐位不变 |
| G4R | endpoint-scoped terminal 分类 / success=False / event multiplicity | 严格 endpoint 语义 + 事件序 gate | 不变 |
| G5R | terminal-kind 资格 / exact-zero transversality guard / RTI trim | eligibility + guard + trim 收敛审计（u_eps=1e-9） | 不变 |
| G6R | 硬拓扑契约 / 双参考锁 / 精化半径 / paired FD plateau / 4-column | 全部实现 + 10/10 audit | refined 取代 grid 下界 |
| G6R2 | 相对误差归一化误用 nonlinear-increment 分母 | 恢复 `ERROR/LINEAR-PREDICTION`；真实重算 | 1% −1.0% / 5% −4.5%（0.040/0.193→0.040/0.185） |

corrective history 体现 successive validation hardening，不是失败隐藏。

## 30. Reproducibility

```
Python package:        pip install -e ".[dev]"（src/hyptraj）
test commands:         pytest -q（目标 G0–G7 各文件 + 全量）
snapshot locations:    tests/data/phase_g{1..6,g}_*_v1.json
scientific generators: scripts/run_phase_g6_grazing.py（G6/G6R/G6R2；
                       科学载荷 deterministic；**last regeneration
                       evidence = G6R2 acceptance**）
G6 generator audit:    G7 审计重跑一次确认：全部科学字段（refined radii /
                       threshold / paired FD / fits）逐位一致；唯一文本差异为
                       generation-metadata `starting_g6r_commit`（记录生成时
                       HEAD，属元数据）与 provenance 捕获方式（`g6r2.
                       old_radii_g6r_nonlinear_denominator` 从生成时 snapshot
                       读取）。按 §63，G7 **不**重跑 research generation、
                       **不**修改已验收 G6 snapshot（已还原，SHA 不变）；
                       若未来真需再生成，应以 G6R 提交后的历史值维护该
                       provenance 字段。
freeze manifest gen:   scripts/build_phase_g_final_manifest.py（READ/HASH/SUMMARIZE/FREEZE；
                       二次运行无 diff）
reference solver:      PRODUCTION（rtol 1e-9）/ REF-0.1（rtol 1e-12, ms 0.1）/
                       REF-0.05（ms 0.05）—— G0 冻结
canonical scaling:     Candidate A diag(1e5, 1, 7e3, 0.1)
branch:                feature/phase-g-predictability
starting accepted commit: d1ac723c6d0cf1ad50b4b679bbc3af8a0d889a45
upstream frozen commit:   96253f1ef7785764d8da3156d7d614d2b244b577（Phase F）
```

不记录 machine-specific 临时路径。

## 31. Final limitations

```
only initial-state sensitivity；constant-K frozen control
local first-order derivative；finite-time horizons
specific frozen Qian/Sanger models；no stochastic uncertainty
no optimization；no control-law sensitivity；no global asymptotic stability
near-grazing linearization eventually becomes invalid（G6R2 r_tau）
controlled local grazing family is NOT a gamma0-K trajectory family
observability analysis was outside Phase-G delivered scope
```

## 32. Final scientific acceptance table

| Component | Analytic/algorithmic object | Independent validation | Final status |
|---|---|---|---|
| Continuous Jacobian | \(A_m = ∂f_m/∂x\) | nonlinear FD（4 modes） | **VALIDATED** |
| Continuous STM | \(C_m = Φ(t,t0)\) | fixed-time FD + semigroup + REF | **VALIDATED** |
| Event-time gradient | \(q_e\) | nonlinear event-time FD | **VALIDATED** |
| Saltation | \(Ξ\) | synchronized event-map FD | **VALIDATED** |
| Hybrid STM | \(Φ_H(T,0)\) | full nonlinear hybrid FD + gate | **VALIDATED** |
| Scaled metrics | \(S_A^{-1}Φ_H S_A\) | REF stability + unit invariance | **VALIDATED** |
| Terminal sensitivity | \(η_T, J_T\) | native terminal nonlinear FD | **VALIDATED** |
| Grazing local pair | \(P_{excursion}\) | 4-column nonlinear FD | **VALIDATED** |
| Grazing validity radius | \(r_τ (τ=1%,5%)\) | bracket + deterministic refinement | **EMPIRICAL LOCAL RESULT** |
| Grazing threshold | — | evidence-based | **NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED** |

## 33. Final key findings

1. **Hybrid events matter even without state jumps.** Qian Capture 是最直接证据（negative control 显示忽略 saltation 会产生 orders-of-magnitude 误差）。
2. **Qian Capture produces structural rank loss in the synchronized first-order hybrid map**（rank→3，σ4=0，STRUCTURAL_SINGULAR；全球 gamma 行 = 0）。
3. **Under canonical scale A at common T=600 s, Sanger baseline has larger worst-direction finite-time amplification than Qian（λ_max ≈ 9×），but this ranking is scale-sensitive**（scale B 下翻转）。
4. **Native RTI/SRTI sensitivities are descriptive, not directly comparable performance endpoints**（Qian RTI ≠ Sanger SRTI）。
5. **Near Sanger grazing, event-time and saltation conditioning grow as transversality denominator tends to zero**（exact `‖qS_A‖=s_r/|d|`、scaled-Xi identity，机器精度）。
6. **The nonlinear first-order validity neighborhood shrinks with local grazing clearance**（absolute validity radius ∝ φ；G6R2：r₁%≈0.040φ、r₅%≈0.185φ，confirmed across tested families；validity-domain shrinkage, H4）。
7. **No universal scalar numeric grazing threshold is supported by the tested branches.**

---

`observability.py` 保持空 placeholder（Phase-G delivered scope 之外）；Phase
G 未因"最后一个空文件"发明 observability 科学。冻结证据清单 / SHA-256 /
authority chain 见 `phase_g_final_freeze_v1.json`。

**PHASE G COMPLETE / FROZEN（final tags 于最终冻结 commit 后创建并指向该
commit）。**

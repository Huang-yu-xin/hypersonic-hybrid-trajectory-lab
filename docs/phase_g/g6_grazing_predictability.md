# G6 — Grazing Transversality Loss & Linearization Validity

状态：**COMPLETE**（G6 accept，2026-08-18）
本次修订：**G6R corrective revision**（G6R validation-contract &
operational-radius corrective patch）→ **G6R2 归一化修正**
（linearization-error NORMALIZATION Contract Fix，2026-08-18，
G6R2 accept 待定）
分支：`feature/phase-g-predictability`
G6 起点：`7a94ed1`（G5R commit）；G6R 起点：G6 freeze commit；G6R2 起点：G6R commit `9c7e80f`
Phase-F 依据：`tests/data/phase_f_gamma_k_sensitivity_v1.json`（B0–B4，10 双参考 extremal anchors）
Machine-readable artifact：`tests/data/phase_g6_grazing_predictability_v1.json`
（整体 schema `phase-g6-grazing-predictability-v1`；G6R 增量块 schema
`phase-g6r-grazing-contract-v1`（`g6r`）；G6R2 增量块 schema
`phase-g6r2-linearization-normalization-v1`（`g6r2`））
生成器：`scripts/run_phase_g6_grazing.py`（deterministic；G6 冻结段
preserved verbatim，G6R/G6R2 段可复现重算）

## 1. 科学问题

G6 研究当 Sanger atmosphere-interface transversality
`d = n^T f^- = v sin(gamma) -> 0` 时，G3/G4/G5 的 standard transverse
first-order description（event-time gradient、saltation、paired
excursion hybrid factor）的系数增长、nonlinear accuracy、topology 保持
半径与完整 grazing-excursion map 分别发生什么。Phase-F B0-B4 frozen
grazing branches 是 source of truth；G6 **不** re-scan gamma0-K domain、
不 refit B0-B4、不计算 asymptotic/chaos claims。

## 2. Notation（避免与 Phase-F 混淆）

```
Phase-F scalar  grazing_phi / phi_N_clearance（branch-conditioned 符号 clearance）
Phase-G matrix  phi_stm / phi_hybrid（4×4 state-transition matrix）
```

新代码禁止用裸 `phi` 同时表示两者（graze 模块全程用明确命名）。

## 3. Frozen-geometry & 10 anchors（程序化加载）

10 个双参考 extremal anchors 从 `phase_f_gamma_k_sensitivity_v1.json`
程序化读取（`grazing.load_frozen_grazing_anchors`），不复制硬编码表。
N 侧：`phi_N = h_SRTI - h_atm < 0`（无 newly-created excursion，禁止
fabricate exit at SRTI）；N+1 侧：`phi_N = h_apogee,new - h_atm > 0`
（newly-created LAST VAC apogee，VAC arc ordinal = N，非 min clearance）。
限几何：`h = h_atm, gamma = 0`（`G_h = 0, v sin gamma = 0`）。

## 4. 实际 anchor audit 结果

| branch | side | regime | Phase-F Phi_N | G6 recompute Phi_N | REF diff | new excursion |
|---|---|---|---|---|---|---|
| B0 | N / N+1 | SRTI_N0/N1 | -0.0809 / +0.0480 | 复现 | < 0.05 m | no / yes |
| B1 | N / N+1 | SRTI_N1/N2 | -0.1282 / +0.1691 | 复现 | < 0.05 m | no / yes |
| B2 | N / N+1 | SRTI_N2/N3 | -0.1549 / +0.1021 | 复现 | < 0.05 m | no / yes |
| B3 | N / N+1 | SRTI_N3/N4 | -0.1352 / +0.0360 | 复现 | < 0.05 m | no / yes |
| B4 | N / N+1 | SRTI_N4/N5 | -0.4079 / +0.4191 | 复现 | < 0.05 m | no / yes |

（数值以 snapshot 为准；`regime_match` 10/10、Phi_N 符号 10/10、
new-excursion ordinal 仅 N+1 侧存在、new apogee ordinal N 仅 N+1 侧存在，
REF-0.1 vs REF-0.05 稳定。）

## 5. Conditioning algebra（exact identities，G6 §12-§13、§58）

```
||q S_A||_2          = s_r / |d|                    （s_r = 1e5 m，canonical A）
|d| ||(S_A^-1 Xi S_A - I)||_2 = s_r ||S_A^-1 (f+ - f-)||_2
```

两条为 exact algebraic invariants（rank-one structure），机器精度成立
（B0/B2 实测 residual 1e-11/1e-15）。**不是 asymptotic 近似**。它们把
`denominator conditioning`（1/|d|）与 `numerator dynamics`
（s_r·||S^-1 Δf||）干净分开。`exact n^Tf^- = 0` 仍为
GRAZING/NONTRANSVERSE，standard G3 saltation 无定义（G5R exact-zero
guard 继续有效）。

## 6. N+1 事件审计（实际 newly-created excursion）

对每 B0–B4 N+1 anchor（目标 exit ordinal = N，VAC arc N，apogee N，
matching entry N）：

| branch | d_exit [m/s] | incidence \|sinγ\| | ||qS_A|| | VAC clearance [m] | VAC duration [s] | d_entry [m/s] |
|---|---|---|---|---|---|---|
| B0 | 0.479 | 7.1e-5 | 2.09e5 | 0.048 | 0.40 | -0.479 |
| B1/B2/B3/B4 | （snapshot） | | | | | |

REF-0.1 vs 0.05：clearance / VAC duration / entry state 稳定（
`vac_duration_diff < 1e-3`, `entry_state_diff < 1e-3`）。`d_exit` 与
Phase-F 报告的 newly-created exit `T_N` 一致（B0≈0.479 m/s）。

## 7. Controlled local grazing family（CONTROLLED_LOCAL_GRAZING_FAMILY）

全部 5 条 N+1 分支各 7 个 alpha 点 REF-stable（REF-0.1 vs 0.05 stable, n=7，
无 numerical stop before 1/64）；每 alpha 减半：`d_exit` 减半、VAC duration
减半、**apogee clearance ≈ /4**（B0：0.048 → 0.012 → 0.003 → 0.0002 …）。
对每个 N+1 anchor 的 exact newly-created exit state，
`x_e(alpha) = [r_e, theta_e, v_e, alpha*gamma_e]`，alpha ∈
{1,1/2,1/4,1/8,1/16,1/32,1/64}（保持 `r_e = R_E + h_atm`；只在出现
REF 不稳定层时停止，**NUMERICAL_RESOLUTION_LIMIT** 是合法终点，非
threshold）。语义：固定 near-grazing exit altitude/theta/velocity，
只把 interface incidence 向 tangency 连续压低；
`trajectory_backed = false, local_event_state_family = true`。

B0 系列（REF-stable tail）：alpha 减半 → `d_exit` 减半、`VAC duration`
减半、**apogee clearance ≈ /4** —— 明确的 local quadratic tangency。

## 8. 几何 fit（H1–H3，hypotheses 非预设）

| branch | H1: slope log Phi_local vs log|d_exit| | fit R² | n |
|---|---|---|---|---|
| B0 | ≈2（quadratic tangency supported） | snapshot | snapshot |
| B1–B4 | （snapshot） | | |

H2（individual saltation ~ 1/|d|）由 exact identity 支撑（numerator
regularity 需验证）；H3（paired excursion factor 的幂律趋势）由实际
`||P~-I||` vs |d| 数据报告。**不强行固定 slope**。

## 9. Paired excursion factor（G6 §24-§25）

```
P_excursion = Xi_entry @ C_VAC @ Xi_exit,   C_VAC = Phi_VAC(t_entry, t_exit)（G2, raw physical）
```

matrix 顺序锁定（exit Xi → VAC continuous STM → entry Xi）；`C_VAC` 用
G2 `integrate_continuous_stm`（复用，不重写 variational equation）。
scaled `P~ = S_A^-1 P S_A` 报告 sigma_max / ||P~-I|| / rank / condition /
dominant directions。**不预设 exit/entry 抵消**；B0 α=1 实测
||P~-I||≈26.9（pair 不抵消，amplification 保持 ~1/d 量级）。

## 10. Local paired nonlinear map & FD（G6 §34-§37）

`local_grazing_excursion_map`：pre-event ATM root（G3 local root）→
identity reset → VAC 到 matching entry（apogee 检查）→ identity reset →
ATM 同步到 nominal `T_vac`。`M_excursion(0)=x_e`、
`DM_excursion(0)=P_excursion`。paired FD（radial normal direction，
`dr = beta*Phi_local`）：`D_pair ≈ P(:,r)`。selected strong/mild cases：
B0（最小 Phase-F T_N）、B3（最小正 Phi_N）、B4（较温和对照）；全 4-column
FD 在至少一个 strong + 一个 mild case 上验证（r/e_r 列为主）。

**G6R 修订（§13b）**：live paired FD 采用 **derivative plateau** 契约 —
在 clearance-normalized `β ∈ [1e-4, 3e-2]`（两侧均 `PAIR_LOCAL_VALID`）
接受 canonical-A scaled-relative error（实测 max ≈ 1.1e-4 ≪ 1e-2），
**取代旧的 β=0.5 + <0.5 容差 smoke**；并升为 **全 4-column** 独立验证
（B0 strong / B4 mild，multi-epsilon per column）。tangent 列用 absolute
scaled residual（radial 列 relative；gamma 列线性域受 incidence cone 约束，
扰动 grid 取 `|Δγ| < |γ_exit|`，frac ∈ [0.01, 0.5]）。

## 11. Linearization validity radius（G6 §29-§33）

对 selected controlled points（B0 a=1/a=0.5、B3 a=1、B4 a=1），radial
`|dr| = beta*Phi_local`，β ∈ {1e-3 … 0.3}；E_lin（两侧）以
`M_excursion(±dr) − M_excursion(0)` 为 ΔNL、`P(:,r)·(±dr)` 为 ΔLIN
（**基准为 synchronized entry state M(0)，非 exit state**），按
`||S_A^-1(ΔNL−ΔLIN)||₂/max(||S_A^-1 ΔLIN||₂, floor)`。实测：

**G6 冻结表（coarse grid-sampled lower bounds，exactly 作为历史值保留）：**

| point | φ [m] | d_exit | r_1%/φ (grid) | r_5%/φ (grid) |
|---|---|---|---|---|
| B0 a=1 | 0.048 | 0.479 | 0.03 | 0.10 |
| B0 a=0.5 | 0.012 | 0.240 | 0.03 | 0.10 |
| B3 a=1 | 0.036 | 0.641 | 0.03 | 0.10 |
| B4 a=1 | 0.419 | 2.19 | 0.03 | 0.10 |

**G6R/G6R2 精化表（refined operational radius，bracket [PASS, FAIL] +
deterministic bisection 于 clearance-normalized β；误差按 frozen
protocol `E = ERROR / LINEAR PREDICTION` 归一化，见 §13b、§13c）：**

| point | φ [m] | d_exit | r_1%/φ (refined) | r_5%/φ (refined) | r_1% bracket [lo,hi] |
|---|---|---|---|---|---|
| B0 a=1 | 0.048 | 0.479 | **0.0400** | 0.1850 | [0.03, 0.1] |
| B0 a=0.5 | 0.012 | 0.240 | 0.0400 | 0.1849 | [0.03, 0.1] |
| B3 a=1 | 0.036 | 0.641 | 0.0395 | 0.1826 | [0.03, 0.1] |
| B4 a=1 | 0.419 | 2.19 | 0.0403 | 0.1863 | [0.03, 0.1] |

→ 精化后 r_1% ≈ 0.040·φ、r_5% ≈ 0.185·φ（scale-free ratio 一致，
跨 branch/alpha 展宽 ≈ 0.0009 与 ≈ 0.0037），**并取代粗暴的 grid
lower sample（0.03/0.10）作为 operational validity radius**；
**absolute validity radius 随 φ → 0（grazing 趋近）收缩 = first-order
validity domain shrinkage 的直接证据（H4）**；同时维度化口径
（|d|、gamma 方向拓扑半径 1.5e-7–2.4e-6 rad）跨 branch 变化，见 §14。

## 12. Actual-anchor initial-state topology radius（G6 §39-§42）

对 10 真实 anchors，使用 full frozen Sanger research trajectory，固定
anchor K，只扰动 Phase-G initial state（primarily gamma方向；
`delta_gamma0` = Phase-G STM 的 initial-state column，**非** Phase-F
parameter sweep）。用 G5R terminal gate 判定同/变 topology：
`epsilon_topo^±(gamma)`、`centered = min(+,−)`；无 transition 于 cap 内
→ `LOWER_BOUND_ONLY`。skip-count 改变 → TOPOLOGY_CHANGE（ordinary
centered STM comparison 失效，非 STM error）。

## 13. Terminal descriptive consequences（G6 §43）

对 10 anchors 复用 G5 `build_terminal_sensitivity`（全部 srti）报告
`||eta S_A||`、fractional terminal-time sensitivity、scaled terminal
sigma_max、rank/nullity。N vs N+1 并排仅作
**CROSS-TOPOLOGY DESCRIPTIVE CONTRAST（NOT A DERIVATIVE）**。

## 13b. G6R corrective validation（validation-contract & operational-radius patch）

G6R 是一次 **corrective revision**：不动 Phase-F frozen physics / G6
frozen claims，只加固验证契约并精化 operational radius。逐项：

1. **Issue 1 — 硬拓扑契约（HARD GUARD）**：`extract_branch_excursion`
   现在对 Phase-F 来源 truth 的不一致 **raise `GrazingTopologyContractError`**
   （source-of-truth 不匹配，不是 G6 数值容差问题，调用方 hard-stop）：
   - N 侧：ordinal-N exit/apogee/entry 必须不存在（absence 确认）；
   - N+1 侧：ordinal-N exit/apogee/entry 必须齐全、时序
     `t_exit < t_apo < t_entry`、`d_exit>0`、`d_entry<0`、
     `vac_duration>0`、`clearance>0`；
   - 实际 frozen regime 必须等于 Phase-F 预期 `SRTI_N`/`SRTI_{N+1}`
     （`sanger_anchor_topology` 内部校验）。契约审计 10/10 通过
     （5 absence + 5 extraction），见 snapshot `g6r.contract_audit`。
2. **Issue 5 — dual-reference 锁 + 事件方向分类**：loader 锁定
   `reference_dual_stable`（10/10 True）与 REF-0.1/REF-0.05 `Phi_N`；
   `PairedExcursionClass` 新增/强制 `WRONG_ENTRY_DIRECTION`，
   `WRONG_EXIT_DIRECTION`（crossing 处 `d≤0`）、`NONPHYSICAL_STATE`
   （非物理起点）、并把 `VAC_EXCURSION_LOST`/`VAC_APOGEE_NOT_FOUND`
   （topology 丢失）与 `NUMERICAL_FAILURE`（integrator 缺陷）结构化分开
   （`_run_vac_excursion` 抛 `VacExcursionFailure(status)`，不再字符串匹配）。
   物理 kind-ordinals 保持精确（synthetic / pullout / SRTI 不入 excursion
   ordinal map）。
3. **Issue 2 — refined operational radius**：
   `refined_operational_radius` 用 bracket（`lower_pass_beta` PASS /
   `upper_fail_beta` FAIL，含 topology-limited 情形）+ **deterministic
   bisection**（24 次）在 clearance-normalized β 上求
   `r_τ = sup{r: 两侧 valid 且 E_pair(r) ≤ τ}`；报告
   `lower_pass_beta / upper_fail_beta / refined_beta /
   refined_radius_m / radius_over_phi / bracket_width`。NONMONOTONE 判定为
   **τ-relative**（fail 之后出现 re-entrant pass ⇒
   `NONMONOTONE_VALIDITY_PROFILE`），tiny-β 舍入噪声 dip（≪τ）不算。
   精化结果（G6R2 protocol-correct 归一化）：r_1%/φ ≈ 0.0395–0.0403、
   r_5%/φ ≈ 0.183–0.186（§11、§13c）。
4. **Issue 3 — paired radial plateau FD**：`paired_radial_fd_plateau`
   在 `β ∈ [1e-4, 3e-2]` 全网格两侧 `PAIR_LOCAL_VALID` 且
   canonical-A scaled-relative error 保持 < 1e-2（实测 max ≈ 1.1e-4）；
   `plateau_pass` 即 acceptance。
5. **Issue 4 — full 4-column paired FD**：`paired_fd_validation` 在 B0
   （strong）与 B4（mild）全 4 列 multi-epsilon 独立 FD；radial 列
   scaled-relative、tangent 列 absolute scaled residual；全部
   `four_column_pass=True`（snapshot `g6r.paired_fd`）。

**规模声明**：G6R 只新增 predictability-layer 校验代码/测试/snapshot
增量/文档；未改动 frozen 物理、未重扫 gamma0-K、未 refit B0–B4、
未新增 Monte Carlo / uncertainty / 优化 / 渐近混沌声明。

## 13c. G6R2 normalization correction（linearization-error 归一化修正）

**Root cause（不隐藏 provenance）**：frozen Phase-G protocol 定义

```
E_lin = ||S_A^-1 (Δx_NL − Δx_LIN)||₂ / max(||S_A^-1 Δx_LIN||₂, ε_floor)
      = ERROR / LINEAR PREDICTION          （分母 = canonical-scaled LINEAR prediction norm）
```

G6R 初版 `_elin_probe` 误用了 **NONLINEAR increment norm**
`||S_A^-1 (M(±εe_r) − M(0))||` 作为 denominator（两者渐近等价但不相同：
`||Δx_NL|| = ||Δx_LIN||·(1+O(β))`）。G6R2 把归一化改回 frozen
definition：显式实现 `scaled_linearization_error(nl, lin, scale_vec)`
——**不再出现 `||S_A^-1 (Mp − M0)||` 作为 relative denominator**。

- plus：`Δx_NL⁺ = M(+εe_r)−M(0)`，`Δx_LIN⁺ = +εP(:,r)`；
  `E₊ = ||S⁻¹[ΔNL⁺−ΔLIN⁺]|| / max(||S⁻¹(εP(:,r))||, ε_floor)`；
- minus：`Δx_NL⁻ = M(−εe_r)−M(0)`，`Δx_LIN⁻ = −εP(:,r)`；
  `E₋ = ||S⁻¹[ΔNL⁻−ΔLIN⁻]|| / max(||S⁻¹(−εP(:,r))||, ε_floor)`；
  两侧 denominator 理论相等（`||−εP||=||εP||`）；
- `E_pair = max(E₊,E₋)`，仍要求 both sides `PAIR_LOCAL_VALID`；
- `ε_floor = 1e-15` 仅为 0/0 数值归一化 guard，**不是** grazing /
  validity / physics threshold；G6 threshold policy 不变。

**重新计算（protocol-correct，真实重跑 generator，未手工乘 correction
factor）**：

| point | old G6R r₁%/φ (nonlin. denom.) | new r₁%/φ (protocol) | Δ | old r₅%/φ | new r₅%/φ | Δ |
|---|---|---|---|---|---|---|
| B0 a=1 | 0.04037 | **0.03998** | −1.0% | 0.19371 | 0.18495 | −4.5% |
| B0 a=0.5 | 0.04036 | 0.03997 | −1.0% | 0.19363 | 0.18487 | −4.5% |
| B3 a=1 | 0.03986 | 0.03947 | −1.0% | 0.19119 | 0.18257 | −4.5% |
| B4 a=1 | 0.04073 | 0.04034 | −1.0% | 0.19487 | 0.18629 | −4.4% |

变化与预期一致（§9：1% 系数小变 −1%；5% 稍大但仍温和 −4.5%）；全部
仍 `MONOTONE_REFINED_RADIUS`、monotone=True、bracket 不变。旧值原样保存
于 snapshot `g6r2.old_radii_g6r_nonlinear_denominator`（不覆盖历史）。
**paired derivative FD 未受影响**：`paired_radial_fd_plateau` /
`paired_fd_validation` 不经过 `_elin_probe`，B0/B4 plateau 与 4-column
结果逐位不变（snapshot `g6r2.paired_fd_results_unchanged=true`）。

## 14. Numeric grazing-threshold decision（evidence-based）

```
FINAL: NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED
```

理由：归一化 1%-validity radius 高度一致（**G6R/G6R2 精化后，protocol
归一化 `E=ERROR/LINEAR PREDICTION`** r_1%/φ ≈ 0.040 跨 B0–B4 与 alpha，
r_5%/φ ≈ 0.185；原 G6 grid 值 0.03/0.10 仅为 lower sample），这**正说明
没有 universal 维度化阈值**：anchors 处的维度化 `|d|` collapse 水平
（0.48–2.19 m/s）与 gamma 方向拓扑保持半径（1.5e-7–2.4e-6 rad，跨度
~16×）均跨 branch 变化，不存在单个数值能把 "grazing-adjacent" 与
"transverse" 分开。G6R 以精化 radius 重审计、G6R2 以 protocol-correct
归一化重算 → 结论**RETAINED AFTER PROTOCOL-CORRECT NORMALIZATION**
（snapshot `g6r.threshold_reauth` + `g6r2.threshold_decision_reaudited`）。
资格判定使用 continuous diagnostics（`|d|`、`|sinγ|`、φ clearance、
validity radius、topology gate、REF stability）。**exact `n^Tf^- = 0`
仍为 GRAZING/NONTRANSVERSE**；小有限 denominator 从不自动拒绝。G6/G6R/G6R2
未冻结任何 universal physics threshold。

## 15. Claim boundaries / G7 handoff

禁止：Xi→∞ = 物理不确定性无穷；grazing = chaos；positive/huge local
amplification = asymptotic Lyapunov；one-branch fit 证明 universal
exponent；N 侧可通过 boundary 求导；N vs N+1 差/参数间距 = derivative；
controlled family 是 gamma0-K 物理轨迹族；numerical resolution limit =
exact grazing；one denominator threshold universal；B0-B4 是解析
bifurcation 曲线。

G7 = final synthesis / final regression / final report / final freeze(tag)。

**G6 = COMPLETE / ACCEPTED；G6R corrective = COMPLETE；G6R2 normalization
fix = COMPLETE（G6R2 accept 待定）；等待人工验收后再进入 G7（G7 PENDING）。**
# G6 — Grazing Transversality Loss & Linearization Validity

状态：**COMPLETE**（G6 accept，2026-08-18）
分支：`feature/phase-g-predictability`
G6 起点：`7a94ed1`（G5R commit）
Phase-F 依据：`tests/data/phase_f_gamma_k_sensitivity_v1.json`（B0–B4，10 双参考 extremal anchors）
Machine-readable artifact：`tests/data/phase_g6_grazing_predictability_v1.json`
（schema `phase-g6-grazing-predictability-v1`）

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

## 11. Linearization validity radius（G6 §29-§33）

对 selected controlled points（B0 a=1/a=0.5、B3 a=1、B4 a=1），radial
`|dr| = beta*Phi_local`，β ∈ {1e-3 … 0.3}；E_lin（两侧）以
`M_excursion(±dr) − M_excursion(0)` 为 ΔNL、`P(:,r)·(±dr)` 为 ΔLIN
（**基准为 synchronized entry state M(0)，非 exit state**），按
`||S_A^-1(ΔNL−ΔLIN)||₂/max(||S_A^-1 ΔLIN||₂, floor)`。实测：

| point | φ [m] | d_exit | r_1%/φ | r_5%/φ |
|---|---|---|---|---|
| B0 a=1 | 0.048 | 0.479 | **0.03** | 0.10 |
| B0 a=0.5 | 0.012 | 0.240 | 0.03 | 0.10 |
| B3 a=1 | 0.036 | 0.641 | 0.03 | 0.10 |
| B4 a=1 | 0.419 | 2.19 | 0.03 | 0.10 |

→ r_1% ≈ 0.03·φ、r_5% ≈ 0.10·φ（scale-free ratio 一致）；
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

## 14. Numeric grazing-threshold decision（evidence-based）

```
FINAL: NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED
```

理由：归一化 1%-validity radius 高度一致（r_1%/φ ≈ 0.03 跨 B0–B4 与
alpha），这**正说明没有 universal 维度化阈值**：anchors 处的维度化
`|d|` collapse 水平（0.48–2.19 m/s）与 gamma 方向拓扑保持半径
（1.5e-7–2.4e-6 rad，跨度 ~16×）均跨 branch 变化，不存在单个数值能把
"grazing-adjacent" 与 "transverse" 分开。资格判定使用 continuous
diagnostics（`|d|`、`|sinγ|`、φ clearance、validity radius、topology
gate、REF stability）。**exact `n^Tf^- = 0` 仍为 GRAZING/NONTRANSVERSE**；
小有限 denominator 从不自动拒绝。G6 未冻结任何 universal physics
threshold。

## 15. Claim boundaries / G7 handoff

禁止：Xi→∞ = 物理不确定性无穷；grazing = chaos；positive/huge local
amplification = asymptotic Lyapunov；one-branch fit 证明 universal
exponent；N 侧可通过 boundary 求导；N vs N+1 差/参数间距 = derivative；
controlled family 是 gamma0-K 物理轨迹族；numerical resolution limit =
exact grazing；one denominator threshold universal；B0-B4 是解析
bifurcation 曲线。

G7 = final synthesis / final regression / final report / final freeze(tag)。

**G6 = COMPLETE；等待人工验收后再进入 G7。**
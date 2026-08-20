# ML-B1 — First-Order Geometry Gate

> 项目：RareTopo — Rare Topology Transition Estimation in Hybrid Dynamical Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab`
> 分支：`feature/phase-h-uncertainty-risk`
> 上游：H2R ACCEPTED（`7895712c`）；Local Fold Geometry / Geometry-IS Variance Theorem ACCEPTED
> 状态：**ML-B1 COMPLETE / READY FOR REVIEW**（5 anchors 全 PASS；人工验收后
> 升级为 ACCEPTED 并进入 H3）
> 执行 brief：`ML_B1_FIRST_ORDER_GEOMETRY_GATE_EXECUTION_BRIEF.md`
> snapshot：`tests/data/ml_b1_first_order_geometry_v1.json`（schema
> `ml-b1-first-order-geometry-v1`，2026-08-20 生成，确定性可复现）

## 1. 本轮唯一问题

> RareTopo 理论中的 **topology margin 与 first-order geometry**，在真实
> nonlinear hybrid simulator 上到底算得对不对？

ML-B1 **不重新证明** 上游 theorem（`a = Phi^T n`、`sign(b) <-> topology side`、
`|b| ~ d^2`、`RV_geom = Theta(beta)`）；只验证其**真实 simulator 实现正确性**。

## 2. 核心对象

### Virtual topology margin（Goal A）

$$
b_j(x_0) = \sigma_j\, G_j\!\big(x^*(t_j^*; x_0)\big),
\qquad
\partial_t \widehat G_j(t_j^*) = 0,
\qquad
\widehat G_j = \sigma_j G_j,
$$

实现语义（Sanger `atmosphere_exit` channel）：

```text
prior true hybrid events : 真实执行（保留真实 event ordering / mode sequence）
critical segment          : 固定 pre-critical mode（SANGER_ATM）做 virtual continuation
critical topology switch  : 不执行（事件列表不注册 atmosphere_exit）
tracked extremum          : gamma: + -> - 的界面函数极值（srti-candidate root）
```

Guard / critical condition / oriented normal（brief §8）：

$$
G_h = h - h_{\rm atm},\qquad
\dot G_h = v\sin\gamma = 0,\qquad
n^\star = \sigma\, e_r,\qquad \sigma = -1\ (\text{verified per anchor}).
$$

`b > 0` 为 nominal-side clearance（`SRTI_N`），`b < 0` 为 transition-side
event-pair regime（`SRTI_{N+1}`）。

### Analytic gradient（Goal C）

$$
\boxed{\,a = \nabla_{x_0} b = (\Phi^\star)^{\mathsf T} n^\star\,},
\qquad
\Phi^\star = \Phi_{\rm crit}(t^\star \leftarrow t_{\rm seg})
\,\underbrace{\Phi_{\rm prior}(t_{\rm seg} \leftarrow 0)}_{\text{连续 STM + prior transverse saltations}},
$$

critical grazing 自身的 saltation **不加入**（virtual continuation 不执行该 switch）。

### Geometry direction（Goal D）

$$
\boxed{\,v_{\rm geom} = -\frac{P_0 a}{\sqrt{a^{\mathsf T} P_0 a}}\,},
\qquad
\boxed{\,a^{\mathsf T} v_{\rm geom} = -\sqrt{a^{\mathsf T} P_0 a}\,},
\qquad
\boxed{\,\alpha = \frac{L_0^{\mathsf T} a}{\lVert L_0^{\mathsf T} a\rVert}\,},
$$

$$
b_{\rm lin}(\lambda) = b_0 - \lambda \sqrt{a^{\mathsf T} P_0 a},
\qquad
\beta_{\rm local} = \frac{b_0}{\sqrt{a^{\mathsf T} P_0 a}}.
$$

## 3. 实现清单（文件）

| 文件 | 作用 |
|---|---|
| `src/hyptraj/uncertainty/topology_margin.py` | margin pipeline / exact-topology oracle / analytic gradient / scaled-FD gate / epsilon sweep / geometry direction / boundary scan / random-tangent controls |
| `scripts/run_ml_b1_geometry_gate.py` | 确定性生成器，产出 machine-readable snapshot |
| `tests/data/ml_b1_first_order_geometry_v1.json` | ML-B1 machine-readable snapshot（schema `ml-b1-first-order-geometry-v1`） |
| `tests/test_uncertainty/test_ml_b1_geometry_gate.py` | ML-B1 regression / live smoke tests |
| `docs/phase_h/ml_b1_first_order_geometry.md` | 本文档 |

## 4. 复用的 frozen primitives（不复制第二套 physics）

- 真实 hybrid simulator：`simulation/sanger_trajectory.py::integrate_sanger_hybrid`
  （production / REF-0.1 / REF-0.05 `SolverConfig`）；
- 事件工厂与界面函数：`simulation/sanger_events.py`
  （`make_srti_candidate_event`、`make_pullout_event`、`atmosphere_interface_normal`）；
- 连续 STM：`predictability/stm.py::integrate_continuous_stm`（20-D augmented，DOP853）；
- 横向 saltation：`predictability/saltation.py::identity_reset_saltation`；
- canonical scaling / covariance：`uncertainty/protocol.py`
  （`S_A = diag(1e5,1,7e3,0.1)`、`P0 = S_A (alpha^2 I) S_A^T`，`alpha = 1`）；
- Phase-F reference-certified anchors：`tests/data/phase_f_gamma_k_sensitivity_v1.json`
  （10 个 B0-B4 双参考 extremal anchors）。

## 5. Anchor 选择

| anchor | 边界/channel | nominal topology | neighbor | conditioning | reference |
|---|---|---|---|---|---|
| `B0_N_side` | B0 / atm-exit | `SRTI_N0` | `SRTI_N1` | well | dual stable |
| `B1_N_side` | B1 / atm-exit | `SRTI_N1` | `SRTI_N2` | well | dual stable |
| `B1_N1_side` | B1 / atm-exit | `SRTI_N2` | `SRTI_N1` | medium | dual stable |
| `B2_N_side` | B2 / atm-exit | `SRTI_N2` | `SRTI_N3` | medium | dual stable |
| `B2_N1_side` | B2 / atm-exit | `SRTI_N3` | `SRTI_N2` | more difficult | dual stable |

`B4_N1_side` 因默认 horizon 内 `max_time` 终止被排除（数值分辨率问题，非一阶
geometry 失效）；避免最极端 grazing anchor 作为 primary acceptance（brief §23）。

## 6. 关键数值结果（详见 snapshot `tests/data/ml_b1_first_order_geometry_v1.json`）

5 个 reference-certified anchors（B0/B1/B2 × N/N1 side）全部通过 ML-B1
acceptance gate：

| anchor | b (REF-0.1) | Phase-F φ | orientation | sign gate | FD plateau | grad cos/L2 | boundary |
|---|---|---|---|---|---|---|---|
| `B0_N_side` | +0.0809 | −0.080928 | PASS | 16/16 | PASS | 1.00000 / 1.4e-6 | PASS |
| `B1_N_side` | +0.1282 | −0.128188 | PASS | 16/16 | PASS | 1.00000 / 2.8e-6 | PASS |
| `B1_N1_side` | −0.1695 | +0.169139 | PASS | 16/16 | PASS | 1.00000 / 2.7e-6 | PASS |
| `B2_N_side` | +0.1549 | −0.154892 | PASS | 16/16 | PASS | 1.00000 / 2.3e-6 | PASS |
| `B2_N1_side` | −0.1031 | +0.102113 | PASS | 16/16 | PASS | 1.00000 / 2.5e-6 | PASS |

- **margin 与 Phase-F certified clearance 吻合**：`b = -phi_F`（如 B1_N_side
  `+0.1282` vs `−0.128188`）。
- **analytic vs scaled-FD**：scaled-space cosine = 1.00000、normalized L2 ≈
  1e-6（材料坐标 {r, v, γ} plateau；θ 为对称性零列，单点大 ε 验证 ≈ 0）。
- **同侧 FD 窗口**：extremal anchors |b| ~ 0.1 m，scaled step > 1e-6 即跨
  拓扑边界（pair gate 正确拒绝）；sweep 扩展至 1e-8..1e-6 后全 4 列出现
  clear plateau。ε > 1e-6 不再评估（必然无效 + REF DOP853 偶发 stall）。
- **sign(b) vs exact topology**：5 anchors × 16 扰动 = 80 samples，agreement
  **80/80 = 100%**，无 mismatch 分类。
- **几何方向**：`beta_local` 全部落在 exact boundary bracket 内（如 B0:
  β=6.59e-7 ∈ [5.69e-7, 7.06e-7]）；b(λ) 与一阶线性预测逐点吻合；
  geometry 方向 min|b| = 0.009（最接近边界、拓扑翻转），random 0.03–0.11，
  tangent 一阶导 = 0.0（理论预期）。
- **solver 稳定性**：REF-0.1 vs REF-0.05 的 b 一致到 1e-6（10/10 anchors
  拓扑一致）；production 的 b 差异 < 3e-5（但其 N1-side 拓扑会漏最浅 skip，
  仅作 secondary audit）。

## 7. Claim boundaries（brief §28）

ML-B1 只证明：

> 在 selected local topology channels 上，当前代码能够正确计算 RareTopo
> 所需的一阶 analytical topology geometry。

ML-B1 不声称：`b` 全局光滑、所有 topology boundaries 是 folds、
`beta_local` 是全局精确 FORM、`q_geom` 已最优、Geometry-IS half-space
theorem 对完整 Sanger nonlinear event 直接成立、learned residual 会改进
Geometry-IS。

## 8. Scope confirmation

```text
H3 NOT STARTED
topology probability NOT estimated
P(N) / P(N+1) NOT estimated
q_geom production sampler NOT implemented
Geometry-IS empirical runs NOT started
CEM NOT run / Subset Simulation NOT run
Flow model NOT trained / learned residual NOT trained
SORM / ML-B2 NOT started
Phase-F domain NOT rescanned
Phase A-G frozen physics NOT modified
```

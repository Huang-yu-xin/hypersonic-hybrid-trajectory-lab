# G3 — Transverse Hybrid Saltation（横截混合 saltation 与事件时间验证）

状态：**COMPLETE**（G3 accept，2026-08-18）
分支：`feature/phase-g-predictability`
G3 起点：`a3c6dfd`（G2R commit）
G0 依据：`docs/phase_g/predictability_protocol.md`（saltation/event-time 约定）
G2 依据：`docs/phase_g/g2_continuous_stm.md`（连续 mode STM，供局部 flow 使用）
Machine-readable artifact：`tests/data/phase_g3_transverse_saltation_v1.json`
（schema `phase-g3-transverse-saltation-v1`）

## 1. 目标与边界

G3 建立并独立验证三个 FROZEN true hybrid switch 的 **event-local
transverse hybrid linearization**：

```
Qian Capture              ENTRY_CAPTURE -> QEG_GLIDE
Sanger atmosphere exit    SANGER_ATM   -> SANGER_VAC
Sanger atmosphere entry   SANGER_VAC   -> SANGER_ATM
```

即 event-time sensitivity 与 saltation matrix。**G3 = event-local
derivative；G4 = whole hybrid trajectory derivative。** 本轮不做 full
hybrid STM / 连续 STM×saltation 链式合成 / RTI·SRTI terminal
sensitivity / FTLE / grazing anchors / Monte Carlo / optimization。

## 2. 约定（沿用 G0，冻结）

```
event time gradient   q_e = d t_e / d x^- = - n^T / (n^T f^-)    shape (4,)
                      d t_e = q_e @ d x^-
saltation matrix      Xi = I + (f^+ - f^-) n^T / (n^T f^-)   (DR = I)
determinant lemma     det(Xi) = (n^T f^+) / (n^T f^-)
f_minus / f_plus      pre / post frozen RHS，n 为 pre-event normal
```

输入 guards：shape `(4,)` / `(4,4)`、finite；`n^T f^- == 0`（exact）→
`NonTransverseEventError`（**绝不除零返回 inf/nan**）；小但非零的
denominator **不**在本轮自动拒绝，只记录 magnitude（G6 处理 grazing
validity domain）。

## 3. Event taxonomy 资格

eligible（可构造 saltation）：

```
qian_capture               sanger_atmosphere_exit   sanger_atmosphere_entry
```

excluded（`NotHybridSwitchError`）：

```
qian_rti  (RESEARCH_TERMINAL)      sanger_srti  (RESEARCH_TERMINAL)
sanger_atmospheric_pullout (DIAGNOSTIC)          sanger_vac_apogee (DIAGNOSTIC)
synthetic_initial_entry (非物理 root crossing)
```

DENSE_RECOVERED 事件仍是同一物理 ATM→VAC switch（resolution metadata），
但 G3 的 normal acceptance set 使用 baseline SRTI_N2 的 solver-resolved
events；本项目 baseline 全部为 SOLVER_EVENT（`event_resolution`），
未使用 Phase-F grazing anchors。

## 4. Event extraction

- **Qian**：`integrate_qian_research_trajectory` 的 exact `capture_event`
  （time/state）；`f_minus = ENTRY_CAPTURE RHS(x_e)`、
  `f_plus = QEG_GLIDE RHS(x_e)`、`n = [0,0,0,1]`（record 无这些字段，
  由 frozen primitives 计算，**不修改** frozen record）。
- **Sanger**：`HybridEventRecord` 已存 state/time/f_minus/f_plus/normal/
  mode_before/mode_after；G3 用 frozen RHS 重新计算 f_minus/f_plus 并
  与 record **交叉验证**（metadata integrity test，f_minus/f_plus
  metadata 误差 = 0.0，normal match = True）。

## 5. Validation event set（baseline 实测）

| event | index | time [s] | mode_before→mode_after | resolution | n^T f^- [m/s or rad/s] |
|---|---|---|---|---|---|
| Qian Capture | 0 | 93.4288 | ENTRY_CAPTURE→QEG_GLIDE | SOLVER_EVENT | +0.00504 (γ̇⁻) |
| Sanger exit X0 | 2 | 202.964 | SANGER_ATM→SANGER_VAC | SOLVER_EVENT | +430.99 |
| Sanger entry E1 | 4 | 484.640 | SANGER_VAC→SANGER_ATM | SOLVER_EVENT | −430.99 |
| Sanger exit X1 | 6 | 748.114 | SANGER_ATM→SANGER_VAC | SOLVER_EVENT | +133.92 |
| Sanger entry E2 | 8 | 814.802 | SANGER_VAC→SANGER_ATM | SOLVER_EVENT | −133.92 |

全部 transversal（`|n^T f^-|` 远离零）；无 grazing-adjacent event 入选。
**未冻结任何数值 grazing threshold。**

## 6. Qian Capture 特殊结构（G3 §10, §26）

Exact capture state 的 QEG active-set audit（baseline）：

```
u_L*_capture = 0.0664   ->   INTERIOR（0 < u_L* < 1）
distance_to_0 = 0.0664,  distance_to_1 = 0.9336
```

因此 post-Capture 是 smooth QEG interior：

```
f^+ - f^- = [0, 0, 0, -γ̇^-]^T   （r/θ/v 行相同；γ̇⁺=0）
Xi_capture = diag(1,1,1,0)
q_c        = [0, 0, 0, -1/γ̇^-]^T
det(Xi)    = 0（lemma = γ̇⁺/γ̇^- ≈ 4.3e-17）
```

该结构由**一般 saltation formula 从 frozen f_minus/f_plus/normal 计算**
得到，未 hard-code。**不**把 det=0 解读为 grazing / infinite
sensitivity / numerical failure，而是：baseline strict-interior
Capture 上，QEG post-mode 把 flight-path-angle normal direction 约束到
local QEG manifold；event-time adjustment 吸收该 normal perturbation，
因此 synchronized event-local first-order map 在该方向是 rank-deficient
（event-local first-order result，后续连续传播由 G4/G5 研究）。

## 7. Sanger 稀疏切变结构（G3 §13）

```
n = e_r=[1,0,0,0],  n^T f^- = ṙ^- = v sinγ
Xi = I + (f^+ - f^-) e_r^T / ṙ^-   →  仅第一列可能改变
r/θ 行同 state 的 ATM/VAC 相同 → Xi[:,0] = [1, 0, Δv̇/ṙ, Δγ̇/ṙ]^T
Xi[:,1]=e_2, Xi[:,2]=e_3, Xi[:,3]=e_4（theta/v/gamma 列恒等）
det(Xi) = 1（lemma = ṙ⁺/ṙ⁻ = 1）
```

符号 sanity（实测符合）：v-row 系数 `Δv̇/ṙ` 对 exit/entry 均为正；
gamma-row 系数 `Δγ̇/ṙ` 均为负（G3 §32）。量级很小（~1e-5 / ~1e-8）
是因为 100 km 处气动力极小（正值、负号正确）。

## 8. 局部非线性验证协议（G3 §17-§23）

对每个 event（以 REF-0.1 提取结果为 nominal）：

1. **local event crossing**（可在 nominal 前或后）：从 `x_e + δx` 出发，
   用 frozen pre-event RHS 沿 ± 方向在 local horizon 内定位最近 event
   surface root（`local_event_crossing_time`；一阶估计 `τ_lin` 只决定
   搜索方向，结果由 solver 终端事件定位，不依赖 sampled grid）。
2. **synchronized post-event map** `M(δx)`：pre-event root `τ_e` →
   perturbed event state（identity reset `x+ = x-`）→ post-event flow
   `-τ_e` 同步到 nominal event time。`M(0)=x_e`，`DM(0)=Ξ`。
3. **event-time FD** `(τ(+ε)−τ(−ε))/(2ε)` vs `q·e_j`；**saltation FD**
   `(M(+ε)−M(−ε))/(2ε)` vs `Ξ[:,j]`；multi-epsilon sweep（base
   `[100 m, 1e-5 rad, 1 m/s, 1e-4 rad]` 仅作 local FD 参考 step，
   **不是 canonical scaling**）。
4. 每侧分类 `TRANSVERSE_LOCAL_VALID / WRONG_EVENT_DIRECTION /
   NO_LOCAL_ROOT / ACTIVE_SET_CHANGED / NONPHYSICAL_STATE /
   NUMERICAL_FAILURE`；Qian 需保持 post-capture QEG interior。
5. Reference convergence：production / REF-0.1 / REF-0.05 提取 event，
   比较 time/state/denom/q/Ξ（重点 `Xi_0.1 ≈ Xi_0.05`）。

tangent directions（如 Sanger θ/v/γ 的 q 分量、Qian θ 的 q 分量）analytically
0 → 只报 absolute residual，不用不稳相对误差。

## 9. 验证结果

### Event-time FD（plateau 处 material relative / absolute residual）

| event | plateau mult | material rel | min abs residual |
|---|---|---|---|
| Qian Capture | 0.001 | 2.2e-13 | 4.3e-11 |
| Sanger exit X0 | 0.01 | 3.1e-10 | 7.2e-13 |
| Sanger entry E1 | 0.01 | 5.4e-11 | 1.3e-13 |
| Sanger exit X1 | 0.003 | 1.5e-9 | 1.1e-11 |
| Sanger entry E2 | 0.003 | 1.4e-9 | 1.1e-11 |

### Saltation local-map FD（plateau 处 material relative / absolute residual）

| event | plateau mult | material rel | min abs residual |
|---|---|---|---|
| Qian Capture | 1.0 | 3.9e-13 | 6.2e-10 |
| Sanger exit X0 | 0.03 | 2.9e-11 | 2.9e-11 |
| Sanger entry E1 | 0.03 | 2.9e-11 | 2.9e-11 |
| Sanger exit X1 | 0.01 | 5.3e-10 | 5.3e-10 |
| Sanger entry E2 | 0.01 | 5.3e-10 | 5.3e-10 |

全部 material relative ≪ 1e-5 target，多数 1e-10–1e-13。

### Reference convergence（REF-0.1 vs REF-0.05）

| event | state max abs | Ξ max abs | q max abs | 判定 |
|---|---|---|---|---|
| Qian Capture | 1.3e-8 | 0.0 | 3.7e-10 | PASS |
| Sanger X0/E1 | ~4e-10 | ~5e-17 | ~6e-15 | PASS |
| Sanger X1/E2 | ~1e-9 | ~1e-15 | ~2e-13 | PASS |

### 分类

全部 event × 全部方向 × 双侧：**TRANSVERSE_LOCAL_VALID**。无
WRONG_EVENT_DIRECTION / NO_LOCAL_ROOT / ACTIVE_SET_CHANGED /
NONPHYSICAL_STATE / NUMERICAL_FAILURE。

## 10. 实现的 API（`src/hyptraj/predictability/saltation.py`）

```
transversality_denominator(f_minus, normal)          # n^T f^-（纯评估）
event_time_gradient(normal, denominator)             # q = -n/denom，(4,)
identity_reset_saltation(f_minus, f_plus, normal)    # I + (f+-f-)n^T/denom
saltation_matrix(DR, f_minus, f_plus, normal)        # 一般式，DR=I 还原
saltation_determinant_lemma(f_minus, f_plus, normal) # (n^T f+)/(n^T f-)
HybridLocalLinearization(...)                        # event-local 容器
assert_saltation_eligible(event_name)                # NotHybridSwitchError
extract_qian_capture(...) / extract_sanger_switches(...)
local_flows_for(event_name, ...)                     # frozen pre/post RHS
event_surface_for(event_name, env)                   # frozen surface
local_event_crossing_time(...)                       # 局部 root（前/后）
synchronized_post_event_map(...)                     # M(δx)=y+
classify_local_side(...)                             # §21 分类
event_time_fd_sweep(...) / saltation_local_map_fd_sweep(...)
```

## 11. 已知限制 / G4 handoff

- 只研究 event-local transverse linearization；**不**链式合成连续
  STM×saltation（G4）。
- 小 denominator 的 grazing-adjacent validity domain 留给 G6；
  `NonTransverseEventError` 只拦 exact-zero。
- RTI / SRTI terminal sensitivity、FTLE 均在后续阶段。

**G4 handoff**：`HybridLocalLinearization`（Ξ、q、f_minus/f_plus/normal）
已 freeze 且 event-local 独立验证通过；G4 可把连续 STM（G2）×当前 saltation
（G3）在正确事件序列上组合成 whole hybrid trajectory derivative。

**G3 = COMPLETE；等待人工验收后再进入 G4。**
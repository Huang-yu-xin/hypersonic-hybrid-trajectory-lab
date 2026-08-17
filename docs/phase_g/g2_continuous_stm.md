# G2 — Continuous STM Validation（单连续模式 STM 积分与非线性验证）

状态：**COMPLETE**（G2 accept，2026-08-18）
分支：`feature/phase-g-predictability`
G2 起点：`d1b3030`（G1 commit）
G1 依据：`docs/phase_g/g1_continuous_variational.md`（G1 COMPLETE）
Machine-readable artifact：`tests/data/phase_g2_continuous_stm_v1.json`
（schema `phase-g2-continuous-stm-v1`）

## 1. 目标与边界

G2 在单一 smooth continuous mode 内建立并验证 state transition matrix：

```
x_dot      = f_m(x)                 （frozen nonlinear RHS）
A_m(x)     = ∂f_m/∂x                （G1 analytic Jacobian，constant K）
Phi_dot    = A_m(x) Phi,  Phi(t0,t0) = I
Phi(t1,t0) = ∂x(t1; x0) / ∂x0
```

只研究 continuous single-mode flow、fixed elapsed time、initial-state
perturbation。明确不做：hybrid switch、saltation、event-time/terminal
sensitivity、FTLE、grazing、Monte Carlo、optimization、gamma0-K rescan。

## 2. State / STM convention（G0 冻结）

```
x = [r, theta, v, gamma]^T,   h = r - R_E
Phi_ij = ∂x_i(t)/∂x_0,j
rows = output state component, columns = initial perturbation
Phi(t0) = I_4
```

## 3. Augmented continuous variational system（G2 §5）

```
z = [x; vec(Phi)]        dim = 4 + 16 = 20
flatten convention: numpy C-order / row-major
    phi_flat = phi.reshape(16, order="C")
    phi      = phi_flat.reshape((4,4), order="C")
z_dot = [x_dot; vec(A(x) Phi)]
```

pack/unpack round-trip 由语义测试锁定。

## 4. Frozen RHS reuse（G2 §6）

augmented RHS 只调用现有接口，**无第二套 physics**：

```
x_dot <- jacobian.frozen_rhs(mode)(x)        （frozen nonlinear RHS）
A     <- jacobian.analytic_jacobian(mode)(x) （G1 analytic Jacobian）
```

## 5. Modes covered / representative windows（真实 frozen trajectories）

| mode | segment | t0 [s] | t1 [s] | duration [s] | h0 [m] | 最近 true-switch margin |
|---|---|---|---|---|---|---|
| ENTRY_CAPTURE | Qian seg0 | 23.36 | 79.41 | 56.1 | 85224 | capture @ 93.4 s（>14 s） |
| QEG_INTERIOR | Qian seg1 | 187.87 | 534.16 | 346.3 | 46041 | RTI @ 723.0 s（>189 s） |
| SANGER_ATM | Sanger seg0 | 60.89 | 172.52 | 111.6 | 59924 | exit @ 202.96 s（>30 s） |
| SANGER_VAC | Sanger seg1 | 287.47 | 442.39 | 154.9 | 125495 | entry @ 484.64 s（>42 s） |

所有 windows：h > 0 throughout；无 true hybrid switch 跨过；
Sanger ATM window 内含 atmospheric pullout（diagnostic，不改变
continuous vector field，**不是 saltation**）；Sanger VAC window 同属
一个真实 VAC segment，无 ATM entry 跨过。

### QEG smooth-branch gate（G2 §8）

整个 integration interval 的 nominal 与全部 accepted ± perturbation
轨迹都必须满足 `0 < u_L*(t) < 1`。Nominal QEG window：

```
min_u_L* = 0.1634,   max_u_L* = 0.6490
min distance to 0 = 0.1634,   min distance to 1 = 0.3510
```

plateau 处全部 ± perturbation（8 条）经 gate 判定为 VALID_SMOOTH_FLOW。
任何离开 interior 的 perturbation 分类为 ACTIVE_SET_CHANGED（validation
-domain violation，**不是 STM error**）；不修改 QEG dynamics 强制保持
interior。

## 6. Solver / tolerance policy（G2 §11, §14）

三层 augmented 配置（20-D，DOP853；state 通道 4 atol + Φ 通道 16 psi_atol）：

| config | rtol | state atol | psi_atol | max_step |
|---|---|---|---|---|
| production_like | 1e-9 | [1e-4,1e-11,1e-7,1e-11] | **1e-11** | 20 s |
| REF-0.1 | 1e-12 | [1e-7,1e-14,1e-10,1e-14] | **1e-13** | 0.1 s |
| REF-0.05 | 1e-12 | [1e-7,1e-14,1e-10,1e-14] | 1e-13 | 0.05 s |

**psi_atol 小收敛审计**（QEG window，production 底包，psi_atol ∈
{1e-9,1e-11,1e-13}）：恢复 Phi 与 REF-0.1 最大差 1.4e-9–7.7e-9，即
Phi 结果对 psi_atol 在该范围**不敏感**（主导误差来自 state 通道的
production rtol=1e-9，而非 Φ 通道）。默认值（1e-11 / 1e-13）有据。

## 7. Computational vs scientific scaling（G2 §12, §13）

G2 为 20-D augmented conditioning 可选用 **computational integration
scaling**（`integration_scaling` / `computational_scaling`，禁止称
"canonical predictability scaling"）：

```
Psi = S_num^-1 Phi S_num,   A_num = S_num^-1 A S_num,   Psi(t0) = I
恢复：Phi = S_num Psi S_num^-1
```

**Representation audit**（每个 window，REF-0.1 下 S ∈ {I, A, B, C}，
恢复 raw Phi 后比较 vs identity）：

| mode | Φ_I−Φ_A | Φ_I−Φ_B | Φ_I−Φ_C | 判定 |
|---|---|---|---|---|
| ENTRY_CAPTURE | 3.7e-8 | 1.0e-7 | 6.8e-8 | **PASS**（<1e-6） |
| QEG_INTERIOR | 6.3e-9 | 3.0e-9 | 5.1e-9 | PASS |
| SANGER_ATM | 2.8e-8 | 7.2e-8 | 1.1e-7 | PASS |
| SANGER_VAC | 1.9e-9 | 2.8e-9 | 1.5e-9 | PASS |

→ **computational scaling representation invariant**。但这**不能**用于
声称某个 S 是科学正确 FTLE scaling：

```
CANONICAL_SCIENTIFIC_SCALE_NUMERIC_VALUES -> PENDING（G5 决定）
```

## 8. Fundamental STM properties（G2 §15 验证）

- Phi(t0,t0) = I：augmented z0 含单位块（测试锁定）。
- 差分方程：`Phi_dot = A(x) Phi`（augmented phidot vs A@Phi 逐位一致）。
- **short-time** `Phi(t0+dt) ≈ I + A(x0)·Δt`（dt = 1e-2 s）：

| mode | max abs residual | 判定 |
|---|---|---|
| ENTRY_CAPTURE | 6.8e-5 | PASS |
| QEG_INTERIOR | 4.5e-4 | PASS |
| SANGER_ATM | 9.6e-5 | PASS |
| SANGER_VAC | 1.7e-5 | PASS |

## 9. Structural STM invariants（G2 §16, §17）

- **theta symmetry**：`Phi(:, θ0) = [0,1,0,0]^T`（所有 mode，residual = 0，exact）。
- **QEG gamma-row flow invariant**：`Phi[γ,:] = [0,0,0,1]`（QEG interior
  window，residual = 0，exact）。

## 10. Reference convergence / self-stability（G2 §24）

| mode | production vs REF-0.1 Φ | REF-0.1 vs REF-0.05 Φ | 判定 |
|---|---|---|---|
| ENTRY_CAPTURE | — | max abs 4.8e-8 / material rel 8.2e-12 | PASS |
| QEG_INTERIOR | — | max abs 1.6e-9 / material rel 1.0e-14 | PASS |
| SANGER_ATM | — | max abs 1.0e-7 / material rel 5.4e-12 | PASS |
| SANGER_VAC | — | max abs 5.8e-10 / material rel 2.9e-15 | PASS |

`Phi_0.1 ≈ Phi_0.05` 成立 → reference self-stability 满足。

## 11. Trajectory consistency（G2 §19）

assign same mode/x0/t_span/solver：standalone frozen nonlinear RHS vs
20-D augmented state channel 在 t1 处最大 state 误差：

```
ENTRY 9.3e-10, QEG 5.5e-12, ATM 4.7e-9, VAC 3.7e-9  （全部 << solver accuracy）
```

## 12. Semigroup / composition（G2 §18）

`Phi(t1,t0) vs Phi(t1,tm) Phi(tm,t0)`（tm = midpoint，REF-0.1 / production
分开报告）：

| mode | max abs | material rel | validation-scaled | 判定 |
|---|---|---|---|---|
| ENTRY_CAPTURE | 2.9e-8 | 5.4e-12 | 1.5e-13 | PASS |
| QEG_INTERIOR | 3.7e-9 | 7.2e-15 | 6.1e-15 | PASS |
| SANGER_ATM | 5.5e-8 | 1.1e-12 | 1.4e-12 | PASS |
| SANGER_VAC | 4.7e-10 | 2.6e-15 | 4.1e-16 | PASS |

## 13. Nonlinear fixed-time FD validation（G2 §20–§23）

对每个 window 的每个 initial-state column（δr0 / δθ0 / δv0 / δγ0）：

```
D_j^NL = [x(t1; x0 + ε_j e_j) − x(t1; x0 − ε_j e_j)] / (2 ε_j)
```

ε 基 = G0 candidate-B `[100 m, 1e-5 rad, 1 m/s, 1e-4 rad]`（**仅 FD research
step**，不是 canonical scientific scaling），multiplier sweep
`{1e-3,3e-3,1e-2,3e-2,1e-1,3e-1,1,3,10}`。

**Slope / plateau**（production-FD vs REF-0.1 Phi）：

| mode | plateau mult | plateau max rel | mult=10 rel |
|---|---|---|---|
| ENTRY_CAPTURE | 0.03 | 1.9e-8 | 9.6e-4 |
| QEG_INTERIOR | 0.01 | 2.4e-9 | 1.1e-3 |
| SANGER_ATM | 0.03 | 2.2e-8 | 2.3e-3 |
| SANGER_VAC | 0.1 | 3.3e-10 | 5.4e-7 |

→ 小步长 solver-noise/roundoff 主导、中部收敛 plateau、大步长 nonlinear
truncation 主导，三层结构清晰。

**Reference-grade FD agreement**（strict REF-0.1 非线性积分，plateau
multiplier，vs REF-0.1 Phi）：

| mode | max abs | material rel | validation-scaled | 判定 |
|---|---|---|---|---|
| ENTRY_CAPTURE | 7.8e-3* | 1.04e-6 | 2.5e-7 | PASS（<1e-5） |
| QEG_INTERIOR | 1.9e-2* | 2.6e-8 | 1.6e-8 | PASS |
| SANGER_ATM | 1.7e-2* | 3.2e-8 | 4.1e-7 | PASS |
| SANGER_VAC | 1.7e-2* | 4.7e-9 | 4.2e-8 | PASS |

* max abs 由 theta-column 的 off-diagonal（理论零项）与其他近零项主导
（绝对 residual 报告）；**material entries 相对误差**全部 ≪ 1e-5 target，
多数 1e-8–1e-11。validation-scaled error `|S⁻¹(D^NL−Φ)S|∞ / max(1,…)` 为
**VALIDATION NORMALIZATION ONLY**，非 predictability ranking。

### 错误分类（G2 §22 gate）

全部 9 multiplier × 4 column 的 ± perturbation 均为 `VALID_SMOOTH_FLOW`
（含 QEG，全部 interior 保持）。无 ACTIVE_SET_CHANGED /
MODE_WINDOW_INVALID / NONPHYSICAL_STATE / NUMERICAL_FAILURE。

## 14. 实现的 API

`src/hyptraj/predictability/stm.py`（G1 基础上扩展）：

```
pack_augmented(x, phi) / unpack_augmented(z)      # 20-D，C-order
make_augmented_rhs(mode, env, vehicle, k, computational_scaling)
integrate_continuous_stm(mode, x0, t_span, env, vehicle, k, solver,
                         computational_scaling, research_domain_guard)
integrate_standalone_mode(...)                    # frozen nonlinear consistency
computational_scaling_transform(phi, s_num, inverse)
StmSolverConfig / stm_production_like_config / stm_strict_reference_config /
stm_companion_reference_config
ContinuousStmResult(mode, t0, t1, x0, x1, phi, solver, computational_scaling)
variational_rhs / state_transition_initial_value（G1 保留）
```

`src/hyptraj/predictability/perturbation.py`（G2 激活）：

```
FlowValidationClass（VALID_SMOOTH_FLOW / ACTIVE_SET_CHANGED /
                     MODE_WINDOW_INVALID / NONPHYSICAL_STATE / NUMERICAL_FAILURE）
fixed_time_nonlinear_difference(...)
gate_perturbed_trajectory(...)
epsilon_sweep_fd(mode, x0, t_span, ..., phi_stm, base_step, multipliers)
validation_scaled_error(fd, phi, scales)          # VALIDATION NORMALIZATION ONLY
FD_BASE_STEP / FD_MULTIPLIERS
```

## 15. 已知限制

- G1 atmospheric Jacobian 定义域 `h > 0`；G2 acceptance windows 满足
  `h > 0` throughout；`integrate_continuous_stm` 内置 `research_domain_guard`
  （仅检查，不修改 frozen RHS）。
- 原始 dimensional STM 的 2-norm / SVD / 大奇异值 **不**作为科学结论
  （G0 claim boundary）；scaled SVD/FTLE 属 G5。

## 16. G3 handoff

连续 mode 内 `Phi(t1,t0)` 已被 augmented 积分 + 三类 solver + 独立
nonlinear FD + semigroup 验证。G3 下一层：跨 hybrid event 的
saltation 更新与 event-time sensitivity —— 现已有 `HybridEventRecord`
的 f_minus / f_plus / normal 元数据可直接消费。

## 17. G2 acceptance

- [x] augmented integrator（20-D, C-order, DOP853 三层 config）
- [x] reference self-stability（0.1 vs 0.05，max abs < 1e-6）
- [x] trajectory consistency（standalone vs augmented < 1e-3）
- [x] semigroup / composition（< 1e-6 abs）
- [x] nonlinear FD plateau（所有 mode 明确 plateau，material rel ≪ 1e-5）
- [x] ENTRY_CAPTURE / QEG / SANGER_ATM / SANGER_VAC STM 验证全 PASS
- [x] theta invariant（= [0,1,0,0]^T exact）
- [x] QEG gamma-row invariant（= [0,0,0,1] exact）
- [x] computational scaling reconstruction invariance（I/A/B/C < 1e-6）
- [x] short-time I+A dt sanity
- [x] psi_atol 收敛审计（默认 1e-11 / 1e-13 有据）
- [x] QEG branch gate（nominal + 全部 accepted perturbations interior）
- [x] snapshot `tests/data/phase_g2_continuous_stm_v1.json` 冻结
- [x] G0/G1 tests 仍 PASS；完整 pytest PASS
- [x] frozen physics / G1 Jacobian semantics 零修改
- [x] 无 saltation / hybrid STM / FTLE / event-time scope leak

**G2 = COMPLETE；等待人工验收后再进入 G3。**
---

## 18. G2R — corrective patch（validation gate）

状态：**COMPLETE**（2026-08-18；commit "修正 Phase G2 双侧扰动与连续模式窗口验证门"）

修正两个 validation-contract 缺陷，**不改动** G2 的数学结果：

### Issue 1 — centered FD 双侧 gate（修复前只 gate +ε）

```
column_valid = （cls_plus == VALID_SMOOTH_FLOW） AND （cls_minus == VALID_SMOOTH_FLOW）
```

任一测 invalid → column rejected，不得进入 STM error metric。machine-readable
输出保留每列的 `classification_plus` / `classification_minus` 以及 derived
pair `classification`（VALID_SMOOTH_FLOW / PAIR_INVALID）。

### Issue 2 — MODE_WINDOW_INVALID 真正生效（修复前为保留枚举）

validation observer 复用 frozen event surfaces 检测 perturbed trajectory
是否在 window 内跨过 true-switch：

```
ENTRY_CAPTURE   make_capture_event（gamma=0, dir+1）          → 跨过则 MODE_WINDOW_INVALID
SANGER_ATM      make_atmosphere_exit_event（h-h_atm, dir+1）  → 跨过则 MODE_WINDOW_INVALID
SANGER_VAC      make_atmosphere_entry_event（h-h_atm, dir-1） → 跨过则 MODE_WINDOW_INVALID
QEG_INTERIOR    仍由 active-set gate（0<u_L*<1；RTI u_L*→1 自然捕获）→ ACTIVE_SET_CHANGED
```

diagnostic events（Sanger pullout / VAC apogee，gamma=0）不是 true switch，
不导致 invalid。仅观察 frozen surface，无 hybrid propagation / reset /
RHS 切换 / saltation。

### Revalidation（原 G2 windows）

| mode | plateau mult | plus classes | minus classes | pair_valid | FD/STM acceptance |
|---|---|---|---|---|---|
| ENTRY_CAPTURE | 0.03 | 4×VALID | 4×VALID | True | 不变（rel 1.04e-6） |
| QEG_INTERIOR | 0.01 | 4×VALID | 4×VALID | True | 不变（rel 2.6e-8） |
| SANGER_ATM | 0.03 | 4×VALID | 4×VALID | True | 不变（rel 3.2e-8） |
| SANGER_VAC | 0.1 | 4×VALID | 4×VALID | True | 不变（rel 4.7e-9） |

G2 snapshot 中所有 STM 矩阵 / solver convergence / semigroup / scaling /
psi_atol 数据与 7445378 逐位一致（69 fields，0 mismatch）；仅新增
per-side / pair 字段。

**G2R = COMPLETE；G2 整体等验收后再进入 G3。**

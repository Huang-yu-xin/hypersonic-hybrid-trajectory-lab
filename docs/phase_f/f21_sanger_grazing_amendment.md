# F2.1 — Sanger Grazing-Transition / Event-Qualification Observability Amendment

状态：**COMPLETE**（2026-08-16）

Branch: `feature/phase-f-gamma-k-sensitivity`
Starting commit: `74197a0`（F2 infrastructure）
Commit: `F21_COMMIT`（见 §Git audit）

## Original blocker

F2 条件扩域 round 1 中，frozen `integrate_sanger_hybrid` 在
(gamma0=-7.75 deg, K=3.125) 抛出：

```
RuntimeError: SRTI candidate above the atmosphere boundary:
h = 100016.949 m > h_atm = 100000.0 m.
```

（`sanger_trajectory.py` SRTI qualification：`h_e > h_atm + 1 m` 直接 raise。）

## Frozen Sanger semantics

ATM segment 注册 4 个 frozen events（`sanger_trajectory.py`）：

| event | root | direction | terminal |
|---|---|---|---|
| atmosphere_exit | G = h - h_atm | +1 | True |
| pullout（诊断）| G = gamma | +1 | False |
| SRTI candidate | G = gamma | -1 | True |
| ground | G = h | -1 | True |

formal SRTI qualification：candidate 在 ATM 中发生、当前 pass 已有 pullout、
无先行 exit、candidate 高度低于大气边界。任何违反 → RuntimeError（frozen）。

**Phase-D frozen 语义不允许把 "SRTI above atmosphere" 当作物理 regime**：
若轨迹真正上穿 h_atm，应先 ATM→VAC，而不是继续 ATM 到上方 gamma root。

## Grazing geometry

Atmosphere interface: `G_h(x) = h - h_atm`，`dG_h/dt = dh/dt = v sin(gamma)`。
SRTI candidate: `gamma = 0`。skip-count transition 的 limiting geometry：

```
G_h = 0  AND  gamma = 0   =>   dG_h/dt = 0
```

定义为 **Sanger atmosphere-interface grazing / tangency transition**。
F2.1 的表述限定为：*the observed blocker is consistent with a grazing
event-resolution problem* —— 已由 strict numerical audit 确认（见下）。

## max_step diagnostic

blocker 点 (gamma0=-7.75, K=3.125)，DOP853、rtol=1e-9、production atol：

| case | max_step [s] | status | terminal kind | skip | t_term [s] | modes |
|---|---|---|---|---|---|---|
| PROD-20 | 20 | RuntimeError | — | — | — | — |
| P-10 | 10 | success | srti | 3 | 1534.399532 | 7 |
| P-5 | 5 | success | srti | 3 | 1534.399531 | 7 |
| P-2 | 2 | success | srti | 3 | 1534.399531 | 7 |
| P-1 | 1 | success | srti | 3 | 1534.399531 | 7 |
| P-0.5 | 0.5 | success | srti | 3 | 1534.399531 | 7 |
| P-0.2 | 0.2 | success | srti | 3 | 1534.399531 | 7 |
| P-0.1 | 0.1 | success | srti | 3 | 1534.399531 | 7 |

结论：max_step ≤ 10 即恢复；**production max_step=20 漏检一个极浅的
atmosphere excursion**（hypothesis 证实）。

## High-precision reference

| case | rtol | atol | max_step | terminal | skip | t_term [s] |
|---|---|---|---|---|---|---|
| REF-0.1 | 1e-12 | [1e-7,1e-14,1e-10,1e-14] | 0.1 | srti | 3 | 1534.399531 |
| REF-0.05 | 1e-12 | 同上 | 0.05 | srti | 3 | 1534.399531 |

**reference self-stable = YES**（terminal kind / skip_count / exact
topology 相同，t_term 一致到 1e-6 s 量级）。F2.1 HARD scientific gate 通过：
blocker 的 physical side 被数值解析，真实拓扑 = **SRTI_N3**。

REF-0.05 事件序列（关键部分）：

```
third ATM pass:  entry t=978.369  pullout t=1077.220 (h=41075)
                 atmosphere_exit  t=1235.635 (h=100000, gamma=+0.002684)
                 vacuum_apogee    t=1238.111 (h=100016.9, gamma=0)   <-- 极浅 VAC 弧
                 atmosphere_entry t=1240.588
fourth ATM pass: pullout t=1400.997 (h=40798)  SRTI t=1534.400 (h=83152)
```

第三个 VAC 弧 apogee 仅高于 h_atm **16.9 m**、VAC 持续约 5 s。production
step=20 s 的一个 step 跨过整个 excursion：exit root 端点同号漏检；gamma
下穿 root（物理上 = vacuum apogee，h=100016.9）被 SRTI candidate 事件捕获
→ h > h_atm → frozen qualification RuntimeError。

## Event-resolution mechanism

- **A. 真实 SRTI**：local atmospheric maximum remains below h_atm → 正常
  qualification（不 recovery）。
- **B. 真实 additional skip**：trajectory 在 local maximum 前退出大气 →
  exit 被 solve_ivp 返回（SOLVER_EVENT）。
- **C. grazing boundary**：maximum touches interface tangentially
  （G_h=0 且 gamma=0）→ 数值上无法稳定分配 → `SANGER_GRAZING_BOUNDARY`
  marker（非 stable regime，F3 P0）。
- **D. numerical event-resolution failure**：production solver 漏检极浅
  interface excursion（本 blocker）→ dense-output root recovery。

## Dense recovery algorithm

触发条件（全部满足才 recovery）：

1. ATM solve 返回 SRTI candidate 且 `h_candidate > h_atm`；
2. atmosphere_exit 未被 solve_ivp 返回；
3. 当前 pass 已有 pullout 且 `h_pullout < h_atm`。

算法：在 `[t_pullout, t_candidate]` 上用已计算的 ATM dense interpolant
`sol.sol(t)` 以 **brentq** 定位 `h(t) - h_atm = 0` 的上穿 root。禁止
nearest sampled row / linear interpolation / epsilon perturbation。

recovered root 必须满足：

- `t_pullout < t_exit_rec < t_candidate`；
- `|h(t_exit_rec) - h_atm| < 1e-6 m`（residual tolerance）；
- `gamma(t_exit_rec) > 0` 且 `dh/dt = v sin(gamma) > 0`（真 transverse
  upward exit）。

任一项失败 → **不 recovery**，terminal kind =
`GRAZING_OR_UNRESOLVED_EVENT`（structured），进入 strict-reference
decision。

recovered switch：ATM segment 截断于 t_exit_rec；`x_plus = x_minus`（严格
连续，与 normal exit 相同）；后续为 frozen SANGER_VAC。事件记录
`event_resolution = "DENSE_RECOVERED"`；`f_minus`/`f_plus`/`normal` 与
normal exit 完全相同（未来 saltation metadata 一致）。**不创造新的
physical switch**。

## Baseline equivalence

p0 = (-5 deg, 3)：research integrator vs frozen `integrate_sanger_hybrid`
— terminal=SRTI、skip=2、全部 event times/states 一致（< 1e-9）、
segments 5=5、**recovered count = 0**。baseline 不触发 recovery。

## F1 equivalence

F1 全部 33 unique points：research vs frozen — same terminal kind / same
skip_count / same event sequence / same exact topology signature。
**33/33 PASS，recovered count = 0**（F1 主域无 recovery 点）。

## D0 equivalence

canonical F2 rerun（v2 cache）验证：主域 289 点 compact regime 与旧 v1 map
逐点一致（runner 内置 F1 consistency gate + 新旧 map 对比见 F2 报告
§Blocker resolution）。Qian 保持 289/289 QIAN_RTI。

## Blocker-point validation

research integrator at (gamma0=-7.75, K=3.125)（production numerics）：

| quantity | value | vs REF-0.05 |
|---|---|---|
| recovered exit time | 1235.634917 s | 1235.634920 s（Δ≈3e-6 s）|
| interface residual | 0.0 m | — |
| exit gamma | +0.002684 rad | +0.002684 |
| exit dh/dt | +13.649 m/s | — |
| candidate overshoot | 16.949 m | 16.9 m（apogee 高度差）|
| terminal kind | srti | srti |
| skip_count | 3 | 3 |
| terminal time | 1534.399532 s | 1534.399531 s |
| exact topology | 7 modes / 3 VAC arcs | identical |

**blocker recovered = YES**；recovered event 与 strict reference 达到合理
numerical agreement；terminal topology 一致。

## Interpretation boundary

- F2.1 证实：blocker = production event-resolution failure（漏检极浅
  excursion），physical topology = SRTI_N3。
- `candidate_overshoot_m` 是 qualification probe / numerical diagnostic，
  **不是** physical post-exit state。
- `SANGER_GRAZING_BOUNDARY` 不是 stable trajectory regime；它是
  numerical-resolution 下的 grazing transition set 的 categorical
  boundary marker，禁止插值、禁止强制分配给 N 或 N+1。
- 禁止用 arbitrary 物理阈值（如 |M| < 100 m）定义 grazing band；
  boundary tolerance 基于 REF-0.1 vs REF-0.05 与 recovered-event
  numerical uncertainty。`_SRTI_ALTITUDE_ASSERT_TOL_M = 1 m` 只是 frozen
  assertion tolerance，不是物理 grazing band 宽度。
- signed grazing margin（candidate_overshoot）暂不冻结为最终 F3 metric；
  F3 开始时再决定是否正式定义 `Phi(gamma0, K)`。

## F2.1 acceptance

    [x] strict reference stable（REF-0.1 == REF-0.05：SRTI_N3）
    [x] blocker physical topology resolved（SRTI_N3，非硬编码，以 reference 为准）
    [x] grazing mechanism documented
    [x] frozen Sanger source unchanged（sanger_trajectory/events/hybrid 零修改）
    [x] dense recovery validated（brentq + transversality 检查）
    [x] every recovered point reference verified（canonical F2 阶段执行）
    [x] baseline equivalence PASS（逐位一致，零 recovery）
    [x] F1 33-point equivalence PASS（零 recovery）
    [x] D0 289 equivalence PASS（canonical rerun 验证）
    [x] no exception-text parsing（recovery 基于 structured candidate/pullout/interface）
    [x] candidate above boundary 不成为 SRTI（转为 exit+VAC，SRTI 在最终 pass 内）
    [x] candidate below boundary 不触发 recovery
    [x] grazing/unresolved case structured（GRAZING_OR_UNRESOLVED_EVENT）
    [x] x_plus = x_minus（状态严格连续）
    [x] 未来 hybrid metadata 保留（f_minus/f_plus/normal 与 normal exit 相同）
    [x] frozen integrate_sanger_hybrid untouched / Phase E regression unchanged
    [x] all tests PASS

## 附录：新模块接口

`src/hyptraj/simulation/sanger_research_trajectory.py`：

- `integrate_sanger_research_trajectory(env, vehicle, initial, control,
  solver=PRODUCTION_SOLVER_CONFIG, dense_output_collector=None,
  max_time=5000, max_segments=50) -> SangerResearchTrajectory`
- `SangerResearchTrajectory`：包装 frozen `SangerHybridTrajectory`
  （downstream 分析全部兼容），附加 `recovered_events` /
  `grazing_diagnostics` / `event_resolution` / `solver_config` /
  `initial_conditions`。
- `recover_interface_exit(sol, env, t_pullout, t_candidate,
  candidate_overshoot_m) -> RecoveredInterfaceEvent | None`（纯函数）。
- Terminal kind 新增：`GRAZING_OR_UNRESOLVED_EVENT`。
- 版本常量：`SANGER_RESEARCH_EVENT_RESOLUTION_VERSION = "v1"`（进入 F2
  cache v2 provenance）。

# Phase G — Finite-Time Local Predictability of Hybrid Trajectories

状态：**G0 COMPLETE / ACCEPTED**；**G1 COMPLETE / ACCEPTED**；
**G2 COMPLETE**（2026-08-18）
分支：`feature/phase-g-predictability`
上游冻结基线：`phase-f-v1.0` = `gamma-k-sensitivity-v1.0` =
`96253f1ef7785764d8da3156d7d614d2b244b577`（Phase F 最终冻结 commit）。
G0 commit：`9db3a35`；G1 commit：`d1b3030`；G2 commit：见 git log（G2 accept 后创建）。

G0/G1/G2 **不创建 final tag**（不创建 `phase-g-v1.0` / `predictability-v1.0`）。
Phase A–F 全部 frozen tags 未移动、未删除、未重写。

## 1. Phase G 目标

Phase G 研究混合轨迹的 **finite-time local predictability**（有限时间
局部可预测性）：

- 连续 mode 内的 STM（state transition matrix）`Phi(t, t0) = d x(t) / d x_0`；
- hybrid mode switch 的 flow-map derivative（saltation）；
- 固定时间 / 事件条件（event-conditioned）两类 predictability 研究问题；
- 基于 scaled STM 的 `sigma_max` / condition number / dominant singular
  vectors / FTLE；
- grazing / transversality-loss 邻域（G6）的可预测性语义边界。

Phase G **不是**：asymptotic chaos 分析、全局稳定性证明、飞行包线
认证、概率不确定性、Monte Carlo、优化。

## 2. Phase G roadmap（G1–G7 建议，G0 只冻结语义，不实现）

| 阶段 | 内容 | G0 状态 |
|---|---|---|
| **G0** | Predictability Protocol Freeze（state / 事件分类 / scaling / 约定 / validation） | **COMPLETE / ACCEPTED** |
| **G1** | continuous Jacobian `A_m = df_m/dx` + FD 验证 + minimal variational algebra | **COMPLETE / ACCEPTED** |
| **G2** | 连续 mode STM / augmented 20-D variational integrator / 非线性 FD + semigroup + scaling audit | **COMPLETE**（`g2_continuous_stm.md`） |
| G3 | hybrid saltation / event-time sensitivity 数值验证 | PENDING（不实现） |
| G4 | 跨事件 STM 与 nonlinear FD 对照（topology gate） | PENDING |
| G5 | fixed-time 与 terminal predictability 指标（scaling audit） | PENDING |
| G6 | grazing / transversality-loss 分析（B0–B4 anchors） | PENDING |
| G7 | 最终报告 / 冻结 | PENDING |

G0–G2 硬性禁止：saltation、hybrid/global STM、production FTLE、
Monte Carlo、optimization、gamma0-K 域重扫（G3–G6 范围）。

## 3. 文档与代码索引

- `docs/phase_g/predictability_protocol.md` —— **G0 权威协议**（human-readable
  source of truth）
- `docs/phase_g/g1_continuous_variational.md` —— **G1 连续变分动力学报告**
  （推导 / API / 验证 / 误差表 / invariants / G2 handoff）
- `docs/phase_g/g2_continuous_stm.md` —— **G2 连续 STM 验证报告**
  （augmented 系统 / 三层 solver / computational vs scientific scaling /
  semigroup / 非线性 FD / 结构 invariants / G3 handoff）
- `src/hyptraj/predictability/protocol.py` —— machine-readable 协议负载
  （`machine_readable_protocol()`，schema `phase-g-predictability-protocol-v1`）
- `src/hyptraj/predictability/event_metadata.py` —— 事件分类学元数据冻结
  （7 个事件，与 frozen event factories 交叉校验）
- `src/hyptraj/predictability/scaling.py` —— state scaling 候选（A/B/C）
  与 canonical-scaling 状态
- `src/hyptraj/predictability/jacobian.py` —— **G1** 连续 mode Jacobians
  （A_atm / A_vac / A_QEG,int）、QEG active-set、FD oracle、误差统计、
  代表状态提取
- `src/hyptraj/predictability/stm.py` —— **G1/G2** minimal variational RHS
  + 20-D augmented 连续 STM integrator（pack/unpack、三层 solver config、
  computational scaling、result dataclass）
- `src/hyptraj/predictability/perturbation.py` —— **G2** fixed-time nonlinear
  FD / epsilon sweep / smooth-flow gate（FlowValidationClass）/ 归一化误差
- `tests/test_predictability/test_phase_g0_protocol.py` —— G0 语义测试
- `tests/test_predictability/test_phase_g1_jacobian.py` —— G1 Jacobian 测试
- `tests/test_predictability/test_phase_g2_continuous_stm.py` —— G2 STM 测试
- `tests/data/phase_g1_continuous_jacobian_v1.json` —— G1 数值审计 snapshot
- `tests/data/phase_g2_continuous_stm_v1.json` —— G2 数值审计 snapshot

未来 G4–G6 模块（`ftle.py` / `metrics.py` / `observability.py`）保持为
空占位，G2 未实现。

## 4. 与其他 Phase 的关系

- **Phase F** 研究 parameter-output Jacobian `d y / d(gamma0, K)`
  （fixed-topology 内）；**Phase G** 研究 state-map Jacobian
  `d x(t) / d x_0` 与 hybrid switch 后的 flow-map derivative。两者严格区分。
- Phase F 的 exact event metadata（F2.1 recovered events、F3 certified
  extremals、F4 representatives、F7A audit anchors）是 Phase G 的事件级
  输入，Chapter 5 给出 G0 已确认的复用清单。
- 生产数值继续使用 `PRODUCTION_SOLVER_CONFIG`（trajectory baseline）；
  Phase-G variational numerics 独立验证（延迟到 G2/G5）。

## 5. G0 输出摘要

- 冻结 G0 协议 semantics（state / 事件分类 / saltation / event-time /
  scaling 约定 / grazing policy / claim boundaries）—— G1/G2 零修改。
- **G1** 建立并验证 4 个 continuous mode 的解析 Jacobian（A_atm /
  A_vac / A_QEG,int），independent FD oracle（4 modes × 4 samples，best
  relative error ≪ 1e-6），结构 invariants 全 PASS，minimal variational
  RHS `dphi = A @ phi`。
- **G2** 建立 20-D augmented continuous STM integrator（单连续 mode /
  fixed elapsed time / initial perturbation），三层 solver（production /
  REF-0.1 / REF-0.05），reference self-stability、standalone-vs-augmented
  trajectory consistency、semigroup、非线性 centered-FD（9-multiplier sweep
  + plateau，material rel ≪ 1e-5）、theta / QEG-gamma-row 结构 invariant、
  computational scaling reconstruction invariance（I/A/B/C）、QEG branch
  gate 全部 PASS。scientific canonical scale 仍 PENDING（G5）。
- 新增测试 `tests/test_predictability/test_phase_g2_continuous_stm.py`
  （55 tests）与 snapshot `tests/data/phase_g2_continuous_stm_v1.json`；
  完整 pytest 通过（含 G0/G1 的 505 旧回归 + G2 新增）。

**Phase G0 + G1 + G2 = COMPLETE；等待人工验收后再进入 G3。**
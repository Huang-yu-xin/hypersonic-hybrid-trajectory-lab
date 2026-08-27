# M3-G-v1 Validity Audit

> **Stage:** M3-G-v1 ｜ **Audit date:** 2026-08-27 ｜ **Data:** `results/phase_m3g_v1/layer_a/m3g_v1_confirmatory_v1.json`（192 试次，73s）
> **Gate audit JSON:** `results/phase_m3g_v1/summary/gate_audit_m3g_v1.json`（schema `raretopo-m3g-v1-gate-audit-v0`）

---

## 1. 有效性证据矩阵

| 项 | 证据 |
|---|---|
| prereg 先于科学 | 提交 `55fb5ec`（task/protocol/confirmatory_seeds）早于任何确认性调用（检查点确认：confirmatory scientific runs = 0 时报告） |
| 确认种子未见且不相交 | `[3031..3038]` ∩ `[2026..2033]` = ∅（配置断言 + 测试 `test_m3gv1_confirmatory_seeds_disjoint` + 运行时守卫） |
| sealed 基准不变 | freeze 自校验哈希 `b613f45dc664…` 一致（测试 + 批元数据） |
| 候选固定 | GA1 / rho=0.02 / pilot M2_hat：门签名白名单（`{direction, g_hat, m2_pilot, delta_theta, rho, arm_legal}`）、AST 标识符扫描无 eval/arms/oracle/GA2/rho_grid/calibration（4 项结构测试） |
| 方向奇偶 | `test_m3gv1_direction_parity`（确认种子 3031 合成 pilot，v1 管道 gradient 块与冻结 `gradient_decision` 逐位一致）+ `v1_trial_gate` 运行时奇偶块 |
| 全量 pytest | 阶段二 **1179 passed / exit 0**（13 项 v1 测试在内） |
| 192 试次完整 | 24 态 × 8 种子，无缺失单元；`V1_0_validity.n_trials = 192` |
| eval-M2 不进在线门 | 签名白名单 + 源码 AST 检查 + 行为测试（代理随 pilot 分母缩放） |

## 2. 泄漏与合法性审计

- 身份闭合 `M2 = Σ_j L_j`：**1152 臂检查 0 违例**（1e-9 容差，`validate_m3g_v1_trial_record` 全程校验）。
- 合法分母纪律：非法臂不作 win/loss/tie/base（`illegal_arms_as_base = 0`；s2=0.55 SHRINK 臂非法 → HOLD_INVALID 折叠逻辑在线生效，本批次无此类激活）。
- 无 oracle 泄漏：门/管道源无 oracle 标识符（AST）；oracle 标签仅用于记录评估（与 M3-D 记账相同）。
- 零额外调用：门只过滤冻结管道内量，各试次 call accounting 与 M3-D 相同（scientific 320k / deployable 120k）。

## 3. 统计正确性与披露

- NOT-IID；(state, seed) 配对单元；per-state 8 种子中位数 → global 24 态中位数。
- **披露（强制）**：headline 泛化 = **out-of-sample over Monte-Carlo / pilot randomness ONLY**；同一 24 proposal states 复用 ⇒ **不声称 state-level 或跨配置泛化**；无 holdout 几何/事件结构外推。

## 4. 威胁与局限

1. 结论域：单一生化 24 态基准；V1-5 在值域上未超越最优固定规则（10/24 胜，中位商 1.0000）——自适应优越性未获支持是**如实测量**，非流程缺陷。
2. WIDEN 类出现 3/64 假 HOLD（false-HOLD rate 0.047）——方向保持仍满足硬门（≥0.90），如实报告为残留成本。
3. VRF 中位 1.0304 与 M3-D 相同：仅成本效率，不构成优越性；也不声称 v1「新增」穿越（与 v0 审计措辞一致）。
4. 阈值/种子在观察结果前完全固定；无事后调参路径（停止规则列于预注册）。

## 5. 结论

有效性链完整：预注册提交 → 检查点（0 科学运行）→ 确认性评估 → 门控审计 → 泄漏/合法性审计。**V1-0..V1-4 全 PASS、V1-5 FAIL、Strong 诊断 PASS**——HOLD 恢复声明得到确认性支持，自适应价值声明不成立。
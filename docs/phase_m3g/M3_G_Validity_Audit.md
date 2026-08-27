# M3-G Validity Audit（freeze-audit 修正版）

> **Stage:** M3-G ｜ **Audit date:** 2026-08-27 ｜ **Data:** sealed batch `results/phase_m3g/layer_a/m3g_online_v1.json`（192 试次，位一致重放）
> **权威门来源:** `M3_G_Gain_Aware_HOLD_Decision_Task.md` @ `9720456` ｜ **偏差审计:** `M3_G_Protocol_Deviation_Audit.md`
> **Gate audit JSON:** `results/phase_m3g/summary/gate_audit_m3g.json`（修正版，schema `raretopo-m3g-gate-audit-v0`）
> **最终裁决:** **M3-G-v0 = NOT FREEZE READY**

---

## 1. Table A — 权威预注册门证据矩阵（commit `9720456` 原阈值）

| 门 | 判定 | 证据 |
|---|---|---|
| **M3G-0 有效性** | **PASS** | 双父 tag 解引用 == 任务文档记录（32b2856…/7bd58c5…）；任务先于科学提交（9720456）；密封基准哈希 `b613f45d…` 自校验一致；无 oracle 泄漏结构测试（决定层源无 oracle 符号，metrics 仅评估用途）；全量 pytest **1166 passed / exit 0**；标定 `extra_simulator_calls=0` |
| **M3G-1 基线奇偶** | **PASS** | 密封重放冻结基线行集与存储 M3-D layer_a **192/192 单元逐位相等，0 失配**（g_hat/g_ci_low/g_ci_high/ESS_grad/action；运行时断言，批元数据留档） |
| **M3G-2 非回归** | **PASS** | Acc3_gain = 0.7604 ≥ 0.75；WIDEN recall = 1.000 ≥ 0.90；SHRINK recall = 1.000 ≥ 0.90 |
| **M3G-3 HOLD 恢复** | **FAIL** | HOLD recall = 0.28125 < 0.50（从 0.250）；act-but-indifferent 48 → 46（−4.2% > −30% 要求） |
| **M3G-4 价值方向** | **PASS** | R_fixed(GA) = 1.0000 ≤ R_fixed(baseline CI-sign) = 1.0000（同一聚合） |
| **M3G-5 near-oracle** | **PASS** | 中位 R_M2 = 0.0000 ≤ 0.05 |
| **Strong（诊断）** | **PASS（诊断）** | deployable 中位 VRF_budget = 1.0304 > 1；**措辞 = 保留 M3-D 的 crude-MC 预算效率穿越；不构成优越性/新增效率**（值与 M3-D 相同） |

## 2. Table B — Secondary / Strengthened Audit Criteria（非原始官方门）

| 准则 | 判定 | 实测 |
|---|---|---|
| 方向保持 W/S ≥ 0.90 | PASS | 1.000 / 1.000 |
| HOLD 强恢复 ≥ 0.70 / +30pp | FAIL | 0.28125（+3.125pp） |
| 均衡质量 ≥ 0.80 / 0.80 | FAIL | 0.7604 / 0.7117 |
| M2 非劣 ≤ 1.00（优选 0.98） | PASS（硬）/ 优选未达 | 1.0000 / 1.0000 |
| 自适应价值 ≤ 0.95 且 ≥16/24 | FAIL | 1.0000；9 胜/5 负/10 平 |

## 3. 协议偏差审计摘要（详见 `M3_G_Protocol_Deviation_Audit.md`）

| 偏差 | 状态 | 证据 |
|---|---|---|
| **A — M2 分母**（评估臂 M2 ⊳ pilot M2_hat） | **MATERIAL，非 result-preserving** | exact-proxy 重放选择 **GA1-0.02 ≠ 冻结 GA2-0.0025**；封闭策略 9/192 动作分歧（归因 9/9）；分母相对差极端 ~215×；原义网格样本内 Acc3 可达 1.000 vs 冻结 0.7604 |
| **B — GA2 CI 传播**（g-CI 线性 ⊳ 逐 replicate） | 选定 rho=0.0025 下 **result-preserving（0/192）** | 修正方向诊断（逐试次取实际方向 Δθ=±0.20，pilot M2）：线性上端 vs 逐 replicate 上端决策分歧 0/192，|gap| 中位 0.001 |

```text
new simulator scientific calls = 0        （标定与重放均零新增）
raw scientific results changed? NO
benchmark / rho / controller changed? NO
```

## 4. 泄漏与完整性审计（已执行批次，事实不变）

- 重放奇偶校验：192/192，0 失配；身份闭合 M2=ΣL_j：1152 臂检查 0 违例（1e-9）；合法分母纪律（无非法臂作 base）；门 API 白名单 + 源级禁 oracle 符号；标定零模拟调用双守卫；rho 网格锁定预注册四值；冻结提交 `48fe50b` 早于密封评估。

## 5. 统计正确性（修正表述）

- 192 行 NOT-IID；(state, seed) 配对单元。
- **in-sample 披露**：标定与密封重放共用同一冻结单元 → 所测提升为 **in-sample calibrated performance**；Acc3 增量区间（n=10,000，种子 [20260827]）定名为 **descriptive paired bootstrap interval after policy selection**：均值 +0.0104，95% [0.0000, 0.0260]——不赋予独立 holdout 验证含义。

## 6. 哈希 / 溯源审计（复测一致）

| 文件 | SHA-256 | 状态 |
|---|---|---|
| m3g_online_v1.json | `647c3e6a…b2f2662` | 未变 |
| m3g_calibration_v0.json | `c8f2482e…c481c4` | 未变 |
| m3d_layer_a_v1.json | `d9b0d6b5…f6ce0` | 未变 |
| M3_D_Benchmark_Freeze.json | `b785190e…a95495` | 未变 |
| m3g_gain_gate_v0.json / m3g_protocol.json | `821dc8a9…15e49` / `8545492f…98b0d` | 未变 |
| exact_proxy_calibration_replay.json | （新增审计产物） | 新增 |

## 7. 威胁与局限

1. 结论域 = 单一生化 24 态基准；无跨基准外推。
2. **操作化替代改变结论**（Deviation A 实质）→ 已执行批次的科学检验地位降级为「特定操作化策略的描述性研究」。
3. 残余误差源（包络内）均未被触发：方向层位一致、门不翻转、决策层无 oracle、PASS/FAIL 仅基于密封批次测量。
4. 全量 pytest 证据：1166 passed / exit 0（修正轮复测见 §8）。

## 8. 测试证据（修正轮）

- 靶向 M3-G 测试：22 passed。
- 全量 pytest：见修正轮产物记录（collected/passed/failed/exit）。

## 9. 结论

有效性链事实（冻结→标定零模拟→冻结提交→密封评估→位一致→泄漏审计）全部成立；**权威门 5/6 PASS + Strong 诊断 PASS，M3G-3 FAIL → 分支 C**；叠加协议偏差审计 → **NOT FREEZE READY**：修正路径为预注册实现直接采用原义代理并重走完整预注册周期。
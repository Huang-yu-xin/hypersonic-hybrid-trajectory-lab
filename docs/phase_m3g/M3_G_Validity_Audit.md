# M3-G Validity Audit

> **Stage:** M3-G ｜ **Audit date:** 2026-08-27 ｜ **Data:** sealed online batch `results/phase_m3g/layer_a/m3g_online_v1.json`（192 试次，160s，位一致重放）
> **Gate audit JSON:** `results/phase_m3g/summary/gate_audit_m3g.json`（schema `raretopo-m3g-gate-audit-v0`）

---

## 1. 证据矩阵（M3G-0..5 + Strong）

| 门 | 判定 | 证据 |
|---|---|---|
| **M3G-0 有效性** | **PASS** | 双父 tag 解引用提交 == 任务文档记录（32b2856…/7bd58c5…）；任务先于科学提交（9720456）；标定仅用存储数据；标定期间额外模拟调用 = 0（monkeypatch 守卫测试）；标定冻结 `48fe50b` 先于密封评估提交；无 oracle 泄漏（结构测试：gate/proxy 源禁 oracle 符号，metrics 仅评估用途）；全量 pytest **1166 passed / exit 0**；密封基准哈希 `b613f45d…` 自校验一致 |
| **M3G-1 方向保持** | **PASS** | WIDEN recall = 1.000（64/64），SHRINK recall = 1.000（64/64），≥ 0.90 硬门 |
| **M3G-2 HOLD 恢复** | **FAIL** | HOLD recall = 0.28125（需 ≥ 0.70）；vs 冻结 M3-D 提升 +3.125pp（需 ≥ +30pp） |
| **M3G-3 均衡质量** | **FAIL** | 均衡精度 0.7604（需 ≥ 0.80）；macro-F1 0.7117（需 ≥ 0.80） |
| **M3G-4 M2 非劣性** | **PASS** | 池化中位数 M2(M3G)/M2(M3D) = 1.0000 ≤ 1.00（层级聚合亦 = 1.0000）；优选 ≤ 0.98 未达成（单独报告，非硬门） |
| **M3G-5 自适应价值** | **FAIL** | 最优固定规则 = ALWAYS_WIDEN；中位数 M2(M3G)/M2(BEST FIXED) = 1.0000（需 ≤ 0.95）；逐态种子中位胜 9/24（需 ≥ 16；5 负 10 平） |
| **STRONG（预算 VRF）** | **PASS（不作优势表述）** | deployable 会计下中位 VRF_budget = 1.0304 > 1；按 M3-D 教训，仅报告成本效率，**不构成自适应优越性** |

### 任务文档（committed task）交叉引用门

| 条目 | 值 | 判定 |
|---|---|---|
| Acc3_gain ≥ 0.75（非回归） | 0.7604 | ✓ |
| act-but-indifferent 相对下降 ≥ −30% | 48 → 46（−4.2%） | ✗ |
| near-oracle 中位 R_M2 ≤ 0.05 | 0.0000 | ✓ |
| value-direction：R_fixed(GA) ≤ R_fixed(baseline) | 1.0000 ≤ 1.0000 | ✓（不劣于） |

## 2. 泄漏与完整性审计

- **重放奇偶校验**：192/192 单元，冻结 gradient 块（g_hat/g_ci/ESS/action）与存储 M3-D Layer-A **逐位相等，0 失配**（运行时断言，证据入批元数据）。
- **身份闭合** `M2 = Σ_j L_j`：1152 次臂检查（192×6），相对容差 1e-9，**0 违例**；`validate_m3g_trial_record` 全程校验。
- **合法分母**：仅合法臂进入聚合；无非法臂作为 base/平手处理（s2=0.55 的 SHRINK 臂非法 → 确定性折叠 HOLD_INVALID 逻辑在线生效；本批次无此类激活，0 折叠，机制测试覆盖）。
- **无 oracle 泄漏**：门 API 签名白名单（direction/variant/rho/g_hat/g_ci_* /m2/delta_theta/arm_legal）；决策层源无 oracle 符号；oracle 标签仅用于评估预测动作（与 M3-D 记账一致）。
- **标定零模拟调用**：结构 + 运行时（monkeypatch 将 draw/eval 替换为 raise）双守卫；冻结 JSON `extra_simulator_calls = 0`。
- **网格锁定**：rho_grid 恰为预注册四值；变体恰为 GA1/GA2；标签/基准未重表征（哈希自校验）。

## 3. 操作化风险与量化

| 风险 | 量化 | 处置 |
|---|---|---|
| M2 归一化替代（pilot M2_hat → 基准臂评估 M2） | 标定-在线代理保真度：**176/176 激活试次门决策一致**；归一化最大相对差 214×（c000_s2_00255/seed2028：pilot 估计在稀有事件区间高方差，评估估计更稳定；该试次两种归一化下代理均远在阈值外，决策不变） | 替代记录于冻结配置；pilot M2_hat 每在线记录留档 |
| GA2 CI 线性传播 vs 真逐 replicate | **0/192 决策分歧**；上端差距中位 0.001（P95 0.0146，最大 0.039） | 事后诊断（`run_m3g_ga2_diagnostic.py`，无臂评估，非科学诊断） |
| rho 灵敏度平坦 | 四档 GA2 行完全相同（批次内无试次保守端落在 (−0.02, −0.0025)） | 如实报告；tie-break 按预注册执行 |

## 4. 统计正确性

- 192 行按 NOT-IID 处理：配对 (state, seed) 单元；Acc3 增量配对 bootstrap（n=10,000，seed [20260827]）：均值 +0.0104，95% CI **[0.0000, 0.0260]**（含 0 → 分类提升不具统计显著性，如实报告）。
- M2 比值聚合按预注册层级（逐态种子中位数 → 再取中位数）与池化中位数双轨报告。

## 5. 威胁与局限

1. 结论域 = 单一生化 24 态基准（8/8/8）；无跨基准外推声明。
2. 增益代理为局部一阶量；曲率/二阶分量未建模（超出 v0 范围，标量策略按负结果政策关闭）。
3. 密封运行使用的统一 M2 归一化（评估臂）与冻结公式中的 M2_hat 存在估计器差异；已量化（§3），决策层不受影响。
4. Strong VRF>1 仅支持「在本冻结合成基准上实现成本效率」；明确禁止「梯度被证明」「自适应优越」等表述。
5. 全量 pytest 证据：1166 passed / exit 0（G2 阶段记录）。

## 6. 结论

有效性链完整：**冻结 → 标定（零模拟）→ 冻结提交 → 密封评估 → 位一致重放 → 门控审计 → 泄漏审计**。所有 PASS/FAIL 判定基于密封批次的直接测量与预注册阈值；无事后调参、无标签/基准改动、无 oracle 泄漏、无额外模拟调用。
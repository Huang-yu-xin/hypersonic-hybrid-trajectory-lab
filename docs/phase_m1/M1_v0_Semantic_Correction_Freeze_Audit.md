# M1-v0 Semantic Correction / Freeze Audit

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems
> **Method Track:** M1 — Closed-Loop Variance-Geometry Adaptive IS
> **Audit type:** Semantic Correction / Freeze Audit（H3 frozen interface 对照）
> **semantic_fix_version:** `m1-v0-semantic-fix-1`
> **Parent M1 package:** `M1_Closed_Loop_Variance_Geometry_Adaptive_IS_package_v1`（原结果未覆盖）
> **H3 frozen tag:** `RareTopo-H3-v1.0`（零改动，git diff 核验）
> **Date:** 2026-08-26
> **Amendment record:** `docs/phase_m1/M1_PREREG_AMENDMENT_Semantic_Correction.md`

---

## A. Executive Summary

**原 M1 科学结论全部保持**：

1. 无 oracle 闭环采样器发现 probability-small variance-dominant missing mode → **PASS（8/8）**；
2. second moment 大幅下降 → **PASS**（median M2 0.01592，降 98.7%）；
3. 达到 hand-designed leakage-oracle 的 10% 内 → **PASS**（M1/M3 = 1.011）;
4. 公平预算 VRF_budget ≈ 4 → **PASS**。

**数字变化（全部为同一方向的边际改善或等价）**：

| 指标 | original | semantic-corrected |
|---|---|---|
| M2 median (B) | 0.01596 | 0.01592 |
| L_S2 median (B) | 0.00213 | 0.00211 |
| VRF_budget median (B) | 3.985 | 3.991 |
| adaptation calls median | 60k | **40k**（诊断复用） |
| oracle gap M1/M3 | 1.017 | 1.011 |
| Benchmark C ratio | 0.0184 | 0.0181 |

**需要收紧/补充的 claim**：

- **Discovery 依赖显式探索成分**（Issue 5）：α=0（纯 q pilot）时 8/8 无法发现 S2（M2 保持 1.86）；α≥0.10 后 8/8。主配置 α=0.5 不变。**删除"失败 proposal 仅凭自身样本发现 unseen mode"的任何隐含表述**；使用补充句："The discovery mechanism relies on an explicit exploration component; variance geometry determines which observed modes are variance-important and how the proposal is adapted."（task §14 措辞规则）。
- **Ablation A 的 estimator 更正**：probability gate 的候选统计量由 raw occurrence fraction 更正为 stratified-aware 目标概率估计（(1/N)Σ1_A p/r_i）；结论不变（P̂(S2)≈6e-3 ≪ 0.10）。
- **Ablation D 对照增强**：HDR 质心修复后，单点 max-weight 对照的劣化由 40% 扩大至 **124%**——set-valued geometry 的价值评估更严格。

**Freeze-ready:** 见 §J。

---

## B. Issues Found

| Issue | Severity | Affected artifacts | Affected claims | Fix | Rerun |
|---|---|---|---|---|---|
| 1. L_eta 用 raw quantile，违反 H3-3A HDR 语义 | **High**（frozen interface 继承错误） | `proposal_update.eta_region_centroid`；B/C/D/E 的组件中心 | "set-valued centroid" 相关一切 | variance-mass 累计 prefix（HDR）+ 质心 helper | **B/C/D/E** |
| 2. （Issue 1 的 rerun 要求） | — | results | — | 新目录 `results/phase_m1_semantic_fix/` | B/C/D/E |
| 3. VRF 口径 | Medium（报告语义） | Report/JSON labels | "VRF≈3.98" 表述 | `vrf_proposal`/`vrf_budget` 单一来源 + 分列核查 + 一致性测试 | 否（重算即可） |
| 4. probability ablation 用 raw fraction 且复制阈值 | Medium（comparator 语义） | `mode_discovery`；Ablation A | "概率信号不足" 结论（方向保留） | IS 目标概率估计器 + threshold-free top-ranked comparator | Ablation A（+新 A2） |
| 5. 探索成分敏感性未量化 | Medium-High（claim 措辞） | closed-loop pilot policy | "discovery 自主性" 表述 | α∈{0,.10,.25,.5,.75,1} 扫描（主 α=0.5 不变） | 新实验 |
| 6. 混合 pilot 下 bootstrap 未分层 | Medium（不确定性估计） | `omega_bootstrap_lcb` | LCB 数字 | stratified bootstrap（层内重采样保 N_q/N_p） | Discovery rerun |
| 7. add_component 多组件权重比例破坏 | Medium（J≥2 路径 bug） | `proposal_update.add_component` | 无（主路径 J=1→2 不受影响） | (1-α) 联合缩放 | 测试 1→2/2→3/3→4 |
| 8. 诊断 pilot 独立采样致满跑超 nominal 预算 | **High**（budget 纪律） | `closed_loop`；B 的 calls | "≤160k nominal" 表述 | 诊断复用为下一轮 pilot + 分列记账 + assert | **B/C/D/E** |

---

## C. H3 L_eta Semantic Correction

**原实现**（违反 H3-3A）：
```python
thr = np.quantile(log_rho[mask], eta)          # raw-count quantile: top 20%
region = mask & (log_rho >= thr)
```

**H3-3A frozen 定义**（`docs/phase_h/H3_3A_set_valued_variance_geometry.md` §3.1-3.2）：
> "**绝不取'前 20% 样本'**——HDR region 是按 ρ_L 排序后累计 ω^V 质量得到的最小 prefix"；m_η = E_{ν_V}[X | X ∈ L_{η,k}]（pooled ω^V 归一）。

**修复实现**（`proposal_update.py`）：
```python
variance_mass_hdr_indices(z, centers, pi, logp, logr, labels, nominal, mode, eta)
  # rho_V desc (stable ties) -> cumulative normalized w_tilde -> first prefix >= eta
variance_mass_region_centroid(z, w_full, idx)
eta_region_centroid(...)  # HDR prefix + variance-mass centroid; fallback eta_used=1.0
```

**Toy regression**: η∈{0.5,0.8,0.9} 时 prefix 累计 ≥ η 且去掉最后项后 < η；非均匀质量下 prefix 大小明显小于 raw quantile（测试 `test_m1_semantic_fix.py::TestVarianceMassHdr`，含手工 toy centroid 对照）。

**B/C/D/E before-vs-after**（8 seeds median）:

| 量 | original | corrected |
|---|---|---|
| B: M2 median | 0.01596 | 0.01592 |
| B: Gate2/3/4/5 pass | 4×True | 4×True |
| B: adaptation calls | 60k | 40k |
| C: M2 ratio median | 0.0184 | 0.0181 |
| C: verdict | PASS×3 | PASS×3 |
| D: max-weight M2 | 0.0224 | 0.0356 |
| E: η 0.5/0.8/0.9 | 0.01596/0.01596/0.01597 | 0.01588/0.01592/0.01596 |

---

## D. VRF Provenance Correction

两个口径在代码与 JSON 中明确分列（`baselines.vrf_proposal` / `vrf_budget` 单一来源；一致性测试 `TestVrfDefinitions`）：

| 口径 | 定义 | B 中 M1 median（corrected） |
|---|---|---|
| `VRF_proposal` | Var_MC(Â_N) 在 **eval 预算** / Var_q(Â_N) 同预算（不计 adaptation） | 6.39 |
| `VRF_budget` | Var_MC 在 **总预算 B** / Var_q 在 B−N_adapt | 3.99 |

约束：JSON `VRF_proposal`/`VRF_budget` 字段、报告表格、Figure M1-6 三处 label 一致；禁止把 3.99 同时写进两列（原报告 §0/§4 措辞已核查，MC 等非自适应方法的 proposal/budget 相等属定义使然，已在 JSON 中显式标注计算式）。

---

## E. Probability Ablation Correction

**为什么 raw frequency ≠ target probability**：固定分层设计（50% q_t + 50% p）下 `n_k/N` = 0.5·P(S2|q_t)+0.5·P(S2|p) = 0.0031，而 P_p(S2)=0.0062（差 2 倍）。

**新 estimator**：P̂_k = (1/N)Σ 1_{A_k} p(x_i)/r_i(x_i)（任意固定设计无偏；测试 `TestStratifiedProbabilityEstimator`）。

**结果**（8 seeds）：
- Ablation A（概率 gate，修正 estimator）：**0/8 birth**，M2 = 1.86 —— P̂(S2)≈6e-3 仍 ≪ 0.10 → 方差信号必要性结论**保留**；
- **A2 新 comparator**（threshold-free top-ranked + 概率质心 + P̂ 归一化权重，全程无方差几何）：8/8 birth S2，M2 = 0.01685（main 0.01592，差 5.8%）。

**解读**（如实）：该 benchmark 每个 round 只有一个 unrepresented 模式，top-ranked comparator 在观测到它时"别无选择"必然选中——它不能按方差重要性排序多候选（无此能力）；单 missing-mode 格局下两种信号都指向同一模式，差异体现在 (a) 多 missing-mode 排序能力（variance 独有）、(b) variance 质心 vs 概率质心的质量（D 的对照 + A2 的 5.8% 差距）。

---

## F. Exploration Sensitivity（Issue 5）

α = P(pilot source = p)，主配置 α=0.5 **不变**；8 seeds × 6 levels，pilot 20k/轮、≤3 轮、eval 100k。

| α | discovery (8) | false birth | median M2 | median L_S2 | VRF_budget |
|---|---|---|---|---|---|
| 0.00 | **0/8** | 0 | 1.86 | 1.85 | ~0.057 |
| 0.10 | 8/8 | 0 | 0.0191 | 0.0059 | ~3.4 |
| 0.25 | 8/8 | 0 | 0.0167 | 0.0031 | ~3.8 |
| **0.50** | **8/8** | **0** | **0.0159** | **0.0021** | **3.99** |
| 0.75 | 8/8 | 0 | 0.0158 | 0.0018 | ~4.0 |
| 1.00 | 8/8 | 0 | 0.0158 | 0.0016 | ~4.0 |

（图：`results/phase_m1_semantic_fix/figures/fig_m1_7_exploration_sensitivity.png`）

**回答**：closed-loop 的 discovery 对探索份额存在**阶跃性依赖**——α=0 时纯 q 样本无法发现 S2（信息论层面：期望 0.63 观测）；α≥0.10 后 8/8 稳定且在 α∈[0.1,1] 单调微优。主配置 α=0.5 处于有效且经济的位置。**claim 措辞按 §14 规则补充探索依赖声明**。

---

## G. Bootstrap Correction（Issue 6）

| | ordinary bootstrap | stratified bootstrap（修复后） |
|---|---|---|
| 重采样 | 全样本混合 | 层内（q-source / p-source）分别重采样，N_q/N_p 精确保持 |
| 适用 | 随机混合设计 | 固定分层设计（v0 pilot 即此） |
| 测试 | — | 层大小保持 / deterministic / 长度校验拒绝 |

修复后 Discovery rerun（stratified LCB）：8/8 PASS 不变（LCB 仍 0.97+），主结论不受 bootstrap 修正影响。

---

## H. Multi-component / Budget Fix（Issue 7 & 8）

- **Issue 7**：`add_component` 现按 π_j^new = (1−α)π_j^old、π_{J+1}=α 精确构造（sum=1、旧比例保持、ordering 无关）；测试 1→2 / 2→3 / 3→4 全过。主路径（1→2）行为不变。
- **Issue 8**：每轮正好一个 pilot（20k），第 t+1 轮 pilot 兼作第 t 轮更新的独立诊断；每 iteration 记录 pilot_calls / cumulative；结果含 budget 明细（pilot_total / diagnostic=0 / reused / new / limit / assertion_passed）。3-birth 满跑测试（三个正交模式）累计 60k ≤ 60k limit ✓；Benchmark B 实际 40k/seed（较原先 60k 省 20k），总 140k ≤ 160k nominal ✓。

---

## I. Gate Re-evaluation（semantic-corrected results，8 seeds）

| Gate | 定义 | corrected result | 判定 |
|---|---|---|---|
| 0 Validity | 全部合法性/测试 | 58 项 M1 测试 + 全量回归通过；H3 frozen 零改动 | ✅ |
| 1 Discovery | ≥7/8 识别 S2 | **8/8**，0 false birth | ✅ PASS |
| 2 Leakage | ≥7/8 L 降 + median ≤0.5 | 8/8；median 0.0017 | ✅ PASS |
| 3 M2 | ≥7/8 M2 降 + median ≤0.5 | 8/8；median 0.0133 | ✅ PASS |
| 4 Oracle gap | median M1/M3 ≤1.10 | **1.011**（competitive） | ✅ PASS |
| 5 Budget | median VRF_budget>1 | **3.99**，8/8>1 | ✅ PASS |

Benchmark C（推广基准，非 gate）：8/8 discovery、M2 ratio 0.0181、无偏 → 全部 PASS。
Ablation A-E 语义修正后全部回答原问题（A 结论保留、B/C/E 不变、D 加强）。

---

## J. Final Verdict

> **M1-v0 is FREEZE READY.**

- 全部 12 个 freeze 条件满足（§15 checklist）：
  L_eta 修复 ✅ / B/C/D/E 重跑 ✅ / original-vs-corrected 对照 ✅ / VRF 口径 ✅ / probability ablation 修正 ✅ / exploration sensitivity ✅ / stratified bootstrap ✅ / multi-component 修复 ✅ / budget 会计修复 ✅ / full pytest ✅ / gates 重新评估 ✅ / verdict 本次 ✅；
- 剩余非阻塞事项（记录于各 milestone 审查，不阻止 freeze）：
  1. q0 口径 L_S2 的 eval 高方差（paired 比较方向稳健）；
  2. 稀有 mode 的 η 质心 fallback（eta_used=1.0，eta=0.8 主路径未触发）；
  3. α 敏感性在 [0.1, 1] 的单调微优已量化（主配置 0.5 保留）；
  4. A2 comparator 单候选"别无选择"局限（已在 §E 如实解读）。

按指示：**不创建 Git tag**；freeze/tag 作为单独步骤等待执行。
# M3-G Protocol Deviation Audit

> **Stage:** M3-G freeze audit（修正轮） ｜ **Audit date:** 2026-08-27
> **Authoritative preregistration:** `docs/phase_m3g/M3_G_Gain_Aware_HOLD_Decision_Task.md` @ commit `9720456`
> **Executed artifacts:** calibration freeze `48fe50b`（GA2, ρ=0.0025）、sealed batch `results/phase_m3g/layer_a/m3g_online_v1.json`
> **Verdict:** **M3-G-v0 = NOT FREEZE READY**（exact-proxy replay 未重现冻结选择；偏差非 result-preserving）

---

## 0. 审计目的与边界

本审计不新增 simulator scientific runs、不改 controller、不调 rho、不改 sealed benchmark、不改任何 raw 结果文件；仅做纯 replay / audit 计算与文档修正。

```text
extra simulator scientific calls = 0
raw scientific result files changed? NO
```

## 1. 现场固定（audit 开始时）

| 项 | 值 |
|---|---|
| branch | `feature/phase-m3g-gain-aware-hold` |
| HEAD | `64f7278ab6cc0834ae30886b57eef9b3bdf47dd1` |
| RareTopo-M3-D-v0 tag object / peeled | `731eac03…` / `7bd58c5992615b8579b1814a3a3fcbea3cda9659`（未变） |
| RareTopo-M3-v0 peeled | `32b285625494d9b3da08be3c559db3855df77667`（未变） |
| sealed benchmark freeze sha | `b613f45dc6645c6da26ab58b5185764f14d771ca6b996bffed88fea1f467a5f3`（未变） |
| calibration freeze commit | `48fe50b`（仍早于 sealed replay/evaluation，未变） |
| raw M3-G 结果哈希 | 见 §6（审计前后一致） |

## 2. Deviation A — M2 分母操作化替代

| 字段 | 记录 |
|---|---|
| **original prereg definition** | \(\widehat{\Delta}_{rel}=\widehat g\,\Delta\theta/\widehat M_2\)（task Sec. 3 原文；\(\widehat M_2\) 指冻结估计器管道内 pilot-based M2_hat = mass/n，20k pilot） |
| **implemented operationalization** | 分母改用 **BASE-arm evaluation M2**（n=100k，CRN [seed,900001]，当前协方差点的直接 IS 估计）；标定（存储 `arms.hold.M2`）与在线（`ev["base"]["M2_hat"]`）一致 |
| **为什么发生** | M3-D D6 记录模式（`raretopo-m3d-v0`）仅持久化各臂评估 M2 与 g/CI/ESS 摘要，**未存 pilot M2_hat 与逐 replicate 数组**（`results/phase_m3d/layer_a/m3d_layer_a_v1.json` 逐条核对）；标定被要求零新调用，只能使用存储量 |
| **什么时候发现** | 本阶段（execution thread）G0 勘察存储 schema 时发现缺失；当时**尚未查看任何 calibration outcome**（选择结果在偏差决策之前未知） |
| **是否看过 calibration outcome** | 否——偏差操作化是在任何标定输出存在之前锁定的（冻结配置记录为其理由） |
| **是否增加 simulator calls** | 否（任一阶段均零新增） |
| **现有 invariance evidence（审计后）** | **不成立**。（i）exact-proxy replay（§4）在预注册原义分母下选择 **GA1-0.02**，与冻结选择 **GA2-0.0025 不一致**；（ii）在封闭策略 GA2-0.0025 下，评估-M2 线性 vs pilot-M2 线性决策分歧 **9/192**；（iii）两估计器相对差极端值 ~215×（c000_s2_00055/seed2028：pilot M2_hat=13.79 vs eval=0.064），量级差异直接决定门是否折叠（抽查：c001_s2_00320/seed2026 的 pilot M2=4.61 使 GA1-0.02 折叠，eval M2≈0.06 则执行） |

**结论（Deviation A）**：M2 归一化替代**改变策略选择与动作集合**，为实质偏差（material），不可标注 result-preserving。

## 3. Deviation B — GA2 不确定性传播操作化替代

| 字段 | 记录 |
|---|---|
| **original prereg definition** | GA2 = 由逐 replicate (g_r, M2_r) 估计传播的增益 bootstrap CI 的保守上端（"bootstrap CI for the gain propagated from the existing per-replicate estimates of g_hat and M2_hat, same fixed-stratified replicates"） |
| **implemented operationalization** | 冻结 g-CI 端点经符号稳定因子 Δθ/M2 的**线性传播**：WIDEN: g_ci_high·0.20/M2 ≤ −ρ；SHRINK: g_ci_low·(−0.20)/M2 ≤ −ρ |
| **为什么发生** | D6 记录模式未存逐 replicate 数组；标定只能在存储摘要上操作 |
| **什么时候发现** | 同 §2（G0 schema 勘察时）；当时未查看 calibration outcome |
| **是否看过 calibration outcome** | 否 |
| **是否增加 simulator calls** | 否 |
| **现有 invariance evidence（审计后）** | **在选定 rho=0.0025 下成立**：修正方向的逐 reveal 检查（`run_m3g_ga2_diagnostic.py` 二次运行，按各试次实际方向取 Δθ=±0.20，pilot M2 归一化）线性上端 vs 真逐 replicate 上端（`bootstrap_gain_replicates`，与冻结 CI 位一致重放）**决策分歧 0/192**，|gap| 中位 0.001（P95 0.0146）。**在其它 rho 上不评估**（因 Deviation A 已使整张冻结网格失真，逐 rho 的 CI 模态差异没有独立意义） |

**结论（Deviation B）**：在选定 rho 与给定分母下 CI 传播模态替代不影响决策；但它无法抵消 Deviation A 的整体失真。

## 4. Exact-proxy calibration replay（纯审计）

按预注册原义代理重建完整 8 候选标定表（`results/phase_m3g/summary/exact_proxy_calibration_replay.json`）：

```text
GA1 : act iff |g_hat*dtheta|/M2_hat_pilot >= rho      （pilot M2_hat = mass/n，20k pilot 重放）
GA2 : act iff per-replicate 有符号增益 CI 上端 <= -rho （g_r*dtheta/M2_r，冻结固定分层 bootstrap 重放）
```

- 重放方式：仅重放 pilot（rng [seed,101]）与 bootstrap（rng [seed,424243]）的确定性抽取；**无 arm evaluation、无新密封行**；replay 的 g_hat 与存储 Layer-A **192/192 位一致**（0 失配）。
- `extra simulator scientific calls = 0`（重放不产生新科学记录；审计定义下纯重放）。

### 重放标定表（192 试次池化）

| 候选 | Acc3 | 均衡精度 | macro-F1 | rW | rS | rH | 合格 |
|---|---|---|---|---|---|---|---|
| GA1-0.0025 | 0.7552 | 0.7552 | 0.703 | 1.000 | 1.000 | 0.266 | ✓ |
| GA1-0.005 | 0.8281 | 0.8281 | 0.809 | 1.000 | 1.000 | 0.484 | ✓ |
| GA1-0.01 | 0.9635 | 0.9635 | 0.963 | 1.000 | 1.000 | 0.891 | ✓ |
| **GA1-0.02** | **1.0000** | **1.0000** | **1.000** | **1.000** | **1.000** | **1.000** | ✓ |
| GA2-0.0025 | 0.8073 | 0.8073 | 0.780 | 1.000 | 1.000 | 0.422 | ✓ |
| GA2-0.005 | 0.9271 | 0.9271 | 0.925 | 1.000 | 1.000 | 0.781 | ✓ |
| GA2-0.01 | 0.9948 | 0.9948 | 0.995 | 1.000 | 1.000 | 0.984 | ✓ |
| GA2-0.02 | 1.0000 | 1.0000 | 1.000 | 1.000 | 1.000 | 1.000 | ✓ |
| baseline M3-D | 0.7500 | 0.7500 | 0.695 | 1.000 | 1.000 | 0.250 | — |

预注册选择规则（合格内最大 Acc3，tie-break 均衡精度→macro-F1→更小 ρ→GA1 在前）→ **选定 (GA1, ρ=0.02)**，Acc3=1.0000（GA2-0.02 同值，tie-break 取 GA1）。

### 一致性判定（Stop Rule）

```text
exact replay 选定策略          : GA1-0.02
frozen calibration 选定策略    : GA2-0.0025
选择是否一致                   : 否  (NOT result-preserving)
封闭策略 GA2-0.0025 逐 trial 动作分歧 : 9 / 192（4.7%）
分歧方向                       : 5× (exact HOLD vs sealed SHRINK)、
                                 4× (exact HOLD vs sealed WIDEN)
因素归因                       : Deviation A 独家（9/9）；Deviation B 0/192
```

冻结网格（评估 M2 分母）下 GA1/GA2 全档平坦且 ≈ baseline（几乎零折叠）；预注册原义网格（pilot M2_hat 分母）下 rho 灵敏度强烈且收敛到 Acc3=1.0（HOLD recall 1.0，48 个 act-but-indifferent 全部正确折叠）。**同一批试次、同一公式、仅分母估计器不同 → 标定选择与分类结论完全翻转。**

## 5. 停止规则裁决（Sec. 5 逐字执行）

```text
exact replay 选择不同 variant/rho（GA1-0.02 ≠ GA2-0.0025）
且产生 materially different decisions/results（9/192 动作分歧；
   精确选中策略的样本内 Acc3 1.0 vs 冻结 0.7604）
=> M3-G-v0 = NOT FREEZE READY
=> 立即停止：不创建 tag、不 push、不重跑 sealed evaluation、
   不以改报告掩盖
```

## 6. 哈希 / 溯源审计

| 文件 | SHA-256（审计后复测） | 状态 |
|---|---|---|
| results/phase_m3g/layer_a/m3g_online_v1.json | `647c3e6abe48a3e88c5719f738943d28e985098052e21b5c8a70683cab2f2662` | 未变 |
| results/phase_m3g/calibration/m3g_calibration_v0.json | `c8f2482ee5af12aceaba6d1577f67af613a670517017ac6c27292aecefc481c4` | 未变 |
| results/phase_m3d/layer_a/m3d_layer_a_v1.json | `d9b0d6b5e4c4cd4480b50210bbc39e89689e538990f478c3bc42ed2d090f6ce0` | 未变 |
| docs/phase_m3d/M3_D_Benchmark_Freeze.json | `b785190e5a2ca8de305a4d66d1459f3c318ac00cd0ab06085f86395153a95495` | 未变 |
| configs/phase_m3g/m3g_gain_gate_v0.json | `821dc8a91dad31d4e2572709e3867b231166291a82efdcfec972f47598815e49` | 未变（内容为已执行操作化，不改写） |
| exact replay 输出 | 见 `exact_proxy_calibration_replay.json`（新增审计产物） | 新增 |

```text
raw scientific results changed? NO
benchmark changed? NO
rho changed? NO
controller changed? NO
new simulator scientific calls? 0
```

## 7. 对已执行流程的裁定

1. **执行链**（冻结 48fe50b → 密封 192 试次 → 审计）内部自洽、位一致、零泄漏、零新增调用——**作为对「评估-M2 操作化策略」的描述性研究仍然成立**（M3G-0/1 位一致门、泄漏门等有效性事实不受影响）。
2. **作为对预注册一阶增益门（原义代理）的科学检验不成立**：操作化替代（Deviation A）实质性改变策略选择与结论（Deviation B 在选定 rho 上无害）。因此原始报告中的「结论对操作化替代稳健」表述**不能成立**，已在本轮修正中撤销。
3. **修正方向（不在此执行）**：M3-G 的预注册实现必须直接使用 pilot M2_hat 与逐 replicate 传播（或在预注册文档中明确分母估计器选择并配套对应标定数据持久化）；随后重新走完整预注册周期（新 task/amendment 提交 → 标定 → 冻结 → 密封评估）。本审计不做任何重跑。

## 8. 修正后的权威口径（本仓库文档统一采用）

- 权威门 = `9720456` 任务文档 **M3G-0..5 + Strong**（阈值见 `M3_G_Final_Report.md` Table A）。
- 执行任务中的更严格指标已更名为 **Secondary / Strengthened Audit Criteria**（Table B），不作为原始预注册官方门。
- 标定与密封评估共用同一冻结 (state, seed) 单元 → 所测提升为 **in-sample calibrated performance**，统计量定名为 **descriptive paired bootstrap interval after policy selection**（不具 holdout 泛化含义）。
- Strong VRF 措辞改为：**M3-G retained the M3-D crossing of the crude-MC budget-efficiency boundary**（VRF_budget=1.0304 与 M3-D 同值；不声称新增穿越或优越性）。
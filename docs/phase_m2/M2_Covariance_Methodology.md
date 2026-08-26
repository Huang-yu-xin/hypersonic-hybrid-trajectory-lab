# M2 Covariance Methodology — 实施与方法文档

> **Project:** RareTopo — Topology-Aware Uncertainty & Risk Propagation in Hybrid Dynamical Systems
> **Method Track:** M2 — Variance-Geometry Covariance Adaptation
> **Schema:** `raretopo-m2-v0` ｜ **Status:** EXECUTED (2026-08-27)
> **Parent frozen chain:** `RareTopo-H3-v1.0` → `RareTopo-M1-v0` → `RareTopo-M1-D-v1.0`（M1-D frozen HEAD `059964eb3b8b927301776ae5505bc3ac8593ed94`）
> **Benchmark freeze SHA-256:** `be2ef47157b95f479949f706de6285827b70e15fa0488e4cdbfc128bd6bb61de`
> **Task document:** `docs/phase_m2/M2_Variance_Geometry_Covariance_Adaptation_Task.md`（SHA-256 `36932a9feb5e8fccd26bb2d8beec8daabab3e1ab6a977dfa7d6b8eeafa39c144`）

---

## 1. 范围与冻结边界

本阶段只研究 **proposal covariance / shape**。Firewall 全程生效：未改动任何 H3 / M1 / M1-D 冻结文件（`git diff 059964e..HEAD -- src/hyptraj/m1 src/hyptraj/m1d docs/phase_m1d configs/phase_m1d` 为空）；M2 全部代码位于新 namespace `src/hyptraj/m2/` 与 `scripts/run_m2_*`。被禁止事项（改 selector、改 birth threshold、重筛 benchmark、调 exploration、加学习组件、依据结果改 seed/gate/λ 等）逐项未触碰。

## 2. 与冻结件的关系（复用清单）

| 冻结组件 | 复用方式 |
|---|---|
| 混合 pilot 抽样 | `m1d.adaptation.draw_mix_pilot`（`rng=[seed,101]`，p-源在前 q-源在后，逐位一致） |
| variance selector | `eligible_candidates`（Sec.16 门，min_obs=5，无 birth-threshold 预筛）+ `selector_pick('variance')`（argmax L̂，Sec.17.2） |
| 新分量均值 | `m1.proposal_update.eta_region_centroid`（η=0.8 variance-mass HDR，**逐字复用**；双算校验偏差恒为 0） |
| HDR 区域定义 | `variance_mass_hdr_indices`（"绝不取前 20% 样本"的最小前缀语义，含 <2 样本回退） |
| 权重优化器 | `m1.mixture_weights.optimize_mixture_weights`（SLSQP+解析梯度，ftol=1e-12 / maxiter=500 / floor=0，**参数零修改**；单测验证未传覆盖参数 + 独立复现逐位一致） |
| 终评与 VRF | `m1d.metrics.eval_proposal_is`（rng tag 900001）+ `attach_vrfs`（frozen `vrf_proposal`/`vrf_budget`） |
| 合法性纪律 | `m1.proposal_update.LEGALITY_MIN_EIG = 0.5`（`check_legality_frozen` 委托同常数，未重定义） |
| Σ_base 读出 | 从冻结 proposal 元数据 `min_eig_sigma_minus_halfI==0.5` 证明性重构 `Σ_base=I₂`（任务 §13 禁止硬编码假设；非单位基会记录不同值→拒绝） |

**新受控变量**：`CovGaussianMixtureProposal`（逐分量协方差高斯混合；`sample` 的 RNG 调用序与冻结家族一致——单次 `choice` + 单块 `standard_normal`——单位协方差实例与冻结家族共享 CRN）。

## 3. 预注册常数（锁定，`configs/phase_m2/m2_covariance_v0.json`）

8 frozen configs（c000/c001/c004/c006/c007/c010/c017/c020）× seeds [2026..2033]；`pilot_n=20000`、`alpha_p=0.5`、`final_eval_n=100000`、`eta_main=0.8`、`lambda_main=0.50`、敏感性 {0.25, 0.75}、`ESS_V_region ≥ 20` 且 `n_region ≥ d+2`、eigen clip [0.55, 4.00]、Layer A/B 语义、Gates M2-0..M2-5 + Strong。**任何一项均未在看到结果后调整**；无 `M2_PREREG_AMENDMENT` 文件（零修订）。

## 4. 共享阶段与锁（§18–§20）

每个 (config, seed) **恰好一次**：
1. 共享 pilot（frozen 流，与已归档 M1-D d1a `variance_selector` 试验逐位可比）；
2. **Selection lock**：候选（Sec.16 门）→ argmax L̂ 恰好计算一次，C0–C4 结构上只能消费 `SharedStage.selected_mode`（无重选接口）；
3. **Mean lock**：η=0.8 HDR centroid（frozen 函数）+ 区域统计独立重算，偏差 >1e-10 即 RuntimeError（全程实测恒 0.0）；
4. C0 更新：`add_component`（π_fallback=0.5 保比值）+ frozen SLSQP → `π_C0`。

**离线溯源核验**（gate audit）：M2 全部 64 个 (config,seed) 的 selected mode 与已归档 `results/phase_m1d/d1_selection_only/layer_a_one_birth_v1.json` 中 `variance_selector` 记录 **0 例不一致**。

## 5. 候选族 C0–C4（§14）

`C0=Σ_base`；`C1=(tr(C_η)/d)·I`；`C2=diag(C_η)`；`C3=C_η`；`C4=(1−λ)Σ_base+λC_η`（λ=0.50）。统一后处理：symmetrize → 特征分解 clip[0.55,4.00] → 重建再 symmetrize → frozen 合法性检查。**Sec.17 元数据全量入库**：eig_pre/post、双向裁剪计数、Frobenius 投影范数、legality_passed、hold、hold_reason。

## 6. 两层设计（§21）

- **Layer A（shape-only）**：所有变体共享 `π=π_C0`（单测 `test_m2_shape_only_same_weights` 断言逐位相等），隔离纯形状效应；
- **Layer B（shape+reweight，headline）**：每变体在**声明的 pilot fit 数据**（= selection 所用同一 pilot；§22 流程图的 fit 集声明）上以 frozen SLSQP 核重新拟合权重（初值 = add_component 拆分值，与冻结路径一致）。

## 7. 数据防火墙与成本核算（§22–§23）

协方差估计只用 pilot；final-eval 样本不进入任何 C_η 计算（`test_m2_no_final_eval_leakage`：冻结点前后采样窗口计数断言）。每 trial 成本 = 20k（共享 pilot）+100k（终评）=120k，与 M1-D d1 trial 完全同口径；`cost.extra_simulator_calls_covariance ≡ 0`（`test_m2_no_extra_simulator_calls`）。λ 消融复用同一 pilot/selection/centroid/CRN，零额外模拟调用。

## 8. 预先声明的统计与容差（§29/§38–§39）

- **层级统计**：within-config 8 seeds 取 median → across-config 8 medians；headline 比值 = median-of-per-config-paired-medians；配对 bootstrap 95% CI（2000 次）作用于 log M2 差；win counts 分 seed/config 两级。
- **Probability consistency（§29）**，两腿并报：
  - vs-ref 诊断腿：t=(P̂−P_ref)/√var̂；实测对**所有方法（含 C0）一致膨胀**（|t| 中位 6.6–29.5）——量级与 P_ref 分母误差（MC 交叉偏差 ≤5.3% + bootstrap 半宽 ≤4.3%）吻合，判定为参考分母伪影，**仅作诊断**；
  - **paired-C0 判定腿（声明为 Gate M2-0 判据）**：t_pair=(P̂_m−P̂_C0)/√(var̂_m+var̂_C0)，阈值 median|t_pair|≤4。实测全部 method×config×layer 最大 **0.41**，0 例越限 → 无 estimator 偏置证据。
- **C/C+±容差、ESS 分带（Ablation F）**：low<20 / medium<200 / high≥200。

## 9. 实施期尽调披露（Run Order §43 相关）

在锁定预算下预先量化了区域 ESS_V 分布（M2-1 稳定性尽调）：**8 config 中仅 2 个 config 的 seed-中位 ESS≥20**（heavy-tail 方差质量 + 双源 r 异质性所致）。这是任务 §12 HOLD 规则与 §43 停止规则的预期冲突点。处理方式：HOLD 是**合法记录行为**（Gate M2-1 明文允许"ESS≥20 或合法 HOLD"），故按预注册执行全部阶段并**把 HOLD 频率作为一等公民披露**（实测 67.2%），不采用任何未授权手段（改预算/阈值/seed 均为冻结项）降低 HOLD 率。§34 离线 Oracle-Cov 因需重跑 simulator 而按任务明文放弃。

## 10. 偏差登记

相对任务文本的**实现层声明**（无科学语义偏离）：
1. §45 要求键 `evaluation.n`/`mode_L` 与冻结评估器键 `n_eval`/`L_table` 并存（别名双写，冻结键保留以兼容 `attach_vrfs`）；
2. 空阶段行（selection 无合格候选）记为 `layer="stage_failed"` 保留行——本批实际 **0 例**（64×8 全部完成 selection）；
3. 投影器对非法输入同样先 symmetrize 再记录 `sigma_pre`（§11"先对称后使用"语义统一）；本批 0 例非法输入。

## 11. 产物

代码 `src/hyptraj/m2/{variance_covariance,covariance_projection,covariance_policy,metrics}.py`；驱动 `scripts/run_m2_{sanity,covariance_experiments,gate_audit,figures}.py`；测试 `tests/test_m2_covariance_pipeline.py`（§40 全部 14 项）；结果 `results/phase_m2/{sanity,layer_a_shape_only,layer_b_shape_reweight,ablations,summary}/`；图 `figures/phase_m2/figure_M2_1..8*.png`。

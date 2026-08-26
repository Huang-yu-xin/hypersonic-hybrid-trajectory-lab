# M2 Final Report — Variance-Geometry Covariance Adaptation

> **Schema:** `raretopo-m2-v0` ｜ **Date:** 2026-08-27 ｜ **Branch:** `feature/phase-m2-covariance-adaptation`
> **Frozen chain:** `RareTopo-H3-v1.0` / `RareTopo-M1-v0` / `RareTopo-M1-D-v1.0`（M1-D HEAD `059964e`，M2 分支自该点创建）
> **Benchmark freeze SHA-256:** `be2ef471…bb61de`（与已归档 M1-D 运行记录逐一匹配）
> **Prereg amendment count:** 0
> **Machine-readable verdict:** `results/phase_m2/summary/gate_audit.json`

---

## 0. 一句话结论（One-Line State）

```text
H3 = frozen; M1-v0 = frozen; M1-D = frozen
M2 = EXECUTED (prereg followed, zero amendments)
M2 verdict: Core mechanism NOT supported on the frozen M1-D benchmark
  - Gate M2-0 PASS, M2-1 PASS (legal-HOLD channel), M2-4 PASS
  - Gate M2-2 FAIL, M2-3 FAIL, M2-5 FAIL; Strong Gate NOT PASSED
  - Interpretation matrix Row 1: covariance geometry offers no
    method-level benefit on this benchmark; where adaptation could act
    (21/64 paired trials, ESS>=20) it systematically INCREASED M2
next gate = (per parent program) none preregistered for M2-v0
```

## 1. 执行顺序（任务 §42）与完成证据

| 阶段 | 状态 | 证据 |
|---|---|---|
| M2-0 Task freeze | ✅ commit `9e36696` | `docs/phase_m2/…Task.md` + 双配置 json；hash 校验 |
| M2-1 estimator + tests | ✅ commit `ecc6618` | `src/hyptraj/m2/` 4 模块；§40 全部 14 项单测（15 passed） |
| M2-2 legality projection + sanity | ✅ | S1 加权点云 12 检查全过；S2 半空间 IS 无偏带/合法性/HOLD 强制触发全过（`results/phase_m2/sanity/`） |
| M2-3 Layer A | ✅ 320 trials | `layer_a_shape_only/layer_a_shape_only_v1.json` |
| M2-4 Layer B | ✅ 320 trials | `layer_b_shape_reweight/layer_b_shape_reweight_v1.json` |
| M2-5 leakage/budget audit | ✅ | `summary/gate_audit.json` + 本报告 §3 |
| M2-6 ablations A–F | ✅ | λ 消融 2×128 trials + A/B/C/E 由主格导出 + F 分带表 |
| M2-7 final gate report | ✅（本文档） | 8 图 `figures/phase_m2/` |

运行时长：主实验 279 s（全预注册预算：64×(20k pilot)+640×(100k eval)+λ 复用，零额外 simulator 调用）。

## 2. 有效性（Gate M2-0 — PASS）

- parent tags / frozen HEAD 未动（firewall diff 为空）；benchmark hash 与归档一致；
- **Selection lock 溯源核验：M2 的 64/64 个 selected mode 与已归档 M1-D `variance_selector` 记录完全一致**（0 mismatch）；
- Mean lock：M2 区域 centroid 与 frozen `eta_region_centroid` 双算偏差恒 0.0；
- 结果格完备：2 层 × 64 (config,seed) × 5 方法 = 640/640，无缺格；
- covariance SPD / frozen legality：0 违规（见 Legality Audit）；
- 概率一致性：paired-C0 判定腿 0 例越限（max median|t_pair|=0.41，阈值 4）；vs-ref 诊断腿对含 C0 的全方法一致膨胀（6.6–29.5），按预声明归因于参考分母误差（P_ref MC 交叉偏差 ≤5.3%），仅诊断不作判据；
- 全量 pytest：见 §6 证据行。

## 3. 科学 Gate 判定

### Gate M2-1 Estimator stability — PASS（合法 HOLD 通道）
- 8/8 config 的 per-config median trial 满足 {ESS_V≥20 **或合法 HOLD**；covariance finite；projection finite}；
- **HOLD 频率（必须披露）**：变体格 172/256 = **67.2%**，全部由 `ESS_V_region<20` 触发（0 例 n_region 不足、0 例非有限）；per-config：c010、c017 100%；c006 87.5%；c007 75%；c000/c001 62.5%；c020 37.5%；c004 12.5%；
- C4 试验中 ESS_V≥20 的仅 42/128（32.8%）；ESS_V 总中位 12.1；
- A_C 中位 7.64（最大 1540）：方差区域高度各向异性且集中——C_η 可测（H-M2.1 的"可测"成立），但其支撑远窄于 p²/q 积分质量。

### Gate M2-2 Core second-moment gain — **FAIL**
- median-of-config-medians M₂(C4)/M₂(C0)（Layer B）= **1.0000**（阈值 ≤0.85）；
- 严格下降 config 数 = **0/8**（需 ≥6）；seed 级胜场 **0/64**；
- 配对 ΔlogM₂：中位 0.000（bootstrap 95% CI [0,0]——HOLD 平局主导），均值 **+0.216**（±0.45）；
- 唯二存在活跃试验多数的 config 全然恶化：c004 config-median ratio 1.831（7 活跃）、c020 1.246（5 活跃）。

### Gate M2-3 Shape-only evidence — **FAIL**
- Layer A median ratio = 1.0000（需 <1）；seed 级胜场 1/64；
- **按 §43 Stop-after-Layer-A 规则记录：direct covariance-shape hypothesis NOT supported。** Layer B 结果仅作 diagnostic，不用于挽救因果声明（亦无需挽救——Layer B 同样为负）。

### Gate M2-4 No catastrophic leakage redistribution — PASS（7/8）
- config-median of per-seed max off-target R_L,j：c000/c001/c006/c007/c010/c017 = 1.000（HOLD 平局），c020 = 1.283，c004 = **2.182**（唯一超 2.0）；7/8 ≤ 2.0 → PASS；
- selected-mode R_L config-median：c004 1.586、c020 1.152、其余 1.0；
- 解读：M₂ 恶化主要通过 **selected mode 自身泄漏放大**实现（收缩 proposal 反而提高该 mode 上的 p²/(q) 积分质量），而非把方差大规模推向其他 mode；c004 存在轻度离靶重分配（2.18 倍，未达"灾难性"多 config 门槛）。

### Gate M2-5 Relative budget efficiency — **FAIL**（方向反转）
- median VRF_budget(C4) = **0.2264** < median VRF_budget(C0) = **0.2728**；
- per-trial VRF 比值中位 = 1.000（HOLD 平局主导）；两条判据（> 与 ≥1.25）均不成立。

### Strong Gate — **NOT PASSED**
- median VRF_budget(C4) = 0.2264 ≪ 1：距 crude-MC 成本边界甚远（与 M1-D 冻结的 VRF_budget≈0.24 量级一致——M2 未改变该格局）。

### Isotropic vs Anisotropic（§32）
- C4<C1 于 4/8 config（需 ≥5）→ 结论收紧：**即便存在（本批不存在的）收益，也主要是 scale/spread 效应而非各向异性形状**；
- 且 C1 自身相对 C0 亦为负（Layer A config-median 全部 ≥1.02–1.66）——**单纯收窄/各向同性缩放同样有害**。

## 4. 消融 A–F 摘要

| 消融 | 结果 |
|---|---|
| A（scale only, C0 vs C1） | C1 在两个层均劣于 C0（Layer A 全 config median ratio 1.02–1.66）；纯 spread 缩放无益 |
| B（diagonal vs full, C2 vs C3/C4） | C2≈C3≈C4（config median 差 <1%）——off-diagonal 旋转贡献可忽略 |
| C（raw vs shrinkage, C3 vs C4） | C4 一致地轻度优于 C3（Layer B trial-median M₂：C3 0.3472 / C4 0.3309；Layer A mean：C3 0.3402 / C4 0.3287），但两者均劣于 C0（median 0.1745）——shrinkage 只减轻伤害，不翻符号 |
| D（λ 敏感性） | 主结果不随 λ 翻转；**活跃试验剂量-响应**：median ratio λ=0.25→0.50→0.75 = 1.266→1.531→1.586——λ 越大（越贴向 C_η）越差，单调 |
| E（Layer A vs Layer B） | 两层同号（均负）：不存在 covariance×weight-interaction 型收益（对照 Interpretation Matrix Row 2 排除） |
| F（ESS 分带） | low(<20)：n=43、ratio≡1.0（全 HOLD）；medium(20–200)：n=21、median 1.531、全部 >1；high：0 例——**越"可信"的区域几何反而越一致地有害** |

## 5. 机制解释（负结果的几何根源）

1. **C_η 支撑 ≪ p²/q 积分质量支撑**：η=0.8 HDR 前缀集中在 mode apex 附近，其条件协方差特征值 ≪1（raw eig 中位 ~0.1–0.4）；而 M₂(q)=∫_A p²/q 的质量对 proposal 的**尾部覆盖**高度敏感。
2. **收窄 proposal → 覆盖恶化 → M₂ 上升**：C1–C4 的净效应都是把新分量从 I 收窄到 ~0.55–0.66 量级（floor clip 只能托底、不能恢复 spread；82.5% 变体触发低侧裁剪即为此信号）。方向性错误——本基准需要的是**加宽**而非收缩。
3. **ESS 门是诚实的第一道防线**：67.2% 的变体格被预注册 HOLD 规则拦截（方差质量重尾使区域 ESS 中位仅 12.1）；在被放行的 21 个高 ESS 试验里，几何估计本身已稳定（paired |t|≤0.41、主方向对齐中位 0.949），但**稳定的错误方向**仍一致地劣化（中位 1.531，最大 7.39）。
4. 与 H3-3B 冻结结论"Σ 是 variance-region spread lever"并不矛盾：该结论说明 Σ 影响方差几何，**不**保证"向局部方差区域匹配"是 M₂ 的下降方向；M2 恰恰证伪了后一半。

## 6. 结论声明（严格按 §48 Claim Boundary）

核心 Gate（M2-2/M2-3）未通过，**§48 的正向声明（含 Strong 升级语）均不可使用**。本阶段允许且仅允许的最强陈述为：

> **On the frozen multi-missing-mode RareTopo benchmark, under matched selection, mean, and simulator budgets, adapting the covariance of the variance-critical proposal component toward the local proposal-dependent variance geometry (C1–C4, incl. the preregistered shrunk main method C4, λ=0.50) did not reduce the estimator second moment relative to the frozen isotropic base covariance; where the adaptation was not HOLD-blocked it systematically increased it (21/21 active paired trials, median ratio 1.53). The method remains below crude-MC cost efficiency (median VRF_budget ≈ 0.23).**

禁止表述（§48）：不得写"universally optimal / solves high-dimensional adaptive IS / reduces M₂"。

按 §49 负结果政策落位：**Case A（C1≈C4→非各向异性收益）与 Case E 前置形态（selected-mode 泄漏放大）成立**；Case B/C/D 部分成立（C3 vs C4：shrinkage 仅缓解不翻转；Layer A/B 同负排除 Case C 的 interaction 收益；Case D 的"降 M₂ 但 VRF<1"未出现——M₂ 根本未降）。无任何 config/λ 删除或事后挑选。

## 7. 图表索引（`figures/phase_m2/`）

| 图 | 内容 | 关键读数 |
|---|---|---|
| figure_M2_1 | 方差区域 + 三椭圆（Σ_base / C_η raw / Σ_C4） | C_η 系统性窄于 base |
| figure_M2_2 | 区域特征值 / A_C 分布 | A_C 中位 7.64 |
| figure_M2_3 | M₂ C0–C4 两层 per-config | 活跃 config 全负 |
| figure_M2_4 | C4/C0 比值两层 | Layer A median 1.0、Layer B 1.0（HOLD 主导） |
| figure_M2_5 | leakage 重分配 | c004 off-target 2.18（7/8 安全） |
| figure_M2_6 | VRF_budget + MC 边界 | C4 0.226 < C0 0.273 ≪ 1 |
| figure_M2_7 | ESS vs 增益 + HOLD 标注 | 21/21 活跃 >1；剂量-响应 |
| figure_M2_8 | λ 敏感性 | 主值不翻转；活跃层随 λ 单调恶化 |

## 8. 完成清单（任务 §51 对照）

- **Freeze/provenance**：H3/M1/M1-D tag 记录 ✅；benchmark hash 验证 ✅；task 先于运行提交 ✅（9e36696）；
- **Estimator**：weighted covariance ✅；toy/ESS/HOLD/symmetry/projection/legality 测试 ✅（§40 全名单见下）；
- **Fairness**：selection lock（64/64 溯源一致）✅；mean lock（dev=0）✅；共享 pilot ✅；CRN 配对 ✅；Layer A 同权 ✅；Layer B 同优化器（spy 断言 frozen 默认参数）✅；零额外 simulator 调用 ✅；
- **Experiments**：sanity ✅；8×8 ✅；Layer A/B ✅；λ 敏感性 ✅；leakage 审计 ✅；
- **Gates**：M2-0..M2-5 全部判定 + Strong 单列 ✅；
- **Reporting**：全部 640+256 trial 记录保留 ✅；无 cherry-picking（全 config 全 seed 全方法，含全部负值）✅；8 图可再现（脚本驱动）✅；full pytest：见下；gate audit ✅；claim 措辞与判定一致 ✅。

**§40 测试名单 → `tests/test_m2_covariance_pipeline.py`**：`test_m2_weighted_variance_covariance_toy / covariance_symmetry / covariance_ess / covariance_hold_low_ess / eigen_projection / frozen_legality_checker / selection_lock / mean_lock / shape_only_same_weights / shape_reweight_same_optimizer / no_final_eval_leakage / no_extra_simulator_calls / result_schema / leakage_redistribution_metrics` —— 15 passed（selection_lock 参数化×2）。

**全量回归证据行**：`1113 passed, 3 warnings in 307.06s (0:05:07)`（exit 0；= 冻结基线 1098 + M2 新增 15）

## 9. 对后续阶段的建议（非承诺）

1. proposal shape 的**加宽方向**（Σ = c·I, c>1）在本几何上是未被本 prereg 覆盖的显著开放方向——但任何后续探索必须走新的 prereg，不得回填 M2；
2. ESS 门槛与 pilot 预算的相互作用值得在 M1-D 固定基准之外单独研究（本批已证明：该基准 67% 格无法满足 §12 的最低作用条件）；
3. c004 型 config 的轻度离靶重分配（2.18×）提示未来 shape 方法需要显式的多 mode 泄漏约束项。

## 10. 产物清单

```text
docs/phase_m2/{M2_…_Task.md, M2_Covariance_Methodology.md,
               M2_Covariance_Legality_Audit.md, M2_Final_Report.md}
configs/phase_m2/{m2_covariance_v0.json, m2_lambda_sensitivity.json}
src/hyptraj/m2/{variance_covariance, covariance_projection,
                covariance_policy, metrics}.py
scripts/{run_m2_sanity, run_m2_covariance_experiments,
         run_m2_gate_audit, run_m2_figures}.py
tests/test_m2_covariance_pipeline.py
results/phase_m2/{sanity/, layer_a_shape_only/, layer_b_shape_reweight/,
                  ablations/, summary/{gate_audit,summary_tables,headline,
                  shape_diagnostics}}
figures/phase_m2/figure_M2_1..8*.png
```

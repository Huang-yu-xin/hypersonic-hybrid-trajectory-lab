# M3 Gradient Validity Audit — Theory, Sanity, and Pipeline Evidence

> **Schema:** `raretopo-m3-v0` ｜ **Date:** 2026-08-27
> **Machine-readable records:** `results/phase_m3/theory_checks/theory_checks_v1.json`、`results/phase_m3/sanity/sanity_v1.json`
> **Unit suite:** `tests/test_m3_covariance_pipeline.py`（任务 §29 全部 15 项，15 passed）

---

## 1. 审计范围

候选定理到可部署估计器的每层断言及其证据：

| 层 | 断言 | 证据 | 状态 |
|---|---|---|---|
| 理论 | 矩阵梯度恒等式（§5）与各向同性导数（§7） | 推导文档 + 方向 FD 49/49 | ✅ |
| 恒等锚 | p≡q 单高斯全域 M₂≡1、梯度≈0 | 8.2e-14 / 1.6e-14 | ✅ |
| 数值 | h=1e-3 中心差分：符号 100%、rel err ≤5e-3 | 49/49 探针，max 1.064e-3 | ✅ |
| 有限样本 | 估计器公式/幂等/ESS/分层 bootstrap | sanity S1/S2/S3 + 15 单测 | ✅ |
| 决策 | 优先级、CI 符号规则、评估最优方向 | 单测 widen/shrink/hold | ✅ |
| 结构 | 无最终评估泄漏、CRN 配对、记账 | 单测 + 全批 validity 块 | ✅ |

## 2. 理论门（M3-1）明细

- 探针构成：单高斯半空间 5 个合法窗内尺度点（矩阵 4 方向 × 5 + 各向同性 4）×2 种子、双分量混合两分量（全域 4 方向 ×2）、恒等锚、S3 叙事，共 **49 项**。
- **A3 窗口纪律（推导 §3）**：单分量 vs 单分量下 p²/q 沿轴 i 衰减需 `s² > λ_i(P)/2`；初始探针 {0.25, 0.49} 落在窗外使积分呈 e^{~260} 病态数值——被门捕获后替换为合法窗 ≥0.81 的探针集。**这是假设-违反的测试点设计问题，非定理失效**；门机制按设计工作（曾 FAIL → 修正 → PASS）。
- 对称真零方向（offdiag，理论值 ~1e-15）采用尺度感知绝对下限（1e-9 × 梯度尺度）而非病态相对比——已记录于检查记录 `structurally_zero` 字段。

## 3. Sanity（§20）与比较器语义

- **池化设计真值（重要）**：项目 pilot 的 target 源行为冻结语义修正固定分层设计（`r_i := logp`、N(0,I) 基测度），故有限样本量的绝对尺度携带设计常数；sanity 真值用**同一池化泛函**的象限积分（`φ₀·p/q` 槽 + `p²/q²` 槽、全局对数移位、α 混合），比值型槽（责任、D、形状因子）设计不变。教科书 ν_V 比较在绝对值上属类别错误——记录在 sanity 输出头部。
- S1 硬门：符号一致 ∧ 点wise 有效 ∧ ESS≥20（尺度 1.21/1.44 × 2 种子全过）；窗口边缘尺度（0.81/1.00）仅报告（有效样本不足、ESS<20 如实触发 HOLD_LOW_ESS 通道）。
- S2：两分量责任加权符号全过；单位分解 max dev 3.6e-15；分量 1 因含水责任质量近零属病态比较器，仅符号门槛。
- S3（解释性）：单偏置团 + 半空间事件区 —— HDR 描述性尺度 0.35 < 起点 0.55（建议收窄）而 ĝ<0（WIDEN），+0.20 步把 M₂ 从 1034.2 → 66.4 降低、按 HDR 收窄则不降。**M2 教训实体化：描述性散布 ≠ 下降方向。**

## 4. 单测清单（§29 逐名核对）

```text
test_m3_gaussian_covariance_loggrad      ✅  entrywise FD 5e-3 + Σ-收缩恒等 1e-10
test_m3_mixture_responsibility           ✅  界/单位分解/比例式 1e-12
test_m3_matrix_gradient_toy              ✅  4 方向符号+相对误差
test_m3_isotropic_gradient_toy           ✅  θ 路径 FD
test_m3_gradient_finite_difference       ✅  恒等锚 + 分母语义
test_m3_stratified_gradient_estimator    ✅  池化真值符号 + 冻结函数交叉校验
test_m3_gradient_bootstrap               ✅  层尺寸保持 / 确定性 / lo≤hi
test_m3_gradient_ess                     ✅  均匀≈N / 尖峰≈1 / 阈值接线
test_m3_direction_rule_widen             ✅
test_m3_direction_rule_shrink            ✅
test_m3_direction_rule_hold              ✅  优先级 INVALID>LOW_ESS>CI；评估最优方向
test_m3_fixed_weight_layer               ✅  Layer A 锁（仅选定分量缩放）
test_m3_counterfactual_crn               ✅  三层流分解：类采样契约逐位正确
test_m3_no_final_eval_leakage            ✅  结构签名 + rng 标签分离（101/900001/424243）
test_m3_result_schema                    ✅  §31 键集/enum/聚合正确性
```

## 5. 估计器诚实性追踪（基准暴露前拦截的缺陷）

1. **μ̂_r 多余 1/N**（sanity S3 暴露）：预注册公式 μ̂=Σâᵢr̂ᵢ 无需再除 N；错误使 D̂ 压缩 ~10³ 量级、ĝ 符号翻转。修复：在归一化权重上定义。
2. **μ̂_r 丢权重归一**（随 1 修复连带）：误用原始 Σaᵢrᵢ 使 ĝ 虚大。修复后 sanity 全符号对齐（S3 演示完成）。
3. **池化泛函漏 φ₀ 测度**（truth 侧）：target 槽 Lebesgue 积分在宽提议下发散（e^{98} 级）；补 N(0,I) 基测度后真值回到 O(1–30) 合理量级。
4. 测试自身 bug：CRN 测试重放把 widen-Cholesky 施加到全部行（含单位分量行），经三层"choice/eps/逐分量变换"分解确认**冻结类实现逐位正确**，测试修正。

以上全部记录于对应提交信息与 sanity JSON，最终批结果未受任何一项影响（均在基准运行前修复）。

## 6. 全批 validity 块汇总（gate_audit.json M3-0）

- selection lock：64/64 与归档 M1-D `variance_selector`（`selected_modes` 字段）一致，**0 mismatch**；
- mean lock：centroid 双算偏差恒 0.0；
- legality：全部 192 臂（64×3）过冻结检查器，0 失败；
- 双口径记账字段：64/64 恒为 320,000 / 120,000，0 缺失；
- 标签稳定性：M2 冻结标签为 HEAD 祖先；四个父标签与冻结记录 SHA 完全一致（H3/M1 取自 `M2_Freeze_Summary.md` 固定格式行，M1-D/M2 取自预注册配置 frozen HEAD）。
- 全量 pytest：见 Final Report §7（含本 M3 新增 15 项在内共 1128 项）。

## 7. 已知限制（如实保留）

- 估计器 δ̂ 对池化极限具有可预期重尾插件偏差（ESS 中位 189，高置信区间窄；偏差随 N 收缩但绝对量级不代表教科书 M₂）——方向判别与排序结论不受影响，绝对 VRF 结论以独立评估为准；
- S3 为解释性演示，不构成硬门；
- 本审计不覆盖全矩阵控制、策略学习或其他基准。
# H3-3B P2R — 真机样本量收敛检查报告（Stage 1）

> **Status: COMPLETE**（2026-08-22；Stage 1 (512,256) 执行完毕，Stage 2 按预注册裁定不启动）
> Branch: `feature/phase-h-uncertainty-risk`
> 任务附记（预注册）：`H3_3B_P2R_RealN_Convergence_Task.md`（先于结果入库，commit `8954ae8`）
> 路线图/台账：`H3_3B_Experiment_Path_Roadmap.md` §2.4 · `H3_3B_Phase_Execution_Ledger.md` §4
> 执行脚本：`scripts/run_h3_3b_p2r_real_n_convergence.py`（v1.1，复用 multi-system 真机管线 import-only）
> 数据：`results/phase_h3/h3_3b_p2r_real_n_convergence_v1.json`（schema `h3-3b-p2r-real-n-convergence-v1`，含 `erratum_v1_1` 勘误块）

---

## 0. 结论先行

P2R 回答 multi-system 报告遗留的问题：**真机 cov 杠杆证据来自最小审计档 (256,128)，加倍样本量后是否稳健？**

**三条结论**：

1. **主 Gate 双系统通过，且方向为改善**（实验证实）：$\rho(\mathrm{tr}\Sigma_V,R_{\eta=0.8})$ C1 0.9095→**0.9459**（+0.036）、C2 0.8610→**0.9459**（+0.085）。真机稳健性声明升级。
2. **逐 seed 秩反转完全消失**（比池化 ρ 更强的证据）：基线档每系统 4 个 seed 中有 2 个存在单调性反转（per-seed $\rho=0.8$）；(512,256) 档下 **8/8 seed-sweep 全部完美单调**（$\rho=1.000$）。
3. **附带 corpus 级勘误发现**（§5，重要）：真机辅助字段（p_mc、is_performance 的 p̂/var/VRF）存在 nominal 常量伪影——'S0' vs expected_regime 'SRTI_N2'——且**同样存在于 multi-system JSON**。主端点 $\rho$ 与区域描述子 nominal 无关、不受影响；诊断同时确认采样流与动力学环境与冻结管线**逐位一致**。

## 1. 预注册与执行摘要

| 项 | 设定 |
|---|---|
| 预注册 | 附记先于任何结果提交推送（`8954ae8`）；两阶段设计（预算约束下 1024 档 contingent） |
| Stage 1 | C1/C2 × $s^2\in\{0.75,1,1.5,2\}$ × seeds$\{1,2120,3,4\}$ × $(N_{MC},N_{IS})=(512,256)$；proposal $q=\mathcal N(x^\ast,s^2I)$ antithetic；workers=4 |
| 实际耗时 | **5995 s ≈ 1.67 h**（C1 per-seed 580–651s，C2 834–927s）——低于附记 2.7h 估计 |
| 基线 | 同公式现场重算自 frozen JSON：C1 pooled16=0.9095 / C2=0.8610（与报告值 0.910/0.861 逐位一致） |

## 2. 主 Gate 结果

| 系统 | 基线 ρ(256,128) | 新档 ρ(512,256) | Δ | 主 Gate（≥基线−0.03） |
|---|---:|---:|---:|---|
| C1 | 0.9095 | **0.9459** | +0.036 | ✅ PASS |
| C2 | 0.8610 | **0.9459** | +0.085 | ✅ PASS |

两系统的 (512,256) 档 $\rho$ 收敛到同一值 0.9459——真机 cov 杠杆映射在该样本量下达到"逐 seed 完全可预测"状态。

## 3. 逐 seed 明细与分析

### 3.1 秩反转的消失（核心改善证据）

| 系统 | 基线 per-seed ρ | 新档 per-seed ρ |
|---|---|---|
| C1 | [0.8, 0.8, 1.0, 1.0] | [1.0, 1.0, 1.0, 1.0] |
| C2 | [0.8, 0.8, 1.0, 1.0] | [1.0, 1.0, 1.0, 1.0] |

基线档每系统各有 2 个 seed 存在一处秩反转（4 点 sweep 中相邻两点 $R_\eta$ 序颠倒）；加倍 N 后 8/8 全部严格单调。机制：SRTI_N1 样本池从 ~128 点扩至 ~384 点，HDR 前缀估计的采样噪声下降，$R_\eta(s^2)$ 的真实单调关系不再被噪声淹没。

### 3.2 $R_\eta$ 配置级稳定性（seed 均值 ± 极差）

| 系统 | $s^2{=}0.75$ | $s^2{=}1$ | $s^2{=}1.5$ | $s^2{=}2$ |
|---|---|---|---|---|
| C1 | 1.817 ±0.056 | 1.492 ±0.051 | 1.290 ±0.059 | 1.215 ±0.054 |
| C2 | 1.981 **±0.221** | 1.526 ±0.052 | 1.337 ±0.065 | 1.251 ±0.063 |

- 内部 $s^2$ 点的 seed 极差普遍 ~0.10–0.13（±5% 相对量级）；**弥散端点（$s^2{=}0.75$）最噪**，尤其 C2（极差 0.441）——扩散区域的大 $R_\eta$ 对尾部采样更敏感，属预期行为。
- 与基线档对比：C1 within-seed 极差持平（0.603 vs 0.616）；**C2 变大**（0.731 vs 0.477），几乎全部由 $s^2{=}0.75$ 端点贡献——方向混杂，如实留档。

## 4. 勘误披露全记录（nominal 常量伪影；corpus 级新发现）

### 4.1 现象

v1 运行输出 `p_mc≡1.0000`、IS 接受率 100%（全部 32 个 config-seed 组合）——与基线 $p_{MC}\approx0.40\text{–}0.50$ 直接矛盾。

### 4.2 诊断设计与证据

seed-matched 前 256 个 $z_{MC}$（与基线同生成流）逐一重标注：

```
T0 setup: nominal='SRTI_N2'  alpha≈7.5e-6 (=8·|beta_local|, beta_local=-9.39e-7)
T1 first-256 labels: {SRTI_N1:127, SRTI_N2:129}
    → p_mc(≠'SRTI_N2') = 127/256 = 0.49609 —— 与基线 JSON 0.4961 逐位一致
T2 full-512 labels:  {SRTI_N1:247, SRTI_N2:265}  p_mc=1.0000 (vs 'S0')
```

**证据链**：(i) 相同样本产生与基线完全一致的标签分布 ⟹ 采样流、坐标变换（$x=center+S_A(\alpha z)$）、动力学环境与冻结管线**逐位一致**；(ii) 分歧仅在比较常量：我的 v1 用 `ms.NOMINAL='S0'`，而 case 的 expected_regime 是 `'SRTI_N2'`（mlb1 anchor 字段）——没有任何真机样本会是 'S0'，故 p_mc≡1、接受率恒 100%。

### 4.3 根因与机制补充

- $\beta_{local}=\pm9.3\times10^{-7}$：设计点到 nominal 边界的距离在浮点意义上为零，$\alpha\approx7.5\times10^{-6}$ 的放大后扰动仍是米级——N1↔N2 的翻转由轨道动力学的混沌敏感性决定。这正是 H3-3A 判定 C1 为 plateau、multi-system 判定其 aligned 的物理背景；协议本身如此，非缺陷。
- **波及范围**：p_mc 与 is_performance 辅助字段受污染；**区域描述子（R/C/G/D）与解析 $\Sigma_V$ 及一切 $\rho$ 端点 nominal 无关、不受影响**。

### 4.4 corpus 级波及（新发现的审计项）

同样的常量伪影**已存在于** `h3_3b_multi_system_validation_v1.json` 的真机 is_performance 字段（实测 acc=n_total、p̂≈0.98）——即 multi-system 报告 §4.3 引用的真机 VRF 数值（C1 0.34–0.96 等）是在"$A$='S0'"的错误事件定义下算出的，语义存疑。**需要强调的边界**：multi-system 的全部 Gate 结论（Gate A 的 ρ、Gate B 的描述子 range、Gate C 方向性）均基于区域描述子与解析量，**不受此伪影波及**；受影响的仅是真机 VRF/p̂ 辅助叙事。已登记为未来审计项（Final Summary §6.6）；若论文需引用真机 VRF，须以正确 nominal 重算后再引。

### 4.5 处置清单

① P2R JSON 打 `erratum_v1_1` 勘误块（受影响/不受影响字段逐项列明）；② 脚本 v1.1 改用 setup nominal 并注明缘由；③ 台账 §4.3 完整披露；④ 本报告 §4 存档诊断证据链。

## 5. Stage 2 裁定

按附记的 contingent 条款："仅当 Stage 1 显示 $\rho$ 随 N 改善且需要趋势第二点时"启动 (1024,512) 档（预计 5.4h）。裁定：**不启动**。理由：主 Gate 已通过且方向为改善、逐 seed 单调性已满贯，稳健性主张成立；N-trend 第二点的边际信息不抵成本。如未来论文需要 N-trend 曲线图，另行预注册后执行。

## 6. Claim Boundary

❌ 不声称 $\rho$ 随 N 收敛到 1 或任何渐近值（单次倍增观测，非收敛研究）；❌ 不声称 $R_c$/regime 边界因此更准（P2R 只证 cov 杠杆端点的稳健性）；❌ 不声称 C2 的 $s^2{=}0.75$ 噪声增大是普适现象；❌ 不在重算前引用任何真机 VRF/p̂ 数值（§4.4 勘误）。

✔ 主张：**(512,256) 档下，两真机系统的 cov 杠杆映射无退化且逐 seed 完美单调（8/8），$\rho$ 提升至 0.946**——限定于这两 case、这一 proposal 族、这一 $s^2$ 网格。

## 7. Artifacts

脚本 `run_h3_3b_p2r_real_n_convergence.py`（v1.1）· 数据 `h3_3b_p2r_real_n_convergence_v1.json`（含 erratum_v1_1）· 任务附记 · 本报告 · 台账 §4 · Final Summary §9。诊断过程记录于会话汇报与本报告 §4（临时诊断脚本已清理）。

## 8. 对后续的接口

- 论文 Section X：真机段落可写"(512,256) 下 $\rho=0.946$，8/8 seed-sweep 严格单调"；真机 VRF 引用前须按 §4.4 重算；
- ML-H4：真机训练标签的区域描述子字段可直接使用（nominal 无关）；
- Final Summary §6.6 登记的真机辅助字段审计项保留，优先级随论文需要而定。

## 9. 一句话总结

> **P2R Stage 1 完成（1.67h，低于预估）：真机 cov 杠杆 ρ 在加倍样本量下双系统过主 Gate 且改善至 0.946，基线的 2×2 个反转 seed 全部消失（8/8 完美单调）——真机稳健性声明升级；过程中揪出并勘误一个 corpus 级辅助字段伪影（nominal 常量 'S0' vs 'SRTI_N2'，波及 multi-system 真机 VRF 叙事但不波及任何 ρ/regime 结论），诊断链完整存档。**

# H3-3B P2R — 真机样本量收敛检查：任务附记（预注册）

> **Status: TASK FROZEN（预注册先于执行；本文件提交后脚本才启动）**
> 路线图：`H3_3B_Experiment_Path_Roadmap.md` §2.4（P2R 可选模块）
> 上游：`H3_3B_multi_system_validation_report.md` §4/§9.2（真机最小审计档 256/128，$\rho=0.910/0.861$）
> 执行脚本：`scripts/run_h3_3b_p2r_real_n_convergence.py`（复用 `run_h3_3b_multi_system_validation` 真机管线，import-only）
> 输出：`results/phase_h3/h3_3b_p2r_real_n_convergence_v1.json`（schema `h3-3b-p2r-real-n-convergence-v1`）

---

## 1. 研究问题

multi-system 的真机 cov 杠杆证据（$\rho(\mathrm{tr}\Sigma_V,R_{\eta=0.8})$：C1 0.910 / C2 0.861）来自最小审计档 $(N_{MC},N_{IS})=(256,128)$。**加倍样本量后 $\rho$ 是否退化？** 这决定论文真机段落的稳健性声明强度。

## 2. 两阶段设计（预算约束下的预注册）

按 multi-system 实测吞吐（7168 样本 / 95 min ≈ 1.26 样本/s wall，workers=4）：

| 阶段 | 配置 | 样本量 | 预计 wall | 状态 |
|---|---|---|---|---|
| **Stage 1** | C1+C2 × $s^2\in\{0.75,1,1.5,2\}$ × 4 seeds × $(N_{MC},N_{IS}){=}(512,256)$ | 12,288 | ≈2.7 h | 本任务书执行 |
| Stage 2（contingent） | $(1024,512)$ 档 | ≈24.6 k | ≈5.4 h | **仅当** Stage 1 显示 $\rho$ 随 N 改善且需要趋势第二点时，另行预注册后执行 |

**两阶段裁定的诚实理由**：若 Stage 1 已无退化，1024 档的边际信息是"趋势第二点"；若 Stage 1 退化，1024 档更无必要。两种情形下 Stage 2 都不是必须——避免为跑而跑。

## 3. 冻结协议

| 项 | 设定 |
|---|---|
| 系统 | C1 (SRTI_N1)、C2 (SRTI_N3)；frozen 锚点与 $\alpha{=}8\lvert\beta\rvert$ 变换逐位承 multi-system |
| 扫描 | cov sweep $s^2\in\{0.75,1,1.5,2\}$（与 multi-system 同格）；proposal $q=\mathcal N(x^\ast,s^2I)$，antithetic |
| seeds | $\{1,2120,3,4\}$；workers=4 |
| 主指标 | $\rho(\mathrm{tr}\Sigma_V,R_{\eta=0.8})$，16 行池化（4 $s^2$ × 4 seeds，与 multi-system 同公式）+ per-seed 副本 |
| 基线 | 从 `h3_3b_multi_system_validation_v1.json` 用**同一公式**现场重算（256/128 档），保证可比性 |
| 辅助指标 | $R_\eta$ seed 极差（vs 基线档）、$p_{MC}$、VRF/ESS、$\mathrm{tr}\Sigma_V$ 闭式核验 |

## 4. Gates（预注册）

- **主 Gate（每系统）**：$\rho_{(512,256)} \ge \rho_{(256,128)}^{baseline} - 0.03$（无退化）。两系统均过 ⟹ 真机稳健性声明升级；任一失败 ⟹ 按系统如实缩限。
- **辅观察（不设阈值）**：$\rho$ 随 N 的方向；$R_\eta$ seed 极差相对基线档的变化；C1（plateau）与 C2（aligned）是否表现一致。
- **失败预案**：$\rho$ 不升反降超容差 ⟹ 如实报告"真机映射精度受 N 之外因素主导"（候选：动力学混沌敏感性、mode 内异质性），真机 claim 缩限至最小审计档结论，不调协议、不挑 $s^2$。

## 5. Claim Boundary

❌ 不声称 $\rho$ 随 N 收敛到 1（采样噪声之外还有模型因素）；❌ 不外推到其他 N/其他 case；❌ 不因结果调整 $s^2$ 网格或 seeds。✔ 主张范围：在 (512,256) 档下，cov 杠杆映射在两真机系统上的稳健性状态（维持/改善/退化的实测方向与幅度）。

## 6. 一句话总结

> **P2R 附记：真机 cov 杠杆 $\rho$ 的样本量稳健性检查——Stage 1 (512,256) 全 sweep 双系统（≈2.7h）预注册主 Gate 为相对基线无退化 0.03，Stage 2 (1024) 视结果 contingent；失败预案为缩限真机 claim，不救数据。**

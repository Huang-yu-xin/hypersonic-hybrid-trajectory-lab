# M1-2 审查报告 — variance-measure / mode-discovery / closed-loop 四模块 + Benchmark A

> **Status**: passed（审查中发现并修复 1 个工程缺陷 + 2 处语义/信念错误后全绿）
> **Reviewer**: python-code-reviewer（主 agent 执行，对照 M1 预注册 task）
> **Date**: 2026-08-26
> **审查对象**（commit `c2f90ce` + `ae12936`）：
> - `src/hyptraj/m1/variance_measure.py`、`mode_discovery.py`、`proposal_update.py`、`closed_loop.py`
> - `tests/test_m1_variance_measure.py`、`test_m1_mode_discovery.py`、`test_m1_closed_loop.py`（共 34 项含 M1-1 的 18 项）
> - `scripts/run_m1_halfspace_sanity.py` + `results/phase_m1/m1_halfspace_sanity_v0.json`
> **对照计划**: task §7 / §10 / §11 / §12 / §13 / §15 / §16 / §17 / §18 / §20(A) / §29.2 / §29.3 / §29.5 / §29.6 / §31

---

## 一、Pass Items（具体可引用）

1. ✅ **§7 方差质量公式逐项实现**：`variance_measure.py:33-50` `variance_mass_weights` = \(1_A p^2/(q_t·r_i)\)（log 空间，\(r_i\) 逐样本保留）；`estimate_variance_measure` 输出 \(M_2=(1/N)Σω̃\)、\(L_k=(1/N)Σ_{A_k}ω̃\)、\(\omega_k^V=L_k/M_2\)、归一化质量权重作 \(\hat\nu_V\)；三种采样源（r=p、r=q、混合 pooling）数值无偏（rel 5e-2 内；r=q 时 \(\omegã=p^2/q^2\) 即经典 \(w^2\) 式逐位一致 1e-8）。
2. ✅ **§29.3 分解一致性**：d=1 crafted 2-mode 上 `sum(L_k) == M2_hat`（rel 1e-10）、`sum(omega_k^V) == 1`；测试同时验证"raw count 不是 variance mass"：S2 样本占比 <1% 而 \(\omega_2^V>0.9\)（`test_m1_variance_measure.py` TestModeDecomposition）。
3. ✅ **§11/§12 birth gate 冻结**：`mode_discovery.py` 用 config 冻结值（0.10/0.05/n≥5），测试直接读 `configs/m1_closed_loop_v0.json` 锁定并与 task §12 对照（改值须 amendment）；`represented_by_component` 与 omega 双条件；bootstrap LCB 仅对潜在候选计算（HOLD 轮省 ~10×）。
4. ✅ **§29.6 birth 行为三案例**：variance-dominant 次模式（P~3e-4 但 \(\omega_2≈0.996\)）通过 gate 触发；far nuisance（期望 0.015 观测）不可见 → 不触发；已 represented 的 mode 即使 \(\omega\) 巨大也不触发 → HOLD。
5. ✅ **Benchmark A case A1（8 预注册 seeds）**：8/8 `no_missing_mode` HOLD、0 false birth、final proposal 恒 1 组件；8/8 P̂ 无偏（vs \(Φ(-1.5)=0.0668\)，3SE 判定）；8/8 M̂₂ 一致（vs 闭式 \(e^{\|m\|^2}Φ(a+m_1)=0.01281\)，10% 内）；预算 = 20000 pilot + 100000 eval，无超支。
6. ✅ **Benchmark A case A2（机制演示）**：7/8 seeds 正确 birth S2 且 0 错误 mode birth（1 seed 信息不足 HOLD，Poisson 期望 6.8 观测 → 理论预期行为）；6 个有效 drop 中 M2 相对下降 97.7–99.4%（独立诊断 pilot 口径）；全部 seeds P̂ 无偏。
7. ✅ **§15 权重更新 + §31 solver 记录**：闭环内 SLSQP 每次 birth 记录 kkt_residue（1e-7~4e-9 ≤ 1e-6）、objective_init→final（如 0.0305→0.0264）、n_iter、centroid_eta_used；未收敛路径 stop_reason=`optimizer_non_convergence` → HOLD。
8. ✅ **§16/§17 HOLD 与 stop rule**：无候选 → `no_missing_mode`；M2 相对改进 < 0.02 → 停止（冻结常量测试 `test_stop_constants_frozen`：3 轮 / 0.02）；centroid/optimizer 失败显式转 HOLD 并保留 reason，不静默成功。
9. ✅ **§18 防火墙**：final eval 用独立随机流（`seed+400000`）在 q_final 冻结后生成；权重优化样本 = 冻结 pilot（两阶段协议）；闭环每轮 pilot 独立重抽。
10. ✅ **H3 冻结零改动 + 可追溯**：`git diff RareTopo-H3-v1.0` 仅新增 M1 文件；结果 JSON 含 `git_commit`/`config_sha256`/`seeds`/`timestamp_utc`/逐 seed 记录；34 项 M1 单元测试全过。

---

## 二、审查中发现并修复的问题

| # | 位置 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | `proposal_update.eta_region_centroid` | η=0.8 区域对稀有 mode 常 <2 样本 → ValueError → seed 2027 无法 ADD（M2 保持 3.845，泄漏未修复） | 工程回退：region <2 时退化全 mode 质心且 `eta_used=1.0` 记录；docstring 显式声明为 implementation detail（非预注册参数修改） | 2027 成功 birth，drop 98.6%；`centroid_eta_used` 入 §31 记录 |
| P2 | 脚本出生语义 | `births` 记录了 candidate（含 centroid 失败/optimizer 失败未实际添加者），与"实际出生"混淆 | 仅统计 `action=="ADD_COMPONENT"` 迭代 | 修正后 n_birth=7 与实际 drop 数一致 |
| P3 | 脚本+测试参考概率 | IS 估计目标是 **p 下**概率，参考却写成 q₀ 下概率（`Φ(a−m)`）——概念混淆 3 处 | 改为 `Φ(a)`（target 口径）；A1 专用参考 `p_ref_a1()` | P_unbiased 8/8 |
| P4 | 测试容差 | rel=2e-3 ≈ 0.08 SE，必然反复失败 | 统计合理容差 1e-2~5e-2（区分公式错误与噪声） | 全部通过 |
| P5 | 测试 IS 采样源 | 从 p 采样却用 IS 权重（算出的实为 M2） | 改为从 q₀ 采样 | P̂=0.0668 vs Φ(-1.5) ✓ |
| P6 | nuisance 断言 | S3 零观测 → 根本不在 mode 列表 → KeyError | 断言改为"不存在或 n<5 且不 eligible" | 通过 |

---

## 三、Remaining Risks

- **稀有 mode 的 centroid 精度**：η=0.8 回退到全 mode 质心（≤6 样本）时，新组件位置可能偏离真实泄漏区；方向性安全（HOLD 不会更糟），但 M1-3/4 的 H3-1 benchmark 若 pilot 观测同样稀疏，需先评估是否触发 amendment（task §37）或接受该实现细节。
- **HOLD-seed 的 M2/eval 高方差**：seed 2033（信息不足未 birth）final eval 的 \(\hat M_2=1.53\)、\(\hat P\) 的 3SE 容差被高方差掩盖——这是"未覆盖泄漏"的真实量化（无偏但方差巨大），不是错误；Benchmark B 报告必须按此如实呈现，不做 seed 剔除。
- **bootstrap LCB 对 n≈5 的覆盖**：保守方向（低估 LCB → 少 birth → HOLD），与信息不足语义一致；已由 §12 gate 的 n≥5 前置条件兜底。
- **A2 触发率依赖 pilot 信息量**：7/8 符合 Poisson(6.8) 理论预期；Gate 1（≥7/8）正式判定在 Benchmark B（H3-1 真实配置）进行，不得把 A2 当 gate 证据。

---

## 四、运行说明

```text
.venv/Scripts/python.exe -m pytest tests/test_m1_*.py
.venv/Scripts/python.exe scripts/run_m1_halfspace_sanity.py
```

## 五、期望输出

- 34 passed；`results/phase_m1/m1_halfspace_sanity_v0.json`（sanity_overall_pass=True）

## 六、推荐下一步

按 task §33 run order：**M1-3（H3-1 variance-important missing-mode discovery）**——复用 frozen H3-1 benchmark 定义（`scripts/run_h3_variance_leakage.py` 语义），在 8 预注册 seeds 上评估 Discovery Gate（≥7/8），FAIL 则按 task §33 STOP。需先读取 H3-1 脚本确认事件/拓扑/Nominal 定义与 pilot 观测规模，并确认 M1-2 闭环在此配置上的信息量。
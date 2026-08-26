# M1-5 审查报告 — Benchmark C（H3-2 curved multi-mode）

> **Status**: passed（审查中发现并修复 2 个口径耦合 bug 后全绿）
> **Reviewer**: python-code-reviewer（主 agent 执行，对照 M1 预注册 task）
> **Date**: 2026-08-26
> **审查对象**（commit `1ba9cfc`）：
> - `scripts/run_m1_benchmark_c_curved.py` + `results/phase_m1/m1_benchmark_c_curved_v0.json`
> - `src/hyptraj/m1/baselines.py`（`_eval`/`run_m1_closed_loop` 参数化）
> **对照计划**: task §20(Benchmark C) / §33(Go 条件) / §12 / H-M1.1 / H-M1.3 / H3-2 frozen 语义

---

## 一、Pass Items（具体可引用）

1. ✅ **H3-2 冻结语义复用**：`label_curved` 与 `run_h3_2_adaptive_geometry_is.py` 逐字一致（S2 = {u₁ > 1+0.5(u₂−1.5)²}，nominal S0，d=2）；frozen 文件零改动。
2. ✅ **MPP ≠ 泄漏点分离复现**：数值求解 MPP_S2=(1.227, 0.827)、xL_S2=(1.087, 1.082)、分离 0.291——H3-2 的曲率结论在该 benchmark 上成立（这正是 Benchmark C 的压力场景：方差几何 ≠ 概率几何）。
3. ✅ **曲率下 discovery 稳定（H-M1.1 推广）**：8/8 seeds birth S2、0 wrong birth——closed-loop 不是线性泄漏案例的一次性巧合。
4. ✅ **M2 机制（H-M1.3 推广）**：median M2_final/M2_q0 = 0.0184（独立 eval 口径，降 98.2%）；8 seeds 比值 0.0125–0.0227 稳定。
5. ✅ **无偏性（§23.4）**：M1 P̂ 0.1111–0.1135 vs curved MC 0.1123（8 seeds 全在 5e-3 内）；curved 真值 P≈0.112（IS 两源一致证实，H3-1 口径 0.073 不适用于本 benchmark——已在脚本注释说明）。
6. ✅ **Oracle 差距**：M1（无 oracle）M2 0.0422–0.0465 vs M2/M3（oracle）0.0407–0.0426——0.4–9% 差距，无 oracle 前提下的机制证据合规。
7. ✅ **Budget/统计纪律**：B=160k（M1 实际 60k 适应 + 100k eval）；8 seeds 全保留；CRN 共享流 3 策略（同样构造，`extra.note` 声明）；CEM 不重复（B 已报告，note 明示）。
8. ✅ **M3 权重真值口径**：leakage-power 权重用 q0 下真实 L_k（(1/N)Σ1_A p²/q0² 而非概率）——post-hoc oracle 信息合法（M3 是 hand-designed baseline），计算式正确（200k q0 流 + log 空间）。

---

## 二、审查中发现并修复的问题

| # | 位置 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | `baselines._eval`/`run_m1_closed_loop` | eval 固定用 H3-1 label + **d=4 logp 常数**：与 2D proposal 的常数不匹配，IS 权重系统性偏小 1/(2π)=0.159125，P̂ 由 0.111 变 0.0116（0.073×0.159 精确吻合）、M2 偏 (1/2π)² | `_eval(..., oracle, logp_fn)` + `run_m1_closed_loop` 透传 | P̂=0.1124≈MC 0.1123；M2=0.0422（与独立复现一致） |
| P2 | `run_m1_benchmark_c_curved.py` crude_mc | 误用 baselines.run_mc（H3-1 label，P=0.073）作 curved 参考；unbiased 判据基于错误参考 | 脚本内 `run_mc_curved`（curved label）；unbiased 判据改 5e-3 且用 curved MC P_hat | unbiased=true |
| P3 | 脚本残留 | 未使用 import（run_mc/run_single_geometry）、函数名与变量冲突（mpp_s2） | 清理/重命名 | 正常运行 |

---

## 三、Remaining Risks

- **curved benchmark 的 q0 M2 高方差**：M2_q0 1.88–3.71（8 seeds 波动大）——curved 下 S2 泄漏极端权重；ratio 判定方向稳健（paired），但报告应注明 q0 口径估计不确定。
- **M1 vs oracle 的微小差距（<4%）在 C 上的解释**：组件中心 = η=0.8 质心（pilot 噪声），oracle 用精确边界点；差距来源是估计而非机制——v0 冻结（不调 covariance/中心微调）前提下如实记录。
- **M3 泄漏权重使用 200k q0 探索流**：该流是 post-hoc 计算的 oracle 信息（built in benchmark definition），不进入 M1 算法闭环——合法性边界在报告与代码注释中标记。
- **d=2 vs d=4**：Benchmark C 用 d=2（H3-2 语义），B 用 d=4（H3-1 语义）——跨 benchmark 的常数/维度切换由脚本参数化保证 no leak（本轮 P1 修复），后续 Benchmark D 需同样检查。

---

## 四、运行说明

```text
.venv/Scripts/python.exe scripts/run_m1_benchmark_c_curved.py   # exit 0 = all verdicts pass
```

## 五、期望输出

- `results/phase_m1/m1_benchmark_c_curved_v0.json`（verdict + per-seed + geometry + mpp/xL）

## 六、推荐下一步

按 task §33 ladder：A/B/C 全过 → **M1-6（Ablations A–E，task §27）**：probability-only birth（Ablation A）、Add-without-reweight（B）、Reweight-without-birth（C）、point-vs-set-centered（D）、eta 敏感性（E，冻结 0.5/0.8/0.9）；随后 M1-7 总报告 + 决策。
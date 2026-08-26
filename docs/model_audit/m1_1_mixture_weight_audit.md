# M1-1 Mixture-Weight Convexity 审查报告

> **Status**: passed（审查中发现并修复 2 个实现级缺陷后全部验证通过）
> **Reviewer**: python-code-reviewer（主 agent 执行，对照 M1 预注册 task）
> **Date**: 2026-08-26
> **审查对象**（commit `a136721`）:
> - `src/hyptraj/m1/mixture_weights.py`
> - `src/hyptraj/m1/__init__.py`
> - `tests/test_m1_mixture_weights.py`
> - `scripts/run_m1_weight_theory_check.py`
> - `configs/m1_closed_loop_v0.json`
> - `docs/phase_m1/M1_Theory_Mixture_Weight_Convexity.md`
> **对照计划**: `docs/phase_m1/M1_Closed_Loop_Variance_Geometry_Adaptive_IS_Task.md` §14 / §15 / §18 / §29.1 / §29.4 / §41

---

## 一、Pass Items（具体可引用）

1. ✅ **公式逐项对照 task §14.1**：`mixture_weights.py:143-148` `m2_gradient` 实现 (T1) `-(1/N)Σ1_A p²q_j/(q_π²·r)`（log 空间，`2logp−logr−2logq_π+logq_j`）；`mixture_weights.py:152-158` `m2_hessian` 实现 (T2) `2/N·Σ1_A p²q_jq_ℓ/(q_π³·r)`。FD 回归验证：梯度 max rel err = 1.36e-10（tol 1e-6），Hessian FD rel err = 7.6e-9（tol 1e-5）。
2. ✅ **无偏性（理论 §9.1 三条路径全部实证）**：V1a 以 r=p 对照 J=1 闭式 `e^{m²}Φ(a+m)`；V1b r=q_{π0} 冻结后对 π≠π0 与 π=π0（经典 w² 式）三组；V1c 混合 pilot（r1=p、r2=q_{π0}）pooling —— 全部 bias ≤ 3 SE。
3. ✅ **预注册冻结一致性**：`run_m1_weight_theory_check.py` 内建 8 项 task 锁定值自检（tau_birth=0.10/0.05、min_obs=5、eta=0.8、pilot=20000、max_iter=3、eval=100000、seeds=[2026..2033]）与 `configs/m1_closed_loop_v0.json` 比对通过，无 mismatch；config 含 sha256 记录。
4. ✅ **§15 冻结求解器行为**：SLSQP + analytic gradient（`optimize_mixture_weights` 以 `jac=m2_gradient` 传入），simplex 等式约束 + [floor,1] bounds 保持（sum=1 至 1e-8），floor=0.0 显式声明（config `floor_policy`）；KKTres max = 1.2e-7 ≤ 1e-6（理论 §8 残余定义）。
5. ✅ **初始化无关 + 经验凸性（理论 §9.2/§5.3）**：4 种初始化（均匀/单峰×2/混合）权重 spread 2.0e-7 ≤ 1e-6、目标 spread 2.1e-14 ≤ 1e-8；200 随机段中点凸性零违例；Hessian eig_min = 0.0178 > 0 → 唯一全局极小（非数值巧合，理论保证）。
6. ✅ **测试矩阵补全 §29.1/§29.4**：`tests/test_m1_mixture_weights.py` 18 项全过（weights 校验、logsumexp 稳定性、ordering invariance、梯度 FD、Hessian 对称/PSD/vᵀHv、FD(grad)、凸性段、退化重合组件 flatness、无事件拒绝）；全量 `1036 passed` 零回归。
7. ✅ **H3 冻结完整性（task §4.1）**：`git diff RareTopo-H3-v1.0` 仅新增 M1 文件；`src/hyptraj/uncertainty/`、`docs/phase_h/`、`scripts/run_h3*`、`tests/test_h3*` 零改动；M1 模块为纯 numpy/scipy 分析层，不 import 仿真器。
8. ✅ **§16/§25 Gate-0 语义**：无事件样本显式 `ValueError`（m2_hat/gradient/hessian/optimize 四路径），SLSQP 失败返回 `success=False` + NaN 标记，禁止静默成功进入比较；错误路径被测试覆盖。
9. ✅ **§18 数据切分防火墙接口**：`logr` 是输入且与 π 独立（两阶段协议：先以 r=q_t 抽样本、再固定样本优化 π），理论文档 §9.3 明确禁止 r 随 π 重抽；无任何 API 允许该违规路径。
10. ✅ **可追溯性（task §38）**：`results/phase_m1/m1_weight_theory_check_v0.json` 含 `git_commit=a136721`、`config_sha256`、seed=2026、timestamp_utc、逐项数值 —— 审查中发现运行时机导致 commit 记录过期，已在最终 commit 上重跑修正（见修复 P5）。

---

## 二、审查中发现并修复的问题

| # | 位置 | 问题 | 修复 | 验证 |
|---|---|---|---|---|
| P1 | `mixture_weights.py` m2_hessian | 外积技巧错误：`aᵀa` 使指数翻倍（4logp−2logr−6logq_π），量级差 5 个数量级 | 改为 `aᵀq`（`a=w·q_j`，`q=q_j`），指数正确为 `2logp−logr−3logq_π+logq_j+logq_ℓ` | FD of direction gradient 7.6e-9；对称 1.1e-16；测试全过 |
| P2 | `tests/...` 批量替换 | `_batch_bias` 缩进损坏 → IndentationError | 恢复模块级定义 | 18 测试通过 |
| P3 | 脚本+测试 quad 参考 | 被积函数尾部 0/0 → NaN + roundoff 警告，参考值失真 | log 空间被积函数（logaddexp.reduce） | V1b/c 参考与闭式自洽 |
| P4 | 脚本 JSON 输出 | numpy bool/scalar 不可序列化 | `_py()` 递归转换 | 输出完整写入 |
| P5 | 结果文件溯源 | 首次运行时 HEAD=d102d79，未含实现 | 最终 commit 重跑 | git_commit=a136721 |
| P6 | `mixture_log_density` | SLSQP 边界探测 `np.log(0)` 警告 | `np.errstate(divide='ignore')` + logsumexp 天然处理 -inf | 警告消除，结果不变 |

---

## 三、Remaining Risks

- **极值 π 数值量级**：权重→0 组件的 log-sum-exp 中间量在最坏情形可能上溢/下溢。v0 冻结 Gaussian 族 + 当前 N(≤8000) 与事件集上未触发；若 M1-3/4 pilot 出现极端情形，目标非有限 → `success=False`/INVALID 路径兜底（§16），需记录不进入比较。
- **ftol=1e-12 对超大 N 可能偏紧**：当前验证 N≤8000 全部收敛（KKTres 1e-7）；M1-4 pilot=20000 时需确认 SLSQP 在 maxiter=500 内收敛，否则按 HOLD 语义上报。
- **统计门确定性**：3 SE 断言基于固定 debug seeds；numpy 版本漂移可能微移数值，但实测余量充足（比值 ≪ 3），容差设计留有安全裕度。
- **理论范围纪律**：定理 C1 已标记 "M1-1 verified theorem"（仅 M1 命名空间），未写入 H3 frozen claim set —— 后续任何报告不得越级引用为 universal 结论（task §40 防火墙）。

---

## 四、运行说明

```text
.venv/Scripts/python.exe -m pytest tests/test_m1_mixture_weights.py
.venv/Scripts/python.exe scripts/run_m1_weight_theory_check.py
```

## 五、期望输出

- 测试：18 passed
- 脚本：`results/phase_m1/m1_weight_theory_check_v0.json`（overall_pass=True）

## 六、推荐下一步

按 task §41 run order：**M1-2（Affine/Half-Space Sanity，Benchmark A）** —— 复用本模块的 m2 目标与 SLSQP，验证无 missing-mode 时闭环 HOLD 且不产生 false birth（task §29.5/§29.6 的 HOLD/Birth 行为测试随 M1-2 落地）。
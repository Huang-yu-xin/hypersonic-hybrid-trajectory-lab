# M3 Methodology — Second-Moment Gradient Covariance Control

> **Schema:** `raretopo-m3-v0` ｜ **Date:** 2026-08-27 ｜ **Branch:** `feature/phase-m3-scalar-gradient-control`
> **Frozen chain:** `RareTopo-H3-v1.0` / `RareTopo-M1-v0` / `RareTopo-M1-D-v1.0` / `RareTopo-M2-v0`（M2 冻结提交 `0a00f44`）
> **Task:** `docs/phase_m3/M3_Second_Moment_Gradient_Covariance_Control_Task.md`（Sec. 1–28）
> **Prereg config:** `configs/phase_m3/m3_scalar_gradient_v0.json`（零修订）

---

## 1. 研究问题与对象

M3 检验：**有限样本二阶矩协方差导数能否为选定的高斯提议分量给出正确的 WIDEN / SHRINK / HOLD 决策，且按预注册小步长移动能降低独立评估的 M₂。**

控制变量为标量各向同性尺度：`Σ_k = s_k² I`、`θ_k = log s_k²`，仅改变选定新生成分量的协方差；均值、全部权重、其余协方差、分量数在 Layer A 全部冻结（§12）。

## 2. 数学对象（推导见 `M3_Covariance_Gradient_Derivation.md`）

```text
q(x) = sum_j pi_j q_j(x);   r_k(x) = pi_k q_k(x)/q(x)
M2(q) = int_A p^2/q dx;     nu_V(dx) = 1_A p^2/q / M2 dx
grad_{Sigma_k} M2 = (M2/2) Sigma^-1 [ E[r_k]Sigma - E[r_k delta delta'] ] Sigma^-1
g_k = dM2/dtheta_k = (M2/2) E[r_k] (dim - D_k/s_k^2),  D_k = E[r_k||delta||^2]/E[r_k]
```

与失效 M2 的本质区别（§1、§6）：对象是**对 M₂ 求导得到的控制信号**，而非描述性几何匹配；责任加权作用于**整个池化测度**，不限于 top-η HDR。

## 3. 有限样本估计器（§8）

在共享 pilot（20k、α=0.5、冻结 `rng=[seed,101]`、冻结混合抽样顺序）上：

```text
a_i     = 1_A(x_i) p(x_i)^2 / (q(x_i) r_i(x_i))      # 冻结方差质量重要值（逐字复用）
ab_i    = a_i / sum a_i
mu_r    = sum ab_i rhat_ki                           # == schema 的 responsibility_mass
D_hat   = sum ab_i rhat_ki ||x_i - m_k||^2 / mu_r
g_hat   = (M2_hat/2) * mu_r * (dim - D_hat/s_k^2),   M2_hat = (1/N) sum a_i
c_i     = ab_i rhat_ki / sum ... ;  ESS_grad = 1/sum c_i^2
```

单位协方差族上与冻结 `variance_mass_weights` 做逐位交叉校验（任何偏差即抛错）。实现纪律：`mu_r` 在归一化权重上定义、无额外 1/N、无未归一化求和——这两个缩放错误在 sanity 阶段被拦截并回归记录（见 Validity Audit §6）。

## 4. 不确定性与决策（§9–10）

- Bootstrap：**冻结固定分层方案**——p/q 源层内重采样、层尺寸精确保持、`seed=[seed,424243]`、500 复本、95% 分位 CI。
- 决策优先级（预注册锁定）：`HOLD_INVALID > HOLD_LOW_ESS (ESS_grad<20) > WIDEN(CI上<0) / SHRINK(CI下>0) / HOLD_UNCERTAIN`。点符号永不用于头条结论。
- 合法性：每个扰动后协方差过冻结检查器 `min_eig >= LEGALITY_MIN_EIG=0.5`；e^{±0.40}·I₂ 最小特征值 0.670 ≥ 0.5，故全部预注册档恒合法，违规记 `HOLD_INVALID`。

## 5. 步长与反事实协议（§11–14）

```text
delta_theta_main = 0.20（sensitivity 仅 [0.10, 0.20, 0.40]，主格恒为 0.20）
s_new^2 = s_old^2 * e^{±delta_theta}
```

每试验独立评估 **BASE / WIDEN / SHRINK** 三臂（100k、`rng=[seed,900001]`），**CRN 配对**：Layer A 权重、分量结构、分量顺序相同 ⇒ `choice` 与 `standard_normal` 流逐位一致，仅选定分量 Cholesky 缩放不同（结构性质经三层流分解测试验证）。pred/opposite 从两扰动臂映射；评估最优方向按 tie tolerance=0.01 三臂两两对比 §14。

## 6. 双口径 Simulator-Call 记账（§22）

```text
scientific_audit_calls  = 20k + 3×100k = 320,000 / trial（研究诊断口径）
deployable_method_calls = 20k + 100k   = 120,000 / trial（只计 GRADIENT 动作路径）
```

选择动作的评估复用已计算诊断臂；反向科学诊断不计入可部署 VRF。64 试验：研究口径总计 20.48M 抽样（pilot 1.28M + 评估 19.2M），梯度估计本身 **零额外 simulator 调用**（复用共享 pilot）。

## 7. 层语义（§12、§21、§24）

- **Layer A（主判据层）**：所有权重 = 冻结 M1-v0 SLSQP 输出 `pi_C0`；反事实仅改选定分量尺度。
- **Layer B（不可救赎层）**：每臂用冻结 SLSQP 核对各分量比例密度重配权重（`optimize_mixture_weights` 原样复用）；仅为审计，若 A 层方向假设失败 B 层无济于事。
- 对照方法：**HOLD**（不动）/ **SHRINK**（固定 −0.20）/ **WIDEN**（固定 +0.20）/ **GRADIENT**（CI 符号规则，否则 HOLD）；Always-Widen 必跑，因其可能直接蕴含 M2 教训的简化启发式。

## 8. 基准协议与点（§15–16）

8 冻结 config × 8 种子 = 64 配对试验；梯度点 = **新生成分量加入且冻结 M1-v0 权重确立之后、任何 M3 协方差改变之前**的提议状态；记录 `selected_mode / component_index / component_mean / component_weight / base_covariance / 全混合状态`；对每个梯度点记录冻结 M2 描述性 HDR 协方差（§17，仅诊断，60/64 试验触发"描述性收窄 vs 梯度放宽"冲突报告）。

## 9. 门与解释（§24–26）

M3-0..M3-6 阈值全部来自预注册配置（成功率先验 0.50/0.75/0.90/0.85/泄漏≤2、+25pp 优势条款）；Strong 门为部署预算 VRF 中位 >1，独立报告。**Gate M3-3 为双条款合成判定（Acc_dir≥0.75 且相对非自适应对照≥+25 pp），两条款同时满足才 PASS，无部分通过**。解释矩阵按 FD/方向/步长/排序四元组定位结论行；负结果与"Gradient≈Always-Widen"均按 §27/§35 措辞边界如实陈述，禁止事后调步长。

## 10. 前置承继与防火墙

M2 负结果（`RareTopo-M2-v0`，verbatim 冻结）为出发点：**描述性方差几何 ≠ 下降控制律**。无 M2 λ 调参、无基准配置改动、无策略学习、无联合优化、无分量删除、无全局最优性宣称；全矩阵控制（M3-v1）仅在标量 v0 核心门全部通过后方可启动——v0 中 Gate M3-3 整体 FAIL（优势条款 +0 pp < +25 pp），故 M3-v1 不获准入。
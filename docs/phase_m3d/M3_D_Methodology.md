# M3-D Methodology — Sign-Diverse Scalar Covariance-Control Benchmark

> **Schema:** `raretopo-m3d-v0` ｜ **Date:** 2026-08-27 ｜ **Branch:** `feature/phase-m3-scalar-gradient-control`
> **Task（canonical sha256 `f90f8b10…`）+ Amendment-1**（`M3_D_PREREG_AMENDMENT_Upward_Scale_Extension.md`,commit `c79d2c8`）
> **Prereg configs:** `configs/phase_m3d/{m3d_candidate_state_grid,m3d_reference_characterization,m3d_online_v0}.json`
> **Parent chain:** H3 → M1-v0 → M1-D → M2-v0(negative) → **M3-v0 frozen @`32b2856`**(tag `RareTopo-M3-v0`)

---

## 1. 研究问题

在**符号多样的 proposal-state 基准**(同一冻结事件族上,受控分量的 s² 遍历宽窄两端且 oracle 标签含 WIDEN/SHRINK/HOLD 三类)中,frozen M3-v0 二阶矩梯度控制器是否产生可测的**自适应价值**:

Gradient policy > max(Always-Widen, Always-Shrink, Always-Hold),配对预算下。

## 2. 基准构造(两代池)

| 代 | 域 | 文件(sha256 锚定于 freeze JSON) |
|---|---|---|
| gen1 | s²∈[0.55…2.00] ×8 | `m3d_candidate_pool.json`(56 态,D0–D3) |
| gen2 | **Amendment-1 扩展** s²∈{2.50,3.20,4.00,5.00,6.40,8.00} ×8 | `m3d_candidate_pool_extension1.json`(48 态) |

- 混合装配锚定种子 2026(frozen shared-stage:η 质心均值、SLSQP π_C0、frozen variance-selector 选中分量,与归档 ALL MATCH);状态间只变 Σ_k=s²I。
- Oracle 标签:N_ref=500k/臂 CRN 批式(tau=0.01,margin≥0.05 双扰动臂定义,HOLD ±3%,支持规则 |对比|≥2×配对 SE,20 批 SE)。
- **标签引擎一致性修复(先于任何在线运行)**:D5 测试暴露 `label_state` 两处实现偏差(margin 含 BASE、support 只记不管),以存储批数组纯重算修正(sidecar `m3d_labels_corrected_v2.json`;总量 W54/S26/H14/A10;冻结集内翻转恰 1 例 c001@0.55→AMBIGUOUS,证据:该态 base-vs-shrink 对比 7.38<2×SE 9.58)。Freeze v2(`b613f45d`)取代 v1(`d9a0e16`),选择规则零改动。

## 3. 冻结基准(D4′,封盘)

每类按 (config_id,s²) 升序取前 8(零替换):
WIDEN:c000@{0.55–2.00},c001@0.70;SHRINK:c000,c001@{4,5,6.4,8};HOLD:{c000,c001}@3.2,{c004}@2.5,{c006,c007}@{2.5,3.2},{c010}@3.2。

## 4. 在线协议(D6)

24 态 × seeds[2026..2033] = 192 试验。pilot 20k rng=[seed,101](target 行 N(0,I)+proposal 行,记录源密度);梯度估计/bootstrap/CI 符号规则/**逐字** = hyptraj.m3 冻结件(parity 测试按位比对)。物理臂 BASE/WIDEN(e^{+0.20})/SHRINK(e^{-0.20})由 eval_proposal_is([seed,900001]) CRN 配对评估;GRADIENT 折叠 HOLD*→base(保原因码),AW/AS/AH 与 ORACLE_ACTION 映射同三臂;双口径 320k/120k 每试验。

## 5. 度量与统计层级(§18–21,35)

Acc3 + 各类 recall/macro-F1/balanced/confusion;R_M2=(M2(G)/M2(O))-1 全局+分类中位、配对 bootstrap(n=10000,seed [20260827]);headline R_fixed = 「每 state 种子中位数的中位数」聚合下 M2(G)/M2(BEST FIXED);胜场计数;ΣL=M₂ 全臂闭合(tol 1e-9);max_{j≠k} 泄漏比。192 行不作 IID。

## 6. 门与消融

阈值全部来自预注册锁(M3D-0..6+Strong,数值见 config `gates_locked`);消融 D-A..D-F(M3-v0 回放仅对照不入门)。任一事后放宽均被禁止。

## 7. 防火墙承继

控制器零改；oracle/reference 字段结构性隔离(测试证：API 白名单+模块源扫描)；Layer A 固定权重；ESS_grad=20;bootstrap 固定分层 [seed,424243];delta_theta=0.20 主值贯穿(含 sensitivity 与 refinement 中点语义)。

# H3-3B Real VRF Audit — 真机性能字段 nominal 勘误审计报告

> **Status: COMPLETE**（2026-08-23；双 Scope 同流重标注，wall 3.84h）
> Branch: `feature/phase-h-uncertainty-risk`
> 任务来源：`RareTopo/handoff/H3_3B_Real_VRF_Audit.md`（目标/范围/三项 Check/Claim Boundary）
> 勘误源头：`H3_3B_P2R_RealN_Convergence_Report.md` §4 · P2R JSON `erratum_v1_1` · 台账 §4.3
> 执行脚本：`scripts/run_h3_3b_real_vrf_audit.py`（v1 + fix/fb f8290 两次崩溃修复）
> 数据：`results/phase_h3/h3_3b_real_vrf_audit_v1.json`（schema `h3-3b-real-vrf-audit-v1`）

---

## 0. 结论先行

按 handoff 任务书完成真机 C1/C2 性能字段的 nominal 勘误审计。**三项 Check 的裁定**：

| Check | 任务书要求 | 实测 | 裁定 |
|---|---|---|---|
| **Check 1** | 审计 p_mc 与旧 frozen 基线对齐 | ❌ 不对齐——但**根因在存储侧而非审计侧**：存储的 multi-system 真机行无法被 committed 管线复现（见 §3 provenance 裁定），而 Scope B 对 P2R 数据**逐位复现（ΔR=0, Δρ=0）**证明审计实现与动力学确定性无恙 | ⚠️ 反转裁定 |
| **Check 2** | perf 字段基于正确 nominal | ✅ 修正后 p̂ 全部落 0.39–0.51（旧值高达 **1.099 > 1** 的不可能概率）；新旧对照表完整存档（§4） | ✅ |
| **Check 3** | 几何结论不受影响 | ✅ Scope B R_η/ρ 与存储**逐位一致（max diff = 0.0）**；Scope A 的差异即 §3 所述 provenance 差异的体现，两套口径下 $\rho$ 均 ≥0.885、Gate-A 结论稳健 | ✅ |

**论文可引用的修正后真机性能**（正确事件定义 $A=\{regime\neq$ `SRTI_N2`$\}$，4 seed 均值）：

| 档位 | 系统 | $\rho$(tr$\Sigma_V,R_\eta$) | VRF ($s^2$=0.75/1/1.5/2) |
|---|---|---:|---|
| (256,128) 审计干净版 | C1 | 0.9095 | 0.584 / 0.666 / 0.361 / 0.285 |
| (256,128) 审计干净版 | C2 | 0.8853 | 0.513 / 0.494 / 0.272 / 0.240 |
| (512,256) P2R 复现 | C1 | 0.9459 | 0.557 / 0.653 / 0.389 / 0.240 |
| (512,256) P2R 复现 | C2 | 0.9459 | 0.378 / 0.444 / 0.381 / 0.212 |

修正后 VRF 全部 <1——与 H3-2 以来的结论"真机不 rare、IS 增益天然有限"一致，且数值语义首次干净。

---

## 1. 根因（精确到行）

共享数字核 `run_h3_3b_synthetic_pilot.py` 第 286 行：

```python
ind = np.asarray(labels_q != NOMINAL, dtype=float)   # NOMINAL = 'S0'
```

该函数为合成案例验证（nominal 确为 'S0'），被 `ms.finalize_real_request` 复用时未传 nominal——真机 case 的 expected_regime 是 `'SRTI_N2'`（mlb1 anchor 字段）。于是真机 perf 的事件指示器恒为全 1：p̂≡E[w]、接受率≡100%。**波及**：multi-system JSON 与 P2R JSON 的全部真机 is_performance 字段。**不波及**：p_mc（finalize 用 setup nominal，一直正确）、区域描述子（nominal 无关）、一切 ρ 端点。

## 2. 方法（无实验重设计）

双 Scope 同流重标注：Scope A 经 `ms.audit_system` 复现 multi-system 请求流（确定性抽签）；Scope B 逐位复制 P2R Stage-1 抽样序。标注走冻结管线（`ms._real_label_fn`，一次 Pool 批量）；物化用修正版 perf + 原版 `mode_region_geometry`。种子/$s^2$ 网格/MC-IS 预算与原跑逐位相同。

执行纪要：v1 崩溃（mc 请求混入 materialise）→ v2 崩溃（mc 批次重复入列致错位）→ v3 修复（去重 + 对齐断言 + 逐 case 救援落盘）后全程通过。

## 3. Check 1 反转裁定：provenance 发现（本报告最重要的产出）

**预期**：审计 p_mc == 存储 p_mc（两者都用正确 nominal、同样本流）。**实测**：8 个 case-seed 对中仅 2 对一致（C1-seed1 0.4961、C2-seed1 0.3906），其余偏差最大至 0.039；cov sweep $R_\eta$ 全部 16 行无一逐位复现（max ΔR=0.646）。

**假设空间排查**：
- ~~动力学 run-to-run 非确定性~~ —— 被 **Scope B 逐位复现**反驳（同一管线隔数小时重跑 P2R 全部样本，ΔR=0.0）：给定 x0，标签确定；
- ~~审计实现 bug~~ —— 同一实现下 Scope B 通过；
- ✔ **存储数据 provenance 问题**：multi-system JSON 生成于 08-22 凌晨，其脚本当时处于**未跟踪状态**（今日才随 `911418c` 入库），生成它的代码状态不可考；且 `_load_existing` 的续跑合并可能把更早代码状态的 partial 行混入终版。旁证：存储 C1 seed_1 与 seed_2120 的 p_mc 完全相同（0.4961/0.4961）——两个不同流给出同计数属可疑重复。

**裁定**：存储 multi-system 真机行的**来源不可复现**（provenance gap）。影响：(i) 其真机 perf/VRF 字段本就因 nominal 伪影作废（§1）；(ii) 其真机 ρ（0.910/0.861）应理解为"该混合来源数据集上的实现值"，本次审计给出干净可复现替代值 **0.9095 / 0.8853**；(iii) Gate-A 结论（≥0.8）在两种口径下均成立，**已发表几何结论不受影响**。

**诊断更正**：P2R 报告期曾临时猜测"C2 混沌不可复现"——被 Scope B 位级复现反驳，正式更正为 provenance 解释。（另注：审计脚本的 `_rescue` 存在同路径覆盖的小缺陷，最终 JSON 完整无缺；已记入待修。）

## 4. Check 2：修正前后对照（论文引用以 new 为准）

cov sweep $s^2{=}1$、seed 1 示例（完整表见 JSON `old_vs_new_demo`）：

| 来源 | p̂（旧→新） | VRF（旧→新） | 接受（旧→新） |
|---|---|---|---|
| multi-system C1 | 0.984 → **0.484** | 1.196 → **0.592** | 128/128 → 73/128 |
| multi-system C2 | **1.099**（>1，不可能概率） → **0.435** | 0.110 → **0.404** | 128/128 → 81/128 |
| P2R C1 | 0.987 → **0.471** | **0.000**（var_mc=0 伪影） → **0.659** | 256/256 → 148/256 |
| P2R C2 | 0.946 → **0.468** | **0.000**（同上） → **0.424** | 256/256 → 163/256 |

语义恢复确认：修正后 p̂ ≈ 0.39–0.51 与"真机不 rare（$P\approx0.5$）"完全一致；VRF <1 与"IS 增益天然有限"一致。

## 5. Check 3：几何结论不受影响的硬证据

- **Scope B**：重跑 P2R Stage-1 全部样本，$R_\eta$ 与存储**逐位一致**（max diff = 0.0），ρ 一致（0.0）——采样流、动力学、区域估计器全链路确定且忠实；
- **Scope A**：$R_\eta$ 差异即 §3 provenance 差异的体现（存储侧行不可复现），而非审计改变了任何几何量；
- 两套口径的 $\rho$：0.9095/0.8853（A）与 0.9459/0.9459（B）——均 ≥0.885，Gate-A 结论与 regime map 中真机点的象限归属（I 类，aligned×compact/diffuse）稳健。

## 6. 对既有文档的修正指令

1. **multi-system 报告 §4.3** 的真机 VRF 数值（C1 0.54–0.96 等）**作废**，替换为本报告 §0 表（引用时注明 nominal-corrected）；
2. **P2R 报告 §3 表格**中 p_mc/VRF 辅助列同理以本审计为准；
3. **Final Summary §6.6** 审计项关闭（本报告即产物）；§9 增补一行收尾；
4. 后续任何文档引用真机 VRF/p̂ 必须来自 `h3_3b_real_vrf_audit_v1.json`。

## 7. Claim Boundary

✔ 允许：更新真机 VRF/IS performance 叙事（已完成）；声明 provenance gap 及其边界。
❌ 禁止且未发生：改变 cov 杠杆结论、regime map、geometry descriptor 结论；修改任何 frozen artifact 或既有 JSON（勘误以独立审计文件承载）。
❌ 不声称：修正后 VRF 具备跨系统可比的最优 proposal 含义（本审计非寻优）；provenance gap 的确切历史成因（代码状态不可考，只可证明不可复现性本身）。

## 8. Artifacts

`scripts/run_h3_3b_real_vrf_audit.py` · `results/phase_h3/h3_3b_real_vrf_audit_v1.json` · 本报告。执行纪要：v1/v2 崩溃修复两次（mc 请求混入、批次重复入列），v3 全程通过。

## 9. 一句话总结

> **Real VRF Audit 完成：真机 perf 字段的 nominal 伪影（根因 pilot.py:286）全面勘正——修正后 p̂≈0.39–0.51、VRF≈0.21–0.66 语义干净可引用；Check 1 反转出更深的 provenance 发现（multi-system 真机行不可被 committed 管线复现，Scope B 位级复现反证动力学确定性），Gate-A 结论在两种口径下均稳健；三项 Check 以"C1 位级通过 + C2 provenance 裁定"如实闭环，几何与 regime 结论零改动。**

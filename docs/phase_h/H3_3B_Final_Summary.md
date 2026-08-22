# H3-3B — Final Summary（H3-3B 完成状态冻结文档 v2）

> 项目：**RareTopo** — Rare Topology Transition Estimation in Hybrid Dynamical Systems
> Scientific backend：`hypersonic-hybrid-trajectory-lab` · 分支：`feature/phase-h-uncertainty-risk`
> 论文主线：ICML 2027 方法论文（内部冻结 2027-01-10）
> **状态：H3-3B COMPLETE（Theory v2 · Pilot · Multi-system · Regime Map P1/P2/P3 全部完成；2026-08-22）**
> 前序状态入口：`H3_Final_Summary.md`（2026-08-21，H3-3A 冻结原貌，**保持不动**）——本文是其 H3-3B 后继增量；两文合并构成完整状态
> 本文用途：任何人开始 H3 之后工作（P2R / mixture / ML-H4 / 论文）前，用这一份文件即可准确知道 **H3-3B 证明了什么、观测到了什么、只是假设什么、哪些旧结论被修正或勘误**

---

## 0. 文档定位（先说清楚这份文件是什么、不是什么）

三条硬约束（沿 corpus 惯例）：

1. **区分层级**：已证（定理）、实验证实（注明作用域）、描述子/假设——分开措辞。
2. **不恢复被推翻/被勘误的旧结论**：真机 C1 旧 $d_L=1.136$ 仍为采样伪影；Phase 1 任务书 C4 的原始论证已被 v2.2 勘误（样本层点估计不稳定是 H3-3A 结论的再现，非缺陷）。
3. **出处可核**：全部数字可溯源至 `results/phase_h3/` 下三份 schema 化 JSON 与对应报告；核对记录见 `H3_3B_Phase_Execution_Ledger.md`。

**H3-3B 一句话现状**：proposal 如何塑造 variance geometry（$(system,q)\to\nu_V^{(q)}$）已从理论、单系统、跨系统走到 regime map——**四类 variance geometry regime 在声明作用域内全部 populated 且统计可分**；期间产生的盲性定理（定理 4.4）把"标准 MPP 居中 IS 对凸失效集方差结构性失明"变成论文级的不可能性结果。

---

## 1. H3-3B 演化链（五步，每步只声称该阶段支持的结论）

| 步 | 阶段 | 对象 | 核心结果 | 状态 |
|---|---|---|---|---|
| 1 | Theory Extension **v2** | $(m,\Sigma)\to(\mu_V,\Sigma_V)$ + 盲性 | 闭式核与合法性 $\Sigma\succ\tfrac12I$（定理 2.1/4.1、命题 3.1）；**定理 4.4**：凸失效集 + $m=x^*\Rightarrow x_L=x^*$ 对任意合法 Σ；注 4.6"三顶帽子"（合法性=对数凹=证明常数）；注 4.7 union 伪 mismatch；注 5.1 区域级分离需偏移锚 | THEORY（v2 回填经外部评审） |
| 2 | Synthetic Pilot | Synthetic B 双杠杆 sweep | 协方差杠杆 $\rho(\mathrm{tr}\Sigma_V,R_\eta)=0.98$、均值杠杆坐标 $\rho=0.99$（绝对位置受截断）；三 Gate 全过 | COMPLETE |
| 3 | Multi-system | A/B/C1/C2 × 11 config | 映射普适（Gate A/B/C 4/4）：cov 杠杆全系统有效（ρ 0.86–0.97 含真机），mean 杠杆仅 mismatch 系统有效 | COMPLETE |
| 4a | **P1 曲率扫描** | $d_L(\beta\kappa)$，15 config × 双约定 × 三对照 | 单调渐变双支曲线（Spearman 1.000）；$\gamma_{sat}=1.265$、$s_0=1.102$；辅约定恒零确认定理 4.4；union 伪 mismatch 3.189 复现；第二族方向一致 | COMPLETE |
| 4b | **P2 阈值标定** | compact/diffuse 切点（零新 MC） | 4 系统 $R_\eta(s^2)$ 单调 4/4 再确认；ABS 全局切点窗口 $R_c\in(1.3925,1.5901)$ 存在且全网格干净单台阶 | COMPLETE |
| 4c | **P3 联合 map** | $(D_L,R_\eta)$ 四象限 | I=9 / II=6 / III=17 / IV=3 全 populated，成员与预注册预测表逐点吻合；分离性 MW $p=0.0136$ | COMPLETE |

执行纪律记录：台账 `H3_3B_Phase_Execution_Ledger.md` 共 12+5+5 项冻结核对，除 P1-C4 一项按预案披露关闭外零静默失败；两处实现期发现均以 DV 条目先声明后执行（DV7 钉参层、C4 勘误）。

## 2. 当前已验证 claims（新增/更新，注明层级与作用域）

1. **MPP 锚定方差盲性（已证定理 + 数值确认）。** 凸失效集 + $q=\mathcal N(x^*,\Sigma\succ\tfrac12I)\Rightarrow x_L=x^*$ 唯一（Thm 4.4，一阶+凹性证明，无需闭式）；推论投影恒等式 $\operatorname{proj}_A(-\operatorname{proj}_A(0))=\operatorname{proj}_A(0)$。数值上：P1 全网格 $D_L^\star\le1.5\times10^{-7}$。*推论*：区域级分离（$D_\eta>0$）必须偏移锚定（注 5.1）——为 leakage-aware proposal 提供必然性论证。
2. **proposal→variance geometry 映射跨系统成立**（实验证实）：4 系统（synthetic linear/curved + real Sanger ×2），cov 杠杆 $\rho\in[0.86,0.97]$、mean 杠杆仅 mismatch 有效（承 multi-system，本阶段无变化）。
3. **曲率轴响应律（实验证实 + 描述子）**：frozen 抛物线族钉 β 上，$d_L$ 自基线偏移 $\delta_0=0.0162$ 起单调渐变生长至 $d_\infty=0.998$（Spearman 1.000）；**无临界曲率**；特征尺度 $s_0=1.102$、$\gamma_{sat}=1.265=O(1)$。**对 H3-2 经验判据的正面修正：$\beta\kappa\sim1$ 是饱和尺度而非起始阈值。** 第二非二次族方向一致（比值 ∈[0.55,1.74]）。
4. **全局 compact/diffuse 阈值存在（标定，限定作用域）**：$R_c\in(1.3925,\,1.5901)$（ABS 定义，4 系统、MPP 锚、$\eta{=}0.8$、$d{=}4$）；中点分类下全网格无交错单台阶；REL 定义窗口佐证。
5. **四类 variance geometry regime 存在且可分（实验证实，hypothesis→证实升级）**：预注册边界下 I=9/II=6/III=17/IV=3 全 populated，成员与预测表逐点吻合；III vs I 分离 $p=0.0136$；跨系统一致（真机 aligned 基线与合成同侧同类）。
6. **逐模态约定的实证依据（新）**：union 级 MPP 锚产生 $D_L^{union}=3.1887$ 的纯跨模态切换伪 mismatch，而同锚逐模态为零（注 4.7 预言精确复现）。

## 3. 当前 non-claims（继承 + 新增，不得声称）

**继承自 `H3_Final_Summary.md` §6 全部条款**（universal mismatch / $x_L$ 普适最优 / 高维解决 / SORM 定理等）。

**H3-3B 新增**：

- ❌ $\gamma_{sat},s_0,R_c,\theta$ 为普适常数——它们是 frozen 测试床族、特定锚定与 $\eta{=}0.8,d{=}4$ 下的描述子；
- ❌ regime map 覆盖一般 hybrid / 其他边界族之外——IV 象限仅 3 点（恰达最低判据），欠采样如实声明；
- ❌ $G_\eta/R_\eta$ 与 VRF 的因果关系——系内强相关（pilot B −0.97）与池化弱相关（+0.20/+0.27）并存，"关联非普适"再次成立；
- ❌ 双层锚定聚合的坐标可比性超出已披露范围——X/Y 可来自不同 proposal 约定（逐点携带 anchor 元数据，路线图 R-2），跨约定颜色比较仅辅助证据；
- ❌ "alignment 过渡律"外推到非凸拓扑——环形/包裹型失效区是盲性定理的逃逸通道（反例 $D_L=2$），未扫描。

## 4. 关键数字速查（frozen，均可溯源 JSON）

| 量 | 值 | 出处 |
|---|---|---|
| $\delta_0=1.5-\beta_B$ | 0.016175 | Phase 1 解析 |
| $\beta_B$ / anchor 连续 β | 1.483825 / 1.479237（差 0.309%） | DV7 |
| 分支点 | $a^\ast=0.05306$，$\gamma^\ast=0.1531$ | Phase 1 |
| $s_0$ / $\gamma_{sat}$ / $d_\infty$ | 1.1020 / 1.2652 / 0.9979 | Phase 1 Gate A |
| 盲性数值上界 | $\max\lvert D_L^\star\rvert=1.52\times10^{-7}$ | Phase 1 辅约定 |
| union 伪 mismatch | 3.18866（预期 3.193±0.15） | Phase 1 对照 |
| $R_c$ 窗口 | (1.3925, 1.5901)，中点 1.4913 | Phase 2 ABS |
| 四象限计数 | I=9 / II=6 / III=17 / IV=3 | Phase 3 |
| III vs I 分离 | $\bar G:0.598$ vs $0.405$，MW $p=0.0136$ | Phase 3 |

## 5. Artifacts 总账

| 类 | 清单 |
|---|---|
| 文档 | Regime Map 计划 · Phase1 任务书 v2.1/v2.2 · 外部评审说明书(+§8) · 实验路径路线图 · 执行台账 · P1/P2/P3 报告 · Theory Extension v2 · 本文件 |
| 脚本 | `run_h3_3b_phase1_curvature_scan.py` · `run_h3_3b_phase2_threshold_calibration.py` · `run_h3_3b_phase3_joint_regime_map.py` |
| 数据 | `h3_3b_phase1_curvature_scan_v1.json` · `h3_3b_phase2_threshold_v1.json` · `h3_3b_phase3_joint_map_v1.json` |
| 图 | fig18（过渡曲线）· fig19（协方差 map）· fig20（联合 regime map） |
| 关键 commit | `2947d8d`（评审吸收）· `79bd8c9`（P1）· `57a0e66`（P2）· `2b66330`（台账）· `ef35423`（P3） |

## 6. 下一步接口（不在 H3-3B 内）

1. **P2R（可选）**：真机 C1/C2 N∈{512,1024} 收敛检查（预算 2–3 h）——检验 cov 杠杆 ρ 随 N 上升；
2. **mixture/compound proposal**：$q=\sum_k\pi_k\mathcal N(m_k,\Sigma_k)$ 进 H3-3B 框架（pilot §11.3 遗留）；
3. **ML-H4 接口**：学习 $(system,q)\to(C_\eta,R_\eta,G_\eta)$（Theory Extension Sec. 8；输入低维 proposal 参数，输出区域描述子）；
4. **论文 Section X 增量**：叙事骨架已备——盲性定理（不可能性结果）→ 偏移锚定/泄漏感知的必然性 → 曲率响应律与饱和尺度 → 四象限 regime map；
5. **形状算子内蕴形式化**（评审 Q3(c)）：future work。

## 7. ASCII 总结块

```
H3-3B FINAL SUMMARY — COMPLETE (2026-08-22)

Chain: Theory v2 (blindness thm) -> pilot -> multi-system
       -> P1 curvature scan -> P2 threshold -> P3 joint map

Proven:   A convex & m=x* => x_L = x* (any legit Sigma);
          1/2 I = integrability = log-concavity = proof constant;
          proj_A(-proj_A(0)) = proj_A(0).
Measured: d_L(beta*kappa) monotone gradual dual-branch, no critical point,
          gamma_sat = 1.265 (saturation, not threshold -- revises H3-2);
          global compact/diffuse cut R_c in (1.393, 1.591), 4/4 systems;
          quadrants I=9 II=6 III=17 IV=3 all populated, separable (p=.014).
Controls: aux convention identically zero; union pseudo-mismatch 3.189;
          second family direction-consistent.

NOT claimed: universal constants; beyond-scope generalization; causal VRF;
             dense Regime-IV sampling; cross-convention color comparability.

Next: P2R(optional) / mixture proposals / ML-H4 / paper Section X.
```

## 8. 一句话总结

> **H3-3B 完结：从"proposal 是否塑造 variance geometry"到"四类 regime 存在且可分"的五步证据链闭环（理论 v2 → pilot → 多系统 → P1/P2/P3），全程 17+5+5 项预注册核对除一项按预案披露外全部通过；盲性定理与饱和尺度修正构成本阶段两项定理级/判据级产出，全部数字可溯源、全部偏差有登记——H3-3B 状态就此冻结。**

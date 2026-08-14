# Reading List — Hypersonic Glide Trajectories

Phase B / Phase B.5 文献审计中**实际验证**（Crossref / NTRS 记录或原文）的文献。
完整 BibTeX 见 `bibliography.bib`。未验证的元数据字段留空，不猜测。

## Equilibrium glide（平衡滑翔）— 原始来源

1. **Eggers, Allen & Neice (1957), NACA TN 4046** — *A Comparative Analysis of
   the Performance of Long-Range Hypervelocity Vehicles*。
   原文（NTRS ID 19930084802）已逐页阅读：平衡滑翔条件
   `L = mg - mV^2/r0`（式 25–30，小倾角假设）；含 Sänger–Bredt 跳滑概念史。
   这是"升力 = 重力 − 离心力"的原始权威出处。

## Quasi-equilibrium glide（准平衡滑翔）— 制导文献

2. **Shen & Lu (2003), JGCD 26(1): 111–121, DOI 10.2514/2.5021** —
   *Onboard Generation of Three-Dimensional Constrained Entry Trajectories*。
   NTRS 预印本 20030002215 已读（OCR）：QEGC 精确形式（式 7）
   `L cos(sigma) + (V^2 - mu/r)/r = 0`；sigma=0 即平衡滑翔；
   "gamma 小且变化缓慢"是 QEG 假设。
3. **Lu (2014), JGCD 37(5), DOI 10.2514/1.62605** — *Entry Guidance: A Unified
   Method*。摘要级验证（AIAA 页面）：统一预测-校正制导，altitude-rate feedback。
4. **Lu (1997), JGCD 20(1): 143–149, DOI 10.2514/2.4008** — *Entry Guidance and
   Trajectory Control for Reusable Launch Vehicle*。元数据级验证。
5. **Harpold & Gavert (1983), JGCD 6(6), DOI 10.2514/3.8523** — *Space Shuttle
   Entry Guidance Performance Results*。元数据级验证。
6. **Mease & Kremer (1992), AIAA 92-4450, DOI 10.2514/6.1992-4450** —
   *Shuttle Entry Guidance Revisited*。NTRS 19930029282 摘要验证：
   drag-acceleration 参考剖面跟踪。
7. **Moore (1991), NASA TM, NTRS 19920010688** — *Space Shuttle Entry Terminal
   Area Energy Management*（TAEM）。元数据级验证。

## Terminal guidance（终端制导）

8. **Kim & Grider (1973), IEEE TAES, DOI 10.1109/TAES.1973.309659** — 撞击姿态
   角约束终端制导（早期经典）。
9. **Wang, Tang & Zhang (2019), IEEE Access 7, DOI 10.1109/ACCESS.2019.2909589** —
   HGRV 短距再入，撞击角+撞击速度联合约束（与本问题最直接对应）。
10. **Liu (2017), CCC, DOI 10.23919/CHICC.2017.8028308** — 终端拦截+撞击角约束
    最优制导律。
11. **Lee (2013), AIAA GNC, DOI 10.2514/6.2013-4951** — 成形制导律（末端指令平缓化）。
12. **Zhang, Zhang & Li (2022), CCC, DOI 10.23919/CCC55666.2022.9901754** — HGV
    终端相位鲁棒跟踪制导。
13. **Kluever (2007), JGCD 30(2), DOI 10.2514/1.24864** — 无动力 RLV 带倾侧角
    约束的终端制导（u_L in [0,1] 类约束的先例）。

## 专著 / 框架

14. **Zarchan, *Tactical and Strategic Missile Guidance*（6th ed. 2012,
    DOI 10.2514/4.868948）** — PN 族与 trajectory shaping 标准手册。
15. **Bryson & Ho, *Applied Optimal Control*（DOI 10.1201/9781315137667）** —
    终端约束最优控制框架。
16. **Vinh, *Optimal Trajectories in Atmospheric Flight*（1981, Elsevier）** —
    大气飞行轨迹分析框架（未获全文，仅框架引用）。

## Steady-glide（稳态滑翔）— 与 QEG 直接相关的专著

17. **Chen, Zhou, Yu & Yang (2021), Springer, DOI 10.1007/978-981-15-8901-0** —
    *Steady Glide Dynamics and Guidance of Hypersonic Vehicle*。
    含 Trajectory Damping Control（ch. 9）与 Singular Perturbation Guidance
    （ch. 11，能量状态法）。元数据级验证。

---

### 说明

- 所有条目均在 Phase B.5-A / B.5-B3 审计中经 Crossref 或 NTRS 验证；
  原文全文阅读的仅 Eggers 1957 与 Shen & Lu 2003（NTRS 预印本）；
- 其余为摘要/元数据级验证——引用时只使用摘要实际支持的内容；
- 未验证页码/卷号/DOI 的字段留空（`bibliography.bib` 中注释标注验证级别）。

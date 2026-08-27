# M3 Final Report — Second-Moment Gradient Covariance Control

> **Schema:** `raretopo-m3-v0` ｜ **Date:** 2026-08-27 ｜ **Branch:** `feature/phase-m3-scalar-gradient-control`
> **Frozen chain:** `RareTopo-H3-v1.0` / `RareTopo-M1-v0` / `RareTopo-M1-D-v1.0` / `RareTopo-M2-v0`（M2 冻结提交 `0a00f44`）
> **Benchmark freeze SHA-256:** `be2ef471…bb61de`（与归档逐一匹配）
> **Prereg:** `docs/phase_m3/M3_Second_Moment_Gradient_Covariance_Control_Task.md`（sha256 `6c3cf811…`）+ `configs/phase_m3/m3_scalar_gradient_v0.json`（**零预注册修订**）
> **Machine-readable verdict:** `results/phase_m3/summary/gate_audit.json`

---

## 0. 一句话结论（One-Line State）

```text
H3 = frozen; M1-v0 = frozen; M1-D = frozen; M2 = frozen (negative, RareTopo-M2-v0)
M3 = EXECUTED (prereg followed, zero amendments)
M3 verdict: finite-sample second-moment gradient predicts the correct
WIDEN direction and its step reliably reduces independent-evaluation M2
(Gates M3-2/4/5/6 PASS; gate M3-3 accuracy clause PASS but the
preregistered +25pp advantage over fixed rules FAILS: gradient ~= Always-Widen)
  - 62/64 trials confident WIDEN; active-set direction accuracy 79.0%
  - predicted-step success rate 93.5%; median M2(pred)/M2(base) 0.846
  - median M2(pred)/M2(opposite) 0.721 (strong ordering)
  - off-target leakage unchanged (8/8 configs, ratio ~1.00)
  - deployable budget VRF median 0.326 (< 1): Strong Gate NOT PASSED
next gate = (per parent program) full-matrix M3-v1 only after all core gates
pass; adaptive-value question is NOT resolved by gradient-vs-fixed-widening
```

## 1. 执行顺序（任务 §33）与完成证据

| 阶段 | 状态 | 证据 |
|---|---|---|
| Step 0 M2 冻结 | ✅ | 标签 `RareTopo-M2-v0`@`0a00f44` 推送；pytest 1113 passed exit 0；`docs/phase_m2/M2_Freeze_Summary.md` |
| M3-0 预注册锁 | ✅ commit `be51c57` | 任务文档落盘 + 双配置 json（§36 全常数）+ M1-D hash 交叉验证 |
| M3-1 推导 + FD 门 | ✅ commit `384bd15` | 推导文档九项；理论校验 49/49、符号 100%、rel err 1.064e-3 ≤ 5e-3 |
| M3-2 估计器 + sanity | ✅ commit `098fbc1` | S1/S2/S3 全过（符号/ESS 硬门）；§29 单测 15/15 |
| M3-3/4 Layer A 主格 | ✅ | 64 试验（~28 s）+ Always-Widen/Shrink 对照 + §17 诊断 + 双口径记账 |
| M3-5/6 门数据 + 对照审计 | ✅ | 见 §2/§3（accuracy 优势条款 FAIL 如实判定） |
| M3-7 Layer B | ✅ 64 试验 | 决策 64/64 与 A 层一致（重加权不改变方向结论） |
| M3-8 步长敏感性 | ✅ 64 试验 | 剂量-反应单调（pred/opp 中位 0.864→0.728→0.544） |
| M3-9 门审计 + 图 + 文档 | ✅ 本文档 | `gate_audit.json` + 8 图 + Methodology/Validity Audit/Final Report |

总运行：主格 28 s + B 层 ~1.5 min + 敏感性 ~44 s + 图/审计秒级。全预注册预算（64×20k pilot + 192×100k 评估 + B 层 192×100k + 敏感性 448×100k），**梯度估计零额外 simulator 调用**。

## 2. 有效性（Gate M3-0 — PASS）

- 四个父标签全部未变（H3/M1 对 `M2_Freeze_Summary.md` 记录、M1-D/M2 对预注册配置 frozen HEAD）；M2 标签为当前 HEAD 祖先；
- benchmark hash `be2ef471…` 与归档一致；任务 sha256 溯源一致；
- selection lock：64/64 与归档 M1-D `variance_selector` 记录一致（`selected_modes` 交叉核验，0 mismatch、0 不可得）；
- mean lock 双算偏差恒 0.0；全部 192 臂过冻结合法性检查器（0 失败）；
- Layer A 全部记录 `layer = fixed_weights`；双口径记账 0 缺失（恒 320,000/120,000）；
- 估计器输入路径无最终评估访问权（结构签名 + rng 标签分离测试）。

## 3. 科学 Gate 判定（Layer A，64 配对试验）

### Gate M3-1 — PASS（理论/数值）
详见 Validity Audit §2；一次因"探针落在假设 A3 窗外"的 FAIL 被门捕获、修正测试点后 PASS，定理本身未改动。

### Gate M3-2 — PASS
活跃率 **62/64 = 96.9%**（≥50%）；仅 2 例 `HOLD_LOW_ESS`（ESS_grad<20），0 例 HOLD_INVALID、0 例 HOLD_UNCERTAIN。ESS_grad 中位 189。

### Gate M3-3 — **部分 PASS（主条 PASS，优势条 FAIL）**
```text
active-set Acc_dir = 0.790 >= 0.75             PASS
+25pp vs best fixed rule    = +0.0 pp          FAIL
  (ALWAYS-WIDEN 0.790 / ALWAYS-SHRINK 0.032)
```
62/64 决策为 WIDEN ⇒ GRADIENT 的活跃集预测与 ALWAYS-WIDEN 逐试验相同 ⇒ **梯度在方向准确率上不提供任何可测增值**（任务 §21 预言成立）。该差异按 §27 如实保留并主导 §5 措辞。

### Gate M3-4 — PASS（强）
活跃集内 `M2(pred)<M2(base)` 成功率 **93.5%**（≥75%）；`median M2(pred)/M2(base) = 0.846 ≤ 0.90`。

### Gate M3-5 — PASS（强）
`median M2(pred)/M2(opposite) = 0.721 ≤ 0.85`；配对 CRN 下排序稳健（四分位 [0.565, 0.897]）。

### Gate M3-6 — PASS
8/8 config 的 `median_seed max_{j≠k} L_j(pred)/L_j(base) ≈ 1.000`（固定权重 + CRN 结构下方差质量未向非目标模式再分布）。

### Strong — NOT PASSED
```text
median deployable VRF(gradient path) = 0.326  (> 1 required)
(ALWAYS-WIDEN 路径同值 0.326：决策=动作)
```
独立评估口径下，预算调整 VRF 低于粗 MC 边界——M3 不获成本效率宣称。

## 4. §17 M2 诊断（描述性 vs 梯度）

60/64 试验发生 `hdr_isotropic_scale ≪ s²_base=1` 而梯度判定 WIDEN 的显式冲突——**M2 教训在最干净的尺度上复现：top-η HDR 描述性散布指向收窄（0.06–0.3 量级），二阶矩导数指向放宽**，且放宽确实降低 M₂（Gate M3-4/5 全数据）。

## 5. 解释与允许措辞（§26/§35）

```text
FD 有效 | 方向准确 | 预测步降 M2 | 击败反向 | (自适应增值/VRF)
  Yes   |   Yes   |    Yes     |   Strong |  +0pp 且 VRF 0.326<1
→ 解释矩阵第 4/5 行边界：局部下降有效、排序强劲，
  但方向价值不优于固定放宽规则，成本效率未获支持。
```

本阶段允许主张（按 §35 第二款 verbatim 措辞边界）：

> **The second-moment derivative correctly predicts widening on this benchmark, but provides limited measurable value beyond a fixed widening rule.**

不主张：全局协方差最优性、policy 学习、全矩阵控制、成本效率、跨基准迁移、任何"梯度方法优于 Always-Widen"的表述。

## 6. Layer B / 敏感性 / 稳健性

- **Layer B**：每臂冻结 SLSQP 重加权后独立评估，决策 64/64 与 A 层一致；`median M2(pred)/M2(opposite) = 0.723`（B 层不改变主结论，也不拯救方向假设失败——符合 §12 设计）。
- **敏感性（解释性）**：主步长 0.20 全网格不变；剂量单调：δ=0.10/0.20/0.40 下 `median pred/base = 0.923/0.846/0.730`、`median pred/opp = 0.864/0.721/0.544`（一步到位的放宽对偏移质量收益更大）。无怪异非线性，不作主判据修订。
- 泄漏、合法性、选择/均值锁在全三层数据中无异常。

## 7. 全量测试证据

- 全量 `python -m pytest -q`（仓库根在 sys.path）：**1128 passed / 0 failed**（含 M3 新增 15 项），退出码 0，耗时见运行日志；（第一次裸 `pytest` 调用因解释器 sys.path 注入差异曾误报 2 项 `ModuleNotFoundError`，已用 `python -m pytest` 复核为 0——操作方问题，非代码缺陷，记录于 `M2_Freeze_Summary.md` §2）。

## 8. 完成清单（任务 §37）核对

| §37 项 | 证据 |
|---|---|
| M2 冻结（报告/pytest/负结论/标签/推送/摘要） | ✅ 全文已核，见 Step 0 |
| M3 理论（矩阵+各向同性推导/假设审计/平稳性审计/无过度宣称） | ✅ `M3_Covariance_Gradient_Derivation.md` |
| M3 实现（责任估计/分层梯度估计/ESS_grad/分层 bootstrap/WIDEN-SHRINK-HOLD/固定权重层/反事实评估） | ✅ `src/hyptraj/m3/` 四模块 |
| 验证（S1/S2/S3/FD/全量 pytest） | ✅ sanity + theory_checks + 1128 passed |
| 基准（8×8/HOLD-WIDEN-SHRINK-GRADIENT/Layer A/Layer B/敏感性保留） | ✅ 三层批次 JSON |
| 门（M3-0..M3-6/Strong 独立报告） | ✅ `gate_audit.json` + 本文档 §2–3 |

## 9. 限制与后续（§27/§28）

- 31 项活跃率与 96.9% 可辨识均受基准几何驱动（方差质量普遍位于单位尺度之外）；不同基准上梯度/固定规则的相对价值需重估；
- 步长 0.20 未事后调整；若未来研究信任区间/曲率，需新预注册；
- 标量成功不蕴含全矩阵成功；**M3-v1 全矩阵控制被本节明确延后**——先决条件"核心门全过"中 M3-3 优势条与 Strong 门未过，故按 §34 不得进入全矩阵实现。
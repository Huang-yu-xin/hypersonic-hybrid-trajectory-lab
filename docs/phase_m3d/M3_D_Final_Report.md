# M3-D Final Report — Sign-Diverse Scalar Covariance Control

> **Schema:** `raretopo-m3d-v0` ｜ **Date:** 2026-08-27 ｜ **Freeze:** v2 hash `b613f45dc6645c6d…`（封盘）
> **Trials:** 192(24 态 × seeds[2026..2033])｜ **Batches:** layer_a + ablations D-A..D-F
> **Machine verdicts:** `results/phase_m3d/summary/gate_audit_m3d.json`

---

## 0. 一句话结论

```text
H3/M1-v0/M1-D/M2-v0 frozen; M3-v0 frozen (adaptive advantage NOT established)
M3-D = EXECUTED on a preregistered SIGN-DIVERSE benchmark (Amendment-1 extension)
     : frozen second-moment gradient controller DOES adapt its scalar action
       to the proposal state (WIDEN/SHRINK recalls both 1.00, oracle regret
       median R_M2 = 0.000) and is near-oracle, and for the first time the
       deployable budget VRF median = 1.030 > 1 (Strong PASSED)
     -- BUT Gate M3D-2 overall FAIL (HOLD recall 0.25 < 0.60) and
        Gate M3D-3 FAIL: R_fixed = 0.988 > 0.90 vs BEST FIXED = ALWAYS-WIDEN,
        gradient beats AW on only 9/24 states (needed >=16/24)
        => sign diversity exists, but the finite-sample CI-sign policy does
           NOT convert it into a best-fixed-rule advantage.
verdict per task Sec.40 branch C:
  "Sign diversity exists, but the current finite-sample gradient policy does
   not convert it into robust adaptive value."
```

## 1. 执行序与工件链

| 步 | 内容 | 提交 |
|---|---|---|
| F/D0-D3 | M3-v0 冻结→任务入仓→56 态参考→§10 STOP | c79d2c8 前 |
| Amend-1 | 向上扩展网格 [2.50…8.00](先于新表征提交) | `c79d2c8` |
| D1′+D3′ | 48 新态表征→8/8/8 GO 零 refinement | `cbf2398` |
| D4′ | Freeze v2(标签一致性修复后重建) | `ad4484c` |
| D5 | 16 结构测试+全量 1144 passed exit 0 | 同上 |
| **D6** | **192 在线试验**(96s;冻结控制器逐字) | `2bababb` |
| **D7** | 门审计 M3D-0..6+Strong | 本文 |
| **D8** | 消融 D-A..D-F(+步敏 768 臂、回放 64 试验) | `a4ee0d9` |
| **D9** | 8 图+三文档+本报告 | 本 commit |

## 2. 门判定(M3D 层 A,预注册阈值)

```text
Gate M3D-0 validity                PASS   五 tag 不变/freeze 哈希自洽/192 格无缺/
                                          双口径恒定/闭合零违例/oracle 隔离绿/pytest 绿
Gate M3D-1 sign diversity          PASS   8/8/8 exact,ambiguous=illegal=0 in benchmark
Gate M3D-2 action accuracy         FAIL
   Acc3 clause                     PASS   Acc3 = 0.750 (floor 0.75, boundary)
   recall clause                   FAIL   W 1.00 / S 1.00 / H 0.250 << 0.60
                                          macro-F1 0.695, balanced acc 0.75
Gate M3D-3 beat best fixed rule    FAIL
   aggregate (median of state seed medians):
     GRADIENT 0.9552 | AW 0.96662 | AS 1.04074* | AH 1.00000
     (*AS 含 1 个非法臂态的排除处理)
   BEST FIXED = ALWAYS-WIDEN; R_fixed = 0.9882  (> 0.90 FAIL)
   wins vs each rule: AW 9-5-10 / AS 14-0-10 / AH 18-4-2   (需 >=16)
Gate M3D-4 near-oracle             PASS   median R_M2 = 0.000 <= 1.10
                                          (61% 恰为 0:动作=oracle 映射同臂)
Gate M3D-5 cross-class robustness  FAIL
   grad/BASE medians: W .8781<=.95 ✓ | S .9658>.95 ✗(差 1.6pp)| H 1.000<=1.02 ✓
Gate M3D-6 leakage safety          PASS   24/24 states max_{j≠k} med ratio<=2;
                                          ΣL=M2 全臂全试验 0 违例@1e-9
STRONG budget VRF                  PASS   deployable 中位 1.0304 > 1
```

核心门不全过 ⇒ 主 claim 与 variant-B 不获授权；按 §40 分支 C 措辞。

## 3. 关键现象解读(由数据决定)

- **方向自适应真实发生**:SHRINK 类 64/64 判对(WIDEN 类亦然),证明有限样本二阶矩导数在宽 proposal 区间可靠地给出收缩信号——这是 M3-v0 widening-dominant 几何下不可能观察到的;
- **HOLD 失效的正确机制(修正后表述)**:`gradient-sign confidence != finite-step action-indifference`。oracle 的 HOLD 定义是**预注册有限步长下的收益不足**(以参考预算判定),而非"符号不确定"。数据事实:(a) WIDEN/SHRINK recall 均为 1.00 ⇒ 符号本身估计正确;(b) 48/64 个 oracle-HOLD 试验上 CI-sign 仍自信地动作——符号置信度对"固定步长是否值得执行"不携带任何信息;(c) 这些态恰好处于 ±1%/±3% 无差别边界带,跨种子实现在线效应中位 r_w=−0.028、r_s=+0.052,68.8% 的试验至少一个扰动在线上越过 1% 改善线而参考端判为 indifferent。因此缺口不是"CI 太宽",而是控制器**缺少『预计有限步长增益太小则 HOLD』的 action-value gate**——这正是 M3-G 阶段的动机;
- **为什么仍打不过 Always-Widen**:聚合被两段几何主导——WIDEN 类上 GRADIENT≡AW(同为放宽,逐值一致),而 HOLD 类上"不动"更优(AW 在该类反而 −2.8%)。梯度唯一的可赢空间(SHRINK 类相对 AW 中位约 −8.8pp 绝对差)不足以把 24 态聚合的 R_fixed 从 0.988 推到 ≤0.90;
- **成本效率首次转正**:Strong PASS(1.030)。⚠️ 该数字仅说明 deployable 口径下预算效率超过粗 MC 边界,**不得解读为 adaptive superiority 或对固定规则的价值优势**——M3D-3 同时 FAIL。

## 4. 消融(D8)

- **D-C 剂量单调**:δ∈{0.10,0.40} 下 widen 中位比 0.982/0.962、shrink 1.018/1.143(主判据 δ=0.20 未动);
- **D-D 点符号 vs CI 符号**:acc 0.667<0.75 且 HOLD 全军覆没(recall 0)——CI 纪律确为主因之一,主规则保持 CI-sign;
- **D-F M3-v0 回放**:原 8×8 单位尺度状态决策 **62 WIDEN/2 HOLD**,与 M3-v0 头条完全一致;median AW/HOLD=0.848。证明 M3-D 的任何自适应增益源于**符号多样的状态**,而非控制器改动(控制器逐字复用的 parity 由测试锚定)。

## 5. 允许主张边界(task §40,分支 C verbatim)

> **Sign diversity exists, but the current finite-sample gradient policy does not convert it into robust adaptive value.**

同时允许如实记录:方向自适应发生且近 oracle(regret 中位 0)、WIDEN/SHRINK 两类判定完美、成本效率门通过(VRF_budget>1 是预算效率事实,**非** adaptive superiority)。**不主张**:Gradient 优于全部固定规则(M3D-3 FAIL)、universal optimality/global convergence/full-matrix/real-system cost efficiency。

### 5.1 局限(freeze audit 增补)

- **事件构型覆盖集中**:冻结基准的 WIDEN 态全部来自 {c000,c001},SHRINK 态全部来自 {c000,c001}——符号切换的实证仅在两个 event configs 上成立;**不得声称 sign switching 已跨全部 8 个事件构型泛化**(HOLD 类覆盖较广但类性能未达标);
- **协议局限(illegal comparator arm)**:`c000@0.55` 的 ALWAYS_SHRINK 臂违反 frozen legality floor(min-eig 0.450<0.5);其统计采用合法分母(该 trial 在 ALL 规则通道排除,永不作为 tie/base/win 证据);不改选 benchmark state;
- 门判定维持:M3D-2 FAIL、M3D-3 FAIL、M3D-5 FAIL、Strong PASS。

## 6. 后续状态

```text
M3-D-v0 = EXECUTED (no adaptive advantage over Always-Widen; near-oracle; STRONG VRF gate PASSED but does not authorize full-matrix escalation per Sec.28/42)
full-matrix M3-v1: 依旧封锁(需要 M3D-3 通过)
next  = 由程序路线决定(候选: 政策侧修复 HOLD 决策面的后续任务需全新 preregistration; 或 M3-D 作为负结果分支归档)
```

## 7. 冻结决定建议

按 §41 负结果政策映射:C 案(accuracy 高、best-fixed 优势缺席)+ D 案要素。建议将 M3-D 记录为负结果主判定执行完毕、等待操作者单独打 tag(`RareTopo-M3-D-v0`)或指示下一步研究任务;本报告不创建 tag。

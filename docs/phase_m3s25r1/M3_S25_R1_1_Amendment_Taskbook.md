# M3-S25-R1.1 Support-Invariant Amendment Taskbook

> **Provenance.** This file is the frozen M3-S25-R1.1 amendment taskbook,
> transcribed verbatim from the human-issued task text received 2026-09-06
> (sections 0-14).  It is the authoritative amendment document; the
> machine-executable application lives in
> `configs/phase_m3s25r1/m3s25r1_contract.json` (invariant definition
> update), `results/phase_m3s25r1/preflight/` (zero-sampling validation)
> and `docs/phase_m3s25r1/M3_S25_R1_1_Amendment_Record.md`, all hash-locked
> by `configs/phase_m3s25r1/m3s25r1_hash_manifest.json`.

---

# M3-S25-R1.1 Support-Invariant Amendment Taskbook

## 0. 阶段定位

**阶段名称：** M3-S25-R1.1\
**Parent：** M3-S25-R1 Round 0\
**性质：** Zero-sampling specification amendment\
**目标：** 修正 M3-S25-R1 中 support-span regression invariant 与 frozen
hash-first candidate selection mechanism 的内部冲突。

本阶段不是重新设计 candidate generation，不是重新搜索 SHRINK，不是补充
truth sampling。

唯一允许修改：

> support coverage invariant 的数学定义。

以下内容保持冻结：

-   config universe；
-   candidate generation mechanism；
-   hash-first selection；
-   freshness firewall；
-   legality rules；
-   seeds；
-   truth semantics；
-   budget；
-   runtime fail-closed ordering；
-   panel rules。

------------------------------------------------------------------------

# 1. Parent 状态封存

M3-S25-R1 Round 0 终态：

    candidate generation:
    PASS

    freshness:
    PASS

    label isolation:
    PASS

    seed:
    PASS

    budget:
    PASS

    runtime:
    PASS

    hash lock:
    PASS

    support-span invariant:
    FAIL

失败原因：

    c000:
    span = 0.6971

    cf1n_new_002:
    span = 0.6649

该失败发生于：

    samples = 0
    TRUTH_AUTHORIZED = NO

因此：

-   没有 truth 消耗；
-   没有科学结果污染；
-   不需要重新执行实验。

------------------------------------------------------------------------

# 2. Amendment 原则

本 amendment 遵循：

## 不改变生成机制

禁止：

-   修改 anchor 数量；
-   修改 hash ranking；
-   修改 stratum 数量；
-   修改 fresh selection；
-   重新抽取 candidate；
-   替换失败 config candidate。

冻结：

    m3s25r1_candidate_universe.json

继续作为唯一 candidate universe。

------------------------------------------------------------------------

# 3. 原 Sec.9 冲突

原定义：

对于每个 config：

\[ `\max`{=tex}(u)-`\min`{=tex}(u)`\ge0.70`{=tex} \]

该条件与：

-   65 anchors/stratum；
-   hash-first minimum hash selection；

不具有确定兼容性。

原因：

hash selection 在每个 stratum 内随机选择位置。

因此：

-   极端 stratum 的 selected anchor 不保证靠近边界；
-   span 存在随机波动。

------------------------------------------------------------------------

# 4. 新 Support Coverage Invariant

M3-S25-R1.1 将 Sec.9 替换为以下三个层级的不变量。

------------------------------------------------------------------------

## Invariant A：Stratum Occupancy

每个 config：

\[ N\_{occupied}=8 \]

要求：

    8 strata
    8 selected anchors
    0 empty strata

该条件保证整个 support window 被结构化覆盖。

------------------------------------------------------------------------

## Invariant B：Minimum Support Reach

每个 config：

\[ `\min`{=tex}(u)`\le0.25`{=tex} \]

含义：

至少存在一个 candidate 位于窗口前 25% support 区域。

------------------------------------------------------------------------

## Invariant C：Maximum Support Reach

每个 config：

\[ `\max`{=tex}(u)`\ge0.85`{=tex} \]

含义：

至少存在一个 candidate 位于窗口后 15% support 区域。

------------------------------------------------------------------------

## Invariant D：Anti-collapse Span

替代原：

\[ span`\ge0.70`{=tex} \]

改为：

\[ `\boxed{
span=\max(u)-\min(u)\ge0.65
}`{=tex} \]

原因：

-   父阶段 collapse：

\[ span`\approx0.0083`{=tex} \]

-   R1 当前最差：

\[ span=0.6649 \]

新的阈值仍保持数量级分离。

------------------------------------------------------------------------

# 5. 不变量解释

新的 invariant 关注：

> support 是否覆盖。

而不是：

> 随机 hash draw 是否恰好产生极端跨度。

因此：

合法状态：

    stratum coverage PASS
    min/max reach PASS
    span >= 0.65 PASS

即可认为：

    support completion achieved

------------------------------------------------------------------------

# 6. 禁止事项

本 amendment 禁止：

-   修改 candidate universe；
-   修改 universe SHA；
-   修改历史 truth；
-   修改 R1 budget；
-   修改 seed namespace；
-   修改 truth classifier；
-   修改 panel quota；
-   修改 runtime。

禁止：

    重新 hash
    重新抽签
    替换 candidate

------------------------------------------------------------------------

# 7. Hash 与冻结规则

R1.1 不产生新的 candidate universe。

更新：

    m3s25r1_contract.json

中的 invariant definition hash。

必须记录：

-   parent contract hash；
-   amendment hash；
-   old invariant；
-   new invariant；
-   reason。

------------------------------------------------------------------------

# 8. Zero-sampling Validation

执行：

    samples = 0
    simulator calls = 0

验证：

## Candidate

    240 states
    30 configs
    8 strata/config

保持不变。

## Freshness

    0 collision
    0 substitution

## Support

检查：

    occupied strata = 8/8
    min(u) <= 0.25
    max(u) >= 0.85
    span >= 0.65

------------------------------------------------------------------------

# 9. Runtime Gate

R1.1 完成后：

若 preflight PASS：

    M3_S25_R1_TRUTH_AUTHORIZED = NO

等待人工审计。

只有人工提交：

    NO -> YES

后允许：

    truth_execute

------------------------------------------------------------------------

# 10. Truth Budget

不改变：

    P_ref:
    0

    Discovery:
    240 × 3 × 100k

    Confirmation:
    240 × 3 × 500k

总预算：

\[ 432,000,000 \]

保持：

    planned == max
    topup = 0
    early_stop = false

------------------------------------------------------------------------

# 11. Regression Requirements

新增测试：

## Invariant replacement

验证：

    old span=0.70 removed
    new span=0.65 active

## Candidate immutability

验证：

    candidate universe SHA unchanged

## No science drift

验证：

    truth semantics hash unchanged
    seed namespace unchanged
    budget unchanged

## Gate isolation

验证：

    preflight cannot enable truth
    tests cannot enable truth

------------------------------------------------------------------------

# 12. Final Outcomes

M3-S25-R1.1 只允许两个结果：

## PASS

    PREFLIGHT PASS
    samples=0
    ready for human execution audit

进入：

    M3-S25-R1 truth authorization

------------------------------------------------------------------------

## FAIL

    M3-S25-R1.1 PREFLIGHT BLOCKED
    samples=0
    STOP

不得自行修改规则。

------------------------------------------------------------------------

# 13. Round 0 Execution Order

固定：

    1. create amendment document
    2. update contract invariant only
    3. update hash manifest
    4. run zero-sampling preflight
    5. run regression tests
    6. verify candidate SHA unchanged
    7. commit
    8. push
    9. STOP
    10. human execution-readiness audit

------------------------------------------------------------------------

# 14. Current Authorization State

必须保持：

    M3_S25_R1_TRUTH_AUTHORIZED = NO

    M3_S25_R1_ARM_A_AUTHORIZED = NO

    M3_S25_R1_ARM_B_AUTHORIZED = NO

    VALUE / RARITY / M3-Q = BLOCKED

------------------------------------------------------------------------

# Conclusion

M3-S25-R1.1 的唯一任务：

> 将 support coverage 的评价标准从"随机 hash
> 结果必须达到固定跨度"修正为"结构化分层覆盖 + 边界 reach +
> anti-collapse span"。

该 amendment
不改变任何候选、数据、预算和实验，仅修复预注册规则中的数学不一致。

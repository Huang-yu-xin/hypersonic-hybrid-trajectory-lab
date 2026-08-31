# RareTopo M3-DS — Corrected Directional-Sign Benchmark with Abstention
## Benchmark Preregistration & Construction Taskbook for Codex

> 项目：`hypersonic-hybrid-trajectory-lab`
>
> 当前 corrected lineage：
>
> ```text
> RareTopo-M3-v2
> RareTopo-M3-D-v1
> RareTopo-ER1-v0
> M3-D2 D2-B
> M3-D3 D3-DISC-B
> M3-RF-B
> ```
>
> M3-RF 最终决策：
>
> ```text
> PRIMARY ROUTE:
> M3-RF-B — REFORMULATE TO DIRECTIONAL WIDEN/SHRINK + ABSTAIN
> ```
>
> corrected evidence：
>
> ```text
> D2 independently confirmed:
> WIDEN  = 12
> HOLD   = 3
> SHRINK = 10
> AMBIGUOUS = 2
>
> D3 boundary-focused discovery:
> WIDEN  = 1
> HOLD   = 2
> SHRINK = 1
> AMBIGUOUS = 10
> INVALID = 0
>
> D3-DISC-B:
> provisional HOLD insufficient
> ```
>
> 因此：
>
> \[
> \boxed{
> \text{HOLD is no longer treated as a balanced action class.}
> }
> \]
>
> 新的 controller semantics：
>
> ```text
> WIDEN   = deploy widening direction
> SHRINK  = deploy shrinking direction
> ABSTAIN = insufficient evidence → BASE / no adaptation
> ```
>
> 其中：
>
> \[
> \boxed{
> \text{ABSTAIN is a protocol action, not a supervised third-class label.}
> }
> \]
>
> M3-DS 的任务是构造一个 corrected、可冻结、可用于未来 controller
> evaluation 的 **双轴 benchmark**：
>
> ```text
> Axis A — Directional Sign
>         confirmed WIDEN vs confirmed SHRINK
>
> Axis B — Abstention Safety
>         low-confidence / HOLD / ambiguous challenge states
> ```
>
> 本阶段不运行 controller。
> rarity-shift 仍然 BLOCKED。
> M3-Q 仍然 BLOCKED。

---

# 0. Core Scientific Question

M3-DS 只回答：

\[
\boxed{
\text{Can we freeze a corrected benchmark that separately measures}
\\
\text{directional decision quality and abstention safety?}
}
\]

它不回答：

```text
controller 是否优于 fixed
rarity-shift 是否翻转 VRF
pilot cost 是否值得
```

这些属于后续 M3-G2 / BV2 / CA 类阶段。

---

# 1. Benchmark Philosophy

旧三动作 benchmark：

```text
WIDEN / HOLD / SHRINK
```

要求三类平衡。

corrected evidence 已表明：

```text
W/S 自然且稳定
HOLD 稀少且 near-boundary ambiguity 占主导
```

因此新 benchmark 不再要求：

```text
8 HOLD
```

而是拆成两个问题：

## Axis A — Directional Sign Accuracy

在 reference evidence 明确支持 W 或 S 的状态上：

```text
controller 是否判断正确方向？
```

## Axis B — Abstention Safety

在 reference evidence 接近零、支持不足或不唯一的状态上：

```text
controller 是否避免错误部署方向动作？
```

这两个问题必须分开统计。

---

# 2. Hard Firewall

M3-DS 禁止：

```text
把 ABSTAIN 当第三个 ground-truth class
把历史 HOLD 重命名为 ABSTAIN truth
修改 corrected classifier
修改 thresholds
修改 event semantics
修改 full-event probability domain
手工 cherry-pick directional states
根据未来 controller 表现选择 benchmark
重新运行 historical M3-G/BV2/CA
运行 rarity-shift
运行 M3-Q
运行 PF
```

本阶段：

```text
controller_online_trials = 0
```

---

# 3. Phase Structure

建议：

```text
DS-0
Parent/source audit
ZERO simulator

DS-1
Directional Axis construction
ZERO simulator

DS-2
Abstention Safety Axis construction
ZERO simulator by default

DS-3
Optional independent reference confirmation
ONLY if needed by preregistered safety-axis rule

DS-4
Dual-axis benchmark freeze
ZERO controller trials
```

---

# 4. Parent Provenance Audit

先执行：

```bash
git branch --show-current
git rev-parse HEAD
git status --short --branch
git log --oneline --decorate -30
git tag --list
```

必须确认：

```text
ER-1 corrected lineage reachable
M3-D2 D2-B reachable
M3-D3 D3-DISC-B reachable
M3-RF-B decision reachable
```

若不匹配：

```text
STOP
```

---

# 5. Source Manifest

创建：

```text
results/phase_m3ds/summary/
m3ds_source_manifest.json
```

锁定至少：

```text
ER-1 semantic contract
M3-v2 corrected results
M3-D-v1 corrected reference records
M3-D2 confirmation states
M3-D2 class-transition audit
M3-D2 final verdict
M3-D3 discovery states
M3-D3 discovery verdict
M3-RF action-space decision
corrected classifier source
```

每项：

```text
path
sha256
commit
role
read_only = true
```

---

# 6. DS-1 — Directional Axis Candidate Universe

Directional candidate universe 只能使用：

```text
independently confirmed corrected D2 states
```

即：

```text
WIDEN  = 12
SHRINK = 10
```

禁止使用：

```text
D3 discovery-only W/S
D2 discovery-only W/S
historical remote pre-ER1 states
```

作为 primary directional benchmark evidence。

---

# 7. Why D2 Confirmed States Are Eligible

这些状态已经通过：

```text
corrected event semantics
full-event probability domain
independent confirmation
frozen corrected classifier
```

因此不需要为了 M3-DS 再生成 reference simulator data。

DS-1：

```text
extra_simulator_calls = 0
```

---

# 8. Directional Axis Target Size

推荐冻结：

```text
8 WIDEN
8 SHRINK
```

总：

```text
16 directional states
```

原因：

```text
保持与旧 benchmark 规模相近
避免 class imbalance
D2 已有 12W/10S，供确定性 diversity selection
```

---

# 9. Directional Diversity Gate

exact 8/8 不能只按 strongest effect 选。

必须优先保持科学 diversity。

建议 gate：

```text
WIDEN selected states:
>= 4 distinct config IDs

SHRINK selected states:
>= 4 distinct config IDs

both classes:
cover as broad an s2 span as deterministically possible
```

若 source stratum 仍是 corrected scientific metadata：

建议：

```text
each class spans >=2 strata
```

只有 machine-readable artifacts 支持时采用。

---

# 10. Deterministic Directional Selection Rule

必须在任何 controller experiment 前冻结。

推荐 greedy rule：

For each class separately：

```text
Step 1:
maximize distinct config coverage

Step 2:
within config, prefer greater s2 spacing from already selected states

Step 3:
prefer stronger independent-confirmation support margin

Step 4:
prefer larger absolute directional effect only after diversity/support

Step 5:
lexical state_id tie-break
```

禁止：

```text
future controller score
future regret
future VRF
```

参与 selection。

---

# 11. Directional Selection Audit

输出：

```text
results/phase_m3ds/summary/
m3ds_directional_candidates.csv
m3ds_directional_selected.csv
m3ds_directional_selection_audit.json
```

字段：

```text
state_id
class
config_id
s2
confirmation support
r_w
r_s
selection rank
selection reason
selected
```

---

# 12. Directional Axis Gate

定义：

```text
M3DS-DIR-1
```

要求：

```text
selected WIDEN = 8
selected SHRINK = 8
invalid = 0
diversity gate PASS
source lock PASS
```

若 PASS：

```text
Directional Axis constructible
```

若 FAIL：

```text
STOP
```

不进入 controller。

---

# 13. Directional Axis Reference Label

Axis A ground truth 只有：

```text
WIDEN
SHRINK
```

这些来自高预算 corrected reference classifier。

ABSTAIN 不出现在 Axis A ground truth。

---

# 14. Reserve Directional Set

未进入 primary 8/8 的 D2 confirmed directional states：

```text
remaining W = 4
remaining S = 2
```

建议保留为：

```text
Directional Reserve / Stress Set
```

用途：

```text
future robustness only
```

不得用于 controller tuning。

必须在 M3-DS freeze 时锁定。

---

# 15. DS-2 — Abstention Safety Axis

Safety Axis 的目的不是构造一个 balanced “ABSTAIN class”。

它要测：

> 在 reference evidence 不支持稳定方向部署时，未来 policy 是否会安全地选择 BASE/no adaptation。

---

# 16. Safety-Axis Candidate Types

允许三类来源：

## Type H — independently confirmed HOLD

D2：

```text
3 states
```

语义：

```text
reference evidence supports no directional improvement under corrected classifier
```

未来 policy 的合理安全行为：

```text
ABSTAIN / BASE
```

但仍然不把 HOLD 改名成新的 truth class。

---

## Type A — independently confirmed AMBIGUOUS

D2：

```text
2 states
```

语义：

```text
reference evidence insufficient / non-unique
```

未来 policy 的安全目标：

```text
avoid wrong-direction deployment
```

---

## Type D3-Amb — D3 discovery ambiguous

D3：

```text
10 states
```

这些不是 independently confirmed。

因此默认只能作为：

```text
Safety Challenge Candidates
```

不能直接成为 high-confidence frozen safety reference。

---

# 17. Primary Safety Axis Without New Simulation

最保守的 primary Safety Axis：

```text
D2 confirmed HOLD = 3
D2 confirmed AMBIGUOUS = 2
```

共：

```text
5 reference safety states
```

这 5 个可 zero-sim freeze。

---

# 18. Safety Semantics

每个 safety state 保留原 reference status：

```text
HOLD
AMBIGUOUS
```

未来 controller evaluation 统一计算：

```text
ABSTAIN deployed?
WIDEN deployed?
SHRINK deployed?
```

但 benchmark 不把 reference label 改成：

```text
ABSTAIN
```

---

# 19. Safety Metrics for Future Controller

M3-DS 只定义，不执行。

未来 M3-G2 必须报告：

### Abstention rate on safety axis

\[
A_{\rm safe}
=
\frac{\#\text{ABSTAIN on safety states}}
{N_{\rm safety}}
\]

### Unsafe directional deployment rate

\[
U_{\rm safe}
=
\frac{\#\text{W/S deployed on safety states}}
{N_{\rm safety}}
\]

但对于 confirmed HOLD 与 confirmed AMBIGUOUS 可分别报告。

---

# 20. Wrong-Direction Risk on Directional Axis

未来 primary safety metric：

\[
\boxed{
R_{\rm wrong}
=
\frac{
\#(\text{W truth → SHRINK})+
\#(\text{S truth → WIDEN})
}{
N_{\rm directional}
}
}
\]

ABSTAIN 不算 wrong-direction。

但会降低 coverage。

---

# 21. Directional Coverage

定义：

\[
C_{\rm dir}
=
\frac{
\#\text{non-abstained directional states}
}{
N_{\rm directional}
}
\]

因此未来 controller 不可通过：

```text
ABSTAIN on everything
```

获得虚假安全成功。

---

# 22. Selective Directional Accuracy

定义：

\[
Acc_{\rm selective}
=
P(
\text{correct direction}
\mid
\text{not abstained}
)
\]

future controller 同时必须报告：

```text
coverage
selective accuracy
wrong-direction rate
```

---

# 23. Risk-Coverage Framing

未来 M3-G2 可将 controller 理解为 selective decision policy：

```text
context → {WIDEN, SHRINK, ABSTAIN}
```

核心曲线：

```text
wrong-direction risk
vs
directional coverage
```

但 M3-DS 不拟合 policy。

---

# 24. Optional DS-3 — D3 Ambiguous Independent Confirmation

是否需要对 D3 的 10 个 discovery ambiguous 做新 confirmation，必须在 DS-2 zero-sim 阶段先决定。

推荐默认：

```text
NOT REQUIRED for primary M3-DS freeze
```

因为已有：

```text
16-state directional primary
5-state independently confirmed safety primary
```

已经足够定义第一版 benchmark。

---

# 25. When Optional Confirmation Is Allowed

只有如果人类明确认为：

```text
5 safety states too small for future safety evaluation
```

才允许 separately preregister：

```text
DS-3 Safety-Axis Expansion
```

针对 D3 的 10 ambiguous states进行：

```text
500k/arm
20 paired CRN batches
same corrected classifier
independent seed namespace
```

但：

```text
不影响 primary directional benchmark
不修改 directional selection
不要求确认出固定数量 “ABSTAIN”
```

---

# 26. No Quota for Safety Axis

非常重要：

Safety Axis 没有：

```text
need >=8 ABSTAIN
```

这样的 quota。

因为 ABSTAIN 是 protocol behavior。

Safety Axis 只需要：

```text
predeclared low-confidence/no-direction reference states
```

---

# 27. Primary M3-DS Benchmark Structure

推荐：

```text
Axis A — Directional Primary:
8 WIDEN
8 SHRINK

Axis A Reserve:
4 WIDEN
2 SHRINK

Axis B — Safety Primary:
3 confirmed HOLD
2 confirmed AMBIGUOUS

Axis B Expansion:
optional, separately preregistered
```

---

# 28. Benchmark JSON Schema

创建：

```text
results/phase_m3ds/summary/
m3ds_benchmark.json
```

建议：

```json
{
  "directional_primary": {
    "widen": [],
    "shrink": []
  },
  "directional_reserve": {
    "widen": [],
    "shrink": []
  },
  "safety_primary": {
    "confirmed_hold": [],
    "confirmed_ambiguous": []
  },
  "safety_expansion": [],
  "controller_online_trials": 0,
  "rarity_shift_authorized": false
}
```

---

# 29. Benchmark Version Semantics

不要叫：

```text
8/8/8 benchmark
```

正式名称：

```text
Corrected Directional-Sign Benchmark with Abstention Safety Axis
```

简称：

```text
M3-DS
```

---

# 30. M3DS Main Gate

定义：

```text
M3DS-1
```

要求：

```text
directional primary W = 8
directional primary S = 8
directional diversity PASS
safety primary states >= 5
all safety states independently confirmed
source lock PASS
event semantics PASS
classifier contract PASS
no controller trials
full regression PASS
```

---

# 31. M3DS-A

若 PASS：

```text
M3DS-A
CORRECTED DIRECTIONAL BENCHMARK WITH SAFETY AXIS FROZEN
```

允许创建：

```text
RareTopo-M3-DS-v0
```

或 repo-consistent equivalent。

下一阶段才允许：

```text
M3-G2
Corrected Directional Controller with Abstention
```

---

# 32. M3DS-B

如果方向 exact 8/8 或 diversity gate失败：

```text
M3DS-B
DIRECTIONAL BENCHMARK NOT CONSTRUCTIBLE
```

停止 controller line。

---

# 33. M3DS-C

如果 safety primary provenance不足：

```text
M3DS-C
SAFETY AXIS INSUFFICIENTLY GROUNDED
```

可考虑 DS-3 minimum information confirmation。

不直接运行 controller。

---

# 34. Controller Firewall

整个 M3-DS：

```text
controller_online_trials = 0
```

无例外。

---

# 35. Rarity Firewall

整个 M3-DS：

```text
rarity_shift = BLOCKED
```

只有 M3-G2 corrected controller重新建立后，才讨论 rarity。

---

# 36. M3-Q Firewall

```text
M3-Q = BLOCKED
```

---

# 37. Historical Remote Evidence Policy

M3-DS 不能把：

```text
historical M3-G-v1
historical BV2
historical CA
historical PF
```

作为 corrected benchmark evidence。

可以在 docs 中标：

```text
historical / superseded under ER-1
```

---

# 38. Required Zero-Sim Analyses

M3-DS 应生成：

```text
directional class balance
config diversity
s2 coverage
support-margin distribution
safety-state provenance
HOLD vs AMBIGUOUS safety composition
```

无需 simulator。

---

# 39. Required Figures

至少：

```text
DS-1 directional candidate universe 12W/10S
DS-2 deterministic selected 8W/8S
DS-3 config diversity map
DS-4 s2 coverage by direction
DS-5 confirmation support margins
DS-6 safety primary states
DS-7 dual-axis benchmark schematic
DS-8 future risk-coverage metric schematic
```

---

# 40. Required Docs

```text
docs/phase_m3ds/
M3_DS_Directional_Benchmark_Task.md
M3_DS_Parent_Audit.md
M3_DS_Directional_Selection_Audit.md
M3_DS_Safety_Axis_Audit.md
M3_DS_Benchmark_Freeze.md
```

---

# 41. Required Outputs

```text
results/phase_m3ds/summary/
m3ds_source_manifest.json
m3ds_directional_candidates.csv
m3ds_directional_selected.csv
m3ds_directional_selection_audit.json
m3ds_safety_primary.csv
m3ds_benchmark.json
m3ds_final_verdict.json
```

---

# 42. Required Tests

至少：

```text
test_m3ds_parent_rf_b
test_m3ds_zero_simulator
test_m3ds_source_hashes
test_m3ds_only_d2_confirmed_directional
test_m3ds_exact_8w_8s
test_m3ds_directional_diversity
test_m3ds_selection_deterministic
test_m3ds_no_future_controller_metric_in_selection
test_m3ds_directional_reserve_frozen
test_m3ds_safety_only_independently_confirmed
test_m3ds_abstain_not_ground_truth_label
test_m3ds_event_semantics_unchanged
test_m3ds_classifier_unchanged
test_m3ds_controller_zero
test_m3ds_rarity_blocked
test_m3ds_m3q_blocked
test_m3ds_output_schema
```

最终：

```bash
python -m pytest -q
```

必须 exit 0。

---

# 43. Commit Sequence

建议：

```text
1. M3-DS task + parent/source audit
2. directional candidate reconstruction
3. deterministic 8/8 selection
4. reserve freeze
5. safety-axis reconstruction
6. benchmark JSON + figures
7. focused tests
8. full regression + final freeze
```

---

# 44. Final Tag Policy

只有：

```text
M3DS-A
```

才创建：

```text
RareTopo-M3-DS-v0
```

如果：

```text
M3DS-B/C
```

不创建 controller-valid benchmark tag。

---

# 45. Future M3-G2 — Not Executed Here

如果 M3DS-A：

下一阶段可 separately preregister：

```text
M3-G2
Corrected Directional Controller with Abstention
```

未来 policy：

```text
context
→ WIDEN / SHRINK / ABSTAIN
```

---

# 46. Future M3-G2 Primary Metrics

M3-DS 只定义，不执行：

### Directional wrong-action rate

```text
W truth → SHRINK
S truth → WIDEN
```

### Directional coverage

```text
fraction non-abstained
```

### Selective directional accuracy

```text
accuracy conditional on non-abstain
```

### Safety-axis unsafe deployment rate

```text
fraction W/S deployed on safety states
```

---

# 47. No “Accuracy Including Abstain”

禁止用一个单一三分类 accuracy：

```text
W / S / ABSTAIN accuracy
```

因为 ABSTAIN不是 ground-truth class。

必须分：

```text
directional accuracy
coverage
safety abstention
unsafe deployment
```

---

# 48. Future Regret Semantics

未来如做 regret：

Directional states：

\[
Regret(a)
=
M_2(a)-M_2(a^*)
\]

Safety states：

```text
BASE is safety fallback
```

但具体 reward/cost formula必须在 M3-G2 preregistration冻结。

---

# 49. ICML Interpretation

RF-B + M3-DS 的叙事比强行三分类更自然：

旧问题：

```text
Can we balance W/H/S?
```

新问题：

> Can a noisy objective-gradient controller make the correct directional
> proposal decision when evidence is strong, and safely abstain when evidence
> is weak?

这可以自然映射为：

```text
selective prediction
risk-coverage
contextual decision
uncertainty-aware abstention
```

更接近 ML 表达。

---

# 50. Current Scientific Claim Boundary

M3-DS 若成功，只能 claim：

> corrected empirical evidence supports a directional WIDEN/SHRINK benchmark
> with a separately defined safety/abstention axis.

不能 claim：

```text
controller成功
adaptive > fixed
rarity决定价值
absolute efficiency
```

这些都尚未重新验证。

---

# 51. Codex Final Report Format

```text
M3-DS STATUS:
COMPLETE / BLOCKED / INVALID

PARENT:
M3-RF route = RF-B
ER1 lineage =
D2 evidence =

ZERO SIMULATOR:
extra_simulator_calls =

DIRECTIONAL CANDIDATES:
confirmed W = 12
confirmed S = 10

DIRECTIONAL PRIMARY:
selected W = 8
selected S = 8
W configs =
S configs =
diversity gate =

DIRECTIONAL RESERVE:
W =
S =

SAFETY PRIMARY:
confirmed HOLD =
confirmed AMBIGUOUS =
total =
all independently confirmed =

ABSTAIN SEMANTICS:
ground-truth class = NO
protocol behavior = YES
fallback = BASE

M3DS-1:
PASS / FAIL =

FINAL VERDICT:
M3DS-A / M3DS-B / M3DS-C / INVALID

CONTROLLER ONLINE TRIALS:
0

RARITY SHIFT:
BLOCKED

M3-Q:
BLOCKED

NEXT AUTHORIZED ACTION:
M3-G2 preregistration / DS-3 safety confirmation / stop

SOURCE HASHES:
unchanged =

FULL REGRESSION:
...

TAG:
...
```

---

# 52. Final Scientific Principle

D2 与 D3 已经说明：

\[
\boxed{
\text{HOLD is not a robust class to balance.}
}
\]

但 corrected evidence 同时表明：

\[
\boxed{
\text{WIDEN and SHRINK are independently reproducible.}
}
\]

因此新的 benchmark 不应问：

```text
Can we force three balanced labels?
```

而应该问：

\[
\boxed{
\text{Can we make the right directional decision when evidence is strong,}
\\
\text{and abstain safely when it is not?}
}
\]

这就是 M3-DS 的唯一任务。

如果 M3DS-A 成功，才重新启动 corrected controller evaluation。

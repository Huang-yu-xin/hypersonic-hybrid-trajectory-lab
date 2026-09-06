# M3-S25-R1 Taskbook

> **Provenance.** This file is the frozen M3-S25-R1 taskbook, transcribed
> verbatim from the human-issued task text received 2026-09-06 (taskbook
> sections 1-39).  It is the authoritative preregistration document for the
> stage; the machine-executable freezes live under `configs/phase_m3s25r1/`
> and `results/phase_m3s25r1/preflight/` and are hash-locked against this
> text by `configs/phase_m3s25r1/m3s25r1_hash_manifest.json`.

---

# M3-S25-R1 Taskbook

## Support-Completion Replacement Development Stage

**阶段名称：** M3-S25-R1
**阶段性质：** Replacement Development / Parameter-Support Completion
**Parent：** M3-S2S
**Parent terminal verdict：** `M3-S2S-PANEL-BLOCKED`
**Parent frozen HEAD：** `f0d73702dc284f9a2ce1f1a205bb5f56f1324d38`

---

# 1. 阶段目标

M3-S25-R1 的唯一科学目标是：

> 修复 M3-S2S 候选生成只覆盖合法 \(s_2\) 窗口低端所造成的 parameter-support defect，在不使用 truth label 进行候选选择的前提下，对此前未充分覆盖的合法 \(s_2\) 区域进行预注册、分层、均匀的 support completion，并建立新的 truth-confirmed development pool。

本阶段**不是**：

* M3-S2S 的 top-up；
* 对原 436M truth budget 的追加；
* 针对 SHRINK 标签的定向搜索；
* 对 30/30/30/30 panel quota 的放宽；
* 对旧 candidate universe 的重新解释；
* 对旧 240 个 truth-exposed states 的重新 confirmation。

---

# 2. Parent 阶段封存

M3-S2S 固定终态：

```text
M3-S2S:
TRUTH EXECUTION       = PASS
TRUTH UNITS           = 488 / 488 COMPLETE
CONSUMED_INVALID      = 0
TRUTH SAMPLES         = 436,000,000
TRUTH RESULT          = W171 / A53 / H16 / S0
PANEL                 = M3-S2S-PANEL-BLOCKED
ARM_A                  = NOT AUTHORIZED
ARM_B                  = NOT AUTHORIZED
VALUE / RARITY / M3-Q = BLOCKED
```

原 240 个 state：

```text
development_eligible = YES
untouched_confirmation_eligible = NO
```

必须全部进入：

```text
M3-S25-R1 parent development registry
```

并永久保留其：

* state_id；
* config_id；
* \(s_2\)；
* frozen truth；
* truth source；
* source hashes；
* exposure status。

不得删除、替换或重新包装成 untouched data。

在创建 R1 前，应关闭旧 T1 gate：

```text
TRUTH_SAMPLING_AUTHORIZED: NO
ARM_A_AUTHORIZED: NO
ARM_B_AUTHORIZED: NO
```

并记录：

```text
M3-S2S truth authorization exercised and exhausted.
M3-S2S terminal status = M3-S2S-PANEL-BLOCKED.
TRUTH_BUDGET consumed = 436,000,000 / 436,000,000.
```

---

# 3. R1 独立授权门

R1 必须使用**新的 approval 文件和新的 gate 名称**，禁止复用旧阶段已使用过的 T1 gate。

初始状态：

```text
M3_S25_R1_TRUTH_AUTHORIZED: NO
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
```

例如：

```text
docs/phase_m3s25r1/M3_S25_R1_Human_Approval.md
```

任何 Codex / script / test / preflight：

> 不得自行把任何 `NO` 改为 `YES`。

---

# 4. Config universe

R1 **不搜索新 config**。

严格继承 M3-S2S 的冻结 30-config universe：

$$
\mathcal C_{\mathrm{R1}}
=
\mathcal C_{\mathrm{S2S}},
\qquad
|\mathcal C_{\mathrm{R1}}|=30.
$$

理由：

> 当前已定位的问题是 \(s_2\)-support placement defect，而不是 config diversity 不足。

因此 R1 不允许：

* 新 raw lattice config；
* config substitution；
* 删除某个 config；
* 根据旧 truth label 调整 config 权重。

必须对 parent config registry 做 hash pin。

---

# 5. Support coordinate

对于每个 config \(c\)，继承其合法窗口：

$$
[s_{2,\mathrm{lo}}(c),s_{2,\mathrm{hi}}(c)].
$$

保持：

$$
s_{2,\mathrm{hi}}=8.0
$$

以及原有 legality calculation 完全不变。

定义 normalized log-support coordinate：

$$
u(s_2;c)
=
\frac{
\log s_2-\log s_{2,\mathrm{lo}}(c)
}{
\log s_{2,\mathrm{hi}}(c)-\log s_{2,\mathrm{lo}}(c)
}.
$$

因此：

$$
u\in[0,1].
$$

M3-S2S 实际候选约只覆盖：

$$
u\lesssim0.123.
$$

R1 固定 support-completion 区间：

$$
\boxed{
u\in[0.15,1.00]
}
$$

该边界在任何 truth sampling 前冻结。

---

# 6. 分层候选设计

每个 config 固定生成：

$$
K=8
$$

个新的 candidate states。

总候选数：

$$
30\times8
=
\boxed{240}.
$$

将：

$$
[0.15,1]
$$

等分为 8 个 strata。

定义：

$$
e_i
=
0.15+\frac{0.85i}{8},
\qquad i=0,\ldots,8.
$$

第 \(i\) 个 stratum 为：

$$
I_i=[e_i,e_{i+1}].
$$

每个 config、每个 stratum **恰好选择一个 fresh state**。

因此每个 config 必须满足：

```text
8 strata
×
1 candidate per stratum
=
8 states
```

禁止：

> 在某个 stratum 不可用时，从其他 stratum 借一个 state。

若任意 config × stratum 无合法 fresh candidate：

```text
M3-S25-R1-PREFLIGHT-BLOCKED
STOP
samples = 0
```

---

# 7. Stratum 内 deterministic fresh selection

为防止再次出现：

> ascending scan → first 8 → low-end concentration

每个 stratum 内生成固定数量：

$$
L=65
$$

个 deterministic interior anchors：

$$
u_{i,m}
=
e_i+
\frac{m+1}{L+1}
(e_{i+1}-e_i),
\qquad
m=0,\ldots,L-1.
$$

对应：

$$
s_{2,i,m}
=
\exp\left[
\log s_{2,\mathrm{lo}}
+
u_{i,m}
\left(
\log s_{2,\mathrm{hi}}
-\log s_{2,\mathrm{lo}}
\right)
\right].
$$

对于每个 anchor 计算：

```text
SHA256(
"M3-S25-R1-CANDIDATE-V1|"
+ config_id
+ "|"
+ stratum_id
+ "|"
+ canonical_s2
)
```

按 hash 升序排序。

选择：

> 排名最高的第一个合法且 fresh 的 anchor。

因此 selection 与：

* truth label；
* discovery result；
* SHRINK/HOLD 数量；
* candidate 数值大小顺序

全部无关。

---

# 8. Freshness firewall

一个 R1 candidate 必须对同一 config 的**所有历史已表征 \(s_2\)** fresh。

历史集合至少包括：

* M3-CF*；
* M3-WCF*；
* M3-PI*；
* M3-S1*；
* M3-S2S；
* 所有 retired / truth-exposed / development artifacts。

设历史值为 \(s_2^{(h)}\)。

若：

$$
|s_2-s_2^{(h)}|
\le
10^{-6}
\max(1,|s_2^{(h)}|)
$$

则该 anchor 判为 collision，不可使用。

特别地：

> M3-S2S 的 240 个 truth-exposed states 必须全部进入 freshness exclusion set。

---

# 9. Candidate-universe preflight

在任何 sampling authorization 之前必须机械验证：

```text
configs                  = 30
strata/config            = 8
candidates               = 240
duplicate state_id       = 0
freshness violations     = 0
legality violations      = 0
truth labels consulted   = 0
candidate substitution   = 0
```

每个 config 还必须满足：

$$
\min u \ge 0.15,
$$

$$
\max u \le 1.0,
$$

以及：

$$
\boxed{
\max u-\min u\ge0.70
}
$$

并要求：

```text
each of the 8 frozen strata occupied exactly once
```

这是本阶段防止再次发生 candidate-support collapse 的强制 regression invariant。

---

# 10. Candidate universe freeze

生成并 git-track：

```text
configs/phase_m3s25r1/m3s25r1_candidate_universe.json
```

内容至少包含：

* config_id；
* state_id；
* \(s_2\)；
* normalized \(u\)；
* stratum_id；
* legality window；
* selected anchor；
* anchor hash；
* freshness audit；
* parent-universe reference；
* origin=`M3-S25-R1-SUPPORT-COMPLETION`。

candidate universe 必须 SHA256 pin。

授权以后：

> 不允许新增、删除、替换或重排 candidate。

---

# 11. P_ref policy

R1 不重新采样 P_ref。

原因：

30 个 config 在此前阶段已经存在与当前 truth semantics 兼容的 P_ref。

建立：

```text
configs/phase_m3s25r1/m3s25r1_p_ref_registry.json
```

恰好 30 条。

每条包含：

```text
config_id
source_stage
source_file
record_file_hash
protocol_hash
sample_count
n_batches
p_ref
```

对于 M3-S2S 的 8 个新 config：

> 使用刚完成的 durable COMPLETE PREF records。

对于其他 config：

> 使用此前 byte-verified / vendored P_ref。

所有 P_ref 在 runtime 使用前必须：

```text
source exists
→ source hash verified
→ protocol compatible
→ exactly one valid durable source
```

任一失败：

```text
M3-S25-R1-X
STOP
NO P_ref RESAMPLING
```

因此：

$$
\boxed{
R1\ P_{\mathrm{ref}}\ sampling\ budget=0
}
$$

---

# 12. Truth semantics

R1 不改变任何 truth 定义。

以下内容必须 byte-identical 或 hash-pinned 到 parent protocol：

* base / widen / shrink semantics；
* probability estimator；
* correction semantics；
* classifier；
* thresholds；
* ESS rules；
* numerical-validity rules；
* discovery sample count；
* confirmation sample count；
* batch structure；
* CRN semantics；
* failure semantics。

R1 改变的只有：

> state support。

不允许因为预期高 \(s_2\) 更可能出现 SHRINK 而改变 truth classifier。

---

# 13. Seed namespaces

R1 使用新的独立 namespace：

```text
M3-S25-R1-DISCOVERY
M3-S25-R1-CONFIRMATION
```

不得复用 M3-S2S seed namespace。

seed 由 frozen deterministic function 派生，并生成：

```text
configs/phase_m3s25r1/m3s25r1_truth_seed_manifest.json
```

必须证明：

```text
480 truth units
all seeds deterministic
0 duplicate logical unit
0 historical namespace collision
0 cross-stream collision
```

---

# 14. Truth execution scope

所有 240 candidates 都执行 discovery 和 confirmation。

禁止 discovery 后按 provisional class 选择性 confirmation。

即：

```text
confirmation_scope = ALL_240_R1_CANDIDATES
early_stop = false
```

这样避免 label-dependent confirmation selection。

---

# 15. Discovery budget

每 state：

$$
3\times100,000
$$

samples。

因此：

$$
240\times3\times100,000
=
\boxed{72,000,000}.
$$

---

# 16. Confirmation budget

每 state：

$$
3\times500,000
$$

samples。

因此：

$$
240\times3\times500,000
=
\boxed{360,000,000}.
$$

---

# 17. R1 truth budget

P_ref：

$$
0.
$$

Discovery：

$$
72,000,000.
$$

Confirmation：

$$
360,000,000.
$$

因此：

$$
\boxed{
\text{R1 TRUTH\_BUDGET\_PLANNED}
=
432,000,000
}
$$

并冻结：

$$
\boxed{
\text{R1 TRUTH\_BUDGET\_MAX}
=
432,000,000
}
$$

要求：

```text
planned == max == 432,000,000
topup = 0
early_stop = false
candidate substitution = false
```

总 truth units：

$$
240+240
=
\boxed{480}.
$$

---

# 18. Durable persistence contract

480 个 truth units 必须使用 durable transactional persistence。

每个 logical unit：

```text
STARTED
→ simulator
→ durable artifact
→ artifact hash verification
→ COMPLETE
```

只有：

```text
exactly one STARTED
exactly one COMPLETE
valid artifact hash
```

才属于可恢复 COMPLETE。

若 sampling 已经发生，但未产生合法 durable COMPLETE：

```text
CONSUMED_INVALID
→ M3-S25-R1-X
→ STOP
→ NO REPLAY
```

禁止：

* 同 logical unit 重采；
* seed substitution；
* same-arm rerun；
* top-up；
* partial record 当 COMPLETE。

---

# 19. Restart integrity

在 simulator 前必须扫描全部已有 R1 ledgers。

任何 unit：

### Fresh

```text
no artifact
AND
no ledger entry
```

才允许首次执行。

### Durable COMPLETE

必须验证：

```text
exactly 1 STARTED
exactly 1 COMPLETE
0 CONSUMED_INVALID
artifact exists
artifact SHA == COMPLETE.record_file_hash
```

通过后 skip。

### 其他任何状态

例如：

```text
STARTED-only
CONSUMED_INVALID
duplicate STARTED
duplicate COMPLETE
COMPLETE-without-STARTED
orphan artifact
hash mismatch
```

全部：

```text
M3-S25-R1-X
STOP
NO REPLAY
```

---

# 20. Runtime fail-closed ordering

`truth_execute` 必须固定为：

```text
1. verify parent terminal state
2. verify old S2S gate closed
3. verify R1 frozen inputs / candidate universe
4. verify P_ref registry and source hashes
5. verify all existing R1 ledger/restart states
6. verify R1 human truth authorization
7. construct pure execution plan
8. simulator calls
```

在 step 6 之前：

```text
simulator calls = 0
truth artifacts written = 0
ledger writes = 0
```

---

# 21. Truth authorization

完成：

* candidate freeze；
* protocol freeze；
* P_ref registry；
* seed manifest；
* budget contract；
* runtime tests；
* hashlock；
* preflight；

之后 STOP。

初始：

```text
M3_S25_R1_TRUTH_AUTHORIZED: NO
```

只有人工审计通过后才允许独立 authorization-only commit：

```text
NO → YES
```

此时：

```text
M3_S25_R1_ARM_A_AUTHORIZED = NO
M3_S25_R1_ARM_B_AUTHORIZED = NO
```

保持不变。

---

# 22. Truth execution completion condition

Truth stage 唯一正常完成条件：

```text
discovery     240 / 240 COMPLETE
confirmation  240 / 240 COMPLETE
CONSUMED_INVALID = 0
actual samples = 432,000,000
```

即：

$$
480/480
$$

durable COMPLETE。

如果不能满足：

```text
M3-S25-R1-X
STOP
```

---

# 23. New truth-exposed inventory

全部 240 个 R1 states 在获得 truth 后必须写入：

```text
results/phase_m3s25r1/summary/
m3s25r1_truth_exposed_inventory.json
```

从此：

```text
development_eligible = YES
untouched_confirmation_eligible = NO
```

无论最终有没有进入 panel。

---

# 24. Development union

定义：

$$
\mathcal D_{\mathrm{old}}
=
\text{M3-S2S 240 truth-exposed states},
$$

$$
\mathcal D_{\mathrm{new}}
=
\text{M3-S25-R1 240 truth-exposed states}.
$$

最终 development pool：

$$
\boxed{
\mathcal D_{\mathrm{union}}
=
\mathcal D_{\mathrm{old}}
\cup
\mathcal D_{\mathrm{new}}
}
$$

最多：

$$
480
$$

states。

旧数据不得因为 parent PANEL-BLOCKED 而丢弃。

---

# 25. Balanced development panel

目标保持：

```text
WIDEN       30
SHRINK      30
HOLD        30
AMBIGUOUS   30
TOTAL       120
```

即：

$$
30/30/30/30.
$$

禁止：

* quota relaxation；
* 120 → smaller panel；
* class merging；
* provisional truth；
  -人工挑选 state。

---

# 26. Panel selection

panel 输入池只能是：

$$
\mathcal D_{\mathrm{union}}.
$$

所有 state 必须具有 frozen confirmed truth。

使用新的 deterministic rank namespace：

```text
M3-S25-R1-PANEL-V1
```

并保留原 M3-S2S 的：

* class quota；
* deterministic round rule；
* config-diversity requirement；
* duplicate protection。

要求最终 panel：

```text
120 unique states
30 / class
>= 24 distinct configs
0 provisional states
0 unconfirmed states
```

若原 panel selector 无法在 union pool 中满足以上条件：

```text
M3-S25-R1-PANEL-BLOCKED
```

---

# 27. PANEL-BLOCKED semantics

若任意 class：

$$
N_c<30,
$$

或者 config-diversity rule 无法满足：

```text
M3-S25-R1-PANEL-BLOCKED
STOP
```

不得：

* 追加候选；
* 补采；
* 放宽 quota；
* 改 support interval；
* 再搜索新 config；
* 使用 reserve；
* 临时修改 classifier。

任何下一轮都必须另开新任务书。

---

# 28. Panel freeze

若成功，写入：

```text
configs/phase_m3s25r1/m3s25r1_panel.json
results/phase_m3s25r1/summary/m3s25r1_panel.csv
```

并记录：

* 120 state IDs；
* source stage：S2S / S25-R1；
* truth class；
* config_id；
* \(s_2\)；
* normalized \(u\)；
* truth artifact hash；
* ranking hash；
* panel SHA256。

之后：

> STOP。

不得自动进入 Arm A。

---

# 29. Arm gates

在 panel freeze 后：

```text
M3_S25_R1_ARM_A_AUTHORIZED: NO
M3_S25_R1_ARM_B_AUTHORIZED: NO
VALUE / RARITY / M3-Q: BLOCKED
```

必须完成独立 post-truth / post-panel audit。

只有之后新的人工 authorization 才可能允许 Arm A。

Arm B 不得与 Arm A 同时授权。

---

# 30. Reserve firewall

所有仍被标记为：

```text
protected reserve
untouched confirmation
final validation
```

的 states：

> R1 一律禁止使用。

R1 只允许：

1. 已 truth-exposed 的旧 development states；
2. 新生成并预注册的 R1 support-completion states。

---

# 31. 必须新增的 regression tests

至少包括：

### Candidate support

```text
exactly 30 configs
exactly 8 strata/config
exactly 240 states
all u >= 0.15
all u <= 1
per-config u span >= 0.70
each stratum exactly once
```

### Freshness

```text
collision with old S2S state → rejected
collision with any historical state → rejected
no cross-stratum borrowing
no label-dependent selection
```

### P_ref

```text
all 30 source hashes verified
missing source → fail before authorization
tampered source → fail before authorization
no P_ref simulator calls
```

### Restart

```text
STARTED-only → fail before simulator
CONSUMED_INVALID → fail before simulator
orphan artifact → fail
duplicate COMPLETE → fail
hash mismatch → fail
valid COMPLETE → safe skip
```

### Budget

```text
240 discovery
240 confirmation
480 total units
72M discovery
360M confirmation
432M total
planned == max
topup == 0
```

### Gate isolation

```text
old S2S truth gate must be NO
R1 truth gate initially NO
module import cannot flip gates
preflight cannot flip gates
tests cannot flip gates
Arm A/B stay NO
```

---

# 32. Required prereg artifacts

在任何 sampling 前至少冻结：

```text
docs/phase_m3s25r1/M3_S25_R1_Taskbook.md
docs/phase_m3s25r1/M3_S25_R1_Human_Approval.md

configs/phase_m3s25r1/m3s25r1_contract.json
configs/phase_m3s25r1/m3s25r1_candidate_universe.json
configs/phase_m3s25r1/m3s25r1_p_ref_registry.json
configs/phase_m3s25r1/m3s25r1_truth_seed_manifest.json
configs/phase_m3s25r1/m3s25r1_budget_contract.json
configs/phase_m3s25r1/m3s25r1_hash_manifest.json

results/phase_m3s25r1/preflight/
```

所有 frozen artifacts 必须 hash-lock。

---

# 33. Round 0：只允许 preregistration

R1 第一轮只允许：

```text
parent closure audit
candidate generation
freshness audit
support audit
P_ref source audit
seed generation
budget construction
runtime implementation
tests
preflight
hashlock
documentation
commit
push
```

科学 simulator：

```text
calls = 0
samples = 0
```

完成后 STOP，等待 execution-readiness audit。

---

# 34. T1：Truth stage

只有审计通过并人工：

```text
M3_S25_R1_TRUTH_AUTHORIZED: YES
```

后，才允许执行唯一 truth command，例如：

```bash
python scripts/run_m3s25r1.py truth_execute
```

执行：

```text
240 discovery
→
240 confirmation
→
480/480 durable COMPLETE
→
truth assignment
→
truth-exposed inventory
→
union development pool
→
panel freeze OR PANEL-BLOCKED
→
STOP
```

---

# 35. 明确禁止事项

整个 M3-S25-R1 禁止：

```text
❌ re-run M3-S2S truth
❌ use old T1 authorization
❌ P_ref resampling
❌ candidate label peeking
❌ SHRINK-targeted candidate replacement
❌ adaptive confirmation
❌ early stop after quota appears sufficient
❌ candidate substitution after freeze
❌ truth top-up
❌ quota relaxation
❌ panel shrinkage
❌ protected reserve consumption
❌ replay of CONSUMED_INVALID unit
❌ Arm A/B activity before post-panel audit
```

---

# 36. 最终可能 verdict

R1 只允许以下终态：

### A. Success

```text
M3-S25-R1-PANEL-FROZEN
```

要求：

```text
480/480 truth COMPLETE
0 CONSUMED_INVALID
432M exact samples
union panel = 120
30/30/30/30
config diversity valid
```

随后 STOP。

### B. Panel blocked

```text
M3-S25-R1-PANEL-BLOCKED
```

truth execution 可以完全成功，但 union pool 仍无法满足冻结 panel 条件。

随后 STOP，不补采。

### C. Runtime / integrity failure

```text
M3-S25-R1-X
```

任何：

* persistence failure；
* consumed-invalid；
* frozen-input drift；
* seed mismatch；
* P_ref mismatch；
* restart inconsistency；
* budget violation；

均进入 X，STOP。

---

# 37. Scientific interpretation

本阶段的科学叙事固定为：

> M3-S2S 对 config space 的覆盖有效，但其 \(s_2\) candidate placement 仅覆盖每个合法 log-window 的低端约 12%，导致 development truth distribution 严重偏向 WIDEN，并无法形成冻结的 balanced panel。M3-S25-R1 不根据已观察到的类别标签搜索 SHRINK，而是在固定 config universe 上预注册地补齐此前未覆盖的 normalized log-\(s_2\) support。所有新 state 在 truth 前均保持 unlabeled，所有 240 state 均执行完整 discovery + confirmation；随后旧、新 truth-exposed development data 合并，在原冻结 30/30/30/30 与 config-diversity 规则下形成 panel，若仍不足则再次 PANEL-BLOCKED。

---

# 38. 当前授权状态

任务书建立时必须是：

```text
M3-S2S:
TRUTH_SAMPLING_AUTHORIZED = NO
ARM_A_AUTHORIZED = NO
ARM_B_AUTHORIZED = NO
TERMINAL = M3-S2S-PANEL-BLOCKED

M3-S25-R1:
TRUTH_AUTHORIZED = NO
ARM_A_AUTHORIZED = NO
ARM_B_AUTHORIZED = NO

R1 simulator calls = 0
R1 scientific samples = 0

VALUE / RARITY / M3-Q = BLOCKED
```

---

# 39. 当前行动

下一步只执行：

```text
1. closure-only 封存 M3-S2S
2. 创建独立 R1 branch
3. 实现本任务书
4. 生成 240-state support-completion universe
5. 完成所有 zero-sampling preflight
6. hash-lock
7. tests / full regression
8. commit + push
9. STOP
10. 等待 R1 final execution-readiness audit
```

在新的人工 truth authorization 之前：

$$
\boxed{
\text{M3-S25-R1 scientific samples}=0
}
$$

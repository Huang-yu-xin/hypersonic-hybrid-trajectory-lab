# M3-S1C：S1 Untouched Confirmation 任务书

> 项目：`Huang-yu-xin/hypersonic-hybrid-trajectory-lab`  
> 建议阶段 ID：`M3-S1C`  
> 建议分支：`feature/phase-m3-s1-untouched-confirmation`  
> 任务性质：**独立、预注册、未触碰 confirmation；只确认已经冻结的 S1，不重新开发 S1**  
> 编制日期：2026-09-06  
> 当前父结论：`PI1VNR-C`

---

## 0. 任务摘要

当前 RareTopo / M3 控制线已经完成首个有效、干净的 PI1VNR 信息实验：

- gradient direction：`0 wrong / 128 deployable trials`；
- V1（冻结的 `<=2x` online-information 架构）：
  - best safety-compliant coverage = `71.1%`；
  - unsafe = `18.75%`；
  - wrong = `0`；
  - `FULL_PASS = NO`；
  - 因此 frozen `<=2x` V1 hypothesis 已被有效否定；
- S1：
  - selected threshold = `5.4417199447782`；
  - coverage = `89.0625%`；
  - unsafe = `12.5%`；
  - wrong = `0`；
  - `FULL_PASS = YES`；
- 但 S1 目前只能称为 **development-supported**，尚未 confirmation；
- protected confirmation / reserve 当前仍未被 S1、V1 probe、threshold replay 或 gradient pilot 触碰；
- VALUE / RARITY / M3-Q 继续 BLOCKED。

因此本阶段只回答一个问题：

> **冻结后的 S1 能否在一个完全未用于 S1 development、threshold selection、V1 analysis 或 gradient pilot 的独立 confirmation panel 上再次通过既定 safety/coverage gates？**

本阶段禁止重新设计 S1、禁止重新选择阈值、禁止用 confirmation 结果调参、禁止顺带开发 V2/S2/ML。

---

# 1. Parent State：必须先审计，审计通过前禁止创建 confirmation protocol

## 1.1 当前已审计父链

当前有效远程 Git 线应至少包含以下提交链：

```text
99851ce08fef6081830b80b0b24c95545c460768
  PI1VNR preregistration

3e411921dbaa4d6ff2fc65e13f2662950e51ceec
  PI1VNR execution / PI1VNR-C

0018b0def6f7f937db649678b7cce05872317277
  PI1VNR final report / persistence seal

7b8ad90c472f58fbe22bb48401541a14fc2e6a9d
  PI1VNR docs/configs finalization
```

本任务以：

```text
7b8ad90c472f58fbe22bb48401541a14fc2e6a9d
```

作为当前已审计 base commit。

### 如果执行时 HEAD 已经前移

不得自动假定安全。

必须：

1. 比较 `7b8ad90...HEAD`；
2. 输出新增 commit / changed-file audit；
3. 确认没有改变：
   - S1 formula；
   - S1 development threshold；
   - PI1VNR gates；
   - reserve firewall；
   - reference truth；
   - persistence semantics；
   - protected confirmation；
4. 若任何科学语义发生变化：**STOP，要求人工重新审计**。

---

## 1.2 必须核对的父结论

开始任何新阶段文件之前，程序必须断言：

```text
CURRENT_SCIENTIFIC_VERDICT = PI1VNR-C

gradient_wrong = 0 / 128

V1:
  threshold-selected-on-development only
  best_safe_coverage = 0.7109375
  unsafe = 0.1875
  wrong = 0
  FULL_PASS = NO

S1:
  threshold = 5.4417199447782
  coverage = 0.890625
  unsafe = 0.125
  wrong = 0
  FULL_PASS = YES
  status = DEVELOPMENT_SUPPORTED
  confirmed = NO

protected_confirmation_touched = NO

VALUE = BLOCKED
RARITY = BLOCKED
M3-Q = BLOCKED
```

任一不一致：

```text
AUDIT FAIL
STOP
NO SIMULATOR CALL
```

---

# 2. 冻结的 S1 定义：本阶段绝对不得修改

## 2.1 S1 formula

继承：

```text
configs/phase_m3pi1vnr/m3pi1vnr_s1_contract.json
```

冻结公式：

$$
S_1
=
\frac{|\hat g|}
{(CI_{\rm high}-CI_{\rm low})/(2\times1.959963984540054)}
$$

等价地，在 CI 确实对应标准正态 95% 区间时：

$$
S_1 \approx \frac{|\hat g|}{SE(\hat g)}.
$$

冻结属性：

```text
same_gradient_data = true
```

即：

> S1 只能使用 gradient trial 已有的数据，不运行任何额外 finite-action probe。

---

## 2.2 冻结的 action sign mapping

继承 PI1VNR gradient contract：

```text
g_hat < 0  => WIDEN
g_hat > 0  => SHRINK
```

不得改符号、不得添加第三种 action、不得根据 confirmation truth 覆盖 sign。

---

## 2.3 冻结的 S1 threshold

本 confirmation **不进行 threshold search**。

唯一允许使用的主阈值：

$$
\boxed{
\tau_{S1}=5.4417199447782
}
$$

决策规则：

```text
if S1 >= 5.4417199447782:
    DEPLOY gradient-selected action
else:
    ABSTAIN
```

禁止：

- midpoint search；
- deploy-all sentinel；
- abstain-all sentinel search；
- 根据 confirmation data 最大化 coverage；
- 根据 confirmation data 压 unsafe；
- 根据 confirmation data 重新 tie-break；
- post-hoc rounding threshold；
- 使用 confirmation 结果生成“更合适的 S1 阈值”。

任何此类行为都会把 confirmation 重新变成 development。

---

# 3. Primary Hypothesis 与 Verdict Contract

## 3.1 Primary confirmation question

冻结假设为：

> **S1 在 untouched confirmation panel 上，使用 development 阶段已经选定的固定阈值 `5.4417199447782`，是否继续满足原有的 deployment coverage 与 safety gates？**

---

## 3.2 冻结 primary gates

继承 PI1VNR：

$$
\mathrm{Coverage}\ge 0.75
$$

$$
\mathrm{WrongDirectionRate}\le 0.05
$$

$$
\mathrm{Unsafe}_{ND}\le 0.20
$$

其中：

### Deployable states

truth ∈：

```text
WIDEN
SHRINK
```

### Non-deployable states

truth ∈：

```text
HOLD
AMBIGUOUS
```

在本阶段统一进入 `ND` safety stratum。

---

## 3.3 Primary metrics

假设 confirmation panel 为：

```text
8 W
8 S
8 ND
```

每个 state：

```text
8 independent fresh replicates
```

则：

```text
W/S deployable trials = 16 * 8 = 128
ND trials             =  8 * 8 = 64
total trials          = 24 * 8 = 192
```

定义：

### Direction wrong rate

在所有 W/S trial 上，检查 gradient sign 对应的 action 是否与 frozen truth 一致：

$$
R_{\rm wrong}
=
\frac{
N(\text{predicted action != frozen W/S truth})
}{
128
}.
$$

注意：

> direction sanity 是 S1 deployment 之前的独立基础检查，不能只统计被 S1 deploy 的 subset。

---

### S1 coverage

在所有 W/S deployable trials 上：

$$
C_{S1}
=
\frac{
N(S_1\ge\tau_{S1})
}{
128
}.
$$

---

### ND unsafe rate

在所有 ND trials 上：

$$
U_{ND}
=
\frac{
N(S_1\ge\tau_{S1})
}{
64
}.
$$

因为 ND 的正确行为是 ABSTAIN，所以任何 S1 deployment 均计为 unsafe。

---

## 3.4 FULL_PASS

```text
S1_CONFIRM_FULL_PASS =
    (wrong_rate <= 0.05)
    AND (coverage >= 0.75)
    AND (nd_unsafe <= 0.20)
```

不得增加或删除 primary gate。

---

## 3.5 本阶段 verdict 名称

建议固定为：

### `M3-S1C-A`

```text
valid confirmation completed
AND
FULL_PASS = YES
```

允许科学表述：

> S1 passed an independent untouched confirmation under the frozen PI1VNR-derived threshold and inherited gates.

此时 S1 可从：

```text
DEVELOPMENT_SUPPORTED
```

升级为：

```text
CONFIRMED
```

但仍不得自动声称：

- population-universal；
- deployment-safe in every regime；
- economic/value benefit 已证；
- RARITY 已通过；
- M3-Q 已授权。

---

### `M3-S1C-B`

```text
valid confirmation completed
AND
FULL_PASS = NO
```

这是**有效负结果**，不是 infrastructure failure。

科学结论：

> S1 development result did not independently confirm under the frozen threshold/gates.

此时：

- 不得在同一 confirmation panel 调 threshold 后重新判；
- 不得挑 subset；
- 不得 same-stage rerun；
- S1 回到“development signal not independently confirmed”；
- 后续若需要重新设计 S2/ML，必须进入新 development stage。

---

### `M3-S1C-X`

出现任一科学完整性失败：

- scientific sampling 已开始，但 trial 无 durable COMPLETE；
- seed collision；
- reserve contamination；
- panel substitution；
- threshold changed；
- frozen config changed after start；
- result/schema/hash 无法验证；
- scientific trial 被非法 replay；
- truth leakage 进入 S1 computation；
- 其他使 confirmation 不再独立/可恢复的问题。

处理：

```text
STOP
NO SAME-STAGE REPLAY
NO SCIENTIFIC VERDICT
```

---

# 4. Confirmation Panel：24-state untouched balanced panel

## 4.1 当前 reserve firewall

PI1VNR closeout 记录：

```text
protected reserve states = 42
panel overlap = 0
UC2R protected confirmation untouched
```

而 PI1VNR fresh development panel 使用：

```text
8 W / 8 S / 8 ND
```

在创建本阶段 panel 前，必须重新执行 live reserve audit。

---

## 4.2 预期剩余 reserve composition

根据 PI1VNR preregistered fresh eligible pool：

```text
W  = 18
S  = 21
ND = 27
```

减去 development panel：

```text
8 W
8 S
8 ND
```

理论预期剩余：

```text
W  = 10
S  = 13
ND = 19
total = 42
```

**必须通过 live manifest / frozen reference records 实际核对。**

不得仅凭本任务书数字直接生成 panel。

若实际不是上述 composition：

```text
STOP
produce discrepancy report
NO SIMULATOR CALL
```

---

## 4.3 Confirmation panel size

冻结目标：

```text
8 W
8 S
8 ND
= 24 states
```

原因：

1. 与 PI1VNR development panel 完全同规模；
2. primary metric denominator 可直接保持：
   - 128 deployable trials；
   - 64 ND trials；
3. reserve 中预期三类均足够；
4. confirmation 后仍保留：

```text
42 - 24 = 18 protected states
```

供后续真正独立阶段使用。

---

## 4.4 Panel selection 禁止使用的信息

选择 confirmation panel 时严禁读取或计算：

- S1；
- `g_hat`；
- gradient CI / SE；
- V1；
- finite-action probe；
- current controller output；
- development error pattern；
- theory descriptors 与 S1 success/failure 的关系；
- ML feature；
- 任何基于 “这个 state 看起来更容易/更难确认 S1” 的指标。

Panel selection 只能使用 **在 S1 development 之前已经冻结或独立获得的元数据**，例如：

- protected-reserve membership；
- frozen high-budget truth stratum；
- `config_id`；
- frozen `state_id`；
- frozen state parameter metadata；
- prior exposure flags。

---

## 4.5 Deterministic selection rule

为防止人工挑样本，panel 必须由预注册 deterministic procedure 产生。

建议规则：

### 第一级：stratify by truth

```text
WIDEN       -> choose 8
SHRINK      -> choose 8
HOLD/AMB    -> choose 8 as ND
```

### 第二级：maximize physical-config diversity

在每个 stratum 内：

1. 优先每个 `config_id` 只取 1 个 state；
2. 先最大化 unique config count；
3. 若不足 8，再允许同 config 的第二个 state；
4. 不允许依据 S1 / gradient / V1 信息破平局。

### 第三级：canonical tie-break

剩余 tie：

```text
canonical sort by:
(config_id, state_id)
```

或使用一个在 preregistration 中写死的 hash-based rank：

```text
rank = SHA256(
    "M3-S1C-PANEL-V1|" + config_id + "|" + state_id
)
```

然后按字节序选择最小 hash。

二者只能选择一个，并在 simulator call 前冻结。

建议使用 hash-based rank，减少人为排列影响。

---

## 4.6 Panel artifacts

至少生成：

```text
configs/phase_m3s1c/m3s1c_panel.json
results/phase_m3s1c/preflight/m3s1c_reserve_audit.csv
results/phase_m3s1c/preflight/m3s1c_panel.csv
results/phase_m3s1c/preflight/m3s1c_panel_overlap_audit.json
```

panel JSON 必须包含：

```text
state_id
config_id
truth
stratum
source_reference_artifact
source_reference_hash
selection_rank
```

但 **execution code 不得通过 truth 字段参与 S1 score 或 action computation**。

最好将：

```text
execution panel metadata
```

与：

```text
sealed truth evaluation table
```

在代码路径上分离。

---

# 5. Freshness / Exposure Firewall

每个 candidate confirmation state 必须检查：

```text
not in PI1VNR development panel
not in PI1VN partial run
not in PI1V Attempt-2
not in gradient pilot
not in V1 probe
not in S1 threshold search
not in any S1 diagnostic
not in any previous confirmation
```

需要生成：

```text
M3_S1C_Exposure_Audit.md
m3s1c_exposure_audit.json
```

每个 state 输出 exposure bitset。

任何 bit 非零：

```text
candidate is ineligible
```

如果最终无法凑齐严格的 `8/8/8`：

```text
STOP
DO NOT silently reduce panel size
DO NOT replace with development states
DO NOT relax freshness rules
```

---

# 6. Fresh Seed Contract

## 6.1 禁止 seed reuse

本阶段所有 scientific seeds 必须：

- 与 PI1VN 全部 retired seeds 不重合；
- 与 PI1VNR development seeds 不重合；
- 与 gradient pilot seeds 不重合；
- 与 V1 probe seeds 不重合；
- 与历史 WCF/WA/CF/SF/PI/UC confirmation streams 不重合。

---

## 6.2 新 namespace

建议：

```text
M3-S1C-GRAD
```

每个 24 states × 8 replicates 生成独立 seed。

总计：

```text
192 fresh gradient seeds
```

生成后创建：

```text
configs/phase_m3s1c/m3s1c_seeds.json
results/phase_m3s1c/preflight/m3s1c_seed_collision_audit.json
```

audit 必须：

```text
planned = 192
unique = 192
historical_collision = 0
```

否则：

```text
STOP
```

---

# 7. Scientific Budget：只运行 gradient，不运行 V1 probe

继承 PI1VNR gradient protocol：

```text
alpha_p = 0.5
batches = 20
replicates = 8
samples_per_trial = 20,000
```

总 scientific gradient budget：

$$
24\times8\times20{,}000
=
3{,}840{,}000
$$

即：

```text
3.84M samples
```

本阶段：

```text
finite-action BASE probe       = 0
finite-action selected probe   = 0
V1 samples                     = 0
```

不得因为某个 state 接近 S1 threshold 而追加 samples。

不得 sequentially top-up。

每个 trial 的预算必须相同且预注册。

---

# 8. Persistence / Path Hardening：完全继承 PI1VNR

不得回退到旧 persistence。

必须继承：

```text
src/hyptraj/m3wa1r/persistence.py
```

及 PI1VNR path hardening。

冻结 durable order：

```text
1. construct bounded paths
2. validate full path lengths
3. verify destination preconditions
4. durable STARTED ledger
5. gradient calculation
6. [NO finite-action probe in S1C]
7. build canonical non-circular payload
8. schema validate
9. compute hashes
10. temp write
11. flush + fsync
12. atomic rename
13. fsync parent directory
14. verify final durable record/hash
15. ledger COMPLETE
```

---

## 8.1 Failure rule

只要：

```text
scientific sampling started
AND
durable COMPLETE not obtained
```

立即：

```text
CONSUMED_INVALID += 1
M3-S1C-X
STOP
NO REPLAY
```

禁止：

- rerun same seed；
- rerun same state/replicate；
- 删除失败记录后假装未发生；
- 用剩余 191 trials 计算正式 confirmation；
- 用 partial results 调 protocol。

partial artifacts 只能：

```text
DIAGNOSTIC_ONLY
```

---

## 8.2 Pre-simulator failure

如果失败发生在任何 scientific simulator call 之前，例如：

- path too long；
- malformed config；
- schema error；
- destination collision；
- missing directory；
- seed manifest mismatch；

则：

```text
NO SCIENTIFIC CONSUMPTION
```

可以修复工程问题，但：

1. 必须记录 incident；
2. 若修改了 frozen scientific config / panel / seeds / S1 contract，则重新 hash-lock；
3. 再次通过完整 preflight；
4. scientific start gate 重新授权。

---

# 9. Pre-registration Artifacts：任何 simulator call 前必须全部 hash-lock

建议新增：

```text
docs/phase_m3s1c/
configs/phase_m3s1c/
results/phase_m3s1c/
```

必须至少创建：

```text
docs/phase_m3s1c/M3_S1C_Task.md
docs/phase_m3s1c/M3_S1C_Preregistration.md
docs/phase_m3s1c/M3_S1C_Parent_Audit.md
docs/phase_m3s1c/M3_S1C_Reserve_Firewall_Audit.md
docs/phase_m3s1c/M3_S1C_Exposure_Audit.md
docs/phase_m3s1c/M3_S1C_Seed_Audit.md
docs/phase_m3s1c/M3_S1C_Path_Preflight.md
docs/phase_m3s1c/M3_S1C_Human_Approval.md
```

configs：

```text
configs/phase_m3s1c/m3s1c_s1_contract.json
configs/phase_m3s1c/m3s1c_gates.json
configs/phase_m3s1c/m3s1c_gradient_protocol.json
configs/phase_m3s1c/m3s1c_panel.json
configs/phase_m3s1c/m3s1c_seeds.json
configs/phase_m3s1c/m3s1c_persistence.json
configs/phase_m3s1c/m3s1c_secondary_analysis.json
```

hash manifest：

```text
results/phase_m3s1c/preflight/m3s1c_prereg_hashes.json
```

必须包含每个 prereg/config artifact 的：

```text
relative_path
sha256
size_bytes
```

并记录：

```text
parent_git_sha
python/version if relevant
scientific code module hashes
persistence module hash
```

---

# 10. Human Approval Gate

在以下全部 PASS 后：

```text
PARENT_AUDIT       PASS
RESERVE_FIREWALL   PASS
EXPOSURE_AUDIT     PASS
PANEL_AUDIT        PASS
SEED_AUDIT         PASS
PATH_PREFLIGHT     PASS
SCHEMA_PREFLIGHT   PASS
PREREG_HASH_LOCK   PASS
```

写：

```text
M3_S1C_Human_Approval.md
```

初始状态必须是：

```text
EXECUTION_AUTHORIZED = NO
```

**Codex 在完成 preregistration package 后必须停止。**

不得自己把：

```text
NO -> YES
```

必须等待人工明确授权。

只有收到明确授权，才允许开始第一个 durable STARTED trial。

---

# 11. Execution Procedure

人工授权后：

## Step 1 — Reverify frozen hashes

运行前重新读取：

```text
m3s1c_prereg_hashes.json
```

要求：

```text
hash_mismatch = 0
```

---

## Step 2 — Reverify empty execution destination

必须防止旧 trial artifacts 混入。

要求：

```text
COMPLETE = 0
STARTED = 0
CONSUMED_INVALID = 0
```

---

## Step 3 — Execute canonical ordering

建议固定：

```text
panel order by frozen selection_rank
then replicate_id = 0..7
```

不得运行过程中按结果改变顺序。

---

## Step 4 — Trial computation

每 trial：

1. durable STARTED；
2. 读取 state execution metadata；
3. 运行 frozen 20k gradient estimator；
4. 得到：
   - `g_hat`
   - `ci_low`
   - `ci_high`
5. 计算：

$$
S_1
=
\frac{|\hat g|}
{(CI_{\rm high}-CI_{\rm low})/(2\times1.959963984540054)}
$$

6. action：

```text
g_hat < 0 => WIDEN
g_hat > 0 => SHRINK
```

7. deployment：

```text
S1 >= 5.4417199447782 => DEPLOY
else                   => ABSTAIN
```

8. durable COMPLETE。

执行代码不得在 trial 时读取 sealed truth label 来影响 3–7。

---

# 12. Evaluation：只有 192/192 durable COMPLETE 后才允许 unseal truth

要求：

```text
planned = 192
COMPLETE = 192
CONSUMED_INVALID = 0
duplicate = 0
missing = 0
hash_fail = 0
```

只有此时：

```text
UNSEAL EVALUATION TRUTH
```

再计算 primary metrics。

---

# 13. Primary Report

必须生成：

```text
results/phase_m3s1c/summary/m3s1c_primary_metrics.json
results/phase_m3s1c/summary/m3s1c_trial_table.csv
results/phase_m3s1c/summary/m3s1c_state_table.csv
docs/phase_m3s1c/M3_S1C_Final_Report.md
```

至少报告：

```text
total trials
complete trials
consumed-invalid trials

direction:
  total deployable trials
  wrong count
  wrong rate

S1:
  fixed threshold
  deployed W count / total W
  deployed S count / total S
  overall deployable coverage
  deployed ND count / total ND
  ND unsafe rate

gates:
  wrong <= 5%
  coverage >= 75%
  unsafe <= 20%

FULL_PASS
FINAL VERDICT
```

---

# 14. Secondary Statistical Reporting：只报告，不改变 primary verdict

建议为三项比例附加：

- Wilson 95% CI；
- exact binomial 95% CI。

但必须明确：

```text
CI = descriptive / uncertainty reporting only
```

不得 post-hoc 添加：

```text
"lower CI must exceed gate"
```

之类的新 primary gate。

如果以后希望把 CI gate 作为标准，必须另开新 stage preregister。

---

# 15. Theory-Mechanism Secondary Analysis

本部分源自当前 grazing-curvature 理论证明线。

## 15.1 目的

只回答：

> S1 residual failure / abstention 是否在理论预测的 grazing / multimodal difficult geometry 附近富集？

本分析：

```text
SECONDARY
NON-VERDICT
NO THRESHOLD TUNING
NO PANEL SELECTION
```

---

## 15.2 可预注册 theory descriptors

只有在现有 simulator / state metadata 中存在**无歧义映射**时才计算。

候选：

$$
G=\beta\kappa
$$

若 canonical mapping 成立，可进一步报告：

$$
c=G-1
$$

$$
a=
\frac{\sqrt{2c}}{1+c}\beta
$$

以及 transverse criticality：

$$
h\lambda_j.
$$

proposal geometry 若已有明确量，可报告类似：

$$
\frac{a}{s_{\rm proposal}}.
$$

---

## 15.3 严禁事项

如果实际 hypersonic state 中：

```text
beta
kappa
lambda
a
```

没有已经定义好的对应关系：

```text
mark NOT_AVAILABLE
```

不得为 confirmation 临时发明 proxy。

不得查看 confirmation outcomes 后再决定用哪个 curvature 指标。

不得因为理论指标显示某些 state “特殊” 而移除它们。

---

## 15.4 推荐只做的分析

如果 descriptors available：

- 按 `S1 deploy / abstain` 报 descriptor 分布；
- 按 `correct-safe / unsafe / missed-deploy` 报描述统计；
- 绘制 S1 score vs preregistered descriptor；
- 不做 confirmation-data-driven feature selection；
- 不将 secondary p-value 用于 S1C-A/B verdict。

结果可以为后续：

```text
ML-0 / S2 / RARITY
```

提供 hypothesis，但不能反向修改本阶段。

---

# 16. 禁止在本阶段进行的工作

本阶段 **DO NOT**：

```text
restart D2/D3/UC/PI/SF/CF/WA/WCF/PI1VNR
```

不得：

1. 重新使用 PI1V Attempt-2 作为科学证据；
2. 重新使用 PI1VN partial 136 durable trials 调阈值；
3. 重新搜索 S1 threshold；
4. 修改 S1 formula；
5. 再跑 V1 probe；
6. 构造 V2；
7. 构造 S2；
8. 开始 ML training；
9. 解锁 VALUE；
10. 解锁 RARITY；
11. 解锁 M3-Q；
12. 从 confirmation panel 中删除“不好看”的 state；
13. 在结果出来后追加 samples；
14. 用 partial confirmation 结果选择后续 confirmation states；
15. 把 confirmation FAIL 写成 infrastructure failure；
16. 把 confirmation PASS 写成 universal population claim。

---

# 17. Test Requirements

新阶段至少新增以下测试类别。

## 17.1 Contract tests

验证：

- S1 formula hash；
- threshold exact equality；
- gates exact equality；
- sign mapping；
- 20k budget；
- 8 replicates；
- no V1 probe。

---

## 17.2 Panel tests

验证：

```text
24 unique states
8 W
8 S
8 ND
```

以及：

- no development overlap；
- no historical exposure；
- expected config diversity selection；
- canonical selection reproducible；
- panel SHA deterministic。

---

## 17.3 Seed tests

验证：

```text
192 unique
0 historical collision
deterministic manifest
```

---

## 17.4 Truth-firewall tests

测试 execution function：

- 不接受 truth 作为 score/action input；
- truth 只能在 completed evaluation stage 解封；
- execution artifact 中不得出现可改变 action 的 truth branch。

---

## 17.5 Persistence tests

至少覆盖：

- STARTED durable before simulator；
- atomic rename；
- fsync path；
- hash verification；
- failure after sampling => consumed-invalid；
- no replay；
- path bounds；
- duplicate destination；
- interrupted temp file；
- corrupted final record。

---

## 17.6 Verdict tests

构造 synthetic summary：

- all gates pass => `S1C-A`；
- coverage fail => `S1C-B`；
- unsafe fail => `S1C-B`；
- wrong fail => `S1C-B`；
- persistence invalid => `S1C-X`；
- incomplete 191/192 => no A/B verdict。

---

# 18. Commit Strategy

禁止把 preregistration 与 execution 混成一个 commit。

建议：

## Commit 1 — stage skeleton / audit tooling

```text
M3-S1C scaffold: parent/reserve/exposure audit and confirmation-only contracts
```

---

## Commit 2 — preregistration lock

包含：

- panel；
- seeds；
- contracts；
- preflight；
- hash manifest；
- human approval = NO。

建议 message：

```text
M3-S1C preregistration: untouched 8W/8S/8ND confirmation panel, frozen S1 threshold/gates, fresh 192-seed stream, persistence/path preflight, hash lock
```

**Commit 2 后 STOP，等待人工授权。**

---

## Commit 3 — execution

只有人工授权后。

建议：

```text
M3-S1C execution: 192/192 frozen S1 confirmation trials [result filled after run]
```

---

## Commit 4 — final report / regression

```text
M3-S1C final report: [S1C-A or S1C-B], persistence seal, full regression
```

---

# 19. Acceptance Checklist

## A. Audit

- [ ] base ancestry includes PI1VNR audited chain
- [ ] current scientific verdict = PI1VNR-C
- [ ] V1 remains validly rejected only for frozen <=2x design
- [ ] S1 remains development-supported, not confirmed
- [ ] protected confirmation remains untouched
- [ ] VALUE / RARITY / M3-Q remain BLOCKED

## B. S1 freeze

- [ ] formula unchanged
- [ ] sign mapping unchanged
- [ ] threshold exactly `5.4417199447782`
- [ ] gates unchanged
- [ ] no threshold search code reachable in confirmation

## C. Panel

- [ ] 42 reserve states audited
- [ ] expected reserve composition verified
- [ ] 24 selected
- [ ] 8 W
- [ ] 8 S
- [ ] 8 ND
- [ ] zero prior scientific exposure
- [ ] deterministic selection
- [ ] panel hash locked

## D. Seeds

- [ ] 192 fresh
- [ ] all unique
- [ ] zero historical collision
- [ ] seed manifest hash locked

## E. Infrastructure

- [ ] path preflight 192/192 PASS
- [ ] persistence tests PASS
- [ ] STARTED-before-simulator verified
- [ ] no replay verified
- [ ] truth firewall verified

## F. Authorization

- [ ] prereg artifacts committed
- [ ] prereg hashes locked
- [ ] Human Approval initially NO
- [ ] explicit human authorization obtained before trial 1

## G. Execution

- [ ] 192/192 durable COMPLETE
- [ ] 0 consumed-invalid
- [ ] 0 duplicate
- [ ] 0 missing
- [ ] 0 hash mismatch
- [ ] total sample budget = 3.84M
- [ ] no V1 probe

## H. Verdict

- [ ] wrong direction computed on all 128 W/S trials
- [ ] coverage computed on all 128 W/S trials
- [ ] unsafe computed on all 64 ND trials
- [ ] no threshold retune
- [ ] A/B/X verdict follows frozen logic exactly

---

# 20. Stop Conditions

任何一个发生立即停止：

```text
parent audit mismatch
reserve count/composition mismatch
protected reserve exposure detected
panel cannot satisfy frozen 8/8/8 design
seed collision
prereg hash mismatch
path preflight fail after scientific start
truth leakage
threshold mutation
scientific config mutation after authorization
sampling started + no durable COMPLETE
unexpected replay
missing trial
duplicate scientific trial
result hash corruption
```

若尚未 scientific sampling：

```text
fix engineering issue
re-audit
re-hash
re-authorize
```

若 scientific sampling 已经开始：

```text
M3-S1C-X
STOP
NO SAME-STAGE REPLAY
```

---

# 21. Deliverables

本阶段最终必须交付：

```text
docs/phase_m3s1c/M3_S1C_Task.md
docs/phase_m3s1c/M3_S1C_Preregistration.md
docs/phase_m3s1c/M3_S1C_Parent_Audit.md
docs/phase_m3s1c/M3_S1C_Reserve_Firewall_Audit.md
docs/phase_m3s1c/M3_S1C_Exposure_Audit.md
docs/phase_m3s1c/M3_S1C_Seed_Audit.md
docs/phase_m3s1c/M3_S1C_Path_Preflight.md
docs/phase_m3s1c/M3_S1C_Human_Approval.md
docs/phase_m3s1c/M3_S1C_Secondary_Theory_Analysis.md
docs/phase_m3s1c/M3_S1C_Final_Report.md

configs/phase_m3s1c/m3s1c_s1_contract.json
configs/phase_m3s1c/m3s1c_gates.json
configs/phase_m3s1c/m3s1c_gradient_protocol.json
configs/phase_m3s1c/m3s1c_panel.json
configs/phase_m3s1c/m3s1c_seeds.json
configs/phase_m3s1c/m3s1c_persistence.json
configs/phase_m3s1c/m3s1c_secondary_analysis.json

results/phase_m3s1c/preflight/*
results/phase_m3s1c/trials/*
results/phase_m3s1c/summary/m3s1c_primary_metrics.json
results/phase_m3s1c/summary/m3s1c_trial_table.csv
results/phase_m3s1c/summary/m3s1c_state_table.csv
```

---

# 22. 本阶段结束后的路线

## 如果 `M3-S1C-A`

允许更新：

```text
S1:
  development-supported -> CONFIRMED
```

然后单独召开 next-stage decision。

优先建议：

```text
ML-0:
  formalize DEPLOY/ABSTAIN learning problem
  build larger independent state-level development dataset
  compare confirmed S1 vs logistic / GBDT / small MLP
```

是否解锁 VALUE / RARITY / M3-Q：

> **不得由 S1C-A 自动推断。必须依据项目既有 gating rules 单独审计后决定。**

---

## 如果 `M3-S1C-B`

结论：

```text
S1 NOT CONFIRMED
```

不得在 confirmation panel 上修 S1。

下一步应新建独立 development stage，可能方向：

```text
S2 / theory-informed deployment score / ML-0
```

confirmation panel 自此视为 exposed，不再用于未来 confirmation。

---

## 如果 `M3-S1C-X`

不产生 S1 scientific verdict。

必须先做 incident / quarantine / reserve-retirement accounting，再决定是否有足够 untouched evidence 建立一个**新 stage ID** 的 confirmation。

---

# 23. Codex 首轮执行指令

Codex 收到本任务书后，第一轮只执行到 preregistration freeze：

```text
1. live Git audit
2. parent PI1VNR-C audit
3. protected reserve audit
4. exposure audit
5. deterministic 8W/8S/8ND panel construction
6. fresh seed construction + collision audit
7. frozen S1/gates/gradient/persistence configs
8. path/schema/persistence preflight
9. tests
10. prereg hash manifest
11. preregistration commit
12. Human Approval = NO
13. STOP
```

**禁止在首轮执行任何 scientific simulator trial。**

向人工汇报：

```text
M3-S1C PREREG STATUS:
PASS / FAIL

PARENT:
...

RESERVE:
42 audited
W/S/ND composition = ...
exposure overlap = ...

CONFIRMATION PANEL:
8 W / 8 S / 8 ND
24 states
panel sha256 = ...

S1:
formula sha256 = ...
threshold = 5.4417199447782
gates = coverage>=0.75, wrong<=0.05, unsafe<=0.20

SEEDS:
192 planned
192 unique
0 collision
seed manifest sha256 = ...

PATH/PERSISTENCE:
PASS / FAIL
max path = ...
tests = ...

PREREG:
hash manifest = ...
commit = ...

EXECUTION_AUTHORIZED:
NO

NEXT:
Await explicit human authorization.
```

---

# 24. Source-of-truth anchors

本任务书继承当前已审计 PI1VNR artifacts，执行时必须从 Git 实际文件重新读入并验证 hash，不允许仅复制本文数值：

```text
configs/phase_m3pi1vnr/m3pi1vnr_s1_contract.json
configs/phase_m3pi1vnr/m3pi1vnr_gates.json
configs/phase_m3pi1vnr/m3pi1vnr_threshold_contract.json
configs/phase_m3pi1vnr/m3pi1vnr_gradient_protocol.json
configs/phase_m3pi1vnr/m3pi1vnr_persistence.json
configs/phase_m3pi1vnr/m3pi1vnr_panel.json

docs/phase_m3pi1vnr/M3_PI1VNR_S1_Comparator.md
docs/phase_m3pi1vnr/M3_PI1VNR_Reserve_Firewall_Audit.md
docs/phase_m3pi1vnr/M3_PI1VNR_Final_Report.md
```

以及最新 `PROJECT_MASTER_HANDOFF` Appendix AH–AZ。

---

# 25. 最终原则

本阶段的核心不是“让 S1 再过一次”。

而是：

> **用一次不可调参、不可挑样本、不可回放、与 development 严格隔离的独立实验，判断 S1 的 development success 是否能够复现。**

因此：

$$
\boxed{
\text{independence}
>
\text{making the result look good}
}
$$

如果 S1 真正有效，冻结的 S1 应该在 untouched panel 上自己通过。

如果没有通过，一个干净的 `S1C-B` 比经过 post-hoc 修补得到的“PASS”更有科学价值。

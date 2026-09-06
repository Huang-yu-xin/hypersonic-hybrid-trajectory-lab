# M3-S2S：Instrumented Fresh Development Sampling 正式任务书

> 项目：`Huang-yu-xin/hypersonic-hybrid-trajectory-lab`  
> 阶段 ID：`M3-S2S`  
> 建议分支：`feature/phase-m3-s2s-instrumented-fresh-development`  
> 父阶段：`M3-S2F-R`  
> 父远端 commit：`86ad583a96806099e9b57f46758584fa9ba790b0`  
> 阶段性质：**fresh development sampling + rich online instrumentation**  
> 本阶段不是 confirmation。  
> 剩余 18 个 protected reserve：**永久保持封存，不参与本阶段任何 sampling / feature / truth / model activity。**

---

# 0. 当前科学状态

本阶段必须以以下已封存结论为唯一父状态：

```text
M3-S1C:
  verdict = M3-S1C-B
  S1 untouched confirmation failed
  wrong = 0/128
  coverage = 0.828125
  ND unsafe = 0.296875
  failure concentrated in AMBIGUOUS

M3-ML0:
  verdict = M3-ML0-C
  48 states / 384 trials
  config-grouped nested CV
  no safety-compliant candidate
  current aggregate online feature family insufficient

M3-S2F:
  verdict = M3-S2F-R
  batch/bootstrap stability hypothesis = UNTESTED
  recoverability barrier = TRUE
  384/384 Tier-A trials lack the internal information needed to test
  bootstrap/batch stability without simulator replay

existing Tier-A:
  48 exposed states
  384 exposed trials
  dataset sha256 =
  f5f684fdb693123c878ebed567a29a98a80cffca774849d85a8204320a76cedd

protected reserve:
  18 untouched states
  used by ML0 = 0
  used by S2F = 0

VALUE:
  BLOCKED

RARITY:
  BLOCKED

M3-Q:
  BLOCKED
```

本阶段开始前必须 live Git audit：

```text
5403e53 -> 76e99ac -> 1f4b0d1 -> 86ad583
```

并确认：

```text
M3-S2F-R remains the current valid scientific state.
```

---

# 1. 核心科学问题

S1 只保留：

$$
S_1 = \frac{|\hat g|}{SE(\hat g)}.
$$

M3-S2F-R 已确认：当前 artifacts 只持久化 aggregate `g_hat`、CI、
`ESS_grad` 等摘要，而真正生成 uncertainty 的 estimator 内部结构在写出时被丢弃。

当前真实 estimator 层级必须明确区分：

```text
STATE
└── OUTER TRIAL REPLICATE
    └── simulator samples (20,000)
        └── per-sample contribution / sufficient-statistic vectors
            └── stratified bootstrap
                └── bootstrap draws
```

禁止继续混用以下概念：

```text
outer trial replicate
bootstrap replicate / bootstrap draw
batch
```

本阶段要检验的核心假设是：

$$
\boxed{
\text{AMBIGUOUS deployment risk may be encoded in the internal}
\atop
\text{shape / influence / stability structure of the gradient estimator}
}
$$

而不是简单地：

```text
“换一个更大的 ML 模型”
```

---

# 2. 本阶段的三个独立授权门

M3-S2S 不允许“一次授权后自动跑完所有采样”。

必须分为：

```text
GATE T — Truth Panel establishment
GATE A — Center-gradient rich-instrumentation arm
GATE B — Optional ±Δ local-shape arm
```

建议统一审批文件：

```text
docs/phase_m3s2s/M3_S2S_Human_Approval.md
```

初始必须为：

```text
TRUTH_SAMPLING_AUTHORIZED: NO
ARM_A_AUTHORIZED: NO
ARM_B_AUTHORIZED: NO
```

Codex 不得自行把任何 `NO` 改成 `YES`。

---

# 3. 首轮 Codex 只执行 preregistration freeze

**第一次收到本任务书时，只允许执行步骤 1–16 的 preregistration 工作。**

首轮：

```text
scientific simulator calls = 0
scientific samples = 0
```

完成：

- parent audit；
- reserve firewall；
- controller-exposure exclusion manifest；
- truth-source audit；
- fresh candidate inventory；
- instrumentation schema；
- seed namespace；
- path/persistence preflight；
- exact budget calculation；
- Arm-A protocol；
- Arm-B candidate protocol；
- tests；
- hash-lock；
- prereg commit；
- push remote；

然后：

```text
STOP
WAIT FOR HUMAN AUTHORIZATION
```

---

# 4. Protected Reserve Firewall：18 个 state 永久禁止使用

必须从 parent source-of-truth 重建：

```text
remaining protected reserve = 18
```

输出：

```text
results/phase_m3s2s/preflight/m3s2s_protected_reserve_18.csv
docs/phase_m3s2s/M3_S2S_Reserve_Firewall_Audit.md
```

只允许字段：

```text
state_id
config_id
source_hash
protected = true
```

对这 18 个 state 禁止：

```text
truth sampling
gradient sampling
S1 calculation
feature extraction
local-shape evaluation
model scoring
plotting
error analysis
candidate selection
threshold selection
```

任何 overlap：

```text
M3-S2S-X
STOP
```

---

# 5. Freshness / Exclusion Manifest

新 development panel 必须排除所有已被 controller / comparator / policy 使用过的 state。

至少排除：

```text
PI1V attempts
PI1VN partial / retired
PI1VNR development panel
S1C confirmation panel
ML0 Tier-A states
all gradient pilots
all V1 probes
all S1 threshold-search / diagnostic panels
all prior controller confirmation panels
18 protected reserve
```

允许：

> 仅用于建立 frozen truth 的 truth/reference-only characterization，

前提是没有：

```text
g_hat controller result
S1
V1
r_hat policy result
deploy / abstain
selected_action from experimental policy signal
```

输出：

```text
configs/phase_m3s2s/m3s2s_exclusion_manifest.json
docs/phase_m3s2s/M3_S2S_Exposure_Firewall_Audit.md
```

Unknown candidate-bearing artifact：

```text
UNRESOLVED
=> candidate ineligible
=> STOP if quota cannot be met
```

禁止 filename-only classification。

---

# 6. Fresh Development Panel 目标

Primary target：

```text
120 independent states
>= 24 unique physical configs
```

目标 truth composition：

```text
30 WIDEN
30 SHRINK
30 HOLD
30 AMBIGUOUS
```

即：

```text
60 DEPLOYABLE
60 NON_DEPLOYABLE
```

目的：

> AMBIGUOUS 必须成为具有独立统计力量的研究层，而不是 ND 中的小子类。

---

# 7. Panel selection rule

Panel selection 必须只使用：

```text
freshness eligibility
frozen truth stratum
config_id
state_id
canonical hash rank
```

禁止使用：

```text
g_hat
S1
V1
gradient stability
difficulty
ML score
theory score
future outcome
manual preference
```

---

## 7.1 Config-diversity round rule

继承 S1C 的 round-based config diversity：

```text
Within each truth stratum:

1. group eligible states by config_id;
2. within each config, sort by frozen SHA256 rank;
3. round 1 takes at most the 1st state per config;
4. round 2 takes at most the 2nd state per config;
5. round k takes at most the k-th state per config;
6. within each round order only by frozen hash rank;
7. stop exactly when the stratum quota reaches 30.
```

建议 rank：

```text
SHA256(
  "M3-S2S-PANEL-V1|" + config_id + "|" + state_id
)
```

必须在任何 truth/controller sampling 前冻结。

---

# 8. Truth Source Audit：优先复用已有 truth-reference-only inventory

在进行任何新 truth sampling 前，Codex 必须先审计：

> 是否已经存在足够的 **controller-unexposed、非 protected、high-budget frozen truth states**。

允许来源包括：

```text
truth/reference inventories
reference-only confirmation
P_ref characterization
corrected CF2-style truth inventory
```

前提：

```text
controller exposure = 0
truth semantics = current corrected semantics
source hash = verified
```

---

## 8.1 Case T0：已有 truth inventory 足够

如果能够得到：

```text
>=30 W
>=30 S
>=30 HOLD
>=30 AMBIGUOUS
>=24 configs overall
```

则：

```text
TRUTH_SAMPLING_REQUIRED = NO
```

直接冻结 120-state panel。

此时：

```text
truth scientific sampling budget = 0
```

然后等待 Arm A 人工授权。

---

## 8.2 Case T1：已有 truth inventory 不足

如果 quota 不足：

```text
TRUTH_SAMPLING_REQUIRED = YES
```

必须使用 repository 中**最新 corrected high-budget truth-establishment protocol**。

Codex 必须先完成：

```text
exact truth contract audit
```

找到并冻结：

```text
truth estimator
BASE / WIDEN / SHRINK semantics
per-arm budgets
discovery budget
confirmation budget
noise / ambiguity thresholds
HOLD / AMBIGUOUS semantics
seed namespace
CRN semantics
retirement rule
consumed-invalid rule
```

不得自行“近似复刻”。

---

## 8.3 Truth contract 不唯一时

如果 repo 中没有一个明确的 canonical corrected truth protocol：

```text
TRUTH_CONTRACT = UNRESOLVED
STOP
NO SIMULATOR CALL
```

等待人工修订任务书。

---

# 9. Truth sampling 必须单独计算 exact budget

任务书不允许把：

```text
19.2M Arm-A gradient samples
```

误称为整个 S2S budget。

如果 `TRUTH_SAMPLING_REQUIRED = YES`：

必须在 prereg 中写出：

```text
candidate states sampled
arms/state
samples/arm
discovery total
confirmation total
maximum truth budget
retirement states
```

并给出 exact integer：

```text
TRUTH_BUDGET_MAX = ...
```

任何 placeholder：

```text
TBD
about
~N
```

均不允许进入 authorization。

---

# 10. Truth panel retirement semantics

Truth establishment 是 development evidence。

任何 state 一旦进行了新的 truth scientific sampling：

```text
state becomes development-exposed
```

即使最终没有进入 120-state primary panel，也不得未来作为 untouched confirmation state。

必须进入：

```text
m3s2s_truth_exposed_inventory
```

---

# 11. Arm A：中心 gradient + rich instrumentation

Arm A 是本阶段 primary experiment。

固定：

```text
states = 120
outer trial replicates / state = 8
samples / trial = 20,000
```

总中心 gradient budget：

$$
120 \times 8 \times 20,000
=
\boxed{19,200,000}
$$

即：

```text
ARM_A_GRADIENT_BUDGET = 19,200,000
```

禁止：

```text
top-up
extra replicate
adaptive samples/state
post-hoc retries
```

---

# 12. Arm A estimator semantics 不得改变

Arm A 必须使用与 PI1VNR / S1C 相同的：

```text
gradient estimator
alpha_p
CRN semantics
S1 formula
sign mapping
20k online sample budget
```

当前 sign mapping：

```text
g_hat < 0 => WIDEN
g_hat > 0 => SHRINK
```

Arm A 的新内容只能是：

```text
instrumentation / persistence
```

不得改变 scientific estimator。

---

# 13. Instrumentation Audit：先读真实 estimator source

Codex 必须在 prereg 时直接审计：

```text
hyptraj.m3d.adaptation.gradient_decision
```

以及实际调用链。

冻结：

```text
N_BOOTSTRAP actual value
bootstrap seed construction
per-sample contribution arrays used
strata / resampling semantics
ESS definition
event-count availability
component summaries
```

不得把：

```text
batches = 20
```

解释成：

```text
20 independent batch gradients
```

除非源码明确如此。

---

# 14. Mandatory persisted instrumentation

每个 Arm-A trial 必须保留足够信息，使以下 feature 无需 simulator replay 即可重建。

---

## 14.1 Aggregate fields

继续持久化：

```text
g_hat
g_ci_low
g_ci_high
SE_g
S1
ESS_grad
M2_hat
D_hat
responsibility_mass
s2_base
gradient_valid
seed
```

按 repo 真实字段名冻结。

---

## 14.2 Bootstrap distribution

必须持久化：

```text
bootstrap_g[0:N_BOOTSTRAP]
```

并记录：

```text
N_BOOTSTRAP
bootstrap_seed
bootstrap_method
bootstrap_schema_version
```

注意：

> bootstrap draws 不是独立 scientific trials。

禁止把 `N_BOOTSTRAP` 当 sample size 做普通独立统计推断。

---

## 14.3 Contribution / sufficient-statistic instrumentation

Codex 必须基于 estimator source 冻结**最小可重建 sufficient-statistic schema**。

如果 estimator 的 bootstrap 基于类似：

```text
a_vec
resp
sq
```

等数组，则必须：

1. 明确每个数组的定义；
2. 明确 shape；
3. 明确 dtype；
4. 明确是否 truth-free / online-available；
5. 明确其是否足以重新计算 aggregate g / bootstrap；
6. 决定持久化完整数组还是 lossless compressed sidecar。

优先原则：

> 如果未来合理的 feature 可能依赖该内部结构，则优先保存 lossless sufficient statistics，而不是再次只保存 summary。

---

## 14.4 Sidecar file

建议每 trial：

```text
trial_record.json
trial_instrumentation.npz
```

或等价的 compressed parquet / npz。

trial record 中保存：

```text
instrumentation_path
instrumentation_sha256
instrumentation_schema
instrumentation_size_bytes
```

事务 COMPLETE 前必须先验证 sidecar durable + hash。

---

# 15. Instrumentation size preflight

在任何 simulator call 前必须用 synthetic shapes 做容量预估。

输出：

```text
estimated bytes / trial
estimated Arm-A total bytes
max path length
max temp path
free disk requirement
```

要求：

```text
DISK_PREFLIGHT = PASS
```

否则：

```text
STOP
NO SCIENTIFIC SAMPLING
```

不得执行到一半才发现磁盘不够。

---

# 16. Arm-A seed protocol

新 namespace：

```text
M3-S2S-A-GRAD
```

或 repository 中 prereg 冻结的等价唯一 namespace。

要求：

```text
120 * 8 = 960 seeds
960 unique
0 collision with all historical scientific streams
```

包括：

```text
PI / PI1V / PI1VN
PI1VNR
S1C
all truth/reference streams
all probes
all previous controller streams
```

---

# 17. Arm A 可开发 feature family

Feature 定义必须在 Arm A sampling 前冻结。

---

## 17.1 Bootstrap stability

从 `bootstrap_g` 构造：

```text
boot_mean
boot_median
boot_std
boot_MAD
boot_IQR
boot_q05
boot_q25
boot_q50
boot_q75
boot_q95
boot_mean_minus_median
boot_sign_probability
boot_opposite_sign_probability
boot_zero_crossing / near-zero probability
boot_quantile_asymmetry
boot_tail_imbalance
```

如数值稳定允许：

```text
boot_skewness
boot_excess_kurtosis
```

但 skew / kurtosis 可标记为 secondary-only。

---

## 17.2 Robust-vs-classical discrepancy

定义：

```text
g_hat - boot_median
abs(g_hat - boot_median)
relative robust discrepancy
S1 vs robust significance discrepancy
```

任何 ratio 必须定义 epsilon / zero handling。

---

## 17.3 Influence / contribution concentration

仅从 online sufficient-statistics 构造：

```text
max_abs_influence_fraction
top_1pct_abs_influence_fraction
top_5pct_abs_influence_fraction
top_10pct_abs_influence_fraction
Herfindahl concentration
effective contribution count
```

具体 influence proxy 必须由 estimator algebra 推导并冻结。

禁止临时选择“看起来分得最好”的 contribution formula。

---

## 17.4 Event / ESS diagnostics

仅当 estimator source 明确在线可得：

```text
event_count
event_rate
ESS_grad
ESS_per_event
ESS_fraction
```

禁止用 high-budget truth event probability。

---

# 18. Practical Significance family

定义：

$$
M_\delta
=
\frac{|\hat g|-\delta}{SE(\hat g)}.
$$

`M_delta` 仅为 development score，不解释为 posterior probability。

δ 不得在 full dataset 上调。

候选 δ 由 inner-train 的：

```text
|g_hat| quantiles
q ∈ {0.10, 0.25, 0.40, 0.50}
```

产生。

每 outer fold：

```text
delta candidates derived from outer-train only
selection uses inner grouped OOF only
```

---

# 19. Arm A primary dataset

Primary development evidence：

```text
fresh 120 states only
```

旧：

```text
PI1VNR / S1C / ML0 Tier-A 48 states
```

只允许用于：

```text
historical baseline comparison
mechanism replication
common-feature sanity checks
```

不得参与 Arm-A primary candidate selection，因为：

- instrumentation schema 不同；
- batch/bootstrap内部信息不存在；
- 会产生 missing-by-stage leakage。

---

# 20. Statistical unit 与 CV

真正 independent unit：

```text
physical config / state
```

不是：

```text
bootstrap draw
trial row
```

Primary CV：

```text
outer = GroupKFold(5)
inner = GroupKFold(4)
group = config_id
```

前提：

```text
>=24 unique configs
```

如果 5/4 fold 的 class/config feasibility 不满足：

```text
STOP BEFORE MODELING
```

不得静默改为 random split。

---

# 21. Model hierarchy

本阶段继续限制模型复杂度。

Primary candidates：

```text
B0 = Frozen S1
B1 = ML0-style aggregate GBDT baseline
A1 = S2S-Stability Logistic
A2 = S2S-Stability GBDT
A3 = S2S-Stability + Practical-Margin Logistic
A4 = S2S-Stability + Practical-Margin GBDT
```

不允许：

```text
MLP
deep neural network
Optuna
Bayesian hyperparameter search
large XGBoost sweep
```

即使 states >= 100，也不自动授权 MLP。

---

# 22. Primary deployment objective

继续冻结：

$$
\max \mathrm{Coverage}
$$

subject to：

$$
ND\ unsafe \le 0.20
$$

以及：

$$
WrongDirection \le 0.05.
$$

direction 仍来自 gradient sign；

ML/S2 只决定：

```text
DEPLOY / ABSTAIN
```

---

# 23. Arm A primary metrics

必须报告 fresh 120-state OOF：

```text
deployable coverage
ND unsafe
HOLD unsafe
AMBIGUOUS unsafe
wrong direction
```

secondary：

```text
ROC-AUC
PR-AUC
Brier
ECE
```

---

# 24. Arm A development success criterion

## `M3-S2S-A`

至少一个 Arm-A candidate：

```text
coverage >= 0.75
ND unsafe <= 0.20
wrong <= 0.05
AMBIGUOUS unsafe < 0.25
```

并满足至少一个 improvement：

```text
coverage gain vs aggregate GBDT >= 0.03
```

或：

```text
ND unsafe reduction vs frozen S1 >= 0.05
while coverage >= 0.75
```

则：

```text
M3-S2S-A
CENTER INSTRUMENTATION DEVELOPMENT SUCCESS
```

结论：

> rich center-gradient instrumentation produced a safety-compliant development candidate.

此时：

```text
DO NOT run Arm B
```

下一步另立：

```text
M3-S2D candidate freeze / fresh expansion task
```

---

# 25. Arm A failure / Arm B eligibility

如果：

```text
no Arm-A candidate satisfies coverage >=0.75 and unsafe<=0.20
```

则中心稳定性 family 没有给出合规 working point。

但 Arm B 并不自动运行。

先生成：

```text
M3_S2S_ArmA_Report.md
```

状态：

```text
M3-S2S-B-GATE
ARM_B_ELIGIBLE = YES/NO
ARM_B_AUTHORIZED = NO
```

---

## 25.1 Arm B eligibility

Arm B 只有在以下情况下可进入人工审批：

1. Arm A 192? / 960 trial completeness全部通过；
2. Arm A scientific integrity valid；
3. gradient-stability feature family 已完整测试；
4. no safety-compliant candidate；
5. local-shape hypothesis remains scientifically relevant；
6. ±Δ machinery can be implemented without changing truth semantics；
7. disk / path / seed / persistence preflight PASS。

否则：

```text
ARM_B_ELIGIBLE = NO
STOP
```

---

# 26. Arm B：±Δ Local-Shape optional arm

Arm B 目标：

测试局部 gradient 是否在很小 proposal-scale 改变下：

```text
magnitude unstable
sign unstable
slope large
```

这可能对应 AMBIGUOUS。

---

## 26.1 Δ parameterization

以：

```text
log(s^2)
```

坐标定义：

$$
u = \log s^2.
$$

候选：

```text
Δ ∈ {0.05, 0.10, 0.20}
```

仅为 prereg candidate grid。

---

## 26.2 Δ 选择规则

最终 Δ 不得在 Arm-B full data 上 post-hoc 选择。

在 Arm A 完成后、Arm B simulator call 前：

- 根据纯工程 feasibility 排除越界 Δ；
- scientific Δ selection 规则必须在 Arm-B authorization 前冻结；
- 若要比较多个 Δ，则必须把“Δ”视为 inner-CV hyperparameter；
- outer-test config 对 Δ selection 完全不可见。

---

# 27. Arm B sampling budget

若对每个 center trial 增加：

```text
u-Δ
u+Δ
```

各 20k samples：

$$
120 \times 8 \times 2 \times 20,000
=
\boxed{38,400,000}
$$

因此：

```text
ARM_B_MAX_BUDGET = 38,400,000
```

中心 Arm A 已有：

```text
19,200,000
```

若 Arm B 激活，online-gradient maximum：

$$
\boxed{57,600,000}
$$

**不包括 truth-establishment budget。**

---

# 28. Arm B CRN rule

±Δ 应尽可能与 center 使用 paired CRN。

Codex 必须在 prereg / Arm-B authorization 前审计：

```text
whether exact CRN pairing is technically supported
seed mapping
arm tags
reproducibility
```

如果无法保证冻结的 pairing semantics：

```text
STOP
DO NOT silently switch to independent streams
```

---

# 29. Arm B local-shape features

允许：

$$
g_- = g(u-\Delta),\quad
g_0 = g(u),\quad
g_+ = g(u+\Delta).
$$

构造：

```text
local_sign_persistence
left_sign_match
right_sign_match
three_point_sign_pattern

gradient_slope =
(g_plus - g_minus)/(2*Delta)

left_slope =
(g_0 - g_minus)/Delta

right_slope =
(g_plus - g_0)/Delta

slope_asymmetry
relative_gradient_slope
local_gradient_range
local_S1_range
```

如允许，可构造二阶有限差分：

$$
g''_{\rm disc}
=
\frac{g_+ - 2g_0 + g_-}{\Delta^2}.
$$

但必须标记为：

```text
local-shape descriptive feature
```

而不是物理曲率定理。

---

# 30. Grazing-curvature theory claim boundary

本阶段仍只有真实可定义的 online / model descriptors。

禁止从真实系统中未经证明地声称：

```text
beta*kappa > 1
canonical lobe separation
sigma_c threshold
```

理论只可作为：

```text
feature hypothesis generator
```

正确写法：

> local gradient instability is structurally analogous to the theory-motivated concern that locally convincing direction information may coexist with globally unsafe proposal behavior.

不是因果证明。

---

# 31. Truth blindness during Arm A / B

Arm A/B execution payload 不能包含：

```text
truth
stratum
confirmed_label
high-budget gain
reference action result
```

Execution view 必须只包含：

```text
state parameters required by simulator
frozen seed
instrumentation schema
arm parameters
```

Truth 只能在：

```text
all required durable records COMPLETE
```

之后解封用于 development evaluation。

---

# 32. Persistence contract

继承 WA1R / S1C hardened persistence semantics：

```text
STARTED durable before simulator call
COMPLETE durable only after:
  scientific record written
  instrumentation sidecar written
  both hashes verified
  fsync
  atomic rename
```

如果：

```text
sampling started
AND
durable COMPLETE cannot be established
```

则：

```text
CONSUMED_INVALID
M3-S2S-X for affected gated arm
STOP
NO REPLAY
NO SAME-ARM RERUN
```

---

# 33. Pre-simulator engineering failure

如果 failure 明确发生于：

```text
before STARTED durable / before simulator call
```

允许：

```text
record incident
fix engineering issue
rerun preflight
rehash
re-authorize if hash-locked artifacts changed
```

不得伪装成 scientific consumed-invalid。

---

# 34. Exact sample accounting

所有预算必须分别记录：

```text
truth samples
Arm-A center-gradient samples
Arm-B left samples
Arm-B right samples
```

禁止只报：

```text
total simulator calls
```

Final report 必须给：

```text
planned
actual
difference
top-up = 0
```

---

# 35. Pre-registration configs

至少：

```text
configs/phase_m3s2s/
  m3s2s_parent_contract.json
  m3s2s_exclusion_manifest.json
  m3s2s_truth_contract.json
  m3s2s_panel_contract.json
  m3s2s_gradient_protocol.json
  m3s2s_instrumentation_contract.json
  m3s2s_feature_contract.json
  m3s2s_model_contract.json
  m3s2s_threshold_contract.json
  m3s2s_arm_b_contract.json
  m3s2s_persistence_contract.json
  m3s2s_verdict_contract.json
```

---

# 36. Preregistration docs

至少：

```text
docs/phase_m3s2s/
  M3_S2S_Task.md
  M3_S2S_Preregistration.md
  M3_S2S_Parent_Audit.md
  M3_S2S_Reserve_Firewall_Audit.md
  M3_S2S_Exposure_Firewall_Audit.md
  M3_S2S_Truth_Source_Audit.md
  M3_S2S_Budget_Audit.md
  M3_S2S_Instrumentation_Preflight.md
  M3_S2S_Seed_Audit.md
  M3_S2S_Path_Disk_Preflight.md
  M3_S2S_Human_Approval.md
```

---

# 37. Hash lock

首轮 prereg 必须生成：

```text
results/phase_m3s2s/preflight/m3s2s_prereg_hashes.json
```

并在 tracked docs 中锚定关键 hash：

```text
panel
exclusion manifest
truth contract
gradient protocol
instrumentation contract
feature contract
seed manifest
persistence module
```

如果 `results/` ignored：

> 必须如实说明哪些 artifacts 只存在本地，哪些是远端可审计锁点。

---

# 38. Tests before authorization

必须新增至少：

## Parent / firewall

- correct parent lineage；
- 18 protected overlap hard fail；
- previous controller exposure hard fail；
- truth-reference-only allowed under frozen semantics。

## Panel

- 30/30/30/30 quota；
- >=24 configs；
- round diversity deterministic；
- input-order invariant；
- hash-rank exact。

## Truth

- canonical truth contract hash；
- no threshold drift；
- ambiguous semantics frozen；
- truth sampling budget exact；
- truth-exposed retirement.

## Instrumentation

- `bootstrap_g` length == frozen N_BOOTSTRAP；
- aggregate g reproducible within frozen tolerance；
- sidecar hash verified；
- sidecar schema immutable；
- bootstrap draws never treated as independent trials；
- sufficient-statistic shape checked。

## Seeds

- all 960 Arm-A seeds unique；
- no historical collision；
- Arm-B namespace disjoint；
- truth namespace disjoint。

## Persistence

- STARTED before simulator；
- sidecar failure => no COMPLETE；
- injected failure after sampling => CONSUMED_INVALID；
- no replay；
- tamper detection。

## Modeling

- group split no config leakage；
- δ from inner train only；
- bootstrap feature computed within trial only；
- truth not in X；
- source/panel identity not in X。

## Verdict

Synthetic tests for:

```text
S2S-A
S2S-B-GATE
S2S-C (Arm-B success)
S2S-D (valid negative after Arm-B)
S2S-X
```

---

# 39. Suggested verdict system

## `M3-S2S-A`

Arm A yields a safety-compliant development candidate.

```text
Arm B NOT RUN
```

---

## `M3-S2S-B-GATE`

Arm A validly completes but no safety-compliant candidate.

```text
Arm B may be eligible
ARM_B_AUTHORIZED remains NO
STOP for human review
```

---

## `M3-S2S-C`

After separately authorized Arm B：

```text
local-shape candidate satisfies development gates
```

---

## `M3-S2S-D`

Arm B validly completes but still no safety-compliant development candidate.

这是 valid negative：

> rich center instrumentation + preregistered local-shape information still did not produce a compliant development frontier.

---

## `M3-S2S-X`

Scientific integrity invalid：

```text
protected contamination
truth-contract violation
seed collision after sampling start
truth leakage
persistence failure after consumption
unrecoverable hash mismatch
group leakage
unauthorized arm execution
```

---

# 40. Arm-B success criterion

Arm B candidate仍使用：

```text
coverage >= 0.75
ND unsafe <= 0.20
wrong <= 0.05
AMBIGUOUS unsafe < 0.25
```

并要求相对 best Arm-A candidate：

```text
coverage gain >= 0.03
```

或：

```text
ND unsafe reduction >= 0.05
with coverage maintained >= 0.75
```

---

# 41. No confirmation claim

即使 `M3-S2S-A` 或 `M3-S2S-C`：

只允许：

```text
development-supported candidate
```

不允许：

```text
confirmed
deployment safe
generalizes to untouched population
```

剩余 18 protected reserve **仍然不能在本阶段打开**。

未来 confirmation 必须另立任务书。

---

# 42. First-run commit strategy

首轮 prereg 建议：

## Commit 1

```text
M3-S2S scaffold: S2F-R parent seal, reserve/exposure firewall, truth-source audit
```

## Commit 2

```text
M3-S2S prereg: 120-state truth/panel design, rich instrumentation schema, Arm-A/B budgets and persistence
```

## Commit 3

```text
M3-S2S prereg lock: seeds/path/disk/tests/hash anchors, authorization remains NO
```

然后 push。

---

# 43. Remote push requirement

首轮必须：

```bash
git push -u origin feature/phase-m3-s2s-instrumented-fresh-development
```

禁止 force push。

push 后验证：

```text
local HEAD == remote HEAD
```

并从 remote 读取关键 configs/docs。

---

# 44. 首轮硬 STOP

完成 prereg push 后：

```text
TRUTH_SAMPLING_AUTHORIZED = NO
ARM_A_AUTHORIZED = NO
ARM_B_AUTHORIZED = NO

scientific simulator calls = 0
```

然后：

```text
STOP
```

不得开始 truth sampling 或 Arm A。

---

# 45. 首轮 Codex 最终汇报格式

```text
M3-S2S PREREG STATUS:
PASS / FAIL

PARENT:
M3-S2F-R verified = YES/NO
base = 86ad583...

SCIENTIFIC EXECUTION:
simulator calls = 0
samples = 0

PROTECTED RESERVE:
remaining = 18
used = 0
firewall = PASS/FAIL

EXPOSURE FIREWALL:
fresh candidate pool = ...
controller-exposed excluded = ...
unknown unresolved = ...

TRUTH SOURCE:
existing compatible truth inventory = YES/NO
TRUTH_SAMPLING_REQUIRED = YES/NO
truth protocol source = ...
truth protocol hash = ...
truth budget max = ...

TARGET PANEL:
states = 120
W/S/HOLD/AMB = 30/30/30/30
unique configs = ...
selection rule = ...
panel frozen = YES/NO

ARM A:
states = 120
replicates/state = 8
samples/trial = 20000
trials = 960
budget = 19,200,000

ESTIMATOR:
N_BOOTSTRAP = ...
bootstrap method = ...
aggregate estimator unchanged = YES/NO

INSTRUMENTATION:
bootstrap_g persisted = YES/NO
sufficient-statistic sidecar schema = ...
reconstructability test = PASS/FAIL
estimated storage = ...

ARM B:
authorized = NO
eligible only after valid Arm-A negative = YES
candidate Δ grid = {0.05,0.10,0.20}
max budget = 38,400,000

SEEDS:
Arm-A planned = 960
unique = ...
historical collision = ...
Arm-B namespace frozen = YES/NO

PATH/DISK:
PASS/FAIL
max path = ...
estimated total storage = ...

TESTS:
S2S prereg = ... passed / 0 failed
full regression = ... passed / 0 failed

HASH LOCK:
PASS/FAIL

COMMITS:
...

REMOTE:
branch = feature/phase-m3-s2s-instrumented-fresh-development
local HEAD = ...
remote HEAD = ...
local == remote = YES

AUTHORIZATION:
TRUTH_SAMPLING_AUTHORIZED = NO
ARM_A_AUTHORIZED = NO
ARM_B_AUTHORIZED = NO

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

NEXT:
Await independent live Git audit and explicit human authorization.
```

---

# 46. Authorization after prereg

人工审计后：

## If T0 — truth inventory already sufficient

人工只需要授权：

```text
ARM_A_AUTHORIZED: YES
```

Truth sampling 保持：

```text
NO
```

---

## If T1 — new truth sampling required

先只授权：

```text
TRUTH_SAMPLING_AUTHORIZED: YES
ARM_A_AUTHORIZED: NO
ARM_B_AUTHORIZED: NO
```

Truth panel完成并 freeze 后：

```text
STOP
```

再次人工审计。

之后才允许：

```text
ARM_A_AUTHORIZED: YES
```

---

# 47. Truth-stage execution if required

Truth sampling完成后必须报告：

```text
candidates sampled
consumed-invalid
final frozen truth labels
quota status
truth budget actual
exposed-but-not-selected states
120-state panel hash
```

如果无法达到：

```text
30/30/30/30
```

禁止放宽 quota。

状态：

```text
M3-S2S-PANEL-BLOCKED
STOP
```

不得直接缩成 100 states。

---

# 48. Arm-A execution order

授权后：

```text
1. reverify prereg hashes
2. verify frozen panel
3. verify 960 seeds
4. verify disk/path
5. verify empty destination
6. run canonical panel-order x replicate-order
7. durable STARTED
8. simulator
9. build aggregate record
10. build instrumentation sidecar
11. validate schema
12. hash both
13. durable COMPLETE
14. continue
```

---

# 49. Arm-A evaluation order

只有：

```text
960/960 durable COMPLETE
0 consumed-invalid
0 duplicates
0 missing
0 sidecar hash mismatch
```

才能：

```text
unseal truth
build feature dataset
run grouped nested-CV
assign M3-S2S-A or M3-S2S-B-GATE
```

---

# 50. Arm-B second approval

若得到：

```text
M3-S2S-B-GATE
```

Codex 必须：

```text
STOP
```

人工审计 Arm-A。

只有人工明确修改：

```text
ARM_B_AUTHORIZED: YES
```

并 commit + push 后，才能运行 Arm B。

---

# 51. Final scientific interpretation

本阶段真正希望区分：

```text
statistically confident gradient
```

与：

```text
stable / practically meaningful / locally persistent gradient
```

如果 Arm A 成功：

> estimator internal structure contains useful safe-deployment information that aggregate S1 discarded.

如果 Arm B 才成功：

> local proposal-scale response provides additional development information beyond center-gradient stability.

如果 Arm B 也失败：

> the tested online gradient stability and local-shape feature families are insufficient under the frozen development protocol.

这些都是 development claims，不是 confirmation。

---

# 52. 最终原则

本阶段的优先级必须保持：

$$
\boxed{
\text{truth integrity}
>
\text{freshness}
>
\text{instrumentation completeness}
>
\text{persistence}
>
\text{grouped generalization}
>
\text{model complexity}
}
$$

最重要的工程教训是：

> **这一次必须把 estimator 内部结构持久化到足以支持未来 feature reconstruction，不能第三次只留下 aggregate summary。**

最重要的科学纪律是：

> **18 个 protected reserve 继续封存；S2S 只负责 fresh development，不负责 confirmation。**

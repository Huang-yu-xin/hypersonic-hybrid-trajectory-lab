# M3-S25-R1 Preregistration

Round 0: **preregistration freeze only** -- scientific simulator calls 0,
samples 0.  All numbers rendered from hash-locked artifacts.

```
M3-S25-R1 PREREG STATUS:
ROUND 0 COMPLETE

PARENT (sealed):
M3-S2S terminal = M3-S2S-PANEL-BLOCKED
old T1 gate closed = YES (ARM_A_AUTHORIZED CLOSED, ARM_B_AUTHORIZED CLOSED, TRUTH_SAMPLING_AUTHORIZED CLOSED)
parent truth budget consumed = 436,000,000 / 436,000,000
parent HEAD = f0d7370 (ancestor verified)
parent ledgers = 488 COMPLETE / 0 CONSUMED_INVALID
parent truth-exposed states preserved = 240

CONFIG UNIVERSE:
strict inheritance = 30 configs (parent universe sha 1ff92a140e8ceb08...)
no new / substituted / deleted / reweighted configs = YES (hash pin)

SUPPORT COMPLETION:
u interval = [0.15, 1.00] frozen before any truth sampling
strata = 8/config, anchors = L=65/stratum, hash-first fresh selection
candidates = 240 (30 x 8), all fresh, 0 collisions
parent realized u coverage <= 0.1231; R1 realized u range = [0.1548, 0.9984]

REGRESSION INVARIANTS (Sec. 9):
candidates/configs/strata/dup/freshness/legality/labels/substitution = PASS
min u >= 0.15 = PASS; max u <= 1.0 = PASS; each stratum exactly once = PASS
per-config span >= 0.70 = FAIL (2/30):
  - c000: span 0.6971 (min u 0.2289, max u 0.9259)
  - cf1n_new_002: span 0.6649 (min u 0.2450, max u 0.9098)

=> PREFLIGHT VERDICT = FAIL
   NOT EXECUTION-READY: support-span invariant FAIL (2/30 configs below 0.70); human adjudication required (taskbook Sec. 27); all gates remain NO; samples = 0

TRUTH (NOT authorized):
confirmation_scope = ALL_240_R1_CANDIDATES; early_stop = false
discovery 240 x 3x100k = 72,000,000
confirmation 240 x 3x500k = 360,000,000
P_ref = 0 (30-entry reuse registry, hash-verified, no resampling)
TRUTH_BUDGET_PLANNED = TRUTH_BUDGET_MAX = 432,000,000

SEEDS:
480 units, new namespaces M3-S25-R1-DISCOVERY / M3-S25-R1-CONFIRMATION
unique seed keys = 480, historical collision = 0, cross-stream = 0

PANEL (post-truth only):
union pool = D_old (240) u D_new (240) <= 480; 120 states; 30/30/30/30
>= 24 distinct configs; rank seed M3-S25-R1-PANEL-V1|; duplicate protection
PANEL-BLOCKED if quotas or diversity cannot be met; NO relaxation

DEVELOPMENT UNION:
D_union = M3-S2S 240 truth-exposed states + R1 240 (registry preserved verbatim)

ARM GATES: M3_S25_R1_ARM_A_AUTHORIZED = NO; M3_S25_R1_ARM_B_AUTHORIZED = NO
VALUE / RARITY / M3-Q = BLOCKED

NEXT:
Round 0 STOP.  The support-span invariant conflict requires human
adjudication (taskbook Sec. 27: any rule change needs a NEW taskbook).
Only after a passing execution-readiness audit may
M3_S25_R1_TRUTH_AUTHORIZED be set to YES by the human.
```

Universe sha256: `9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`

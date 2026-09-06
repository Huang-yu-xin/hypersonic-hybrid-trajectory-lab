# M3-S25-R1 Preregistration

Round 0: **preregistration freeze only** -- scientific simulator calls 0,
samples 0.  All numbers rendered from hash-locked artifacts.  Amended by
**M3-S25-R1.1** then **M3-S25-R1.2** (structural support invariants;
candidate universe and its SHA unchanged throughout).

```
M3-S25-R1 PREREG STATUS:
ROUND 0 COMPLETE (amended by M3-S25-R1.1, then M3-S25-R1.2)

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

STRUCTURAL SUPPORT INVARIANTS (M3-S25-R1.2; bounds derived from the
frozen generator constants U_LO=0.15, U_HI=1.00, N_STRATA=8,
L_ANCHORS=65; tol=1e-12; NO hash-draw dependence):
A stratum occupancy 8/8          = True
B min(u) <= u0_max + tol        = True
C max(u) >= u7_min - tol        = True
D span >= (u7_min-u0_max) - tol = True
structural bounds: u0_max = 0.2546401515151515
                   u7_min = 0.8953598484848485
                   span   = 0.6407196969696970
conflicts (0/30):
  (none)
superseded chain: R1.0 span >= 0.70 (FAIL c000 0.6971 / cf1n_new_002 0.6649);
                  R1.1 fixed 0.25/0.85/0.65 (FAIL m3s2s_cfg_005 min u
                  0.251420 > 0.25) -- both RESOLVED by the structural
                  bounds; records: M3_S25_R1_Support_Invariant_Conflict.md,
                  M3_S25_R1_1_Amendment_Record.md; R1.1 BLOCKED preflight
                  preserved as historical evidence (m3s25r1_1_preflight_
                  R1_1_historical.json, sha 5cdf399fd9ab7b8a...)

=> PREFLIGHT VERDICT = PASS
   EXECUTION-READY

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
Round 0 STOP.  Structural support invariants PASS; per the M3-S25-R1.2
amendment, M3_S25_R1_TRUTH_AUTHORIZED remains NO pending the human
execution-readiness audit.  Only an explicit human NO -> YES commit
enables `python scripts/run_m3s25r1.py truth_execute`.
```

Universe sha256: `9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`

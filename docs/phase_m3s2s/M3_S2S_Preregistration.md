# M3-S2S Preregistration

First round: **preregistration freeze only** — scientific simulator calls 0,
samples 0.  All numbers rendered from hash-locked artifacts.

```
M3-S2S PREREG STATUS:
COMPLETE

PARENT:
M3-S2F-R verified = YES
base = 926a5fc
Tier-A dataset hash match = YES

RESERVE:
remaining = 18 (permanent, membership-only)
used = 0

EXPOSURE FIREWALL:
content-based comparator classification; UNKNOWN => UNRESOLVED => ineligible
fresh candidate pool = 240 truth-UNLABELED states / 30 configs

TRUTH SOURCE:
existing compatible truth inventory = NO (fresh corrected pool = 0)
TRUTH_SAMPLING_REQUIRED = YES (T1)
truth protocol = CF1N three-phase (pref reuse / discovery 3x100k / confirmation 3x500k)
TRUTH_BUDGET_MAX = 436,000,000

TARGET PANEL:
states = 120, quota 30W/30S/30HOLD/30AMB, >= 24 configs
selection = truth stratify + round-based config diversity + SHA256('M3-S2S-PANEL-V1|'|config|state)
panel frozen = NO (freezes only after truth establishment)

ARM A:
states = 120 x 8 replicates x 20000 samples = 960 trials
ARM_A_GRADIENT_BUDGET = 19,200,000
estimator unchanged = YES (persistence-only delta)

ESTIMATOR / INSTRUMENTATION:
N_BOOTSTRAP = 500
bootstrap = fixed-stratified, seed [seed, 424243]
sidecar = npz(a_vec, resp, sq, strata, bootstrap_g) sha-pinned before COMPLETE
batches=20 is a config constant, NOT 20 batch gradients (source-verified)

ARM B:
authorized = NO (candidate protocol only; delta grid {0.05,0.10,0.20} log s^2)
ARM_B_MAX_BUDGET = 38,400,000; eligible only after M3-S2S-B-GATE + human YES

TRUTH SCOPE (AMENDMENT):
confirmation_scope = ALL_240_FRESH_CANDIDATES
early_stop_on_quota = false
discovery_states = 240
confirmation_states = 240
TRUTH_BUDGET_PLANNED = 436,000,000
TRUTH_BUDGET_MAX = 436,000,000
CF1N estimator/label semantics reused verbatim (scope change only)

CANDIDATE UNIVERSE (AMENDMENT):
tracked artifact = configs/phase_m3s2s/m3s2s_candidate_universe.json
candidate_universe_sha256 = 1ff92a140e8ceb0878100ebdeea6bdcf5f6f5fd91ec0838bf9a84b3931412ca0
vendored truth protocol = configs/phase_m3s2s/reference_truth_protocol/ (7 byte-exact snapshots)

SEEDS:
Arm-A candidate pool = 1920 seeds (960 = frozen panel subset)
unique = 1920, historical collision = 0
Arm-B namespace disjoint = YES

PATH/DISK:
PATH_PREFLIGHT = PASS, DISK_PREFLIGHT = PASS
max path = 133 (limit 220)
worst-case storage = 1.85 GB

AUTHORIZATION:
TRUTH_SAMPLING_AUTHORIZED = NO
ARM_A_AUTHORIZED = NO
ARM_B_AUTHORIZED = NO

VALUE / RARITY / M3-Q = BLOCKED

NEXT:
Await independent live Git audit and explicit gate-by-gate human authorization.
```

## EXECUTION-READINESS AMENDMENT (zero-sampling; final audit block)

1. **Vendored artifacts are the runtime source of truth.**  All M3-S2S
   truth-protocol/config resolution reads exclusively from
   `configs/phase_m3s2s/reference_truth_protocol/` via
   `src/hyptraj/m3s2s/vendored_runtime.py`, whose guarded reader refuses any
   access to `configs/phase_m3cf1n/*`, `results/phase_m3wcf1/*`,
   `results/phase_m3cf0/*`, `docs/phase_m1d/*` at execution time (those
   remain historical-comparison inputs only).  The vendored SHA256 values
   frozen in `m3s2s_truth_contract.json` are unchanged; `load_vendored`
   hard-fails on any hash drift.  Vendored set now also includes the
   per-config historical P_ref records (8 CF1N-PREF + 6 WCF1-PREF +
   `m3d2_probability_reference.json`) needed by the classification gate.

2. **Tracked universe is the execution source.**  Truth execution loads
   `configs/phase_m3s2s/m3s2s_candidate_universe.json` and verifies its
   sha256 before any simulator call.  **Sha normalization disclosure:** the
   preregistration report previously quoted `d74a7be7...`, which was the
   CRLF working-tree rendering on Windows; the tracked git blob (LF) has
   always been `1ff92a140e8ceb0878100ebdeea6bdcf5f6f5fd91ec0838bf9a84b3931
   412ca0`.  The amendment pins the LF form and writes the artifact as LF
   bytes, so working tree == git blob == audited sha; the logical content
   (all 240 states) is byte-identical to the previously audited blob.

3. **Gated truth-execution stage implemented (not executed).**
   `truth_preflight` (ran now: PASS, 240/240 vendored-only dry assembly,
   destination empty, gates frozen NO), `truth_execute` (requires
   TRUTH_SAMPLING_AUTHORIZED: YES; P_ref = exactly the 8 frozen new configs
   x 500k; discovery = all 240 x 3 x 100k; confirmation = all 240 x 3 x
   500k; confirmation_scope = ALL_240_FRESH_CANDIDATES; early_stop_on_quota
   = false; planned = max = 436,000,000; no top-up; no candidate
   substitution), and `truth_panel` (truth assignment + exposed inventory
   for ALL 240 truth-sampled states + 120-state round/hash panel selection
   only after 488/488 durable COMPLETE; M3-S2S-PANEL-BLOCKED + STOP if the
   quota or >=24-config floor is unachievable; no relaxation, no shrinkage).
   Hardened transactional persistence inherited: STARTED durable before
   simulator; post-sampling failure => CONSUMED_INVALID => M3-S2S-X =>
   STOP => NO REPLAY.  Exact per-stream consumption (P_ref / discovery /
   confirmation) accounted planned/actual/difference.

4. **Evidence:** S2S prereg suite 37 passed / 0 failed; full regression
   2286 passed / 0 failed, 3 warnings, 385.45s (exit 0); prereg hash
   manifest regenerated including the new modules
   (vendored_runtime / truth_execution / m3d2 experiment / gradient
   estimator).  Scientific simulator calls = 0; samples = 0.
   TRUTH_SAMPLING_AUTHORIZED = NO; ARM_A_AUTHORIZED = NO;
   ARM_B_AUTHORIZED = NO.

# M3-S2S Preregistration

First round: **preregistration freeze only** — scientific simulator calls 0,
samples 0.  All numbers rendered from hash-locked artifacts.

```
M3-S2S PREREG STATUS:
COMPLETE

PARENT:
M3-S2F-R verified = YES
base = 86ad583
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

## Prereg lock evidence (first round)

- Tests: S2S prereg suite 20 passed / 0 failed; full regression 2269 passed /
  0 failed, 3 warnings, 336.12s (python -m pytest -q, exit 0).
- Prereg hash manifest: `results/phase_m3s2s/preflight/m3s2s_prereg_hashes.json`
  (results/ is gitignored by repo policy — the manifest is results-local and
  re-derivable; the REMOTE-AUDITABLE locks are the committed contracts in
  `configs/phase_m3s2s/` and the hash anchors recorded in this doc:
  panel rule seed `M3-S2S-PANEL-V1|`, rank string, TRUTH_BUDGET_MAX
  436,000,000, ARM_A_GRADIENT_BUDGET 19,200,000, ARM_B_MAX_BUDGET
  38,400,000, N_BOOTSTRAP 500, sidecar schema m3s2s_instr_v1, seed
  namespaces M3-S2S-A-GRAD / M3-S2S-B-GRAD).
- Truth-contract phase hashes (canonical CF1N protocol) are committed inside
  `configs/phase_m3s2s/m3s2s_truth_contract.json`.
- Authorization gates: TRUTH_SAMPLING_AUTHORIZED = NO; ARM_A_AUTHORIZED =
  NO; ARM_B_AUTHORIZED = NO.  Simulator calls 0; samples 0.

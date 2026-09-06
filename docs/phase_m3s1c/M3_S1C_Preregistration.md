# M3-S1C Preregistration

Frozen before any simulator call.  All numbers below are rendered from the
hash-locked artifacts in `results/phase_m3s1c/preflight/` and
`configs/phase_m3s1c/`.

```
M3-S1C PREREG STATUS:
COMPLETE

PARENT:
base commit = 7b8ad90c472f58fbe22bb48401541a14fc2e6a9d
HEAD at freeze = 3bd967d7d2f50f6299cf0f2f452f137f06dd84c0
scientific verdict = PI1VNR-C
S1 status = DEVELOPMENT_SUPPORTED (confirmed = NO)
VALUE / RARITY / M3-Q = BLOCKED
protected confirmation = untouched

RESERVE:
42 audited
W/S/ND composition = 10/13/19
exposure overlap = 0

CONFIRMATION PANEL:
8 W / 8 S / 8 ND
24 states
W configs = 5, S configs = 7, ND configs = 8
panel sha256 = 1b1e390f3c87e3e8556f37a92b6e4e4988a6b738d62eb7c6ab9eb7e39d3921a5
selection = truth stratify -> max config diversity -> sha256('M3-S1C-PANEL-V1|'|config|state) rank

S1:
formula sha256 = d58b920b9e47884bb1103549a78eed1a0215daf183998fe6ba1b4bac256a860b
threshold = 5.4417199447782 (frozen; NO search in S1C)
gates = coverage>=0.75, wrong<=0.05, unsafe<=0.20

SEEDS:
192 planned
192 unique
0 collision
namespace = M3-S1C-GRAD
seed manifest sha256 = d98ff18d24d48c624845dba3958247013f7933818ecdf69039b0a211e50122c8

SCIENTIFIC BUDGET:
gradient = 24 x 8 x 20000 = 3,840,000 samples
finite-action probe = 0
V1 samples = 0

PATH/PERSISTENCE:
PATH_PREFLIGHT = PASS (192/192; max final 147, max temp 198, limit 220)
persistence module = src/hyptraj/m3wa1r/persistence.py (sha256 locked)
failure rule = CONSUMED_INVALID => M3-S1C-X => STOP, no replay

PREREG:
hash manifest = results/phase_m3s1c/preflight/m3s1c_prereg_hashes.json (14 files)
PREREG_HASH_LOCK = PASS

EXECUTION_AUTHORIZED:
NO

NEXT:
Await explicit human authorization.
```

## AMENDMENT A — frozen config-diversity round rule

Formally frozen (before any simulator call) in the panel contract
(`configs/phase_m3s1c/m3s1c_panel.json` -> `selection_rule`) and implemented
verbatim in `scripts/run_m3s1c.py::select_panel`:

```text
Within each truth stratum:
1. Group all eligible untouched states by config_id.
2. Within each config_id: sort states by the preregistered frozen
   selection_rank = SHA256("M3-S1C-PANEL-V1|" + config_id + "|" + state_id).
3. Select states in config-diversity rounds:
   Round k takes at most the k-th ranked state from each config; the
   candidates within a round are ordered only by their own frozen rank.
4. Stop immediately when exactly 8 states have been selected for that
   truth stratum.
5. No S1, gradient, V1, controller result, theory descriptor, development
   outcome, or manual preference may affect selection.
```

Scientific meaning: **lexicographically maximize physical-config diversity
before allowing additional repeated states from an already represented
config.**  The canonical rank string used by the implementation is exactly
`SHA256("M3-S1C-PANEL-V1|" + config_id + "|" + state_id)` (byte-order
ascending); no deviation exists.  Pool-composition consequence (recorded,
not a rule change): the W stratum offers only 5 unique configs, so rounds
2/3 legitimately admit the 2nd/3rd ranked states of already represented
configs.

## AMENDMENT B — frozen previous-confirmation exposure semantics

`previous_confirmation_exposure` (exposure bit 8) is formally defined as
**previous controller/comparator/policy-level confirmation exposure** — NOT
any historical artifact whose filename contains "confirm".  Classification
is by record content with nearest-ancestor namespace inheritance:

```text
comparator      record carries any comparator/policy field
                (g_hat, g_ci_low, g_ci_high, ci_low, ci_high,
                gradient_valid, S1, s1_score, V1, v1_score, r_hat,
                se_r_hat, selected_action, controller_action,
                deployment, deploy, abstain, policy_decision,
                action_sign, ESS_grad) or sits under a
                comparator-pattern namespace (GRAD|PROBE|TRIAL|V1|S1|POLICY)
                => FORBIDDEN (state ineligible)

truth_reference record carries truth/reference fields (confirmed_label,
                provisional_label, P_ref_hash, p_ref_hash) or sits under a
                truth-stream namespace (...-REF / ...-CONFIRM) with no
                comparator field of its own
                => ALLOWED (this is the frozen high-budget truth stratum
                that the confirmation panel requires; taskbook Sec. 4.4)

unknown         neither of the above on a candidate-bearing record
                => UNRESOLVED => STOP panel freeze; unknown artifacts are
                NEVER auto-allowed (amendment Sec. 3.6)
```

Without this distinction the confirmation design is self-contradictory: the
panel requires frozen W/S/HOLD/AMBIGUOUS truth, but the high-budget
reference characterization that establishes that truth would itself
disqualify every state.

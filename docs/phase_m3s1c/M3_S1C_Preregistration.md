# M3-S1C Preregistration

Frozen before any simulator call.  All numbers below are rendered from the
hash-locked artifacts in `results/phase_m3s1c/preflight/` and
`configs/phase_m3s1c/`.

```
M3-S1C PREREG STATUS:
COMPLETE

PARENT:
base commit = 7b8ad90c472f58fbe22bb48401541a14fc2e6a9d
HEAD at freeze = 7b8ad90c472f58fbe22bb48401541a14fc2e6a9d
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

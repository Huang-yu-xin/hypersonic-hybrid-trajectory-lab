# M3-WA1R Preregistration

Frozen before any simulator call.

```
M3-WA1R PREREG STATUS:
COMPLETE

PARENT:
WA1 = WA1-X
PI1VR0 = PI1VR0-CAP-B
PI1V valid verdict = PI1V-X

WA1 INCIDENT:
consumed-invalid candidates = 1
consumed candidate ID = cf1n_new_000_wa1_w_s2_1p788854382
retired = YES
reused = NO

WA1 NEVER-STARTED:
audited count = 7
all simulator samples = 0
all exposure = 0

UNUSED PRE-OUTCOME CANDIDATE:
count = 1
ID = cf1n_new_003_wa1_w_s2_1p788854382
generated before WA1 outcome = YES
sampled = NO

RECOVERY CANDIDATES:
count = 8
distinct configs = 5
max/config = 3 (exceeds preferred <=2; deterministic valid universe exists per Sec. 17/35 -- see m3wa1r_recovery_diversity_gate.json)
manifest hash = cd21bf4cae279c4afaffd0c43f99526164521441cd76738874df48b9665c57dc
new midpoint generated after WA1-X = NO

P_REF:
dependency = CONFIG_SPECIFIC
new P_ref samples = 0
all reused records durable = YES

PERSISTENCE:
safe paths = PASS
STARTED before simulator = PASS
non-circular hash contract = PASS
WA1 bug regression = PASS
atomic persistence = PASS
consumed-invalid replay = FORBIDDEN

M3WA1R-PERSIST-1:
PASS (synthetic components; full regression re-verified at close)

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
expected finite-action samples = 12000000

SEEDS:
namespace = M3-WA1R-REF
count = 8
collision with WA1 = 0
all prior collision = 0
hash-locked = YES

EXISTING FRESH RESERVE:
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34

SUCCESS TARGET:
combined fresh W:
  exact 8 selectable
  configs >=6
  max2/config

full fresh panel:
  8W / 8S / 8ND

W-CONFIG CEILING NOTE:
retiring the consumed candidate (config cf1n_new_000) caps the combined W
distinct-config ceiling at 5 (< 6); the reference still executes per the
frozen protocol and the W feasibility gate decides the verdict.

INVALID PI1V DATA:
used = NO

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN WA1R REFERENCE

```

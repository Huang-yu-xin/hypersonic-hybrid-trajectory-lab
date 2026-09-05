# M3-WA1 Preregistration

Frozen before any simulator call.

```
M3-WA1 PREREG STATUS:
COMPLETE

PARENT:
PI1VR0 = PI1VR0-CAP-B
PI1V valid verdict = PI1V-X

INVALID PI1V DATA:
used in candidate design = NO
used in selector = NO

EXISTING FRESH RESERVE:
W = 7
S = 29
HOLD = 13
AMB = 21
ND = 34

EXISTING FRESH W:
distinct configs = 4
max/config = 3

W SUPPORT INVENTORY:
eligible adjacent-W configs = 6
eligible adjacent-W pairs = 9

P_REF:
dependency = CONFIG_SPECIFIC
reuse/new rule frozen = YES (reuse durable config P_ref; 0 new samples)

WA1 CANDIDATES:
count = 8
distinct configs = 6
max/config = 2
IDs = cf1n_new_000_wa1_w_s2_1p788854382, cf1n_new_001_wa1_w_s2_1p4142135624, cf1n_new_002_wa1_w_s2_1p4142135624, cf1n_new_003_wa1_w_s2_1p4142135624, cf1n_new_003_wa1_w_s2_2p2360679775, cf1n_new_005_wa1_w_s2_1p4142135624, cf1n_new_005_wa1_w_s2_1p788854382, cf1n_new_007_wa1_w_s2_1p4142135624
manifest hash = 02765e17109651c5cb846116c064eaba6e980519faeec07432b119e6e6fa2679

CANDIDATE RULE:
adjacent confirmed W only = YES
log midpoint = YES
fresh identities = YES
adaptive extension = FORBIDDEN

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
finite-action samples = 12000000

SEEDS:
namespace = M3-WA1-REF
collision = 0
hash-locked = YES

PERSISTENCE:
PI1VR0 hardened contract = ENABLED
STARTED before simulator = YES
consumed-invalid replay = FORBIDDEN

SUCCESS TARGET:
combined fresh W subset:
  exact W = 8
  configs >=6
  max/config <=2

full fresh panel:
  8W / 8S / 8ND

PILOT:
gradient = 0
probe = 0

V1:
new test = NO
threshold = null

S1:
confirmation = NOT AUTHORIZED

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN WA1 REFERENCE

```

# M3-WCF1 Preregistration

Frozen before any simulator call.

```
M3-WCF1 PREREG STATUS:
COMPLETE

PARENT:
WA1R = WA1R-B
WA1 = WA1-X
PI1V valid verdict = PI1V-X

CURRENT FRESH W:
state count = 15
distinct configs = 5
exact8/config>=6 feasible = NO

INVALID PI1V DATA:
used in config selection = NO
used in s2 selection = NO
used in panel selection = NO

PHYSICAL CONFIG SPACE:
legal fresh capacity = 120
selector = sequential maximin
outcome-blind = YES

NEW CONFIGS:
count = 6
IDs = wcf1_new_000, wcf1_new_001, wcf1_new_002, wcf1_new_003, wcf1_new_004, wcf1_new_005
manifest hash = 18ca0ae9c6617da7d0fbbb5ab8c59225c6c0dd2b0f9fd32ac7db4a68f51432cf
prior config collisions = 0

VALID W-BY-s2 AUDIT:
source = corrected durable high-budget only
invalid evidence used = NO

W-TARGET s2:
count = 2
values = [1.6, 1.25]
selector rule frozen = YES
common-grid values = YES

REFERENCE STATES:
count = 12
fresh identities = 12/12
manifest hash = dc011f2fc48c6866f5810134b4bf7837a8a25e243cd2eed2baf57a1d6bfd122b

P_REF:
new streams = 6
samples/config = 500000
namespace = M3-WCF1-PREF

REFERENCE:
samples/arm = 500000
arms = 3
batches = 20
states = 12
namespace = M3-WCF1-REF

EXPECTED COST:
P_ref = 3000000
finite-action reference = 18000000
total = 21000000

PERSISTENCE:
hardened contract = ENABLED
STARTED-before-simulator = YES
non-circular hash = YES
consumed-invalid replay = FORBIDDEN

PRIMARY TARGET:
K_NEW_W_CONFIG >=1

FINAL W GATE:
exact W = 8
configs >=6
max2/config

FULL PANEL TARGET:
8W / 8S / 8ND

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
HUMAN APPROVAL TO RUN WCF1

```

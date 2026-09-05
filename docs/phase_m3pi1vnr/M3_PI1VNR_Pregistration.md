# M3-PI1VNR Preregistration

Frozen before any simulator call.

```
M3-PI1VNR PREREG STATUS:
COMPLETE

PARENT:
PI1VN = PI1VN-X
WCF1 = WCF1-A
PI1V = PI1V-X

PI1VN INCIDENT:
planned trials = 192
durable complete = 136
consumed-invalid = 1
never started = 55
replay performed = NO

PI1VN PANEL:
states = 24
retired = 24
reused in PI1VNR = 0

PI1VN SEEDS:
retired = YES
reused = 0

INVALID DIAGNOSTICS:
PI1V Attempt-2 used = NO
PI1VN partial metrics used = NO

REFERENCE:
new P_ref samples = 0
new high-budget reference samples = 0

FRESH RESERVE:
eligible W = 18
eligible S = 21
eligible HOLD+AMB = 27

SECOND FRESH PANEL:
states = 24
W = 8
S = 8
ND = 8
W configs = 8
S configs = 8
ND configs = see m3pi1vnr_panel_capacity_gate.json
ND regions = see m3pi1vnr_panel_capacity_gate.json
hash = 1914bf6d2c173107b955c00b2c49e9775c3e0c4e14ab0354b3f10d7e2fdcbd66
pilot exposure = 0
probe exposure = 0

M3PI1VNR-PANEL-1:
PASS

REMAINING PROTECTED RESERVE:
states = 42
pilot exposure = 0

PATH CONTRACT:
run_uuid max length = 32
state slug max length = 64
temp basename max length = 76
full path limit = 220

ACTUAL PATH PREFLIGHT:
trials = 192
PASS = 192
FAIL = 0
max observed final path length = 150
max observed temp path length = 217

WORST-CASE PATH TEST:
PASS (see m3pi1vnr_synthetic_bug_regression.json / persistence gate)

OVER-LIMIT FAILURE:
before simulator = YES

PERSISTENCE:
STARTED-before-simulator = PASS
atomic = PASS
non-circular hash = PASS
no replay = PASS
synthetic E2E = PASS

M3PI1VNR-PERSIST-1:
PASS (re-verified at close)

SCIENTIFIC PROTOCOL:
R = 8
B_grad = 20000
BASE probe = 10000
selected probe = 10000
paired CRN = 20
V1 unchanged = YES
S1 unchanged = YES
metrics unchanged = YES
threshold rule unchanged = YES

GATES:
wrong <=5%
coverage >=75%
unsafe <=20%
unique gain >=5pp or S1 no-full-pass

SEEDS:
gradient namespace = M3-PI1VNR-GRAD
probe namespace = M3-PI1VNR-PROBE
planned trials = 192
collisions = 0
hash locked = YES

MAX ONLINE SAMPLES:
gradient = 3840000
probe = 3840000
total = 7680000

CONFIRMATION:
authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN PI1VNR

```

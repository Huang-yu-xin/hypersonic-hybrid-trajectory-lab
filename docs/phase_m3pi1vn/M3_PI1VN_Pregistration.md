# M3-PI1VN Preregistration

Frozen before any simulator call.

```
M3-PI1VN PREREG STATUS:
COMPLETE

PARENT:
WCF1 = WCF1-A
PI1V valid verdict = PI1V-X

FRESH DEVELOPMENT PANEL:
states = 24
W = 8
S = 8
ND = 8
hash = b4ddf4937095d5445ef4eb480afb22c2274e9449c0936c2d58a3a985febfa66a
hash matches WCF1 = YES
pilot exposure = 0
probe exposure = 0

PROTECTED RESERVE:
states = 66
pilot exposure = 0

INVALID / RETIRED DATA:
PI1V Attempt-2 used = NO
original CF2 panel used = NO
WA1 consumed state used = NO
retired seeds used = NO

GRADIENT:
R = 8
B_grad = 20000
sign rule = g_hat<0 WIDEN / g_hat>0 SHRINK
protocol hash = 7a2251af2c39d54b67ed2a5f83483eda5e925827ec369f51920755c1d0dc6a1a

PROBE:
BASE = 10000
selected action = 10000
total = 20000
paired CRN batches = 20
opposite action = 0
adaptive probe = NO

ONLINE COST:
per valid trial max = 40000
<=2x B_grad = YES

V1:
formula = (-0.01-r_hat)/SE(r_hat)
margin = -0.01
estimator hash = c7332b9e91ce8c286f94201a334d73aa0afcd7127cb5b5d85fda79ffeebba38f
SE estimator hash = c7332b9e91ce8c286f94201a334d73aa0afcd7127cb5b5d85fda79ffeebba38f

S1:
definition hash = c7332b9e91ce8c286f94201a334d73aa0afcd7127cb5b5d85fda79ffeebba38f
same gradient data = YES
probe information used = NO

METRICS:
wrong semantics frozen = YES
coverage semantics frozen = YES
unsafe semantics frozen = YES

GATES:
wrong <=5%
coverage >=75%
unsafe <=20%

UNIQUE INFORMATION:
S1 full-pass absent
OR
V1 best-safe coverage - S1 best-safe coverage >=5pp

THRESHOLD RULE:
deterministic = YES
invalid PI1V threshold reused = NO

SEEDS:
gradient namespace = M3-PI1VN-GRAD
probe namespace = M3-PI1VN-PROBE
planned trials = 192
collisions = 0
hash-locked = YES

PERSISTENCE:
hardened = ENABLED
STARTED-before-simulator = YES
non-circular hash = YES
consumed-invalid replay = FORBIDDEN

MAX SAMPLES:
gradient = 3840000
probe = 3840000
total = 7680000

CONFIRMATION:
authorized = NO

VALUE / RARITY / M3-Q:
BLOCKED

NEXT:
HUMAN APPROVAL TO RUN PI1VN

```

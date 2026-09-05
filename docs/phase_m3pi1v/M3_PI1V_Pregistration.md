# M3-PI1V Preregistration

Frozen before any simulator call.

```
M3-PI1V PREREG STATUS:
COMPLETE

PARENT:
CF2 = CF2-A

DEVELOPMENT PANEL:
states = 24
W = 8
S = 8
ND = 8
hash = 843ee98e5be20d71964684d29e7671f5168bd2c36a6d2b02a745be88aff85d5c
hash verified = YES

PILOT-PROTECTED RESERVE:
states = 70
pilot exposure = 0

LEGACY PROTECTED CONFIRMATION:
pilot exposure = 0

INHERITED GRADIENT:
source = hyptraj.m3d.adaptation.gradient_decision (frozen M3-v0; UC3/PI1 committed)
protocol hash = 7a2251af2c39d54b67ed2a5f83483eda5e925827ec369f51920755c1d0dc6a1a
R = 8
B_grad = 20000
sign convention = g_hat < 0 => WIDEN; g_hat >= 0 => SHRINK
invalid rule = estimator problems OR non-finite g_hat/CI/ESS OR ESS_grad < 20 => invalid; policy action ABSTAIN; no opposite direction inferred

FINITE-ACTION PROBE:
BASE samples/trial = 10000
selected-action samples/trial = 10000
total probe samples/trial = 20000
probe <= B_grad = YES
total online <=2x = YES
opposite action probe = 0
paired CRN = YES

V1:
r_hat = selected/BASE - 1
margin = -0.01
SE estimator = paired-batch SE, std(batch r, ddof=1)/sqrt(20)
SE source hash = dec03c1a927d3cc375d4b16519756d4df350445b815f5b5c9a47406f58906f72
formula = (-0.01-r_hat)/SE

S1:
definition source = UC3 S1_gradient_z (configs/phase_m3uc3/m3uc3_score_contract.json)
source hash = d5e4f6b012cf6d0ad8343e7d4b2ef9cd6f7537d789a608bd838afad330ef2483
same gradient data = YES

METRICS:
wrong semantics inherited = YES
coverage semantics inherited = YES
unsafe semantics inherited = YES

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
frozen before pilot = YES

SEEDS:
gradient namespace = M3-PI1V-GRAD
probe namespace = M3-PI1V-PROBE
all prior collisions = 0
hash-locked = YES

PERSISTENCE:
transactional = ENABLED
consumed-invalid rerun = FORBIDDEN

PLANNED TRIALS:
24 x R = 192

MAX GRADIENT SAMPLES = 3840000
MAX PROBE SAMPLES = 3840000
MAX TOTAL ONLINE SAMPLES = 7680000

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

CONFIRMATION:
authorized = NO
reserve pilot = 0

NEXT:
HUMAN APPROVAL TO RUN PI1V DEVELOPMENT

```

# M5-AR Final Routing Report

```text
M5-AR STATUS:
BLOCKED

LIVE GIT:
branch = feature/phase-m5ar-architecture-regime-review
PF3 tag = RareTopo-M4-PF3-v0
PF3 commit = dbe730d4a0cf12de253e2f46384d9abc99d9a60e

ZERO-SIMULATOR:
extra_simulator_calls = 0
sources_unchanged = true

PF3 PARENT FREEZE:
frozen nominal label = S0
downstream comparison literal = NOMINAL
PF3 A1 median stored P_hat = 1.0000823667
median frozen event probability = 0.0747756716
median P_hat / p_ref = 13.3942
median true-event share of stored variance_mass = 0.0197806
gate = STOP_DO_NOT_START_M5AR

LOCAL-FAMILY CEILING:
NOT RUN

EVENT/TOPOLOGY REPRESENTATION:
NOT RUN

STATIC MIXTURE ARCHITECTURE:
NOT RUN

PATH/STAGE:
NOT RUN

BENCHMARK/REGIME:
NOT RUN

PRIMARY ROUTING VERDICT:
NONE — routing was not performed

M3-Q:
BLOCKED

NEXT REQUIRED ACTION:
Repair the nominal-label comparison and separately regenerate/re-freeze the
affected M3-D through PF3 evidence before restarting M5-AR.

FORBIDDEN NEXT STEPS:
Do not select R1-R6 from the invalid evidence, do not run a next-generation
proposal experiment, and do not create RareTopo-M5-AR-v0.
```

The machine-readable evidence is in
`results/phase_m5ar/summary/m5ar_pf3_parent_freeze_audit.json`.  This report
does not claim that any architecture, representation, path, or regime
mechanism is dominant.

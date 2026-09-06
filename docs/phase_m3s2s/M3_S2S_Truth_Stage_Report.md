# M3-S2S Truth Stage Report

Outcome: **M3-S2S-PANEL-BLOCKED** (taskbook Sec. 47).  Recorded
2026-09-06.  TRUTH_SAMPLING_AUTHORIZED = YES was exercised for this stage
only; **ARM_A_AUTHORIZED = NO; ARM_B_AUTHORIZED = NO; VALUE / RARITY /
M3-Q = BLOCKED.**

## Execution integrity (clean)

- 488/488 truth units durable COMPLETE: 8 PREF + 240 discovery +
  240 confirmation.  0 CONSUMED_INVALID.  0 duplicates.
- Exact sample accounting (planned == actual, topup = 0):
  PREF 4,000,000 + discovery 72,000,000 + confirmation 360,000,000
  = **436,000,000** (TRUTH_BUDGET fully consumed).

## Frozen truth outcome (240 states, ALL_240_FRESH_CANDIDATES)

| truth | n | quota | short |
|---|---|---|---|
| WIDEN | 171 | 30 | - |
| AMBIGUOUS | 53 | 30 | - |
| HOLD | 16 | 30 | **-14** |
| SHRINK | **0** | 30 | **-30** |

`M3-S2S-PANEL-BLOCKED`: the frozen 30/30/30/30 quota cannot be filled.
Per taskbook Sec. 47 the quota was NOT relaxed and the panel was NOT
shrunk; no 120-state panel exists; no Arm A/B activity; STOP executed.

## Root cause (candidate-plan placement defect, stated honestly)

The frozen candidate grid placed every fresh s2 point at the BOTTOM of
each config's legality window: all 240 candidate s2 values lie in
**[0.547, 0.734]** while the window extended to 8.0.  The implementation
took "the first 8 fresh points" from an ascending log-spaced scan, which
selects the lowest 8 positions of the window instead of spreading points
across it.  The corrected benchmark's SHRINK region lives at high s2, so
zero SHRINK states were sampled; HOLD was likewise under-sampled.  This
is a plan-design defect of this stage, realized only after the truth
budget was spent; the 64-point capacity check had confirmed fresh points
existed across the whole window, so the defect was in the take-order, not
in availability.

## State of the 240 truth-exposed states

- ALL 240 states are recorded in
  `results/phase_m3s2s/summary/m3s2s_truth_exposed_inventory.json` and are
  **retired from all future untouched confirmation use** (selected or not).
- They remain valid DEVELOPMENT data (frozen truth, 20k-protocol
  gradient-compatible) for a future development stage -- subject to a new
  taskbook.

## Budget position / required next decision (human)

- TRUTH_BUDGET_MAX = 436,000,000 is fully consumed.  Any additional truth
  sampling (e.g., high-s2-focused candidates to fill HOLD/SHRINK) requires
  a NEW preregistered budget and a new human authorization -- no sampling
  may occur under the current freeze.
- The candidate-grid placement rule must be redesigned (e.g., stratified
  log-deciles across the full legality window) and preregistered before
  any new truth round.  No rule change is made in this report.

## Gates

TRUTH_SAMPLING_AUTHORIZED = YES (exercised; truth stage complete/blocked).
ARM_A_AUTHORIZED = NO.  ARM_B_AUTHORIZED = NO.
VALUE / RARITY / M3-Q = BLOCKED.

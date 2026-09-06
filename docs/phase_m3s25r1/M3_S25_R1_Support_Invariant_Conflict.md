# M3-S25-R1 Support-Invariant Conflict (Round 0, zero samples)

## What happened

The frozen selection mechanism (taskbook Sec. 7) and the frozen
regression invariant (taskbook Sec. 9: per-config `max u - min u >=
0.70`) conflict on the realized hash draws for 2/30 configs:

| config | min u | max u | span |
|---|---|---|---|
| c000 | 0.2289 | 0.9259 | 0.6971 |
| cf1n_new_002 | 0.2450 | 0.9098 | 0.6649 |

Both failing selections are **rank-1 (lowest-hash) fresh anchors with
zero collisions** -- the outcome of the hash draw itself, not a
freshness or legality artifact.  All other Sec. 9 invariants pass
(240 states / 30 configs / 8 strata each, each stratum occupied exactly
once, min u >= 0.15, max u <= 1.0, 0 duplicates, 0 freshness violations,
0 legality violations, 0 truth labels consulted, 0 substitutions).

## Why the conflict is structural, not incidental

Under the frozen mechanism the selected anchor within a stratum is the
lowest-hash fresh anchor, which is uniform over the 65 interior anchor
positions.  Writing the stratum-0 (resp. stratum-7) selection as
`u_min = 0.15 + a`, `a in (0.0016, 0.1046)` (resp. `u_max = 1.0 - b`),
the span is `0.85 - (a + b)`; `span < 0.70` iff `a + b > 0.15`, with
per-config probability about 16.5 percent under independent uniform
draws.  Across 30 configs the probability that at least one config
violates the invariant is about 99.6 percent: **the invariant as frozen
cannot generally be satisfied by the mechanism as frozen.**  The
mechanism's anti-collapse guarantee is `span >= e_7 - e_1 = 0.6375`
(one anchor per stratum, worst case), and typical realized spans are
about 0.75.

Empirical robustness: the realized conflicts are identical under three
honest definitions of the historical characterized set (parent 4-source
minimum; full characterized-artifact sweep; sweep without proposal
artifacts), so the outcome is not an artifact of the firewall's input
choice.

## Disposition (fail-closed; no self-authorization)

- The universe is frozen exactly as the frozen mechanism produced it
  (`configs/phase_m3s25r1/m3s25r1_candidate_universe.json`, hash-pinned);
  the preflight records the honest verdict:
  `FAIL`.
- No candidate substitution, no rule relaxation, no support-interval
  change, no re-rolled hash (taskbook Sec. 27/35).  `truth_execute`
  refuses to run while the frozen preflight verdict is not PASS
  (mechanically enforced fail-closed ordering, taskbook Sec. 20 step 3).
- Round 0 ends with samples = 0 and all gates NO.  Per taskbook Sec. 27
  any change (invariant threshold or selection mechanism) requires a NEW
  taskbook from the human; this report only documents the conflict and
  the measured facts for that adjudication.
- For scale: the parent stage's defect had realized span about 0.0083
  (all candidates inside the bottom 12.3 percent of the window).  The
  realized R1 universe spans at least 0.6649
  per config -- the anti-collapse purpose of the invariant is met with
  large margin everywhere; the frozen numeric threshold 0.70 is what
  2/30 configs miss.

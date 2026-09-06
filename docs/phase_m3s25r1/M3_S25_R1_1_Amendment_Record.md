# M3-S25-R1.1 Amendment Record (zero sampling)

Amendment document:
`docs/phase_m3s25r1/M3_S25_R1_1_Amendment_Taskbook.md` (sha256
`44012df4307e704304d22281f5a899c72aff3bd13a19cb788746bb15b7aba586`).
Applied per amendment Sec. 13: amendment document -> contract invariant
update only -> hash manifest -> zero-sampling preflight -> regression
tests -> candidate-SHA verification -> commit -> push -> STOP.

## What changed (and what did not)

- REPLACED: the M3-S25-R1.0 support-span regression invariant
  (per-config `span >= 0.70`) with the M3-S25-R1.1 support-coverage
  invariants A/B/C/D (recorded in `m3s25r1_contract.json` together with
  the parent contract hash, the amendment hash, the old invariant, the
  new invariants and the reason).
- UNCHANGED (amendment Sec. 2/6): the candidate universe file and its
  SHA256 (`9d1f704a4d9b8ca8b3eda4069e5e0a76e3c103cef65e315c4223058d6e600d02`),
  the generation mechanism, hash-first selection, freshness firewall,
  legality rules, seeds, truth semantics, budget (432,000,000),
  runtime fail-closed ordering, panel rules.  No re-hash, no re-draw,
  no candidate substitution.

## Zero-sampling validation outcome (amendment Sec. 8/12)

- Candidate immutability: 240 states / 30 configs / 8 strata per config,
  universe SHA unchanged -- PASS.
- Freshness: 0 collisions, 0 substitutions -- PASS.
- Support invariants:
  - A (stratum occupancy 8/8): PASS for all 30 configs.
  - C (max(u) >= 0.85): PASS for all 30 configs (worst max u =
    0.898580).
  - D (span >= 0.65): PASS for all 30 configs (worst span =
    0.664867) -- the ORIGINAL R1.0 conflict
    (c000 span 0.6971, cf1n_new_002 span 0.6649) is RESOLVED by D.
  - B (min(u) <= 0.25): **FAIL for 1/30 configs**:

| config | failed | min u | max u | span |
|---|---|---|---|---|
| m3s2s_cfg_005 | B_min_reach_le_0.25 | 0.251420 | 0.953314 | 0.701894 |

## Residual conflict (same structural class as the R1.0 conflict)

The B-violating selection is the stratum-0 rank-1 (lowest-hash) fresh
anchor with ZERO collisions -- again a pure hash draw, not a freshness
or legality artifact.  A stratum-0 anchor is uniform over
u in (0.1516, 0.2546); `min(u) <= 0.25` fails iff the draw lands in the
top 3 of 65 positions (m >= 62), a per-config probability of about
4.6 percent, hence about 76 percent across 30 configs.  The mechanism's
structural guarantee is `min(u) < e_1 = 0.25625`, so the frozen 0.25
threshold again exceeds what the mechanism guarantees.  Measured fact
for adjudication: any B threshold in [0.251421, 0.25625) passes the
frozen universe; `0.25625` (= e_1) is the exact structural bound.

## Disposition (amendment Sec. 12; fail-closed)

- Preflight verdict: **FAIL** -- outcome
  **M3-S25-R1.1 PREFLIGHT BLOCKED**, samples = 0, simulator calls = 0.
- No self-modification of rules (amendment Sec. 12); `truth_execute`
  refuses while the frozen preflight verdict is not PASS; all three R1
  gates and the sealed parent gates remain NO.
- The original R1.0 conflict is resolved (D); the residual B conflict is
  documented above with its exact numbers for the next human
  adjudication.

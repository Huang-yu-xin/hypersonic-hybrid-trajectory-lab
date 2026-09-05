# M3-WA1R Human Approval

- Date: 2026-09-05 (before the first WA1R simulator call).
- The mandatory pre-run STOP report (task book Sec. 51) was frozen in
  `M3_WA1R_Pregistration.md` / `results/phase_m3wa1r/summary/m3wa1r_prereg_status.txt`,
  with all preregistration hashes in `m3wa1r_prereg_hashes.json`.
- Pre-run full regression (task book Sec. 50 step 12): **1973 passed, 0 failed**;
  M3WA1R-PERSIST-1 = PASS.
- The user's session directive — "按照新的任务书执行任务" (execute the new task book) —
  constitutes the human approval to run the WA1R one-shot reference, consistent
  with the standing prior-authorization pattern (UC3, PI1V, WA1).
- Scope: the 8 frozen recovery candidates (7 never-started + 1 pre-outcome unused)
  only; the consumed candidate and all WA1 seeds stay retired; no reserve piloting;
  no V1/S1 routes; VALUE/RARITY/M3-Q stay BLOCKED. If any WA1R sampling begins and
  durable persistence fails: CONSUMED_INVALID => WA1R-X => STOP, no replay, no
  second recovery attempt inside WA1R.

Approved action: run the 8 one-shot 500k/arm three-arm references
(12,000,000 finite-action samples) under the repaired non-circular persistence contract.

# M3-WCF1 Human Approval

- Date: 2026-09-05 (before the first WCF1 simulator call).
- The mandatory pre-run STOP report (task book Sec. 38) was frozen in
  `M3_WCF1_Pregistration.md` / `results/phase_m3wcf1/summary/m3wcf1_prereg_status.txt`,
  with all preregistration hashes in `m3wcf1_prereg_hashes.json`.
- The user's session directive — "按照新的任务书继续执行任务" (continue executing the
  new task book) — constitutes the human approval to run WCF1 (P_ref generation +
  references), consistent with the standing prior-authorization pattern
  (UC3, PI1V, WA1, WA1R).
- Scope: the 6 frozen physical configs / 12 frozen states only. No reserve
  piloting; no V1 test; no S1 confirmation; VALUE/RARITY/M3-Q stay BLOCKED. If any
  WCF1 sampling begins and durable persistence fails: CONSUMED_INVALID => WCF1-X
  => STOP; no replay, no replacement.

Approved action: 6 config-specific P_ref streams (3,000,000 samples) + 12 one-shot
500k/arm three-arm references (18,000,000 finite-action samples) under the repaired
non-circular persistence contract.

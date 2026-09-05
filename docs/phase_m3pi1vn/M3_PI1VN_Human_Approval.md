# M3-PI1VN Human Approval

- Date: 2026-09-05 (before the first PI1VN simulator call).
- The mandatory pre-pilot STOP report (task book Sec. 39) was frozen in
  `M3_PI1VN_Pregistration.md` / `results/phase_m3pi1vn/summary/m3pi1vn_prereg_status.txt`
  with all preregistration hashes.
- The user's session directive — "根据新的任务书继续完成任务" (continue the task per the
  new task book) — constitutes the human approval to run the PI1VN development
  pilot, per the standing prior-authorization pattern (UC3, PI1V, WA1, WA1R, WCF1).
- Scope: the frozen 24-state WCF1 fresh panel only. The current protected reserve
  (66 states), UC2R confirmation, and all retired/invalid data remain untouched.
  Confirmation, VALUE, RARITY, M3-Q stay BLOCKED inside PI1VN regardless of verdict.
  If any trial begins and durable persistence fails: CONSUMED_INVALID => PI1VN-X
  => STOP, no replay.

Approved action: run all 24 x 8 = 192 frozen PI1VN trials (<=2x online budget)
under the repaired non-circular persistence contract.

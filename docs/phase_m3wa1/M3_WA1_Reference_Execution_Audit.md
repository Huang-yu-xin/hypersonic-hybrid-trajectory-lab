# M3-WA1 Reference Execution Audit

Status: **INVALID (WA1-X)**.

- Trial 1 of 8 (`cf1n_new_000_wa1_w_s2_1p788854382`) consumed its full 1,500,000-sample reference; the durable record never reached COMPLETE (schema-validator defect at step 7).
- Ledger: 1 STARTED, 0 COMPLETE, 1 CONSUMED_INVALID; hashes FAIL.
- Frozen rule applied: CONSUMED_INVALID -> WA1-X -> STOP; no replay. Candidates 2-8 were never started (STOP means stop).
- Code defect fixed for successor stages; the stage was NOT rerun.

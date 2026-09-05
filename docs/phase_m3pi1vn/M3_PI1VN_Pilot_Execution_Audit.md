# M3-PI1VN Pilot Execution Audit

Status: **INVALID (PI1VN-X)**.

- Trials durable COMPLETE: 136/192; consumed-invalid: 1 (trial 137); never started: 55.
- Root cause: caller-supplied run_uuid doubled the encoded state id in the temp filename (~265 chars > Windows MAX_PATH 260) for the longest panel state names.
- Frozen rule applied: CONSUMED_INVALID -> PI1VN-X -> STOP; no replay.
- Defects fixed for the successor stage (uuid4 run_uuid; module-level bounded temp names).

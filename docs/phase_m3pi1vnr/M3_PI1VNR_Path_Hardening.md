# M3-PI1VNR Path Hardening

Status: **PASS** (module-level enforcement).

- run_uuid: uuid4 hex (32) via module-level safen_run_uuid; caller overlong values hashed into bounded tokens (taskbook Sec. 16/21).
- State slug <= 64 chars (safe id truncated + digest); temp basename <= 76 chars; both enforced inside hyptraj.m3wa1r.persistence, not only by the caller.
- Full-path limit 220 chars validated BEFORE the simulator; over-limit => PathSafetyError (pre-scientific failure), verified by failure injection with the simulator never invoked.
- Exhaustive 192-path preflight: 192/192 PASS, max final 150, max temp 217.

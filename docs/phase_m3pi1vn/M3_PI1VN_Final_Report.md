# M3-PI1VN Final Report

**Verdict: PI1VN-X**

Trial 137 of 192 (`cf1n_new_005_wa1_w_s2_1p4142135624__rep0`) completed its scientific sampling but never reached a durable COMPLETE record: the caller-supplied run_uuid duplicated the encoded state id inside the temp filename, exceeding the Windows MAX_PATH limit for the longest panel state names. The frozen contract fired exactly as written: **CONSUMED_INVALID -> PI1VN-X -> STOP, no replay**.

- 136 earlier trials are durably complete and remain DIAGNOSTIC ONLY; they support no threshold, verdict, or route decision.
- Defect fixed (uuid4 run_uuid + module-level bounded temp names).
- The frozen design survives; a successor stage may re-preregister under a fresh namespace without reusing the consumed trial or seed.
- VALUE/RARITY/M3-Q: BLOCKED; confirmation trials 0.

FULL REGRESSION:
2097 passed, 3 warnings in 319.79s (0:05:19)

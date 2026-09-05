# M3-WA1 Final Report

**Verdict: WA1-X**

Trial 1 of 8 (`cf1n_new_000_wa1_w_s2_1p788854382`) consumed its full 1,500,000-sample reference but never reached a durable COMPLETE record: the schema validator demanded a payload field (record_sha256) that the payload builder wrote too late. The frozen contract fired exactly as written: **CONSUMED_INVALID -> WA1-X -> STOP, no replay** — the same rule that invalidated M3-PI1V, applied here to WA1's own first trial.

- The failure was a WA1 implementation defect (validator/payload inconsistency), not a provenance or leakage problem.
- The preregistration (parent audit, W-support inventory, 9-pair candidate pool, 8-candidate manifest, seeds, contracts) was frozen before outcomes and remains valid; a successor stage may re-preregister the same design under a fresh namespace without reusing the consumed trial identity or seed.
- No PI1V invalid data was used; the 70-state reserve is untouched; VALUE / RARITY / M3-Q stay BLOCKED.

FULL REGRESSION:
1925 passed, 3 warnings in 313.59s (0:05:13)

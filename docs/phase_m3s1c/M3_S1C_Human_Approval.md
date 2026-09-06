# M3-S1C Human Approval

- Date: 2026-09-06 (preregistration freeze; before any S1C simulator call).
- All preregistration gates PASS: PARENT_AUDIT / RESERVE_FIREWALL / EXPOSURE_AUDIT /
  PANEL_AUDIT / SEED_AUDIT / PATH_PREFLIGHT / SCHEMA_PREFLIGHT / PREREG_HASH_LOCK.
- Preregistration package committed with EXECUTION_AUTHORIZED = NO.

## Authorization record

- Independent live Git audit of remote commit
  `509a266fbf95205e926096399bee43901fe765cc` (prereg amendment) has PASSED.
- Explicit human authorization received on 2026-09-06: "M3-S1C EXECUTION
  AUTHORIZATION: APPROVED."
- Scope: the frozen M3-S1C protocol only — 24 untouched states (8 W / 8 S /
  8 ND), 8 replicates/state, 20,000 gradient samples/trial, 192 trials,
  3.84M total samples, S1 threshold 5.4417199447782; NO V1 probe, NO
  threshold search, NO top-up, NO panel/seed substitution.  Before trial 1
  all prereg hashes must reverify and the execution destination must be
  empty.  If sampling begins for any trial and durable COMPLETE fails:
  M3-S1C-X => STOP => NO REPLAY => NO SAME-STAGE RERUN.  Evaluate (truth
  unseal + frozen primary gates) only after 192/192 durable COMPLETE with
  0 consumed-invalid.  VALUE / RARITY / M3-Q remain untouched (BLOCKED).

EXECUTION_AUTHORIZED: YES
AUTHORIZER: Human
AUTHORIZATION_DATE: 2026-09-06

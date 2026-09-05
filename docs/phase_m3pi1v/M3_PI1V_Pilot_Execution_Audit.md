# M3-PI1V Pilot Execution Audit

Status: **COMPLETE**.

- Trials expected 192, complete 192, consumed-invalid 0.
- Gradient samples 3,840,000; BASE probe 1,920,000; selected-action probe 1,920,000; saved by invalid gradients 0; total 7,680,000 (<=2x budget: True).
- Opposite-action probe samples: 0 (frozen assert = 0).
- Every trial was written transactionally (STARTED -> temp -> fsync -> schema validation -> sha256 -> atomic rename -> parent-dir fsync -> final hash verify -> COMPLETE).
- Persistence audit: canonical hashes PASS, consumed-invalid 0.

## Infrastructure incidents (full transparency)

Two pre-evidence infrastructure incidents occurred and are documented in `results/phase_m3pi1v/summary/m3pi1v_persistence_incident_audit.json`:

1. **Attempt-1 persistence abort.** The first execution consumed 3,840,000 gradient + 3,840,000 probe samples but could commit no record: the trial identity contained `::`, which is illegal in Windows temp-file names, and the STARTED ledger entry was written after sampling instead of before. All 192 attempt-1 trials were quarantined under `results/phase_m3pi1v/quarantine_attempt1` (192 STARTED + 192 CONSUMED_INVALID, 0 COMPLETE) and never used by any analysis.
2. **Post-pilot prereg-audit rewrite + forensic restore.** A defensive prepare re-run rewrote seven pre-pilot audit files (recorded_at only) before failing its own seed self-collision check; the original timestamps were forensically recovered so every frozen prereg hash verifies again.

The authoritative pilot (attempt 2) replays the same frozen seed plan deterministically -- the reset introduced zero researcher degrees of freedom, no protected state was touched, and no durable evidence from attempt 1 exists.

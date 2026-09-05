# M3-PI1VR0 Incident Forensics

Status: **COMPLETE** (forensics only; nothing was rewritten into a primary run).

- Attempt 1: 192 scientific trials started, 0 durable COMPLETE, 192 CONSUMED_INVALID.
  - Filename root cause: trial identifier contained "::"; Windows temporary filenames cannot contain ':' (OSError 22 at temp-file creation).
  - Sequencing violation: STARTED ledger entry was written inside the write path, after scientific sampling, instead of before each trial.
- Attempt 2: same-seed deterministic replay, 192/192 persisted, **diagnostic only**.
- Valid verdict: **PI1V-X**. Attempt-2 outputs may not freeze thresholds, declare primary results, choose budgets, or authorize confirmation.
- Repair: `src/hyptraj/m3pi1vr0/persistence.py` implements the frozen 12-step contract with filesystem-safe ids and STARTED-before-simulator ordering.

# M3-S1C Path Preflight

Status: **PASS** (live, 2026-09-06T09:56:00+0800).

- 192/192 trial paths PASS under the inherited bounded-path
  contract (slug <= 64, temp basename <= 76,
  run uuid <= 32, full path <= 220).
- max final path = 147; max temp path = 198.
- Over-limit failures occur strictly BEFORE any scientific simulator call.

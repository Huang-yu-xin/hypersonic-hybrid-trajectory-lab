# M3-S25-R1-A2R-B0.5 Amendment Record — Arm-B execute-route repair
(zero sampling)

**Date:** 2026-09-09
**Authorization base:** `3f866942df16c1e2592cdbf2b7a237144c14bedb`
**Nature:** mechanical repair of the Arm-B execution route; **no
scientific simulator call, no sample consumed**
**Status:** gate `M3_S25_R1_A2R_ARM_B_AUTHORIZED` returned to **NO**;
STOP for re-audit and re-authorization

---

## 1. What happened

The human Arm-B authorization of 2026-09-09 (commit `3f86694`, the
single change `M3_S25_R1_A2R_ARM_B_AUTHORIZED: NO -> YES`) was presented
for execution as

```
python scripts/run_m3s25r1.py arm_b_execute
```

The frozen pre-sampling gates ran first and **PASSED**:

```
B0 center artifacts verified: PASS (269 inherited + 691 A2R = 960
    centers, effective_samples=19200000)
B0 runtime plan verified: PASS
```

The runner then aborted inside the side-trial loop **before the first
scientific simulator call**:

```
NameError: name 'math' is not defined
    scripts/run_m3s25r1.py:4037  s2_side = s2_center * math.exp(...)
```

**Nothing was consumed and nothing was persisted.** The B0 trial ledger
does not exist; `results/phase_m3s25r1/arm_b/trials/` holds 0 files; the
960-center / 19,200,000-sample effective center dataset was never opened
for writing (A2R 691 and A1R 270 records unchanged, verified after the
fact). This is therefore **not** a `CONSUMED_INVALID` and **not** a
terminal `M3-S25-R1-A2R-X`: the authorization was never exercised.

---

## 2. The three defects (all mechanical, none scientific)

No Delta, seed, sample count, CRN semantics, feature, model, CV rule or
threshold was involved. Only the wiring of the execution route.

| # | Defect | Effect |
|---|--------|--------|
| 1 | `math` never imported, yet the loop calls `math.exp(-AB.DELTA)` | `NameError` on the first side trial while computing `s2_side` |
| 2 | `run_trial_transactional(uid, rec_p, side_p, B0_LEDGER, _compute, dir_fsync_fn=...)` passes 5 positional args against `(logical_id, final_path, run_simulator, *, ledger_path, pre_hash_validator, ...)` | `TypeError: too many positional arguments` — proven statically with `inspect.signature().bind()` and confirmed by the A2R route, which uses the keyword form |
| 3 | Mandatory `pre_hash_validator` omitted; `_compute` returned a `(record, arrays)` tuple where a **dict** payload is required; the instrumentation sidecar was never written | payload hash assignment would fail on a tuple; no sidecar on disk; `instrumentation_sha256` would stay `null` — a silent loss of the lossless replicate data |

**Why the test suite did not catch it.** Every prior `arm_b_execute`
test was an `inspect.getsource()` source-text assertion (e.g.
`assert "verify_center_artifacts" in src`). The trial loop was never
actually executed under test, so the wiring was never exercised. All
B0.1–B0.4.3 commits are correctly labelled "0 scientific simulator
calls" — which is exactly why the defect survived.

---

## 3. Repair

`scripts/run_m3s25r1.py::arm_b_execute`

1. Added `import math` at module level.
2. Restructured the loop body into `run_side_trial(unit)`, mirroring the
   **proven** A2R route that already completed 691/691 durable trials:
   `run_trial_transactional(uid, rec_p, compute, ledger_path=B0_LEDGER,
   pre_hash_validator=validate, base_entry={...},
   dir_fsync_fn=fsync_directory_bounded_retry)`.
3. Added the mandatory `validate(payload)` (schema / namespace / seed /
   side / samples / Delta / sidecar-hash / truth-leak checks).
4. `compute()` now writes the sidecar first via
   `AB.write_sidecar_transactional(...)` (bounded directory-fsync retry)
   and binds its SHA-256 into the record before the record is hashed and
   persisted; it returns the record **dict**.
5. Fail-closed on `result["status"] != "COMPLETE"`.

Frozen order preserved: `STARTED` → 20,000 samples → sidecar + record →
fsync → atomic rename → bounded directory-fsync retry → durable hash
verification → `COMPLETE`.

No scientific constant was touched: `DELTA = 0.10` in `u = log(s^2)`,
1,920 side trials (960 L + 960 R), 20,000 samples per trial,
38,400,000 budget, top-up 0, substitution 0, center never rerun, CRN
anchor = center seed, center 19,200,000 untouched.

---

## 4. New test coverage (the actual gap)

`tests/test_m3s25r1_b05_execute_route.py` drives the **real** execute
route through the **real** persistence path, with the sampling entry
point `draw_online_pilot` substituted by a deterministic stand-in so the
scientific simulator is never called:

- `test_b05_execute_route_durable_complete` — 2/2 durable `COMPLETE`,
  0 `CONSUMED_INVALID`, sidecar present **and** its hash bound into the
  record, `samples == 20_000`, `delta == 0.10`, L/R share the single
  frozen center CRN seed, and the real result tree is untouched.
- `test_b05_sidecar_failure_leaves_no_complete` — if the sidecar cannot
  be made durable there is **no** `COMPLETE` and a `CONSUMED_INVALID` is
  recorded (fail-closed).
- `test_b05_gate_no_stops_before_any_trial` — with the gate NO nothing
  is written at all.
- `test_b05_real_center_artifacts_verifier_passes` /
  `test_b05_real_runtime_plan_verifier_passes` — the two frozen
  pre-sampling verifiers on the real full artifacts
  (269 + 691 = 960 centers, 19,200,000 samples, manifest SHA pin,
  1920 → 960 L/R CRN topology).
- structural guards pinning the keyword-form call and `import math`.

> Note on the scratch directory: pytest's `tmp_path` exceeds the
> 220-character `FULL_PATH_LIMIT` once the state slug and temp basename
> are appended, and the persistence layer correctly refuses it *before*
> the simulator. The tests therefore use a deliberately short repository
> scratch path (`.b05tmp`, removed by fixture teardown).

---

## 5. Environment finding (recorded for future runs)

| Interpreter | numpy / scipy | sklearn | Can run scientific execution? |
|---|---|---|---|
| `.venv` (3.13.2) | 2.5.2 / 1.18.0 | **absent** | **No** — `import arm_a_eval` fails |
| shell `python` (3.13.12) | — | **absent** | **No** |
| hermes venv (**3.11.15**) | 2.4.6 / 1.17.1 | 1.9.0 | **Yes** — this is what A2R used |

Evidence: `__pycache__/*.cpython-311.pyc`; the A2R evaluation uses
`sklearn.model_selection.GroupKFold`. Switching interpreters would put
the Arm-B side draws on a different numeric stack than the frozen
19,200,000 center samples and could break the bit-exact crosscheck.
**Arm-B execution must use Python 3.11.15.**

---

## 6. Pre-existing hash-lock failure (found while re-running the suite)

Running the full M3-S25-R1 suite surfaced

```
FAILED tests/test_m3s25r1_prereg.py::test_hashlock_and_artifacts_consistent
```

This is **pre-existing, not introduced by B0.5**. The hash manifest pinned
`scripts/run_m3s25r1.py` at `c20ccc90...` (frozen at `618d4a0`, the A2R0
preregistration), while the script at the authorization base `3f86694`
already hashed to `2a0834e8...` — because B0.2 (`c2a7ff5`) added 211 lines
to the runner without refreshing the lock, and B0.4.1–B0.4.3 did the same.

Following the A0.2 precedent ("scientific-code hash lock refreshed"), the
lock was regenerated with `python scripts/run_m3s25r1.py hashlock`:
`PREREG_HASH_LOCK: PASS`, `simulator_calls: 0`, 58 files locked, 0 file
mismatches, 0 code mismatches.

> Follow-up worth doing separately: the stale lock went unnoticed for
> several B0.x amendments because each commit only ran its own new tests
> ("N/N tests PASS") rather than the round-0 suite. The B0.5 real-path
> tests plus this lock refresh restore the invariant.

---

## 7. Current state

- `M3_S25_R1_A2R_ARM_B_AUTHORIZED: NO` (returned from YES; withdrawal
  record appended to `M3_S25_R1_Human_Approval.md`)
- All other gates unchanged and NO: TRUTH, ARM_A, ARM_B, A1R_ARM_A,
  A1R_ARM_B, A2R_ARM_A
- VALUE / RARITY / M3-Q remain BLOCKED
- B0 ledger: absent; B0 side samples: 0 of 38,400,000
- Center effective dataset: 19,200,000 samples, intact
- `arm_b_evaluate` was **not** run

## STOP

Amendment complete. STOP for human re-audit. Do **not** run
`arm_b_execute` or `arm_b_evaluate` until the gate is explicitly
re-authorized.

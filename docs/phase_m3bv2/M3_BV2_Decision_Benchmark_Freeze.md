# M3-BV2 Decision Benchmark Freeze (Axis A)

> **Frozen:** 2026-08-27T16:50:20+00:00 UTC ｜ commit `37d17bc`
> **Status:** 8 WIDEN / 8 HOLD / 8 SHRINK — decision-correctness benchmark; **no adaptive-value claim from this axis**.
> **Seal:** after this freeze: no state replacement, no metric change, no functional change, no margin change, no controller-informed amendment.
> Freeze body sha256: `f3d3a62463757db7f21d3fe2d5dac89655c24738255cdee788c8795fc73215dc`

## Gates

| Gate | Result |
|---|---|
| D0 validity (BV-v0 tag, task/lock-before-science, source hashes, legality, M2=sum L, no controller leakage) | PASS (see B2 reuse record + test suite) |
| D1 diversity 8/8/8 | True |
| D2 stability >= 0.80 every state + HOLD indifference rule | True |
| config coverage (>=4 configs/class, <=2 states/config/class) | True |

## Selected states (24)

| config | s2 | state_id | class | margin | stability |
|---|---|---|---|---|---|
| m1d_b20260827_c000 | 0.65 | c000_s2_00065 | WIDEN | 0.5967159946241739 | 1.0 |
| m1d_b20260827_c000 | 0.85 | c000_s2_00085 | WIDEN | 0.39500593031443776 | 1.0 |
| m1d_b20260827_c000 | 3 | c000_s2_00300 | HOLD | 0.010302967994354022 | 1.0 |
| m1d_b20260827_c000 | 6.4 | c000_s2_00640 | SHRINK | 0.1250997087469075 | 1.0 |
| m1d_b20260827_c000 | 8 | c000_s2_00800 | SHRINK | 0.14617335659281044 | 1.0 |
| m1d_b20260827_c001 | 0.65 | c001_s2_00065 | WIDEN | 0.45612285653899864 | 1.0 |
| m1d_b20260827_c001 | 0.85 | c001_s2_00085 | WIDEN | 0.49547240734474113 | 1.0 |
| m1d_b20260827_c001 | 3 | c001_s2_00300 | HOLD | 0.008984891584846076 | 1.0 |
| m1d_b20260827_c001 | 6.4 | c001_s2_00640 | SHRINK | 0.1445359682272961 | 1.0 |
| m1d_b20260827_c001 | 8 | c001_s2_00800 | SHRINK | 0.16494870266368278 | 1.0 |
| m1d_b20260827_c004 | 0.65 | c004_s2_00065 | WIDEN | 0.3751315316087779 | 1.0 |
| m1d_b20260827_c004 | 0.85 | c004_s2_00085 | WIDEN | 0.31389779254979766 | 1.0 |
| m1d_b20260827_c004 | 2.3 | c004_s2_00230 | HOLD | -0.00045317988334909505 | 1.0 |
| m1d_b20260827_c004 | 3 | c004_s2_00300 | HOLD | -0.009140826145898076 | 1.0 |
| m1d_b20260827_c004 | 6.4 | c004_s2_00640 | SHRINK | 0.14249352934576084 | 1.0 |
| m1d_b20260827_c004 | 8 | c004_s2_00800 | SHRINK | 0.16548435181935647 | 1.0 |
| m1d_b20260827_c006 | 0.65 | c006_s2_00065 | WIDEN | 0.2454047990295118 | 1.0 |
| m1d_b20260827_c006 | 0.85 | c006_s2_00085 | WIDEN | 0.18664850797042057 | 1.0 |
| m1d_b20260827_c006 | 2.3 | c006_s2_00230 | HOLD | -0.007615944918853166 | 1.0 |
| m1d_b20260827_c006 | 3 | c006_s2_00300 | HOLD | -0.0003631176637201455 | 1.0 |
| m1d_b20260827_c006 | 6.4 | c006_s2_00640 | SHRINK | 0.0664841997548112 | 1.0 |
| m1d_b20260827_c006 | 8 | c006_s2_00800 | SHRINK | 0.06883022761900166 | 1.0 |
| m1d_b20260827_c007 | 3 | c007_s2_00300 | HOLD | 0.004117791132540385 | 1.0 |
| m1d_b20260827_c010 | 3 | c010_s2_00300 | HOLD | -0.00043829678092966107 | 1.0 |

## Semantics

- Eligibility: frozen label (statistical support + direction margin >= 0.05) AND headline stability >= 0.80; HOLD adds the frozen +/-3% indifference + headline +/-5% rule.
- Selection: deterministic, coverage-aware, config_id ascending, (stability desc, margin desc, s2 asc) — verbatim replay of the BV-v0 locked rule (cross-check identical).
- Budgets: reference 500k/arm x 20 CRN batches (prior characterization, B2 reuse); headline 100k/arm x 8 matched replicates.
- Controller runs on BV2: **0**.

# M3-BV2 Value Benchmark Freeze (Axis B)

> **Frozen:** 2026-08-27T16:50:20+00:00 UTC ｜ commit `37d17bc`
> **Status:** 12 WIDEN / 12 SHRINK — adaptive-value benchmark; Oracle feasibility PASS required before this freeze.
> **Seal:** after this freeze: no state replacement, no metric change, no functional change, no margin change, no controller-informed amendment.
> Freeze body sha256: `61ce24d2f512639e0a66eb6f7a8f15233a473035ba91d472677c04d5bb03052e`

## Unified functional

```
J(pi) = median_state [ median_replicate log( M2(pi) / M2(BASE) ) ]
BestFixed = argmin f in {ALWAYS_WIDEN, ALWAYS_SHRINK, ALWAYS_HOLD} J(f)
G_Oracle = J(BestFixed) - J(Oracle)
```

## Gates

| Gate | Result |
|---|---|
| V0 validity (12W/12S deterministic, legal, stable, margin >= 0.05, coverage, no controller) | True |
| V1 fixed-rule tradeoff (diagnostic; weak flag = one fixed rule dominates both classes) | weak flag = False |
| V2 Oracle feasibility (G_Oracle >= -log(0.95)) | True |
| V3 opposite-class regret (R_opp,W / R_opp,S >= 1.05) | True |

BestFixed = **ALWAYS_WIDEN**; J(BestFixed) = -0.014791;
J(Oracle) = -0.068943; G_Oracle = 0.054152;
equivalent ratio exp(-G) = 0.94729 (threshold 0.95).

Opposite-class regret: R_opp,W = **1.3472**,
R_opp,S = **1.1268** (threshold 1.05).

## Selected states (24)

| config | s2 | state_id | class | margin | stability |
|---|---|---|---|---|---|
| m1d_b20260827_c000 | 0.65 | c000_s2_00065 | WIDEN | 0.5967159946241739 | 1.0 |
| m1d_b20260827_c000 | 0.85 | c000_s2_00085 | WIDEN | 0.39500593031443776 | 1.0 |
| m1d_b20260827_c000 | 1.1 | c000_s2_00110 | WIDEN | 0.33106818182146935 | 1.0 |
| m1d_b20260827_c001 | 0.65 | c001_s2_00065 | WIDEN | 0.45612285653899864 | 1.0 |
| m1d_b20260827_c001 | 0.85 | c001_s2_00085 | WIDEN | 0.49547240734474113 | 1.0 |
| m1d_b20260827_c001 | 1.1 | c001_s2_00110 | WIDEN | 0.35155073950421645 | 1.0 |
| m1d_b20260827_c004 | 0.65 | c004_s2_00065 | WIDEN | 0.3751315316087779 | 1.0 |
| m1d_b20260827_c004 | 0.85 | c004_s2_00085 | WIDEN | 0.31389779254979766 | 1.0 |
| m1d_b20260827_c004 | 1.1 | c004_s2_00110 | WIDEN | 0.24910598532332087 | 1.0 |
| m1d_b20260827_c006 | 0.65 | c006_s2_00065 | WIDEN | 0.2454047990295118 | 1.0 |
| m1d_b20260827_c006 | 0.85 | c006_s2_00085 | WIDEN | 0.18664850797042057 | 1.0 |
| m1d_b20260827_c006 | 1.1 | c006_s2_00110 | WIDEN | 0.14621147711822985 | 1.0 |
| m1d_b20260827_c000 | 5 | c000_s2_00500 | SHRINK | 0.0975415885122164 | 1.0 |
| m1d_b20260827_c000 | 6.4 | c000_s2_00640 | SHRINK | 0.1250997087469075 | 1.0 |
| m1d_b20260827_c000 | 8 | c000_s2_00800 | SHRINK | 0.14617335659281044 | 1.0 |
| m1d_b20260827_c001 | 5 | c001_s2_00500 | SHRINK | 0.10469278200170647 | 1.0 |
| m1d_b20260827_c001 | 6.4 | c001_s2_00640 | SHRINK | 0.1445359682272961 | 1.0 |
| m1d_b20260827_c001 | 8 | c001_s2_00800 | SHRINK | 0.16494870266368278 | 1.0 |
| m1d_b20260827_c004 | 5 | c004_s2_00500 | SHRINK | 0.11940911037165165 | 1.0 |
| m1d_b20260827_c004 | 6.4 | c004_s2_00640 | SHRINK | 0.14249352934576084 | 1.0 |
| m1d_b20260827_c004 | 8 | c004_s2_00800 | SHRINK | 0.16548435181935647 | 1.0 |
| m1d_b20260827_c006 | 5 | c006_s2_00500 | SHRINK | 0.05497584587682052 | 1.0 |
| m1d_b20260827_c006 | 6.4 | c006_s2_00640 | SHRINK | 0.0664841997548112 | 1.0 |
| m1d_b20260827_c006 | 8 | c006_s2_00800 | SHRINK | 0.06883022761900166 | 1.0 |

## Semantics

- No HOLD states by design; ALWAYS_HOLD remains a fixed comparator (J(ALWAYS_HOLD) = 0 by construction).
- Eligibility: frozen label WIDEN/SHRINK (statistical support + direction margin >= 0.05 embedded) AND headline stability >= 0.80.
- Selection: deterministic (task Sec. 13/14), coverage >= 4 configs/class, <= 3 states/config/class; Oracle feasibility checked AFTER selection; no manual headroom selection.
- Budgets: reference 500k/arm x 20 CRN batches (prior characterization, B2 reuse); headline 100k/arm x 8 matched replicates.
- Controller runs on BV2: **0**.

# M3-DS Directional Selection Audit (DS-1)

Zero-simulator. Source: `results/phase_m3d2/summary/m3d2_confirmation_summary.json`
(sha256 locked in `m3ds_source_manifest.json`). No reference simulator data
was regenerated: D2 confirmed states already passed corrected event
semantics, the full-event probability domain, independent confirmation and
the frozen corrected classifier.

## Candidate universe

Only independently confirmed corrected D2 states are eligible:

```text
WIDEN  = 12
SHRINK = 10
```

Forbidden as primary directional evidence: D3 discovery-only W/S, D2
discovery-only W/S, historical remote pre-ER1 states. `invalid = 0` in the
directional pool.

## Deterministic selection rule (taskbook section 10)

Applied per class, lexicographic greedy key:

1. maximize distinct config coverage (uncovered config preferred)
2. prefer greater s2 spacing from already selected states
3. prefer stronger independent-confirmation support margin
   (`class_certainty_score`)
4. prefer larger absolute directional effect (`|r_w|` for WIDEN,
   `|r_s|` for SHRINK; `r = M2(arm)/M2(base) - 1`)
5. lexical `state_id` tie-break

No future controller score, regret or VRF participates. The rule is frozen
in `src/hyptraj/m3ds/selection.py` before any controller experiment.

## Selected primary (8 WIDEN / 8 SHRINK)

| class | selected | distinct configs | strata | s2 span |
|---|---|---|---|---|
| WIDEN | 8 | 5 (c000, c001, c004, c010, c020) | G-W, G-H | 1.25 - 2.5 |
| SHRINK | 8 | 5 (c000, c001, c004, c010, c020) | G-H, G-S | 4.0 - 8.0 |

Diversity gate: `>= 4 distinct configs` per class PASS; `>= 2 strata` per
class PASS; selected s2 sets cover the full candidate span per class.

Full per-state ranks and reasons:
`results/phase_m3ds/summary/m3ds_directional_candidates.csv` and
`m3ds_directional_selected.csv`; machine audit:
`m3ds_directional_selection_audit.json`.

## Directional Reserve / Stress Set (frozen)

```text
reserve WIDEN  = 4 : c001_s2_00250, c010_s2_00200, c020_s2_00200, c020_s2_00250
reserve SHRINK = 2 : c001_s2_00800, c020_s2_00640
```

Policy: future robustness only; forbidden for controller tuning. Locked in
`m3ds_benchmark.json.directional_reserve`.

## Gate M3DS-DIR-1

```text
selected WIDEN = 8            PASS
selected SHRINK = 8           PASS
invalid = 0                   PASS
diversity gate                PASS
source lock                   PASS
=> M3DS-DIR-1                 PASS  (Directional Axis constructible)
```

## Axis A reference labels

Axis A ground truth is exactly {WIDEN, SHRINK}, inherited from the
high-budget corrected reference classifier. ABSTAIN never appears as an
Axis A ground-truth label.

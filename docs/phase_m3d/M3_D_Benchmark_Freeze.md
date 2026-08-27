# M3-D Benchmark Freeze — 24 Sign-Diverse Proposal States

> **Schema:** `raretopo-m3d-benchmark-freeze-v0` ｜ **Date:** 2026-08-27 ｜ **Seal:** permanent after this commit
> **Commit discipline:** this freeze is committed BEFORE any online adaptive trial (task Sec. 12/42)
> **Freeze hash:** `b613f45dc6645c6d…`

## Selection (verbatim rule, zero substitutions)

`eligible = oracle_action ∈ {WIDEN, SHRINK, HOLD}; sort by (config_id, s²) ascending within class; FIRST 8.`

| class | states (config@s² in rank order) |
|---|---|
| WIDEN | c000@0.55, c000@0.7, c000@0.85, c000@1, c000@1.25, c000@1.6, c000@2, c001@0.7 |
| SHRINK | c000@4, c000@5, c000@6.4, c000@8, c001@4, c001@5, c001@6.4, c001@8 |
| HOLD | c000@3.2, c001@3.2, c004@2.5, c006@2.5, c006@3.2, c007@2.5, c007@3.2, c010@3.2 |

## Per-state margins & reference uncertainty

| class | state | Δ_dir | rel SE base | ratios S/B, W/B |
|---|---|---:|---:|---|
| WIDEN | c000@0.55 | 0.622 | 0.0538 | +0.2571 / -0.2252 |
| WIDEN | c000@0.7 | 0.434 | 0.0215 | +0.2068 / -0.1585 |
| WIDEN | c000@0.85 | 0.437 | 0.0139 | +0.2198 / -0.1513 |
| WIDEN | c000@1 | 0.377 | 0.0134 | +0.1902 / -0.1359 |
| WIDEN | c000@1.25 | 0.253 | 0.0075 | +0.1315 / -0.0973 |
| WIDEN | c000@1.6 | 0.192 | 0.0051 | +0.1091 / -0.0695 |
| WIDEN | c000@2 | 0.118 | 0.0058 | +0.0726 / -0.0403 |
| WIDEN | c001@0.7 | 0.517 | 0.0262 | +0.2458 / -0.1789 |
| SHRINK | c000@4 | 0.056 | 0.0059 | -0.0183 / +0.0366 |
| SHRINK | c000@5 | 0.095 | 0.0048 | -0.0377 / +0.0538 |
| SHRINK | c000@6.4 | 0.127 | 0.0054 | -0.0538 / +0.0666 |
| SHRINK | c000@8 | 0.145 | 0.0049 | -0.0620 / +0.0736 |
| SHRINK | c001@4 | 0.060 | 0.0054 | -0.0188 / +0.0399 |
| SHRINK | c001@5 | 0.099 | 0.0047 | -0.0385 / +0.0568 |
| SHRINK | c001@6.4 | 0.142 | 0.0038 | -0.0593 / +0.0744 |
| SHRINK | c001@8 | 0.162 | 0.0062 | -0.0690 / +0.0822 |
| HOLD | c000@3.2 | 0.006 | 0.0052 | +0.0055 / +0.0167 |
| HOLD | c001@3.2 | 0.009 | 0.0060 | +0.0087 / +0.0160 |
| HOLD | c004@2.5 | 0.010 | 0.0046 | +0.0120 / +0.0098 |
| HOLD | c006@2.5 | 0.000 | 0.0115 | +0.0134 / +0.0002 |
| HOLD | c006@3.2 | -0.000 | 0.0095 | -0.0000 / +0.0108 |
| HOLD | c007@2.5 | -0.007 | 0.0142 | +0.0187 / -0.0066 |
| HOLD | c007@3.2 | 0.005 | 0.0094 | +0.0049 / +0.0065 |
| HOLD | c010@3.2 | 0.001 | 0.0051 | +0.0134 / +0.0014 |

## Artifacts referenced

- `results/phase_m3d/reference/m3d_candidate_pool.json` sha256 `50b48ddf4fc32f5c…` (56 reference states)
- `results/phase_m3d/reference/m3d_candidate_pool_extension1.json` sha256 `3816186805963cb8…` (48 reference states)

## Seal

After the commit of this freeze the 24-state benchmark is permanently closed: no further amendment, no state deletion, no threshold change, no benchmark adjustment informed by Gradient outcomes (operator directive 2026-08-27).

# M3-D3-2 Boundary-Focused `s2` Discovery Verdict

## Frozen execution record

- Human approval for the D3-1 preregistration was recorded before any
  simulator call.
- The preregistration source-hash lock, candidate identity audit, seed audit,
  full-event semantics check, and D2 classifier-equivalence check passed.
- Exactly 14 locked candidates across five configurations were evaluated once,
  each with three arms, 100,000 samples per arm, and 20 paired CRN batches.
- Actual discovery simulator samples: 4,200,000.  There was no adaptive
  sampling, controller trial, or rarity-shift execution.

## Result

| Class | New states |
| --- | ---: |
| WIDEN | 1 |
| HOLD | 2 |
| SHRINK | 1 |
| AMBIGUOUS | 10 |
| INVALID | 0 |

`M3D3-DISC-1` required at least 10 new provisional HOLD states.  The observed
count was 2.  The resulting discovery verdict is therefore:

```text
D3-DISC-B — PROVISIONAL HOLD INSUFFICIENT
```

No confirmation shortlist was created.  Under the frozen protocol, this is
negative evidence for the targeted boundary-enrichment hypothesis and requires
human scientific review before any new M3-D3 direction can be considered.

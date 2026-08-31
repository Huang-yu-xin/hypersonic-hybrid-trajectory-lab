# M4-PF3-A Discovery Safety Freeze

The locked two-state implementation discovery passed without a protocol
change.

| State | Class | `A_alloc` | Weight TV | Logit-step norm | Minimum ESS | Maximum normalized weight |
|---|---|---:|---:|---:|---:|---:|
| `c006_s2_00110` | WIDEN | 0.243484 | 0.011468 | 0.20 | 1295.87 | 0.003968 |
| `c006_s2_00500` | SHRINK | 0.264927 | 0.011468 | 0.20 | 1366.47 | 0.002863 |

Both states passed finite-weight, support, positive-weight, simplex and CRN
draw-order checks. There were no fallbacks. Discovery did not change
`eta_alpha`, the arms, state set, seed lock, confirmation budget, success gates
or cost accounting.

Locked artifact hashes:

- discovery record:
  `f7b05c63312b6cd7819aab668d379a3ec3681d5e9803dfa1d882e9d4985495e1`
- WIDEN construction archive:
  `1411ffe0643988f2238080bca0c7e1ee602a8abc7647860149b7abe06714e675`
- SHRINK construction archive:
  `508fd82ee6e52d7e50bca8ae54ee0ad21971c39d9ec5f5a324ed672b1f03e837`

The confirmatory protocol remains the preregistered Route-A protocol committed
before discovery.

# ER-1 Supersession Ledger

Historical tags are immutable.  “Pending revalidation” means the tag remains
inspectable but its event-dependent scientific conclusions cannot authorize a
child stage.

| Historical tag | Status | Corrected tag | Reason |
|---|---|---|---|
| `RareTopo-M2-v0` | VALID | — | authoritative `S0` nominal semantics used |
| `RareTopo-M3-v0` | SUPERSEDED / PENDING REVALIDATION | — | first contaminated empirical event mask |
| `RareTopo-M3-D-v0` | SUPERSEDED / PENDING REVALIDATION | — | direct contaminated event mask and contaminated parent |
| `RareTopo-M3-G-v1` | SUPERSEDED / PENDING REVALIDATION | — | event-dependent gradient and action evidence |
| `RareTopo-M3-BV-v0` | SUPERSEDED / PENDING REVALIDATION | — | contaminated M3-D value evidence |
| `RareTopo-M3-BV2-v0` | SUPERSEDED / PENDING REVALIDATION | — | contaminated matched controller evaluation |
| `RareTopo-M3-CA-v0` | SUPERSEDED / PENDING REVALIDATION | — | artifact-only derivation from contaminated BV2 |
| `RareTopo-M4-PF0-v0` | PARTIALLY VALID | — | theory/SPD algebra valid; empirical application pending |
| `RareTopo-M4-PF1-v0` | SUPERSEDED / PENDING REVALIDATION | — | direct contaminated event mask |
| `RareTopo-M4-PF2-0-v0` | SUPERSEDED / PENDING REVALIDATION | — | contaminated parent gradient evidence |
| `RareTopo-M4-PF2-v0` | SUPERSEDED / PENDING REVALIDATION | — | direct contaminated event mask and final evaluations |
| `RareTopo-M4-PF3-0-v0` | SUPERSEDED / PENDING REVALIDATION | — | contaminated variance-mass diagnostics |
| `RareTopo-M4-PF3-v0` | SUPERSEDED / PENDING REVALIDATION | — | direct contaminated event mask and final evaluations |

The machine-readable ledger is
`results/evidence_repair/summary/er1_supersession_ledger.json` and will be
updated only for stages that remain authorized after corrected parent gates.

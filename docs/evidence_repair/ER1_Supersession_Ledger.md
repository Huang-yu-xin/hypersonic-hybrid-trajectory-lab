# ER-1 Supersession Ledger

Historical tags are immutable and remain inspectable. Corrected tags are new
evidence freezes; they do not replace or move the old tag objects.

| Historical tag | Status | Corrected tag | Reason |
|---|---|---|---|
| `RareTopo-M2-v0` | VALID | — | last clean frozen empirical parent |
| `RareTopo-M3-v0` | SUPERSEDED | `RareTopo-M3-v2` | corrected replay changes event-dependent metrics; VRF reference semantics are invalid; only M3-D remains authorized |
| `RareTopo-M3-D-v0` | SUPERSEDED | `RareTopo-M3-D-v1` | corrected state composition fails the exact 8/8/8 reference gate |
| `RareTopo-M3-G-v1` | SUPERSEDED / BLOCKED | — | corrected M3-D does not authorize replay |
| `RareTopo-M3-BV-v0` | SUPERSEDED / BLOCKED | — | corrected M3-D does not authorize replay |
| `RareTopo-M3-BV2-v0` | SUPERSEDED / BLOCKED | — | corrected M3-D does not authorize replay |
| `RareTopo-M3-CA-v0` | SUPERSEDED / BLOCKED | — | inherited scientific verdict lacks a corrected BV2 parent |
| `RareTopo-M4-PF0-v0` | PARTIALLY VALID / BLOCKED | — | theory and SPD algebra survive; empirical application is unauthorized |
| `RareTopo-M4-PF1-v0` | SUPERSEDED / BLOCKED | — | corrected upstream parent failed |
| `RareTopo-M4-PF2-0-v0` | SUPERSEDED / BLOCKED | — | corrected upstream parent failed |
| `RareTopo-M4-PF2-v0` | SUPERSEDED / BLOCKED | — | diagnostic raw reanalysis cannot restore missing final evaluation |
| `RareTopo-M4-PF3-0-v0` | SUPERSEDED / BLOCKED | — | no corrected PF2 parent authorizes routing |
| `RareTopo-M4-PF3-v0` | SUPERSEDED / BLOCKED | — | diagnostic raw reanalysis cannot create a corrected PF3 parent |

No corrected tag exists after M3-D because the old lineage stopped at its
reference gate. `RareTopo-M3-v1` is an immutable intermediate repair snapshot
superseded by `RareTopo-M3-v2`. M5-AR and M3-Q remain blocked.

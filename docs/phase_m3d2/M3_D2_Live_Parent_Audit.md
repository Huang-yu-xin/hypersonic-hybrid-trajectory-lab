# M3-D2 Live Parent Audit

Date: 2026-08-31 (Asia/Shanghai)

## Live Git state before D2 scientific work

- Starting branch: `feature/evidence-repair-event-semantics`
- Starting HEAD: `d7575c51fc0c14e88753ffb0208ef5885df76164`
- D2 branch: `feature/phase-m3d2-corrected-sign-diverse-benchmark`
- Working tree: tracked files clean; 15 pre-existing untracked paths were present.
- Preservation rule: the pre-existing untracked archives and figure directories are user-owned, remain untouched, and are excluded from every M3-D2 commit.

## Required parent tags

| Tag | Annotated tag object | Peeled commit | Status |
|---|---|---|---|
| `RareTopo-M2-v0` | `2267290323b91824232059b0b53d2e7b8d6bd970` | `0a00f4459609f712aa76dc4d14349d9cd0d58fc9` | verified |
| `RareTopo-M3-v2` | `94ec7e0baa22888c2ec4bf36fbcdd8a3fd4caab8` | `f30e8bf52d69fb6327df7fa1487347f193543f22` | verified |
| `RareTopo-M3-D-v1` | `eb0f4940344c8d1ea0a85eb7a278cfb2dfba8863` | `8204819bb3c5230f5940f410056cf43b8e44b89b` | verified |
| `RareTopo-ER1-v0` | `2f0ed46e7992f02bb64836ddb681f3fd9a6415b5` | `d7575c51fc0c14e88753ffb0208ef5885df76164` | verified |

Historical tags were inspected with `git tag --list` and `git show-ref --tags --dereference`; no tag was moved or deleted.

## Required ER-1 evidence

- `docs/evidence_repair/ER1_Final_Corrected_Lineage_Report.md`: present; declares schema-2 event membership as `topology != S0` and the valid frontier as corrected M3 plus the negative corrected M3-D gate.
- `docs/evidence_repair/ER1_Supersession_Ledger.md`: present; records `RareTopo-M2-v0` as the last clean empirical parent and supersedes historical M3/M3-D evidence with the corrected tags.
- `docs/evidence_repair/ER1_Event_Semantics_Contract.md`: present.

## Full regression

Command: `pytest -q`

Result:

```text
1363 passed, 3 warnings in 361.28s
exit code 0
```

The three warnings are the existing pytest class-scoped-fixture deprecation warnings in the H3 test suite. No M3-D2 scientific simulation had been run when this audit was recorded.

## D2-0 verdict

`PASS` — required parent evidence is available, the live regression matches the ER-1 closing expectation, and scientific work may proceed on the dedicated D2 branch.

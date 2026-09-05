# M3-WA1R Final Report

**Verdict: WA1R-B**

The recovery executed validly and restored durable corrected high-budget reference evidence, but the combined fresh W pool cannot satisfy exact W=8 with >=6 distinct configs at max 2/config: retiring the consumed config-000 candidate caps the config ceiling at 5. No adaptive third augmentation inside WA1R; a broader W-reference expansion requires separate preregistration.

- WA1 remains WA1-X; consumed candidate reused = NO; all old WA1 seeds retired.
- Recovery reference: 8/8 complete, labels {'AMBIGUOUS': 0, 'HOLD': 0, 'INVALID': 0, 'SHRINK': 0, 'WIDEN': 8}.
- Persistence: hash contract PASS, ledger 8 COMPLETE / 0 consumed-invalid.
- W feasibility: exact-8 False, configs>=6 False, max2/config False.
- V1/S1: no decision made; PI1V Attempt-2 remains diagnostic only.
- VALUE / RARITY / M3-Q: BLOCKED.

FULL REGRESSION:
1973 passed, 3 warnings in 311.21s (0:05:11)

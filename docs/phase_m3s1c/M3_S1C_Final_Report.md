# M3-S1C Final Report

Verdict: **M3-S1C-B** (recorded 2026-09-06T10:18:39+0800).

- Trials: 192/192 durable COMPLETE,
  0 consumed-invalid.
- Budget: 3,840,000 gradient samples; probe = 0; V1 = 0.
- Frozen threshold = 5.4417199447782 (no search, no retune).

## Primary gates (frozen)

| metric | value | gate | pass |
|---|---|---|---|
| wrong direction rate | 0.000000 | <= 0.05 | True |
| deployable coverage | 0.828125 | >= 0.75 | True |
| ND unsafe rate | 0.296875 | <= 0.2 | False |

- FULL_PASS = **False**.
- Direction sanity (Sign-No-Abstain, all 128 W/S trials): wrong = 0,
  invalid gradient trials = 2.
- Descriptive uncertainty only (never a gate): coverage Wilson 95% CI
  [0.7534600319269827, 0.8836688405185272]; unsafe [0.19905151325539794, 0.41770201103542925]; wrong [0.0, 0.029136956273508416].

## Scientific claim boundary

S1 development result did not independently confirm under the frozen threshold/gates (M3-S1C-B, a valid negative result). No threshold retune, no subset selection, no same-stage rerun is permitted; S1 returns to "development signal not independently confirmed"; any successor (S2/ML-0) requires a new development stage. The confirmation panel is exposed and retired from future confirmation use.

# ER-1 Execution Lock

ER-1 repairs the event-semantics and evidence lineage that caused M5-AR to
stop at commit `ce4b075`.  Historical tags and result directories are
immutable.  ER1–ER5 use zero simulator calls while raw artifacts suffice.
Any replay uses a new output namespace and the original states, seeds,
budgets, hyperparameters and gates.  A child stage runs only if its corrected
parent still authorizes it.  M5-AR and M3-Q remain blocked throughout repair.

The live audit baseline is `1328 passed, 3 warnings`; the historical PF3 tag
still resolves to `dbe730d4a0cf12de253e2f46384d9abc99d9a60e`.

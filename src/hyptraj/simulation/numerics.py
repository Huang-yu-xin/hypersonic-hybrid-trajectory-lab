"""Frozen production numerical configuration selected in Phase C.

The Phase B DEFAULT_SOLVER_CONFIG remains untouched for regression continuity.
Future phases should import PRODUCTION_SOLVER_CONFIG explicitly.
"""

import numpy as np
from .trajectory import SolverConfig

PRODUCTION_SOLVER_CONFIG = SolverConfig(
    method="DOP853",
    rtol=1e-9,
    atol=np.array([1e-4, 1e-11, 1e-7, 1e-11]),
    max_step=20.0,
    dense_output=True,
)

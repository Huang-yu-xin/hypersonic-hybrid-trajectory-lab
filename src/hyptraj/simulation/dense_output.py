"""Opt-in dense-output observation hooks (E0.1 amendment, runtime-only).

The frozen integrators already compute solver dense interpolants
(``solve_ivp(..., dense_output=True)``) but only expose sampled grids and
exact event states.  This module provides the E0.1 observer channel that
lets analysis layers reach the *already computed* continuous solutions
without re-integrating, re-fitting, or modifying physics / events / state
machines / numerical configs / canonical result containers.

Contract (E0.1 amendment, docs/phase_e/comparison_protocol.md):

* the hook is strictly opt-in: integrators call ``add`` only when an
  explicit collector is passed (default ``None`` keeps every existing
  call byte-identical);
* the collected ``solution`` callables are the very objects produced by
  the frozen ``solve_ivp`` calls -- no second integration, no sampled-grid
  cubic spline, no monkeypatch;
* ``DenseSolutionSegment`` is an ephemeral analysis object: it must never
  be serialized to JSON / CSV / pickle or enter any canonical baseline
  artifact, and it is never stored on the frozen result containers.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np

DenseSolutionCallable = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class DenseSolutionSegment:
    """One continuous dense solution segment of a frozen integration.

    Parameters
    ----------
    index
        Stage / segment index in integration order (Qian: 0,1,2 for
        ENTRY_CAPTURE / QEG_GLIDE / GROUND_CONTINUATION; Sanger: the
        ``HybridSegment.index``).
    name
        Stage / segment identifier (mode label for Sanger; mode label for
        Qian stages as well).
    mode
        Physics mode label of the segment.
    t_start, t_end
        Integration time bounds of the segment (``[t_start, t_end]``).
    solution
        The dense callable already produced by the frozen
        ``solve_ivp(dense_output=True)`` call (``OdeSolution.sol``).
    """

    index: int
    name: str
    mode: str
    t_start: float
    t_end: float
    solution: DenseSolutionCallable


class DenseOutputCollector:
    """Observer hook collecting dense solution segments from integrators.

    Integrators append one segment per solved stage via :meth:`add`; the
    collector is purely observational and can never affect integration.
    """

    def __init__(self) -> None:
        self._segments: list[DenseSolutionSegment] = []

    def add(self, segment: DenseSolutionSegment) -> None:
        """Record one dense segment (called by the integrator only)."""
        self._segments.append(segment)

    @property
    def segments(self) -> tuple[DenseSolutionSegment, ...]:
        """Collected segments in integration order (read-only view)."""
        return tuple(self._segments)

    def __len__(self) -> int:
        return len(self._segments)

    def __iter__(self):
        return iter(self._segments)

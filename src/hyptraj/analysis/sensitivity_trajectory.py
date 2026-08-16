"""Phase-F hybrid-regime classification (F0.1 amendment, pure mapping).

Pure, read-only mapping from the structured research-terminal results to
the Phase-F regime taxonomy frozen in
``docs/phase_f/sensitivity_protocol.md`` §8–§9:

* ``classify_qian_regime``  -- Qian terminal kind -> Qian regime label;
* ``classify_sanger_regime`` -- Sanger terminal kind (+ skip count) ->
  Sanger regime label.

Hard constraints (F0.1 §16–§17, §22):

* the classifier NEVER parses RuntimeError / SciPy message text, never
  inspects exceptions and never re-integrates -- the terminal reason must
  come from the structured result only;
* ``success = False`` is NOT uniformly mapped to a failure regime: the
  physical terminals (``GROUND_*``) and the horizon censor map to their
  own regimes;
* ``INVALID_INPUT`` is not produced here: the sweep layer catches the
  ``ValueError`` raised by invalid inputs (e.g. ``K <= 0`` from
  ``ConstantKControl``) and classifies it via the exported constant.
"""

from hyptraj.simulation.qian_research_trajectory import (
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE,
    TERMINAL_MAX_TIME,
    TERMINAL_RTI,
    TERMINAL_SOLVER_FAILURE,
)
from hyptraj.simulation.sanger_research_trajectory import (
    TERMINAL_GRAZING_OR_UNRESOLVED_EVENT,
)
from hyptraj.simulation.sanger_trajectory import (
    TERMINAL_GROUND_BEFORE_SRTI,
    TERMINAL_MAX_SEGMENTS,
    TERMINAL_MAX_TIME as SANGER_TERMINAL_MAX_TIME,
    TERMINAL_SOLVER_FAILURE as SANGER_TERMINAL_SOLVER_FAILURE,
    TERMINAL_SRTI,
)

# ---------------------------------------------------------------------------
# Qian regime labels (F0 protocol §8 + F0.1 amendment §16)
# ---------------------------------------------------------------------------
QIAN_REGIME_RTI = "QIAN_RTI"
QIAN_REGIME_GROUND_BEFORE_CAPTURE = "GROUND_BEFORE_CAPTURE"
QIAN_REGIME_GROUND_AFTER_CAPTURE_BEFORE_RTI = (
    "GROUND_AFTER_CAPTURE_BEFORE_RTI"
)
QIAN_REGIME_CENSORED = "CENSORED"
QIAN_REGIME_NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
QIAN_REGIME_INVALID_INPUT = "INVALID_INPUT"
# F0.1 amendment: near-simultaneous terminal events that cannot be resolved
# within the strict tie tolerance (F0.1 §10) -- a boundary-ambiguous state,
# neither a pure numerical failure nor a censored case.
QIAN_REGIME_BOUNDARY_AMBIGUOUS = "BOUNDARY_AMBIGUOUS"

_QIAN_TERMINAL_TO_REGIME = {
    TERMINAL_RTI: QIAN_REGIME_RTI,
    TERMINAL_GROUND_BEFORE_CAPTURE: QIAN_REGIME_GROUND_BEFORE_CAPTURE,
    TERMINAL_GROUND_AFTER_CAPTURE_BEFORE_RTI: (
        QIAN_REGIME_GROUND_AFTER_CAPTURE_BEFORE_RTI
    ),
    TERMINAL_MAX_TIME: QIAN_REGIME_CENSORED,
    TERMINAL_SOLVER_FAILURE: QIAN_REGIME_NUMERICAL_FAILURE,
    TERMINAL_AMBIGUOUS_SIMULTANEOUS_EVENT: QIAN_REGIME_BOUNDARY_AMBIGUOUS,
}

# ---------------------------------------------------------------------------
# Sanger regime labels (F0 protocol §9)
# ---------------------------------------------------------------------------
SANGER_REGIME_GROUND_BEFORE_SRTI = "GROUND_BEFORE_SRTI"
SANGER_REGIME_CENSORED = "CENSORED"
SANGER_REGIME_NUMERICAL_FAILURE = "NUMERICAL_FAILURE"
SANGER_REGIME_INVALID_INPUT = "INVALID_INPUT"
# F2.1/F3: grazing-limit point that the strict reference must decide
# (reference-confirmed side or SANGER_GRAZING_BOUNDARY marker).
SANGER_REGIME_GRAZING_OR_UNRESOLVED = "GRAZING_OR_UNRESOLVED_EVENT"

_SANGER_TERMINAL_TO_REGIME = {
    TERMINAL_GROUND_BEFORE_SRTI: SANGER_REGIME_GROUND_BEFORE_SRTI,
    SANGER_TERMINAL_MAX_TIME: SANGER_REGIME_CENSORED,
    TERMINAL_MAX_SEGMENTS: SANGER_REGIME_CENSORED,
    SANGER_TERMINAL_SOLVER_FAILURE: SANGER_REGIME_NUMERICAL_FAILURE,
    TERMINAL_GRAZING_OR_UNRESOLVED_EVENT: (
        SANGER_REGIME_GRAZING_OR_UNRESOLVED),
}


def classify_qian_regime(result) -> str:
    """Map a structured Qian result (or its ``terminal_kind``) to a regime.

    Pure mapping on ``terminal_kind`` only; never inspects ``message`` or
    exception text.  An unknown kind raises ``KeyError`` (programming
    error), it is never silently treated as a failure.
    """
    kind = getattr(result, "terminal_kind", result)
    return _QIAN_TERMINAL_TO_REGIME[kind]


def classify_sanger_regime(result, skip_count: int | None = None) -> str:
    """Map a structured Sanger result (or its ``terminal_kind``) to a regime.

    ``skip_count`` (from the frozen ``SangerTrajectoryMetrics.skip_count``)
    is required for an SRTI terminal kind: the compact regime label is
    ``SRTI_N{skip_count}``.  ``max_time`` / ``max_segments`` both map to
    the same computational censor regime -- the horizon is never
    misinterpreted as physical topology.
    """
    kind = getattr(result, "terminal_kind", result)
    if kind == TERMINAL_SRTI:
        if skip_count is None:
            raise ValueError(
                "skip_count is required to classify an SRTI terminal kind; "
                "pass the frozen SangerTrajectoryMetrics.skip_count."
            )
        return f"SRTI_N{int(skip_count)}"
    return _SANGER_TERMINAL_TO_REGIME[kind]

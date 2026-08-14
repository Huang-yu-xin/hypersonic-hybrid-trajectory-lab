"""Trajectory mode semantics (Phase B.5: approved Qian continuous glide)."""

from .continuous_glide import (
    ENTRY_CAPTURE,
    GROUND_CONTINUATION,
    MODES,
    QEG_GLIDE,
    continuous_glide_rhs,
    qeg_lift_fraction,
)

__all__ = [
    "ENTRY_CAPTURE",
    "GROUND_CONTINUATION",
    "MODES",
    "QEG_GLIDE",
    "continuous_glide_rhs",
    "qeg_lift_fraction",
]

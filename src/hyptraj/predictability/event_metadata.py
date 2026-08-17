"""Phase-G0 event-taxonomy metadata freeze (G0 -- no G1 computation).

This module freezes the *event taxonomy* that every Phase-G variational /
hybrid-sensitivity layer (G1 onward) must honour.  It is METADATA ONLY:

* event surfaces, directions, normals, mode transitions, classification,
  reset semantics, saltation requirement and terminal-sensitivity status
  for the two frozen research models (Qian, Sanger);
* pure registry containers; no trajectory integration, no Jacobian, no
  STM, no saltation computation, no FTLE.

Surfaces and directions are NOT re-implemented here: they are pinned to
the frozen simulation factories (``simulation/events.py``,
``simulation/sanger_events.py``).  Where the frozen code already exposes
a primitive (``atmosphere_interface_normal``) that primitive is REUSED.
Only metadata that the frozen code does not yet expose -- e.g. the Qian
capture normal ``n = [0, 0, 0, 1]^T`` (surface ``g = gamma``) -- is
recorded here as a frozen convention for the future G1 Jacobian layer.

Source of truth: ``docs/phase_g/predictability_protocol.md`` (G0).
Frozen physical sources: Phase B.5 / C / D / E / F (untouched).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

import numpy as np

from hyptraj.models.parameters import EnvironmentParams
from hyptraj.simulation.sanger_events import atmosphere_interface_normal

# ---------------------------------------------------------------------------
# Frozen implementation state ordering (G0 §4 -- never to be re-ordered by
# Phase-G notation; a display re-ordering must be declared as such).
# ---------------------------------------------------------------------------
STATE_ORDER = ("r", "theta", "v", "gamma")

#: STM convention: rows = output state component, columns = initial
#: perturbation component.  ``Phi_ij = d x_i(t) / d x_0,j``.
STM_ROW_OUTPUT, STM_COL_INITIAL_PERTURBATION = True, True


# ---------------------------------------------------------------------------
# Event classification vocabulary (G0 §6, §22)
# ---------------------------------------------------------------------------
class EventClassification(str, Enum):
    """Frozen event-classification labels (G0 protocol).

    * ``TRUE_HYBRID_MODE_SWITCH`` -- the mode/vector field genuinely
      changes across the event; the state itself is continuous but the
      flow-map derivative requires a saltation update (NEEDS_SALTATION).
    * ``RESEARCH_TERMINAL`` -- the trajectory ends at this event; the
      event-time and terminal-map sensitivities are the objects of study;
      NO post-terminal mode and NO saltation are ever invented.
    * ``DIAGNOSTIC`` -- a trajectory feature event that does not change
      the mode; never eligible for saltation.
    """

    TRUE_HYBRID_MODE_SWITCH = "TRUE_HYBRID_MODE_SWITCH"
    RESEARCH_TERMINAL = "RESEARCH_TERMINAL"
    DIAGNOSTIC = "DIAGNOSTIC"


@dataclass(frozen=True)
class EventTaxonomyEntry:
    """One frozen event-taxonomy row (G0 §6 table).

    ``surface`` is a short symbolic identifier of the frozen root
    function (never a re-implementation); ``direction`` is the crossing
    direction of the frozen event factory; ``normal`` is the unit event
    normal in the frozen ``[r, theta, v, gamma]`` ordering (explicitly
    ``None`` when it belongs to a genuine G1 derivative and is deferred);
    ``reset_is_identity`` records ``x+ = x-`` and ``DR = I``;
    ``saltation`` says whether the first-order hybrid STM update is
    REQUIRED; ``terminal_sensitivity`` says whether the event carries
    event-time / terminal-map sensitivity semantics.
    """

    event: str
    surface: str
    direction: int
    mode_before: str | None
    mode_after: str | None
    classification: EventClassification
    reset_is_identity: bool
    saltation: bool
    terminal_sensitivity: bool
    normal: np.ndarray | None = None
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        """Serializable metadata row (no numpy objects, G0 §21)."""
        return {
            "event": self.event,
            "surface": self.surface,
            "direction": self.direction,
            "mode_before": self.mode_before,
            "mode_after": self.mode_after,
            "classification": self.classification.value,
            "reset_is_identity": self.reset_is_identity,
            "saltation": self.saltation,
            "terminal_sensitivity": self.terminal_sensitivity,
            "normal": (
                None if self.normal is None else [float(v) for v in self.normal]
            ),
            "notes": list(self.notes),
        }


# Frozen constants used ONLY as metadata annotations (G0 §6.1).
_QIAN_CAPTURE_NORMAL = np.array([0.0, 0.0, 0.0, 1.0])


def _qian_capture_event():
    """Direction / hybrid-switch attributes of the FROZEN capture factory."""
    from hyptraj.simulation.events import make_capture_event

    ev = make_capture_event()
    return int(ev.direction), bool(ev.terminal), bool(ev.hybrid_switch)


def _qian_rti_event():
    """Direction / terminal attributes of the FROZEN QEG-end (RTI) factory."""
    from hyptraj.simulation.events import make_qeg_end_event

    ev = make_qeg_end_event(EnvironmentParams(), None, lambda t, s: 3.0)
    return int(ev.direction), bool(ev.terminal)


def _sanger_event_attrs(kind: str) -> tuple[int, bool]:
    """Direction / terminal attributes of the FROZEN Sanger event factories."""
    from hyptraj.simulation.sanger_events import (
        make_atmosphere_entry_event,
        make_atmosphere_exit_event,
        make_pullout_event,
        make_srti_candidate_event,
        make_vacuum_apogee_event,
    )

    env = EnvironmentParams()
    ev = {
        "atmosphere_exit": make_atmosphere_exit_event(env),
        "atmosphere_entry": make_atmosphere_entry_event(env),
        "atmospheric_pullout": make_pullout_event(),
        "vacuum_apogee": make_vacuum_apogee_event(),
        "srti": make_srti_candidate_event(),
    }[kind]
    return int(ev.direction), bool(ev.terminal)


# ---------------------------------------------------------------------------
# Frozen event taxonomy (G0 §6).  Each row is cross-checked against the
# frozen factories by the semantic tests (no re-implementation).
# ---------------------------------------------------------------------------
EVENT_TAXONOMY: tuple[EventTaxonomyEntry, ...] = (
    # ---- Qian -----------------------------------------------------------
    EventTaxonomyEntry(
        event="qian_capture",
        surface="g_c = gamma",
        direction=+1,
        mode_before="ENTRY_CAPTURE",
        mode_after="QEG_GLIDE",
        classification=EventClassification.TRUE_HYBRID_MODE_SWITCH,
        reset_is_identity=True,
        saltation=True,
        terminal_sensitivity=False,
        normal=_QIAN_CAPTURE_NORMAL,
        notes=(
            "x+ = x- but the vector field changes (u_L jumps 1 -> clip(u_L*,0,1));",
            "state continuity does NOT remove the saltation need (G0 §7-§8);",
            "G1 must derive f_minus/f_plus at analysis time from the frozen",
            "RHS primitives (Qian metadata gap recorded in G0 audit).",
        ),
    ),
    EventTaxonomyEntry(
        event="qian_rti",
        surface="L_req - L = 0",
        direction=+1,
        mode_before="QEG_GLIDE",
        mode_after=None,
        classification=EventClassification.RESEARCH_TERMINAL,
        reset_is_identity=False,
        saltation=False,
        terminal_sensitivity=True,
        normal=None,
        notes=(
            "Research Terminal Interface = QEG feasibility loss (u_L* -> 1);",
            "event-time and terminal-map sensitivity;",
            "NO post-RTI research mode, NO RTI saltation for notation;",
            "normal needs d(L_req-L)/dx: a genuine G1 derivative, deferred.",
        ),
    ),
    # ---- Sanger true mode switches -------------------------------------
    EventTaxonomyEntry(
        event="sanger_atmosphere_exit",
        surface="G_h = h - h_atm",
        direction=+1,
        mode_before="SANGER_ATM",
        mode_after="SANGER_VAC",
        classification=EventClassification.TRUE_HYBRID_MODE_SWITCH,
        reset_is_identity=True,
        saltation=True,
        terminal_sensitivity=False,
        normal=atmosphere_interface_normal(),
        notes=("x+ = x-, DR = I; f_ATM != f_VAC in general (D0 §16).",),
    ),
    EventTaxonomyEntry(
        event="sanger_atmosphere_entry",
        surface="G_h = h - h_atm",
        direction=-1,
        mode_before="SANGER_VAC",
        mode_after="SANGER_ATM",
        classification=EventClassification.TRUE_HYBRID_MODE_SWITCH,
        reset_is_identity=True,
        saltation=True,
        terminal_sensitivity=False,
        normal=atmosphere_interface_normal(),
        notes=("Same surface as the exit, opposite direction; DR = I.",),
    ),
    # ---- Sanger diagnostic events --------------------------------------
    EventTaxonomyEntry(
        event="sanger_atmospheric_pullout",
        surface="gamma = 0",
        direction=+1,
        mode_before="SANGER_ATM",
        mode_after="SANGER_ATM",
        classification=EventClassification.DIAGNOSTIC,
        reset_is_identity=True,
        saltation=False,
        terminal_sensitivity=False,
        normal=None,
        notes=("Atmospheric local minimum; NEVER a hybrid switch (G0 §6.5).",),
    ),
    EventTaxonomyEntry(
        event="sanger_vac_apogee",
        surface="gamma = 0",
        direction=-1,
        mode_before="SANGER_VAC",
        mode_after="SANGER_VAC",
        classification=EventClassification.DIAGNOSTIC,
        reset_is_identity=True,
        saltation=False,
        terminal_sensitivity=False,
        normal=None,
        notes=("VAC local maximum; NEVER a mode change (G0 §6.6).",),
    ),
    # ---- Sanger research terminal ---------------------------------------
    EventTaxonomyEntry(
        event="sanger_srti",
        surface="gamma = 0",
        direction=-1,
        mode_before="SANGER_ATM",
        mode_after=None,
        classification=EventClassification.RESEARCH_TERMINAL,
        reset_is_identity=False,
        saltation=False,
        terminal_sensitivity=True,
        normal=None,
        notes=(
            "Sanger Research Terminal Interface = skip-capability loss;",
            "event-time and terminal-map sensitivity;",
            "NO fake post-SRTI mode, NO fake SRTI saltation (G0 §6.7).",
        ),
    ),
)


def event_by_name(name: str) -> EventTaxonomyEntry:
    """Registry lookup (raises ``KeyError`` for unknown event names)."""
    for entry in EVENT_TAXONOMY:
        if entry.event == name:
            return entry
    raise KeyError(f"Unknown Phase-G event taxonomy entry: {name!r}")


def all_taxonomy_rows() -> tuple[dict, ...]:
    """Serializable taxonomy table (G0 §21 machine-readable protocol)."""
    return tuple(entry.as_dict() for entry in EVENT_TAXONOMY)


def crosscheck_frozen_factories() -> list[str]:
    """Verify taxonomy direction/terminal against the FROZEN factories.

    Returns a list of human-readable consistency failures (empty when the
    taxonomy fully agrees with the frozen event factories).  The G0
    semantic tests treat any failure as an error.
    """
    failures: list[str] = []

    cap_dir, cap_terminal, cap_hybrid = _qian_capture_event()
    if cap_dir != +1 or not cap_terminal or not cap_hybrid:
        failures.append(
            "Qian capture factory drifted from (direction=+1, terminal, "
            "hybrid_switch=True)."
        )

    rti_dir, rti_terminal = _qian_rti_event()
    if rti_dir != +1 or not rti_terminal:
        failures.append("Qian RTI factory drifted from (direction=+1, terminal).")

    ref = {
        "sanger_atmosphere_exit": "atmosphere_exit",
        "sanger_atmosphere_entry": "atmosphere_entry",
        "sanger_atmospheric_pullout": "atmospheric_pullout",
        "sanger_vac_apogee": "vacuum_apogee",
        "sanger_srti": "srti",
    }
    for entry in EVENT_TAXONOMY:
        key = ref.get(entry.event)
        if key is None:
            continue
        dir_, terminal = _sanger_event_attrs(key)
        if dir_ != entry.direction:
            failures.append(
                f"Frozen factory direction mismatch for {entry.event}: "
                f"taxonomy {entry.direction} vs factory {dir_}."
            )
        # Diagnostic events are non-terminal; every mode-switch / research
        # terminal event is terminal in the frozen D2/D3 state machine.
        expect_terminal = entry.classification != EventClassification.DIAGNOSTIC
        if terminal != expect_terminal:
            failures.append(
                f"Frozen factory terminal mismatch for {entry.event}: "
                f"expected {expect_terminal}, factory {terminal}."
            )
    return failures
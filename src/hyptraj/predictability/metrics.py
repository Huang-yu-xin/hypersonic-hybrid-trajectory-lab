"""Phase-G5 fixed-time predictability metric layer (G5 -- metric only).

G5 does NOT re-implement the hybrid STM: it calls the G4
``build_hybrid_stm`` directly and adds the DIMENSIONLESS scientific
metric layer on top (scaled SVD / FTLE / rank / condition / dominant
directions / row-column interpretability, from ``ftle``).  The raw
physical hybrid STM ``Phi_H`` is the interface between G4 (integration)
and G5 (metrics); the G2/G4 COMPUTATIONAL scaling is unrelated to the
G5 SCIENTIFIC canonical scale (which only acts as ``S^-1 Phi S`` at the
final step).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from hyptraj.models.parameters import EnvironmentParams, VehicleParams
from hyptraj.predictability import ftle
from hyptraj.predictability.hybrid_stm import build_hybrid_stm
from hyptraj.predictability.scaling import SCALING_CANDIDATES, canonical_candidate

STATE_ORDER = ("r", "theta", "v", "gamma")


def scale_values_by_key(scale_key: str) -> dict:
    for cand in SCALING_CANDIDATES:
        if cand.key == scale_key:
            return dict(cand.scales)
    raise KeyError(f"unknown scale candidate {scale_key!r}")


@dataclass(frozen=True)
class FixedTimePredictabilityResult:
    """Fixed-time scientific predictability metrics of a hybrid STM."""

    model: str
    horizon_s: float
    scale_key: str
    scale_values: dict

    phi_raw: np.ndarray
    phi_scaled: np.ndarray

    singular_values: np.ndarray
    sigma_max: float
    lambda_max: float

    numerical_rank: int
    nullity: int
    condition_number: float | None
    condition_status: str

    dominant_input_direction_scaled: np.ndarray
    dominant_output_direction_scaled: np.ndarray
    dominant_input_direction_physical: np.ndarray

    scaled_column_norms: np.ndarray
    scaled_row_norms: np.ndarray

    svd_reconstruction_error: float
    singular_gap_1_2: float | None

    topology_signature: tuple[str, ...]
    endpoint_mode: str
    solver_label: str
    metadata: dict = field(default_factory=dict)


def compute_fixed_time_metrics(
    model: str,
    t_final: float,
    env: EnvironmentParams,
    vehicle: VehicleParams,
    k=3.0,
    research_solver=None,
    stm_solver=None,
    scale_key: str | None = None,
) -> FixedTimePredictabilityResult:
    """Compute the canonical fixed-time metrics from a G4 hybrid STM.

    ``scale_key=None`` uses the current canonical candidate (G5 freeze:
    Candidate A).  Raises if the fixed time equals a true-switch / the
    research terminal (G4 endpoint restrictions).
    """
    scale_key = scale_key or canonical_candidate().key
    scales = scale_values_by_key(scale_key)

    from hyptraj.predictability.stm import stm_strict_reference_config

    if stm_solver is None:
        stm_solver = stm_strict_reference_config()
    if research_solver is None:
        from hyptraj.analysis.comparison_validation import (
            REFERENCE_SOLVER_CONFIG,
        )

        research_solver = REFERENCE_SOLVER_CONFIG

    # initial state from the frozen baseline (gamma0=-5 deg, K=3, h0=100 km)
    from hyptraj.models.parameters import InitialCondition

    ini = InitialCondition()
    x0 = np.array([env.earth_radius + ini.altitude, ini.range_angle,
                   ini.velocity, np.deg2rad(ini.flight_path_angle_deg)])

    hybrid = build_hybrid_stm(
        model, x0, t_final, env, vehicle, k,
        research_solver=research_solver, stm_solver=stm_solver,
    )
    m = ftle.finite_time_metrics(hybrid.phi_final, scales, float(t_final))
    return FixedTimePredictabilityResult(
        model=model,
        horizon_s=float(t_final),
        scale_key=scale_key,
        scale_values=dict(scales),
        phi_raw=hybrid.phi_final,
        phi_scaled=m["phi_scaled"],
        singular_values=np.asarray(m["singular_values"], dtype=float),
        sigma_max=m["sigma_max"],
        lambda_max=m["lambda_max"],
        numerical_rank=m["numerical_rank"],
        nullity=m["nullity"],
        condition_number=m["condition_number"],
        condition_status=m["condition_status"],
        dominant_input_direction_scaled=np.asarray(
            m["dominant_input_direction_scaled"]),
        dominant_output_direction_scaled=np.asarray(
            m["dominant_output_direction_scaled"]),
        dominant_input_direction_physical=np.asarray(
            m["dominant_input_direction_physical"]),
        scaled_column_norms=np.asarray(m["scaled_column_norms"]),
        scaled_row_norms=np.asarray(m["scaled_row_norms"]),
        svd_reconstruction_error=m["svd_reconstruction_error"],
        singular_gap_1_2=m["singular_gap_1_2"],
        topology_signature=hybrid.topology_signature,
        endpoint_mode=hybrid.endpoint_mode,
        solver_label=hybrid.solver_label,
        metadata={
            "terminal_margin_s": hybrid.terminal_margin,
            "event_margins_s": list(hybrid.event_margins),
            "raw_dimensional_singular_values_ANTI_EXAMPLE": m[
                "raw_dimensional_singular_values_ANTI_EXAMPLE"],
        },
    )
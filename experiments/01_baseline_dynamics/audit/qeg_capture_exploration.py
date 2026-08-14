"""Phase B.5-B1 (EXPLORATORY, NOT FROZEN): Candidate B2 Entry/Capture + QEG glide.

Approved interpretation (DECISION: B2-PROVISIONAL):
  * 2-D longitudinal plane; effective longitudinal lift factor
        u_L = cos(sigma),  u_L in [0, 1];
  * K = 3 remains the AERODYNAMIC lift-to-drag ratio (K_eff = K * u_L);
  * Stage 1 ENTRY: literal Eq.(4) dynamics with u_L = 1, starting from the
    original initial state, until the FIRST upward zero crossing of gamma
    (gamma = 0, direction = +1) -- the QEG CAPTURE event;
  * Stage 2 QEG_GLIDE:
        L_req = m (g - v^2/r) cos(gamma)
        u_L   = clip(L_req / L, 0, 1)
        gamma_dot = u_L * L / (m v) + (v/r - g/v) cos(gamma)
    No state is modified directly; no k_gamma feedback; no terminal-dive law.
  * QEG ends at the first POST-CAPTURE upward crossing of u_L* = 1
    (L_req = L) -- the QEG FEASIBILITY-LOSS event; the simulation stops there
    and the result is reported for human review.

This script is EXPLORATORY ONLY: it does not modify src/hyptraj, does not
freeze any regression baseline, and does not delete literal_eq4_uncontrolled.

Outputs (results/audit/phase_b5/):
    qeg_capture_exploration.json
    fig_qeg_h_R.png, fig_qeg_h_t.png, fig_qeg_v_t.png, fig_qeg_gamma_t.png,
    fig_qeg_uL_t.png, fig_qeg_sigma_t.png, fig_qeg_L_Lreq.png
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "01_baseline_dynamics"))

import baseline_config as cfg  # noqa: E402
from hyptraj.models.dynamics import atmospheric_dynamics, derived_quantities  # noqa: E402
from hyptraj.models.gravity import gravity_acceleration  # noqa: E402
from hyptraj.simulation.events import make_ground_event  # noqa: E402

AUDIT_DIR = PROJECT_ROOT / "results" / "audit" / "phase_b5"


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------

def _lreq(state, env, vehicle):
    """L_req = m (g - v^2/r) cos(gamma): lift required for gamma_dot = 0."""
    r, _theta, v, gamma = state
    g = gravity_acceleration(r - env.earth_radius, env)
    return vehicle.mass * (g - v**2 / r) * np.cos(gamma)


def _state0(env, initial):
    return np.array(
        [env.earth_radius + initial.altitude, initial.range_angle,
         initial.velocity, np.deg2rad(initial.flight_path_angle_deg)]
    )


def _make_gamma0_capture_event():
    """First upward zero crossing of the flight-path angle (QEG capture)."""

    def event(t, y):
        return float(y[3])

    event.terminal = True
    event.direction = +1
    return event


def _make_qeg_end_event(env, vehicle, control):
    """First post-capture upward crossing of u_L* = 1, i.e. L_req = L."""

    def event(t, y):
        r, _theta, v, gamma = y
        g = gravity_acceleration(r - env.earth_radius, env)
        rho = env.density_sea_level * np.exp(-max(r - env.earth_radius, 0.0) / env.scale_height)
        K = control(t, y)  # aerodynamic L/D (approved interpretation)
        q = 0.5 * rho * v * v
        L = q * vehicle.reference_area * K * vehicle.drag_coefficient
        req = vehicle.mass * (g - v**2 / r) * np.cos(gamma)
        return float(req - L)  # < 0 during QEG, crosses 0 upward at feasibility loss

    event.terminal = True
    event.direction = +1
    return event


def _rhs_qeg(t, y, env, vehicle, control):
    """QEG_GLIDE stage RHS: Eq.(4) with u_L = clip(L_req/L, 0, 1)."""
    r, theta, v, gamma = y
    altitude = r - env.earth_radius
    h_eval = max(altitude, 0.0)
    g = gravity_acceleration(h_eval, env)
    rho = env.density_sea_level * np.exp(-h_eval / env.scale_height)
    K = control(t, y)
    q = 0.5 * rho * v * v
    cd = vehicle.drag_coefficient
    cl = K * cd
    drag = q * vehicle.reference_area * cd
    lift = q * vehicle.reference_area * cl

    req = vehicle.mass * (g - v**2 / r) * np.cos(gamma)
    u = float(np.clip(req / lift, 0.0, 1.0)) if lift > 0.0 else 0.0

    r_dot = v * np.sin(gamma)
    theta_dot = v * np.cos(gamma) / r
    v_dot = -drag / vehicle.mass - g * np.sin(gamma)
    gamma_dot = (u * lift / (vehicle.mass * v)
                 + (v / r - g / v) * np.cos(gamma))
    return np.array([r_dot, theta_dot, v_dot, gamma_dot])


def _point_data(t, state, env, vehicle, control, u_L):
    """All quantities of interest at one state (u_L passed explicitly)."""
    dq = derived_quantities(t, state, env, vehicle, control)
    req = _lreq(state, env, vehicle)
    sigma = np.degrees(np.arccos(np.clip(u_L, 0.0, 1.0)))
    return {
        "time_s": float(t),
        "altitude_km": dq["altitude_m"] / 1000.0,
        "range_km": dq["range_m"] / 1000.0,
        "velocity_mps": float(state[2]),
        "gamma_deg": float(np.degrees(state[3])),
        "q_pa": dq["dynamic_pressure_pa"],
        "L_n": dq["lift_n"],
        "L_req_n": float(req),
        "u_L": float(u_L),
        "sigma_deg": float(sigma),
    }


def main() -> None:
    env, vehicle, initial, control = cfg.get_baseline_setup()

    # ---------------- Stage 1: ENTRY (literal Eq.(4), u_L = 1) -----------
    sol1 = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (0.0, 5000.0), _state0(env, initial),
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True,
        events=[_make_gamma0_capture_event()],
    )
    if not sol1.success or sol1.t_events[0].size == 0:
        raise RuntimeError(f"Capture event not found: {sol1.message}")

    t_capture = float(sol1.t_events[0][0])
    state_capture = sol1.sol(t_capture)
    dq_c = derived_quantities(t_capture, state_capture, env, vehicle, control)
    lreq_c = _lreq(state_capture, env, vehicle)
    u_capture = lreq_c / dq_c["lift_n"]  # u_L* at the capture instant

    # ---------------- Stage 2: QEG_GLIDE ---------------------------------
    sol2 = solve_ivp(
        lambda t, y: _rhs_qeg(t, y, env, vehicle, control),
        (t_capture, 5000.0), state_capture,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True,
        events=[_make_qeg_end_event(env, vehicle, control)],
    )
    if not sol2.success or sol2.t_events[0].size == 0:
        raise RuntimeError(f"QEG feasibility-loss event not found: {sol2.message}")

    t_end = float(sol2.t_events[0][0])
    state_end = sol2.sol(t_end)

    # ---------------- uniform grids ---------------------------------------
    n1, n2 = 500, 1500
    t1 = np.linspace(0.0, t_capture, n1)
    t2 = np.linspace(t_capture, t_end, n2)
    s1 = sol1.sol(t1)
    s2 = sol2.sol(t2)

    # QEG per-point control history
    u2 = np.empty(n2)
    L2 = np.empty(n2)
    Lreq2 = np.empty(n2)
    for i in range(n2):
        dq = derived_quantities(t2[i], s2[:, i], env, vehicle, control)
        L2[i] = dq["lift_n"]
        Lreq2[i] = _lreq(s2[:, i], env, vehicle)
        u2[i] = float(np.clip(Lreq2[i] / L2[i], 0.0, 1.0))

    sigma2 = np.degrees(np.arccos(np.clip(u2, 0.0, 1.0)))

    # ---------------- report -----------------------------------------------
    capture = _point_data(t_capture, state_capture, env, vehicle, control, u_capture)
    end_pt = _point_data(t_end, state_end, env, vehicle, control,
                         float(np.clip(_lreq(state_end, env, vehicle)
                                       / derived_quantities(t_end, state_end, env, vehicle, control)["lift_n"], 0.0, 1.0)))

    qeg_duration = t_end - t_capture
    range_capture = env.earth_radius * state_capture[1] / 1000.0
    range_end = env.earth_radius * state_end[1] / 1000.0

    h2 = s2[0] - env.earth_radius
    gamma2 = np.degrees(s2[3])
    segment = {
        "duration_s": qeg_duration,
        "range_gained_km": range_end - range_capture,
        "range_at_end_km": range_end,
        "gamma_min_deg": float(np.min(gamma2)),
        "gamma_max_deg": float(np.max(gamma2)),
        "u_L_min": float(np.min(u2)),
        "u_L_max": float(np.max(u2)),
        "sigma_min_deg": float(np.min(sigma2)),
        "sigma_max_deg": float(np.max(sigma2)),
        "sigma_median_deg": float(np.median(sigma2)),
        "fraction_sigma_gt_70deg": float(np.mean(sigma2 > 70.0)),
        "fraction_sigma_gt_80deg": float(np.mean(sigma2 > 80.0)),
        "fraction_sigma_gt_85deg": float(np.mean(sigma2 > 85.0)),
        "max_altitude_after_capture_km": float(np.max(h2) / 1000.0),
        "h_gt_100km_ever": bool(np.any(h2 > 100_000.0)),
    }

    report = {
        "capture_event": capture,
        "qeg_end_event": end_pt,
        "qeg_segment": segment,
        "note": "EXPLORATORY ONLY - no terminal-dive law, no frozen baseline",
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "qeg_capture_exploration.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    # ---------------- console ----------------------------------------------
    print("=== B2-PROVISIONAL exploratory run: ENTRY -> QEG CAPTURE -> QEG GLIDE ===")
    print("\nQEG CAPTURE EVENT (first upward gamma = 0 crossing):")
    for k, v in capture.items():
        print(f"  {k:>14s}: {v:.6g}")
    print("\nQEG FEASIBILITY-LOSS EVENT (u_L* = 1, L_req = L):")
    for k, v in end_pt.items():
        print(f"  {k:>14s}: {v:.6g}")
    print("\nQEG SEGMENT:")
    for k, v in segment.items():
        print(f"  {k:>32s}: {v:.6g}")

    # ---------------- figures ----------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    h1 = (s1[0] - env.earth_radius) / 1000.0
    h2k = h2 / 1000.0
    R1 = env.earth_radius * s1[1] / 1000.0
    R2 = env.earth_radius * s2[1] / 1000.0
    v1, v2 = s1[2], s2[2]
    gam1 = np.degrees(s1[3])

    def style(ax):
        ax.axvline(t_capture, color="tab:green", ls="--", lw=1.0)
        ax.axvline(t_end, color="tab:red", ls="--", lw=1.0)
        ax.axvspan(0.0, t_capture, color="tab:orange", alpha=0.08)
        ax.axvspan(t_capture, t_end, color="tab:green", alpha=0.08)
        ax.text(t_capture * 0.5, ax.get_ylim()[1], "ENTRY/CAPTURE", ha="center",
                va="top", fontsize=8, color="tab:orange")
        ax.text((t_capture + t_end) * 0.5, ax.get_ylim()[1], "QEG GLIDE",
                ha="center", va="top", fontsize=8, color="tab:green")
        ax.text(t_capture, ax.get_ylim()[0], "QEG CAPTURE EVENT",
                ha="right", va="bottom", fontsize=7, color="tab:green", rotation=90)
        ax.text(t_end, ax.get_ylim()[0], "QEG FEASIBILITY-LOSS EVENT",
                ha="right", va="bottom", fontsize=7, color="tab:red", rotation=90)
        ax.grid(True, ls=":", lw=0.5)

    # h-R
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(R1, h1, lw=1.2, color="tab:orange", label="ENTRY (u_L=1)")
    ax.plot(R2, h2k, lw=1.2, color="tab:green", label="QEG GLIDE")
    ax.plot(R1[-1], h1[-1], "o", color="tab:green", ms=7)
    ax.plot(R2[-1], h2k[-1], "s", color="tab:red", ms=7)
    ax.set_xlabel("Range [km]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("B2-PROVISIONAL: h - R (capture + QEG exploratory)")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_h_R.png", dpi=300); plt.close(fig)

    # h-t
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t1, h1, lw=1.2, color="tab:orange")
    ax.plot(t2, h2k, lw=1.2, color="tab:green")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("B2-PROVISIONAL: h - t"); style(ax)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_h_t.png", dpi=300); plt.close(fig)

    # v-t
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t1, v1, lw=1.2, color="tab:orange")
    ax.plot(t2, v2, lw=1.2, color="tab:green")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Velocity [m/s]")
    ax.set_title("B2-PROVISIONAL: v - t"); style(ax)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_v_t.png", dpi=300); plt.close(fig)

    # gamma-t
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t1, gam1, lw=1.2, color="tab:orange")
    ax.plot(t2, gamma2, lw=1.2, color="tab:green")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Flight-path angle [deg]")
    ax.set_title("B2-PROVISIONAL: gamma - t"); style(ax)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_gamma_t.png", dpi=300); plt.close(fig)

    # u_L - t
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t1, np.ones_like(t1), lw=1.2, color="tab:orange", label="u_L = 1 (ENTRY)")
    ax.plot(t2, u2, lw=1.2, color="tab:green", label="u_L = clip(L_req/L, 0, 1)")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("u_L (effective lift fraction)")
    ax.set_title("B2-PROVISIONAL: u_L - t"); ax.set_ylim(-0.05, 1.05)
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_uL_t.png", dpi=300); plt.close(fig)

    # sigma - t
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t2, sigma2, lw=1.2, color="tab:blue")
    ax.axhline(70.0, color="grey", ls=":", lw=0.8)
    ax.axhline(80.0, color="grey", ls=":", lw=0.8)
    ax.axhline(85.0, color="grey", ls=":", lw=0.8)
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Implied bank angle sigma = arccos(u_L) [deg]")
    ax.set_title("B2-PROVISIONAL: sigma - t (QEG segment)")
    ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_sigma_t.png", dpi=300); plt.close(fig)

    # L vs L_req
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t2, L2, lw=1.2, color="tab:green", label="L (available)")
    ax.plot(t2, Lreq2, lw=1.2, color="tab:red", ls="--", label="L_req = m(g-v^2/r) cos(gamma)")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Force [N]")
    ax.set_title("B2-PROVISIONAL: L vs L_req (QEG segment)")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_qeg_L_Lreq.png", dpi=300); plt.close(fig)

    print(f"\nreport + 7 figures written to {AUDIT_DIR}")


if __name__ == "__main__":
    main()

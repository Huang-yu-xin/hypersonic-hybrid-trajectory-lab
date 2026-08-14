"""Phase B.5-A / Task 4: candidate-model feasibility study (sandbox only).

Part 1 -- u_L*(t) = L_req(t)/L(t) analysis on the literal Eq.(4) trajectory:
    * how much of the flight is u_L* within the physical range [0, 1]
      (bank-angle interpretation u_L = cos sigma),
    * when it saturates (u_L* > 1: lift deficit; u_L* < 0: would need
      reversed lift -- never happens here because v < v_circ),
    * distribution summary.

Part 2 -- sandbox integration of Candidate B (quasi-equilibrium effective
lift glide), as tentatively defined in the audit:

    L_eff = u_L * L,        u_L = clip(L_req / L, 0, 1)
    gamma_dot = u_L * L/(m v) + (v/r - g/v) cos(gamma)

i.e. the exact gamma_dot = 0 algebraic constraint is enforced whenever the
required lift is available.  This is an EXPLORATORY experiment only; it is
not a production model and does not touch src/hyptraj.

Outputs:
    results/audit/phase_b5/fig_candidateB_uL_star.png
    results/audit/phase_b5/fig_candidateB_trajectory_compare.png
    results/audit/phase_b5/candidate_b_feasibility.json
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "01_baseline_dynamics"))

import baseline_config as cfg  # noqa: E402
from hyptraj.models.dynamics import derived_quantities  # noqa: E402
from hyptraj.models.gravity import gravity_acceleration  # noqa: E402
from hyptraj.simulation.events import make_ground_event  # noqa: E402

AUDIT_DIR = PROJECT_ROOT / "results" / "audit" / "phase_b5"


def lreq(state, env, vehicle):
    """Lift required for gamma_dot = 0: L_req = m (g - v^2/r) cos(gamma)."""
    r, _theta, v, gamma = state
    g = gravity_acceleration(r - env.earth_radius, env)
    return vehicle.mass * (g - v**2 / r) * np.cos(gamma)


def run_literal(env, vehicle, initial, control):
    state0 = np.array(
        [env.earth_radius + initial.altitude, initial.range_angle,
         initial.velocity, np.deg2rad(initial.flight_path_angle_deg)]
    )
    return solve_ivp(
        lambda t, y: _literal_rhs(t, y, env, vehicle, control),
        (0.0, 5000.0), state0,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True, events=make_ground_event(env),
    )


def _literal_rhs(t, y, env, vehicle, control):
    from hyptraj.models.dynamics import atmospheric_dynamics
    return atmospheric_dynamics(t, y, env, vehicle, control)


def _rhs_candidate_b(t, y, env, vehicle, control):
    """Full Eq.(4) with gamma_dot modified by u_L = clip(L_req/L, 0, 1)."""
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


def _rhs_candidate_c(t, y, env, vehicle, control, k_gamma):
    """Candidate C demonstration: gamma -> 0 proportional feedback on top of
    the equilibrium feedforward.

        u_L = clip(L_req/L - k_gamma * gamma, 0, 1)

    With gamma < 0 (descending) this requests more lift, driving gamma
    toward 0; at gamma ~ 0 it reduces to the equilibrium glide (u_L ~ 1).
    NOTE: k_gamma is a demonstration gain, NOT derived from literature.
    """
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
    u = float(np.clip(req / lift - k_gamma * gamma, 0.0, 1.0)) if lift > 0.0 else 0.0

    r_dot = v * np.sin(gamma)
    theta_dot = v * np.cos(gamma) / r
    v_dot = -drag / vehicle.mass - g * np.sin(gamma)
    gamma_dot = (u * lift / (vehicle.mass * v)
                 + (v / r - g / v) * np.cos(gamma))
    return np.array([r_dot, theta_dot, v_dot, gamma_dot])


def main() -> None:
    env, vehicle, initial, control = cfg.get_baseline_setup()

    # ---------------- Part 1: u_L* analysis on the literal trajectory ----
    sol_lit = run_literal(env, vehicle, initial, control)
    tf_lit = float(sol_lit.t_events[0][0])

    t = np.linspace(0.0, tf_lit, 8001)
    st = sol_lit.sol(t)
    L = np.empty_like(t)
    Lreq = np.empty_like(t)
    for i in range(len(t)):
        dq = derived_quantities(t[i], st[:, i], env, vehicle, control)
        L[i] = dq["lift_n"]
        Lreq[i] = lreq(st[:, i], env, vehicle)
    u_star = Lreq / L

    stats = {
        "u_star_min": float(np.min(u_star)),
        "u_star_max": float(np.max(u_star)),
        "fraction_in_[0,1]": float(np.mean((u_star >= 0) & (u_star <= 1))),
        "fraction_>1_saturated": float(np.mean(u_star > 1)),
        "fraction_<0": float(np.mean(u_star < 0)),
        "first_time_in_[0,1]_s": float(t[np.argmax(u_star <= 1)]),
    }

    # ---------------- Part 2: sandbox Candidate B ------------------------
    state0 = np.array(
        [env.earth_radius + initial.altitude, initial.range_angle,
         initial.velocity, np.deg2rad(initial.flight_path_angle_deg)]
    )
    sol_b = solve_ivp(
        lambda t, y: _rhs_candidate_b(t, y, env, vehicle, control),
        (0.0, 5000.0), state0,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True, events=make_ground_event(env),
    )

    if sol_b.success and sol_b.t_events[0].size > 0:
        tf_b = float(sol_b.t_events[0][0])
        tb = np.linspace(0.0, tf_b, 4001)
        stb = sol_b.sol(tb)
        h_b = stb[0] - env.earth_radius
        gamma_b = np.rad2deg(stb[3])

        u_b = np.empty_like(tb)
        for i in range(len(tb)):
            L_i = derived_quantities(tb[i], stb[:, i], env, vehicle, control)["lift_n"]
            u_b[i] = float(np.clip(lreq(stb[:, i], env, vehicle) / L_i, 0.0, 1.0))

        # gamma is frozen where |gamma_dot| ~ 0 (the u_L-unsaturated phase)
        gdot_b = np.gradient(gamma_b, tb)
        frozen_mask = np.abs(gdot_b) < 1e-6
        frozen_gamma = (
            float(np.median(gamma_b[frozen_mask])) if frozen_mask.any() else np.nan
        )

        metrics_b = {
            "flight_time_s": tf_b,
            "range_km": env.earth_radius * stb[1, -1] / 1000.0,
            "terminal_velocity_mps": float(stb[2, -1]),
            "max_altitude_km": float(np.max(h_b) / 1000.0),
            "max_altitude_after_entry_km": float(np.max(h_b[1:]) / 1000.0),
            "never_exceeds_100km_after_t0": bool(np.all(h_b[1:] <= 100_000.0 + 1e-3)),
            "terminal_gamma_deg": float(gamma_b[-1]),
            "gamma_frozen_fraction": float(np.mean(frozen_mask)),
            "gamma_frozen_value_deg": frozen_gamma,
            "u_L_saturated_fraction_gt_0.999": float(np.mean(u_b > 0.999)),
        }
    else:
        tf_b = None
        metrics_b = {"error": sol_b.message}

    # ---------------- Part 3: sandbox Candidate C (demonstration) ---------
    # gamma -> 0 proportional feedback with an ARBITRARY demonstration gain.
    k_gamma = 2.0  # dimensionless; NOT derived from literature
    sol_c = solve_ivp(
        lambda t, y: _rhs_candidate_c(t, y, env, vehicle, control, k_gamma),
        (0.0, 5000.0), state0,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True, events=make_ground_event(env),
    )

    if sol_c.success and sol_c.t_events[0].size > 0:
        tf_c = float(sol_c.t_events[0][0])
        tc = np.linspace(0.0, tf_c, 4001)
        stc = sol_c.sol(tc)
        h_c = stc[0] - env.earth_radius
        metrics_c = {
            "demonstration_gain_k_gamma": k_gamma,
            "flight_time_s": tf_c,
            "range_km": env.earth_radius * stc[1, -1] / 1000.0,
            "terminal_velocity_mps": float(stc[2, -1]),
            "max_altitude_km": float(np.max(h_c) / 1000.0),
            "max_altitude_after_entry_km": float(np.max(h_c[1:]) / 1000.0),
            "never_exceeds_100km_after_t0": bool(np.all(h_c[1:] <= 100_000.0 + 1e-3)),
            "terminal_gamma_deg": float(np.rad2deg(stc[3, -1])),
            "mean_gamma_deg_after_capture": float(np.mean(np.rad2deg(stc[3, 2000:]))),
        }
    else:
        tf_c = None
        metrics_c = {"error": sol_c.message}

    summary = {
        "u_star_analysis": stats,
        "candidate_b_sandbox": metrics_b,
        "candidate_c_demo": metrics_c,
        "literal_for_comparison": {
            "flight_time_s": tf_lit,
            "range_km": env.earth_radius * st[1, -1] / 1000.0,
            "terminal_velocity_mps": float(st[2, -1]),
            "max_altitude_km": float(np.max(st[0] - env.earth_radius) / 1000.0),
        },
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "candidate_b_feasibility.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
        f.write("\n")

    # ---------------- console --------------------------------------------
    print("Candidate feasibility (sandbox)")
    print("\nPart 1 -- u_L*(t) = L_req/L on the literal trajectory:")
    for k, v in stats.items():
        print(f"  {k:>28s}: {v:.6g}")
    print("\nPart 2 -- Candidate B sandbox (u_L = clip(L_req/L, 0, 1)):")
    for k, v in metrics_b.items():
        print(f"  {k:>32s}: {v}")
    print("\nPart 3 -- Candidate C demo (u_L = clip(L_req/L - k*gamma, 0, 1), k=2 demo gain):")
    for k, v in metrics_c.items():
        print(f"  {k:>32s}: {v}")
    print("\nLiteral for comparison:")
    for k, v in summary["literal_for_comparison"].items():
        print(f"  {k:>22s}: {v:.6g}")

    # ---------------- figures --------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # u_L* over the literal flight
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t, u_star, lw=1.0, color="tab:purple")
    ax.axhspan(0.0, 1.0, color="tab:green", alpha=0.12)
    ax.axhline(1.0, color="tab:green", ls="--", lw=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("u_L* = L_req / L (log)")
    ax.set_title("Candidate B: required effective-lift fraction on the literal trajectory")
    ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout()
    fig.savefig(AUDIT_DIR / "fig_candidateB_uL_star.png", dpi=300)
    plt.close(fig)

    # literal vs candidate B/C comparison
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2))
    ax = axes[0]
    ax.plot(env.earth_radius * st[1] / 1000.0, (st[0] - env.earth_radius) / 1000.0,
            lw=1.1, color="tab:red", label="Literal Eq.(4)")
    if tf_b is not None:
        ax.plot(env.earth_radius * stb[1] / 1000.0, h_b / 1000.0,
                lw=1.1, color="tab:blue", label="Candidate B sandbox")
    if tf_c is not None:
        ax.plot(env.earth_radius * stc[1] / 1000.0, h_c / 1000.0,
                lw=1.1, color="tab:green", label="Candidate C demo")
    ax.set_xlabel("Range [km]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("h - R"); ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)

    ax = axes[1]
    ax.plot(t, st[2], lw=1.1, color="tab:red", label="Literal Eq.(4)")
    if tf_b is not None:
        ax.plot(tb, stb[2], lw=1.1, color="tab:blue", label="Candidate B sandbox")
    if tf_c is not None:
        ax.plot(tc, stc[2], lw=1.1, color="tab:green", label="Candidate C demo")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Velocity [m/s]")
    ax.set_title("v - t"); ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout()
    fig.savefig(AUDIT_DIR / "fig_candidateB_trajectory_compare.png", dpi=300)
    plt.close(fig)

    print(f"\nfigures + candidate_b_feasibility.json written to {AUDIT_DIR}")


if __name__ == "__main__":
    main()

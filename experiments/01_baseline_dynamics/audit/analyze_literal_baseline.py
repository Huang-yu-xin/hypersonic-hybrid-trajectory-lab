"""Phase B.5-A / Task 3: dynamic diagnosis of the literal Eq.(4) baseline.

Sandbox analysis script (NOT a production model).  It re-integrates the
literal Eq.(4) uncontrolled baseline and diagnoses WHY the trajectory
skips back above 100 km, using

    L_req(t) = m * (g(h) - v^2 / r) * cos(gamma)      (gamma-dot = 0 requirement)
    eta_L(t) = L_req(t) / L(t)                         (required / available lift)

and the first dive -- pull-up -- 100 km crossing -- first peak event table.

Outputs:
    results/audit/phase_b5/fig_literal_h_t_events.png
    results/audit/phase_b5/fig_literal_L_Lreq.png
    results/audit/phase_b5/fig_literal_eta_L.png
    results/audit/phase_b5/literal_diagnosis.json
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "experiments" / "01_baseline_dynamics"))

import baseline_config as cfg  # noqa: E402
from hyptraj.models.dynamics import atmospheric_dynamics, derived_quantities  # noqa: E402
from hyptraj.models.gravity import gravity_acceleration  # noqa: E402
from hyptraj.simulation.events import make_ground_event  # noqa: E402

AUDIT_DIR = PROJECT_ROOT / "results" / "audit" / "phase_b5"

OUTPUT_COLUMNS = [
    "time_s",
    "altitude_km",
    "velocity_mps",
    "gamma_deg",
    "q_pa",
    "L_n",
    "L_req_n",
    "eta_L",
]


def compute_lreq(state, env, vehicle):
    """L_req = m (g - v^2/r) cos(gamma): lift needed for gamma_dot = 0."""
    r, _theta, v, gamma = state
    g = gravity_acceleration(r - env.earth_radius, env)
    return vehicle.mass * (g - v**2 / r) * np.cos(gamma)


def state_row(t, state, env, vehicle, control):
    """Quantities of interest at a given state."""
    dq = derived_quantities(t, state, env, vehicle, control)
    L = dq["lift_n"]
    lreq = compute_lreq(state, env, vehicle)
    return {
        "time_s": float(t),
        "altitude_km": dq["altitude_m"] / 1000.0,
        "velocity_mps": float(state[2]),
        "gamma_deg": float(np.rad2deg(state[3])),
        "q_pa": dq["dynamic_pressure_pa"],
        "L_n": L,
        "L_req_n": lreq,
        "eta_L": float(lreq / L) if L > 0.0 else np.nan,
    }


def find_root(f, t_a, t_b, sign_from, sign_to):
    """Locate the first time in [t_a, t_b] where scalar function `f`
    crosses from `sign_from` to `sign_to`."""
    # coarse bracketing on a fine grid, then brentq refine
    grid = np.linspace(t_a, t_b, 4001)
    vals = np.array([f(t) for t in grid])
    for i in range(len(grid) - 1):
        if (vals[i] < 0.0) != (vals[i + 1] < 0.0):
            if np.sign(vals[i]) == sign_from and np.sign(vals[i + 1]) == sign_to:
                return brentq(f, grid[i], grid[i + 1], xtol=1e-12, rtol=1e-12)
    return None


def main() -> None:
    env, vehicle, initial, control = cfg.get_baseline_setup()

    state0 = np.array(
        [
            env.earth_radius + initial.altitude,
            initial.range_angle,
            initial.velocity,
            np.deg2rad(initial.flight_path_angle_deg),
        ]
    )

    sol = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (0.0, 5000.0),
        state0,
        method="DOP853",
        rtol=1e-8,
        atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0,
        dense_output=True,
        events=make_ground_event(env),
    )
    tf = float(sol.t_events[0][0])

    # ---- event times -------------------------------------------------
    t_gamma0 = find_root(lambda t: float(sol.sol(t)[3]), 0.0, tf, -1.0, +1.0)
    # h - 100 km crossing upward: r - (Re + h_atm) goes from - to +
    t_100up = find_root(
        lambda t: float(sol.sol(t)[0] - (env.earth_radius + 100_000.0)),
        t_gamma0, tf, -1.0, +1.0,
    )
    # first peak: gamma + -> - after the upward 100 km crossing
    t_peak = find_root(lambda t: float(sol.sol(t)[3]), t_100up, tf, +1.0, -1.0)
    # first local minimum of h == first gamma = 0 upward crossing
    t_hmin = t_gamma0

    events = {
        "t0": (0.0, state0.copy()),
        "t_hmin": (t_hmin, sol.sol(t_hmin)),
        "t_gamma0": (t_gamma0, sol.sol(t_gamma0)),
        "t_100up": (t_100up, sol.sol(t_100up)),
        "t_peak": (t_peak, sol.sol(t_peak)),
    }

    rows = {}
    for name, (t, st) in events.items():
        rows[name] = state_row(t, st, env, vehicle, control)
        rows[name]["time_s"] = t

    # ---- uniform grid diagnostics ------------------------------------
    t_grid = np.linspace(0.0, tf, 4001)
    st_grid = sol.sol(t_grid)
    h = st_grid[0] - env.earth_radius
    gamma = st_grid[3]
    q = np.empty_like(t_grid)
    L = np.empty_like(t_grid)
    L_req = np.empty_like(t_grid)
    for i in range(len(t_grid)):
        dq = derived_quantities(t_grid[i], st_grid[:, i], env, vehicle, control)
        q[i] = dq["dynamic_pressure_pa"]
        L[i] = dq["lift_n"]
        L_req[i] = compute_lreq(st_grid[:, i], env, vehicle)
    eta = L_req / L  # L > 0 everywhere on the literal trajectory

    # ---- eta_L region analysis ----------------------------------------
    frac_ok = float(np.mean((eta >= 0.0) & (eta <= 1.0)))
    frac_high = float(np.mean(eta > 1.0))
    frac_neg = float(np.mean(eta < 0.0))
    eta_min = float(np.nanmin(eta))
    eta_max = float(np.nanmax(eta))
    first_feasible_idx = int(np.argmax(eta <= 1.0))
    t_first_feasible = float(t_grid[first_feasible_idx])
    # longest contiguous segment with eta in [0,1] (sustained glide capacity)
    in_ok = (eta >= 0.0) & (eta <= 1.0)
    longest = (0, 0)  # (start_idx, length)
    run_start = None
    for i, ok in enumerate(in_ok):
        if ok and run_start is None:
            run_start = i
        elif not ok and run_start is not None:
            if i - run_start > longest[1]:
                longest = (run_start, i - run_start)
            run_start = None
    if run_start is not None and len(in_ok) - run_start > longest[1]:
        longest = (run_start, len(in_ok) - run_start)
    sustained = (
        (float(t_grid[longest[0]]), float(t_grid[longest[0] + longest[1] - 1]))
        if longest[1] > 50
        else None
    )

    summary = {
        "flight_time_s": tf,
        "range_km": env.earth_radius * st_grid[1, -1] / 1000.0,
        "events": rows,
        "eta_L": {
            "min": eta_min,
            "max": eta_max,
            "fraction_in_[0,1]": frac_ok,
            "fraction_>1": frac_high,
            "fraction_<0": frac_neg,
            "first_time_eta_le_1_s": t_first_feasible,
            "longest_glide_capacity_interval_s": sustained,
        },
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "literal_diagnosis.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, allow_nan=True)
        f.write("\n")

    # ---- console report ------------------------------------------------
    print("Literal Eq.(4) uncontrolled baseline -- dynamic diagnosis")
    print(f"tf = {tf:.3f} s,  Rf = {summary['range_km']:.1f} km")
    print()
    hdr = f"{'event':>9s} | " + " | ".join(f"{c:>12s}" for c in OUTPUT_COLUMNS[1:])
    print(hdr)
    print("-" * len(hdr))
    for name, row in rows.items():
        vals = " | ".join(
            f"{row[c]:12.6g}" for c in OUTPUT_COLUMNS[1:]
        )
        print(f"{name:>9s} | {vals}")
    print()
    print("eta_L = L_req / L  region analysis over the whole flight:")
    print(f"  eta_L in [0,1]      : {frac_ok * 100:6.2f} % of flight")
    print(f"  eta_L > 1 (lack L)  : {frac_high * 100:6.2f} % of flight")
    print(f"  eta_L < 0 (need -L) : {frac_neg * 100:6.2f} % of flight")
    print(f"  eta_L range         : [{eta_min:.4g}, {eta_max:.4g}]")
    print(f"  first time eta<=1   : t = {t_first_feasible:.2f} s")
    print(f"  first sustained     : {sustained}")

    # ---- figures --------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    markers = {
        "t0": "o",
        "t_hmin": "s",
        "t_gamma0": "^",
        "t_100up": "D",
        "t_peak": "v",
    }
    colors = {"t0": "k", "t_hmin": "tab:blue", "t_gamma0": "tab:cyan",
              "t_100up": "tab:orange", "t_peak": "tab:red"}

    # 1) h(t) with event markers
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t_grid, h / 1000.0, lw=1.1, color="tab:blue")
    for name, (t, _) in events.items():
        ax.plot(t, rows[name]["altitude_km"], marker=markers[name],
                color=colors[name], markersize=8, label=f"{name}  t={t:.1f}s")
    ax.axhline(100.0, color="grey", ls="--", lw=0.8)
    ax.text(t_grid[-1] * 0.99, 101.5, "h_atm = 100 km", ha="right", fontsize=8)
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("Literal Eq.(4): altitude and first-dive / pull-up events")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout()
    fig.savefig(AUDIT_DIR / "fig_literal_h_t_events.png", dpi=300)
    plt.close(fig)

    # 2) L(t) vs L_req(t)
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t_grid, L, lw=1.1, color="tab:green", label="L (available lift)")
    ax.plot(t_grid, L_req, lw=1.1, color="tab:red", ls="--",
            label="L_req = m(g - v^2/r) cos(gamma)")
    ax.set_yscale("log")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Force [N] (log)")
    ax.set_title("Literal Eq.(4): available vs required lift")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout()
    fig.savefig(AUDIT_DIR / "fig_literal_L_Lreq.png", dpi=300)
    plt.close(fig)

    # 3) eta_L(t) with region bands
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t_grid, eta, lw=1.1, color="tab:purple")
    ax.axhspan(0.0, 1.0, color="tab:green", alpha=0.12)
    ax.text(t_grid[-1] * 0.98, 1.05, "feasible region eta in [0,1]",
            ha="right", va="bottom", fontsize=8)
    ax.axhline(1.0, color="tab:green", ls="--", lw=0.8)
    ax.axhline(0.0, color="tab:green", ls="--", lw=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("eta_L = L_req / L (log)")
    ax.set_title("Literal Eq.(4): lift-requirement ratio")
    ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout()
    fig.savefig(AUDIT_DIR / "fig_literal_eta_L.png", dpi=300)
    plt.close(fig)

    print(f"\nfigures + literal_diagnosis.json written to {AUDIT_DIR}")


if __name__ == "__main__":
    main()

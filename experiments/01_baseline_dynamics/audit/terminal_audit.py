"""Phase B.5-B2 (EXPLORATORY): Terminal dynamics audit T1 vs T2.

Both terminal candidates start from the EXACT same QEG feasibility-loss
event state x_T = [r, theta, v, gamma] at t = 723.04 s (h = 46.041 km,
v = 3192.5 m/s, gamma ~ 0, L = L_req, u_L = 1), obtained by re-running the
identical two-stage integration of qeg_capture_exploration.py.

    T1 = Full-Lift Natural Descent          u_L = 1,  sigma = 0
    T2 = Zero-Longitudinal-Lift Dive        u_L = 0,  sigma = 90 deg (2-D projection)

Both candidates use identical numerical settings (DOP853, rtol=1e-8,
component-scaled atol, max_step=10 s, ground event h=0) and integrate
naturally to the ground event.  Only u_L differs.

EXPLORATORY ONLY: no production model, no frozen baseline, no k_gamma,
no optimization, no predictor-corrector, no drag-profile optimization,
no Phase C.

Outputs (results/audit/phase_b5/):
    terminal_audit.json
    fig_terminal_h_R.png, fig_terminal_h_t.png, fig_terminal_v_t.png,
    fig_terminal_gamma_t.png, fig_terminal_q_t.png, fig_terminal_uL_t.png,
    fig_terminal_T1_L_Lreq.png
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

PROJECT_ROOT = Path(__file__).resolve().parents[3]

import qeg_capture_exploration as qeg  # noqa: E402 (sibling module in audit/)
from hyptraj.models.dynamics import atmospheric_dynamics, derived_quantities  # noqa: E402
from hyptraj.models.gravity import gravity_acceleration  # noqa: E402
from hyptraj.simulation.events import make_ground_event  # noqa: E402

AUDIT_DIR = qeg.AUDIT_DIR

V_QEG_END_REF = 3192.5  # reference value of v at the QEG-end event [m/s]


def _rhs_t2(t, y, env, vehicle, control):
    """T2 terminal RHS: Eq.(4) with the lift term removed from gamma_dot
    (u_L = 0: zero longitudinal lift projection).  Drag is unchanged."""
    r, theta, v, gamma = y
    altitude = r - env.earth_radius
    h_eval = max(altitude, 0.0)
    g = gravity_acceleration(h_eval, env)
    rho = env.density_sea_level * np.exp(-h_eval / env.scale_height)
    K = control(t, y)
    q = 0.5 * rho * v * v
    cd = vehicle.drag_coefficient
    drag = q * vehicle.reference_area * cd

    r_dot = v * np.sin(gamma)
    theta_dot = v * np.cos(gamma) / r
    v_dot = -drag / vehicle.mass - g * np.sin(gamma)
    gamma_dot = (v / r - g / v) * np.cos(gamma)
    return np.array([r_dot, theta_dot, v_dot, gamma_dot])


def _find_crossings(f, t_grid, vals, direction=None):
    """Indices of sign changes on a grid; optionally filtered by sign
    change direction (+1: - to +; -1: + to -)."""
    out = []
    for i in range(len(t_grid) - 1):
        v0, v1 = vals[i], vals[i + 1]
        if (v0 < 0.0) != (v1 < 0.0):
            if direction is None:
                out.append((t_grid[i], t_grid[i + 1]))
            elif direction > 0 and v0 < 0.0 <= v1:
                out.append((t_grid[i], t_grid[i + 1]))
            elif direction < 0 and v0 > 0.0 >= v1:
                out.append((t_grid[i], t_grid[i + 1]))
    return out


def _refine_root(f, a, b):
    return brentq(f, a, b, xtol=1e-12, rtol=1e-12)


def main() -> None:
    env, vehicle, initial, control = qeg.cfg.get_baseline_setup()

    # ---------------- common Entry + QEG segments (identical to B.5-B1) ---
    sol1 = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (0.0, 5000.0), qeg._state0(env, initial),
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True,
        events=[qeg._make_gamma0_capture_event()],
    )
    t_capture = float(sol1.t_events[0][0])
    state_capture = sol1.sol(t_capture)

    sol2 = solve_ivp(
        lambda t, y: qeg._rhs_qeg(t, y, env, vehicle, control),
        (t_capture, 5000.0), state_capture,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True,
        events=[qeg._make_qeg_end_event(env, vehicle, control)],
    )
    t_gate = float(sol2.t_events[0][0])
    x_T = sol2.sol(t_gate).copy()  # EXACT QEG feasibility-loss event state
    v_qeg_end = float(x_T[2])

    # ---------------- T1 / T2 terminal integrations ----------------------
    ground = make_ground_event(env)

    sol_t1 = solve_ivp(
        lambda t, y: atmospheric_dynamics(t, y, env, vehicle, control),
        (t_gate, 5000.0), x_T,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True, events=ground,
    )
    sol_t2 = solve_ivp(
        lambda t, y: _rhs_t2(t, y, env, vehicle, control),
        (t_gate, 5000.0), x_T,
        method="DOP853", rtol=1e-8, atol=[1e-3, 1e-10, 1e-6, 1e-10],
        max_step=10.0, dense_output=True, events=ground,
    )

    assert sol_t1.success and sol_t1.t_events[0].size > 0, sol_t1.message
    assert sol_t2.success and sol_t2.t_events[0].size > 0, sol_t2.message
    tf_t1 = float(sol_t1.t_events[0][0])
    tf_t2 = float(sol_t2.t_events[0][0])

    # ---------------- grids -------------------------------------------------
    n1, n2, nt = 400, 1200, 3000
    t1g = np.linspace(0.0, t_capture, n1)
    t2g = np.linspace(t_capture, t_gate, n2)
    s1g = sol1.sol(t1g)
    s2g = sol2.sol(t2g)

    def q_of(t, st):
        dq = derived_quantities(t, st, env, vehicle, control)
        return dq["dynamic_pressure_pa"], dq["drag_n"], dq["lift_n"]

    def candidate_grid(sol, tf, n, u_mode):
        """u_mode: 't1' (u_L=1) or 't2' (u_L=0)."""
        t = np.linspace(t_gate, tf, n)
        st = sol.sol(t)
        q = np.empty(n); D = np.empty(n); L = np.empty(n)
        Lreq = np.empty(n)
        for i in range(n):
            q[i], D[i], L[i] = q_of(t[i], st[:, i])
            Lreq[i] = qeg._lreq(st[:, i], env, vehicle)
        u = np.ones(n) if u_mode == "t1" else np.zeros(n)
        return t, st, q, D, L, Lreq, u

    t_t1, s_t1, q_t1, D_t1, L_t1, Lreq_t1, u_t1 = candidate_grid(sol_t1, tf_t1, nt, "t1")
    t_t2, s_t2, q_t2, D_t2, L_t2, Lreq_t2, u_t2 = candidate_grid(sol_t2, tf_t2, nt, "t2")

    # ---------------- T1 shape events --------------------------------------
    # gamma zero crossings, h local extrema (gamma=0 either way), eta_L=1 crossings
    gamma_t1 = np.degrees(s_t1[3])
    h_t1 = s_t1[0] - env.earth_radius
    eta_t1 = Lreq_t1 / L_t1

    def events_on(sol, t, vals, f, directions):
        out = []
        for a, b in _find_crossings(f, t, vals, directions):
            out.append(_refine_root(f, a, b))
        return out

    t_gamma0_t1 = events_on(
        sol_t1, t_t1, s_t1[3],
        lambda tt: float(sol_t1.sol(tt)[3]), None)
    t_hmin_t1 = events_on(
        sol_t1, t_t1, s_t1[3],
        lambda tt: float(sol_t1.sol(tt)[3]), -1)  # h local min (gamma + -> -)
    t_hmax_t1 = events_on(
        sol_t1, t_t1, s_t1[3],
        lambda tt: float(sol_t1.sol(tt)[3]), +1)  # h local max (gamma - -> +)
    t_eta1_t1 = events_on(
        sol_t1, t_t1, eta_t1 - 1.0,
        lambda tt: float(qeg._lreq(sol_t1.sol(tt), env, vehicle)
                         / derived_quantities(tt, sol_t1.sol(tt), env, vehicle, control)["lift_n"] - 1.0),
        None)

    # ---------------- T2 gamma thresholds ----------------------------------
    gamma_t2 = np.degrees(s_t2[3])
    h_t2 = s_t2[0] - env.earth_radius

    def threshold_crossing(deg):
        for i in range(len(t_t2) - 1):
            if gamma_t2[i] >= deg >= gamma_t2[i + 1] and gamma_t2[i] > gamma_t2[i + 1]:
                tt = _refine_root(
                    lambda tt: float(np.degrees(sol_t2.sol(tt)[3]) - deg),
                    t_t2[i], t_t2[i + 1])
                stt = sol_t2.sol(tt)
                return tt, float(stt[0] - env.earth_radius) / 1000.0
        return None

    t2_thresholds = {f"{d}deg": threshold_crossing(d) for d in (-5.0, -10.0, -20.0, -30.0)}
    gamma_min_t2 = float(np.min(gamma_t2))

    # ---------------- metrics ------------------------------------------------
    def terminal_metrics(t, st, q, D, L, u):
        dR = env.earth_radius * (st[1, -1] - x_T[1]) / 1000.0
        return {
            "delta_t_terminal_s": float(t[-1] - t_gate),
            "delta_R_terminal_km": dR,
            "v_f_mps": float(st[2, -1]),
            "gamma_f_deg": float(np.degrees(st[3, -1])),
            # terminology: q_max is the dynamic-pressure PEAK; the time
            # integral of q is the current thermal-load PROXY.
            "dynamic_pressure_peak_terminal_pa": float(np.max(q)),
            "drag_peak_terminal_n": float(np.max(D)),
            "lift_peak_terminal_n": float(np.max(L)),
            "thermal_load_proxy_terminal_pas": float(np.trapezoid(q, t)),
        }

    m_t1 = terminal_metrics(t_t1, s_t1, q_t1, D_t1, L_t1, u_t1)
    m_t2 = terminal_metrics(t_t2, s_t2, q_t2, D_t2, L_t2, u_t2)

    def full_metrics(tf, st_end, q_all_max, q_proxy_all, vf):
        return {
            "t_f_s": tf,
            "R_f_km": env.earth_radius * st_end[1] / 1000.0,
            "v_f_mps": vf,
            "dynamic_pressure_peak_full_pa": q_all_max,
            "thermal_load_proxy_full_pas": q_proxy_all,
        }

    # full-flight arrays for q integral / q max / residence times
    t_all1 = np.concatenate([t1g, t2g, t_t1])
    s_all1 = np.concatenate([s1g, s2g, s_t1], axis=1)
    t_all2 = np.concatenate([t1g, t2g, t_t2])
    s_all2 = np.concatenate([s1g, s2g, s_t2], axis=1)
    q_all1 = np.empty_like(t_all1); q_all2 = np.empty_like(t_all2)
    for i in range(len(t_all1)):
        q_all1[i] = q_of(t_all1[i], s_all1[:, i])[0]
        q_all2[i] = q_of(t_all2[i], s_all2[:, i])[0]

    full1 = full_metrics(tf_t1, s_t1[:, -1], float(np.max(q_all1)),
                         float(np.trapezoid(q_all1, t_all1)), m_t1["v_f_mps"])
    full2 = full_metrics(tf_t2, s_t2[:, -1], float(np.max(q_all2)),
                         float(np.trapezoid(q_all2, t_all2)), m_t2["v_f_mps"])

    def residence(v_segments, t_segments):
        """High-speed residence proxy: duration over which v > threshold.

        Computed per segment with the segment's OWN uniform time step;
        joint duplicate points (same time at segment boundaries) are
        excluded from all but the first segment.  (The earlier
        implementation used the first segment's step for every point,
        which overcounted the later segments.)
        """
        out = {}
        for thr in (3000.0, 2000.0, 1500.0):
            total = 0.0
            for i, (t_seg, v_seg) in enumerate(zip(t_segments, v_segments)):
                if i > 0:
                    v_seg = v_seg[1:]  # drop the duplicated joint point
                    t_seg = t_seg[1:]
                dt = t_seg[1] - t_seg[0]
                total += float(np.sum(v_seg > thr)) * dt
            out[f"t_v_gt_{int(thr)}_s"] = total
        return out

    residence1 = residence(
        [s1g[2], s2g[2], s_t1[2]], [t1g, t2g, t_t1])
    residence2 = residence(
        [s1g[2], s2g[2], s_t2[2]], [t1g, t2g, t_t2])

    eta_v1 = m_t1["v_f_mps"] / v_qeg_end
    eta_v2 = m_t2["v_f_mps"] / v_qeg_end

    report = {
        "common_qeg_end_state": {
            "t_s": t_gate,
            "h_km": float(x_T[0] - env.earth_radius) / 1000.0,
            "v_mps": v_qeg_end,
            "gamma_deg": float(np.degrees(x_T[3])),
            "range_km": env.earth_radius * x_T[1] / 1000.0,
            "state_xT": [float(v) for v in x_T],
            "L_eq_Lreq": True,
            "u_L": 1.0,
        },
        "t1": {
            "definition": "u_L = 1 (full lift, sigma = 0), natural descent",
            "control_transition": "continuous (delta u_L = 0)",
            "terminal": m_t1,
            "full": full1,
            "velocity_retention": {"eta_v": eta_v1, "delta_v_terminal_mps": v_qeg_end - m_t1["v_f_mps"]},
            "high_speed_residence_s": residence1,
            "shape_events": {
                "n_gamma_zero_crossings": len(t_gamma0_t1),
                "n_h_local_min": len(t_hmin_t1),
                "n_h_local_max": len(t_hmax_t1),
                "n_eta1_crossings": len(t_eta1_t1),
                "gamma_zero_crossing_times_s": t_gamma0_t1,
                "h_local_min_times_s": t_hmin_t1,
                "h_local_max_times_s": t_hmax_t1,
                "eta1_crossing_times_s": t_eta1_t1,
            },
        },
        "t2": {
            "definition": "u_L = 0 (zero longitudinal lift, sigma = 90 deg 2-D limit)",
            "control_transition": "discontinuous event-localized switch (delta u_L = -1)",
            "terminal": m_t2,
            "full": full2,
            "velocity_retention": {"eta_v": eta_v2, "delta_v_terminal_mps": v_qeg_end - m_t2["v_f_mps"]},
            "high_speed_residence_s": residence2,
            "dive": {
                "gamma_min_deg": gamma_min_t2,
                "thresholds": {
                    name: (None if val is None else {"t_s": val[0], "h_km": val[1]})
                    for name, val in t2_thresholds.items()
                },
            },
        },
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_DIR / "terminal_audit.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    # ---------------- console -------------------------------------------------
    print("=== Phase B.5-B2 terminal audit: T1 vs T2 ===")
    print(f"Common QEG-end state: t={t_gate:.3f}s h={x_T[0]-env.earth_radius:.3f}m "
          f"v={v_qeg_end:.3f} m/s gamma~0 R={env.earth_radius*x_T[1]/1000:.1f}km")
    for name, m, full, eta, res, extra in [
        ("T1", m_t1, full1, eta_v1, residence1, report["t1"]["shape_events"]),
        ("T2", m_t2, full2, eta_v2, residence2, report["t2"]["dive"]),
    ]:
        print(f"\n--- {name} ---")
        for k, v in m.items():
            print(f"  {k:>26s}: {v:.6g}")
        for k, v in full.items():
            print(f"  {k:>26s}: {v:.6g}")
        print(f"  eta_v = vf/v_QEGend      : {eta:.6g}")
        print(f"  delta_v_terminal [m/s]   : {v_qeg_end - m['v_f_mps']:.6g}")
        for k, v in res.items():
            print(f"  {k:>26s}: {v:.6g}")
        if name == "T1":
            for k, v in extra.items():
                print(f"  {k:>26s}: {v}")
        else:
            print(f"  gamma_min_deg            : {extra['gamma_min_deg']:.6g}")
            for k, v in extra["thresholds"].items():
                print(f"  gamma={k:>6s}: {('NOT REACHED' if v is None else f't={v['t_s']:.2f}s h={v['h_km']:.2f}km')}")

    # ---------------- figures ---------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def phases(ax, tmax):
        ax.axvline(t_capture, color="tab:green", ls="--", lw=1.0)
        ax.axvline(t_gate, color="tab:red", ls="--", lw=1.0)
        ax.axvspan(0, t_capture, color="tab:orange", alpha=0.06)
        ax.axvspan(t_capture, t_gate, color="tab:green", alpha=0.06)
        ax.text(t_capture, ax.get_ylim()[1], "QEG CAPTURE", ha="right", va="top",
                fontsize=7, color="tab:green", rotation=90)
        ax.text(t_gate, ax.get_ylim()[1], "TERMINAL GATE", ha="right", va="top",
                fontsize=7, color="tab:red", rotation=90)
        ax.text(tmax, ax.get_ylim()[0], "GROUND", ha="right", va="bottom",
                fontsize=7, color="k")

    R1 = env.earth_radius * s1g[1] / 1000.0
    R2 = env.earth_radius * s2g[1] / 1000.0
    h1 = (s1g[0] - env.earth_radius) / 1000.0
    h2 = (s2g[0] - env.earth_radius) / 1000.0
    hT1 = (s_t1[0] - env.earth_radius) / 1000.0
    hT2 = (s_t2[0] - env.earth_radius) / 1000.0
    RT1 = env.earth_radius * s_t1[1] / 1000.0
    RT2 = env.earth_radius * s_t2[1] / 1000.0

    # 1) h-R
    fig, ax = plt.subplots(figsize=(8.0, 4.8))
    ax.plot(R1, h1, lw=1.1, color="tab:orange", label="ENTRY (u_L=1)")
    ax.plot(R2, h2, lw=1.1, color="tab:green", label="QEG GLIDE")
    ax.plot(RT1, hT1, lw=1.1, color="tab:blue", label="T1 full-lift descent")
    ax.plot(RT2, hT2, lw=1.1, color="tab:purple", ls="--", label="T2 zero-lift dive")
    ax.plot(R2[-1], h2[-1], "o", color="tab:red", ms=6)
    ax.plot(RT1[-1], 0, "v", color="tab:blue", ms=6)
    ax.plot(RT2[-1], 0, "v", color="tab:purple", ms=6)
    ax.set_xlabel("Range [km]"); ax.set_ylabel("Altitude [km]")
    ax.set_title("B.5-B2: h - R (common Entry+QEG, T1 and T2 continuations)")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_terminal_h_R.png", dpi=300); plt.close(fig)

    # 2-6) time series with phase markers
    pairs = [
        ("fig_terminal_h_t.png", "Altitude [km]", t1g, h1, t2g, h2, t_t1, hT1, t_t2, hT2),
        ("fig_terminal_v_t.png", "Velocity [m/s]", t1g, s1g[2], t2g, s2g[2], t_t1, s_t1[2], t_t2, s_t2[2]),
        ("fig_terminal_gamma_t.png", "gamma [deg]", t1g, np.degrees(s1g[3]), t2g, np.degrees(s2g[3]),
         t_t1, np.degrees(s_t1[3]), t_t2, np.degrees(s_t2[3])),
        ("fig_terminal_q_t.png", "q [kPa]", t1g, q_all1[:n1] / 1000.0, t2g, q_all1[n1:n1 + n2] / 1000.0,
         t_t1, q_t1 / 1000.0, t_t2, q_t2 / 1000.0),
    ]
    for fname, ylab, ta, ya, tb, yb, tc, yc, td, yd in pairs:
        fig, ax = plt.subplots(figsize=(8.0, 4.6))
        ax.plot(ta, ya, lw=1.1, color="tab:orange")
        ax.plot(tb, yb, lw=1.1, color="tab:green")
        ax.plot(tc, yc, lw=1.1, color="tab:blue", label="T1")
        ax.plot(td, yd, lw=1.1, color="tab:purple", ls="--", label="T2")
        ax.legend(fontsize=8)
        ax.set_xlabel("Time [s]"); ax.set_ylabel(ylab)
        ax.set_title(f"B.5-B2: {ylab} vs time")
        phases(ax, max(tf_t1, tf_t2)); ax.grid(True, ls=":", lw=0.5)
        fig.tight_layout(); fig.savefig(AUDIT_DIR / fname, dpi=300); plt.close(fig)

    # 6) u_L - t
    u_qeg = np.empty(n2)
    for i in range(n2):
        Li = derived_quantities(t2g[i], s2g[:, i], env, vehicle, control)["lift_n"]
        u_qeg[i] = float(np.clip(qeg._lreq(s2g[:, i], env, vehicle) / Li, 0.0, 1.0))
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t1g, np.ones(n1), lw=1.1, color="tab:orange")
    ax.plot(t2g, u_qeg, lw=1.1, color="tab:green")
    ax.plot(t_t1, u_t1, lw=1.1, color="tab:blue", label="T1: u_L = 1")
    ax.plot(t_t2, u_t2, lw=1.1, color="tab:purple", ls="--", label="T2: u_L = 0")
    ax.legend(fontsize=8)
    ax.set_xlabel("Time [s]"); ax.set_ylabel("u_L")
    ax.set_title("B.5-B2: u_L vs time"); ax.set_ylim(-0.1, 1.1)
    phases(ax, max(tf_t1, tf_t2)); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_terminal_uL_t.png", dpi=300); plt.close(fig)

    # 7) L and L_req for T1
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    ax.plot(t_t1, L_t1, lw=1.2, color="tab:green", label="L (full lift)")
    ax.plot(t_t1, Lreq_t1, lw=1.2, color="tab:red", ls="--", label="L_req = m(g-v^2/r) cos(gamma)")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Force [N]")
    ax.set_title("B.5-B2: L and L_req for T1 (terminal)")
    ax.legend(fontsize=8); ax.grid(True, ls=":", lw=0.5)
    fig.tight_layout(); fig.savefig(AUDIT_DIR / "fig_terminal_T1_L_Lreq.png", dpi=300); plt.close(fig)

    print(f"\nreport + 7 figures written to {AUDIT_DIR}")


if __name__ == "__main__":
    main()

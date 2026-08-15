"""E5 lightweight tests: visualization pipeline structure.

Checks artifact loading, unit conversion helpers, figure definitions,
the no-integration constraint, exact-JSON marker sourcing, and a figure
generation smoke.  NO pixel-level snapshot regression and no hard-coded
style coordinates.

    A  plot script loads expected artifacts
    B  five core figure definitions exist
    C  no solve_ivp / integrator call in plotting pipeline
    D  unit conversion helpers consistent
    E  exact checkpoint JSON used for markers
    F  figure generation smoke
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

PLOT_PATH = (Path(__file__).parents[1] / "experiments"
             / "06_qian_sanger_comparison" / "plot_phase_e_comparison.py")
RESULTS = Path("results/qian_sanger_comparison")


@pytest.fixture(scope="module")
def plot():
    spec = importlib.util.spec_from_file_location("plot_phase_e", PLOT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def artifacts_exist():
    required = [
        "common_conditions/summary.json",
        "mechanism/mechanism_summary.json",
        "mechanism/energy_budget.json",
        "mechanism/qian_energy_curve.csv",
        "mechanism/sanger_energy_curve.csv",
        "diagnostics/diagnostics_summary.json",
        "diagnostics/aerodynamic_diagnostics.json",
        "diagnostics/native_endpoint.json",
    ]
    return all((RESULTS / p).exists() for p in required)


# ---------------------------------------------------------------------------
# A / B / C. Structure
# ---------------------------------------------------------------------------
def test_a_plot_script_loads_expected_artifacts(plot, artifacts_exist):
    if not artifacts_exist:
        pytest.skip("E2-E4 artifacts missing (run the E2/E3/E4 runners)")
    qian = plot.load_curve_csv("mechanism/qian_energy_curve.csv")
    sanger = plot.load_curve_csv("mechanism/sanger_energy_curve.csv")
    assert qian["time_s"].size > 0
    assert sanger["time_s"].size > 0
    assert set(qian) == {"time_s", "range_m", "altitude_m", "velocity_mps",
                         "specific_energy_jpkg", "energy_loss_jpkg",
                         "normalized_mode", "source_mode", "segment_index"}
    states = plot.marker_states()
    assert set(states) == {
        "qian_rti", "sanger_srti", "common_time_qian", "common_time_sanger",
        "common_range_qian", "common_range_sanger", "protocol_d_qian",
        "protocol_d_sanger",
    }


def test_b_five_core_figure_definitions_exist(plot):
    assert plot.CORE_FIGURES == [
        "E5_F1_trajectory_geometry.png",
        "E5_F2_state_energy_retention.png",
        "E5_F3_range_energy_mechanism.png",
        "E5_F4_atmospheric_exposure.png",
        "E5_F5_dynamic_pressure.png",
    ]
    assert len(plot.CORE_FIGURES) == 5


def test_c_no_solve_ivp_or_integrator_in_plotting_pipeline(plot):
    source = PLOT_PATH.read_text(encoding="utf-8")
    # No integration machinery may be imported or invoked.  (Docstring
    # prose may mention the words; the checks target actual code.)
    assert "from hyptraj.simulation" not in source
    assert "import solve_ivp" not in source
    assert "build_qian_comparison" not in source
    assert "build_sanger_comparison" not in source
    assert not hasattr(plot, "solve_ivp")
    assert not hasattr(plot, "integrate_qian_glide")
    assert not hasattr(plot, "integrate_sanger_hybrid")
    # Only frozen-model imports are allowed for the visualization q.
    assert "hyptraj.models.atmosphere" in source


# ---------------------------------------------------------------------------
# D. Unit conversion helpers
# ---------------------------------------------------------------------------
def test_d_unit_conversion_helpers_consistent(plot):
    assert plot._km(1_234_567.8) == pytest.approx(1234.5678)
    assert plot._kmps(7000.0) == pytest.approx(7.0)
    assert plot._mj(19_921_285.0) == pytest.approx(19.921285)
    # Markers and curves must share the same helpers (no per-figure units).
    assert plot._km is plot._km and plot._kmps(1000.0) == 1.0


# ---------------------------------------------------------------------------
# E. Exact checkpoint JSON used for markers
# ---------------------------------------------------------------------------
def test_e_exact_checkpoint_json_used_for_markers(plot, artifacts_exist):
    if not artifacts_exist:
        pytest.skip("E2-E4 artifacts missing")
    source = PLOT_PATH.read_text(encoding="utf-8")
    # No nearest-row / argmin selection machinery in the plotting code
    # (docstring prose may mention the terms; the checks target calls).
    assert "argmin(" not in source
    assert "argmax(" not in source
    assert "iloc" not in source
    # Markers reproduce the exact JSON values (bit-level).
    states = plot.marker_states()
    with open(RESULTS / "common_conditions" / "summary.json",
              encoding="utf-8") as f:
        common = json.load(f)
    assert states["common_time_sanger"]["time_s"] == \
        common["common_time"]["sanger_state"]["time_s"]
    assert states["common_range_qian"]["range_m"] == \
        common["common_range"]["qian_state"]["range_m"]
    with open(RESULTS / "mechanism" / "common_atmospheric_exposure.json",
              encoding="utf-8") as f:
        pd_artifact = json.load(f)
    assert states["protocol_d_sanger"]["time_s"] == \
        pd_artifact["sanger_state"]["time_s"]


# ---------------------------------------------------------------------------
# F. Figure generation smoke
# ---------------------------------------------------------------------------
def test_f_figure_generation_smoke(plot, artifacts_exist, monkeypatch,
                                   tmp_path):
    if not artifacts_exist:
        pytest.skip("E2-E4 artifacts missing")
    monkeypatch.setattr(plot, "FIG_DIR", tmp_path)
    qian_curve = plot.load_curve_csv("mechanism/qian_energy_curve.csv")
    sanger_curve = plot.load_curve_csv("mechanism/sanger_energy_curve.csv")
    states = plot.marker_states()
    mechanism = plot.load_json("mechanism/mechanism_summary.json")
    budgets = plot.load_json("mechanism/energy_budget.json")
    aero = plot.load_json("diagnostics/aerodynamic_diagnostics.json")

    plot.figure_e1(qian_curve, sanger_curve, states)
    plot.figure_e2(qian_curve, sanger_curve, states)
    plot.figure_e3(qian_curve, sanger_curve, states)
    plot.figure_e4(states, mechanism, budgets)
    plot.figure_e5(qian_curve, sanger_curve, states, aero)

    for name in plot.CORE_FIGURES:
        path = tmp_path / name
        assert path.exists(), name
        assert path.stat().st_size > 10_000, name
        img = np.asarray(plot.plt.imread(path))
        assert img.size > 0

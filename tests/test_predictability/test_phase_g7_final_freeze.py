"""Phase-G7 final-freeze structural tests.

Fast, deterministic, STATEFUL against the committed freeze manifest
``tests/data/phase_g_final_freeze_v1.json``.  These tests deliberately do
NOT depend on git tags or git at all (tests run before the final tags are
created, and package source may be distributed without ``.git``): the tag
names and tag-target POLICY are frozen, while the tag targets themselves
are verified by the G7 shell audit.

Key contract: the manifest SHA-256 of every accepted scientific artifact
(protocol doc + G1-G6 snapshots) must equal the CURRENT committed artifact
SHA-256.  Any future modification of an accepted scientific snapshot
explicitly breaks this regression = the freeze is no longer locked.
"""

import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
DATA = REPO / "tests" / "data"
DOCS = REPO / "docs" / "phase_g"
MANIFEST = json.loads((DATA / "phase_g_final_freeze_v1.json")
                      .read_text(encoding="utf-8"))

ARTIFACTS = [
    "docs/phase_g/predictability_protocol.md",
    "tests/data/phase_g1_continuous_jacobian_v1.json",
    "tests/data/phase_g2_continuous_stm_v1.json",
    "tests/data/phase_g3_transverse_saltation_v1.json",
    "tests/data/phase_g4_hybrid_stm_v1.json",
    "tests/data/phase_g5_predictability_metrics_v1.json",
    "tests/data/phase_g6_grazing_predictability_v1.json",
]

ACCEPTED_CHAIN = [
    "G0", "G1", "G2", "G2R", "G3", "G4", "G4R",
    "G5", "G5R", "G6", "G6R", "G6R2",
]


def _sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _checkout(src: str, token: str) -> bool:
    return token not in src


@pytest.fixture(scope="module")
def g6():
    return json.loads((DATA / "phase_g6_grazing_predictability_v1.json")
                      .read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def g5():
    return json.loads((DATA / "phase_g5_predictability_metrics_v1.json")
                      .read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 51. Commit-chain test
# ---------------------------------------------------------------------------
def test_manifest_schema_and_status():
    assert MANIFEST["schema_version"] == "phase-g-final-freeze-v1"
    assert MANIFEST["status"] in ("PHASE G COMPLETE / FROZEN",)


def test_commit_chain_locked():
    chain = MANIFEST["provenance"]["accepted_stage_commits"]
    assert list(chain.keys()) == ACCEPTED_CHAIN
    # every stage commit is a full 40-hex SHA
    for stage, sha in chain.items():
        assert len(sha) == 40, stage
        int(sha, 16)
    assert MANIFEST["provenance"]["starting_final_scientific_commit"] \
        == chain["G6R2"]
    assert MANIFEST["provenance"]["upstream_phase_f_commit"].startswith(
        "96253f1")


def test_final_tags_policy_only_no_sha():
    ft = MANIFEST["final_tags"]
    assert ft["names"] == ["phase-g-v1.0", "predictability-v1.0"]
    assert ft["tag_target_policy"] == \
        "both tags point to the same final G7 freeze commit"
    # no self-referential final SHA recorded
    assert "final_g7_sha" not in MANIFEST


# ---------------------------------------------------------------------------
# 52. Artifact hash tests
# ---------------------------------------------------------------------------
def test_artifact_sha256_lock():
    hashes = MANIFEST["artifact_sha256"]
    assert set(hashes.keys()) == set(ARTIFACTS)
    for rel, sha in hashes.items():
        assert sha == _sha256(rel), f"freeze broken for {rel}"


# ---------------------------------------------------------------------------
# 53. Scaling final tests
# ---------------------------------------------------------------------------
def test_canonical_scaling_locked():
    cs = MANIFEST["canonical_scaling"]
    assert cs["candidate"] == "A"
    assert cs["scale_values"] == {"r": 1e5, "theta": 1.0,
                                  "v": 7e3, "gamma": 0.1}
    assert cs["status"] == "CANONICAL_SCALE_NUMERIC_VALUES_FROZEN"
    assert cs["ranking_scale_sensitive"] is True


# ---------------------------------------------------------------------------
# 54. G4/G5 final-contract tests
# ---------------------------------------------------------------------------
def test_fixed_time_topology_and_metrics_present():
    ft = MANIFEST["final_key_results"]["fixed_time"]
    assert ft["qian"]["T600"]["topology_signature"] == ["qian_capture"]
    assert ft["sanger"]["T600"]["topology_signature"] == [
        "sanger_atmosphere_exit", "sanger_atmosphere_entry"]
    assert ft["qian"]["T600"]["condition_status"] == "STRUCTURAL_SINGULAR"
    assert ft["qian"]["T600"]["numerical_rank"] == 3
    assert ft["sanger"]["T600"]["numerical_rank"] == 4
    assert ft["sanger"]["T600"]["condition_status"] == "FINITE"
    assert ft["sanger"]["T900"]["numerical_rank"] == 4


def test_scale_sensitivity_reported():
    sa = MANIFEST["final_key_results"]["scale_audit_T600"]
    # A ordering: Sanger sigma_max > Qian sigma_max
    assert sa["qian_T600"]["A"]["sigma_max"] < sa["sanger_T600"]["A"][
        "sigma_max"]
    # B ordering flips
    assert sa["qian_T600"]["B"]["sigma_max"] > sa["sanger_T600"]["B"][
        "sigma_max"]


def test_native_terminal_warning_present():
    assert "DESCRIPTIVE" in MANIFEST["final_key_results"][
        "native_terminal_warning"].upper() or "descriptive" in \
        MANIFEST["final_key_results"]["native_terminal_warning"].lower()
    assert MANIFEST["claim_boundaries"][
        "native_terminal_not_fair_cross_model_ranking"] is True


def test_terminal_eligibility_recorded():
    term = MANIFEST["final_key_results"]["terminal"]
    assert term["qian"]["terminal"] == "RTI"
    assert term["qian"]["rank"] == 2
    assert term["sanger"]["terminal"] in ("SRTI", "srti")
    assert term["sanger"]["rank"] == 3


# ---------------------------------------------------------------------------
# 55. G6/G6R2 final-contract tests
# ---------------------------------------------------------------------------
def test_grazing_threshold_locked():
    g6r = MANIFEST["final_key_results"]["grazing"]
    assert g6r["threshold_decision"] == "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED"
    assert MANIFEST["claim_boundaries"][
        "no_universal_numeric_grazing_threshold"] is True


def test_g6r2_normalization_locked():
    g6r2 = MANIFEST["final_key_results"]["grazing"]["g6r2_normalization"]
    assert g6r2["error_normalization"] == "ERROR_OVER_LINEAR_PREDICTION"
    assert g6r2["old_error_normalization"] == \
        "ERROR_OVER_NONLINEAR_INCREMENT"
    assert g6r2["paired_fd_results_unchanged"] is True
    # provenance retained (old nonlinear-denominator values)
    assert g6r2["old_radii_g6r_nonlinear_denominator"]["B0_a1"][
        "r_5pct_refined"] > 0.193


def test_g6r2_radii_final_authority_locked():
    g6r = MANIFEST["final_key_results"]["grazing"]
    radii = g6r["refined_validity_radii_final_G6R2"]
    assert list(radii.keys()) == ["B0_a0.5", "B0_a1", "B3_a1", "B4_a1"] or \
        set(radii) == {"B0_a1", "B0_a0.5", "B3_a1", "B4_a1"}
    for k, rec in radii.items():
        assert rec["r_1pct_refined"]["classification"] == \
            "MONOTONE_REFINED_RADIUS"
        assert 0.03 < rec["r_1pct_refined"]["radius_over_phi"] < 0.1
        assert 0.1 < rec["r_5pct_refined"]["radius_over_phi"] < 0.2
    assert MANIFEST["validity_radius_authority_chain"][
        "G6R2_linear_prediction_denominator"] == "FINAL_AUTHORITY"
    assert MANIFEST["validity_radius_authority_chain"][
        "G6_coarse_grid"] == "HISTORICAL"
    assert MANIFEST["validity_radius_authority_chain"][
        "G6R_nonlinear_denominator"] == "SUPERSEDED"


def test_dual_reference_and_paired_fd_locked():
    g6r = MANIFEST["final_key_results"]["grazing"]
    ca = g6r["contract_audit"]
    assert ca["n_anchors"] == 10
    assert ca["n_side_absence_confirmations"] == 5
    assert ca["n1_side_extractions"] == 5
    assert ca["dual_reference_stable_10of10"] is True
    for br in ("B0", "B4"):
        p = g6r["paired_fd"][br]
        assert p["radial_plateau_pass"] is True
        assert p["four_column_pass"] is True
        assert p["max_scaled_rel_error"] < 1e-2


def test_grazing_quadratic_scaling_recorded():
    g6r = MANIFEST["final_key_results"]["grazing"]
    fits = g6r["controlled_family_scaling"]
    assert set(fits) == {"B0", "B1", "B2", "B3", "B4"}
    for br, f in fits.items():
        assert f["H1_Phi_vs_d_slope"] == pytest.approx(2.0, abs=0.5)
        assert f["H3_pair_norm_vs_d_slope"] == pytest.approx(-1.0, abs=0.05)


# ---------------------------------------------------------------------------
# 56. Report / README stale-state tests
# ---------------------------------------------------------------------------
def test_final_report_present_and_authoritative():
    rep = (DOCS / "phase_g_final_report.md").read_text(encoding="utf-8")
    assert "# Phase G Final Report" in rep
    assert "FINITE-TIME LOCAL PREDICTABILITY" in rep.upper()
    assert "FINAL_AUTHORITY" in rep or "G6R2" in rep
    assert "NO_UNIVERSAL_NUMERIC_THRESHOLD_SUPPORTED" in rep
    assert "0.1" in rep  # limitations exist
    assert "observability analysis was outside Phase-G delivered scope" in rep


def test_readme_reaches_final_frozen_state():
    readme = (DOCS / "README.md").read_text(encoding="utf-8")
    assert "G7" in readme
    # no pending / accept-pending markers remain
    for stale in ("G7 PENDING", "G6R accept pending", "G6R2 accept pending",
                  "G7 pending", "G6R2 PENDING"):
        assert stale not in readme, stale


def test_old_radii_not_presented_as_authority():
    # G6 coarse / G6R nonlinear-denominator numbers must not appear as the
    # operative radii in the final report beyond provenance notes.
    rep = (DOCS / "phase_g_final_report.md").read_text(encoding="utf-8")
    assert "FINAL_AUTHORITY" in rep
    assert rep.count("0.03 / 0.10") <= 1  # provenance table only


# ---------------------------------------------------------------------------
# 61. Observability placeholder
# ---------------------------------------------------------------------------
def test_observability_placeholder_stays_empty():
    import importlib.util
    spec = importlib.util.find_spec("hyptraj.predictability.observability")
    assert spec is not None
    source = Path(spec.origin).read_text(encoding="utf-8")
    assert source.strip() == "", (
        "observability placeholder must remain empty (outside Phase-G scope)")


# ---------------------------------------------------------------------------
# 47/57. Claim boundaries (no git dependency)
# ---------------------------------------------------------------------------
def test_claim_boundaries_locked():
    cb = MANIFEST["claim_boundaries"]
    assert cb["finite_time_local_only"] is True
    assert cb["no_chaos_claim"] is True
    assert cb["no_probabilistic_uncertainty"] is True
    assert cb["no_optimization"] is True
    assert cb["no_gamma0K_rescan_in_phase_g"] is True
    assert cb["observability_analysis_outside_scope"] is True


def test_no_pytest_dependency_on_git_tags(g5, g6):
    # concrete guard: recommended snapshots still present and readable
    # without touching git
    assert g5["schema_version"] == "phase-g5-predictability-metrics-v1"
    assert g6["schema_version"] == "phase-g6-grazing-predictability-v1"

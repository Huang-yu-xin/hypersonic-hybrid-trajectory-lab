"""Run the locked, zero-simulator M4-PF3-0 archive diagnosis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path

import numpy as np

from hyptraj.m4pf3.diagnostics import (
    _as_proposal,
    allocation_diagnostics,
    build_birth_candidates,
    coverage_diagnostics,
    load_archive,
    responsibility_matrix,
    routing_verdict,
)


REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "configs" / "phase_m4pf3_0"
RESULT = REPO / "results" / "phase_m4pf3_0"
SUMMARY = RESULT / "summary"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def encode(value) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(child) for child in value]
    return value


def load_locks() -> tuple[dict, dict, dict]:
    protocol = json.loads((CONFIG / "m4pf3_0_protocol.json").read_text(
        encoding="utf-8"))
    source_lock = json.loads((CONFIG / "m4pf3_0_source_lock.json").read_text(
        encoding="utf-8"))
    manifest_path = REPO / source_lock["manifest_path"]
    if sha256_file(manifest_path) != source_lock[
            "manifest_sha256_before_analysis"]:
        raise RuntimeError("PF3-0 source manifest changed before analysis")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["source_count"] != source_lock["source_count"]:
        raise RuntimeError("PF3-0 source count mismatch")
    bad = [row["path"] for row in manifest["sources"]
           if sha256_file(REPO / row["path"]) != row["sha256"]]
    if bad:
        raise RuntimeError(f"PF3-0 source hash mismatch: {bad}")
    return protocol, source_lock, manifest


def metadata() -> tuple[dict, dict]:
    raw = json.loads((
        REPO / "results" / "phase_m4pf2" / "m4pf2_confirmation_raw.json"
    ).read_text(encoding="utf-8"))
    by_state = {row["state_id"]: row for row in raw["states"]}
    with (REPO / "results" / "phase_m4pf2" / "summary"
          / "m4pf2_state_table.csv").open(encoding="utf-8") as stream:
        p11 = {row["state_id"]: float(row["VRF_budget"])
               for row in csv.DictReader(stream) if row["cell"] == "P11"}
    return by_state, p11


def diagnostic_pass(protocol: dict, manifest: dict) \
        -> tuple[list[dict], list[dict], list[dict], dict]:
    state_meta, p11_vrf = metadata()
    archive_rows = sorted(
        (row for row in manifest["sources"]
         if row["role"] == "PF2 S0-anchor gradient archive"),
        key=lambda row: row["proposal_identity"]["state_id"])
    states, components, coverage_rows = [], [], []
    for ordinal, source in enumerate(archive_rows, 1):
        archive = load_archive(REPO / source["path"])
        identity = archive["proposal_identity"]
        state_id = identity["state_id"]
        alpha, means, covariances = _as_proposal(identity)
        responsibilities, _ = responsibility_matrix(
            archive["samples"], alpha, means, covariances)
        stored_component = int(identity["component_index"])
        responsibility_error = float(np.max(np.abs(
            responsibilities[:, stored_component] - archive["responsibility"])))
        if responsibility_error > 1e-10:
            raise RuntimeError(
                f"stored responsibility mismatch for {state_id}: "
                f"{responsibility_error}")
        allocation = allocation_diagnostics(
            archive["variance_mass"], responsibilities, alpha,
            protocol["allocation"]["starvation_epsilon"])
        coverage, d_min, nearest = coverage_diagnostics(
            archive["samples"], archive["variance_mass"], means, covariances,
            archive["source_strata"])
        meta = state_meta[state_id]
        state_row = {
            "state_id": state_id,
            "config_id": meta["state_key"]["config_id"],
            "s2": meta["state_key"]["s2"],
            "action_class": meta["class"],
            "diagnostic_anchor": identity["anchor_arm"],
            "component_count": int(alpha.size),
            "A_alloc": allocation["A_alloc"],
            "H_alpha": allocation["H_alpha"],
            "H_r_bar": allocation["H_r_bar"],
            "N_eff_alpha": allocation["N_eff_alpha"],
            "N_eff_r_bar": allocation["N_eff_r_bar"],
            "U99": coverage["U99"],
            "U999": coverage["U999"],
            "raw_outside99": coverage["raw_outside99"],
            "raw_outside999": coverage["raw_outside999"],
            "top_1pct_uncovered_fraction":
                coverage["top_1pct"]["uncovered_fraction_within_tail"],
            "top_0_1pct_uncovered_fraction":
                coverage["top_0_1pct"]["uncovered_fraction_within_tail"],
            "top_1pct_total_tilted_mass":
                coverage["top_1pct"]["total_tilted_mass"],
            "top_0_1pct_total_tilted_mass":
                coverage["top_0_1pct"]["total_tilted_mass"],
            "d_min2_median_raw": coverage["d_min2_median_raw"],
            "d_min2_q99_raw": coverage["d_min2_q99_raw"],
            "d_min2_tilted_mean": coverage["d_min2_tilted_mean"],
            "PF2_P11_VRF": p11_vrf[state_id],
            "responsibility_replay_max_abs_error": responsibility_error,
        }
        states.append(state_row)
        for k in range(alpha.size):
            components.append({
                "state_id": state_id,
                "action_class": meta["class"],
                "component_index": k,
                "is_pf2_updated_component": k == stored_component,
                "alpha": float(allocation["alpha"][k]),
                "r_bar": float(allocation["r_bar"][k]),
                "descent_direction": float(
                    allocation["descent_direction"][k]),
                "starvation_ratio": float(
                    allocation["starvation_ratio"][k]),
                "nearest_component_raw_fraction":
                    coverage["nearest_component_raw_fraction"][k],
                "nearest_component_tilted_mass":
                    coverage["nearest_component_tilted_mass"][k],
            })
        coverage_rows.append({
            **state_row,
            "tau99": coverage["tau99"],
            "tau999": coverage["tau999"],
            "nearest_component_tilted_mass_json":
                encode(coverage["nearest_component_tilted_mass"]),
            "nearest_component_raw_fraction_json":
                encode(coverage["nearest_component_raw_fraction"]),
            "source_stratum_uncovered_mass_json":
                encode(coverage["source_strata"]),
        })
        print(f"[PF3-0 {ordinal:02d}/24] {state_id} "
              f"A={allocation['A_alloc']:.4f} U99={coverage['U99']:.4f}",
              flush=True)
        del d_min, nearest
    route = routing_verdict(states, protocol)
    return states, components, coverage_rows, route


def candidate_pass(protocol: dict, manifest: dict, route: str) -> list[dict]:
    if route not in ("B", "C"):
        return []
    rows = []
    archives = sorted(
        (row for row in manifest["sources"]
         if row["role"] == "PF2 S0-anchor gradient archive"),
        key=lambda row: row["proposal_identity"]["state_id"])
    for source in archives:
        archive = load_archive(REPO / source["path"])
        identity = archive["proposal_identity"]
        alpha, means, covariances = _as_proposal(identity)
        coverage, d_min, _ = coverage_diagnostics(
            archive["samples"], archive["variance_mass"], means, covariances,
            archive["source_strata"])
        candidates = build_birth_candidates(
            archive["samples"], archive["variance_mass"],
            archive["source_strata"], identity, coverage, d_min, protocol)
        for candidate in candidates:
            rows.append({
                "state_id": identity["state_id"],
                "candidate_id": candidate["candidate_id"],
                "generator": candidate["generator"],
                "centre_json": encode(candidate["centre"]),
                "covariance_source_component":
                    candidate["covariance_source_component"],
                "covariance_json": encode(candidate["covariance"]),
                "source_stratum": candidate.get("source_stratum", ""),
                "source_stratum_uncovered_share":
                    candidate.get("source_stratum_uncovered_share", ""),
                "represented_uncovered_mass":
                    candidate["represented_uncovered_mass"],
                "represented_fraction_of_uncovered_mass":
                    candidate["represented_fraction_of_uncovered_mass"],
                "birth_score": candidate["birth_score"],
                "stream_scores_json": encode(candidate["stream_scores"]),
                "one_sided_95_t_lcb": candidate["one_sided_95_t_lcb"],
                "point_positive": candidate["point_positive"],
                "admitted": candidate["admitted"],
            })
    by_state = {}
    for row in rows:
        if row["admitted"]:
            by_state.setdefault(row["state_id"], []).append(row)
    for candidates in by_state.values():
        best = sorted(candidates,
                      key=lambda row: (-row["birth_score"],
                                       row["candidate_id"]))[0]
        best["selected_candidate"] = True
    for row in rows:
        row.setdefault("selected_candidate", False)
    return rows


def summarize(protocol: dict, source_lock: dict, manifest: dict,
              states: list[dict], candidates: list[dict], route: dict) -> dict:
    a = [row["A_alloc"] for row in states]
    u99 = [row["U99"] for row in states]
    u999 = [row["U999"] for row in states]
    positive_states = len({row["state_id"] for row in candidates
                           if row["point_positive"]})
    admitted_states = len({row["state_id"] for row in candidates
                           if row["admitted"]})
    sensitivity = [routing_verdict(states, protocol, multiplier)
                   for multiplier in protocol["routing"][
                       "sensitivity_multipliers"]]
    return {
        "schema_version": "raretopo-m4pf3-0-diagnostic-summary-v0",
        "stage": "M4-PF3-0",
        "extra_simulator_calls": 0,
        "source_manifest_sha256_before":
            source_lock["manifest_sha256_before_analysis"],
        "source_manifest_sha256_after": sha256_file(
            REPO / source_lock["manifest_path"]),
        "source_count": manifest["source_count"],
        "state_count": len(states),
        "allocation": {
            "median_A_alloc": float(statistics.median(a)),
            "states_ge_0_15": sum(value >= 0.15 for value in a),
            "minimum_A_alloc": min(a),
            "maximum_A_alloc": max(a),
            "median_H_alpha": float(statistics.median(
                row["H_alpha"] for row in states)),
            "median_H_r_bar": float(statistics.median(
                row["H_r_bar"] for row in states)),
        },
        "coverage": {
            "median_U99": float(statistics.median(u99)),
            "median_U999": float(statistics.median(u999)),
            "states_U99_ge_0_20": sum(value >= 0.20 for value in u99),
            "states_U999_ge_0_25": sum(value >= 0.25 for value in u999),
            "maximum_U99": max(u99),
            "maximum_U999": max(u999),
            "median_top_1pct_uncovered_fraction": float(statistics.median(
                row["top_1pct_uncovered_fraction"] for row in states)),
            "maximum_top_1pct_uncovered_fraction": max(
                row["top_1pct_uncovered_fraction"] for row in states),
        },
        "birth": {
            "candidate_count": len(candidates),
            "states_with_positive_candidate": positive_states,
            "states_with_admitted_candidate": admitted_states,
            "selected_candidate_count": sum(
                bool(row["selected_candidate"]) for row in candidates),
        },
        "routing": route,
        "routing_sensitivity": sensitivity,
        "next_authorized_stage": {
            "A": "PF3-A weight reallocation",
            "B": "PF3-B missing-mode birth/repair",
            "C": "PF3-C allocation x birth factorial",
            "D": "higher-level proposal/regime review; no PF3 intervention",
        }[route["route"]],
        "claim_boundary": (
            "frozen PF2 S0-anchor archive diagnosis; routing heuristic, "
            "not a deployable controller or universal mechanism claim"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    protocol, source_lock, manifest = load_locks()
    if args.validate_only:
        print(json.dumps({
            "source_count": manifest["source_count"],
            "source_manifest_sha256": sha256_file(
                REPO / source_lock["manifest_path"]),
            "extra_simulator_calls": 0,
        }, indent=2))
        return 0
    states, components, coverage, route = diagnostic_pass(protocol, manifest)
    candidates = candidate_pass(protocol, manifest, route["route"])
    summary = summarize(protocol, source_lock, manifest, states, candidates,
                        route)
    if summary["source_manifest_sha256_before"] != \
            summary["source_manifest_sha256_after"]:
        raise RuntimeError("PF3-0 source manifest changed during analysis")
    SUMMARY.mkdir(parents=True, exist_ok=True)
    write_csv(SUMMARY / "m4pf3_0_state_diagnostics.csv", states)
    write_csv(SUMMARY / "m4pf3_0_component_diagnostics.csv", components)
    write_csv(SUMMARY / "m4pf3_0_coverage_diagnostics.csv", coverage)
    if candidates:
        write_csv(SUMMARY / "m4pf3_0_birth_candidates.csv", candidates)
    (SUMMARY / "m4pf3_0_diagnostic_summary.json").write_text(
        json.dumps(jsonable(summary), indent=2, allow_nan=False) + "\n",
        encoding="utf-8")
    print(json.dumps(jsonable(summary), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

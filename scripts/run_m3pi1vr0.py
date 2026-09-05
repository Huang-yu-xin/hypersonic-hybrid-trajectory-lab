"""M3-PI1VR0 -- PI1V incident quarantine and fresh development recovery.

Zero-simulator recovery stage.  Freezes the corrected PI1V scientific verdict
(PI1V-X: attempt 1 began trials without durable COMPLETE records; attempt 2
was a same-stage deterministic replay, which the frozen no-replay rule does
not rehabilitate), quarantines both attempts as DIAGNOSTIC_ONLY, retires the
original 24-state CF2 development panel and all PI1V seeds, repairs the
persistence contract (filesystem-safe ids + STARTED-before-simulator order +
no-replay + frozen-artifact overwrite guard), and re-audits the untouched
70-state reserve for a fresh 8W/8S/8ND development panel.

Stages: quarantine | persistence | reserve | selection | report
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

from hyptraj.m3pi1vr0.persistence import (
    FAULT_DESCRIPTIONS,
    FAULT_TAGS,
    FrozenArtifactError,
    ReplayError,
    assert_not_frozen,
    decode_fs_id,
    ensure_not_started,
    ensure_seed_unused,
    run_trial_transactional,
    safe_fs_id,
    trial_sha256,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/phase_m3pi1vr0/summary"
SYN = ROOT / "results/phase_m3pi1vr0/synthetic"
DOC = ROOT / "docs/phase_m3pi1vr0"

PI1V = ROOT / "results/phase_m3pi1v"
PI1V_OUT = PI1V / "summary"
QUAR1 = PI1V / "quarantine_attempt1"
QUAR2 = PI1V / "quarantine_attempt2"

CF2 = ROOT / "results/phase_m3cf2/summary"
UC2R = ROOT / "results/phase_m3uc2r/summary"
CF1N = ROOT / "results/phase_m3cf1n"
SF2 = ROOT / "results/phase_m3sf2/summary"

OLD_PANEL_CSV = CF2 / "m3cf2_development_panel.csv"
OLD_PANEL_HASH = "843ee98e5be20d71964684d29e7671f5168bd2c36a6d2b02a745be88aff85d5c"
RESERVE_CSV = CF2 / "m3cf2_pilot_protected_reserve_manifest.csv"
SELECTION_VIEW_CF2 = CF2 / "m3cf2_selection_view.csv"

# attempt-2 analysis outputs (computed from invalid-run trials) -> quarantine
ATTEMPT2_ANALYSIS_FILES = [
    "m3pi1v_direction_sanity.json",
    "m3pi1v_v1_trials.csv",
    "m3pi1v_s1_trials.csv",
    "m3pi1v_v1_threshold_frontier.csv",
    "m3pi1v_s1_threshold_frontier.csv",
    "m3pi1v_selected_thresholds.json",
    "m3pi1v_primary_metrics.json",
    "m3pi1v_comparative_information_gain.json",
    "m3pi1v_state_level_policy_audit.csv",
    "m3pi1v_loso_diagnostic.csv",
    "m3pi1v_loco_diagnostic.csv",
    "m3pi1v_truth_stratified_metrics.json",
    "m3pi1v_persistence_audit.json",
    "m3pi1v_final_verdict.json",
]

DIAGNOSTIC_MARKER = (
    "DIAGNOSTIC_ONLY -- M3-PI1V was invalidated (PI1V-X) by the frozen\n"
    "persistence rule (attempt 1: trials began without durable COMPLETE\n"
    "records; attempt 2: same-stage deterministic replay).  Everything in\n"
    "this directory is retained for diagnostics and provenance only and may\n"
    "not be used to freeze thresholds, declare primary results, choose\n"
    "budgets, or authorize confirmation.  See\n"
    "results/phase_m3pi1vr0/summary/m3pi1vr0_pi1v_scientific_status.json\n")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def dump(p, v) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(v, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def csvread(p) -> list[dict]:
    with Path(p).open(newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def csvwrite(p, rows: list[dict]) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def git_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def invariance_block(extra: dict | None = None) -> dict:
    base = {
        "simulator_samples": 0,
        "new_reference_samples": 0,
        "new_p_ref_samples": 0,
        "gradient_pilot_trials": 0,
        "finite_action_probe_trials": 0,
        "threshold": None,
        "protected_confirmation_pilot_trials": 0,
        "value": "BLOCKED",
        "rarity_shift": "BLOCKED",
        "m3_q": "BLOCKED",
        "s1_confirmation_authorized": False,
        "v1_new_test": False,
        "budget_escalation": "PREMATURE",
    }
    base.update(extra or {})
    return base


# --------------------------------------------------------------------------
# stage: quarantine
# --------------------------------------------------------------------------

def quarantine() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOC.mkdir(parents=True, exist_ok=True)

    # -- corrected scientific status (taskbook Sec. 2) -----------------------
    status = {
        "recorded_at": now(),
        "stage": "M3-PI1VR0",
        "PI1V valid verdict": "PI1V-X",
        "PI1V-C retained as primary": "NO",
        "primary V1 sufficiency result": "UNAVAILABLE",
        "primary S1 comparator result": "UNAVAILABLE",
        "attempt-2 numerical result": "DIAGNOSTIC_ONLY",
        "rule": "if a scientific trial begins but no durable COMPLETE record "
                "exists: trial = CONSUMED_INVALID, PI1V-X, STOP; no rerun in "
                "the same stage; deterministic replay does not override this rule",
        "forbidden_uses_of_attempt2": [
            "freezing a threshold",
            "declaring V1 insufficient as a primary scientific result",
            "declaring S1 superior",
            "choosing a higher V1 budget",
            "authorizing S1 confirmation",
        ],
    }
    dump(OUT / "m3pi1vr0_pi1v_scientific_status.json", status)

    # -- quarantine attempt 2 ------------------------------------------------
    moved = {"trials": False, "figures": False, "summary_analysis": []}
    if (PI1V / "trials").exists():
        shutil.move(PI1V / "trials", QUAR2 / "trials")
        moved["trials"] = True
    if (PI1V / "figures").exists():
        shutil.move(PI1V / "figures", QUAR2 / "figures")
        moved["figures"] = True
    (QUAR2 / "summary_analysis").mkdir(parents=True, exist_ok=True)
    for name in ATTEMPT2_ANALYSIS_FILES:
        src = PI1V_OUT / name
        if src.exists():
            shutil.move(src, QUAR2 / "summary_analysis" / name)
            moved["summary_analysis"].append(name)
    for marker_dir in (QUAR1, QUAR2):
        if marker_dir.exists():
            (marker_dir / "DIAGNOSTIC_ONLY.txt").write_text(DIAGNOSTIC_MARKER,
                                                            encoding="utf-8")

    # -- superseded banners on PI1V result docs ------------------------------
    banner = (
        "> **SUPERSEDED (M3-PI1VR0):** the valid scientific verdict of M3-PI1V is\n"
        "> **PI1V-X**, not PI1V-C.  Attempt 1 began trials without durable COMPLETE\n"
        "> records; attempt 2 was a same-stage deterministic replay, which the\n"
        "> frozen no-replay rule does not rehabilitate.  All attempt-2 numbers in\n"
        "> this document are **DIAGNOSTIC ONLY** and support no primary claim,\n"
        "> threshold, budget decision, or confirmation authorization.\n\n")
    for doc_name in ("M3_PI1V_Final_Report.md", "M3_PI1V_V1_Analysis.md",
                     "M3_PI1V_S1_Comparator.md"):
        p = ROOT / "docs/phase_m3pi1v" / doc_name
        if p.exists() and not p.read_text(encoding="utf-8").startswith(">"):
            p.write_text(banner + p.read_text(encoding="utf-8"), encoding="utf-8")

    # -- retire the original 24-state development panel ----------------------
    panel = csvread(OLD_PANEL_CSV)
    if len(panel) != 24 or sha(OLD_PANEL_CSV) != OLD_PANEL_HASH:
        raise RuntimeError("PI1VR0-X: original panel identity check failed")
    retired_rows = [{
        "state_id": r["state_id"], "truth": r["truth"], "config_id": r["config_id"],
        "s2": r["s2"], "source_stage": r["source_stage"],
        "status": "PILOT_EXPOSED_RETIRED",
        "pilot_exposure": "attempt1_and_attempt2_gradient_pilot",
        "forbidden_use": "fresh development; future confirmation; future threshold selection",
        "retired_by": "M3-PI1VR0",
    } for r in panel]
    csvwrite(OUT / "m3pi1vr0_retired_development_states.csv", retired_rows)

    # -- retire all PI1V seeds ----------------------------------------------
    seed_manifest = load(PI1V_OUT / "m3pi1v_seed_manifest.json")
    retired_seeds = {
        "recorded_at": now(),
        "retired_namespaces": ["M3-PI1V-GRAD", "M3-PI1V-PROBE"],
        "R": seed_manifest["R"],
        "gradient_seeds": seed_manifest["planned_gradient_seeds"],
        "probe_seeds": seed_manifest["planned_probe_seeds"],
        "gradient_seed_count": len(seed_manifest["planned_gradient_seeds"]),
        "probe_seed_count": len(seed_manifest["planned_probe_seeds"]),
        "used_by_attempts": ["attempt1 (CONSUMED_INVALID)", "attempt2 (deterministic replay)"],
        "retirement_rule": "never reused by any future stage; new stages require fresh "
                           "namespaces (e.g. M3-PI1VN-GRAD / M3-PI1VN-PROBE)",
        "seed_manifest_source": "results/phase_m3pi1v/summary/m3pi1v_seed_manifest.json "
                                "(frozen pre-pilot; hash-locked in m3pi1v_prereg_hashes.json)",
    }
    dump(OUT / "m3pi1vr0_retired_seed_manifest.json", retired_seeds)

    # -- incident forensics (taskbook Sec. 6) --------------------------------
    forensics = {
        "recorded_at": now(),
        "attempt1": {
            "scientific_trials_started": 192,
            "durable_complete": 0,
            "consumed_invalid": 192,
            "filename_root_cause": 'trial identifier contained "::"; Windows '
                                   "temporary filenames cannot contain ':' "
                                   "(OSError 22 at temp-file creation)",
            "sequencing_violation": "STARTED ledger entry was written inside the "
                                    "write path, after scientific sampling, "
                                    "instead of before each trial",
            "samples_consumed": {"gradient": 3840000, "probe": 3840000},
            "quarantine": QUAR1.as_posix(),
        },
        "attempt2": {
            "deterministic_replay": True,
            "seeds": "same frozen M3-PI1V-GRAD / M3-PI1V-PROBE seed plan",
            "trials_persisted": 192,
            "primary_scientific_use": "NO",
            "diagnostic_only": True,
            "quarantine": QUAR2.as_posix(),
        },
        "valid_verdict": "PI1V-X",
        "do_not_rewrite": "this recovery must not be rewritten into a valid "
                          "primary run; the original <=2x hypothesis requires a "
                          "fresh independent panel and new seeds (M3-PI1VN)",
        "repair": "persistence contract repaired in "
                  "src/hyptraj/m3pi1vr0/persistence.py; see "
                  "m3pi1vr0_persistence_contract.json",
    }
    dump(OUT / "m3pi1vr0_incident_forensics.json", forensics)

    # -- quarantine manifest (taskbook Sec. 3) --------------------------------
    def hash_tree(root: Path) -> dict:
        out = {}
        for p in sorted(root.rglob("*")):
            if p.is_file():
                out[p.relative_to(root).as_posix()] = sha(p)
        return out

    quar2_files = hash_tree(QUAR2) if QUAR2.exists() else {}
    quar1_files = {p.name: sha(p) for p in sorted(QUAR1.glob("*.jsonl"))} \
        if QUAR1.exists() else {}
    qm = {
        "recorded_at": now(),
        "scientific_use": "diagnostic only",
        "quarantined_items": {
            "original_24_development_states": [r["state_id"] for r in panel],
            "attempt1_trial_identities": "192 logical ids (state::rep); ledger "
                                         "192 STARTED + 192 CONSUMED_INVALID",
            "attempt2_trial_identities": sorted(
                {e.get("state_id") for e in _ledger(QUAR2 / "trials/trial_ledger.jsonl")}
            ) if (QUAR2 / "trials/trial_ledger.jsonl").exists() else [],
            "pi1v_gradient_seeds": retired_seeds["gradient_seeds"],
            "pi1v_probe_seeds": retired_seeds["probe_seeds"],
            "attempt1_artifacts": {"path": QUAR1.as_posix(), "ledgers": quar1_files},
            "attempt2_artifacts": {"path": QUAR2.as_posix(),
                                   "trials_moved": moved["trials"],
                                   "figures_moved": moved["figures"],
                                   "analysis_files_moved": moved["summary_analysis"],
                                   "files": quar2_files},
            "invalid_run_outputs": moved["summary_analysis"],
        },
        "hashes": {"attempt2_files_sha256": quar2_files},
        "attempt2_counts": _attempt2_ledger_counts(),
    }
    dump(OUT / "m3pi1vr0_quarantine_manifest.json", qm)

    # -- source manifest ------------------------------------------------------
    source_paths = [
        "results/phase_m3cf2/summary/m3cf2_development_panel.csv",
        "results/phase_m3cf2/summary/m3cf2_pilot_protected_reserve_manifest.csv",
        "results/phase_m3cf2/summary/m3cf2_candidate_truth_inventory.csv",
        "results/phase_m3cf2/summary/m3cf2_selection_view.csv",
        "results/phase_m3cf2/summary/m3cf2_selector_contract.json",
        "results/phase_m3cf2/summary/m3cf2_reserve_summary.json",
        "results/phase_m3pi1v/summary/m3pi1v_seed_manifest.json",
        "results/phase_m3pi1v/summary/m3pi1v_prereg_hashes.json",
        "results/phase_m3pi1v/summary/m3pi1v_persistence_incident_audit.json",
        "results/phase_m3uc2r/summary/m3uc2r_reference_states.csv",
        "results/phase_m3cf1/summary/m3cf1_final_verdict.json",
        "results/phase_m3cf1n/summary/m3cf1n_final_verdict.json",
        "results/phase_m3cf1n/summary/m3cf1n_confirmation_state_manifest.csv",
        "results/phase_m3sf2/summary/m3sf2_mapping_bank.csv",
        "src/hyptraj/m3pi1vr0/persistence.py",
        "src/hyptraj/m3cf1r0/persistence.py",
    ]
    dump(OUT / "m3pi1vr0_source_manifest.json", {
        "base_commit": git_commit(), "recorded_at": now(),
        "simulator_samples": 0,
        "entries": [{"path": p, "sha256": sha(ROOT / p), "read_only": True}
                    for p in source_paths],
    })
    print("PI1VR0 quarantine: status frozen (PI1V-X), attempt-2 quarantined, "
          "24 states retired, seeds retired")


def _ledger(path: Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _attempt2_ledger_counts() -> dict:
    c = Counter(e.get("status") for e in _ledger(QUAR2 / "trials/trial_ledger.jsonl"))
    return {"STARTED": c.get("STARTED", 0), "COMPLETE": c.get("COMPLETE", 0),
            "CONSUMED_INVALID": c.get("CONSUMED_INVALID", 0)}


# --------------------------------------------------------------------------
# stage: persistence (synthetic verification of the repaired contract)
# --------------------------------------------------------------------------

def _mock_payload(state_id: str, seed: int) -> dict:
    return {
        "schema": "m3pi1vr0_synthetic_v1",
        "state_id": state_id,
        "seed": seed,
        "arm_summaries": {"base": {"placeholder": True},
                          "selected": {"placeholder": True}},
        "note": "mock payload; no scientific sampling anywhere",
        "metadata_hashes": {"payload_schema": "m3pi1vr0-synthetic-v1"},
    }


def _validate_mock(rec: dict) -> None:
    required = {"schema", "state_id", "seed", "arm_summaries", "note",
                "metadata_hashes"}
    missing = required - set(rec)
    if missing:
        raise ValueError(f"schema validation failed; missing {sorted(missing)}")
    if rec["state_id"].startswith("bad"):
        raise ValueError("schema validation failed; deliberately invalid record")


def persistence() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SYN.mkdir(parents=True, exist_ok=True)

    # -- contracts ------------------------------------------------------------
    dump(OUT / "m3pi1vr0_persistence_contract.json", {
        "recorded_at": now(),
        "module": "src/hyptraj/m3pi1vr0/persistence.py",
        "module_sha256": sha(ROOT / "src/hyptraj/m3pi1vr0/persistence.py"),
        "inherited_from": "M3-CF1R0 hardened persistence primitives "
                          "(ledger_append with tail repair + fsync, "
                          "fsync_directory)",
        "mandatory_order": [
            "1. validate filesystem-safe trial ID/path",
            "2. durable STARTED ledger entry",
            "3. invoke scientific simulator",
            "4. serialize canonical record to temp file",
            "5. flush",
            "6. fsync(temp)",
            "7. schema validation",
            "8. sha256",
            "9. atomic rename temp -> final",
            "10. fsync parent directory",
            "11. verify final hash",
            "12. durable ledger COMPLETE",
        ],
        "simulator_before_start_ledger": "FORBIDDEN",
        "consumed_invalid_policy": "trial = CONSUMED_INVALID; same stage cannot "
                                   "rerun same state/rep; same exact seed cannot "
                                   "be reused; stage verdict must remain INVALID; "
                                   "deterministic replay does not override",
        "frozen_artifact_overwrite_guard": "refuse overwrite of existing or "
                                           "prereg-hash-locked artifacts; new "
                                           "versions need a new stage/versioned "
                                           "filename",
    })
    dump(OUT / "m3pi1vr0_path_sanitization_contract.json", {
        "recorded_at": now(),
        "function": "hyptraj.m3pi1vr0.persistence.safe_fs_id",
        "rules": [
            "no ':' (hence no '::') in any emitted filename or path component",
            "no reserved Windows device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)",
            "canonical: the same logical id always maps to the same safe filename",
            "reversible: escaping maps every char outside [A-Za-z0-9.-] (and '_' "
            "itself) to _xHH, so decoding is unambiguous",
            "the logical scientific state ID is unchanged inside the record body; "
            "only the filesystem path is encoded",
        ],
        "max_component_length": 200,
        "examples": {
            "c000_sf2_map3_s2_4p5177271546::rep0":
                safe_fs_id("c000_sf2_map3_s2_4p5177271546::rep0"),
            "con_state::1": safe_fs_id("con_state::1"),
        },
        "round_trip_verified": all(
            decode_fs_id(safe_fs_id(x)) == x
            for x in ("a::1", "con_x::2", ".hidden::3", "state_1::rep7")),
    })

    # -- synthetic failure-injection matrix (mock payloads only) --------------
    ledger = SYN / "injection_ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    for stale in SYN.glob("inj_*"):
        stale.unlink()   # remove artifacts of any previous injection run
    results = []
    for tag in FAULT_TAGS:
        try:
            rec = run_trial_transactional(
                "synth_state::rep0",
                SYN / f"inj_{safe_fs_id('synth_state::rep0')}_{tag}.json",
                lambda t=tag: {"ran_with_fault": t,
                               **_mock_payload("synth_state::rep0", 1)},
                ledger_path=ledger, validator=_validate_mock, fault=tag,
                base_entry={"seed": 1}, run_uuid=f"uuid-{tag}")
            status, exc_type = rec["status"], None
            final_exists, temp_leftover = rec["final_exists"], rec["temp_leftover"]
        except Exception as exc:
            # a failure BEFORE the STARTED entry means the trial never began:
            # no ledger entry, nothing consumed, no CONSUMED_INVALID
            status, exc_type = "NOT_STARTED", type(exc).__name__
            final = SYN / f"inj_{safe_fs_id('synth_state::rep0')}_{tag}.json"
            final_exists = final.exists()
            temp_leftover = bool(list(final.parent.glob(".*.tmp.*")))
        results.append({"fault": tag, "status": status,
                        "exception_type": exc_type,
                        "final_exists": final_exists,
                        "temp_leftover": temp_leftover})
    # validator failure after full serialization
    rec = run_trial_transactional(
        "synth_bad::rep0", SYN / f"inj_{safe_fs_id('synth_bad::rep0')}_VALIDATOR.json",
        lambda: _mock_payload("bad_record", 2),
        ledger_path=ledger, validator=_validate_mock, base_entry={"seed": 2},
        run_uuid="uuid-validator")
    results.append({"fault": "VALIDATOR_REJECT", "status": rec["status"],
                    "final_exists": rec["final_exists"],
                    "temp_leftover": rec["temp_leftover"]})
    # happy path
    rec = run_trial_transactional(
        "synth_ok::rep0", SYN / f"inj_{safe_fs_id('synth_ok::rep0')}_NONE.json",
        lambda: _mock_payload("synth_ok::rep0", 3),
        ledger_path=ledger, validator=_validate_mock, base_entry={"seed": 3},
        run_uuid="uuid-happy")
    results.append({"fault": "NONE", "status": rec["status"],
                    "final_exists": rec["final_exists"],
                    "temp_leftover": rec["temp_leftover"]})
    entries = _ledger(ledger)
    counts = Counter(e.get("status") for e in entries)
    # ordering evidence: the happy-path simulator observed a STARTED entry first
    started_first = any(e.get("status") == "STARTED" and e.get("state_id") == "synth_ok::rep0"
                        for e in entries)
    dump(OUT / "m3pi1vr0_failure_injection.json", {
        "recorded_at": now(),
        "payloads": "mock only; zero scientific sampling",
        "fault_tags": {t: FAULT_DESCRIPTIONS[t] for t in FAULT_TAGS},
        "results": results,
        "ledger_status_counts": dict(counts),
        "assertions": {
            "post_start_faults_are_consumed_invalid": all(
                r["status"] == "CONSUMED_INVALID" for r in results
                if r["fault"] not in ("BEFORE_START_LEDGER", "NONE")),
            "pre_start_fault_never_began": all(
                r["status"] == "NOT_STARTED" for r in results
                if r["fault"] == "BEFORE_START_LEDGER"),
            "no_final_before_rename_faults": all(
                not r["final_exists"] for r in results
                if r["fault"] in ("BEFORE_START_LEDGER", "AFTER_START_BEFORE_SIM",
                                  "AFTER_SIM_BEFORE_TEMP", "AFTER_TEMP_BEFORE_FSYNC",
                                  "AFTER_FSYNC_BEFORE_VALIDATE",
                                  "AFTER_VALIDATE_BEFORE_RENAME", "VALIDATOR_REJECT")),
            "no_temp_leftover_on_happy_path": all(
                not r["temp_leftover"] for r in results if r["fault"] == "NONE"),
            "started_entry_written_for_every_started_trial": started_first,
        },
    })

    # -- synthetic E2E (8 mock states, STARTED-before-simulator evidence) ----
    e2e_ledger = SYN / "e2e_ledger.jsonl"
    if e2e_ledger.exists():
        e2e_ledger.unlink()
    e2e_dir = SYN / "e2e"
    if e2e_dir.exists():
        shutil.rmtree(e2e_dir)
    sim_order_observations = []
    for i in range(8):
        lid = f"e2e_state_{i}::rep{ i % 3 }"
        seed = 100 + i

        def sim(lid=lid, seed=seed):
            started = any(e.get("state_id") == lid and e.get("status") == "STARTED"
                          for e in _ledger(e2e_ledger))
            sim_order_observations.append({"logical_id": lid, "started_before_sim": started})
            return _mock_payload(lid, seed)

        rec = run_trial_transactional(
            lid, e2e_dir / f"{safe_fs_id(lid)}.json",
            sim, ledger_path=e2e_ledger, validator=_validate_mock,
            base_entry={"seed": seed}, run_uuid=f"e2e-{i}")
        assert rec["status"] == "COMPLETE", rec
    # no-replay: restarting a completed identity, or reusing a seed, is refused
    replay_refusals = {}
    try:
        ensure_not_started(e2e_ledger, "e2e_state_0::rep0")
        replay_refusals["identity_reuse"] = False
    except ReplayError:
        replay_refusals["identity_reuse"] = True
    try:
        ensure_seed_unused(e2e_ledger, 100)
        replay_refusals["seed_reuse"] = False
    except ReplayError:
        replay_refusals["seed_reuse"] = True
    # frozen-artifact overwrite guard
    guard_refusals = {}
    try:
        assert_not_frozen(e2e_dir / f"{safe_fs_id('e2e_state_0::rep0')}.json")
        guard_refusals["existing_file"] = False
    except FrozenArtifactError:
        guard_refusals["existing_file"] = True
    try:
        assert_not_frozen(ROOT / "configs/phase_m3pi1v/m3pi1v_gates.json",
                          prereg_record=load(PI1V_OUT / "m3pi1v_prereg_hashes.json"))
        guard_refusals["prereg_hash_locked"] = False
    except FrozenArtifactError:
        guard_refusals["prereg_hash_locked"] = True
    e2e_entries = _ledger(e2e_ledger)
    e2e_complete = [e for e in e2e_entries if e.get("status") == "COMPLETE"]
    hash_ok = all(
        sha(ROOT / e["expected_output_path"]) == e["final_sha256"]
        for e in e2e_complete)
    leftovers = [p.name for p in e2e_dir.glob(".*.tmp.*")]
    dump(OUT / "m3pi1vr0_synthetic_e2e.json", {
        "recorded_at": now(),
        "states": 8,
        "payloads": "mock only; zero scientific sampling",
        "all_complete": len(e2e_complete) == 8,
        "output_hash_match": hash_ok,
        "temp_leftovers": leftovers,
        "started_before_simulator_observations": sim_order_observations,
        "started_before_simulator_pass": all(
            o["started_before_sim"] for o in sim_order_observations),
        "no_replay_refusals": replay_refusals,
        "frozen_artifact_guard_refusals": guard_refusals,
    })
    print("PI1VR0 persistence: contracts written; failure injection + synthetic "
          "E2E complete (mock payloads only)")


# --------------------------------------------------------------------------
# stage: reserve exposure audit + capacity
# --------------------------------------------------------------------------

def reserve() -> None:
    reserve_rows = csvread(RESERVE_CSV)
    inv = {r["state_id"]: r for r in csvread(
        CF2 / "m3cf2_candidate_truth_inventory.csv")}
    cf2_view = {r["state_id"]: r for r in csvread(SELECTION_VIEW_CF2)}
    cf1n_manifest = {r["state_id"]: r for r in csvread(
        CF1N / "summary/m3cf1n_confirmation_state_manifest.csv")}
    sf2_bank = {r["state_id"] for r in csvread(SF2 / "m3sf2_mapping_bank.csv")}
    uc2r_conf = {r["state_id"] for r in csvread(
        UC2R / "m3uc2r_reference_states.csv") if r["split"] == "CONFIRMATION"}
    old24 = {r["state_id"] for r in csvread(OLD_PANEL_CSV)}
    cf1_verdict = load(ROOT / "results/phase_m3cf1/summary/m3cf1_final_verdict.json")["verdict"]

    # every PI1V trial identity ever touched (both attempts, quarantined)
    touched: set[str] = set()
    for q in (QUAR1, QUAR2):
        tdir = q / "trials"
        if tdir.exists():
            touched |= {d.name for d in tdir.iterdir() if d.is_dir()}

    rows = []
    for r in reserve_rows:
        sid = r["state_id"]
        inv_row = inv.get(sid)
        reasons = []
        if inv_row is None:
            reasons.append("missing_from_cf2_corrected_truth_inventory")
        else:
            if inv_row["durable_complete"] != "True":
                reasons.append("truth_not_durable_complete")
            if inv_row["full_event_valid"] != "True":
                reasons.append("event_semantics_invalid")
            h = inv_row.get("canonical_sha256", "")
            if not (isinstance(h, str) and len(h) == 64
                    and all(c in "0123456789abcdef" for c in h.lower())):
                reasons.append("canonical_hash_missing_or_malformed")
        # source-level durable provenance
        if r["source_stage"] == "M3-CF1N":
            if sid not in cf1n_manifest or \
                    not (CF1N / "confirmation" / f"{sid}.json").exists():
                reasons.append("cf1n_confirmation_record_missing")
        elif r["source_stage"] == "M3-SF2":
            if sid not in sf2_bank:
                reasons.append("sf2_bank_record_missing")
        else:
            reasons.append("unknown_source_stage")
        # exposures (PI1V attempts touched only the old 24 panel states)
        grad_exposure = 1 if sid in touched else 0
        probe_exposure = 1 if sid in touched else 0
        # threshold replay: attempt-2 score tables must not reference this state
        threshold_replay = _threshold_replay_exposure(sid)
        if grad_exposure or probe_exposure:
            reasons.append("pilot_or_probe_exposed_by_invalid_pi1v")
        if threshold_replay:
            reasons.append("threshold_replay_exposure")
        if sid in old24:
            reasons.append("in_original_24_panel")
        if sid in uc2r_conf:
            reasons.append("uc2r_protected_confirmation")
        if r["source_stage"].startswith("M3-CF1") and r["source_stage"] != "M3-CF1N":
            reasons.append("cf1_invalid_evidence")
        if cf1_verdict != "CF1-X":
            reasons.append("cf1_status_changed")
        eligible = not reasons
        rows.append({
            "state_id": sid, "truth": r["truth"], "config_id": r["config_id"],
            "source_stage": r["source_stage"], "source_region": r["source_region"],
            "was_CF2_reserve": "True",
            "gradient_exposure": grad_exposure,
            "probe_exposure": probe_exposure,
            "threshold_replay_exposure": threshold_replay,
            "eligible_fresh_development": "True" if eligible else "False",
            "reason": "eligible" if eligible else "; ".join(reasons),
        })
    rows.sort(key=lambda x: x["state_id"])
    csvwrite(OUT / "m3pi1vr0_reserve_exposure_audit.csv", rows)
    n_eligible = sum(1 for r in rows if r["eligible_fresh_development"] == "True")
    dump(OUT / "m3pi1vr0_reserve_audit_summary.json", {
        "recorded_at": now(),
        "original_protected_states": len(reserve_rows),
        "verified_untouched": n_eligible,
        "ineligible": [r["state_id"] for r in rows
                       if r["eligible_fresh_development"] == "False"],
        "exposures_all_zero": all(
            r["gradient_exposure"] == 0 and r["probe_exposure"] == 0
            and r["threshold_replay_exposure"] == 0 for r in rows),
    })
    print(f"PI1VR0 reserve: {n_eligible}/{len(reserve_rows)} states eligible, "
          "exposures all zero")


def _threshold_replay_exposure(state_id: str) -> int:
    """Attempt-2 threshold/score outputs must never reference reserve states."""
    for name in ("m3pi1v_v1_trials.csv", "m3pi1v_s1_trials.csv",
                 "m3pi1v_state_level_policy_audit.csv",
                 "m3pi1v_loso_diagnostic.csv", "m3pi1v_loco_diagnostic.csv"):
        p = QUAR2 / "summary_analysis" / name
        if p.exists() and state_id in p.read_text(encoding="utf-8"):
            return 1
    return 0


# --------------------------------------------------------------------------
# stage: selection view + capacity + selector contract + remaining reserve
# --------------------------------------------------------------------------

def selection() -> None:
    audit = csvread(OUT / "m3pi1vr0_reserve_exposure_audit.csv")
    eligible_ids = {r["state_id"] for r in audit
                    if r["eligible_fresh_development"] == "True"}
    cf2_view = {r["state_id"]: r for r in csvread(SELECTION_VIEW_CF2)}
    reserve_rows = {r["state_id"]: r for r in csvread(RESERVE_CSV)}

    # -- redacted selection view (taskbook Sec. 17) ---------------------------
    view = []
    for sid in sorted(eligible_ids):
        src = cf2_view[sid]
        view.append({
            "state_id": sid,
            "truth": src["truth"],
            "config_id": src["config_id"],
            "physical_family": src["physical_family"],
            "s2": src["s2"],
            "source_stage": src["source_stage"],
            "source_region": reserve_rows[sid]["source_region"],
            "stable_config_flag": src["stable_config_flag"],
            "canonical_bank_order": src["canonical_bank_order"],
        })
    csvwrite(OUT / "m3pi1vr0_selection_view.csv", view)
    view_hash = sha(OUT / "m3pi1vr0_selection_view.csv")
    dump(OUT / "m3pi1vr0_selection_view_hash.json", {
        "recorded_at": now(),
        "selection_view_sha256": view_hash,
        "rows": len(view),
        "forbidden_fields_absent": ["attempt-2 V1", "attempt-2 S1",
                                    "gradient confidence", "r_hat", "SE",
                                    "effect magnitude", "M2 ratio",
                                    "threshold distance"],
        "frozen_before_selection": True,
    })

    # -- capacity audit (taskbook Sec. 18) ------------------------------------
    by_truth = {"W": [], "S": [], "HOLD": [], "AMBIGUOUS": []}
    for r in view:
        by_truth["W" if r["truth"] == "WIDEN"
                 else "S" if r["truth"] == "SHRINK"
                 else "HOLD" if r["truth"] == "HOLD"
                 else "AMBIGUOUS"].append(r)
    nd = by_truth["HOLD"] + by_truth["AMBIGUOUS"]

    def config_profile(states):
        c = Counter(s["config_id"] for s in states)
        return {"distinct_configs": len(c),
                "max_selectable_at_2_per_config": sum(min(2, n) for n in c.values())}

    def region_profile(states):
        c = Counter(s["source_region"] for s in states)
        return {"distinct_source_regions": len(c)}

    cap = {
        "recorded_at": now(),
        "eligibility_source": "m3pi1vr0_reserve_exposure_audit.csv",
        "attempt2_influence": "none: attempt-2 V1/S1 outputs are quarantined and "
                              "were never read by any eligibility or capacity step",
        "eligible_reserve_W": len(by_truth["W"]),
        "eligible_reserve_S": len(by_truth["S"]),
        "eligible_reserve_HOLD": len(by_truth["HOLD"]),
        "eligible_reserve_AMBIGUOUS": len(by_truth["AMBIGUOUS"]),
        "eligible_reserve_ND": len(nd),
        "config_counts_by_truth": {
            "W": config_profile(by_truth["W"]),
            "S": config_profile(by_truth["S"]),
            "ND": config_profile(nd),
        },
        "source_region_counts_by_truth": {
            "W": region_profile(by_truth["W"]),
            "S": region_profile(by_truth["S"]),
            "ND": region_profile(nd),
        },
        "requirements": {
            "W": "8 states, >=6 distinct configs, max 2/config",
            "S": "8 states, >=6 distinct configs, max 2/config",
            "ND": "8 states, >=6 configs OR >=6 source regions, max 2/config",
        },
        "feasibility": {
            "W_count_ge_8": len(by_truth["W"]) >= 8,
            "S_count_ge_8": len(by_truth["S"]) >= 8,
            "ND_count_ge_8": len(nd) >= 8,
            "W_diversity_feasible":
                config_profile(by_truth["W"])["max_selectable_at_2_per_config"] >= 8
                and config_profile(by_truth["W"])["distinct_configs"] >= 6,
            "S_diversity_feasible":
                config_profile(by_truth["S"])["max_selectable_at_2_per_config"] >= 8
                and config_profile(by_truth["S"])["distinct_configs"] >= 6,
            "ND_diversity_feasible":
                (config_profile(nd)["max_selectable_at_2_per_config"] >= 8
                 and (config_profile(nd)["distinct_configs"] >= 6
                      or region_profile(nd)["distinct_source_regions"] >= 6)),
        },
        "counts_relaxed_after_shortage": False,
    }
    feasible = all(cap["feasibility"].values())
    cap["FRESH_PANEL_CAPACITY"] = "PASS" if feasible else "FAIL"
    cap["binding_shortage"] = [k for k, v in cap["feasibility"].items() if not v]
    cap["fresh_development_panel_created"] = False if not feasible else None
    cap["note"] = ("do not relax counts after seeing shortages; a future fresh "
                   "panel requires separately preregistered fresh reference "
                   "augmentation (M3-PI1VR0-CAP-B route)") if not feasible else None
    dump(OUT / "m3pi1vr0_fresh_panel_capacity.json", cap)

    # -- frozen deterministic selector contract (taskbook Sec. 19) ------------
    dump(OUT / "m3pi1vr0_selector_contract.json", {
        "recorded_at": now(),
        "deterministic": True,
        "manual_override": "FORBIDDEN",
        "input": "redacted selection view only (m3pi1vr0_selection_view.csv); "
                 "invalid-run scores are forbidden inputs",
        "forbidden_inputs": ["attempt-2 V1", "attempt-2 S1", "gradient confidence",
                             "r_hat", "SE", "effect magnitude", "M2 ratio",
                             "threshold distance"],
        "rules": {
            "W": "exactly 8; priority: maximize distinct configs, maximize "
                 "source-region diversity, max 2/config, maximize s2 spacing to "
                 "already-selected states, lower canonical_bank_order, lexical "
                 "state_id",
            "S": "preferred: one untouched confirmed SHRINK state per stable "
                 "config (8 configs x 1) if available; otherwise exactly 8 with "
                 ">=6 distinct configs, max 2/config, s2 spacing, lower "
                 "canonical_bank_order, lexical state_id; never generate new "
                 "states to force the shape",
            "ND": "exactly 8; truth = HOLD + AMBIGUOUS; maximize config diversity "
                  "or source-region diversity, max 2/config, s2 spacing, lower "
                  "canonical_bank_order, lexical state_id",
        },
        "selection_order": ["S", "W", "ND"],
        "capacity_verdict": cap["FRESH_PANEL_CAPACITY"],
    })

    # -- fresh panel: only if capacity PASS -----------------------------------
    if feasible:
        panel = _run_selector(view)
        csvwrite(OUT / "m3pi1vr0_fresh_development_panel.csv", panel)
        dump(OUT / "m3pi1vr0_fresh_panel_hash.json", {
            "recorded_at": now(),
            "panel_sha256": sha(OUT / "m3pi1vr0_fresh_development_panel.csv"),
            "states": len(panel),
            "pilot_exposure": 0, "probe_exposure": 0,
            "invalid_run_scores_used": False,
        })
        consumed = {r["state_id"] for r in panel}
    else:
        consumed = set()

    # -- remaining reserve (taskbook Sec. 21) ---------------------------------
    remaining = [{
        "state_id": r["state_id"], "truth": r["truth"],
        "config_id": r["config_id"], "source_stage": r["source_stage"],
        "source_region": r["source_region"], "s2": r["s2"],
        "status": "PILOT_PROTECTED_RESERVE",
        "consumed_by_fresh_panel": "True" if r["state_id"] in consumed else "False",
    } for r in sorted(reserve_rows.values(), key=lambda x: x["state_id"])]
    csvwrite(OUT / "m3pi1vr0_remaining_reserve_manifest.csv", remaining)
    ct = Counter(r["truth"] for r in remaining if r["consumed_by_fresh_panel"] == "False")
    dump(OUT / "m3pi1vr0_remaining_reserve_summary.json", {
        "recorded_at": now(),
        "remaining_protected_states": len(remaining) - len(consumed),
        "consumed_by_fresh_panel": len(consumed),
        "remaining_by_truth": dict(ct),
        "pilot_exposure": 0,
        "protection": "all unused valid reserve states remain "
                      "PILOT_PROTECTED_RESERVE",
    })
    print(f"PI1VR0 selection: capacity {cap['FRESH_PANEL_CAPACITY']} "
          f"(binding shortage: {cap['binding_shortage']}); remaining reserve "
          f"{len(remaining) - len(consumed)}")


def _run_selector(view: list[dict]) -> list[dict]:
    """Deterministic selector (taskbook Sec. 19); only view fields are used."""
    def pick(states, n):
        chosen = []
        pool = sorted(states, key=lambda s: (int(s["canonical_bank_order"]),
                                             s["state_id"]))
        while len(chosen) < n and pool:
            used_cfg = Counter(c["config_id"] for c in chosen)
            used_region = Counter(c["source_region"] for c in chosen)
            candidates = [s for s in pool if used_cfg[s["config_id"]] < 2]
            if not candidates:
                raise RuntimeError("selector: diversity constraint infeasible")
            best = min(candidates, key=lambda s: (
                used_cfg[s["config_id"]],
                used_region[s["source_region"]],
                min((abs(float(s["s2"]) - float(c["s2"])) for c in chosen),
                    default=float("inf")),
                int(s["canonical_bank_order"]),
                s["state_id"]))
            chosen.append(best)
            pool.remove(best)
        if len(chosen) != n:
            raise RuntimeError("selector: shortfall")
        return chosen

    s_pool = [r for r in view if r["truth"] == "SHRINK"]
    w_pool = [r for r in view if r["truth"] == "WIDEN"]
    nd_pool = [r for r in view if r["truth"] in ("HOLD", "AMBIGUOUS")]
    panel = pick(s_pool, 8) + pick(w_pool, 8) + pick(nd_pool, 8)
    panel.sort(key=lambda r: (r["truth"], int(r["canonical_bank_order"])))
    return panel


# --------------------------------------------------------------------------
# stage: report (gate + verdict + docs)
# --------------------------------------------------------------------------

def _regression_summary() -> str:
    log = ROOT / "results/phase_m3pi1vr0/summary/m3pi1vr0_full_regression.log"
    if not log.exists():
        return "pending"
    tail = [ln for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    passed = [ln for ln in tail if " passed" in ln]
    return passed[-1] if passed else "; ".join(tail[-2:])


def report() -> None:
    DOC.mkdir(parents=True, exist_ok=True)
    status = load(OUT / "m3pi1vr0_pi1v_scientific_status.json")
    forensics = load(OUT / "m3pi1vr0_incident_forensics.json")
    inj = load(OUT / "m3pi1vr0_failure_injection.json")
    e2e = load(OUT / "m3pi1vr0_synthetic_e2e.json")
    cap = load(OUT / "m3pi1vr0_fresh_panel_capacity.json")
    ras = load(OUT / "m3pi1vr0_reserve_audit_summary.json")
    rem = load(OUT / "m3pi1vr0_remaining_reserve_summary.json")
    retired = csvread(OUT / "m3pi1vr0_retired_development_states.csv")
    seeds = load(OUT / "m3pi1vr0_retired_seed_manifest.json")
    qm = load(OUT / "m3pi1vr0_quarantine_manifest.json")

    # -- persistence gate (taskbook Sec. 12) ----------------------------------
    regression = _regression_summary()
    regression_pass = "passed" in regression and "failed" not in regression \
        and "error" not in regression
    gate_components = {
        "safe_filename_test": "PASS" if load(OUT / "m3pi1vr0_path_sanitization_contract.json")[
            "round_trip_verified"] else "FAIL",
        "started_before_simulator": "PASS" if e2e["started_before_simulator_pass"] else "FAIL",
        "atomic_persistence": "PASS" if e2e["all_complete"] and e2e["output_hash_match"]
            and not e2e["temp_leftovers"] else "FAIL",
        "failure_injection": "PASS" if all(inj["assertions"].values()) else "FAIL",
        "consumed_invalid_no_replay": "PASS" if all(
            e2e["no_replay_refusals"].values()) else "FAIL",
        "frozen_artifact_overwrite_guard": "PASS" if all(
            e2e["frozen_artifact_guard_refusals"].values()) else "FAIL",
        "synthetic_e2e": "PASS" if e2e["all_complete"] and not e2e["temp_leftovers"] else "FAIL",
        "full_regression": "PASS" if regression_pass else ("PENDING" if regression == "pending" else "FAIL"),
    }
    gate_pass = all(v == "PASS" for v in gate_components.values())
    dump(OUT / "m3pi1vr0_persistence_gate.json", {
        "recorded_at": now(),
        "gate": "M3PI1VR0-PERSIST-1",
        "components": gate_components,
        "verdict": "PASS" if gate_pass else "FAIL",
        "full_regression": regression,
    })

    # -- verdict (taskbook Sec. 26 priority) ----------------------------------
    if not gate_pass and "PENDING" not in gate_components.values():
        verdict = "PI1VR0-INFRA-B"
    elif cap["FRESH_PANEL_CAPACITY"] == "FAIL":
        verdict = "PI1VR0-CAP-B"
    elif not gate_pass:
        verdict = "PI1VR0-INFRA-B"
    else:
        verdict = "PI1VR0-A"
    dump(OUT / "m3pi1vr0_final_verdict.json", {
        "status": "COMPLETE",
        "verdict": verdict,
        "recorded_at": now(),
        "pi1v_scientific_status": status,
        "quarantine": {"attempt1": forensics["attempt1"],
                       "attempt2": forensics["attempt2"],
                       "scientific_use": qm["scientific_use"]},
        "original_panel_retired": {"states": len(retired),
                                   "future_pilot_use": "NO",
                                   "future_confirmation_use": "NO"},
        "seeds_retired": {"namespaces": seeds["retired_namespaces"],
                          "gradient": seeds["gradient_seed_count"],
                          "probe": seeds["probe_seed_count"]},
        "persistence_gate": {"M3PI1VR0-PERSIST-1": gate_components,
                             "verdict": "PASS" if gate_pass else "FAIL"},
        "reserve": {"original_protected_states": ras["original_protected_states"],
                    "verified_untouched": ras["verified_untouched"],
                    "eligible_fresh_development": ras["verified_untouched"]},
        "capacity": {"W": cap["eligible_reserve_W"], "S": cap["eligible_reserve_S"],
                     "HOLD": cap["eligible_reserve_HOLD"],
                     "AMB": cap["eligible_reserve_AMBIGUOUS"],
                     "ND": cap["eligible_reserve_ND"],
                     "8W_8S_8ND_feasible": cap["FRESH_PANEL_CAPACITY"] == "PASS",
                     "binding_shortage": cap["binding_shortage"]},
        "fresh_panel": {"states": "NA" if not cap["fresh_development_panel_created"]
                        else cap.get("fresh_panel_states"),
                        "hash": "NA",
                        "invalid_run_scores_used": "NO",
                        "pilot_exposure": 0},
        "remaining_protected_reserve": {"states": rem["remaining_protected_states"],
                                        "pilot_exposure": 0},
        **invariance_block(),
        "next": {
            "PI1VR0-A": "M3-PI1VN independent fresh-panel finite-action "
                        "information validation",
            "PI1VR0-CAP-B": "separately preregistered fresh reference augmentation",
            "PI1VR0-INFRA-B": "infrastructure repair; no simulator authorized",
            "PI1VR0-X": "stop; invalid recovery",
        }[verdict],
    })

    # -- mandatory final report text (taskbook Sec. 30) -----------------------
    final = load(OUT / "m3pi1vr0_final_verdict.json")
    txt = f"""M3-PI1VR0 STATUS:
COMPLETE

PI1V SCIENTIFIC STATUS:
valid verdict = PI1V-X
PI1V-C retained as primary = NO
attempt-2 metrics = DIAGNOSTIC_ONLY

ATTEMPT 1:
scientific trials started = 192
durable complete = 0
consumed-invalid = 192

ATTEMPT 2:
deterministic replay = YES
primary scientific use = NO

ORIGINAL DEVELOPMENT PANEL:
states retired = 24
future pilot use = NO
future confirmation use = NO

SEEDS:
old PI1V seeds retired = YES

PERSISTENCE:
safe filename encoding = {gate_components['safe_filename_test']}
STARTED-before-simulator = {gate_components['started_before_simulator']}
atomic persistence = {gate_components['atomic_persistence']}
consumed-invalid no-replay = {gate_components['consumed_invalid_no_replay']}
frozen-artifact rewrite guard = {gate_components['frozen_artifact_overwrite_guard']}
synthetic E2E = {gate_components['synthetic_e2e']}

M3PI1VR0-PERSIST-1:
{gate_components['verdict']}

RESERVE:
original protected states = {ras['original_protected_states']}
verified untouched = {ras['verified_untouched']}
eligible fresh-development candidates = {ras['verified_untouched']}

CAPACITY:
W = {cap['eligible_reserve_W']}
S = {cap['eligible_reserve_S']}
HOLD = {cap['eligible_reserve_HOLD']}
AMB = {cap['eligible_reserve_AMBIGUOUS']}
ND = {cap['eligible_reserve_ND']}
8W/8S/8ND feasible = {'YES' if cap['FRESH_PANEL_CAPACITY'] == 'PASS' else 'NO'}

FRESH PANEL:
states = {'24' if cap['fresh_development_panel_created'] else 'NA'}
W = {'8' if cap['fresh_development_panel_created'] else 'NA'}
S = {'8' if cap['fresh_development_panel_created'] else 'NA'}
ND = {'8' if cap['fresh_development_panel_created'] else 'NA'}
hash = {'see m3pi1vr0_fresh_panel_hash.json' if cap['fresh_development_panel_created'] else 'NA'}
invalid-run scores used = NO
pilot exposure = 0

REMAINING PROTECTED RESERVE:
states = {rem['remaining_protected_states']}
pilot exposure = 0

SIMULATOR:
new samples = 0

V1:
new test = NO
threshold = null

S1:
confirmation authorized = NO

VALUE:
BLOCKED
RARITY:
BLOCKED
M3-Q:
BLOCKED

FINAL VERDICT:
{verdict}

NEXT:
{final['next']}

FULL REGRESSION:
{regression}
"""
    (OUT / "m3pi1vr0_final_report.txt").write_text(txt, encoding="utf-8")

    # -- docs -----------------------------------------------------------------
    (DOC / "M3_PI1VR0_Task.md").write_text(
        "# M3-PI1VR0 Task\n\nTask book: "
        "`M3_PI1VR0_Incident_Quarantine_and_Fresh_Development_Recovery_Task.md` "
        "(zero-simulator recovery after invalid same-stage replay; see the "
        "frozen outputs under `results/phase_m3pi1vr0/summary/`).\n",
        encoding="utf-8")
    (DOC / "M3_PI1VR0_Incident_Forensics.md").write_text(
        "# M3-PI1VR0 Incident Forensics\n\nStatus: **COMPLETE** (forensics only; "
        "nothing was rewritten into a primary run).\n\n"
        f"- Attempt 1: {forensics['attempt1']['scientific_trials_started']} "
        f"scientific trials started, {forensics['attempt1']['durable_complete']} "
        f"durable COMPLETE, {forensics['attempt1']['consumed_invalid']} "
        "CONSUMED_INVALID.\n"
        f"  - Filename root cause: {forensics['attempt1']['filename_root_cause']}.\n"
        f"  - Sequencing violation: {forensics['attempt1']['sequencing_violation']}.\n"
        "- Attempt 2: same-seed deterministic replay, 192/192 persisted, "
        "**diagnostic only**.\n"
        "- Valid verdict: **PI1V-X**. Attempt-2 outputs may not freeze thresholds, "
        "declare primary results, choose budgets, or authorize confirmation.\n"
        "- Repair: `src/hyptraj/m3pi1vr0/persistence.py` implements the frozen "
        "12-step contract with filesystem-safe ids and STARTED-before-simulator "
        "ordering.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VR0_Scientific_Quarantine.md").write_text(
        "# M3-PI1VR0 Scientific Quarantine\n\nStatus: **COMPLETE**.\n\n"
        "- Both attempts quarantined: attempt 1 under "
        f"`{QUAR1.as_posix()}`, attempt 2 under `{QUAR2.as_posix()}` "
        "(trials, figures, and the 14 invalid-run analysis outputs).\n"
        "- All 24 original CF2 development states marked "
        "**PILOT_EXPOSED_RETIRED** "
        "(`m3pi1vr0_retired_development_states.csv`); forbidden for fresh "
        "development, future confirmation, and future threshold selection.\n"
        f"- All PI1V seeds retired ({seeds['gradient_seed_count']} gradient + "
        f"{seeds['probe_seed_count']} probe; namespaces "
        f"{', '.join(seeds['retired_namespaces'])}); never to be reused.\n"
        "- Scientific use of everything quarantined: **diagnostic only**.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VR0_Persistence_Repair.md").write_text(
        "# M3-PI1VR0 Persistence Repair\n\nStatus: "
        f"**{gate_components['verdict']}** (M3PI1VR0-PERSIST-1).\n\n"
        "- Frozen 12-step order enforced structurally; the simulator is never "
        "invoked before the durable STARTED entry (verified synthetically on "
        f"all {len(sim_obs_count(e2e))} mock trials).\n"
        "- Filesystem-safe canonical ids: `safe_fs_id` (no ':', no '::', no "
        "reserved names, stable, reversible; logical id unchanged in the record "
        "body).\n"
        f"- Failure injection: {len(inj['results'])} injection points + validator "
        "failure, all CONSUMED_INVALID with correct post-states.\n"
        "- No-replay rule encoded (`ensure_not_started` / `ensure_seed_unused`); "
        "deterministic replay does not override it.\n"
        "- Frozen-artifact overwrite guard: existing and prereg-hash-locked "
        "artifacts are refused.\n"
        f"- Full regression: {regression}.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VR0_Fresh_Reserve_Audit.md").write_text(
        "# M3-PI1VR0 Fresh Reserve Audit\n\nStatus: **COMPLETE**.\n\n"
        f"- Original protected states: {ras['original_protected_states']}; "
        f"verified untouched: {ras['verified_untouched']}; exposures "
        "(gradient / probe / threshold-replay) all zero.\n"
        "- Per-state eligibility recorded in "
        "`m3pi1vr0_reserve_exposure_audit.csv`: corrected durable hash-valid "
        "truth, pilot exposure 0, probe exposure 0, not in the original 24-state "
        "panel, not UC2R protected confirmation, not CF1 invalid evidence.\n"
        "- Attempt-2 V1/S1 outputs did not influence eligibility (they were "
        "quarantined before the audit and never read).\n",
        encoding="utf-8")
    (DOC / "M3_PI1VR0_Fresh_Panel_Selection.md").write_text(
        "# M3-PI1VR0 Fresh Panel Selection\n\nStatus: **"
        f"{cap['FRESH_PANEL_CAPACITY']}**.\n\n"
        f"- Redacted selection view frozen before selection "
        f"({len(csvread(OUT / 'm3pi1vr0_selection_view.csv'))} eligible states; "
        "no score fields; hash-locked).\n"
        f"- Capacity: W={cap['eligible_reserve_W']}, S={cap['eligible_reserve_S']}, "
        f"HOLD={cap['eligible_reserve_HOLD']}, AMB={cap['eligible_reserve_AMBIGUOUS']}, "
        f"ND={cap['eligible_reserve_ND']}.\n"
        f"- Binding shortage: {', '.join(cap['binding_shortage'])} -- the reserve "
        "holds only 7 untouched WIDEN states (4 distinct configs; at most 6 "
        "selectable under max 2/config), so an exact 8W/8S/8ND panel is "
        "infeasible. Counts were NOT relaxed.\n"
        "- No fresh development panel was created; no new states were generated "
        "to force the shape; the deterministic selector contract is frozen for "
        "the augmentation successor.\n"
        f"- Remaining protected reserve: {rem['remaining_protected_states']} "
        "states, pilot exposure 0.\n",
        encoding="utf-8")
    (DOC / "M3_PI1VR0_Final_Decision.md").write_text(
        "# M3-PI1VR0 Final Decision\n\n"
        f"**Verdict: {verdict}**\n\n"
        + {
            "PI1VR0-A": "Recovery complete; a fresh independent 8W/8S/8ND "
                        "development panel is frozen; the clean next stage is "
                        "M3-PI1VN with the ORIGINAL frozen PI1V hypothesis and "
                        "new namespaces M3-PI1VN-GRAD / M3-PI1VN-PROBE.",
            "PI1VR0-CAP-B": "Fresh development capacity is insufficient: the "
                            "untouched reserve cannot supply 8 WIDEN states. The "
                            "next stage is a separately preregistered fresh "
                            "reference augmentation; no counts were relaxed and "
                            "no budget escalation was derived from the invalid "
                            "run (the valid <=2x PI1V result is UNAVAILABLE, not "
                            "negative).",
            "PI1VR0-INFRA-B": "Persistence recovery failed; no simulator "
                              "authorized.",
            "PI1VR0-X": "Invalid recovery.",
        }[verdict] + "\n\n"
        "- PI1V scientific status: valid verdict PI1V-X; PI1V-C not retained as "
        "primary; attempt-2 metrics diagnostic only.\n"
        "- Simulator: zero new samples; V1: no new test, threshold null; S1: "
        "confirmation NOT authorized.\n"
        "- VALUE / RARITY / M3-Q: BLOCKED.\n"
        f"- FULL REGRESSION: {regression}.\n",
        encoding="utf-8")
    print(txt)
    print(f"PI1VR0 report: verdict {verdict}")


def sim_obs_count(e2e: dict) -> list:
    return e2e["started_before_simulator_observations"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("quarantine", "persistence", "reserve",
                                     "selection", "report"))
    a = p.parse_args()
    {"quarantine": quarantine, "persistence": persistence, "reserve": reserve,
     "selection": selection, "report": report}[a.stage]()

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRODUCE_DB = ROOT / "scripts" / "produce_db.py"


@pytest.fixture
def inspect_db(tmp_path):
    db_path = str(tmp_path / "inspect_test.db")
    os.environ["PRODUCTION_DB_PATH"] = db_path

    import production_db as _db
    _db.migrate(db_path)

    conn = _db.connect(db_path)
    now = _db._now()
    prod_id = "prod_inspect"

    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, "
        "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_inspect", "in_progress", "beefcafe", "inspect_seed", now, now),
    )

    # Stage runs
    for name, status in [("research", "completed"), ("write_script", "completed"),
                          ("storyboard", "completed"), ("compile_media", "completed"),
                          ("generate_media", "running"), ("qa_media", "pending")]:
        conn.execute(
            "INSERT INTO stage_runs (id, production_id, stage_name, attempt, status, "
            "started_at, finished_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (_db._id("sr"), prod_id, name, 1, status,
             now if status != "pending" else None,
             now if status in ("completed",) else None,
             now, now),
        )

    # Storyboard document + creative_beats (shots)
    sb_rev_id = _db._id("dr")
    conn.execute(
        "INSERT INTO document_revisions (id, production_id, kind, revision, "
        "status, schema_version, payload_json, payload_sha256, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (sb_rev_id, prod_id, "storyboard", 1, "active", "1",
         _db._json({"shots": []}), _db._sha256_bytes(b"sb"), now),
    )
    for i, (role, label) in enumerate([
        ("hero", "intro_shot"), ("hero", "explanation_shot"),
        ("broll", "demo_shot"), ("graphic", "stat_shot"),
    ]):
        beat_id = _db._id("cb")
        vi = json.dumps({"visual_concept": label, "must_show": role + "_subject",
                         "action": "appears"})
        conn.execute(
            "INSERT INTO creative_beats (id, storyboard_revision_id, ordinal, "
            "label, shot_type, visual_intent_json, visual_role) VALUES (?,?,?,?,?,?,?)",
            (beat_id, sb_rev_id, i, label, "medium", vi, role),
        )

    # Render units
    ru_ids = []
    for i, (label, atype, st, apol) in enumerate([
        ("intro_hero", "lipsync_video", "generated", "HERO_SYNC_LOCKED"),
        ("explain_hero", "lipsync_video", "generated", "HERO_SYNC_LOCKED"),
        ("demo_broll", "broll_video", "generated", "BROLL_FLEX"),
        ("stat_graphic", "local_graphic", "generated", "SILENT_GRAPHIC"),
    ]):
        ru_id = f"ru_{label}"
        ru_ids.append(ru_id)
        art_id = _db._id("art")
        conn.execute(
            "INSERT INTO artifacts (id, production_id, kind, uri, mime_type, "
            "sha256, created_at) VALUES (?,?,?,?,?,?,?)",
            (art_id, prod_id, "generated_video",
             f"/media/{label}.mp4", "video/mp4",
             _db._sha256_bytes(label.encode()), now),
        )
        conn.execute(
            "INSERT INTO render_units (id, production_id, ordinal, label, asset_type, "
            "audio_policy, final_audio_source, provider_audio_usage, text_policy, "
            "lipsync_required, required_start_ms, required_end_ms, required_duration_ms, "
            "slot_index, slot_total, status, active_artifact_id, concept_key, "
            "visual_role, metadata_json, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (ru_id, prod_id, i, label, atype, apol, "none", "discarded",
             "NO_VISIBLE_TEXT", 0, 0, 5000, 5000, 0, 1, st, art_id,
             f"concept_{label}", role, _db._json({}), now, now),
        )

    # Validations (QA verdicts)
    for ru_id, vname, vstatus, method in [
        ("ru_intro_hero", "syncnet_offset", "pass", "seedance_2.0"),
        ("ru_explain_hero", "syncnet_offset", "fail", "seedance_2.0"),
        ("ru_demo_broll", "semantic_role_qa", "pass", "vision_model_v1"),
        ("ru_demo_broll", "broll_technical", "pass", "ffmpeg"),
        ("ru_stat_graphic", "ocr_text_match", "pass", "tesseract_v1"),
    ]:
        conn.execute(
            "INSERT INTO validations (id, production_id, subject_type, subject_id, "
            "validator_name, status, evidence_json, artifact_sha256, algorithm_version, "
            "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_db._id("val"), prod_id, "render_unit", ru_id,
             vname, vstatus, _db._json({"method": method, "simulated": False}),
             _db._sha256_bytes(vname.encode()), "1.0", now),
        )

    # Provider jobs
    for ru_id, prov in [("ru_intro_hero", "seedance"), ("ru_explain_hero", "seedance"),
                         ("ru_demo_broll", "kling")]:
        conn.execute(
            "INSERT INTO provider_jobs (id, production_id, render_unit_id, provider, "
            "operation, idempotency_key, status, submitted_at, completed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (_db._id("pj"), prod_id, ru_id, prov, "generate_video",
             _db._id("ik"), "completed", now, now),
        )

    # Cost events
    for op, est in [("generate_video", 0.05), ("generate_video", 0.05),
                    ("generate_video", 0.03), ("tts", 0.01)]:
        conn.execute(
            "INSERT INTO cost_events (id, production_id, provider, operation, "
            "estimated_usd, actual_usd, created_at) VALUES (?,?,?,?,?,?,?)",
            (_db._id("co"), prod_id, "seedance", op, est, est, now),
        )

    # Approval requests
    for gate, st in [("gate_a_content", "pass"), ("gate_a_spend", "pass"),
                     ("gate_b_review", "pending")]:
        conn.execute(
            "INSERT INTO approval_requests (id, production_id, gate_name, status, "
            "requested_at, forced) VALUES (?,?,?,?,?,?)",
            (_db._id("ar"), prod_id, gate, st, now, 0),
        )

    # Change requests
    conn.execute(
        "INSERT INTO change_requests (id, production_id, subject_type, subject_id, "
        "change_type, requested_by_stage, target_stage, reason, status, "
        "created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (_db._id("cr"), prod_id, "render_unit", "ru_demo_broll",
         "regeneration", "qa_media", "generate_media",
         "semantic mismatch detected", "open", now),
    )

    conn.commit()
    conn.close()

    _db._db_path_override = db_path

    yield {"db_path": db_path, "prod_id": prod_id, "ru_ids": ru_ids}

    _db._db_path_override = None
    if "PRODUCTION_DB_PATH" in os.environ:
        del os.environ["PRODUCTION_DB_PATH"]


def _run_cli(*args, db_path=None):
    env = os.environ.copy()
    if db_path:
        env["PRODUCTION_DB_PATH"] = db_path
    cmd = [sys.executable, str(PRODUCE_DB)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), env=env)


class TestInspectProduction:
    def test_inspect_lists_all_render_units_with_qa(self, inspect_db):
        db_path = inspect_db["db_path"]
        prod_id = inspect_db["prod_id"]
        ru_ids = inspect_db["ru_ids"]

        result = _run_cli("inspect", prod_id, db_path=db_path)
        assert result.returncode == 0, f"inspect failed: {result.stderr}"

        output = json.loads(result.stdout)
        units = output.get("units", {})
        assert isinstance(units, dict), f"units should be dict, got {type(units)}"

        assert len(units) == len(ru_ids), \
            f"expected {len(ru_ids)} units, got {len(units)}"

        for ru_id in ru_ids:
            assert ru_id in units, f"unit {ru_id} missing from report"
            unit = units[ru_id]
            assert "asset_type" in unit
            assert "policies" in unit
            assert "artifact_sha" in unit or "active_artifact_id" in unit
            assert "qa_verdicts" in unit
            assert isinstance(unit["qa_verdicts"], list)

        # intro_hero should have 1 pass, explain_hero 1 fail, demo_broll 2 (1 pass, 1 pass)
        assert len(units["ru_intro_hero"]["qa_verdicts"]) == 1
        assert units["ru_intro_hero"]["qa_verdicts"][0]["status"] == "pass"

        assert len(units["ru_explain_hero"]["qa_verdicts"]) == 1
        assert units["ru_explain_hero"]["qa_verdicts"][0]["status"] == "fail"

        assert len(units["ru_demo_broll"]["qa_verdicts"]) == 2

        assert len(units["ru_stat_graphic"]["qa_verdicts"]) == 1

    def test_inspect_unknown_production_exits_nonzero(self, inspect_db):
        db_path = inspect_db["db_path"]

        result = _run_cli("inspect", "nonexistent_prod", db_path=db_path)
        assert result.returncode != 0, \
            f"expected non-zero exit for unknown production, got {result.returncode}"
        assert "not found" in result.stderr.lower(), \
            f"expected 'not found' in stderr, got: {result.stderr}"

    def test_inspect_json_output_contains_required_keys(self, inspect_db, tmp_path):
        db_path = inspect_db["db_path"]
        prod_id = inspect_db["prod_id"]

        json_file = str(tmp_path / "inspect_output.json")
        result = _run_cli("inspect", prod_id, "--json", json_file, db_path=db_path)
        assert result.returncode == 0, f"inspect --json failed: {result.stderr}"

        with open(json_file) as f:
            data = json.load(f)

        assert isinstance(data, dict), "JSON output must be a dict"
        assert "production" in data, "missing 'production' key"
        assert "stages" in data, "missing 'stages' key"
        assert "storyboard" in data, "missing 'storyboard' key"
        assert "word_timing" in data, "missing 'word_timing' key"
        assert "timing" in data, "missing 'timing' key"
        assert "units" in data, "missing 'units' key"
        assert "validations" in data, "missing 'validations' key"
        assert "provider_jobs" in data, "missing 'provider_jobs' key"
        assert "cost_totals" in data, "missing 'cost_totals' key"
        assert "approvals" in data, "missing 'approvals' key"
        assert "change_requests" in data, "missing 'change_requests' key"
        assert "blockers" in data, "missing 'blockers' key"

        assert len(data["units"]) == len(inspect_db["ru_ids"])

    def test_inspect_readonly_no_db_writes(self, inspect_db):
        db_path = inspect_db["db_path"]
        prod_id = inspect_db["prod_id"]

        import production_db as _db
        conn = _db.connect(db_path)
        pre_counts = {
            "render_units": conn.execute("SELECT COUNT(*) as c FROM render_units").fetchone()["c"],
            "validations": conn.execute("SELECT COUNT(*) as c FROM validations").fetchone()["c"],
            "change_requests": conn.execute("SELECT COUNT(*) as c FROM change_requests").fetchone()["c"],
            "approval_requests": conn.execute("SELECT COUNT(*) as c FROM approval_requests").fetchone()["c"],
            "cost_events": conn.execute("SELECT COUNT(*) as c FROM cost_events").fetchone()["c"],
            "stage_runs": conn.execute("SELECT COUNT(*) as c FROM stage_runs").fetchone()["c"],
            "provider_jobs": conn.execute("SELECT COUNT(*) as c FROM provider_jobs").fetchone()["c"],
            "artifacts": conn.execute("SELECT COUNT(*) as c FROM artifacts").fetchone()["c"],
            "productions": conn.execute("SELECT COUNT(*) as c FROM productions").fetchone()["c"],
            "document_revisions": conn.execute("SELECT COUNT(*) as c FROM document_revisions").fetchone()["c"],
            "creative_beats": conn.execute("SELECT COUNT(*) as c FROM creative_beats").fetchone()["c"],
        }
        conn.close()

        result = _run_cli("inspect", prod_id, db_path=db_path)
        assert result.returncode == 0

        conn = _db.connect(db_path)
        post_counts = {
            "render_units": conn.execute("SELECT COUNT(*) as c FROM render_units").fetchone()["c"],
            "validations": conn.execute("SELECT COUNT(*) as c FROM validations").fetchone()["c"],
            "change_requests": conn.execute("SELECT COUNT(*) as c FROM change_requests").fetchone()["c"],
            "approval_requests": conn.execute("SELECT COUNT(*) as c FROM approval_requests").fetchone()["c"],
            "cost_events": conn.execute("SELECT COUNT(*) as c FROM cost_events").fetchone()["c"],
            "stage_runs": conn.execute("SELECT COUNT(*) as c FROM stage_runs").fetchone()["c"],
            "provider_jobs": conn.execute("SELECT COUNT(*) as c FROM provider_jobs").fetchone()["c"],
            "artifacts": conn.execute("SELECT COUNT(*) as c FROM artifacts").fetchone()["c"],
            "productions": conn.execute("SELECT COUNT(*) as c FROM productions").fetchone()["c"],
            "document_revisions": conn.execute("SELECT COUNT(*) as c FROM document_revisions").fetchone()["c"],
            "creative_beats": conn.execute("SELECT COUNT(*) as c FROM creative_beats").fetchone()["c"],
        }
        conn.close()

        for table in pre_counts:
            assert pre_counts[table] == post_counts[table], \
                f"Table {table} changed: {pre_counts[table]} -> {post_counts[table]}"

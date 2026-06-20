import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from authoring_service import record_approval_decision, request_approval
from media_service import ensure_render_unit_artifact_state, poll_provider_job, submit_provider_job
from production_repo import commit_timeline_spans, plan_render_units, register_artifact


class _RunResult:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _approve_spend(production_id: str) -> None:
    request_approval(production_id, "gate_a_spend", subject_sha256="test")
    record_approval_decision(production_id, "gate_a_spend", "pass")


def _unit(production_id: str, *, status: str = "ordered", asset_type: str = "generated_video",
          model: str = "seedance_2_0") -> dict:
    spans = commit_timeline_spans(
        production_id,
        [{"label": f"B{abs(hash((production_id, status, asset_type))) % 999:03d}",
          "start_ms": 0, "end_ms": 5000}],
    )
    units = plan_render_units(
        production_id,
        [{
            "span_id": spans[0]["id"],
            "asset_type": asset_type,
            "model": model,
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "NO_VISIBLE_TEXT",
            "visual_function": "illustrate",
            "narrative_claim": "test claim",
            "information_to_show": "test visual",
            "viewer_takeaway": "test takeaway",
            "required_action": "slow pan",
            "distinctness_requirement": "specific test visual",
            "semantic_acceptance_criteria": "matches the test claim",
            "concept_key": "test_concept",
            "concept_hash": "test_concept",
        }],
    )
    with _db.transaction(None) as conn:
        conn.execute("UPDATE render_units SET status=? WHERE id=?", (status, units[0]["id"]))
    return units[0]


class _CompletingAdapter:
    def poll(self, external_job_id):
        return {"status": "completed", "raw_response": "completed", "external_job_id": external_job_id}

    def download(self, external_job_id, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake mp4 payload")
        return output_path


class _SubmittingAdapter(_CompletingAdapter):
    def __init__(self):
        self.submits = 0

    def submit(self, payload, idempotency_key):
        self.submits += 1
        return {"external_job_id": "00000000-0000-0000-0000-000000000001", "status": "submitted"}


def test_completed_higgsfield_table_output_updates_job_status(monkeypatch):
    prod = _db.ensure_production("hf_table_status")
    _approve_spend(prod["id"])
    ru = _unit(prod["id"])
    job = submit_provider_job(prod["id"], ru["id"], "higgsfield", "generate_video", {"model": "seedance_2_0"})

    table = "ID | MODEL | STATUS\nabc | seedance_2_0 | completed"
    updated = poll_provider_job(job["id"], external_job_id="abc", new_status=table, response_payload={"raw": table})

    assert updated["status"] == "completed"
    assert table not in updated["status"]


def test_higgsfield_poll_parses_completed_table_output(monkeypatch):
    from paid_adapters import HiggsfieldSeedanceAdapter
    import paid_adapters

    table = "ID | MODEL | STATUS | URL\nabc | seedance_2_0 | completed | https://cdn.example/x.mp4"
    monkeypatch.setattr(paid_adapters.subprocess, "run", lambda *a, **k: _RunResult(stdout=table))

    result = HiggsfieldSeedanceAdapter({}).poll("abc")

    assert result["status"] == "completed"
    assert result["raw_response"] == table


def test_completed_provider_job_downloads_registers_artifact_and_marks_generated(monkeypatch):
    import produce_db
    import provider_adapter

    prod = _db.ensure_production("completed_download")
    ru = _unit(prod["id"], status="generating")
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation, external_job_id,
                idempotency_key, status, request_json, submitted_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            ("pjob_test", prod["id"], ru["id"], "higgsfield", "generate_video",
             "ext_done", "idem_done", "running", '{"duration_ms":5000}', _db._now()),
        )

    monkeypatch.setattr(provider_adapter, "get_provider_adapter", lambda *a, **k: _CompletingAdapter())
    monkeypatch.setattr(provider_adapter, "validate_downloaded_artifact", lambda path: {
        "duration_ms": 5000, "width": 1920, "height": 1080, "has_audio": 0,
        "sha256": "sha", "format_name": "mp4",
    })

    result = produce_db.invoke_generate_media({"production_id": prod["id"]}, Path("/tmp"))

    conn = _db.connect(None)
    row = conn.execute(
        """SELECT ru.status, ru.active_artifact_id, pj.status AS job_status
           FROM render_units ru JOIN provider_jobs pj ON pj.render_unit_id=ru.id
           WHERE ru.id=?""",
        (ru["id"],),
    ).fetchone()
    conn.close()
    assert result["jobs_completed"] == 1
    assert row["status"] == "generated"
    assert row["active_artifact_id"]
    assert row["job_status"] == "completed"


def test_existing_artifact_is_not_regenerated(monkeypatch, tmp_path):
    import produce_db
    import provider_adapter

    prod = _db.ensure_production("existing_artifact")
    ru = _unit(prod["id"], status="ordered")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"already here")
    art = register_artifact(prod["id"], clip, "generated_media")
    with _db.transaction(None) as conn:
        conn.execute(
            "UPDATE render_units SET active_artifact_id=?, status='ordered' WHERE id=?",
            (art["id"], ru["id"]),
        )
    adapter = _SubmittingAdapter()
    monkeypatch.setattr(provider_adapter, "get_provider_adapter", lambda *a, **k: adapter)

    result = produce_db.invoke_generate_media({"production_id": prod["id"]}, tmp_path)

    assert result["new_jobs_submitted"] == 0
    assert adapter.submits == 0
    conn = _db.connect(None)
    count = conn.execute("SELECT COUNT(*) FROM provider_jobs WHERE render_unit_id=?", (ru["id"],)).fetchone()[0]
    status = conn.execute("SELECT status FROM render_units WHERE id=?", (ru["id"],)).fetchone()["status"]
    conn.close()
    assert count == 0
    assert status == "generated"


def test_diagnostic_audio_artifact_is_not_recovered_as_generated(tmp_path):
    prod = _db.ensure_production("diagnostic_not_generated")
    _approve_spend(prod["id"])
    ru = _unit(prod["id"], status="ordered")
    job = submit_provider_job(
        prod["id"], ru["id"], "higgsfield", "generate_video",
        {"model": "seedance_2_0", "duration_sec": 14},
    )
    wav = tmp_path / "clip.diagnostic_audio.wav"
    wav.write_bytes(b"diagnostic audio placeholder")

    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO artifacts
               (id, production_id, kind, uri, storage_backend, mime_type,
                sha256, size_bytes, provider_job_id, metadata_json, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "art_diag_only", prod["id"], "provider_diagnostic_audio",
                str(wav), "local", "audio/wav", "sha", wav.stat().st_size,
                job["id"], '{"usage_policy":"diagnostic_only"}', _db._now(),
            ),
        )
        conn.execute(
            "UPDATE render_units SET status='ordered', active_artifact_id=NULL WHERE id=?",
            (ru["id"],),
        )

    assert ensure_render_unit_artifact_state(ru["id"], db_path=None) is None

    conn = _db.connect(None)
    state = conn.execute(
        "SELECT status, active_artifact_id FROM render_units WHERE id=?",
        (ru["id"],),
    ).fetchone()
    conn.close()
    assert state["status"] == "ordered"
    assert state["active_artifact_id"] is None


def test_capacity_full_prevents_submission_without_failed_job(monkeypatch):
    import produce_db

    prod = _db.ensure_production("capacity_full")
    _unit(prod["id"], status="ordered", model="seedance_2_0")
    with _db.transaction(None) as conn:
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, provider, operation, idempotency_key, status, request_json, submitted_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("pjob_active", prod["id"], "higgsfield", "generate_video", "active",
             "running", '{"model":"seedance_2_0"}', _db._now()),
        )
    monkeypatch.setenv("HIGGSFIELD_CAPACITY_SEEDANCE_2_0", "1")

    with pytest.raises(RuntimeError, match="WAITING_ON_PROVIDER_CAPACITY"):
        produce_db.invoke_generate_media({"production_id": prod["id"]}, Path("/tmp"))

    conn = _db.connect(None)
    failed = conn.execute("SELECT COUNT(*) FROM provider_jobs WHERE status='failed'").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM provider_jobs").fetchone()[0]
    conn.close()
    assert failed == 0
    assert total == 1


def test_generate_media_fails_closed_when_units_remain_ordered_or_failed():
    import produce_db

    prod = _db.ensure_production("gen_fails_closed")
    _unit(prod["id"], status="failed")

    with pytest.raises(RuntimeError, match="not generated/valid"):
        produce_db.invoke_generate_media({"production_id": prod["id"]}, Path("/tmp"))


def test_qa_media_fails_closed_if_required_unit_not_valid():
    import produce_db

    prod = _db.ensure_production("qa_fails_closed")
    _unit(prod["id"], status="ordered")

    with pytest.raises(RuntimeError, match="not ready for QA"):
        produce_db.invoke_qa_media({"production_id": prod["id"]}, Path("/tmp"))


def test_local_graphic_does_not_create_provider_job():
    import produce_db

    prod = _db.ensure_production("local_graphic_block")
    ru = _unit(prod["id"], status="ordered", asset_type="local_graphic", model=None)

    with pytest.raises(RuntimeError, match="LOCAL_GRAPHIC_RENDER_NOT_IMPLEMENTED"):
        produce_db.invoke_generate_media({"production_id": prod["id"]}, Path("/tmp"))

    conn = _db.connect(None)
    count = conn.execute("SELECT COUNT(*) FROM provider_jobs WHERE render_unit_id=?", (ru["id"],)).fetchone()[0]
    conn.close()
    assert count == 0

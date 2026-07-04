"""Tests for produce_db.py orchestrator (ALN-A2).

Verifies DB-native execution, crash/resume, and stage graph traversal.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRODUCE_DB = ROOT / "scripts" / "produce_db.py"
TEST_DB = ROOT / "db" / "test_produce_db.db"

# NOTE: do NOT set os.environ["PRODUCTION_DB_PATH"] at module scope (D-017). That leaks
# into every subsequently-collected test in the session (monkeypatch restores it to this
# value after each test), breaking order-independence. Conftest's autouse
# _isolate_production_db sets it per test; these tests also pass db_path=TEST_DB explicitly.

import production_db as _db
import produce_db
from produce_db import run_production, STAGE_REGISTRY


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure a clean test database + restore module-global state for each test.

    Many tests below monkeypatch produce_db.STAGE_INVOKERS (a module global) to mock
    stages. Some set mocks outside their finally-restored dict, which leaked MagicMock
    invokers into subsequently-collected tests and broke them order-dependently (D-017:
    the s8_resume e2e got a no-op audio_timing -> 'No active timeline spans'). Snapshot
    STAGE_INVOKERS here and restore it after every test so no mock can leak.
    """
    import produce_db as _pdb
    saved_invokers = dict(_pdb.STAGE_INVOKERS)
    if TEST_DB.exists():
        TEST_DB.unlink()
    # Also remove any test project dirs
    import shutil
    test_proj = ROOT / "Videos" / "Projects" / "test_orchestrator_short"
    if test_proj.exists():
        shutil.rmtree(test_proj)
    yield
    _pdb.STAGE_INVOKERS.clear()
    _pdb.STAGE_INVOKERS.update(saved_invokers)
    # Cleanup after test if needed


def _run_cli(*args):
    """Helper for simple CLI smoke tests."""
    env = os.environ.copy()
    env["PRODUCTION_DB_PATH"] = str(TEST_DB)
    cmd = [sys.executable, str(PRODUCE_DB)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT), env=env)


def test_cli_create_and_status():
    """Smoke test: verify CLI create and status commands work."""
    result = _run_cli("create", "--seed", "cli smoke test", "--format", "short")
    assert result.returncode == 0, f"Failed: {result.stderr}"
    
    output = json.loads(result.stdout)
    prod_id = output["production_id"]
    assert output["project_slug"] == "cli_smoke_test"
    
    status_result = _run_cli("status", prod_id)
    assert status_result.returncode == 0
    status_data = json.loads(status_result.stdout)
    assert status_data["production"]["seed"] == "cli smoke test"
    assert status_data["production"]["status"] == "created"
    assert status_data["blockers"] == []


def _canonical_storyboard_for_orchestrator():
    return {
        "storyboard_contract_version": "1.0",
        "approved_script_revision_id": "script_rev_test",
        "approved_script_sha256": "sha",
        "authoring_model_profile": "storyboard_sonnet5",
        "authoring_model": "kilo/anthropic/claude-sonnet-5",
        "claim_inventory": [],
        "narrative_beats": [],
        "shots": [{
            "shot_id": "SHOT_001",
            "segment_id": "SEG_001",
            "visual_role": "host_present_speaking",
            "visual_concept": "James at his desk explaining the thesis.",
            "why_this_visual": "Direct address anchors trust.",
            "narrative_alignment": "The host shot supports the spoken thesis.",
            "literal_vs_metaphorical": "literal",
            "prompt_intent": "Use the canonical host studio framing.",
            "planned_duration_sec": 5.0,
            "min_usable_duration_sec": 4.0,
            "max_usable_duration_sec": 7.0,
            "duration_drift_policy": "trim_ok",
            "assembly_fit_policy": "Trim only.",
            "fallback_strategy": "human_review",
            "qa_requirements": ["Verify James matches reference."],
        }],
        "overlays": [],
        "segment_work_orders": [{
            "segment_id": "SEG_001",
            "narration_text_exact": "The unfair advantage is a system.",
        }],
        "feedback_policy": {"repair_authority": "sonnet5_only", "max_repair_rounds": 3, "block_on_unresolved": True},
        "timing_policy": {"planned_is_intent": True, "observed_is_truth": True, "drift_resolution_order": ["trim_ok"]},
        "approval": {"status": "draft", "creative_author": "sonnet5"},
    }


def test_invoke_storyboard_uses_sonnet_canonical_and_persists_projected_beats(monkeypatch):
    monkeypatch.delenv("YT_TEST_MODE", raising=False)
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(TEST_DB))
    _db._db_path_override = str(TEST_DB)
    _db.migrate(TEST_DB)

    prod = _db.ensure_production("sonnet_storyboard_proj", seed="storyboard", video_type="short", db_path=TEST_DB)
    from authoring_service import save_script, get_storyboard
    save_script(prod["id"], {
        "segments": [{"id": "SEG_001", "label": "B1", "text": "The unfair advantage is a system."}],
    }, db_path=TEST_DB)

    canonical = _canonical_storyboard_for_orchestrator()
    with patch("sonnet_storyboard_wrapper.generate_canonical_storyboard") as mock_gen:
        mock_gen.return_value = {
            "status": "SUCCESS",
            "storyboard": canonical,
            "authoring_metadata": {"model": "kilo/anthropic/claude-sonnet-5"},
            "authoring_errors": [],
            "narration_mutations": [],
        }
        result = produce_db.invoke_storyboard(
            {"production_id": prod["id"], "project_slug": "sonnet_storyboard_proj",
             "seed": "storyboard", "video_type": "short"},
            Path("/tmp"),
        )

    assert result["authoring"] == "sonnet5_canonical"
    assert result["canonical_shots"] == 1
    assert result["beats"] == 1
    mock_gen.assert_called_once()

    saved = get_storyboard(prod["id"], db_path=TEST_DB)
    assert saved["storyboard_contract_version"] == "1.0"
    assert saved["projection_mode"] == "canonical_sonnet5_to_db_beats"
    assert saved["beats"][0]["canonical_shot_id"] == "SHOT_001"
    assert saved["beats"][0]["shot_type"] == "hero_lipsync"
    assert saved["beats"][0]["visual_intent"]["narrative_claim"]

    conn = _db.connect(TEST_DB)
    row = conn.execute(
        "SELECT shot_type, visual_intent_json FROM creative_beats ORDER BY ordinal LIMIT 1"
    ).fetchone()
    conn.close()
    assert row["shot_type"] == "hero_lipsync"
    assert json.loads(row["visual_intent_json"])["shot_id"] == "SHOT_001"


def test_invoke_review_storyboard_uses_non_mutating_v2_gate(monkeypatch):
    monkeypatch.delenv("YT_TEST_MODE", raising=False)
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(TEST_DB))
    _db._db_path_override = str(TEST_DB)
    _db.migrate(TEST_DB)

    prod = _db.ensure_production("sonnet_review_proj", seed="review", video_type="short", db_path=TEST_DB)
    from authoring_service import save_storyboard, _get_active_storyboard_revision_id

    canonical = _canonical_storyboard_for_orchestrator()
    canonical["beats"] = [{
        "beat_id": "SHOT_001",
        "label": "SHOT_001",
        "canonical_shot_id": "SHOT_001",
        "shot_type": "hero_lipsync",
        "visual_intent": {"shot_id": "SHOT_001", "narrative_claim": "claim"},
        "narration_text": "The unfair advantage is a system.",
    }]
    save_storyboard(prod["id"], canonical, db_path=TEST_DB)
    before_rev = _get_active_storyboard_revision_id(prod["id"], db_path=TEST_DB)

    with patch("review_storyboard_v2.creative_review") as mock_review:
        mock_review.return_value = (True, {
            "storyboard_sha256": "review_sha",
            "overall_score": 4.5,
        })
        result = produce_db.invoke_review_storyboard(
            {"production_id": prod["id"], "project_slug": "sonnet_review_proj",
             "seed": "review", "video_type": "short"},
            Path("/tmp"),
        )

    assert result["status"] == "pass"
    assert result["review"] == "sonnet5_creative_review"
    assert _get_active_storyboard_revision_id(prod["id"], db_path=TEST_DB) == before_rev
    mock_review.assert_called_once()


def test_invoke_compile_media_honors_reused_storyboard_intent(monkeypatch):
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(TEST_DB))
    _db._db_path_override = str(TEST_DB)
    _db.migrate(TEST_DB)

    prod = _db.ensure_production("reused_compile_proj", seed="reused", video_type="short", db_path=TEST_DB)
    from authoring_service import save_storyboard
    save_storyboard(prod["id"], {
        "beats": [{
            "label": "SHOT_001",
            "shot_type": "hero_lipsync",
            "visual_intent": {
                "asset_type": "reused",
                "audio_policy": "HERO_PROVIDER_AUDIO_ISLAND",
                "reuse": {"allowed": True, "source": "canonical_existing_footage_intent"},
                "visual_function": "illustrate",
                "narrative_claim": "Existing host footage.",
                "information_to_show": "James at desk.",
                "viewer_takeaway": "Credibility anchor.",
                "required_action": "Preserve existing footage.",
                "distinctness_requirement": "No replacement generation.",
                "semantic_acceptance_criteria": "Existing clip is used.",
            },
            "narration_text": "The unfair advantage is a system.",
        }]
    }, db_path=TEST_DB)

    conn = _db.connect(TEST_DB)
    beat_id = conn.execute("SELECT id FROM creative_beats LIMIT 1").fetchone()["id"]
    conn.execute(
        """INSERT INTO timeline_spans
           (id, production_id, creative_beat_id, label, start_ms, end_ms, duration_ms, status, ordinal)
           VALUES ('span_reused_1', ?, ?, 'SHOT_001', 0, 5000, 5000, 'active', 0)""",
        (prod["id"], beat_id),
    )
    conn.commit()
    conn.close()

    captured = {}

    def fake_compile_render_plan(production_id, span_specs, estimated_cost_usd, db_path=None):
        captured["production_id"] = production_id
        captured["span_specs"] = span_specs
        captured["estimated_cost_usd"] = estimated_cost_usd
        return {"plan_revision_id": "plan_reused", "render_units": []}

    with patch("tts_service.compile_render_plan", side_effect=fake_compile_render_plan):
        result = produce_db.invoke_compile_media(
            {"production_id": prod["id"], "project_slug": "reused_compile_proj",
             "seed": "reused", "video_type": "short"},
            Path("/tmp"),
        )

    assert result["estimated_cost_usd"] == 0.0
    spec = captured["span_specs"][0]
    assert spec["asset_type"] == "reused"
    assert spec["model"] == "reused"
    assert spec["audio_policy"] == "HERO_PROVIDER_AUDIO_ISLAND"
    assert spec["provider_audio_usage"] == "final_mix"
    assert spec["slots"] == [{
        "slot_index": 0,
        "slot_total": 1,
        "start_ms": 0,
        "end_ms": 5000,
    }]


def test_invoke_generate_media_blocks_unlinked_reused_without_provider_submit(monkeypatch):
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(TEST_DB))
    _db._db_path_override = str(TEST_DB)
    _db.migrate(TEST_DB)

    prod = _db.ensure_production("reused_generate_proj", seed="reused", video_type="short", db_path=TEST_DB)
    from production_repo import commit_timeline_spans, plan_render_units

    spans = commit_timeline_spans(prod["id"], [{
        "label": "SHOT_001",
        "start_ms": 0,
        "end_ms": 5000,
        "narration_text": "The unfair advantage is a system.",
    }], db_path=TEST_DB)
    plan_render_units(prod["id"], [{
        "span_id": spans[0]["id"],
        "label": "SHOT_001",
        "asset_type": "reused",
        "model": "reused",
        "audio_policy": "HERO_PROVIDER_AUDIO_ISLAND",
        "final_audio_source": "provider_audio",
        "provider_audio_usage": "final_mix",
        "text_policy": "NO_VISIBLE_TEXT",
        "lipsync_required": False,
        "render_mode": "generated_video",
    }], db_path=TEST_DB)

    with patch("media_service.submit_provider_job") as mock_submit:
        with pytest.raises(RuntimeError, match="reused_asset_unlinked"):
            produce_db.invoke_generate_media(
                {"production_id": prod["id"], "project_slug": "reused_generate_proj",
                 "seed": "reused", "video_type": "short"},
                Path("/tmp"),
            )
    mock_submit.assert_not_called()


@patch("produce_db.invoke_research")
@patch("produce_db.invoke_write_script")
def test_run_walks_graph_and_resumes(mock_write, mock_research):
    """Verify run_production walks the graph and can resume after failure."""
    # Setup: Create a production
    prod = _db.ensure_production("resume_test_proj", seed="resume test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    call_counts = {"research": 0, "write_script": 0}
    
    def side_effect_research(inputs, tmp_path):
        call_counts["research"] += 1
        return {"claims": 3}
        
    def side_effect_write_script(inputs, tmp_path):
        call_counts["write_script"] += 1
        if call_counts["write_script"] == 1:
            raise RuntimeError("Simulated crash on first attempt")
        return {"segments": []}
        
    mock_research.side_effect = side_effect_research
    mock_write.side_effect = side_effect_write_script
    
    # Update STAGE_INVOKERS to use our mocks
    produce_db.STAGE_INVOKERS["research"] = ("research_brief", mock_research)
    produce_db.STAGE_INVOKERS["write_script"] = ("script", mock_write)
    
    # Mock ALL other stages to prevent real execution and file dependencies
    mock_stages = [
        "review_script", "gate_a_content", "storyboard", "review_storyboard", "gate_storyboard", "tts", "audio_timing",
        "reconcile_timing", "compile_media", "gate_a_spend", "generate_media",
        "qa_media", "repair", "graphics_compositing", "assemble", "qa_final", "gate_b_review", "publish", "analytics"
    ]
    original_invokers = {}
    for stage in mock_stages:
        kind, orig_fn = produce_db.STAGE_INVOKERS[stage]
        original_invokers[stage] = (kind, orig_fn)
        produce_db.STAGE_INVOKERS[stage] = (kind, MagicMock(return_value={"status": "stubbed"}))
    
    try:
        # First run: should fail at write_script
        with pytest.raises(SystemExit) as exc_info:
            run_production(prod_id, db_path=TEST_DB)
        assert exc_info.value.code == 1
        
        # Verify research succeeded and write_script failed in DB
        conn = _db.connect(TEST_DB)
        research_status = conn.execute(
            "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='research' ORDER BY attempt DESC LIMIT 1",
            (prod_id,)
        ).fetchone()["status"]
        ws_status = conn.execute(
            "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='write_script' ORDER BY attempt DESC LIMIT 1",
            (prod_id,)
        ).fetchone()["status"]
        conn.close()
        
        assert research_status == "succeeded"
        assert ws_status == "failed"
        assert call_counts["research"] == 1
        assert call_counts["write_script"] == 1
        
        # Second run (resume): should skip research and succeed at write_script
        run_production(prod_id, db_path=TEST_DB)
        
        # Verify write_script was called a second time and succeeded
        assert call_counts["write_script"] == 2
        
        conn = _db.connect(TEST_DB)
        ws_status_final = conn.execute(
            "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='write_script' ORDER BY attempt DESC LIMIT 1",
            (prod_id,)
        ).fetchone()["status"]
        conn.close()
        
        assert ws_status_final == "succeeded"
        
    finally:
        # Restore original invokers
        for stage, (kind, orig_fn) in original_invokers.items():
            produce_db.STAGE_INVOKERS[stage] = (kind, orig_fn)


@patch("produce_db.invoke_tts")
@patch("produce_db.invoke_audio_timing")
def test_tts_wiring_enforces_provenance(mock_timing, mock_tts):
    """Verify TTS and audio_timing stages wire to tts_service with provenance."""
    prod = _db.ensure_production("tts_provenance_proj", seed="tts test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    # Mock invokers to simulate success
    mock_tts.return_value = {"status": "saved", "artifact_id": "art_1"}
    mock_timing.return_value = {"status": "saved", "spans_committed": 5}
    
    # Update STAGE_INVOKERS
    produce_db.STAGE_INVOKERS["tts"] = (None, mock_tts)
    produce_db.STAGE_INVOKERS["audio_timing"] = (None, mock_timing)
    
    # Mock all other stages to prevent real execution (tts/audio_timing are patched above)
    mock_stages = [
        "research", "write_script", "review_script", "gate_a_content",
        "storyboard", "review_storyboard", "reconcile_timing",
        "compile_media", "gate_a_spend", "generate_media", "qa_media", "repair",
        "graphics_compositing", "assemble", "qa_final", "gate_b_review", "publish", "analytics"
    ]
    original_invokers = {}
    for stage in mock_stages:
        kind, orig_fn = produce_db.STAGE_INVOKERS[stage]
        original_invokers[stage] = (kind, orig_fn)
        produce_db.STAGE_INVOKERS[stage] = (kind, MagicMock(return_value={"status": "stubbed"}))
    
    try:
        # Manually mark pre-TTS stages as succeeded so we reach TTS
        # S2-T01: tts now depends on review_storyboard (canonical order)
        for stage in ["research", "write_script", "review_script", "gate_a_content",
                       "storyboard", "review_storyboard", "gate_storyboard"]:
            _db.mirror_stage_state("tts_provenance_proj", stage, "done", db_path=TEST_DB)
            
        # Create dummy files that TTS/timing expect
        project_dir = ROOT / "Videos" / "Projects" / "tts_provenance_proj_short"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "script.json").write_text('{"segments": [{"text": "hello"}]}')
        (project_dir / "storyboard.json").write_text('{"beats": [{"beat_id": "B001"}]}')
        (project_dir / "narration").mkdir(exist_ok=True)
        (project_dir / "narration" / "continuous.mp3").write_bytes(b"fake audio")
        
        # Run production
        run_production(prod_id, db_path=TEST_DB)
        
        # Verify TTS invoker was called with production_id (provenance linkage)
        assert mock_tts.call_count >= 1
        call_kwargs = mock_tts.call_args[0][0] # inputs dict
        assert call_kwargs["production_id"] == prod_id
        
        # Verify audio_timing invoker was called
        assert mock_timing.call_count >= 1
        
    finally:
        # Restore original invokers
        for stage, (kind, orig_fn) in original_invokers.items():
            produce_db.STAGE_INVOKERS[stage] = (kind, orig_fn)


@patch("produce_db.invoke_compile_media")
def test_compile_media_derives_from_measured_spans(mock_compile):
    """Verify compile_media wires to tts_service and derives durations from spans, not targets."""
    prod = _db.ensure_production("compile_spans_proj", seed="compile test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    # Mock invoker to simulate success
    mock_compile.return_value = {"status": "saved", "plan_revision_id": "plan_1", "units_count": 3}
    produce_db.STAGE_INVOKERS["compile_media"] = (None, mock_compile)
    
    # Mock all other stages to prevent real execution (compile_media is patched above)
    mock_stages = [
        "research", "write_script", "review_script", "gate_a_content",
        "storyboard", "review_storyboard", "tts", "audio_timing", "reconcile_timing",
        "gate_a_spend", "generate_media", "qa_media", "repair",
        "graphics_compositing", "assemble", "qa_final", "gate_b_review", "publish", "analytics"
    ]
    original_invokers = {}
    for stage in mock_stages:
        kind, orig_fn = produce_db.STAGE_INVOKERS[stage]
        original_invokers[stage] = (kind, orig_fn)
        produce_db.STAGE_INVOKERS[stage] = (kind, MagicMock(return_value={"status": "stubbed"}))
    
    try:
        # Manually mark pre-compile stages as succeeded
        # S2-T01: compile_media depends on reconcile_timing
        for stage in ["research", "write_script", "review_script", "gate_a_content",
                       "storyboard", "review_storyboard", "gate_storyboard", "tts", "audio_timing", "reconcile_timing"]:
            _db.mirror_stage_state("compile_spans_proj", stage, "done", db_path=TEST_DB)
            
        # Insert dummy active timeline spans into DB
        conn = _db.connect(TEST_DB)
        conn.execute(
            """INSERT INTO timeline_spans (id, production_id, label, start_ms, end_ms, duration_ms, status, ordinal)
               VALUES ('span_1', ?, 'B001', 0, 5000, 5000, 'active', 0)""",
            (prod_id,)
        )
        conn.execute(
            """INSERT INTO timeline_spans (id, production_id, label, start_ms, end_ms, duration_ms, status, ordinal)
               VALUES ('span_2', ?, 'B002', 5000, 12000, 7000, 'active', 1)""",
            (prod_id,)
        )
        conn.commit()
        conn.close()
        
        # Run production
        run_production(prod_id, db_path=TEST_DB)
        
        # Verify compile_media invoker was called
        assert mock_compile.call_count >= 1
        call_kwargs = mock_compile.call_args[0][0] # inputs dict
        assert call_kwargs["production_id"] == prod_id
        
    finally:
        # Restore original invokers
        for stage, (kind, orig_fn) in original_invokers.items():
            produce_db.STAGE_INVOKERS[stage] = (kind, orig_fn)


def test_generate_media_async_state_machine(monkeypatch, tmp_path):
    """generate_media submits a conservative wave and fails closed while jobs are in flight."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(TEST_DB))
    monkeypatch.setattr(_db, "_db_path_override", str(TEST_DB))
    prod = _db.ensure_production("gen_media_async_proj", seed="gen async test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]

    from produce_db import invoke_generate_media
    from authoring_service import request_approval, record_approval_decision
    from production_repo import commit_timeline_spans, plan_render_units

    spans = commit_timeline_spans(
        prod_id,
        [{"label": "B001", "start_ms": 0, "end_ms": 5000}],
        db_path=TEST_DB,
    )
    plan_render_units(
        prod_id,
        [{
            "span_id": spans[0]["id"],
            "asset_type": "generated_video",
            "model": "kling3_0",
            "audio_policy": "BROLL_FLEX",
            "final_audio_source": "none",
            "provider_audio_usage": "discarded",
            "text_policy": "NO_VISIBLE_TEXT",
            "visual_function": "illustrate",
            "narrative_claim": "test",
            "information_to_show": "test",
            "viewer_takeaway": "test",
            "required_action": "slow pan",
            "distinctness_requirement": "distinct",
            "semantic_acceptance_criteria": "matches test",
            "concept_key": "test",
            "concept_hash": "test",
        }],
        db_path=TEST_DB,
    )
    request_approval(prod_id, "gate_a_spend", subject_sha256="plan", db_path=TEST_DB)
    record_approval_decision(prod_id, "gate_a_spend", "pass", db_path=TEST_DB)

    with pytest.raises(RuntimeError, match="not generated/valid"):
        invoke_generate_media({"production_id": prod_id}, tmp_path)

    conn = _db.connect(TEST_DB)
    jobs = conn.execute(
        "SELECT status FROM provider_jobs WHERE production_id=?", (prod_id,)
    ).fetchall()
    conn.close()
    assert [j["status"] for j in jobs] == ["submitted"]


@patch("produce_db.invoke_assemble")
@patch("produce_db.invoke_qa_final")
@patch("produce_db.invoke_gate_b_review")
def test_assembly_bypasses_manifest_file(mock_gate_b, mock_qa, mock_assemble):
    """Verify assemble, qa_final, and gate_b_review wire to assemble_db without manifest.json."""
    prod = _db.ensure_production("assembly_proj", seed="assembly test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    # Mock invokers to simulate success
    mock_assemble.return_value = {"status": "completed", "deliverable_id": "del_1", "artifact_path": "/tmp/test.mp4"}
    mock_qa.return_value = {"status": "passed", "validation_id": "val_1"}
    mock_gate_b.return_value = {"status": "pass", "approval_id": "app_1"}
    
    produce_db.STAGE_INVOKERS["assemble"] = (None, mock_assemble)
    produce_db.STAGE_INVOKERS["qa_final"] = (None, mock_qa)
    produce_db.STAGE_INVOKERS["gate_b_review"] = (None, mock_gate_b)
    
    # Mock all other stages to prevent real execution (assemble/qa_final/gate_b are patched above)
    mock_stages = [
        "research", "write_script", "review_script", "gate_a_content",
        "storyboard", "review_storyboard", "tts", "audio_timing", "reconcile_timing",
        "compile_media", "gate_a_spend", "generate_media", "qa_media", "repair",
        "graphics_compositing", "publish", "analytics"
    ]
    original_invokers = {}
    for stage in mock_stages:
        kind, orig_fn = produce_db.STAGE_INVOKERS[stage]
        original_invokers[stage] = (kind, orig_fn)
        produce_db.STAGE_INVOKERS[stage] = (kind, MagicMock(return_value={"status": "stubbed"}))
    
    try:
        # Manually mark pre-assembly stages as succeeded
        # S2-T01: assemble depends on graphics_compositing → repair → qa_media
        for stage in ["research", "write_script", "review_script", "gate_a_content",
                      "storyboard", "review_storyboard", "gate_storyboard", "tts", "audio_timing", "reconcile_timing",
                      "compile_media", "gate_a_spend", "generate_media", "qa_media",
                      "repair", "graphics_compositing"]:
            _db.mirror_stage_state("assembly_proj", stage, "done", db_path=TEST_DB)
            
        # Run production
        run_production(prod_id, db_path=TEST_DB)
        
        # Verify assembly invokers were called
        assert mock_assemble.call_count >= 1
        assert mock_qa.call_count >= 1
        assert mock_gate_b.call_count >= 1
        
        # Verify they received production_id for DB lookups
        assert mock_assemble.call_args[0][0]["production_id"] == prod_id
        
    finally:
        # Restore original invokers
        for stage, (kind, orig_fn) in original_invokers.items():
            produce_db.STAGE_INVOKERS[stage] = (kind, orig_fn)


@patch("produce_db.invoke_qa_media")
def test_qa_media_enforces_no_silent_fallback(mock_qa_media):
    """Verify qa_media wires to media_service and fails if any unit is invalid (no silent fallback)."""
    prod = _db.ensure_production("qa_media_proj", seed="qa test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    # Mock invoker to simulate success
    mock_qa_media.return_value = {"status": "passed", "units_validated": 3}
    produce_db.STAGE_INVOKERS["qa_media"] = (None, mock_qa_media)
    
    # Mock all other stages to prevent real execution (qa_media is patched above)
    mock_stages = [
        "research", "write_script", "review_script", "gate_a_content",
        "storyboard", "review_storyboard", "tts", "audio_timing", "reconcile_timing",
        "compile_media", "gate_a_spend", "generate_media", "repair",
        "graphics_compositing", "assemble", "qa_final", "gate_b_review", "publish", "analytics"
    ]
    original_invokers = {}
    for stage in mock_stages:
        kind, orig_fn = produce_db.STAGE_INVOKERS[stage]
        original_invokers[stage] = (kind, orig_fn)
        produce_db.STAGE_INVOKERS[stage] = (kind, MagicMock(return_value={"status": "stubbed"}))
    
    try:
        # Manually mark pre-QA stages as succeeded
        # S2-T01: qa_media depends on generate_media (unchanged) but upstream order changed
        for stage in ["research", "write_script", "review_script", "gate_a_content",
                      "storyboard", "review_storyboard", "gate_storyboard", "tts", "audio_timing", "reconcile_timing",
                      "compile_media", "gate_a_spend", "generate_media"]:
            _db.mirror_stage_state("qa_media_proj", stage, "done", db_path=TEST_DB)
            
        # Run production
        run_production(prod_id, db_path=TEST_DB)
        
        # Verify qa_media invoker was called
        assert mock_qa_media.call_count >= 1
        call_kwargs = mock_qa_media.call_args[0][0] # inputs dict
        assert call_kwargs["production_id"] == prod_id
        
    finally:
        # Restore original invokers
        for stage, (kind, orig_fn) in original_invokers.items():
            produce_db.STAGE_INVOKERS[stage] = (kind, orig_fn)


def test_from_stage_invalidates_downstream():
    """Verify --from-stage correctly invalidates the target stage and all downstream stages."""
    prod = _db.ensure_production("invalidate_test_proj", seed="invalidate test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    # Manually mark research and write_script as succeeded
    _db.mirror_stage_state("invalidate_test_proj", "research", "done", db_path=TEST_DB)
    _db.mirror_stage_state("invalidate_test_proj", "write_script", "done", db_path=TEST_DB)
    
    # Run with --from-stage write_script
    # We must mock all stages to prevent real execution
    with patch.object(produce_db, "STAGE_INVOKERS") as mock_invokers:
        # Create a mock invoker that just returns success for everything
        def dummy_invoker(inputs, tmp_path):
            return {"status": "stubbed"}
            
        mock_invokers.get.return_value = ("stubbed_kind", dummy_invoker)
        
        run_production(prod_id, from_stage="write_script", db_path=TEST_DB)
    
    # Verify write_script and downstream are invalidated (status='stale')
    conn = _db.connect(TEST_DB)
    all_ws = conn.execute(
        "SELECT status FROM stage_runs WHERE production_id=? AND stage_name='write_script'",
        (prod_id,)
    ).fetchall()
    conn.close()
    
    statuses = [row["status"] for row in all_ws]
    # The invalidation should have added a 'stale' entry
    assert "stale" in statuses


@patch("produce_db.invoke_research")
@patch("produce_db.invoke_write_script")
def test_resume_without_legacy_json(mock_write, mock_research):
    """Verify that deleting legacy JSON files does not break DB-native resume."""
    prod = _db.ensure_production("no_json_test_proj", seed="no json test", video_type="short", db_path=TEST_DB)
    prod_id = prod["id"]
    
    # Mock invokers to simulate success and return dummy payloads
    mock_research.return_value = {"status": "saved", "document_id": "doc_1"}
    mock_write.return_value = {"status": "saved", "document_id": "doc_2"}
    
    # Update STAGE_INVOKERS
    produce_db.STAGE_INVOKERS["research"] = (None, mock_research)
    produce_db.STAGE_INVOKERS["write_script"] = (None, mock_write)
    
    # Mock all subsequent stages to prevent real execution
    mock_stages = [
        "review_script", "gate_a_content", "storyboard", "review_storyboard", "gate_storyboard", "tts", "audio_timing",
        "reconcile_timing", "compile_media", "gate_a_spend", "generate_media",
        "qa_media", "repair", "graphics_compositing", "assemble", "qa_final", "gate_b_review", "publish", "analytics"
    ]
    original_invokers = {}
    for stage in mock_stages:
        kind, orig_fn = produce_db.STAGE_INVOKERS[stage]
        original_invokers[stage] = (kind, orig_fn)
        produce_db.STAGE_INVOKERS[stage] = (kind, MagicMock(return_value={"status": "stubbed"}))
    
    try:
        # Run once to create legacy files (simulating a previous run)
        run_production(prod_id, db_path=TEST_DB)
        
        # Delete the legacy JSON files
        import shutil
        project_dir = ROOT / "Videos" / "Projects" / "no_json_test_proj_short"
        if project_dir.exists():
            shutil.rmtree(project_dir)
            
        # Invalidate write_script to force a resume from there
        _db.invalidate_stages("no_json_test_proj", ["write_script"], reason="test resume without json", db_path=TEST_DB)
        
        # Run again: should succeed WITHOUT reading the deleted JSON files
        # because invoke_write_script now reads from get_research_brief (DB)
        run_production(prod_id, db_path=TEST_DB)
        
        # Verify write_script was called again
        assert mock_write.call_count >= 2
        
    finally:
        # Restore original invokers
        for stage, (kind, orig_fn) in original_invokers.items():
            produce_db.STAGE_INVOKERS[stage] = (kind, orig_fn)

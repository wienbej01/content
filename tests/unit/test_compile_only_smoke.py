"""ENG-1002: Compile-only smoke test — run compile/media plan only, no providers.

Verifies:
1. Production seed can be created.
2. Compile/media plan runs without error.
3. Render units are created with correct asset_type assignments.
4. Provider prompts are text-free (no exact-text risk keywords).
5. Local graphic units have deterministic_text_spec, NOT provider_visual_prompt.
6. Forbidden provider plan query returns zero rows.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _make_tone_wav(path: Path, duration_sec: float) -> None:
    """Generate a real, ffprobe-valid mono PCM tone."""
    from timeline_utils import MASTER_SAMPLE_RATE
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_sec}",
        "-acodec", "pcm_s16le", "-ar", str(MASTER_SAMPLE_RATE), "-ac", "1",
        str(path),
    ], capture_output=True, check=True)


@pytest.fixture
def db(tmp_path):
    import production_db as _db
    p = tmp_path / "test_compile_only_smoke.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    if "PRODUCTION_DB_PATH" in os.environ:
        del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db, tmp_path, monkeypatch):
    """Create a complete short production seed (research, script, storyboard, TTS, timing).
    
    This replicates the minimal DB state needed for compile_media to work:
    - production row
    - storyboard revision with creative beats (shot_type assigned)
    - timeline_spans with creative_beat_id
    - tts_master artifact
    """
    monkeypatch.setenv("YT_TEST_MODE", "1")
    import production_db as _db
    from authoring_service import save_document_revision
    from production_repo import register_artifact

    prod_row = _db.ensure_production("compile_only_smoke_test", db_path=db)
    pid = prod_row["id"]

    # Storyboard revision
    storyboard_rev = save_document_revision(pid, "storyboard", {"beats": [], "schema_version": "2.0"}, db_path=db)

    # Visual intent fixtures
    hero_intent = {
        "visual_function": "illustrate",
        "concept_key": "intro_concept",
        "concept_hash": "intro123",
        "narrative_claim": "Welcome to this smoke test",
        "information_to_show": "A presenter speaking",
        "viewer_takeaway": "This is a smoke test intro",
        "required_action": "watch",
        "distinctness_requirement": "talking head",
        "semantic_acceptance_criteria": "presenter visible",
    }
    title_intent = {
        "visual_function": "demonstrate",
        "concept_key": "title_card",
        "concept_hash": "title456",
        "narrative_claim": "Title card display",
        "information_to_show": "The title of the video",
        "viewer_takeaway": "Know the video topic",
        "required_action": "read",
        "distinctness_requirement": "branded title card",
        "semantic_acceptance_criteria": "title is visible",
    }
    broll_intent = {
        "visual_function": "illustrate",
        "concept_key": "environment",
        "concept_hash": "env789",
        "narrative_claim": "The environment establishment",
        "information_to_show": "An environment",
        "viewer_takeaway": "Establish setting",
        "required_action": "observe",
        "distinctness_requirement": "wide shot",
        "semantic_acceptance_criteria": "environment visible",
    }
    source_intent = {
        "visual_function": "demonstrate",
        "concept_key": "source_card",
        "concept_hash": "src012",
        "narrative_claim": "Source card display",
        "information_to_show": "A source citation",
        "viewer_takeaway": "Know the source",
        "required_action": "read",
        "distinctness_requirement": "source card branding",
        "semantic_acceptance_criteria": "source is visible",
    }

    # Create creative beats
    beats = [
        ("beat_intro", 1, "intro", "hero_lipsync", hero_intent, {}),
        ("beat_title", 2, "title", "graphic_title_card", title_intent,
         {"required": True, "layout": "key_line", "text": "SMOKE TEST"}),
        ("beat_broll", 3, "broll", "broll_environment", broll_intent, {}),
        ("beat_source", 4, "source", "graphic_title_card", source_intent,
         {"required": True, "layout": "lower_third", "text": "SOURCE CARD"}),
    ]

    with _db.transaction(db) as conn:
        for beat_id, ordinal, label, shot_type, v_intent, graphics in beats:
            conn.execute(
                "INSERT INTO creative_beats "
                "(id, storyboard_revision_id, ordinal, label, shot_type, visual_intent_json, graphics_json) "
                "VALUES (?,?,?,?,?,?,?)",
                (beat_id, storyboard_rev["id"], ordinal, label, shot_type,
                 json.dumps(v_intent), json.dumps(graphics)),
            )

    # Create timeline spans (need to match beat ordinals)
    spans_data = [
        (1, "beat_intro", "hero_lipsync_intro", 0, 4000),
        (2, "beat_title", "graphic_title", 4000, 8000),
        (3, "beat_broll", "broll_clip", 8000, 12000),
        (4, "beat_source", "source_card", 12000, 16000),
    ]

    with _db.transaction(db) as conn:
        for ordinal, beat_id, label, start_ms, end_ms in spans_data:
            conn.execute(
                "INSERT INTO timeline_spans "
                "(id, production_id, creative_beat_id, label, start_ms, end_ms, duration_ms, status, ordinal) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"span_{label}", pid, beat_id, label, start_ms, end_ms,
                 end_ms - start_ms, "active", ordinal),
            )

    # Register a TTS master artifact (needed for hero lipsync slicing)
    d = Path(tempfile.mkdtemp(prefix="compile_smoke_tts_"))
    wav = d / "continuous.wav"
    _make_tone_wav(wav, 5.0)
    register_artifact(pid, wav, "tts_master", db_path=db)

    yield prod_row

    # Cleanup
    import shutil
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    _db._db_path_override = None


class TestCompileOnlySmoke:
    """ENG-1002: Compile-only smoke test with DB query validation."""

    def test_compile_media_creates_render_plan(self, db, prod, tmp_path):
        """Compile media stage creates render units with proper asset type assignment."""
        from scripts.produce_db import invoke_compile_media

        result = invoke_compile_media({"production_id": prod["id"]}, tmp_path)
        assert result["status"] == "saved"
        assert result["units_count"] > 0
        assert result["plan_revision_id"] is not None
        assert result["estimated_cost_usd"] > 0

    def test_render_units_have_correct_asset_types(self, db, prod, tmp_path):
        """Render units reflect the canonical asset types from compile_media."""
        from scripts.produce_db import invoke_compile_media
        import production_db as _db

        invoke_compile_media({"production_id": prod["id"]}, tmp_path)

        conn = _db.connect(db)
        units = conn.execute(
            """SELECT id, label, ordinal, asset_type, model, audio_policy, text_policy,
                      status, metadata_json
               FROM render_units
               WHERE production_id=? AND status!='stale'
               ORDER BY ordinal""",
            (prod["id"],),
        ).fetchall()
        conn.close()

        assert len(units) >= 4, f"Expected >=4 units, got {len(units)}"

        # Classify by asset type
        local_graphics = [u for u in units if u["asset_type"] == "local_graphic"]
        provider_videos = [u for u in units if u["asset_type"] in ("generated_video", "lipsync_video")]

        assert len(local_graphics) >= 1, "Should have >=1 local_graphic units"
        assert len(provider_videos) >= 1, "Should have >=1 provider-eligible units"

    def test_forbidden_provider_plan_query_returns_zero(self, db, prod, tmp_path):
        """Critical invariant: no local-graphic-type render unit has a provider_visual_prompt."""
        from scripts.produce_db import invoke_compile_media
        import production_db as _db

        invoke_compile_media({"production_id": prod["id"]}, tmp_path)

        # The ENG-1002 forbidden provider plan query:
        conn = _db.connect(db)
        forbidden_units = conn.execute(
            """SELECT id, asset_type, metadata_json
               FROM render_units
               WHERE production_id=?
                 AND asset_type IN ('local_graphic', 'title_card', 'lower_third',
                                   'source_card', 'quote_card', 'chart', 'diagram')
                 AND metadata_json LIKE '%provider_visual_prompt%'""",
            (prod["id"],),
        ).fetchall()
        conn.close()

        assert len(forbidden_units) == 0, (
            f"Found {len(forbidden_units)} forbidden unit(s) with provider_visual_prompt: "
            + "; ".join(f"{u['asset_type']}({u['id']})" for u in forbidden_units)
        )

    def test_local_graphics_have_deterministic_text_spec_not_provider_prompt(self, db, prod, tmp_path):
        """Local graphic units have deterministic_text_spec, NOT provider_visual_prompt."""
        from scripts.produce_db import invoke_compile_media
        import production_db as _db

        invoke_compile_media({"production_id": prod["id"]}, tmp_path)

        conn = _db.connect(db)
        local_graphics = conn.execute(
            """SELECT id, label, metadata_json
               FROM render_units
               WHERE production_id=? AND asset_type='local_graphic' AND status!='stale'
               ORDER BY ordinal""",
            (prod["id"],),
        ).fetchall()
        conn.close()

        for u in local_graphics:
            meta = json.loads(u["metadata_json"]) if u["metadata_json"] else {}
            dts = meta.get("deterministic_text_spec")
            assert dts is not None, (
                f"Local graphic {u['label'] or u['id']} has no deterministic_text_spec"
            )
            assert "provider_visual_prompt" not in meta, (
                f"Local graphic {u['label'] or u['id']} has provider_visual_prompt (forbidden)"
            )
            assert "type" in dts, (
                f"Local graphic {u['label'] or u['id']} deterministic_text_spec has no type"
            )
            assert "text" in dts or "headline" in dts, (
                f"Local graphic {u['label'] or u['id']} deterministic_text_spec has no text"
            )

    def test_provider_prompts_are_text_free(self, db, prod, tmp_path):
        """Provider-eligible render units have text-free prompts (no exact-text risks)."""
        from scripts.produce_db import invoke_compile_media
        from media_contract import detect_provider_prompt_text_risks
        import production_db as _db

        invoke_compile_media({"production_id": prod["id"]}, tmp_path)

        conn = _db.connect(db)
        provider_units = conn.execute(
            """SELECT id, label, asset_type, metadata_json
               FROM render_units
               WHERE production_id=?
                 AND asset_type IN ('generated_video', 'lipsync_video')
                 AND status!='stale'
               ORDER BY ordinal""",
            (prod["id"],),
        ).fetchall()
        conn.close()

        for u in provider_units:
            meta = json.loads(u["metadata_json"]) if u["metadata_json"] else {}
            prompt = meta.get("provider_visual_prompt") or meta.get("prompt") or ""
            risks = detect_provider_prompt_text_risks(prompt)
            assert len(risks) == 0, (
                f"Provider unit {u['label'] or u['id']}({u['asset_type']}) "
                f"has text risk(s): {'; '.join(risks)}"
            )

    def test_total_estimated_cost_is_reasonable(self, db, prod, tmp_path):
        """Estimated cost should be non-zero and finite."""
        from scripts.produce_db import invoke_compile_media

        result = invoke_compile_media({"production_id": prod["id"]}, tmp_path)
        cost = result["estimated_cost_usd"]
        assert cost > 0, f"Estimated cost should be positive, got {cost}"
        assert cost < 100, f"Estimated cost seems too high: ${cost}"

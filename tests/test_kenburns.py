"""TKT-407: Ken Burns effect for still_kenburns render units.

Verifies that still_kenburns units in graphics_compositing render as motion
clips via ffmpeg zoompan (deterministic from unit id seed, duration == span).
"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

import production_db as _db
from produce_db import invoke_graphics_compositing
from production_repo import commit_timeline_spans, plan_render_units


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test_kenburns.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_kenburns", video_type="short", db_path=db)


@pytest.fixture
def ref_image(tmp_path):
    from PIL import Image
    img = Image.new("RGB", (200, 150), color=(80, 40, 160))
    for x in range(0, 200, 30):
        img.putpixel((x, 75), (255, 200, 50))
    for y in range(0, 150, 30):
        img.putpixel((100, y), (50, 255, 100))
    img_path = tmp_path / "ref.png"
    img.save(str(img_path))
    return str(img_path)


def _make_still_kenburns_spec(span_id, ref_image_path=None):
    base = {
        "asset_type": "still_kenburns",
        "model": "still_kenburns",
        "audio_policy": "SILENT_GRAPHIC",
        "final_audio_source": "none",
        "provider_audio_usage": "discarded",
        "text_policy": "NO_VISIBLE_TEXT",
        "render_mode": "still_kenburns",
        "visual_function": "illustrate",
        "narrative_claim": "test ken burns",
        "information_to_show": "test visual",
        "viewer_takeaway": "test takeaway",
        "required_action": "slow pan",
        "distinctness_requirement": "test distinctness",
        "semantic_acceptance_criteria": "matches test",
        "concept_key": "test_kb",
        "concept_hash": "test_kb",
        "span_id": span_id,
    }
    if ref_image_path:
        base["image_path"] = ref_image_path
    return base


def _extract_frame_md5(video_path, at_sec):
    """Extract a single frame at a given time and return its MD5 hash."""
    import tempfile
    import hashlib as _hl
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        fout = td / "frame.png"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path),
             "-ss", str(at_sec), "-vframes", "1", str(fout)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        if fout.exists():
            return _hl.md5(fout.read_bytes()).hexdigest()
        return None


class TestKenBurnsBaseline:
    """TKT-407: still_kenburns units receive artifacts in graphics_compositing."""

    def test_still_kenburns_receives_artifact(self, db, prod, ref_image):
        """still_kenburns unit gets a video artifact through graphics_compositing."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "KENBURNS", "start_ms": 0, "end_ms": 3000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_still_kenburns_spec(spans[0]["id"], ref_image),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_kenburns", "video_type": "short"}
        result = invoke_graphics_compositing(inputs, Path("/tmp"))

        assert result["status"] == "completed"
        assert result.get("still_kenburns_rendered", 0) >= 1

        conn = _db.connect(db)
        ru = conn.execute(
            """SELECT id, active_artifact_id FROM render_units
               WHERE production_id=? AND asset_type='still_kenburns' AND status!='stale'""",
            (prod["id"],)
        ).fetchone()
        conn.close()

        assert ru["active_artifact_id"] is not None


class TestKenBurnsMotion:
    """TKT-407: still_kenburns produces motion video artifact."""

    def test_produces_video_with_motion(self, db, prod, ref_image):
        """Video artifact: duration matches span, frame-diff proves motion."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "KENBURNS", "start_ms": 0, "end_ms": 3000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_still_kenburns_spec(spans[0]["id"], ref_image),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_kenburns", "video_type": "short"}
        invoke_graphics_compositing(inputs, Path("/tmp"))

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT id, active_artifact_id FROM render_units WHERE production_id=? AND asset_type='still_kenburns'",
            (prod["id"],)
        ).fetchone()
        art = conn.execute(
            "SELECT uri, kind, metadata_json FROM artifacts WHERE id=?",
            (ru["active_artifact_id"],)
        ).fetchone()
        conn.close()

        artifact_path = Path(art["uri"])
        assert artifact_path.exists()

        meta = json.loads(art["metadata_json"])
        assert meta.get("render_method") == "still_kenburns"
        assert meta.get("renderer") == "render_graphics.py"
        assert meta.get("deterministic_renderer") is True

        probe = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(artifact_path)],
            text=True,
        ))
        has_video = any(s.get("codec_type") == "video" for s in probe.get("streams", []))
        assert has_video

        dur = float(probe["format"]["duration"])
        assert 2.0 < dur < 4.0, f"Expected duration ~3s, got {dur}s"

        assert art["kind"] == "generated_media_video"

        md5_early = _extract_frame_md5(artifact_path, 0.2)
        md5_late = _extract_frame_md5(artifact_path, dur - 0.5)
        assert md5_early is not None
        assert md5_late is not None
        assert md5_early != md5_late, "First and later frames are identical -- no motion"

        assert meta.get("reference_image") is not None
        assert "zoom_range" in meta
        assert "seed" in meta


class TestKenBurnsDeterminism:
    """TKT-407: zoompan params derivable deterministically from unit id seed."""

    def test_different_seeds_produce_different_output(self, db, prod, ref_image):
        """Two units produce different zoompan output."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "KB_A", "start_ms": 0, "end_ms": 2000},
            {"label": "KB_B", "start_ms": 2000, "end_ms": 4000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_still_kenburns_spec(spans[0]["id"], ref_image),
            _make_still_kenburns_spec(spans[1]["id"], ref_image),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_kenburns", "video_type": "short"}
        invoke_graphics_compositing(inputs, Path("/tmp"))

        conn = _db.connect(db)
        rus = conn.execute(
            "SELECT id, active_artifact_id FROM render_units WHERE production_id=? AND asset_type='still_kenburns' AND status!='stale'",
            (prod["id"],)
        ).fetchall()
        assert len(rus) == 2
        arts = [conn.execute("SELECT sha256 FROM artifacts WHERE id=?",
                (r["active_artifact_id"],)).fetchone() for r in rus]
        conn.close()

        assert arts[0]["sha256"] != arts[1]["sha256"], \
            "Different unit seeds should produce different zoompan output"


class TestKenBurnsRegression:
    """Non-still units are untouched by TKT-407."""

    def test_local_graphic_beside_still_kenburns(self, db, prod, ref_image):
        """local_graphic and still_kenburns coexist."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "GFX", "start_ms": 0, "end_ms": 2000},
            {"label": "KB", "start_ms": 2000, "end_ms": 4000},
        ], db_path=db)

        dts = {"type": "title_card", "text": "TEST", "headline": "TEST"}
        plan_render_units(prod["id"], [
            {
                "asset_type": "local_graphic",
                "model": None,
                "audio_policy": "SILENT_GRAPHIC",
                "final_audio_source": "none",
                "provider_audio_usage": "discarded",
                "text_policy": "DETERMINISTIC_GRAPHIC",
                "render_mode": "deterministic_graphic",
                "deterministic_text_spec": dts,
                "span_id": spans[0]["id"],
            },
            _make_still_kenburns_spec(spans[1]["id"], ref_image),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_kenburns", "video_type": "short"}
        result = invoke_graphics_compositing(inputs, Path("/tmp"))

        assert result["status"] == "completed"
        assert result.get("local_graphic_rendered", 0) >= 1
        assert result.get("still_kenburns_rendered", 0) >= 1


class TestKenBurnsNegative:
    """TKT-407: error cases."""

    def test_missing_reference_image_raises_error(self, db, prod):
        """Render error when no reference image available."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "KB", "start_ms": 0, "end_ms": 3000},
        ], db_path=db)

        plan_render_units(prod["id"], [
            _make_still_kenburns_spec(spans[0]["id"], ref_image_path=None),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_kenburns", "video_type": "short"}

        from render_graphics import render_still_kenburns_render_unit
        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT id FROM render_units WHERE production_id=? AND asset_type='still_kenburns'",
            (prod["id"],)
        ).fetchone()
        conn.close()

        with pytest.raises(RuntimeError, match="no reference_image_path"):
            render_still_kenburns_render_unit(None, prod["id"], ru["id"])

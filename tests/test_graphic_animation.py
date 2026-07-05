"""TKT-405: Integration tests for wired animation in graphics_compositing.

Verifies:
- >2s graphics render animated video artifacts via invoke_graphics_compositing.
- Motion proven via frame-diff between early and later frames.
- validate_animation_requirement enforced on >2s graphics without animation.
- <=2s graphics still use static PNG path.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

import production_db as _db
from produce_db import invoke_graphics_compositing
from production_repo import commit_timeline_spans, plan_render_units

ROOT = Path(__file__).resolve().parent.parent


def _probe_video_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=15,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return float(r.stdout.strip())


def _extract_frame(path, time_s, frame_path):
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(time_s), "-i", str(path),
         "-vframes", "1", "-q:v", "2", str(frame_path)],
        capture_output=True, check=True, timeout=30,
    )


def _frame_pixel_diff(path_a, path_b):
    from PIL import Image
    import numpy as np
    a = np.array(Image.open(path_a).convert("L"), dtype=np.float64)
    b = np.array(Image.open(path_b).convert("L"), dtype=np.float64)
    return float(np.mean(np.abs(a - b)))


def _get_active_artifact_meta(production_id, render_unit_id, db_path):
    conn = _db.connect(db_path)
    ru = conn.execute(
        "SELECT active_artifact_id FROM render_units WHERE id=?",
        (render_unit_id,)
    ).fetchone()
    if not ru or not ru["active_artifact_id"]:
        conn.close()
        return None
    art = conn.execute(
        "SELECT uri, kind, mime_type, metadata_json FROM artifacts WHERE id=?",
        (ru["active_artifact_id"],)
    ).fetchone()
    conn.close()
    return dict(art) if art else None


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test_anim.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db._db_path_override = str(p)
    _db.migrate(str(p))
    yield str(p)
    _db._db_path_override = None
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_anim_gfx", video_type="short", db_path=db)


def _gfx_spec(span_id, dts, required_duration_ms=5000):
    return {
        "asset_type": "local_graphic",
        "model": None,
        "audio_policy": "SILENT_GRAPHIC",
        "final_audio_source": "none",
        "provider_audio_usage": "discarded",
        "text_policy": "DETERMINISTIC_GRAPHIC",
        "render_mode": "deterministic_graphic",
        "deterministic_text_spec": dts,
        "span_id": span_id,
        "required_duration_ms": required_duration_ms,
    }


class TestGraphicsAnimationWired:
    """TKT-405: Animation wired into invoke_graphics_compositing."""

    def test_span_gt_2s_renders_video_artifact_with_motion(self, db, prod, tmp_path):
        """5s stat_callout unit produces a video artifact with proven motion."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "ANI", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "stat_card", "stat": "99%", "headline": "Success Rate"}
        plan_render_units(prod["id"], [
            _gfx_spec(spans[0]["id"], dts, required_duration_ms=5000),
        ], db_path=db)

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT id FROM render_units WHERE production_id=? AND asset_type='local_graphic'",
            (prod["id"],)
        ).fetchone()
        conn.close()
        assert ru is not None

        inputs = {"production_id": prod["id"], "project_slug": "test_anim_gfx", "video_type": "short"}
        result = invoke_graphics_compositing(inputs, Path("/tmp"))

        assert result["status"] == "completed"
        assert result["local_graphic_rendered"] >= 1

        art = _get_active_artifact_meta(prod["id"], ru["id"], db)
        assert art is not None

        assert art["kind"] in ("generated_media_video",), \
            f"Expected animated video artifact for >2s graphic, got kind={art['kind']}"
        assert art["uri"].endswith(".mp4"), \
            f"Expected .mp4 artifact for animated graphic, got {art['uri']}"

        duration = _probe_video_duration(art["uri"])
        assert duration is not None
        assert abs(duration - 5.0) < 1.0

        f0 = tmp_path / "frame_0.2.png"
        f1 = tmp_path / "frame_1.5.png"
        _extract_frame(art["uri"], 0.2, f0)
        _extract_frame(art["uri"], 1.5, f1)
        diff = _frame_pixel_diff(f0, f1)
        assert diff > 0, f"Motion not proven: pixel diff = {diff}"

    def test_span_gt_2s_no_animation_fails_validation(self, db, prod):
        """>2s graphic without animation spec fails via validate_animation_requirement."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "NO_ANI", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "stat_card", "stat": "99%", "headline": "Success"}
        plan_render_units(prod["id"], [
            _gfx_spec(spans[0]["id"], dts, required_duration_ms=5000),
        ], db_path=db)

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT id FROM render_units WHERE production_id=? AND asset_type='local_graphic'",
            (prod["id"],)
        ).fetchone()
        conn.close()

        from render_graphics import validate_animation_requirement

        spec = dts
        with pytest.raises(RuntimeError, match="BLOCKED_GRAPHICS_ANIMATION_REQUIRED"):
            validate_animation_requirement({"layout": "stat_callout", "text": "99%"}, duration_sec=5.0)

    def test_span_lte_2s_uses_static_png_path(self, db, prod):
        """<=2s graphics still use the static PNG path."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "SHORT", "start_ms": 0, "end_ms": 2000},
        ], db_path=db)

        dts = {"type": "stat_card", "stat": "50%", "headline": "Short"}
        plan_render_units(prod["id"], [
            _gfx_spec(spans[0]["id"], dts, required_duration_ms=2000),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_anim_gfx", "video_type": "short"}
        result = invoke_graphics_compositing(inputs, Path("/tmp"))

        assert result["status"] == "completed"

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT id, active_artifact_id FROM render_units WHERE production_id=? AND asset_type='local_graphic'",
            (prod["id"],)
        ).fetchone()
        conn.close()

        assert ru is not None
        assert ru["active_artifact_id"] is not None

        art = _get_active_artifact_meta(prod["id"], ru["id"], db)
        assert art is not None
        assert art["kind"] == "generated_media"
        assert art["uri"].endswith(".png")

    def test_animated_artifact_qa_frame_ocr_passes(self, db, prod, tmp_path):
        """OCRed steady-state frame from animated video passes basic checks."""
        spans = commit_timeline_spans(prod["id"], [
            {"label": "QA_ANI", "start_ms": 0, "end_ms": 5000},
        ], db_path=db)

        dts = {"type": "stat_card", "stat": "99%", "headline": "QA Test"}
        plan_render_units(prod["id"], [
            _gfx_spec(spans[0]["id"], dts, required_duration_ms=5000),
        ], db_path=db)

        inputs = {"production_id": prod["id"], "project_slug": "test_anim_gfx", "video_type": "short"}
        result = invoke_graphics_compositing(inputs, Path("/tmp"))
        assert result["status"] == "completed"

        conn = _db.connect(db)
        ru = conn.execute(
            "SELECT id, active_artifact_id FROM render_units WHERE production_id=? AND asset_type='local_graphic'",
            (prod["id"],)
        ).fetchone()
        conn.close()

        art = _get_active_artifact_meta(prod["id"], ru["id"], db)
        assert art is not None
        assert art["kind"] in ("generated_media_video",), \
            f"Expected video artifact for >2s graphic, got kind={art['kind']}"

        f_end = tmp_path / "qa_frame_end.png"
        dur = _probe_video_duration(art["uri"])
        assert dur is not None
        _extract_frame(art["uri"], max(0, dur - 0.5), f_end)
        assert f_end.exists()

        from PIL import Image
        img = Image.open(f_end)
        assert img.size[0] > 0 and img.size[1] > 0

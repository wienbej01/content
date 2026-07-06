"""Tests for TKT-103: Automated measure -> compensate -> re-measure loop.

Tests the compensate_hero_audio repair action with a fixture sync backend.
Includes REPAIR-TKT-601B-W1: directional compensation for positive offsets.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import production_db as _db
from production_repo import register_artifact, link_artifact_to_render_unit
from media_service import run_contract_media_qa, run_repair_lifecycle
from sync_scorer.scorer import _set_sync_scorer_backend, FixtureSyncBackend
from compensate import compensate, COMPENSATION_MIN_OFFSET_MS, COMPENSATION_MAX_OFFSET_MS


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y"] + list(args), capture_output=True, check=True)


def make_video(path: Path, duration_sec: float = 3.0):
    _ffmpeg(
        "-f", "lavfi", "-i", f"color=c=red:s=320x240:r=24:d={duration_sec}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(path),
    )


def make_audio(path: Path, duration_sec: float = 3.0):
    _ffmpeg(
        "-f", "lavfi", "-i", f"anoisesrc=d={duration_sec}:c=pink:r=48000",
        str(path),
    )


class CountdownFixtureBackend:
    """Fixture backend that returns decreasing offsets on consecutive calls."""

    def __init__(self, offsets: list[float], confidence: float = 0.8):
        self._offsets = list(offsets)
        self._idx = 0
        self._confidence = confidence
        self._available = True

    def availability(self) -> bool:
        return self._available

    def score(self, video_path, audio_path):
        offset = self._offsets[self._idx] if self._idx < len(self._offsets) else 0.0
        self._idx += 1
        return FixtureSyncBackend(
            offset_ms=offset, confidence=self._confidence,
            face_track_found=True,
            method="countdown_fixture",
        ).score(video_path, audio_path)


class ConstantFixtureBackend:
    """Fixture backend that returns a constant offset."""

    def __init__(self, offset_ms: float, confidence: float = 0.8):
        self._offset_ms = offset_ms
        self._confidence = confidence
        self._available = True

    def availability(self) -> bool:
        return self._available

    def score(self, video_path, audio_path):
        return FixtureSyncBackend(
            offset_ms=self._offset_ms, confidence=self._confidence,
            face_track_found=True,
            method="constant_fixture",
        ).score(video_path, audio_path)


@pytest.fixture(autouse=True)
def reset_backend():
    yield
    _set_sync_scorer_backend(None)


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "test.db"
    _db.migrate(str(p))
    return str(p)


@pytest.fixture
def prod(db_path):
    return _db.ensure_production("tkt103_test", db_path=db_path)


def _setup_hero_unit(prod, db_path, tmp_path, offset_ms: float):
    """Create a hero render unit with artifacts and provider job.

    Returns (render_unit_id, video_path, audio_path).
    """
    video_path = tmp_path / "provider_video.mp4"
    make_video(video_path)

    audio_path = tmp_path / "source_slice.wav"
    make_audio(audio_path)

    art_video = register_artifact(
        prod["id"], video_path, "generated_video", db_path=db_path,
    )
    art_audio = register_artifact(
        prod["id"], audio_path, "hero_audio_slice", db_path=db_path,
    )

    conn = _db.connect(db_path)
    ru_id = f"ru_tkt103_{uuid.uuid4().hex[:8]}"
    pj_id = f"pj_{uuid.uuid4().hex[:8]}"
    now = _db._now()
    conn.close()

    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO render_units
               (id, production_id, label, asset_type, audio_policy,
                lipsync_required, required_start_ms, required_end_ms,
                required_duration_ms, ordinal, status, render_mode,
                source_slice_sha256, active_artifact_id, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ru_id, prod["id"], "H001", "lipsync_video", "HERO_SYNC_LOCKED",
             1, 0, 3000, 3000, 1, "generated", "hero_lipsync",
             art_audio["sha256"], art_video["id"], now, now),
        )
        conn.execute(
            """INSERT INTO provider_jobs
               (id, production_id, render_unit_id, provider, operation, status,
                idempotency_key, submitted_at, completed_at)
               VALUES (?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
            (pj_id, prod["id"], ru_id, "seedance",
             "generate_lipsync", "completed", f"idemp_{uuid.uuid4().hex[:8]}"),
        )

    return ru_id, video_path, audio_path


class TestCompensateHeroAudio:

    def test_correctable_offset_compensates_and_passes(self, db_path, prod, tmp_path):
        ru_id, video_path, audio_path = _setup_hero_unit(
            prod, db_path, tmp_path, offset_ms=200.0,
        )

        backend = CountdownFixtureBackend(offsets=[200.0, 5.0])
        _set_sync_scorer_backend(backend)

        qa = run_contract_media_qa(db_path, prod["id"], ru_id)
        assert qa["status"] == "fail", (
            f"Expected QA to fail for 200ms offset, got {qa['status']}"
        )
        evidence = json.loads(qa["evidence_json"]) if isinstance(qa["evidence_json"], str) else qa["evidence_json"]
        assert evidence.get("lipsync_review_status") == "CORRECTABLE", (
            f"Expected CORRECTABLE, got {evidence.get('lipsync_review_status')}"
        )

        result = run_repair_lifecycle(prod["id"], ru_id, db_path=db_path)
        assert result.get("compensated") is True, (
            f"Expected compensation to succeed, got: {result}"
        )
        assert result.get("qa_passed") is True, (
            f"Expected QA to pass after compensation, got: {result}"
        )
        assert result.get("new_artifact_id") is not None, "Expected a new artifact ID"

        conn = _db.connect(db_path)
        pj = conn.execute(
            "SELECT compensated_artifact_path FROM provider_jobs "
            "WHERE render_unit_id=? ORDER BY rowid DESC LIMIT 1",
            (ru_id,),
        ).fetchone()
        conn.close()
        assert pj and pj["compensated_artifact_path"], (
            "Expected compensated_artifact_path to be set after successful compensation"
        )
        assert Path(pj["compensated_artifact_path"]).exists(), (
            f"Compensated artifact file not found: {pj['compensated_artifact_path']}"
        )

        conn = _db.connect(db_path)
        comp_row = conn.execute(
            "SELECT evidence_json FROM validations "
            "WHERE subject_id=? AND validator_name='compensation_attempt'",
            (ru_id,),
        ).fetchone()
        conn.close()
        assert comp_row is not None, "Expected compensation_attempt validation row"
        comp_ev = json.loads(comp_row["evidence_json"]) if isinstance(comp_row["evidence_json"], str) else comp_row["evidence_json"]
        assert comp_ev.get("offset_ms") == 200.0

        # Verify re-measure validation was written
        conn = _db.connect(db_path)
        sync_val = conn.execute(
            "SELECT status, evidence_json FROM validations "
            "WHERE subject_id=? AND validator_name='syncnet_offset' "
            "ORDER BY rowid DESC LIMIT 1",
            (ru_id,),
        ).fetchone()
        conn.close()
        assert sync_val is not None
        sync_ev = json.loads(sync_val["evidence_json"]) if isinstance(sync_val["evidence_json"], str) else sync_val["evidence_json"]
        assert sync_ev.get("offset_ms") == 5.0, (
            f"Expected re-measured offset 5.0, got {sync_ev.get('offset_ms')}"
        )

    def test_uncorrectable_offset_routes_to_regeneration(self, db_path, prod, tmp_path):
        ru_id, video_path, audio_path = _setup_hero_unit(
            prod, db_path, tmp_path, offset_ms=800.0,
        )

        backend = ConstantFixtureBackend(offset_ms=800.0)
        _set_sync_scorer_backend(backend)

        qa = run_contract_media_qa(db_path, prod["id"], ru_id)
        assert qa["status"] == "fail", (
            f"Expected QA to fail for 800ms offset, got {qa['status']}"
        )

        result = run_repair_lifecycle(prod["id"], ru_id, db_path=db_path)
        assert result.get("compensated") is None, (
            f"Expected no compensation attempt for uncorrectable offset, got: {result}"
        )
        assert "change_request_id" in result, (
            f"Expected change request for regeneration, got: {result}"
        )
        assert result.get("qa_passed") is True, (
            f"Expected repair to succeed (fall through to regeneration), got: {result}"
        )

    def test_failing_compensation_routes_to_regeneration(self, db_path, prod, tmp_path):
        ru_id, video_path, audio_path = _setup_hero_unit(
            prod, db_path, tmp_path, offset_ms=200.0,
        )

        backend = ConstantFixtureBackend(offset_ms=200.0)
        _set_sync_scorer_backend(backend)

        qa = run_contract_media_qa(db_path, prod["id"], ru_id)
        assert qa["status"] == "fail"

        result = run_repair_lifecycle(prod["id"], ru_id, db_path=db_path)
        assert result.get("compensated") is False, (
            f"Expected compensation to be marked as failed, got: {result}"
        )
        assert "change_request_id" in result, (
            f"Expected change request for fallback regeneration, got: {result}"
        )

        conn = _db.connect(db_path)
        pj = conn.execute(
            "SELECT compensated_artifact_path FROM provider_jobs "
            "WHERE render_unit_id=? ORDER BY rowid DESC LIMIT 1",
            (ru_id,),
        ).fetchone()
        conn.close()
        assert pj and not pj["compensated_artifact_path"], (
            "Expected compensated_artifact_path to remain NULL after failed compensation"
        )


class TestDirectionalCompensation601B:
    """REPAIR-TKT-601B-W1: directional compensation keyed on offset sign."""

    def test_positive_offset_advances_audio(self, tmp_path):
        video = tmp_path / "input.mp4"
        make_video(video)
        audio = tmp_path / "input.wav"
        make_audio(audio)
        output = tmp_path / "compensated.mp4"

        result = compensate(video, audio, +480, output)
        assert "error" not in result, f"Compensation failed: {result.get('error')}"
        assert result["offset_ms_applied"] == -480, (
            f"Positive offset must advance audio (negative applied), got {result['offset_ms_applied']}"
        )
        assert result["offset_ms_measured"] == 480
        assert output.exists()

    def test_negative_offset_delays_audio(self, tmp_path):
        video = tmp_path / "input.mp4"
        make_video(video)
        audio = tmp_path / "input.wav"
        make_audio(audio)
        output = tmp_path / "compensated.mp4"

        result = compensate(video, audio, -300, output)
        assert "error" not in result, f"Compensation failed: {result.get('error')}"
        assert result["offset_ms_applied"] == 300, (
            f"Negative offset must delay audio (positive applied), got {result['offset_ms_applied']}"
        )
        assert result["offset_ms_measured"] == -300
        assert output.exists()

    def test_positive_offset_reduces_measured_offset(self, tmp_path):
        video = tmp_path / "input.mp4"
        make_video(video, duration_sec=5.0)
        audio = tmp_path / "input.wav"
        make_audio(audio, duration_sec=5.0)
        output = tmp_path / "compensated.mp4"

        result = compensate(video, audio, +480, output)
        assert "error" not in result
        assert result["offset_ms_applied"] == -480
        assert output.exists()

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", str(output)],
            capture_output=True, text=True,
        )
        out_dur = json.loads(probe.stdout)["format"]["duration"]
        assert float(out_dur) > 0, "Output must have valid duration"

    def test_compensation_cap_raised(self):
        assert COMPENSATION_MAX_OFFSET_MS == 600, (
            f"COMPENSATION_MAX_OFFSET_MS must be 600 (was 400), got {COMPENSATION_MAX_OFFSET_MS}"
        )

    def test_positive_offset_correctable_with_raised_cap(self, db_path, prod, tmp_path):
        ru_id, video_path, audio_path = _setup_hero_unit(
            prod, db_path, tmp_path, offset_ms=480.0,
        )

        backend = CountdownFixtureBackend(offsets=[480.0, 5.0])
        _set_sync_scorer_backend(backend)

        qa = run_contract_media_qa(db_path, prod["id"], ru_id)
        assert qa["status"] == "fail"
        evidence = json.loads(qa["evidence_json"]) if isinstance(qa["evidence_json"], str) else qa["evidence_json"]
        assert evidence.get("lipsync_review_status") == "CORRECTABLE", (
            f"480ms must be CORRECTABLE with raised cap (600ms), got {evidence.get('lipsync_review_status')}"
        )

        result = run_repair_lifecycle(prod["id"], ru_id, db_path=db_path)
        assert result.get("compensated") is True, (
            f"Expected 480ms to be compensated successfully, got: {result}"
        )
        assert result.get("qa_passed") is True

    def test_offset_above_cap_uncorrectable(self, db_path, prod, tmp_path):
        ru_id, video_path, audio_path = _setup_hero_unit(
            prod, db_path, tmp_path, offset_ms=700.0,
        )

        backend = ConstantFixtureBackend(offset_ms=700.0)
        _set_sync_scorer_backend(backend)

        qa = run_contract_media_qa(db_path, prod["id"], ru_id)
        assert qa["status"] == "fail"
        evidence = json.loads(qa["evidence_json"]) if isinstance(qa["evidence_json"], str) else qa["evidence_json"]
        assert evidence.get("lipsync_review_status") == "FAIL", (
            f"700ms must be FAIL (>600ms cap), got {evidence.get('lipsync_review_status')}"
        )

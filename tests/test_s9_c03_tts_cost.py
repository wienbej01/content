"""S9-C03: TTS paid-call cost must be recorded in cost_events.

Background: invoke_tts made a real ~$0.30 ElevenLabs call (S9) but wrote no
cost_events row; the ~$0.90 spent is not in the ledger. This test verifies
that TTS operations record their cost to the cost_events table for spend
auditing against the $5 cap.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def prod(tmp_path, request):
    """Test production with script segments.

    Uses the autouse fixture's production_db._db_path_override for consistency.
    Each test gets a unique production slug based on the test name.
    Cleans up the project directory after the test.
    """
    import production_db as _db
    from authoring_service import save_research_brief, save_script
    from stage_runner import save_document_revision
    import subprocess
    import shutil

    # The autouse fixture sets _db_path_override to tmp_path / "test_production.db"
    _db.migrate(None)  # Migrate to the default path (the override)
    db_path = None  # Use default (override set by conftest)

    # Use test function name for unique production slug
    test_name = request.function.__name__ if hasattr(request, 'function') else 'test'
    prod_slug = f"s9_c03_tts_cost_{test_name}"

    prod = _db.ensure_production(prod_slug, seed="x", video_type="short", db_path=db_path)
    pid = prod["id"]
    save_research_brief(
        pid, {"summary": "x"},
        citations=[{"url": "a", "is_primary": True},
                   {"url": "b", "is_primary": True},
                   {"url": "c", "is_primary": True}],
        db_path=db_path)
    # Script with known text length for cost calculation
    test_text = "hello world this is a test " * 10  # ~270 chars
    save_script(pid, {"segments": [{"label": "B1", "text": test_text}]}, db_path=db_path)

    # Create an active document revision (invoke_tts requires this)
    save_document_revision(pid, "script", {"segments": [{"label": "B1", "text": test_text}]}, db_path=db_path)

    # Mark write_script as succeeded
    _db.mirror_stage_state(pid, "write_script", "succeeded", db_path=db_path)

    # Clean up any existing audio file from previous runs
    project_dir = ROOT / "Videos" / "Projects" / prod_slug
    audio_dir = project_dir / "narration"
    if audio_dir.exists():
        shutil.rmtree(audio_dir.parent, ignore_errors=True)

    yield prod

    # Cleanup: remove project directory after test
    if project_dir.exists():
        shutil.rmtree(project_dir, ignore_errors=True)


@pytest.fixture
def mock_audio_path(tmp_path):
    """Mock TTS audio result. Returns a function that creates the audio file.

    The returned function accepts a path argument and creates the audio file there.
    """
    import subprocess

    def _create_audio(path):
        """Create a fake audio file at the given path."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1:sample_rate=44100",
            "-q:a", "9", str(p),
        ], capture_output=True, check=True)
        return p

    return _create_audio


def test_invoke_tts_records_cost_event(prod, mock_audio_path, monkeypatch):
    """invoke_tts must write a cost_events row after successful TTS generation.

    This test uses a mocked ElevenLabsAdapter to avoid real paid calls while
    exercising the cost recording path. The cost should be derived from
    estimate_cost(text) and recorded as actual_usd (we use actual_usd since
    the call succeeded; ElevenLabs charges per character).
    """
    import os
    import production_db as _db
    import produce_db
    import paid_adapters
    import tempfile

    monkeypatch.delenv("YT_TEST_MODE", raising=False)  # Real path (but mocked adapter)

    # Debug: verify the env var is deleted
    assert os.environ.get("YT_TEST_MODE") is None, "YT_TEST_MODE should be None after deletion"

    # Mock the adapter to create a fake audio file in a temp location and return a dict
    def mock_submit(self, payload, idempotency_key):
        # Create a temporary audio file
        temp_dir = Path(tempfile.mkdtemp(prefix="el_tts_"))
        temp_audio = temp_dir / "narration.mp3"
        audio_file = mock_audio_path(str(temp_audio))
        # Return a dict like the real adapter does
        return {"audio_path": str(audio_file), "audio_size_bytes": audio_file.stat().st_size}
    monkeypatch.setattr(paid_adapters.ElevenLabsAdapter, "submit", mock_submit)

    # Calculate expected cost from the same logic invoke_tts should use
    conn = _db.connect(None)  # Uses autouse fixture's override
    segs = conn.execute(
        "SELECT ss.text FROM script_segments ss"
        " JOIN document_revisions dr ON ss.script_revision_id = dr.id"
        " WHERE dr.production_id=?",
        (prod["id"],),
    ).fetchall()
    conn.close()
    tts_text = " ".join(s["text"] for s in segs if s["text"])

    adapter = paid_adapters.ElevenLabsAdapter({})
    expected_cost = adapter.estimate_cost({"text": tts_text})

    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "x",
        "video_type": "short",
    }

    result = produce_db.invoke_tts(inputs, Path.cwd())

    # Verify cost event was written
    conn = _db.connect(None)  # Uses autouse fixture's override
    cost_row = conn.execute(
        "SELECT * FROM cost_events WHERE production_id=?",
        (prod["id"],),
    ).fetchone()
    conn.close()

    assert cost_row is not None, "No cost_events row found after TTS"
    assert cost_row["provider"] == "elevenlabs", f"Wrong provider: {cost_row['provider']}"
    assert cost_row["operation"] == "tts", f"Wrong operation: {cost_row['operation']}"
    assert cost_row["actual_usd"] == expected_cost, \
        f"Cost mismatch: expected {expected_cost}, got {cost_row['actual_usd']}"
    assert cost_row["currency"] == "USD"
    # provider_job_id should be NULL for TTS (no provider_jobs row)
    assert cost_row["provider_job_id"] is None


def test_cost_amount_matches_estimate_cost(prod, mock_audio_path, monkeypatch):
    """The recorded cost amount must match estimate_cost(text) for the script.

    This is a regression test for cost calculation correctness.
    """
    import production_db as _db
    import produce_db
    import paid_adapters
    import tempfile

    monkeypatch.delenv("YT_TEST_MODE", raising=False)

    def mock_submit(self, payload, idempotency_key):
        temp_dir = Path(tempfile.mkdtemp(prefix="el_tts_"))
        temp_audio = temp_dir / "narration.mp3"
        audio_file = mock_audio_path(str(temp_audio))
        return {"audio_path": str(audio_file), "audio_size_bytes": audio_file.stat().st_size}
    monkeypatch.setattr(paid_adapters.ElevenLabsAdapter, "submit", mock_submit)

    # Get the text that will be used for TTS
    conn = _db.connect(None)  # Uses autouse fixture's override
    segs = conn.execute(
        "SELECT ss.text FROM script_segments ss"
        " JOIN document_revisions dr ON ss.script_revision_id = dr.id"
        " WHERE dr.production_id=?",
        (prod["id"],),
    ).fetchall()
    conn.close()
    tts_text = " ".join(s["text"] for s in segs if s["text"])

    # Expected cost per ElevenLabsAdapter.estimate_cost
    adapter = paid_adapters.ElevenLabsAdapter({})
    expected_cost = adapter.estimate_cost({"text": tts_text})

    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "x",
        "video_type": "short",
    }

    produce_db.invoke_tts(inputs, Path.cwd())

    # Verify recorded cost matches the estimate
    conn = _db.connect(None)  # Uses autouse fixture's override
    row = conn.execute(
        "SELECT actual_usd FROM cost_events WHERE production_id=?",
        (prod["id"],),
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["actual_usd"] == expected_cost, \
        f"Cost ${row['actual_usd']} != estimate ${expected_cost} for {len(tts_text)} chars"


def test_cost_not_recorded_on_tts_failure(prod, monkeypatch):
    """Cost must NOT be recorded if TTS call fails."""
    import production_db as _db
    import produce_db
    import paid_adapters

    monkeypatch.delenv("YT_TEST_MODE", raising=False)

    # Mock adapter to raise error (simulating API failure)
    def mock_submit_error(self, payload, idempotency_key):
        raise paid_adapters.ProviderAdapterError("ElevenLabs API error: 500")
    monkeypatch.setattr(paid_adapters.ElevenLabsAdapter, "submit", mock_submit_error)

    inputs = {
        "production_id": prod["id"],
        "project_slug": prod["project_slug"],
        "seed": "x",
        "video_type": "short",
    }

    with pytest.raises(paid_adapters.ProviderAdapterError, match="ElevenLabs API error"):
        produce_db.invoke_tts(inputs, Path.cwd())

    # Verify no cost event was written
    conn = _db.connect(None)  # Uses autouse fixture's override
    row = conn.execute(
        "SELECT * FROM cost_events WHERE production_id=?",
        (prod["id"],),
    ).fetchone()
    conn.close()

    assert row is None, "Cost event recorded despite TTS failure"

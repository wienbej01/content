"""S8 safety regression: invoke_tts must NEVER make a paid call in YT_TEST_MODE.

Background: invoke_tts instantiated ElevenLabsAdapter directly (bypassing
get_provider_adapter's test-mode guard), so a missing master-narration file
triggered a REAL paid ElevenLabs call even under YT_TEST_MODE=1. This test
pins the fix: in test mode, a missing master narration must fail loud — never
fall through to the network.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def test_invoke_tts_refuses_paid_call_when_audio_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("YT_TEST_MODE", "1")

    import production_db as _db
    from authoring_service import save_research_brief, save_script
    import produce_db
    import paid_adapters

    prod = _db.ensure_production("s8_tts_guard", seed="x", video_type="short")
    pid = prod["id"]
    save_research_brief(
        pid, {"summary": "x"},
        citations=[{"url": "a", "is_primary": True},
                   {"url": "b", "is_primary": True},
                   {"url": "c", "is_primary": True}])
    save_script(pid, {"segments": [{"label": "B1", "text": "hello world this is a test"}]})

    # If the guard fails, this boom makes the paid call explode rather than
    # silently hitting the network.
    def _boom(*a, **k):
        raise AssertionError(
            "ElevenLabsAdapter.submit must NOT be called in YT_TEST_MODE")
    monkeypatch.setattr(paid_adapters.ElevenLabsAdapter, "submit", _boom)

    inputs = {"production_id": pid, "project_slug": prod["project_slug"],
              "seed": "x", "video_type": "short"}

    with pytest.raises(RuntimeError, match="forbidden"):
        produce_db.invoke_tts(inputs, tmp_path)

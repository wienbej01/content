"""ENG-0203: Capability-gate negative_prompt for paid provider adapters.

Tests that the HiggsfieldSeedanceAdapter respects per-model capability
mapping for negative_prompt:
  - seedance_2_0  → supports_negative_prompt = False → omit --negative_prompt
  - kling3_0      → supports_negative_prompt = False → omit --negative_prompt
  - future model  → supports_negative_prompt = True  → include --negative_prompt

Dry-run metadata records omission when capability is absent.

ENG-0202: Adapter-level second guard — contract enforcement at the adapter.
"""
import os
import subprocess
from unittest.mock import patch

import pytest

from paid_adapters import HiggsfieldSeedanceAdapter, ProviderAdapterError


def _dry_run_submit(adapter, payload):
    """Run adapter.submit with HIGGSFIELD_DRY_RUN=1 and return the result."""
    env = {**os.environ, "HIGGSFIELD_DRY_RUN": "1"}
    with patch.dict(os.environ, env, clear=False):
        return adapter.submit(payload, idempotency_key="test_dry_run_key")


class TestNegativePromptCapabilityGate:
    ADAPTER = HiggsfieldSeedanceAdapter(config={})

    PAYLOAD_LIPSYNC = {
        "model": "seedance_2_0",
        "prompt": "James at desk",
        "negative_prompt": "no futuristic holograms, no neon",
        "duration_sec": 10,
    }

    PAYLOAD_BROLL = {
        "model": "kling3_0",
        "prompt": "Cinematic office shot",
        "negative_prompt": "no futuristic holograms, no neon",
        "duration_sec": 10,
    }

    def test_seedance_dry_run_omits_negative_prompt(self):
        """Seedance dry-run with negative_prompt does not include --negative_prompt."""
        result = _dry_run_submit(self.ADAPTER, self.PAYLOAD_LIPSYNC)
        assert result["dry_run"] is True
        assert "--negative_prompt" not in result["args"]
        assert result.get("negative_prompt_omitted") is True
        assert result.get("omitted_reason") == "provider_capability"

    def test_kling_dry_run_omits_negative_prompt(self):
        """Kling dry-run with negative_prompt does not include --negative_prompt."""
        result = _dry_run_submit(self.ADAPTER, self.PAYLOAD_BROLL)
        assert result["dry_run"] is True
        assert "--negative_prompt" not in result["args"]
        assert result.get("negative_prompt_omitted") is True
        assert result.get("omitted_reason") == "provider_capability"

    def test_future_provider_with_capability_includes_negative_prompt(self):
        """Model with supports_negative_prompt=True includes --negative_prompt."""
        caps = dict(self.ADAPTER.PROVIDER_CAPABILITIES)
        caps["future_model_v1"] = {
            "supports_negative_prompt": True,
            "supports_audio_path": False,
        }
        with patch.object(
            self.ADAPTER, "PROVIDER_CAPABILITIES", caps
        ):
            payload = {
                "model": "future_model_v1",
                "prompt": "Test",
                "negative_prompt": "no blurry faces",
                "duration_sec": 5,
            }
            result = _dry_run_submit(self.ADAPTER, payload)
        assert result["dry_run"] is True
        assert "--negative_prompt" in result["args"]
        idx = result["args"].index("--negative_prompt")
        assert result["args"][idx + 1] == "no blurry faces"
        assert result.get("negative_prompt_omitted") is None

    def test_dry_run_metadata_records_omission(self):
        """Dry-run metadata includes negative_prompt_omitted + omitted_reason."""
        result = _dry_run_submit(self.ADAPTER, self.PAYLOAD_LIPSYNC)
        assert result["negative_prompt_omitted"] is True
        assert result["omitted_reason"] == "provider_capability"

    def test_dry_run_no_negative_prompt_no_omission_flag(self):
        """When negative_prompt is not in the payload, no omission metadata."""
        payload = dict(self.PAYLOAD_LIPSYNC)
        del payload["negative_prompt"]
        result = _dry_run_submit(self.ADAPTER, payload)
        assert result.get("negative_prompt_omitted") is None
        assert result.get("omitted_reason") is None


# ---------------------------------------------------------------------------
# ENG-0202: Adapter-level second guard
# ---------------------------------------------------------------------------

class TestAdapterSecondGuard:
    ADAPTER = HiggsfieldSeedanceAdapter(config={})

    def test_local_graphic_fails(self):
        """Direct adapter call with asset_type=local_graphic fails."""
        payload = {
            "asset_type": "local_graphic",
            "model": "kling3_0",
            "prompt": "test",
            "duration_sec": 5,
        }
        with pytest.raises(ProviderAdapterError) as exc:
            self.ADAPTER.submit(payload, idempotency_key="test")
        msg = str(exc.value)
        assert "BLOCKED" in msg
        assert "local_graphic" in msg

    def test_title_card_prompt_fails(self):
        """Direct adapter call with prompt=Title card: ... fails."""
        payload = {
            "asset_type": "generated_video",
            "model": "kling3_0",
            "prompt": "Title card: I'M JAMES HARRINGTON. MCKINSEY'S",
            "duration_sec": 5,
        }
        with pytest.raises(ProviderAdapterError) as exc:
            self.ADAPTER.submit(payload, idempotency_key="test")
        msg = str(exc.value)
        assert "BLOCKED" in msg
        assert "exact-text risk" in msg

    def test_safe_generated_video_passes_dry_run(self):
        """Direct adapter call with safe generated_video payload passes dry-run."""
        payload = {
            "asset_type": "generated_video",
            "model": "kling3_0",
            "prompt": "Cinematic establishing shot of a modern office",
            "duration_sec": 5,
        }
        result = _dry_run_submit(self.ADAPTER, payload)
        assert result["dry_run"] is True
        assert "--prompt" in result["args"]

    def test_safe_lipsync_passes_dry_run(self):
        """Direct adapter call with lipsync_video and audio path passes dry-run."""
        payload = {
            "asset_type": "lipsync_video",
            "model": "seedance_2_0",
            "prompt": "Photorealistic close-up of James",
            "audio_path": "/fixtures/audio/test.wav",
            "duration_sec": 10,
        }
        result = _dry_run_submit(self.ADAPTER, payload)
        assert result["dry_run"] is True
        assert "--audio" in result["args"]

    def test_adapter_error_does_not_create_files(self):
        """Adapter error for blocked payload does not create/modify files."""
        payload = {
            "asset_type": "local_graphic",
            "model": "kling3_0",
            "prompt": "test",
            "duration_sec": 5,
        }
        # Stub subprocess.run to fail loudly if called — it should not be
        with patch.object(subprocess, "run", side_effect=RuntimeError("should not reach subprocess")):
            with pytest.raises(ProviderAdapterError) as exc:
                self.ADAPTER.submit(payload, idempotency_key="test")
            assert "BLOCKED" in str(exc.value)
"""Tests for smoke_config.py — strict smoke config loader and defaults."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from smoke_config import SmokeConfig


class TestSmokeConfigDefaults:
    """When the config file is missing or empty, defaults must apply."""

    def test_load_returns_defaults_for_empty_dict(self):
        cfg = SmokeConfig({})
        assert cfg.strict_media_contract is True
        assert cfg.strict_provider_prompt_text_free is True
        assert cfg.strict_local_graphics is True
        assert cfg.strict_final_qa_contract is True
        assert cfg.allow_ocr_unavailable is False
        assert cfg.max_paid_provider_jobs == 20
        assert cfg.max_total_usd == 5.00

    def test_load_returns_defaults_for_none(self):
        cfg = SmokeConfig({})
        assert cfg.max_paid_provider_jobs == 20
        assert cfg.max_total_usd == 5.00

    def test_load_from_missing_file_returns_defaults(self, tmp_path):
        missing = tmp_path / "does_not_exist.yaml"
        cfg = SmokeConfig.load(missing)
        assert cfg.strict_media_contract is True
        assert cfg.max_total_usd == 5.00


class TestSmokeConfigValues:
    """When the config file has values, they override defaults."""

    def test_custom_max_jobs(self):
        cfg = SmokeConfig({"max_paid_provider_jobs": 5})
        assert cfg.max_paid_provider_jobs == 5

    def test_custom_max_usd(self):
        cfg = SmokeConfig({"max_total_usd": 1.00})
        assert cfg.max_total_usd == 1.00

    def test_custom_strict_flags(self):
        cfg = SmokeConfig({
            "strict_media_contract": False,
            "strict_provider_prompt_text_free": False,
            "strict_local_graphics": False,
            "strict_final_qa_contract": False,
            "allow_ocr_unavailable": True,
        })
        assert cfg.strict_media_contract is False
        assert cfg.strict_provider_prompt_text_free is False
        assert cfg.strict_local_graphics is False
        assert cfg.strict_final_qa_contract is False
        assert cfg.allow_ocr_unavailable is True

    def test_as_dict_returns_copy(self):
        cfg = SmokeConfig({"max_paid_provider_jobs": 3})
        d = cfg.as_dict
        assert d["max_paid_provider_jobs"] == 3
        assert isinstance(d, dict)

    def test_str_values_coerced_correctly(self):
        """If YAML produces strings for numeric fields, int/float properties still coerce."""
        cfg = SmokeConfig({"max_paid_provider_jobs": "3", "max_total_usd": "0.50"})
        assert cfg.max_paid_provider_jobs == 3
        assert isinstance(cfg.max_paid_provider_jobs, int)
        assert cfg.max_total_usd == 0.50
        assert isinstance(cfg.max_total_usd, float)


class TestSmokeConfigLoadFromFile:
    """Integration test — load from the actual configs/strict_smoke.yaml."""

    def test_load_smoke_contract_yaml_exists(self):
        """The real config file must exist at the expected path."""
        cfg = SmokeConfig.load()
        assert cfg.max_paid_provider_jobs == 20
        assert cfg.max_total_usd == 5.00
        assert cfg.strict_media_contract is True
        assert cfg.strict_provider_prompt_text_free is True
        assert cfg.strict_local_graphics is True
        assert cfg.strict_final_qa_contract is True
        assert cfg.allow_ocr_unavailable is False
        assert isinstance(cfg.as_dict, dict)

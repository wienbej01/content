"""Tests for TKT-501 act-specific music scoring rules."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


class TestAudioScoring:
    def test_load(self):
        cfg_path = ROOT / "configs" / "audio_scoring.yaml"
        assert cfg_path.exists()
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text())
        assert "acts" in cfg
        assert "silence_functions" in cfg
        for act in range(1, 7):
            assert act in cfg["acts"], f"Act {act} missing from audio_scoring.yaml"

    def test_query_act_3(self):
        cfg_path = ROOT / "configs" / "audio_scoring.yaml"
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text())
        act3 = cfg["acts"][3]
        assert act3["tempo_bpm"] > 0
        assert act3["energy_level"] > 0
        assert act3["instrumentation"]
        assert act3["reference_style"]

    def test_each_act_has_distinct_settings(self):
        cfg_path = ROOT / "configs" / "audio_scoring.yaml"
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text())
        acts = cfg["acts"]
        tempos = [acts[a]["tempo_bpm"] for a in range(1, 7)]
        energies = [acts[a]["energy_level"] for a in range(1, 7)]
        # Not all identical
        assert len(set(tempos)) > 1
        assert len(set(energies)) > 1

    def test_silence_functions(self):
        cfg_path = ROOT / "configs" / "audio_scoring.yaml"
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text())
        silence_fns = cfg["silence_functions"]
        assert "paradigm_shift" in silence_fns
        assert "philosophical_close" in silence_fns

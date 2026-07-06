"""Deterministic, hermetic EDL override fixtures.

Three fixtures for the edit-decision-list (EDL) override feature (TKT-601):
  1. valid_edl       — trim ±0.5s on non-hero beats, no constraint violation.
  2. invalid_edl     — trim below BEAT_MIN_SEC or shot-mix band violation.
  3. reorder_edl     — swap two adjacent non-hero beats.

Each fixture is a JSON file with a deterministic shape. No production code changes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import NamedTuple


class EDLFixture(NamedTuple):
    path: Path
    label: str  # 'valid' | 'invalid' | 'reorder'


def _base_beats() -> list[dict]:
    return [
        {"beat_id": "b_hook_001", "order": 0, "act": 1, "shot_type": "hero_lipsync",
         "narrative_function": "hook", "est_duration_sec": 8.0, "audio_policy": "keep_lipsync"},
        {"beat_id": "b_archival_002", "order": 1, "act": 1, "shot_type": "broll_archival",
         "narrative_function": "evidence_anchor", "est_duration_sec": 6.0},
        {"beat_id": "b_background_003", "order": 2, "act": 2, "shot_type": "talking_head_standard",
         "narrative_function": "thesis_statement", "est_duration_sec": 12.0,
         "audio_policy": "keep_lipsync"},
        {"beat_id": "b_metaphorical_004", "order": 3, "act": 2, "shot_type": "broll_metaphorical",
         "narrative_function": "visual_pause", "est_duration_sec": 4.0},
        {"beat_id": "b_pattern_005", "order": 4, "act": 3, "shot_type": "talking_head_standard",
         "narrative_function": "pattern_definition", "est_duration_sec": 10.0,
         "audio_policy": "keep_lipsync"},
        {"beat_id": "b_graphic_006", "order": 5, "act": 3, "shot_type": "graphic_progressive",
         "narrative_function": "framework_render", "est_duration_sec": 7.0},
        {"beat_id": "b_system_007", "order": 6, "act": 4, "shot_type": "talking_head_standard",
         "narrative_function": "system_walkthrough", "est_duration_sec": 9.0,
         "audio_policy": "keep_lipsync"},
        {"beat_id": "b_environment_008", "order": 7, "act": 5, "shot_type": "broll_environment",
         "narrative_function": "tonal_reset", "est_duration_sec": 5.0},
        {"beat_id": "b_giveback_009", "order": 8, "act": 6, "shot_type": "talking_head_standard",
         "narrative_function": "thesis_close", "est_duration_sec": 11.0,
         "audio_policy": "keep_lipsync"},
        {"beat_id": "b_cta_010", "order": 9, "act": 6, "shot_type": "talking_head_hero",
         "narrative_function": "call_to_action", "est_duration_sec": 6.0,
         "audio_policy": "keep_lipsync"},
    ]


def make_valid_edl(tmp_path: Path) -> EDLFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "valid_edl.json"
    doc = {"edl_version": "1.0", "overrides": [
        {"beat_id": "b_archival_002", "trim_start_sec": 0.0, "trim_end_sec": 0.5},
        {"beat_id": "b_system_007", "trim_start_sec": 0.5, "trim_end_sec": 0.0},
        {"beat_id": "b_environment_008", "trim_start_sec": 0.4, "trim_end_sec": 0.4},
        {"beat_id": "b_pattern_005", "music_duck_db": -12.0}
    ], "beats": _base_beats()}
    out.write_text(json.dumps(doc, indent=2))
    return EDLFixture(out, "valid")


def make_invalid_edl(tmp_path: Path) -> EDLFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "invalid_edl.json"
    doc = {"edl_version": "1.0", "overrides": [
        # trim 5.6s off a 6.0s beat → new length 0.4s < BEAT_MIN_SEC (0.1s is floor; documented impl will floor at 0.5s here)
        {"beat_id": "b_metaphorical_004", "trim_start_sec": 2.8, "trim_end_sec": 2.8},
        # exceeds hero chain cap by attempting to fully hero-lengthen via reorder
        {"beat_id": "b_hook_001", "reorder_after": "b_cta_010"}
    ], "beats": _base_beats()}
    out.write_text(json.dumps(doc, indent=2))
    return EDLFixture(out, "invalid")


def make_reorder_edl(tmp_path: Path) -> EDLFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "reorder_edl.json"
    doc = {"edl_version": "1.0", "overrides": [
        {"beat_id": "b_archival_002", "reorder_after": "b_background_003"},
        {"beat_id": "b_metaphorical_004", "reorder_after": "b_pattern_005"}
    ], "beats": _base_beats()}
    out.write_text(json.dumps(doc, indent=2))
    return EDLFixture(out, "reorder")


_ALL_BUILDERS = {
    "valid": make_valid_edl,
    "invalid": make_invalid_edl,
    "reorder": make_reorder_edl,
}


def build_all_fixtures(tmp_path: Path) -> dict[str, EDLFixture]:
    return {name: builder(tmp_path) for name, builder in _ALL_BUILDERS.items()}

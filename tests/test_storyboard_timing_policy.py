#!/usr/bin/env python3
"""tests/test_storyboard_timing_policy.py — Timing/drift policy validator tests for S22_T009.

Tests 9 required scenarios:
  1. Complete timing policy passes.
  2. Missing planned_duration_sec fails.
  3. Missing min/max usable duration fails.
  4. min > planned fails.
  5. planned > max fails.
  6. Unknown drift policy fails.
  7. Hero lipsync with pad_ok only fails.
  8. B-roll missing trim/regen policy fails.
  9. Local graphic missing extension policy fails.

All tests use local fixtures. No LLM calls, no paid APIs.
No drift resolution is tested here — only policy validation.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validate_timing_drift_policy import validate_timing_policy, load_fixture

FIXTURE = ROOT / "tests" / "fixtures" / "storyboard_v2"


def _error_text(errors):
    texts = []
    for e in errors:
        texts.append(e.get("message", ""))
        texts.append(e.get("entity_id", ""))
        texts.append(e.get("path", ""))
    return "\n".join(texts)


class TestCompleteTimingPolicy:
    def test_valid_semantic_storyboard_passes_timing(self):
        data = load_fixture("valid_semantic_storyboard.json")
        errors = validate_timing_policy(data)
        assert errors == [], (
            f"Valid semantic storyboard with complete timing policy should pass. "
            f"Got {len(errors)} errors: {[e['message'] for e in errors]}"
        )

    def test_valid_two_segment_passes_timing(self):
        data = load_fixture("valid_two_segment_storyboard.json")
        errors = validate_timing_policy(data)
        assert errors == [], (
            f"Valid two-segment storyboard with complete timing policy should pass. "
            f"Got {len(errors)} errors: {[e['message'] for e in errors]}"
        )

    def test_non_canonical_skips_timing(self):
        data = load_fixture("legacy_v2_fixture.json")
        errors = validate_timing_policy(data)
        assert errors == [], "Non-canonical storyboard should skip timing policy validation"


class TestMissingPlannedDuration:
    def test_missing_planned_duration_fails(self):
        data = load_fixture("timing_missing_planned_duration.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when planned_duration_sec is missing"
        assert "BLOCKED_MISSING_PLANNED_DURATION" in text, \
            f"Error should contain BLOCKED_MISSING_PLANNED_DURATION, got: {text}"
        assert "SH001" in text, \
            f"Error should reference shot SH001, got: {text}"


class TestMissingMinMaxDuration:
    def test_missing_min_max_duration_fails(self):
        data = load_fixture("timing_missing_min_max.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) >= 2, \
            f"Should fail with at least 2 errors (min + max), got {len(errors)}"
        assert "BLOCKED_MISSING_MIN_DURATION" in text, \
            f"Error should contain BLOCKED_MISSING_MIN_DURATION, got: {text}"
        assert "BLOCKED_MISSING_MAX_DURATION" in text, \
            f"Error should contain BLOCKED_MISSING_MAX_DURATION, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestMinGreaterThanPlanned:
    def test_min_greater_than_planned_fails(self):
        data = load_fixture("timing_min_greater_than_planned.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when min > planned"
        assert "BLOCKED_MIN_EXCEEDS_PLANNED" in text, \
            f"Error should contain BLOCKED_MIN_EXCEEDS_PLANNED, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestPlannedGreaterThanMax:
    def test_planned_greater_than_max_fails(self):
        data = load_fixture("timing_planned_greater_than_max.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail when planned > max"
        assert "BLOCKED_PLANNED_EXCEEDS_MAX" in text, \
            f"Error should contain BLOCKED_PLANNED_EXCEEDS_MAX, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestUnknownDriftPolicy:
    def test_unknown_drift_policy_fails(self):
        data = load_fixture("timing_unknown_drift_policy.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for unknown drift policy"
        assert "BLOCKED_UNKNOWN_DRIFT_POLICY" in text, \
            f"Error should contain BLOCKED_UNKNOWN_DRIFT_POLICY, got: {text}"
        assert "some_unknown_policy" in text, \
            f"Error should reference the unknown policy value, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestHeroLipsyncPadOnly:
    def test_hero_lipsync_pad_only_fails(self):
        data = load_fixture("timing_hero_lipsync_pad_only.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for hero_lipsync with pad_ok only"
        assert "BLOCKED_HERO_LIPSYNC_PAD_ONLY" in text, \
            f"Error should contain BLOCKED_HERO_LIPSYNC_PAD_ONLY, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestBrollMissingTrimPolicy:
    def test_broll_missing_trim_policy_fails(self):
        data = load_fixture("timing_broll_missing_trim_policy.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for B-roll with pad_ok only (no trim policy)"
        assert "BLOCKED_BROLL_MISSING_TRIM_POLICY" in text, \
            f"Error should contain BLOCKED_BROLL_MISSING_TRIM_POLICY, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestLocalGraphicMissingExtensionPolicy:
    def test_local_graphic_missing_extension_policy_fails(self):
        data = load_fixture("timing_local_graphic_missing_extension_policy.json")
        errors = validate_timing_policy(data)
        text = _error_text(errors)
        assert len(errors) > 0, "Should fail for local graphic with pad_ok only (no extension policy)"
        assert "BLOCKED_GRAPHIC_MISSING_EXTENSION_POLICY" in text, \
            f"Error should contain BLOCKED_GRAPHIC_MISSING_EXTENSION_POLICY, got: {text}"
        assert "SH001" in text, f"Error should reference shot SH001, got: {text}"


class TestErrorContainsShotId:
    def test_errors_contain_entity_id_and_path(self):
        data = load_fixture("timing_unknown_drift_policy.json")
        errors = validate_timing_policy(data)
        assert len(errors) > 0
        for e in errors:
            assert "entity_id" in e, f"Error missing entity_id: {e}"
            assert "path" in e, f"Error missing path: {e}"
            assert e["severity"] == "BLOCKER", \
                f"Error severity should be BLOCKER, got: {e['severity']}"


class TestEdgeCases:
    def test_hero_lipsync_trim_ok_passes(self):
        data = load_fixture("valid_semantic_storyboard.json")
        errors = validate_timing_policy(data)
        hero_errors = [e for e in errors if "hero_lipsync" in str(e.get("entity_id", "")) or "SH001" in e.get("entity_id", "")]
        assert hero_errors == [], (
            f"Hero/lipsync with trim_ok should pass. Got: {[e['message'] for e in hero_errors]}"
        )

    def test_broll_trim_ok_passes(self):
        data = load_fixture("valid_semantic_storyboard.json")
        errors = validate_timing_policy(data)
        broll_errors = [e for e in errors if "broll" in str(e.get("entity_id", "")).lower() or "SH002" in e.get("entity_id", "")]
        assert broll_errors == [], (
            f"B-roll with trim_ok should pass. Got: {[e['message'] for e in broll_errors]}"
        )

    def test_graphic_extend_still_ok_passes(self):
        data = load_fixture("valid_semantic_storyboard.json")
        errors = validate_timing_policy(data)
        assert errors == [], "Valid storyboard with proper policies should pass entirely"

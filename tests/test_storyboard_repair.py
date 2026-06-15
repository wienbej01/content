"""tests/test_storyboard_repair.py — PST-04 tests (mocked LLM, no real API calls)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from repair_storyboard_beats import repair_beats, validate_repair, build_repair_prompt


def _production_sb(beats):
    total_dur = beats[-1]["audio_end_sec"] if beats else 0
    return {
        "schema_version": "1.0",
        "project_id": "test",
        "master_audio_duration_sec": total_dur,
        "total_beats": len(beats),
        "beats": beats,
    }


def _creative_sb(beats):
    return {"schema_version": "2.0", "project_id": "test", "beats": beats}


def _repair_beat(narration="This is a single long sentence that cannot be split mechanically.",
                 start=86.627, end=96.200):
    dur = round(end - start, 3)
    return {
        "beat_id": "B008",
        "source_beat_id": "B008",
        "audio_start_sec": start,
        "audio_end_sec": end,
        "audio_duration_sec": dur,
        "narration_text": narration,
        "treatment": "hero_lipsync",
        "model": "seedance_2_0",
        "model_max_duration_sec": 10.0,
        "needs_repair": True,
        "coverage_plan": [{
            "asset_role": "primary",
            "asset_type": "generated_video",
            "required_start_sec": start,
            "required_end_sec": end,
            "required_duration_sec": dur,
        }],
        "graphics": [],
    }


NARRATION = "This is a single long sentence that cannot be split mechanically."


def _valid_repair_response(_prompt):
    """Mock LLM returning a valid repair (switch to broll to fit within limits)."""
    return [{
        "beat_id": "B008a",
        "source_beat_id": "B008",
        "audio_start_sec": 86.627,
        "audio_end_sec": 96.200,
        "audio_duration_sec": 9.573,
        "narration_text": NARRATION,
        "treatment": "broll",
        "model": "kling3_0",
        "model_max_duration_sec": 10.0,
        "coverage_plan": [{"asset_role": "primary", "asset_type": "generated_video",
                          "required_start_sec": 86.627, "required_end_sec": 96.200,
                          "required_duration_sec": 9.573}],
        "graphics": [],
        "split_index": 0,
        "split_total": 1,
    }]


def test_immutable_fields_enforced():
    """LLM output changes narration_text → repair rejected with IMMUTABLE_FIELD error."""
    beat = _repair_beat()

    def bad_llm(_prompt):
        r = _valid_repair_response(_prompt)
        r[0]["narration_text"] = "DIFFERENT narration that the LLM hallucinated."
        return r

    prod = _production_sb([beat])
    creative = _creative_sb([{"beat_id": "B008", "shot_type": "hero_lipsync"}])

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=bad_llm)
    assert log[0]["status"] == "REPAIR_FAILED"
    assert any("IMMUTABLE_FIELD" in e and "narration_text" in e for e in log[0]["errors"])


def test_audio_boundaries_enforced():
    """LLM output changes audio_start_sec → rejected."""
    beat = _repair_beat()

    def bad_llm(_prompt):
        r = _valid_repair_response(_prompt)
        r[0]["audio_start_sec"] = 85.0  # shifted
        return r

    prod = _production_sb([beat])
    creative = _creative_sb([{"beat_id": "B008", "shot_type": "hero_lipsync"}])

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=bad_llm)
    assert log[0]["status"] == "REPAIR_FAILED"
    assert any("IMMUTABLE_FIELD" in e and "audio_start_sec" in e for e in log[0]["errors"])


def test_missing_graphics_rejected():
    """Parent had required graphic, LLM output omits it → rejected."""
    beat = _repair_beat()
    beat["graphics"] = [{"type": "lower_third", "text": "Key Point", "required": True}]

    def bad_llm(_prompt):
        r = _valid_repair_response(_prompt)
        r[0]["graphics"] = []  # omitted required graphic
        return r

    prod = _production_sb([beat])
    creative = _creative_sb([{"beat_id": "B008", "shot_type": "hero_lipsync"}])

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=bad_llm)
    assert log[0]["status"] == "REPAIR_FAILED"
    assert any("MISSING_GRAPHIC" in e for e in log[0]["errors"])


def test_model_limit_still_exceeded():
    """LLM output still has audio_duration_sec > model_max → rejected, marked REPAIR_FAILED."""
    beat = _repair_beat(start=80.0, end=95.0)  # 15s, exceeds 10s max

    def bad_llm(_prompt):
        return [{
            "beat_id": "B008a",
            "source_beat_id": "B008",
            "audio_start_sec": 80.0,
            "audio_end_sec": 95.0,
            "audio_duration_sec": 15.0,  # still exceeds 10s
            "narration_text": beat["narration_text"],
            "treatment": "hero_lipsync",
            "model": "seedance_2_0",
            "model_max_duration_sec": 10.0,
            "coverage_plan": [{"asset_role": "primary", "asset_type": "generated_video",
                              "required_start_sec": 80.0, "required_end_sec": 95.0,
                              "required_duration_sec": 15.0}],
            "graphics": [],
            "split_index": 0,
            "split_total": 1,
        }]

    prod = _production_sb([beat])
    creative = _creative_sb([{"beat_id": "B008", "shot_type": "hero_lipsync"}])

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=bad_llm)
    assert log[0]["status"] == "REPAIR_FAILED"
    assert any("REPAIR_FAILED" in e and "exceeds model_max" in e for e in log[0]["errors"])
    # Beat should be marked as failed in the storyboard
    failed_beat = next(b for b in result["beats"] if b["beat_id"] == "B008")
    assert failed_beat.get("repair_status") == "REPAIR_FAILED"


def test_valid_repair_accepted():
    """Valid LLM output replaces the needs_repair beat in production storyboard."""
    beat = _repair_beat()
    prod = _production_sb([beat])
    creative = _creative_sb([{"beat_id": "B008", "shot_type": "hero_lipsync",
                              "visual_prompt": "James explains concept"}])

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=_valid_repair_response)
    assert log[0]["status"] == "REPAIRED"
    assert log[0]["replacement_count"] == 1
    # The repaired beat should be in the storyboard
    assert result["beats"][0]["beat_id"] == "B008a"
    assert result["beats"][0]["treatment"] == "broll"
    assert "needs_repair" not in result["beats"][0]


def test_dry_run_doesnt_call_llm():
    """--dry-run prints prompt context without calling LLM."""
    beat = _repair_beat()
    prod = _production_sb([beat])
    creative = _creative_sb([{"beat_id": "B008", "shot_type": "hero_lipsync"}])

    call_count = [0]

    def counting_llm(_prompt):
        call_count[0] += 1
        return _valid_repair_response(_prompt)

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=counting_llm, dry_run=True)
    assert call_count[0] == 0
    assert log[0]["status"] == "DRY_RUN"
    assert "prompt_preview" in log[0]


def test_only_named_beats_sent():
    """Only beats in the --beats list are sent to LLM; others unchanged."""
    beat_ok = {
        "beat_id": "B007",
        "source_beat_id": "B007",
        "audio_start_sec": 80.0,
        "audio_end_sec": 86.627,
        "audio_duration_sec": 6.627,
        "narration_text": "This beat is fine.",
        "treatment": "broll",
        "model": "kling3_0",
        "model_max_duration_sec": 10.0,
        "coverage_plan": [{"asset_role": "primary", "asset_type": "generated_video",
                          "required_start_sec": 80.0, "required_end_sec": 86.627,
                          "required_duration_sec": 6.627}],
        "graphics": [],
    }
    beat_repair = _repair_beat()

    prod = _production_sb([beat_ok, beat_repair])
    prod["master_audio_duration_sec"] = 96.200
    creative = _creative_sb([
        {"beat_id": "B007", "shot_type": "broll"},
        {"beat_id": "B008", "shot_type": "hero_lipsync"},
    ])

    sent_beats = []

    def tracking_llm(prompt):
        sent_beats.append(prompt)
        return _valid_repair_response(prompt)

    result, log = repair_beats(prod, creative, ["B008"], llm_fn=tracking_llm)

    # Only one LLM call (for B008)
    assert len(sent_beats) == 1
    assert "B008" in sent_beats[0]
    # B007 unchanged
    assert result["beats"][0]["beat_id"] == "B007"
    assert result["beats"][0]["narration_text"] == "This beat is fine."

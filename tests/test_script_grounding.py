"""Tests for write_script.py anti-fabrication changes (ESC-B)."""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from write_script import build_writer_prompt, detect_unsourced_named_claims  # noqa: E402

SAMPLE_BRIEF = {
    "seed": "ai decisions",
    "angle": "structural use of AI",
    "key_claims": [
        {
            "claim": "Shrestha, Ben-Menahem and von Krogh (2019) identify three AI decision modes.",
            "source": {
                "title": "How I use AI to make better decisions",
                "author_or_site": "IESE Insight / Shrestha, Ben-Menahem & von Krogh (2019)",
                "year": "2019",
                "url": "https://www.iese.edu/insight/articles/ai-decisions/",
            },
        }
    ],
    "research_text": (
        "A 2019 paper by Shrestha, Ben-Menahem and von Krogh (surfaced by IESE Insight) "
        "found there are three distinct AI decision modes. Choosing the wrong mode produces "
        "worse outcomes than no AI at all."
    ),
    "sources": [
        {"title": "How I use AI to make better decisions", "url": "https://www.iese.edu/insight/articles/ai-decisions/", "year": "2019"}
    ],
    "suggested_titles": ["Why You're Using AI Wrong"],
}


def test_research_text_in_prompt():
    """The writer prompt must include research_text from the brief."""
    prompt = build_writer_prompt(SAMPLE_BRIEF, "short")
    assert SAMPLE_BRIEF["research_text"] in prompt


def test_prompt_has_anti_fabrication_rule():
    """Prompt must contain the explicit anti-fabrication constraint."""
    prompt = build_writer_prompt(SAMPLE_BRIEF, "short")
    assert "Do NOT name a researcher, institution, study" in prompt
    assert "HARD FAILURE" in prompt


def test_detect_unsourced_named_claim():
    """A script claiming 'Stanford researchers found X' when Stanford is NOT in the brief → flagged."""
    script = "Stanford researchers found that confirmation bias affects 90% of executives."
    flagged = detect_unsourced_named_claims(script, SAMPLE_BRIEF)
    assert any("Stanford" in f for f in flagged)


def test_sourced_claim_not_flagged():
    """A claim referencing IESE / Shrestha that IS in the brief → not flagged."""
    script = "Shrestha researchers found three distinct AI decision modes at IESE."
    flagged = detect_unsourced_named_claims(script, SAMPLE_BRIEF)
    # Shrestha and IESE are both in the brief corpus
    assert not any("Shrestha" in f for f in flagged)


def test_no_fabrication_guard_is_warning_not_block():
    """detect_unsourced_named_claims returns a list; write_script does not raise on it."""
    # The function returns a list (possibly empty) — it never raises
    result = detect_unsourced_named_claims("Harvard researchers found X", SAMPLE_BRIEF)
    assert isinstance(result, list)
    # Even with flagged items, it's just a list — no exception
    assert len(result) >= 0

    # Verify write_script doesn't raise when heuristic fires (mock LLM)
    fake_script = {
        "segments": [{"id": "001", "text": "MIT researchers found that focus doubles output."}],
        "video_type": "short",
        "narration_mode": "continuous_voiceover",
    }
    with patch("llm_call.llm_call", return_value=(fake_script, "{}", None, None)):
        from write_script import write_script
        # Should not raise — warnings go to stderr only
        data, prompt = write_script(SAMPLE_BRIEF, "short")
        assert data is not None

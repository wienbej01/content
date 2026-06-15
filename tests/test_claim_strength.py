"""Tests for ESC-D: claim-strength matching and attribution exactness."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from write_script import (  # noqa: E402
    CLAIM_STRENGTH_RULE,
    build_writer_prompt,
    detect_overclaim_language,
)

BRIEF_WEAK_FRAMING = {
    "seed": "value capture",
    "angle": "professionals lose leverage",
    "key_claims": [
        {
            "claim": "A Stanford professor observes that many professionals fail to capture value.",
            "source": {"title": "Interview clip", "author_or_site": "Stanford"},
        }
    ],
    "research_text": (
        "In a quote from a Stanford lecture, Professor X observes that many "
        "professionals struggle with value capture. This is an observation, not a "
        "controlled study."
    ),
    "sources": [{"title": "Stanford lecture clip", "url": "https://example.com"}],
}


def test_claim_strength_rule_in_prompt():
    """build_writer_prompt includes CLAIM_STRENGTH_RULE text."""
    prompt = build_writer_prompt(BRIEF_WEAK_FRAMING, "flagship")
    assert "MATCH THE SOURCE'S CLAIM STRENGTH" in prompt
    assert "attribute to the authors" in prompt.lower() or "ATTRIBUTE EXACTLY" in prompt


def test_overclaim_detected():
    """Strong verb + weakly-framed source triggers a warning."""
    script = "Stanford research found professionals capture less value than expected."
    warnings = detect_overclaim_language(script, BRIEF_WEAK_FRAMING)
    assert len(warnings) > 0
    assert any("Stanford" in w for w in warnings)


def test_matched_strength_not_flagged():
    """Script matching brief's weak framing does NOT trigger a warning."""
    script = "A Stanford observation suggests professionals may struggle with value capture."
    warnings = detect_overclaim_language(script, BRIEF_WEAK_FRAMING)
    assert len(warnings) == 0


def test_misattribution_guidance_present():
    """Prompt instructs attributing to actual authors, not commenting institution."""
    prompt = build_writer_prompt(BRIEF_WEAK_FRAMING, "flagship")
    assert "commenting institution" in prompt.lower() or "NOT to the commenting institution" in prompt


def test_overclaim_is_warning_not_block():
    """detect_overclaim_language returns a list (warning-only), never raises."""
    script = "Stanford research found professionals capture less value."
    result = detect_overclaim_language(script, BRIEF_WEAK_FRAMING)
    assert isinstance(result, list)
    # Confirm it doesn't raise — the function completed successfully

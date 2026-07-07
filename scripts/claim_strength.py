"""TKT-403: Claim-strength mapper.

Extracts hedging language from source text and maps to a claim_strength enum:
  - observation: "an observation", "one study suggests"
  - quote: "according to X", "X argues"
  - single_study: "a study found", "one trial reported"
  - settled_science: "research proves", "studies show", "we prove"

Pure heuristic, no paid calls.
"""
from __future__ import annotations

import re
from typing import Optional


_STRENGTH_PATTERNS = [
    ("settled_science", re.compile(
        r"\b(?:research\s+(?:proves|shows|demonstrates)|studies\s+(?:show|prove|"
        r"demonstrate)|we\s+prove|it\s+is\s+(?:proven|established|settled)|"
        r"the\s+(?:evidence|science)\s+(?:is|shows))\b", re.I)),
    ("single_study", re.compile(
        r"\b(?:one\s+(?:study|trial|paper|experiment)|a\s+(?:single|recent)\s+"
        r"(?:study|trial|paper)|one\s+(?:study|trial)\s+(?:found|reported|showed)|"
        r"a\s+study\s+(?:found|reported|suggests|indicates)|"
        r"early\s+evidence\s+(?:suggests|indicates|points))\b", re.I)),
    ("quote", re.compile(
        r"\b(?:according\s+to|as\s+(?:noted|argued|stated|observed)\s+by|"
        r"(?:argues|notes|remarks|observes|suggests|contends)\s+that|"
        r"(?:in\s+the\s+words\s+of))\b", re.I)),
    ("observation", re.compile(
        r"\b(?:an?\s+(?:observation|commentary|opinion|remark)|"
        r"(?:this|that|it)\s+(?:is|was)\s+(?:an?\s+)?(?:observation|commentary|"
        r"opinion|remark|comment)|(?:one|we|they)\s+(?:might|could|may)\s+"
        r"(?:observe|note|remark|comment))\b", re.I)),
]

DEFAULT_STRENGTH = "observation"


def map_claim_strength(source_text: str) -> str:
    """Map source text to a claim_strength enum value.

    Returns the strongest matching level found in the text.
    Priority: settled_science > single_study > quote > observation.
    """
    for strength, pattern in _STRENGTH_PATTERNS:
        if pattern.search(source_text):
            return strength
    return DEFAULT_STRENGTH


def map_claim_strength_for_claim(claim: dict) -> str:
    """Map a key_claim dict to its strength, using source text if available."""
    if isinstance(claim, dict):
        source_text = claim.get("source", {}).get("text", "") or claim.get("claim", "")
        return map_claim_strength(source_text)
    return map_claim_strength(str(claim))

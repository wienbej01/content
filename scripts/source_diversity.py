"""TKT-404: Source diversity gate.

Rejects research briefs where any single source contributes >40% of key_claims.
Researcher is re-invoked with diversification instructions.

Config flag: SOURCE_DIVERSITY_MODE = off|on (default off).
"""
from __future__ import annotations

import os
from collections import Counter

SOURCE_DIVERSITY_MAX_FRACTION = 0.4


def check_source_diversity(brief: dict) -> dict:
    """Check diversity of sources across key_claims.

    Returns dict with 'passed', 'max_fraction', and 'dominant_source'.
    """
    if os.environ.get("SOURCE_DIVERSITY_MODE") != "on":
        return {"passed": True, "max_fraction": 0.0, "dominant_source": None, "mode": "off"}

    claims = brief.get("key_claims", [])
    if not claims:
        return {"passed": True, "max_fraction": 0.0, "dominant_source": None}

    source_names = []
    for claim in claims:
        if isinstance(claim, dict):
            src = claim.get("source", {})
            name = src.get("author") or src.get("title") or src.get("url", "")
            if name:
                source_names.append(name)

    if not source_names:
        return {"passed": True, "max_fraction": 0.0, "dominant_source": None}

    counts = Counter(source_names)
    max_source, max_count = counts.most_common(1)[0]
    max_fraction = max_count / len(source_names)

    return {
        "passed": max_fraction <= SOURCE_DIVERSITY_MAX_FRACTION,
        "max_fraction": round(max_fraction, 4),
        "dominant_source": max_source,
        "threshold": SOURCE_DIVERSITY_MAX_FRACTION,
    }

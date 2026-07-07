"""TKT-401: Citation URL download + NER cross-reference pipeline.

Provides:
  - fetch_and_extract(url) -> str
  - extract_entities(text) -> dict
  - verify_claim(claim_text, source_text) -> float
  - verify_brief(brief) -> list[dict]

Config flag: CITATION_VERIFY_MODE = off|on (default off).
Test mode uses TKT-003 fixtures (local HTML files).
"""
from __future__ import annotations

import os
import re
import urllib.parse
from typing import Optional


CITATION_CONFIDENCE_THRESHOLD = 0.6


def fetch_and_extract(url: str) -> str:
    """Fetch URL and extract readable text.

    In test mode (YT_TEST_MODE=1), resolves file:// URLs to local fixture HTML.
    In production, uses urllib to fetch and readability-lxml to extract.
    """
    if url.startswith("file://"):
        path = url[len("file://"):]
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return _strip_html(f.read())
    if os.environ.get("YT_TEST_MODE") == "1":
        # In test mode, reject non-file URLs to avoid network
        if not url.startswith("file://"):
            raise RuntimeError(f"Network disabled in test mode: {url}")
    # Production path
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            return _strip_html(html)
    except Exception as e:
        raise RuntimeError(f"fetch_and_extract failed for {url}: {e}") from e


def _strip_html(html: str) -> str:
    """Simple HTML tag stripping (no external dependency)."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_entities(text: str) -> dict:
    """Deterministic NER heuristic: extract capitalized names, years, percentages."""
    names = set()
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
        names.add(m.group(1))
    for m in re.finditer(r"\b([A-Z][a-z]+)\s+(?:University|Institute|School|Lab)\b", text):
        names.add(m.group(0))
    years = set(re.findall(r"\b(1[5-9]\d{2}|20[0-2]\d)\b", text))
    percentages = set(f"{m}%" for m in re.findall(r"\b(\d+(?:\.\d+)?)(?=%)", text))
    return {"names": sorted(names), "years": sorted(years), "percentages": sorted(percentages)}


def verify_claim(claim_text: str, source_text: str) -> float:
    """Return overlap score [0, 1] between claim and source text.

    Uses word-level Jaccard similarity with named-entity boosting.
    """
    claim_lower = claim_text.lower()
    source_lower = source_text.lower()
    claim_words = set(re.findall(r"[a-z0-9]+", claim_lower))
    source_words = set(re.findall(r"[a-z0-9]+", source_lower))
    if not claim_words:
        return 0.0
    overlap = len(claim_words & source_words)
    base_score = overlap / len(claim_words)
    # Boost if named entities from claim appear in source
    claim_entities = extract_entities(claim_text)
    source_entities = extract_entities(source_text)
    entity_boost = 0.0
    if claim_entities["names"]:
        matched = sum(1 for n in claim_entities["names"] if n.lower() in source_lower)
        entity_boost = 0.2 * (matched / len(claim_entities["names"]))
    return min(1.0, base_score + entity_boost)


def verify_brief(brief: dict) -> list[dict]:
    """Verify all key_claims in a research brief. Returns list of results."""
    results = []
    for claim in brief.get("key_claims", []):
        claim_text = claim.get("claim", "") if isinstance(claim, dict) else str(claim)
        source_url = claim.get("source", {}).get("url", "") if isinstance(claim, dict) else ""
        result = {
            "claim": claim_text,
            "source_url": source_url,
            "verified": False,
            "confidence": 0.0,
            "error": None,
        }
        if not source_url:
            result["error"] = "no source URL"
            results.append(result)
            continue
        try:
            source_text = fetch_and_extract(source_url)
            confidence = verify_claim(claim_text, source_text)
            result["confidence"] = round(confidence, 4)
            result["verified"] = confidence >= CITATION_CONFIDENCE_THRESHOLD
        except Exception as e:
            result["error"] = str(e)
        results.append(result)
    return results

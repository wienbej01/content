import json
import re
from pathlib import Path

import pytest

from tests.fixtures.citation_fixtures import (
    CitationFixture,
    build_all_fixtures,
    make_correctly_sourced,
    make_fabricated,
    make_mixed,
)


def _url_to_path(url: str, tmp_path: Path) -> Path:
    """ Resolve a citation source URL to a filesystem path.

    The fixture generators use stable 'local.test/<filename>' URLs;
    source HTML files live in tmp_path/<fixture>_sources/.
    """
    if url.startswith("file://"):
        return Path(url[len("file://"):])
    if url.startswith("local.test/"):
        filename = url[len("local.test/"):]
        candidate = tmp_path / filename
        if candidate.exists():
            return candidate
        # search up to four parent levels for the source_dir nesting
        p = tmp_path
        for _ in range(4):
            for sub in p.iterdir():
                if sub.is_dir():
                    cand = sub / filename
                    if cand.exists():
                        return cand
            p = p.parent
        return candidate  # fall through; will raise FileNotFoundError
    return Path(url)


def _url_body_contains(claim: str, source_url: str, tmp_path: Path) -> bool:
    """Local-content match assertion used by the test matrix.

    Mirrors what `fetch_and_extract(url) -> str` + `extract_entities(text) -> dict`
    + `verify_claim(claim_text, source_text) -> float` should do in TKT-401,
    but fully local (no network).
    """
    path = _url_to_path(source_url, tmp_path)
    if not path.exists():
        return False
    text = path.read_text().lower()
    cleaned_claim = re.sub(r"[^0-9a-z]+", " ", claim.lower()).split()
    if not cleaned_claim:
        return False
    # require each non-trivial word (length>2) of the claim to appear in source body
    significant = [w for w in cleaned_claim if len(w) > 2]
    matched = sum(1 for w in significant if w in text)
    if not significant:
        return False
    return matched / len(significant) >= 0.5


def test_correctly_sourced(tmp_path: Path):
    fx = make_correctly_sourced(tmp_path / "correctly_sourced")
    assert fx.brief_path.exists()
    brief = json.loads(fx.brief_path.read_text())
    for claim in brief["key_claims"]:
        url = claim["source"]["url"]
        assert _url_body_contains(claim["claim"], url, tmp_path / "correctly_sourced"), (
            f"Correctly-sourced brief: claim {claim['claim']!r} not found in source {url}"
        )
    assert fx.source_dir.exists()


def test_fabricated(tmp_path: Path):
    fx = make_fabricated(tmp_path / "fabricated")
    brief = json.loads(fx.brief_path.read_text())
    failures = []
    for claim in brief["key_claims"]:
        if not _url_body_contains(claim["claim"], claim["source"]["url"], tmp_path / "fabricated"):
            failures.append(claim)
    assert len(failures) >= 1, "Fabricated fixture must have at least one unverifiable claim"
    assert _url_body_contains(brief["key_claims"][0]["claim"], brief["key_claims"][0]["source"]["url"], tmp_path / "fabricated")


def test_mixed(tmp_path: Path):
    fx = make_mixed(tmp_path / "mixed")
    brief = json.loads(fx.brief_path.read_text())
    failures, passes = [], []
    for claim in brief["key_claims"]:
        if _url_body_contains(claim["claim"], claim["source"]["url"], tmp_path / "mixed"):
            passes.append(claim)
        else:
            failures.append(claim)
    assert len(passes) == 1, f"Mixed fixture expected 1 sourcing pass, got {len(passes)}"
    assert len(failures) == 1, f"Mixed fixture expected 1 sourcing failure, got {len(failures)}"


def test_fixture_parses_and_has_required_fields(tmp_path: Path):
    for name, builder in [
        ("correctly_sourced", make_correctly_sourced),
        ("fabricated", make_fabricated),
        ("mixed", make_mixed),
    ]:
        fx = builder(tmp_path / name)
        assert fx.brief_path.exists(), f"{name}: brief_path missing"
        brief = json.loads(fx.brief_path.read_text())
        assert "key_claims" in brief, f"{name}: missing key_claims"
        for claim in brief["key_claims"]:
            assert "claim" in claim and "source" in claim and "url" in claim["source"]
            path = _url_to_path(claim["source"]["url"], tmp_path / name)
            assert path.exists(), f"{name}: source body file missing at {path}"


def test_determinism(tmp_path: Path):
    for name, builder in [
        ("correctly_sourced", make_correctly_sourced),
        ("fabricated", make_fabricated),
        ("mixed", make_mixed),
    ]:
        fx1 = builder(tmp_path / f"{name}_a").brief_path
        fx2 = builder(tmp_path / f"{name}_b").brief_path
        assert fx1.read_bytes() == fx2.read_bytes(), f"{name}: fixture not deterministic"


def test_hermetic_no_network(monkeypatch, tmp_path: Path):
    import socket
    noop = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network disabled"))
    monkeypatch.setattr(socket, "gethostbyname", noop)
    fx = make_correctly_sourced(tmp_path / "hermetic")
    assert fx.brief_path.exists()
    assert len(list(fx.source_dir.glob("*.html"))) >= 2

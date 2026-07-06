import json
from pathlib import Path

import pytest

from tests.fixtures.edl_fixtures import (
    EDLFixture,
    build_all_fixtures,
    make_invalid_edl,
    make_reorder_edl,
    make_valid_edl,
)


def test_valid_edl_parses(tmp_path: Path):
    fx = make_valid_edl(tmp_path)
    doc = json.loads(fx.path.read_text())
    assert doc["edl_version"] == "1.0"
    assert len(doc["overrides"]) == 4
    for ov in doc["overrides"]:
        if "trim_end_sec" in ov:
            assert ov["trim_end_sec"] <= 0.5, "valid EDL must not trim > 0.5s"


def test_invalid_edl_parses(tmp_path: Path):
    fx = make_invalid_edl(tmp_path)
    doc = json.loads(fx.path.read_text())
    assert len(doc["overrides"]) == 2
    # second override is an out-of-range reorder (hook → cta crosses act boundary)
    assert doc["overrides"][1]["reorder_after"] == "b_cta_010"


def test_reorder_edl_parses(tmp_path: Path):
    fx = make_reorder_edl(tmp_path)
    doc = json.loads(fx.path.read_text())
    assert len(doc["overrides"]) == 2
    for ov in doc["overrides"]:
        assert "reorder_after" in ov


def test_edl_determinism(tmp_path: Path):
    for name, builder in [
        ("valid", make_valid_edl),
        ("invalid", make_invalid_edl),
        ("reorder", make_reorder_edl),
    ]:
        fx1 = builder(tmp_path / f"{name}_a").path
        fx2 = builder(tmp_path / f"{name}_b").path
        assert fx1.read_bytes() == fx2.read_bytes(), f"{name}: not deterministic"


def test_edl_hermetic_no_network(monkeypatch, tmp_path: Path):
    import socket
    noop = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network disabled"))
    monkeypatch.setattr(socket, "gethostbyname", noop)
    fx = make_valid_edl(tmp_path)
    assert fx.path.exists()


def test_edl_fixture_full_payload(tmp_path: Path):
    all_fx = build_all_fixtures(tmp_path)
    assert len(all_fx) == 3
    for name, fixture in all_fx.items():
        assert isinstance(fixture, EDLFixture)
        assert fixture.path.exists()
        assert fixture.label in {"valid", "invalid", "reorder"}
        doc = json.loads(fixture.path.read_text())
        assert "overrides" in doc
        assert "beats" in doc
        assert len(doc["beats"]) == 10

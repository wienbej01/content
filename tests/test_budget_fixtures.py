import json
from pathlib import Path

import pytest

from tests.fixtures.budget_fixtures import (
    BEAT_CAP,
    BEAT_MAX,
    BEAT_MIN,
    BudgetFixture,
    _flat_allocate,
    _weighted_allocate,
    build_all_fixtures,
    make_flat_budget_fixture,
    make_weighted_budget_fixture,
)


def test_flat_allocation_sum(tmp_path: Path):
    fx = make_flat_budget_fixture(tmp_path / "flat_sum")
    doc = json.loads(fx.path.read_text())
    assert doc["cap"] == BEAT_CAP
    assert abs(doc["sum"] - BEAT_CAP) < 0.01, f"flat sum {doc['sum']} != cap {BEAT_CAP}"
    assert doc["allocation_mode"] == "flat"


def test_flat_allocation_equal(tmp_path: Path):
    fx = make_flat_budget_fixture(tmp_path / "flat_eq")
    doc = json.loads(fx.path.read_text())
    amounts = [b["amount_usd"] for b in doc["beats"]]
    assert len(amounts) == 10
    assert len(set(amounts)) == 1, f"flat allocation produced unequal amounts: {amounts}"


def test_weighted_allocation_sum(tmp_path: Path):
    fx = make_weighted_budget_fixture(tmp_path / "weighted_sum")
    doc = json.loads(fx.path.read_text())
    assert abs(doc["sum"] - BEAT_CAP) < 0.01, f"weighted sum {doc['sum']} != cap {BEAT_CAP}"
    assert doc["allocation_mode"] == "weighted"


def test_weighted_allocation_within_bounds(tmp_path: Path):
    fx = make_weighted_budget_fixture(tmp_path / "weighted_bounds")
    doc = json.loads(fx.path.read_text())
    for b in doc["beats"]:
        assert b["amount_usd"] >= BEAT_MIN, f"beat {b['beat_id']} below floor: {b['amount_usd']}"
        assert b["amount_usd"] <= BEAT_MAX, f"beat {b['beat_id']} above ceil: {b['amount_usd']}"


def test_weighted_vs_flat_hero_beats(tmp_path: Path):
    """Hero beats (weight ≥2.5) must receive ≥3× what light beats (weight ≤0.5) receive.

    Per the plan's requirement: "weighted allocation gives hero beats ≥3× non-hero".
    Hero weight is 3.0, light weight is 0.5 — ratio 6× in weight → at least 3× in budget after
    floor/ceiling effects.
    """
    weighted = json.loads(make_weighted_budget_fixture(tmp_path / "cmp_weighted").path.read_text())
    hero_amounts = [b["amount_usd"] for b in weighted["beats"] if b["weight"] >= 2.5]
    light_amounts = [b["amount_usd"] for b in weighted["beats"] if b["weight"] <= 0.75]
    assert hero_amounts and light_amounts, "fixture must have both hero and light beats"
    min_hero = min(hero_amounts)
    max_light = max(light_amounts)
    assert min_hero > max_light * 3.0, (
        f"min hero amount {min_hero} not ≥3× max light amount {max_light}"
    )


def test_budget_determinism(tmp_path: Path):
    for name, builder in [
        ("flat", make_flat_budget_fixture),
        ("weighted", make_weighted_budget_fixture),
    ]:
        fx1 = builder(tmp_path / f"{name}_a").path
        fx2 = builder(tmp_path / f"{name}_b").path
        assert fx1.read_bytes() == fx2.read_bytes(), f"{name}: not deterministic"


def test_budget_hermetic_no_network(monkeypatch, tmp_path: Path):
    import socket
    noop = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network disabled"))
    monkeypatch.setattr(socket, "gethostbyname", noop)
    fx = make_weighted_budget_fixture(tmp_path / "hermetic")
    doc = json.loads(fx.path.read_text())
    assert abs(doc["sum"] - BEAT_CAP) < 0.01


def test_budget_full_payload(tmp_path: Path):
    all_fx = build_all_fixtures(tmp_path)
    assert len(all_fx) == 2
    for name, fixture in all_fx.items():
        assert isinstance(fixture, BudgetFixture)
        assert fixture.path.exists()
        assert fixture.label in {"flat", "weighted"}
        doc = json.loads(fixture.path.read_text())
        assert "cap" in doc
        assert "allocation_mode" in doc
        assert "sum" in doc
        assert "beats" in doc
        assert len(doc["beats"]) == 10


def test_budget_allocator_api():
    """Test the allocator functions directly for full coverage."""
    beats = [
        {"viewer_attention_weight": 3.0},
        {"viewer_attention_weight": 1.0},
        {"viewer_attention_weight": 0.5},
        {"viewer_attention_weight": 1.5},
    ]
    flat = _flat_allocate(beats, 60.0)
    assert len(flat) == 4
    assert abs(sum(flat) - 60.0) < 0.01
    assert len(set(flat)) == 1

    weighted = _weighted_allocate(beats, 60.0)
    assert len(weighted) == 4
    assert abs(sum(weighted) - 60.0) < 0.01
    # highest weight (3.0) should get the most
    assert weighted[0] > weighted[2], "heaviest beat should receive more than lightest"
    for a in weighted:
        assert BEAT_MIN <= a <= BEAT_MAX

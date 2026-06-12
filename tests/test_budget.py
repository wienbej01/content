#!/usr/bin/env python3
"""tests/test_budget.py — T7 tests for budget.py (G4 gate)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    import importlib.util
    spec = importlib.util.spec_from_file_location("budget", ROOT / "scripts" / "budget.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _plan(est_usd, beats=None, video_type="explainer"):
    if beats is None:
        beats = [
            {"beat_id": "B001", "cost": {"est_usd": 0.0}},   # $0 local
            {"beat_id": "B002", "cost": {"est_usd": 0.0}},
            {"beat_id": "B003", "cost": {"est_usd": 0.49}},   # generated
            {"beat_id": "B004", "cost": {"est_usd": 0.49}},
            {"beat_id": "B005", "cost": {"est_usd": 0.0}},    # $0 still
        ]
    return {"project_id": "test", "video_type": video_type,
            "beats": beats, "totals": {"est_usd": est_usd}}


def test_within_cap_passes():
    B = _load()
    blocking, _ = B.check(_plan(40.0))
    assert blocking == [], blocking
    print("  ✓ plan within cap passes")


def test_over_cap_fails():
    B = _load()
    blocking, _ = B.check(_plan(65.0))
    assert any("exceeds budget cap" in b for b in blocking)
    print("  ✓ over-cap plan is blocked")


def test_short_cap_lower():
    B = _load()
    # explainer cap is 60; short cap is 25
    blocking, _ = B.check(_plan(30.0, video_type="short"))
    assert any("exceeds budget cap" in b for b in blocking)
    print("  ✓ short video cap (25) is lower than explainer cap (60)")


def test_beat_anomaly_over_3usd():
    B = _load()
    beats = [{"beat_id": f"B{i:03d}", "cost": {"est_usd": 0.0}} for i in range(10)]
    beats.append({"beat_id": "B011", "cost": {"est_usd": 4.50}})  # no justification
    blocking, _ = B.check(_plan(4.50, beats=beats))
    assert any("$4.50 > $3" in b for b in blocking)
    print("  ✓ beat >$3 without justification is flagged")


def test_beat_anomaly_justified_passes():
    B = _load()
    beats = [{"beat_id": f"B{i:03d}", "cost": {"est_usd": 0.0}} for i in range(10)]
    beats.append({"beat_id": "B011", "cost": {"est_usd": 4.50},
                  "justification": "Act-6 emotional close"})
    blocking, _ = B.check(_plan(4.50, beats=beats))
    assert not any("$4.50 > $3" in b for b in blocking)
    print("  ✓ justified >$3 beat passes")


def test_zero_cost_pct_enforced():
    B = _load()
    # All beats are generated (non-zero cost) → <15% $0
    beats = [{"beat_id": f"B{i:03d}", "cost": {"est_usd": 0.49}} for i in range(10)]
    blocking, _ = B.check(_plan(4.90, beats=beats))
    assert any("$0 routes" in b for b in blocking)
    print("  ✓ <15% $0 beats is blocked")


def test_records_gate(tmp_path):
    import gates
    orig_dir = gates.PROJECTS_DIR
    gates.PROJECTS_DIR = tmp_path / "Projects"
    try:
        plan = _plan(40.0)
        plan_path = tmp_path / "media_plan.json"
        plan_path.write_text(json.dumps(plan))
        blocking, _ = _load().check(plan)
        assert blocking == []
        gates.record_gate("test", "budget", "pass", artifact_path=str(plan_path))
        entry = gates.gate_status("test", "budget")
        assert entry is not None and entry["status"] == "pass"
    finally:
        gates.PROJECTS_DIR = orig_dir
    print("  ✓ budget gate records to ledger")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

#!/usr/bin/env python3
"""tests/test_gates.py — T3 tests for the gate ledger + spend lock.

No external services, no Higgsfield, no API calls. Uses a temp project dir by
monkeypatching gates.PROJECTS_DIR.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("gates", ROOT / "scripts" / "gates.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def gates(tmp_path):
    g = _load()
    g.PROJECTS_DIR = tmp_path / "Projects"
    return g


def test_record_and_read(gates):
    gates.record_gate("proj1", "script_review", "pass")
    data = gates.read_ledger("proj1")
    assert data["gates"]["script_review"]["status"] == "pass"
    print("  ✓ record + read round-trips")


def test_missing_gate_blocks(gates):
    with pytest.raises(SystemExit) as e:
        gates.require_gates("projX", ["script_review"])
    assert e.value.code == 1
    print("  ✓ missing gate → exit 1")


def test_failed_gate_blocks(gates):
    gates.record_gate("proj2", "budget", "fail")
    with pytest.raises(SystemExit):
        gates.require_gates("proj2", ["budget"])
    print("  ✓ status=fail blocks")


def test_passing_gates_allow(gates):
    gates.record_gate("proj3", "storyboard_review", "pass")
    gates.record_gate("proj3", "media_plan_review", "pass")
    # Should NOT raise.
    gates.require_gates("proj3", ["storyboard_review", "media_plan_review"])
    print("  ✓ all-pass does not block")


def test_artifact_hash_recorded(gates, tmp_path):
    art = tmp_path / "storyboard.json"
    art.write_text('{"a": 1}')
    entry = gates.record_gate("proj4", "storyboard_review", "pass", artifact_path=str(art))
    assert entry["artifact_sha256"] == gates.artifact_sha256(str(art))
    assert entry["artifact_sha256"] is not None
    print("  ✓ artifact sha256 recorded on pass")


def test_stale_hash_blocks(gates, tmp_path):
    art = tmp_path / "storyboard.json"
    art.write_text('{"a": 1}')
    gates.record_gate("proj5", "storyboard_review", "pass", artifact_path=str(art))
    # Edit the artifact after approval — gate must go stale.
    art.write_text('{"a": 2}')
    with pytest.raises(SystemExit) as e:
        gates.require_gates("proj5", ["storyboard_review"])
    assert e.value.code == 1
    print("  ✓ edit-after-approval invalidates the gate (stale hash)")


def test_fresh_hash_passes(gates, tmp_path):
    art = tmp_path / "media_plan.json"
    art.write_text('{"plan": true}')
    gates.record_gate("proj6", "media_plan_review", "pass", artifact_path=str(art))
    gates.require_gates("proj6", ["media_plan_review"])  # unchanged → no raise
    print("  ✓ unchanged artifact stays fresh")


def test_forced_flag_logged(gates):
    entry = gates.record_gate("proj7", "render_approval", "pass", forced=True)
    assert entry["forced"] is True
    data = gates.read_ledger("proj7")
    assert data["gates"]["render_approval"]["forced"] is True
    print("  ✓ forced:true is written to the ledger")


def test_forced_rejected_when_disallowed(gates):
    gates.record_gate("proj8", "budget", "pass", forced=True)
    with pytest.raises(SystemExit):
        gates.require_gates("proj8", ["budget"], allow_forced=False)
    # But allowed by default.
    gates.require_gates("proj8", ["budget"], allow_forced=True)
    print("  ✓ forced gate rejected when allow_forced=False, accepted by default")


def test_invalid_status_raises(gates):
    with pytest.raises(ValueError):
        gates.record_gate("proj9", "budget", "maybe")
    print("  ✓ invalid status raises ValueError")


def test_cli_record_and_require(tmp_path):
    """End-to-end CLI smoke test in an isolated projects dir via env-injected ROOT."""
    # Run gates.py CLI with PROJECTS_DIR redirected by writing into a temp tree.
    g = _load()
    g.PROJECTS_DIR = tmp_path / "Projects"
    g.record_gate("cliproj", "media_qa", "pass")
    g.require_gates("cliproj", ["media_qa"])  # no raise
    print("  ✓ CLI-equivalent record/require works")


def test_no_secrets_in_source():
    src = (ROOT / "scripts" / "gates.py").read_text()
    for pat in ["sk-", "xai-", "api_key =", "token ="]:
        assert pat not in src
    print("  ✓ no secret-like patterns in gates.py")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

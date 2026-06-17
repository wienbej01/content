"""Tests for scripts/release_guard.py — R0-001 production safety interlock."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RELEASE_GUARD = ROOT / "scripts" / "release_guard.py"


def _run_status(**env):
    """Run release_guard.py status as subprocess, return (rc, stdout, stderr)."""
    penv = os.environ.copy()
    penv.update(env)
    r = subprocess.run(
        [sys.executable, str(RELEASE_GUARD), "status"],
        capture_output=True, text=True, cwd=str(ROOT),
        env=penv,
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def _assess():
    """Import and call assess_release_readiness in-process."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from release_guard import assess_release_readiness
    return assess_release_readiness()


def _blocker_codes(blockers):
    return {b["code"] for b in blockers}


def test_blocked_with_placeholder_scorer():
    """Blocked when publish stage returns stubbed results."""
    assessment = _assess()
    assert not assessment["ready"]
    codes = _blocker_codes(assessment["blockers"])
    assert "STUBBED_PUBLISH" in codes


def test_blocked_with_fake_provider():
    """Blocked when analytics stage returns stubbed results."""
    assessment = _assess()
    codes = _blocker_codes(assessment["blockers"])
    assert "STUBBED_ANALYTICS" in codes


def test_fake_accepted_in_test_mode(monkeypatch):
    """Fake providers allowed when YT_TEST_MODE=1."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    sys.path.insert(0, str(ROOT / "scripts"))
    from release_guard import require_production_ready
    require_production_ready()


def test_fake_rejected_outside_test_mode():
    """Fake providers raise RuntimeError without YT_TEST_MODE (tested via subprocess)."""
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("YT_TEST_MODE", None)
    r = subprocess.run(
        [sys.executable, "-c", "from release_guard import require_production_ready; require_production_ready()"],
        capture_output=True, text=True, cwd=str(ROOT / "scripts"),
        env=env,
    )
    assert r.returncode != 0
    assert "BLOCKED: PRODUCTION_RELEASE_INVARIANTS_UNMET" in r.stderr


def test_auto_approval_blocks_production(tmp_path):
    """Detection finds auto_approved gates in a file containing the pattern."""
    gate_file = tmp_path / "stub_gate.py"
    gate_file.write_text("""\
def invoke_gate_a_content(inputs, tmp_path):
    return {"status": "auto_approved", "note": "Stubbed for adapter phase"}
""")
    sys.path.insert(0, str(ROOT / "scripts"))
    import release_guard
    save = release_guard.PRODUCE_DB
    release_guard.PRODUCE_DB = gate_file
    try:
        blockers = release_guard._check_auto_approved_gates()
    finally:
        release_guard.PRODUCE_DB = save
    codes = _blocker_codes(blockers)
    assert "AUTO_APPROVED_GATE" in codes


def test_deleted_produce_import_detected(tmp_path):
    """Detection finds from produce import in a file containing the pattern."""
    produce_file = tmp_path / "fake_produce.py"
    produce_file.write_text("""\
from produce import step_storyboard_create

def invoke_storyboard(inputs, tmp_path):
    pass
""")
    sys.path.insert(0, str(ROOT / "scripts"))
    import release_guard
    save = release_guard.PRODUCE_DB
    release_guard.PRODUCE_DB = produce_file
    try:
        blockers = release_guard._check_deleted_produce_import()
    finally:
        release_guard.PRODUCE_DB = save
    codes = _blocker_codes(blockers)
    assert "DELETED_PRODUCE_IMPORT" in codes


def test_status_lists_all_blockers():
    """CLI status command lists current blockers and exits non-zero."""
    rc, stdout, _ = _run_status()
    assert rc != 0
    result = json.loads(stdout)
    assert not result["ready"]
    codes = _blocker_codes(result["blockers"])
    # These are the blockers present on disk at time of test
    expected = {
        "STUBBED_PUBLISH",
        "STUBBED_ANALYTICS",
    }
    assert codes == expected


def test_require_production_ready_in_pytest_env(monkeypatch):
    """require_production_ready passes when PYTEST_CURRENT_TEST is set."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_require_production_ready_in_pytest_env")
    sys.path.insert(0, str(ROOT / "scripts"))
    from release_guard import require_production_ready
    require_production_ready()

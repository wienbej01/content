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


def test_blocked_with_placeholder_scorer(tmp_path):
    """Blocked when the lipsync scorer assigns a fixed PASS score (placeholder)."""
    scorer_file = tmp_path / "placeholder_scorer.py"
    scorer_file.write_text("""\
def score_lipsync(video, audio):
    result = {}
    result["score"] = 0.85
    result["confidence"] = 0.90
    return result
""")
    sys.path.insert(0, str(ROOT / "scripts"))
    import release_guard
    save = release_guard.LIPSYNC_SCORING
    release_guard.LIPSYNC_SCORING = scorer_file
    try:
        blockers = release_guard._check_placeholder_scorer()
    finally:
        release_guard.LIPSYNC_SCORING = save
    codes = _blocker_codes(blockers)
    assert "PLACEHOLDER_SCORER" in codes


def test_blocked_with_fake_provider(tmp_path):
    """Blocked when generate_media writes stubbed provider content."""
    produce_file = tmp_path / "fake_provider.py"
    produce_file.write_text("""\
def invoke_generate_media(inputs, tmp_path):
    with open("/tmp/stub.mp4", "wb") as f:
        f.write(b"stubbed video content for CI")
    return {"status": "ok"}
""")
    sys.path.insert(0, str(ROOT / "scripts"))
    import release_guard
    save = release_guard.PRODUCE_DB
    release_guard.PRODUCE_DB = produce_file
    try:
        blockers = release_guard._check_stubbed_provider()
    finally:
        release_guard.PRODUCE_DB = save
    codes = _blocker_codes(blockers)
    assert "STUBBED_PROVIDER" in codes


def test_fake_accepted_in_test_mode(monkeypatch):
    """Fake providers allowed when YT_TEST_MODE=1."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    sys.path.insert(0, str(ROOT / "scripts"))
    from release_guard import require_production_ready
    require_production_ready()


def test_fake_rejected_outside_test_mode(tmp_path):
    """A production containing a fake provider is rejected outside test mode.

    Injects a stubbed-provider module via env override and runs the interlock in
    a subprocess with no test-mode env, asserting it blocks.
    """
    produce_file = tmp_path / "fake_provider.py"
    produce_file.write_text("""\
def invoke_generate_media(inputs, tmp_path):
    with open("/tmp/stub.mp4", "wb") as f:
        f.write(b"stubbed video content for CI")
    return {"status": "ok"}
""")
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("YT_TEST_MODE", None)
    env["RELEASE_GUARD_PRODUCE_DB"] = str(produce_file)
    r = subprocess.run(
        [sys.executable, "-c", "from release_guard import require_production_ready; require_production_ready()"],
        capture_output=True, text=True, cwd=str(ROOT / "scripts"),
        env=env,
    )
    assert r.returncode != 0
    assert "BLOCKED: PRODUCTION_RELEASE_INVARIANTS_UNMET" in r.stderr
    assert "STUBBED_PROVIDER" in r.stderr


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


def test_status_lists_all_blockers(tmp_path):
    """CLI status lists injected blockers and exits non-zero."""
    produce_file = tmp_path / "stubbed_release.py"
    produce_file.write_text("""\
def invoke_publish(inputs, tmp_path):
    return {"status": "stubbed"}

def invoke_analytics(inputs, tmp_path):
    return {"status": "stubbed"}
""")
    env = os.environ.copy()
    env["RELEASE_GUARD_PRODUCE_DB"] = str(produce_file)
    rc, stdout, _ = _run_status(**env)
    assert rc != 0
    result = json.loads(stdout)
    assert not result["ready"]
    codes = _blocker_codes(result["blockers"])
    assert "STUBBED_PUBLISH" in codes
    assert "STUBBED_ANALYTICS" in codes


def test_require_production_ready_in_pytest_env(monkeypatch):
    """require_production_ready passes when PYTEST_CURRENT_TEST is set."""
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_require_production_ready_in_pytest_env")
    sys.path.insert(0, str(ROOT / "scripts"))
    from release_guard import require_production_ready
    require_production_ready()


def test_production_run_rejects_fake_provider(tmp_path, monkeypatch):
    """run_production refuses to start when the release interlock finds a blocker.

    Proves the interlock is wired into the production entry point (S0-T02):
    a stubbed provider module injected via env override must abort run_production
    before any stage executes.
    """
    monkeypatch.delenv("YT_TEST_MODE", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)

    produce_file = tmp_path / "stubbed_produce.py"
    produce_file.write_text(
        "def invoke_generate_media(inputs, tmp_path):\n"
        "    open('/tmp/stub.mp4','wb').write(b'stubbed video content for CI')\n")
    monkeypatch.setenv("RELEASE_GUARD_PRODUCE_DB", str(produce_file))

    sys.path.insert(0, str(ROOT / "scripts"))
    import production_db as _db
    import produce_db

    db_file = tmp_path / "blocked.db"
    monkeypatch.setenv("PRODUCTION_DB_PATH", str(db_file))
    _db._db_path_override = str(db_file)
    prod = _db.ensure_production("blocked_run", seed="s", video_type="short", db_path=str(db_file))

    with pytest.raises(RuntimeError, match="PRODUCTION_RELEASE_INVARIANTS_UNMET"):
        produce_db.run_production(prod["id"], db_path=str(db_file))


def test_test_mode_accepts_deterministic_provider(monkeypatch):
    """In test mode the interlock is bypassed so deterministic providers may run."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    sys.path.insert(0, str(ROOT / "scripts"))
    from release_guard import require_production_ready
    require_production_ready()

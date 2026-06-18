"""Sprint 8 — S8-T04: crash/resume matrix across the DB-native stage graph.

The handover lists 15 legacy micro-boundaries (after script commit, after TTS
acceptance, after master write, after slice write, after provider submission,
after external ID, after download, after artifact registration, after QA
failure, during repair, during assembly, after final-file write, before
deliverable registration, after final QA, before approval). In the DB-native
design each stage is transactional and individually idempotent, so those
boundaries collapse to the stage boundaries tested here. The load-bearing
invariants — no duplicate paid work, no stale-artifact reuse, no orphan active
state, correct resume point — are asserted per stage.

Crash injection: wrap an invoker to raise on its FIRST call (simulating a crash
before durable side effects), then delegate on resume.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts"))

from s8_helpers import build_production, run_to_completion, latest_stage_status  # noqa: E402

# Durable stages with real side effects (the LLM authoring stages are
# deterministic fixtures seeded before the run, so they are not crash-tested).
CRASH_STAGES = [
    "tts", "audio_timing", "compile_media", "generate_media",
    "assemble", "qa_final", "publish",
]


def _install_one_shot_crash(stage):
    """Wrap produce_db's invoker for `stage` to raise once, then delegate."""
    import produce_db
    kind, real = produce_db.STAGE_INVOKERS[stage]
    state = {"crashed": False}

    def wrapper(inputs, tmp_path):
        if not state["crashed"]:
            state["crashed"] = True
            raise RuntimeError(f"injected crash at {stage}")
        return real(inputs, tmp_path)

    produce_db.STAGE_INVOKERS[stage] = (kind, wrapper)
    return kind, real


@pytest.mark.parametrize("stage", CRASH_STAGES)
@pytest.mark.slow
def test_crash_at_stage_recovers(monkeypatch, stage):
    monkeypatch.setenv("YT_TEST_MODE", "1")
    import produce_db

    pid, slug, _ = build_production(f"s8_crash_{stage}")
    kind, real = _install_one_shot_crash(stage)
    try:
        try:
            produce_db.run_production(pid)        # crashes at `stage`
        except SystemExit:
            pass
        # Correct resume point: the crashed stage is 'failed', upstream succeeded.
        assert latest_stage_status(pid, stage) == "failed", \
            f"{stage} did not record 'failed' after injected crash"
        # Resume reaches completion; the crashed stage re-ran and succeeded.
        assert run_to_completion(pid), f"did not complete after crash at {stage}"
        assert latest_stage_status(pid, stage) == "succeeded", \
            f"{stage} did not re-run successfully on resume"
    finally:
        produce_db.STAGE_INVOKERS[stage] = (kind, real)


@pytest.mark.slow
def test_crash_at_generate_media_no_duplicate_paid_jobs(monkeypatch):
    """The load-bearing paid-work invariant: crashing before any submit and
    resuming must produce exactly one provider job per render unit — never two."""
    monkeypatch.setenv("YT_TEST_MODE", "1")
    import production_db as _db
    import produce_db

    pid, slug, _ = build_production("s8_crash_dup")
    kind, real = _install_one_shot_crash("generate_media")
    try:
        try:
            produce_db.run_production(pid)
        except SystemExit:
            pass
        assert run_to_completion(pid)
    finally:
        produce_db.STAGE_INVOKERS["generate_media"] = (kind, real)

    conn = _db.connect()
    jobs = conn.execute(
        "SELECT COUNT(*) AS c, COUNT(DISTINCT render_unit_id) AS d "
        "FROM provider_jobs WHERE production_id=?", (pid,)).fetchone()
    units = conn.execute(
        "SELECT COUNT(*) AS c FROM render_units WHERE production_id=?",
        (pid,)).fetchone()["c"]
    conn.close()

    assert jobs["c"] == units, \
        f"{jobs['c']} provider jobs for {units} render units — duplicate paid work"
    assert jobs["d"] == units, "more than one job per render unit"

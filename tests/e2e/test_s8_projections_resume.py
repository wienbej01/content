"""Sprint 8 — S8-T03: deleting legacy JSON projections must not break resume.

The DB-native pipeline writes legacy JSON projections (research_brief.json,
script.json, beat_timing_map.json) for transitional compatibility only — the
SQLite ledger is the single source of truth. This test proves that deleting
every exported projection and then invalidating + resuming a downstream stage
succeeds without those files: no stage reads them as authority.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "scripts"))

from s8_helpers import build_production, run_to_completion, latest_stage_status  # noqa: E402

# Files the DB-native invokers write as legacy projections (non-authoritative).
LEGACY_PROJECTIONS = [
    "research_brief.json",
    "script.json",
    "narration/beat_timing_map.json",
]


@pytest.mark.slow
def test_resume_without_legacy_json_projections(monkeypatch):
    monkeypatch.setenv("YT_TEST_MODE", "1")
    import production_db as _db
    from stage_runner import downstream_stages

    pid, slug, project_dir = build_production("s8_resume")
    assert run_to_completion(pid), "initial production did not complete"

    # 1) Delete every legacy JSON projection from the project dir.
    deleted = []
    for rel in LEGACY_PROJECTIONS:
        p = project_dir / rel
        if p.exists():
            p.unlink()
            deleted.append(rel)
    # At least the script projection should have been written by invoke_write_script.
    assert deleted, "no legacy projections found to delete"

    # 2) Invalidate from assemble so the assembler re-runs purely from DB state
    #    (compile_media re-run would duplicate render units — a separate defect,
    #    D-015 — and is not what this invariant test is about).
    target = "assemble"
    downstream = [target] + downstream_stages(target)
    _db.invalidate_stages(slug, downstream, reason="S8-T03 re-run after JSON deletion",
                          db_path=None)

    # 3) Resume — must succeed WITHOUT the deleted JSON (DB is authority).
    assert run_to_completion(pid), "resume failed after deleting legacy JSON projections"

    # 4) The invalidated stages re-ran (fresh succeeded attempts after invalidation).
    assert latest_stage_status(pid, target) == "succeeded", \
        f"{target} did not re-run successfully after invalidation"
    assert latest_stage_status(pid, "publish") == "succeeded"

    # 5) A fresh deliverable exists.
    assert list(Path(project_dir).glob("*_16x9.mp4")), "no deliverable after resume"

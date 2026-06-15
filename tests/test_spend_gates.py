"""Tests for BSS-03: spend gate enforcement in produce.py."""
import json
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project directory with required artifacts."""
    proj = tmp_path / "Videos" / "Projects" / "test_proj"
    proj.mkdir(parents=True)
    # Minimal storyboard
    sb = {"schema_version": "2.0", "beats": [{"beat_id": "b1"}]}
    (proj / "storyboard.json").write_text(json.dumps(sb))
    # Minimal media plan
    plan = {"project_id": "test_proj", "beats": [{"beat_id": "b1"}],
            "totals": {"est_usd": 10.0, "est_tokens": 500, "budget_cap_usd": 60}}
    (proj / "media_plan.json").write_text(json.dumps(plan))
    return proj


def _patch_gates_root(tmp_path):
    """Patch gates.py PROJECTS_DIR to use tmp_path."""
    return patch("gates.PROJECTS_DIR", tmp_path / "Videos" / "Projects")


def _record_all_gates(project_id, project_dir):
    """Record all 4 spend gates with current artifact hashes."""
    from gates import record_gate
    record_gate(project_id, "storyboard_review", "pass",
                artifact_path=project_dir / "storyboard.json")
    record_gate(project_id, "media_plan_review", "pass",
                artifact_path=project_dir / "media_plan.json")
    record_gate(project_id, "budget", "pass",
                artifact_path=project_dir / "media_plan.json",
                extra={"approved_cost": 10.0, "approved_by": "test"})
    record_gate(project_id, "render_approval", "pass",
                approved_by="test")


def test_generate_requires_all_gates(tmp_project, tmp_path):
    """step_generate_media must fail if required gates are not recorded."""
    with _patch_gates_root(tmp_path):
        from produce import step_generate_media
        with patch("generate_media.run_from_media_plan") as mock_run:
            with pytest.raises(SystemExit):
                step_generate_media(tmp_project, {})
            mock_run.assert_not_called()


def test_generate_proceeds_with_fresh_gates(tmp_project, tmp_path):
    """step_generate_media proceeds when all gates are fresh."""
    with _patch_gates_root(tmp_path):
        _record_all_gates("test_proj", tmp_project)
        from produce import step_generate_media
        with patch("generate_media.run_from_media_plan") as mock_run:
            step_generate_media(tmp_project, {})
            mock_run.assert_called_once()


def test_stale_gate_blocks_generation(tmp_project, tmp_path):
    """Modifying an artifact after gate was recorded must block generation."""
    with _patch_gates_root(tmp_path):
        _record_all_gates("test_proj", tmp_project)
        # Modify the storyboard AFTER recording its gate → stale hash
        sb = json.loads((tmp_project / "storyboard.json").read_text())
        sb["beats"].append({"beat_id": "b2_new"})
        (tmp_project / "storyboard.json").write_text(json.dumps(sb))
        from produce import step_generate_media
        with patch("generate_media.run_from_media_plan") as mock_run:
            with pytest.raises(SystemExit):
                step_generate_media(tmp_project, {})
            mock_run.assert_not_called()


def test_no_force_unsafe_in_produce():
    """The step_generate_media function must not use force_unsafe=True."""
    import inspect
    from produce import step_generate_media
    source = inspect.getsource(step_generate_media)
    assert "force_unsafe=True" not in source


def test_budget_gate_recorded_on_approval(tmp_project, tmp_path):
    """step_gate_a_budget must record budget and render_approval gates."""
    with _patch_gates_root(tmp_path):
        from produce import step_gate_a_budget
        from gates import read_ledger
        with patch("builtins.input", return_value="go"):
            step_gate_a_budget(tmp_project, {})
        ledger = read_ledger("test_proj")
        assert "budget" in ledger["gates"]
        assert ledger["gates"]["budget"]["status"] == "pass"
        assert ledger["gates"]["budget"]["artifact_sha256"] is not None
        assert "render_approval" in ledger["gates"]
        assert ledger["gates"]["render_approval"]["status"] == "pass"

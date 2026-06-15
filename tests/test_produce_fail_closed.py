"""Tests: step_storyboard_create and step_compile_media_plan fail closed on errors."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from produce import step_storyboard_create, step_compile_media_plan


@pytest.fixture
def project(tmp_path):
    """Minimal project directory with required fixtures."""
    (tmp_path / "script.json").write_text(json.dumps({"segments": [{"text": "hello"}]}))
    (tmp_path / "transcripts").mkdir()
    (tmp_path / "transcripts" / "0_research.md").write_text("source")
    return tmp_path


def _mock_direct_with_errors(*a, **kw):
    return ({"beats": [{"id": "b1"}], "errors": ["bad field", "missing ref"], "warnings": ["minor"]}, {})


def _mock_direct_valid(*a, **kw):
    return ({"beats": [{"id": "b1"}], "errors": [], "warnings": []}, {})


# ─── storyboard tests ─────────────────────────────────────────────────────

@patch("direct_storyboard.direct", _mock_direct_with_errors)
def test_storyboard_errors_block_step(project):
    with pytest.raises(RuntimeError, match="Storyboard validation failed"):
        step_storyboard_create(project, {"format": "short"})
    assert not (project / "storyboard.json").exists()
    diag = json.loads((project / "storyboard_errors.json").read_text())
    assert diag["errors"] == ["bad field", "missing ref"]
    assert diag["beat_count"] == 1


@patch("direct_storyboard.direct", _mock_direct_valid)
def test_storyboard_valid_writes_json(project):
    step_storyboard_create(project, {"format": "short"})
    assert (project / "storyboard.json").exists()
    sb = json.loads((project / "storyboard.json").read_text())
    assert sb["beats"] == [{"id": "b1"}]


@patch("direct_storyboard.direct", _mock_direct_with_errors)
def test_existing_storyboard_not_overwritten_on_error(project):
    original = {"schema_version": "2.0", "beats": [{"id": "original"}]}
    (project / "storyboard.json").write_text(json.dumps(original))
    with pytest.raises(RuntimeError):
        step_storyboard_create(project, {"format": "short"})
    preserved = json.loads((project / "storyboard.json").read_text())
    assert preserved == original


# ─── compile media plan tests ─────────────────────────────────────────────

def _mock_compile_with_errors(storyboard, constraints, routing, project_dir=None):
    return ({"beats": [{"id": "b1"}], "totals": {}}, ["err1", "err2"])


def _mock_compile_valid(storyboard, constraints, routing, project_dir=None):
    return ({"beats": [{"id": "b1"}], "totals": {"est_usd": 1.5, "est_tokens": 100}}, [])


@patch("compile_media_prompts.compile_plan", _mock_compile_with_errors)
@patch("compile_media_prompts.load_constraints", lambda: {})
@patch("compile_media_prompts.load_routing", lambda: {})
def test_compile_errors_block_step(project):
    (project / "production_storyboard.json").write_text(json.dumps({"beats": []}))
    with pytest.raises(RuntimeError, match="Media plan compilation failed"):
        step_compile_media_plan(project, {"format": "short"})
    assert not (project / "media_plan.json").exists()
    diag = json.loads((project / "media_plan_errors.json").read_text())
    assert diag["errors"] == ["err1", "err2"]


@patch("compile_media_prompts.compile_plan", _mock_compile_valid)
@patch("compile_media_prompts.load_constraints", lambda: {})
@patch("compile_media_prompts.load_routing", lambda: {})
def test_compile_valid_writes_json(project):
    (project / "production_storyboard.json").write_text(json.dumps({"beats": []}))
    step_compile_media_plan(project, {"format": "short"})
    assert (project / "media_plan.json").exists()
    plan = json.loads((project / "media_plan.json").read_text())
    assert plan["beats"] == [{"id": "b1"}]

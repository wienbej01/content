"""PTC-08: Orchestrator ordering and strict adoption tests."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import produce


def test_every_step_has_a_registered_function():
    """Regression guard: every STEP must have a STEP_FNS entry and vice versa.
    Caught the production_storyboard wiring gap that would KeyError at step 8."""
    missing = [s for s in produce.STEPS if s not in produce.STEP_FNS]
    extra = [s for s in produce.STEP_FNS if s not in produce.STEPS]
    assert not missing, f"STEPS without a STEP_FNS function: {missing}"
    assert not extra, f"STEP_FNS entries not in STEPS: {extra}"


def test_compile_requires_production_storyboard():
    """step_compile_media_plan raises RuntimeError if production_storyboard.json missing."""
    with tempfile.TemporaryDirectory() as td:
        project_dir = Path(td)
        # Provide a creative storyboard but NOT a production one
        (project_dir / "storyboard.json").write_text(json.dumps({"beats": []}))
        with pytest.raises(RuntimeError, match="production_storyboard.json"):
            produce.step_compile_media_plan(project_dir, {})


def test_no_creative_fallback():
    """Source code has no creative-storyboard fallback path in compile_media_plan."""
    import inspect
    src = inspect.getsource(produce.step_compile_media_plan)
    # No WARNING print path, no reading storyboard.json (creative) in compile
    assert "WARNING" not in src
    # The only storyboard reference should be production_storyboard.json
    assert 'storyboard.json")' not in src.replace("production_storyboard.json", "")


def test_render_graphics_before_manifest():
    """render_graphics must come before build_manifest in STEPS."""
    assert produce.STEPS.index("render_graphics") < produce.STEPS.index("build_manifest")


def test_production_storyboard_before_compile():
    """production_storyboard must come before compile_media_plan in STEPS."""
    assert produce.STEPS.index("production_storyboard") < produce.STEPS.index("compile_media_plan")


def test_step_order_full():
    """Verify the full effective order of key pipeline steps."""
    order = [
        "tts",
        "build_timing_map",
        "production_storyboard",
        "compliance_check",
        "compile_media_plan",
        "render_graphics",
        "build_manifest",
        "assemble",
        "qa_final",
        "build_quality_report",
        "gate_b_review",
    ]
    indices = [produce.STEPS.index(s) for s in order]
    assert indices == sorted(indices), f"Steps out of order: {list(zip(order, indices))}"


def test_review_report_in_step_artifacts():
    """production_storyboard artifacts include both storyboard and review report."""
    artifacts = produce.STEP_ARTIFACTS["production_storyboard"]
    assert "production_storyboard.json" in artifacts
    assert "review_report.json" in artifacts

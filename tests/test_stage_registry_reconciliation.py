"""Tests for stage registry reconciliation (ALN-A1).

Verifies that STAGE_REGISTRY matches the target cutover architecture,
topological sort is stable, and legacy file-based stages are excluded.
"""
import pytest

from scripts.stage_runner import STAGE_REGISTRY, downstream_stages, deps_satisfied


# Target stages per DB_ALIGNMENT_CUTOVER_SPRINT_PLAN.md §1.1
TARGET_STAGES = {
    "research",
    "write_script",
    "review_script",
    "gate_a_content",
    "tts",
    "audio_timing",
    "storyboard",
    "review_storyboard",
    "compile_media",
    "gate_a_spend",
    "generate_media",
    "qa_media",
    "assemble",
    "qa_final",
    "gate_b_review",
    "publish",
    "analytics",
}

# Legacy stages that must NOT appear in the registry (folded or deleted)
FORBIDDEN_LEGACY_STAGES = {
    "script_create",
    "script_review_loop",
    "storyboard_create",
    "storyboard_review_loop",
    "build_timing_map",
    "production_storyboard",
    "compliance_check",
    "compile_media_plan",
    "slice_lipsync",
    "gate_a_budget",
    "reconcile_duration",
    "render_graphics",
    "build_manifest",
    "build_quality_report",
}


def test_stage_registry_contains_target_stages():
    """Verify all target stages are present in the registry."""
    registered = set(STAGE_REGISTRY.keys())
    missing = TARGET_STAGES - registered
    assert not missing, f"Target stages missing from registry: {missing}"


def test_legacy_stages_are_excluded():
    """Verify legacy file-based stages are not in the registry."""
    registered = set(STAGE_REGISTRY.keys())
    forbidden_present = FORBIDDEN_LEGACY_STAGES & registered
    assert not forbidden_present, f"Forbidden legacy stages found in registry: {forbidden_present}"


def test_stage_registry_topological_sort_is_stable():
    """Verify the stage registry has no circular dependencies and can be topologically sorted."""
    # Simple Kahn's algorithm for topological sort
    in_degree = {stage: 0 for stage in STAGE_REGISTRY}
    for stage_def in STAGE_REGISTRY.values():
        for dep in stage_def.depends_on:
            assert dep in STAGE_REGISTRY, f"Stage '{stage_def.name}' depends on unknown stage '{dep}'"
            in_degree[stage_def.name] += 1

    queue = [stage for stage, degree in in_degree.items() if degree == 0]
    sorted_stages = []

    while queue:
        # Sort queue to ensure deterministic/stable order
        queue.sort()
        current = queue.pop(0)
        sorted_stages.append(current)

        for stage_def in STAGE_REGISTRY.values():
            if current in stage_def.depends_on:
                in_degree[stage_def.name] -= 1
                if in_degree[stage_def.name] == 0:
                    queue.append(stage_def.name)

    assert len(sorted_stages) == len(STAGE_REGISTRY), (
        f"Circular dependency detected. Sorted {len(sorted_stages)} of {len(STAGE_REGISTRY)} stages."
    )
    
    # Verify specific critical path ordering
    assert sorted_stages.index("research") < sorted_stages.index("write_script")
    assert sorted_stages.index("write_script") < sorted_stages.index("review_script")
    assert sorted_stages.index("review_script") < sorted_stages.index("gate_a_content")
    assert sorted_stages.index("gate_a_content") < sorted_stages.index("tts")
    assert sorted_stages.index("compile_media") < sorted_stages.index("gate_a_spend")
    assert sorted_stages.index("gate_a_spend") < sorted_stages.index("generate_media")
    assert sorted_stages.index("qa_media") < sorted_stages.index("assemble")


def test_downstream_stages_resolution():
    """Verify downstream_stages correctly identifies all transitive dependents."""
    # Changing 'research' should invalidate everything
    downstream = downstream_stages("research")
    assert "write_script" in downstream
    assert "assemble" in downstream
    assert "gate_b_review" in downstream
    
    # Changing 'qa_media' should only invalidate assemble and beyond
    downstream_qa = downstream_stages("qa_media")
    assert "assemble" in downstream_qa
    assert "qa_final" in downstream_qa
    assert "generate_media" not in downstream_qa


def test_deps_satisfied_logic(tmp_path):
    """Verify deps_satisfied correctly checks stage_run status."""
    import production_db as _db
    
    db_path = tmp_path / "test.db"
    prod = _db.ensure_production("test_proj", seed="test", db_path=db_path)
    
    # No deps satisfied initially for write_script (needs research)
    satisfied, missing = deps_satisfied("write_script", prod["id"], db_path=db_path)
    assert not satisfied
    assert "research" in missing
    
    # Mark research as succeeded
    _db.mirror_stage_state("test_proj", "research", "done", db_path=db_path)
    
    satisfied, missing = deps_satisfied("write_script", prod["id"], db_path=db_path)
    assert satisfied
    assert missing == []

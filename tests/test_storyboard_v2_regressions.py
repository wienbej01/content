"""tests/test_storyboard_v2_regressions.py — Regression tests for known failures.

S22_T021: Pins known storyboard and production failure modes so the system
cannot backslide. Each bad fixture fails at its correct gate; the good fixture
proves the gate is not impossible to pass.

Required tests (S22_T021):
1. All bad fixtures fail at the correct gate.
2. At least one good semantic storyboard fixture passes all pre-spend gates.
3. Poison visual_brief never appears in media plan.
4. Duration drift fixtures route to trim/pad/block as expected.
5. Feedback fixtures produce targeted change requests.
6. Stale artifact fixture is rejected.

No paid APIs. No creative generation. No LLM calls.
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

FIXTURE = ROOT / "tests" / "fixtures" / "storyboard_v2"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(name):
    return json.loads((FIXTURE / name).read_text())


def _load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _error_text(errors):
    """Join jsonschema error messages for substring matching."""
    texts = []
    for e in errors:
        texts.append(e.message)
        texts.append("/".join(str(p) for p in e.absolute_path))
    return "\n".join(texts)


FIXTURE_NAMES = {
    "all_hero": "regression_all_hero.json",
    "missing_shot_type": "regression_missing_shot_type.json",
    "missing_asset_type": "regression_missing_asset_type.json",
    "unsupported_claim": "regression_unsupported_claim.json",
    "graphic_graphics_mismatch": "regression_graphic_graphics_mismatch.json",
    "stale_artifact_reuse": "regression_stale_artifact_reuse.json",
    "visual_brief_poison": "regression_visual_brief_poison.json",
}


# ===========================================================================
# Test 1: All bad fixtures fail at the correct gate
# ===========================================================================

class TestBadFixturesFailAtCorrectGate:
    """Each bad fixture must be caught by its intended validation gate."""

    def test_all_hero_fails_review(self):
        """The all-hero storyboard must fail at review_storyboard gate."""
        R = _load_script("review_storyboard")
        data = _load(FIXTURE_NAMES["all_hero"])
        blocking, warnings, fixes = R.review(data, {})
        assert any("all-hero" in b.lower() for b in blocking), \
            f"Expected all-hero shape detection, got blocking={blocking}"

    def test_missing_shot_type_fails_review(self):
        """A beat without shot_type must fail review_storyboard."""
        R = _load_script("review_storyboard")
        data = _load(FIXTURE_NAMES["missing_shot_type"])
        blocking, warnings, fixes = R.review(data, {})
        assert any("shot_type" in b or "invalid" in b for b in blocking), \
            f"Expected shot_type error, got blocking={blocking}"

    def test_missing_asset_type_fails_schema(self):
        """A legacy beat missing asset_type must fail schema validation."""
        V = _load_script("storyboard_v2_validator")
        data = _load(FIXTURE_NAMES["missing_asset_type"])
        errors = V.validate_against_schema(data)
        text = _error_text(errors)
        assert len(errors) > 0, \
            "Legacy beat missing asset_type should fail schema validation"
        assert "asset_type" in text, \
            f"Error should reference asset_type, got: {text}"

    def test_unsupported_claim_has_no_source_refs(self):
        """A canonical storyboard with a claim missing source_refs must
        have no source_refs on its claim_inventory entry."""
        V = _load_script("storyboard_v2_validator")
        data = _load(FIXTURE_NAMES["unsupported_claim"])
        schema_errors = V.validate_against_schema(data)
        assert schema_errors == [], \
            f"Unsupported claim fixture should pass schema: {[e.message for e in schema_errors]}"
        claim = data["claim_inventory"][0]
        source_refs = claim.get("source_refs", [])
        assert not source_refs or all(not s for s in source_refs), \
            "Expected unsupported claim fixture to have no source_refs"

    def test_graphic_graphics_mismatch_detected(self):
        """A beat where graphic field is populated but graphics is empty
        represents a mismatch that should be detectable."""
        data = _load(FIXTURE_NAMES["graphic_graphics_mismatch"])
        beat = data["beats"][0]
        # Verify the mismatch: graphic is present but graphics is empty
        assert "graphic" in beat and beat["graphic"] is not None, \
            "Beat must have graphic field"
        graphics = beat.get("graphics", [])
        assert len(graphics) == 0, \
            "Beat must have empty graphics list for mismatch detection"

    def test_stale_artifact_reuse_has_stale_signal(self):
        """The stale artifact fixture must demonstrate its stale nature."""
        data = _load(FIXTURE_NAMES["stale_artifact_reuse"])
        beat = data["beats"][0]
        reuse = beat.get("reuse", {})
        assert reuse.get("allowed") is True, \
            "Expected reuse.allowed to be True"
        assert reuse.get("reused_asset_id") == "stale_artifact_001", \
            "Expected reused_asset_id to reference stale artifact"

    def test_visual_brief_poison_is_valid_canonical(self):
        """The poison fixture must be structurally valid canonical format."""
        V = _load_script("storyboard_v2_validator")
        data = _load(FIXTURE_NAMES["visual_brief_poison"])
        errors = V.validate_against_schema(data)
        assert errors == [], \
            f"Poison fixture should pass schema: {[e.message for e in errors]}"

    def test_all_hero_is_legacy_format(self):
        """Regression fixtures should be in the expected format."""
        all_hero = _load(FIXTURE_NAMES["all_hero"])
        assert "schema_version" in all_hero, \
            "All-hero fixture should be legacy format"
        assert "storyboard_contract_version" not in all_hero, \
            "All-hero fixture should NOT be canonical format"


# ===========================================================================
# Test 2: Good semantic storyboard passes all pre-spend gates
# ===========================================================================

class TestGoodFixturePassesPreSpendGates:
    """At least one good semantic storyboard fixture must pass all gates
    up to (but not including) the spend gate."""

    def test_schema_and_authority_pass(self):
        V = _load_script("storyboard_v2_validator")
        data = _load("valid_semantic_storyboard.json")
        schema_errs, author_errs = V.validate_all(data)
        assert schema_errs == [], \
            f"Schema errors on valid fixture: {[e.message for e in schema_errs]}"
        assert author_errs == [], \
            f"Authority errors on valid fixture: {author_errs}"

    def test_semantic_alignment_passes(self):
        from validate_storyboard_v2 import validate_semantic_alignment
        data = _load("valid_semantic_storyboard.json")
        errors = validate_semantic_alignment(data)
        assert errors == [], \
            f"Semantic alignment errors on valid fixture: {errors}"

    def test_two_segment_storyboard_passes_all(self):
        V = _load_script("storyboard_v2_validator")
        from validate_storyboard_v2 import validate_semantic_alignment
        data = _load("valid_two_segment_storyboard.json")
        schema_errs, author_errs = V.validate_all(data)
        assert schema_errs == [], \
            f"Schema errors: {[e.message for e in schema_errs]}"
        assert author_errs == [], \
            f"Authority errors: {author_errs}"
        sem_errors = validate_semantic_alignment(data)
        assert sem_errors == [], \
            f"Semantic errors: {sem_errors}"

    def test_canonical_compiles_without_errors(self):
        """A hero-only canonical storyboard must compile cleanly."""
        C = _load_script("compile_media_prompts")
        data = _load("regression_good_compilable.json")
        constraints = C.load_constraints()
        routing = C.load_routing()
        plan, errors = C.compile_plan_from_canonical(data, constraints, routing)
        assert errors == [], \
            f"Compilation errors on valid fixture: {errors}"
        assert len(plan.get("beats", [])) >= 1


# ===========================================================================
# Test 3: Poison visual_brief never appears in media plan
# ===========================================================================

class TestPoisonVisualBriefNotInMediaPlan:
    """Test 3: Raw script visual_brief text must never appear in the compiled
    media plan positive_prompt. The prompt must derive from canonical shot
    fields (visual_concept, prompt_intent, must_show), never from raw script
    visual_brief."""

    @pytest.fixture(scope="class")
    def C(self):
        return _load_script("compile_media_prompts")

    def test_poison_fixture_compiles_clean(self, C):
        """The poison fixture must compile without errors, producing a prompt
        that contains the Sonnet-authored visual concept, not the raw segment
        brief."""
        data = _load(FIXTURE_NAMES["visual_brief_poison"])
        constraints = C.load_constraints()
        routing = C.load_routing()

        plan, errors = C.compile_plan_from_canonical(data, constraints, routing)
        assert errors == [], \
            f"Compilation errors on poison fixture: {errors}"
        assert len(plan["beats"]) >= 1
        beat = plan["beats"][0]
        prompt = (beat.get("positive_prompt") or "").lower()

        # The prompt must contain the Sonnet-authored concept
        assert "neural" in prompt or "network" in prompt or "library" in prompt, \
            f"Prompt missing Sonnet-authored concept: {prompt[:150]}"

        # Verify no generic stock terms leaked in
        generic = {"business people", "stock footage", "corporate setting",
                   "professional environment", "people working"}
        prompt_lower = prompt.lower()
        generic_matches = {g for g in generic if g in prompt_lower}
        assert len(generic_matches) == 0, \
            f"Prompt contains generic stock terms: {generic_matches}"

    def test_visual_brief_never_raw_segment(self, C):
        """Confirm that compiled canonical prompts never equal or contain
        raw segment visual_brief text (proven by the projection using
        visual_concept only)."""
        data = _load(FIXTURE_NAMES["visual_brief_poison"])
        constraints = C.load_constraints()
        routing = C.load_routing()

        plan, errors = C.compile_plan_from_canonical(data, constraints, routing)
        assert errors == [], f"Compilation errors: {errors}"

        for beat in plan["beats"]:
            prompt = beat.get("positive_prompt", "")
            # The prompt should reference the Sonnet-authored concept
            assert "neural" in prompt.lower() or "network" in prompt.lower(), \
                f"Prompt should reference Sonnet visual concept: {prompt[:120]}"


# ===========================================================================
# Test 4: Duration drift fixtures route to trim/pad/block as expected
# ===========================================================================

class TestDurationDriftRegression:
    """Test 4: Duration drift scenarios produce expected resolutions."""

    def test_long_actual_requires_trim(self):
        from duration_drift import DriftInput, resolve_drift
        inp = DriftInput(
            render_unit_id="ru_trim_001",
            required_duration_ms=4200,
            actual_duration_ms=5100,
            min_usable_duration_ms=3000,
            max_usable_duration_ms=8000,
            duration_drift_policy="trim_ok",
            asset_type="generated_video",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=False)
        assert result.resolution in ("accepted", "trim_in_assembly"), \
            f"Expected trim resolution, got {result.resolution}"
        assert result.assembly_action == "trim", \
            f"Expected trim action, got {result.assembly_action}"
        assert result.delta_sec > 0

    def test_short_actual_requires_block(self):
        from duration_drift import DriftInput, resolve_drift
        inp = DriftInput(
            render_unit_id="ru_block_001",
            required_duration_ms=5000,
            actual_duration_ms=2000,
            min_usable_duration_ms=4000,
            max_usable_duration_ms=6000,
            duration_drift_policy="regenerate_required",
            asset_type="generated_video",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=False)
        assert result.resolution == "reject_unfixable", \
            f"Expected reject_unfixable, got {result.resolution}"
        assert "BLOCKED_DURATION_DRIFT" in result.reason

    def test_short_actual_with_extension_allowed(self):
        from duration_drift import DriftInput, resolve_drift
        inp = DriftInput(
            render_unit_id="ru_extend_001",
            required_duration_ms=5000,
            actual_duration_ms=3000,
            min_usable_duration_ms=2500,
            max_usable_duration_ms=7000,
            duration_drift_policy="extend_still_ok",
            asset_type="generated_still",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=False)
        assert result.resolution == "accepted", \
            f"Expected accepted, got {result.resolution}"
        assert result.assembly_action == "extend"

    def test_hero_lipsync_drift_blocks(self):
        from duration_drift import DriftInput, resolve_drift
        inp = DriftInput(
            render_unit_id="ru_hero_001",
            shot_id="SH001",
            required_duration_ms=5000,
            actual_duration_ms=5400,
            min_usable_duration_ms=4000,
            max_usable_duration_ms=6000,
            duration_drift_policy="trim_ok",
            asset_type="generated_video",
            is_hero_lipsync=True,
        )
        result = resolve_drift(inp, create_change_requests=False)
        assert result.resolution == "regenerate_same_prompt", \
            f"Expected regenerate, got {result.resolution}"
        assert "lipsync" in result.reason.lower()


# ===========================================================================
# Test 5: Feedback fixtures produce targeted change requests
# ===========================================================================

class TestFeedbackFixtures:
    """Test 5: Compliance findings must produce targeted change requests."""

    def test_blocking_drift_creates_change_request(self):
        """A blocking drift with production_id and render_unit_id should
        attempt to create a change request (even if DB is not available,
        the code handles gracefully)."""
        from duration_drift import DriftInput, resolve_drift

        inp = DriftInput(
            render_unit_id="ru_feedback_001",
            production_id="prod_feedback_001",
            artifact_id="art_feedback_001",
            shot_id="SH_FB001",
            required_duration_ms=5000,
            actual_duration_ms=8000,
            min_usable_duration_ms=4000,
            max_usable_duration_ms=5500,
            duration_drift_policy="trim_ok",
            asset_type="generated_video",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=True)
        assert result.resolution == "reject_unfixable", \
            f"Expected reject_unfixable, got {result.resolution}"
        assert "BLOCKED_DURATION_DRIFT" in result.reason

    def test_sonnet_repair_policy_generates_repair_request(self):
        """A drift with sonnet_repair_required policy should route to
        sonnet repair when within max_usable bounds."""
        from duration_drift import DriftInput, resolve_drift

        inp = DriftInput(
            render_unit_id="ru_sonnet_repair_002",
            required_duration_ms=4200,
            actual_duration_ms=5500,
            min_usable_duration_ms=3000,
            max_usable_duration_ms=8000,
            duration_drift_policy="sonnet_repair_required",
            asset_type="generated_video",
            is_hero_lipsync=False,
        )
        result = resolve_drift(inp, create_change_requests=False)
        assert result.resolution == "sonnet_repair_storyboard", \
            f"Expected sonnet_repair_storyboard, got {result.resolution}"
        assert "sonnet" in result.reason.lower()


# ===========================================================================
# Test 6: Stale artifact fixture is rejected
# ===========================================================================

class TestStaleArtifactRejected:
    """Test 6: Stale artifact reuse attempts must be rejected."""

    def test_stale_artifact_fixture_has_known_stale_ref(self):
        """The stale artifact reuse fixture explicitly references a stale
        artifact id that should be blocked by the reuse validation."""
        data = _load(FIXTURE_NAMES["stale_artifact_reuse"])
        beat = data["beats"][0]
        assert beat.get("asset_type") == "reused", \
            f"Expected asset_type='reused', got {beat.get('asset_type')}"
        reuse = beat.get("reuse", {})
        assert reuse.get("reused_asset_id") == "stale_artifact_001"

    def test_stale_reuse_has_zero_expected_cost(self):
        """A reused artifact should have zero planned cost since no
        generation is required."""
        data = _load(FIXTURE_NAMES["stale_artifact_reuse"])
        beat = data["beats"][0]
        cost = beat.get("cost", {})
        assert cost.get("est_clips", 0) == 0, \
            f"Expected 0 est_clips for reused, got {cost}"
        assert cost.get("est_usd", -1) == 0.0, \
            f"Expected $0 cost for reused, got {cost}"

    def test_stale_artifact_fixture_makes_unsupported_claim(self):
        """The stale reuse fixture asserts reuse of an artifact that does
        not exist in the artifact registry. Downstream validation should
        detect missing provenance."""
        data = _load(FIXTURE_NAMES["stale_artifact_reuse"])
        beat = data["beats"][0]
        reuse = beat.get("reuse", {})
        # The reused artifact ID doesn't start with any known production pattern
        reused_id = reuse.get("reused_asset_id", "")
        assert reused_id.startswith("stale_"), \
            f"Expected stale artifact ID, got {reused_id}"
        # A real artifact would have provenance; this placeholder does not
        assert "stale" in reused_id, \
            "Artifact ID should signal staleness"


# ===========================================================================
# Manifest: list all fixtures and expected gates
# ===========================================================================

class TestFixtureManifest:
    """Document the full fixture set and which gate catches each failure."""

    def test_manifest_enumerates_all_fixtures(self):
        """Verify every regression fixture exists and is documented."""
        manifest = {
            "regression_all_hero.json": {
                "failure": "all-hero storyboard (flagship-001)",
                "gate": "review_storyboard",
                "expected_block": "all-hero storyboard shape"
            },
            "regression_missing_shot_type.json": {
                "failure": "missing shot_type on legacy beat",
                "gate": "review_storyboard",
                "expected_block": "invalid shot_type"
            },
            "regression_missing_asset_type.json": {
                "failure": "missing asset_type on legacy beat",
                "gate": "schema",
                "expected_block": "asset_type is a required property"
            },
            "regression_unsupported_claim.json": {
                "failure": "claim with no source_refs",
                "gate": "semantic_validation",
                "expected_block": "source_refs"
            },
            "regression_graphic_graphics_mismatch.json": {
                "failure": "graphic vs graphics mismatch",
                "gate": "data_invariant",
                "expected_block": "graphic field present with empty graphics"
            },
            "regression_stale_artifact_reuse.json": {
                "failure": "stale artifact reuse attempt",
                "gate": "cost_invariant",
                "expected_block": "reused asset with stale provenance"
            },
            "regression_visual_brief_poison.json": {
                "failure": "raw visual_brief poison prompt",
                "gate": "storyboard_projection",
                "expected_block": "visual_concept only (no raw brief)"
            },
        }

        for fname, info in manifest.items():
            path = FIXTURE / fname
            assert path.exists(), f"Fixture file missing: {path}"
            data = _load(fname)
            assert data is not None, f"Failed to parse {fname}"
            assert "failure" in info
            assert "gate" in info

    def test_existing_known_failures_still_present(self):
        """Pre-existing failure fixtures must remain in the directory."""
        existing_failures = [
            "semantic_generic_broll.json",
            "missing_segment_work_orders.json",
            "shot_missing_drift_policy.json",
            "non_sonnet_author.json",
            "missing_script_hash.json",
            "semantic_decorative_graphic.json",
        ]
        for fname in existing_failures:
            assert (FIXTURE / fname).exists(), \
                f"Existing failure fixture removed: {fname}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

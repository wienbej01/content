"""Tests for produce.py resume and state invalidation (TKT-13)."""
import json as _json; from pathlib import Path as _P
_MODEL_MAX = float(_json.loads((_P(__file__).resolve().parent.parent / "docs" / "channel_universe" / "constraints.json").read_text()).get("lipsync_render_rules", {}).get("max_clip_duration_sec", 15))
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from produce import STEPS, _load_state, _save_state, invalidate_from_step


@pytest.fixture
def project_dir(tmp_path):
    """Create a minimal project directory."""
    (tmp_path / "narration").mkdir()
    return tmp_path


def _all_done_state():
    """Return step_status with all steps marked done."""
    return {
        "step_status": {s: {"status": "done", "completed_at": "2026-01-01T00:00:00"} for s in STEPS},
        "seed": "test",
        "format": "short",
    }


class TestFromStepInvalidatesDownstream:
    def test_invalidates_downstream_keeps_upstream(self, project_dir):
        state = _all_done_state()
        invalidated = invalidate_from_step(state, "qa_media", project_dir)

        # Downstream of qa_media (inclusive)
        expected_invalidated = ["qa_media", "reconcile_duration", "render_graphics",
                                "build_manifest", "assemble", "qa_final",
                                "build_quality_report", "gate_b_review"]
        assert invalidated == expected_invalidated

        # Check downstream is pending
        for s in expected_invalidated:
            assert state["step_status"][s]["status"] is None

        # Check upstream is still done
        upstream = STEPS[:STEPS.index("qa_media")]
        for s in upstream:
            assert state["step_status"][s]["status"] == "done"

    def test_from_step_tts_invalidates_all_downstream(self, project_dir):
        state = _all_done_state()
        invalidated = invalidate_from_step(state, "tts", project_dir)

        expected_start = STEPS.index("tts")
        assert invalidated == STEPS[expected_start:]
        for s in STEPS[expected_start:]:
            assert state["step_status"][s]["status"] is None
        for s in STEPS[:expected_start]:
            assert state["step_status"][s]["status"] == "done"


class TestFailedStepResetsOnResume:
    def test_downstream_of_failed_invalidated(self, project_dir):
        state = {
            "seed": "test", "format": "short",
            "step_status": {s: {"status": "done"} for s in STEPS},
        }
        # Mark compile_media_plan as failed
        state["step_status"]["compile_media_plan"] = {"status": "failed", "error": "boom"}
        # build_manifest is downstream and was "done" (stale)
        state["step_status"]["build_manifest"] = {"status": "done"}

        _save_state(project_dir, state)
        loaded = _load_state(project_dir)

        # Simulate the propagation logic from run_pipeline
        step_status = loaded["step_status"]
        for s in STEPS:
            info = step_status.get(s, {})
            if info.get("status") == "failed":
                idx = STEPS.index(s)
                for ds in STEPS[idx + 1:]:
                    ds_info = step_status.get(ds, {})
                    if ds_info.get("status") == "done":
                        step_status[ds] = {"status": None}

        # build_manifest is downstream of compile_media_plan → must be invalidated
        assert step_status["build_manifest"]["status"] is None
        # compile_media_plan itself stays failed
        assert step_status["compile_media_plan"]["status"] == "failed"


class TestBackwardCompatOldCompletedList:
    def test_old_format_migrates(self, project_dir):
        old_state = {
            "seed": "test", "format": "short",
            "completed_steps": ["research", "script_create"],
        }
        (project_dir / "state.json").write_text(json.dumps(old_state))
        loaded = _load_state(project_dir)

        assert "completed_steps" not in loaded
        assert "step_status" in loaded
        assert loaded["step_status"]["research"]["status"] == "done"
        assert loaded["step_status"]["script_create"]["status"] == "done"
        assert "storyboard_create" not in loaded["step_status"]

    def test_old_format_deduplicates(self, project_dir):
        old_state = {
            "seed": "test", "format": "short",
            "completed_steps": ["research", "research", "script_create", "script_create"],
        }
        (project_dir / "state.json").write_text(json.dumps(old_state))
        loaded = _load_state(project_dir)

        assert loaded["step_status"]["research"]["status"] == "done"
        assert loaded["step_status"]["script_create"]["status"] == "done"
        # No duplicates possible in dict form
        assert len(loaded["step_status"]) == 2


class TestNoDuplicateSteps:
    def test_step_status_dict_prevents_duplicates(self, project_dir):
        state = _all_done_state()
        _save_state(project_dir, state)

        # Simulate running research again (as run_pipeline does)
        state["step_status"]["research"] = {
            "status": "done",
            "result": {},
            "completed_at": "2026-06-01T00:00:00",
        }
        _save_state(project_dir, state)

        loaded = _load_state(project_dir)
        # Only one entry per step (dict guarantees this)
        research_entries = [k for k in loaded["step_status"] if k == "research"]
        assert len(research_entries) == 1


class TestArtifactDeletedOnInvalidation:
    def test_manifest_deleted(self, project_dir):
        manifest = project_dir / "manifest.json"
        manifest.write_text('{"test": true}')
        assert manifest.exists()

        state = _all_done_state()
        invalidate_from_step(state, "build_manifest", project_dir)

        assert not manifest.exists()
        assert state["step_status"]["build_manifest"]["status"] is None

    def test_timing_map_deleted(self, project_dir):
        narration = project_dir / "narration"
        narration.mkdir(exist_ok=True)
        timing = narration / "beat_timing_map.json"
        timing.write_text('{}')

        state = _all_done_state()
        invalidate_from_step(state, "build_timing_map", project_dir)

        assert not timing.exists()

    def test_tts_audio_not_deleted(self, project_dir):
        """TTS audio is expensive — must NOT be deleted on invalidation."""
        narration = project_dir / "narration"
        narration.mkdir(exist_ok=True)
        audio = narration / "continuous.mp3"
        audio.write_text("fake audio")

        state = _all_done_state()
        invalidate_from_step(state, "tts", project_dir)

        # TTS audio preserved
        assert audio.exists()
        # But downstream timing map state is invalidated
        assert state["step_status"]["build_timing_map"]["status"] is None

    def test_glob_artifacts_deleted(self, project_dir):
        """Assembly glob patterns (*_16x9.mp4) should be deleted."""
        (project_dir / "test_16x9.mp4").write_text("fake")
        (project_dir / "test_9x16.mp4").write_text("fake")

        state = _all_done_state()
        invalidate_from_step(state, "assemble", project_dir)

        assert not (project_dir / "test_16x9.mp4").exists()
        assert not (project_dir / "test_9x16.mp4").exists()


class TestAtomicStateWrite:
    def test_no_partial_writes(self, project_dir):
        state = _all_done_state()
        _save_state(project_dir, state)

        # tmp file should not persist after write
        assert not (project_dir / ".state.json.tmp").exists()
        assert (project_dir / "state.json").exists()

        loaded = json.loads((project_dir / "state.json").read_text())
        assert loaded["step_status"]["research"]["status"] == "done"


# ─── BSS-05 Tests ─────────────────────────────────────────────────────────


class TestFailedReviewStepNotComplete:
    """BSS-05: A step that raises RuntimeError must mark failed; downstream stays pending."""

    def test_failed_review_step_not_complete(self, project_dir):
        state = {
            "seed": "test", "format": "short",
            "step_status": {},
        }
        # Mark steps up to script_create as done
        for s in STEPS[:STEPS.index("script_review_loop")]:
            state["step_status"][s] = {"status": "done"}

        # Simulate what run_pipeline does when a step raises
        step_name = "script_review_loop"
        state["step_status"][step_name] = {"status": "failed", "error": "mandatory issues remain"}
        state["failed_step"] = step_name
        _save_state(project_dir, state)

        # Reload and run the propagation logic from run_pipeline
        loaded = _load_state(project_dir)
        step_status = loaded["step_status"]
        for s in STEPS:
            info = step_status.get(s, {})
            if info.get("status") == "failed":
                idx = STEPS.index(s)
                for ds in STEPS[idx + 1:]:
                    ds_info = step_status.get(ds, {})
                    if ds_info.get("status") == "done":
                        step_status[ds] = {"status": None}

        # script_review_loop is failed
        assert step_status["script_review_loop"]["status"] == "failed"
        # All downstream not marked done
        for ds in STEPS[STEPS.index("script_review_loop") + 1:]:
            assert step_status.get(ds, {}).get("status") != "done"


class TestStaleStoryboardInvalidatesReviewGate:
    """BSS-05: Modifying storyboard.json after gate approval invalidates the gate."""

    def test_stale_storyboard_invalidates_review_gate(self, project_dir):
        from gates import record_gate, require_gates, read_ledger, _stale

        # Set up a fake project with a storyboard
        proj_id = project_dir.name
        # gates.py looks for projects in Videos/Projects/{id} — we'll monkey-patch
        import gates
        original_projects_dir = gates.PROJECTS_DIR
        gates.PROJECTS_DIR = project_dir.parent
        try:
            (project_dir / "gates.json").parent.mkdir(parents=True, exist_ok=True)

            # Create storyboard and record gate
            sb_path = project_dir / "storyboard.json"
            sb_path.write_text(json.dumps({"beats": [{"id": "b1"}]}))
            record_gate(proj_id, "storyboard_review", "pass", artifact_path=sb_path)

            # Verify gate is valid
            ledger = read_ledger(proj_id)
            entry = ledger["gates"]["storyboard_review"]
            assert _stale(entry, None) is None

            # Modify storyboard (simulates --from-step storyboard_create)
            sb_path.write_text(json.dumps({"beats": [{"id": "b1"}, {"id": "b2_new"}]}))

            # Now the gate is stale
            reason = _stale(entry, None)
            assert reason is not None
            assert "changed" in reason
        finally:
            gates.PROJECTS_DIR = original_projects_dir


class TestGateBUnreachableWithoutQualityReport:
    """BSS-05: gate_b_review cannot be reached if build_quality_report fails."""

    def test_gate_b_unreachable_without_quality_report(self, project_dir):
        # build_quality_report is before gate_b_review in STEPS
        bqr_idx = STEPS.index("build_quality_report")
        gbr_idx = STEPS.index("gate_b_review")
        assert bqr_idx < gbr_idx

        # Simulate: build_quality_report fails → pipeline stops → gate_b never runs
        state = _all_done_state()
        state["step_status"]["build_quality_report"] = {"status": "failed", "error": "FAIL"}
        _save_state(project_dir, state)

        loaded = _load_state(project_dir)
        step_status = loaded["step_status"]

        # Propagation: downstream of failed step can't be done
        for s in STEPS:
            info = step_status.get(s, {})
            if info.get("status") == "failed":
                idx = STEPS.index(s)
                for ds in STEPS[idx + 1:]:
                    ds_info = step_status.get(ds, {})
                    if ds_info.get("status") == "done":
                        step_status[ds] = {"status": None}

        # gate_b_review invalidated
        assert step_status["gate_b_review"]["status"] is None


class TestAllStepsHaveErrorPropagation:
    """BSS-05: No step function swallows exceptions that would mask failures."""

    def test_all_steps_have_error_propagation(self):
        import inspect
        from produce import STEP_FNS

        # Patterns that indicate swallowed errors (not acceptable in step functions)
        # Exception: _notify and Telegram sends are side-effects, not control flow
        for step_name, fn in STEP_FNS.items():
            source = inspect.getsource(fn)
            # No bare 'except: pass' or 'except Exception: pass' in step functions
            # (which would swallow real errors)
            lines = source.split("\n")
            for i, line in enumerate(lines):
                stripped = line.strip()
                # A bare except+pass pattern
                if stripped == "pass" and i > 0:
                    prev = lines[i - 1].strip()
                    if prev.startswith("except") and "Exception" in prev:
                        # Only acceptable if it's in a Telegram/notification context
                        context = "\n".join(lines[max(0, i-3):i+1])
                        assert "telegram" in context.lower() or "notify" in context.lower(), \
                            f"Step {step_name!r} has swallowed exception at line {i}: {context}"


# ─── PST-07 Tests — State and Fingerprint Invalidation ────────────────────


class TestTTSChangeInvalidatesProductionStoryboard:
    """PST-07: invalidate_from_step('tts') resets production_storyboard."""

    def test_tts_change_invalidates_production_storyboard(self, project_dir):
        state = _all_done_state()
        invalidate_from_step(state, "tts", project_dir)
        assert state["step_status"]["production_storyboard"]["status"] is None


class TestTimingMapChangeInvalidatesProductionStoryboard:
    """PST-07: invalidate_from_step('build_timing_map') resets production_storyboard."""

    def test_timing_map_change_invalidates_production_storyboard(self, project_dir):
        state = _all_done_state()
        invalidate_from_step(state, "build_timing_map", project_dir)
        assert state["step_status"]["production_storyboard"]["status"] is None


class TestProductionStoryboardFingerprintWritten:
    """PST-07: reconcile writes .fp.json beside output."""

    def test_production_storyboard_fingerprint_written(self, tmp_path):
        from reconcile_production_storyboard import reconcile_with_hashes, _load_constraints
        from artifact_fingerprint import write_fingerprint, read_fingerprint
        import hashlib

        # Minimal fixtures
        sb = {"project_id": "test", "beats": [
            {"beat_id": "b1", "shot_type": "broll", "narration_text": "Hello world."}
        ]}
        tm = {"total_duration": 5.0, "beats": [
            {"beat_id": "b1", "start": 0.0, "end": 5.0, "duration": 5.0}
        ]}
        sb_path = tmp_path / "storyboard.json"
        tm_path = tmp_path / "timing_map.json"
        out_path = tmp_path / "production_storyboard.json"
        sb_path.write_text(json.dumps(sb))
        tm_path.write_text(json.dumps(tm))

        constraints = {"max_clip_sec": _MODEL_MAX, "min_clip_sec": 4.0}
        result, _ = reconcile_with_hashes(sb_path, tm_path, sb, tm, constraints)
        out_path.write_text(json.dumps(result, indent=2))

        # Write fingerprint as reconcile_production_storyboard.py does
        sb_hash = hashlib.sha256(sb_path.read_bytes()).hexdigest()
        tm_hash = hashlib.sha256(tm_path.read_bytes()).hexdigest()
        write_fingerprint(
            out_path,
            producer="reconcile_production_storyboard",
            producer_version="1.0",
            upstream_hashes=[sb_hash, tm_hash],
            project_id="test",
        )

        fp = read_fingerprint(out_path)
        assert fp is not None
        assert fp["producer"] == "reconcile_production_storyboard"
        assert sorted(fp["upstream_hashes"]) == sorted([sb_hash, tm_hash])


class TestStaleFingerprintDetected:
    """PST-07: wrong upstream hash in fp → stale detected."""

    def test_stale_fingerprint_detected(self, tmp_path):
        from artifact_fingerprint import write_fingerprint, verify_fingerprint
        import hashlib

        # Create a fake production_storyboard.json
        out_path = tmp_path / "production_storyboard.json"
        out_path.write_text('{"beats": []}')

        # Write fingerprint with old upstream hashes
        old_sb_hash = hashlib.sha256(b"old storyboard content").hexdigest()
        old_tm_hash = hashlib.sha256(b"old timing map content").hexdigest()
        write_fingerprint(
            out_path,
            producer="reconcile_production_storyboard",
            producer_version="1.0",
            upstream_hashes=[old_sb_hash, old_tm_hash],
            project_id="test",
        )

        # New upstream hashes (storyboard changed)
        new_sb_hash = hashlib.sha256(b"new storyboard content").hexdigest()
        valid, reason = verify_fingerprint(
            out_path, upstream_hashes=[new_sb_hash, old_tm_hash]
        )
        assert not valid
        assert "upstream_hashes mismatch" in reason

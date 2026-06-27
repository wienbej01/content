"""S15-T005: Semantic-role verification pipeline integration.

This module integrates S15_T004 frame sampling and S15_T003 semantic-role QA evidence
recording into a unified pipeline for publish-grade render units.

Key responsibilities:
1. Sample frames from render units using frame_sampling.sample_frames_for_render_unit()
2. Verify semantic role from sampled frames using a pluggable verifier interface
3. Record semantic-role QA evidence using semantic_role_qa.record_semantic_role_qa()
4. Provide a deterministic test-only verifier for development/testing

The pipeline is deterministic and fail-closed:
- Frame sampling failures prevent semantic-role pass evidence
- Verifier failures record semantic_role_qa failure and block assembly
- Evidence is bound to render_unit id AND current visual_role (S15_T003 invariant)

Since real AI vision is not yet available, this module provides:
- A clean Verifier interface for pluggable semantic analysis
- A DeterministicTestVerifier for development/testing (deterministic pass/fail based on config)
- Production-ready hooks for S15_GATE to integrate real AI vision when available

No fake-green: The pipeline requires explicit verifier output; labels, asset_type, or
visual_role alone cannot produce pass evidence.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

import production_db as _db

from frame_sampling import FrameSamplingError, sample_frames_for_render_unit
from semantic_role_qa import SEMANTIC_ROLE_QA_VALIDATOR, record_semantic_role_qa


class Verifier(ABC):
    """Abstract semantic-role verifier interface.

    A verifier inspects sampled frame metadata and produces a pass/fail verdict
    about whether the rendered content satisfies the declared visual_role.
    """

    @abstractmethod
    def verify(
        self,
        render_unit_id: str,
        visual_role: str,
        frame_metadata: List[Dict[str, Any]],
        video_path: Path,
    ) -> Dict[str, Any]:
        """Verify semantic role from sampled frames.

        Args:
            render_unit_id: Render unit being verified.
            visual_role: Declared editorial visual_role (e.g., "hero_trust", "broll_evidence").
            frame_metadata: List of frame info dicts from frame sampling, each with:
                - frame_index: int
                - path: str (absolute path to sampled frame JPEG)
                - timestamp_sec: float
            video_path: Path to source video artifact.

        Returns:
            Dict with:
            - result: "pass" or "fail"
            - reason: Optional[str] (required on fail, optional on pass)
            - details: Optional[Dict] with extra evidence (e.g., detected objects, confidence)
        """
        ...


class DeterministicTestVerifier(Verifier):
    """Deterministic test-only verifier for development and testing.

    This verifier produces deterministic pass/fail results based on configuration.
    It does NOT perform real semantic understanding — it's a test harness that
    verifies the pipeline wiring without requiring AI vision.

    In production, this would be replaced by a real AI vision verifier (S15_GATE).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Configure deterministic test verifier.

        Args:
            config: Dict with optional rules:
                - fail_on_unit_ids: List of render_unit_ids that should fail
                - fail_on_visual_roles: List of visual_roles that should fail
                - default_result: "pass" or "fail" (default "pass")
        """
        self.config = config or {}

    def verify(
        self,
        render_unit_id: str,
        visual_role: str,
        frame_metadata: List[Dict[str, Any]],
        video_path: Path,
    ) -> Dict[str, Any]:
        """Verify semantic role using deterministic test rules.

        This does NOT perform real semantic analysis. It's a test harness that
        verifies the pipeline integration with deterministic pass/fail results.
        """
        # Check deterministic failure rules
        fail_unit_ids = self.config.get("fail_on_unit_ids", [])
        if render_unit_id in fail_unit_ids:
            return {
                "result": "fail",
                "reason": f"[DETERMINISTIC TEST] render_unit {render_unit_id} configured to fail",
                "details": {"deterministic_test": True, "config_rule": "fail_on_unit_ids"},
            }

        fail_roles = self.config.get("fail_on_visual_roles", [])
        if visual_role in fail_roles:
            return {
                "result": "fail",
                "reason": f"[DETERMINISTIC TEST] visual_role '{visual_role}' configured to fail",
                "details": {"deterministic_test": True, "config_rule": "fail_on_visual_roles"},
            }

        # Default to pass (for testing valid pipeline flow)
        return {
            "result": "pass",
            "reason": None,
            "details": {"deterministic_test": True, "verifier_type": "DeterministicTestVerifier"},
        }


def verify_and_record_semantic_role(
    production_id: str,
    render_unit_id: str,
    verifier: Verifier,
    frame_output_base_dir: Path,
    frame_strategy: str = "start_middle_end",
    frame_count: int = 3,
    db_path=None,
) -> Dict[str, Any]:
    """Sample frames, verify semantic role, and record QA evidence.

    This is the primary S15_T005 integration pipeline. It:

    1. Samples frames from the render_unit's video artifact (S15_T004)
    2. Runs the verifier to inspect frames and produce pass/fail verdict
    3. Records semantic-role QA evidence in the DB (S15_T003)

    If frame sampling fails, semantic-role QA evidence cannot be created.
    If verification fails, evidence records failure and assembly will block.

    Args:
        production_id: Production ID.
        render_unit_id: Render unit ID to verify.
        verifier: Verifier instance (DeterministicTestVerifier for testing, real AI for S15_GATE).
        frame_output_base_dir: Base directory for frame output.
        frame_strategy: "start_middle_end" or "evenly_spaced"
        frame_count: Number of frames to sample (3 for start_middle_end, 1-20 for evenly_spaced)
        db_path: Production database path.

    Returns:
        Dict with:
            - render_unit_id: str
            - visual_role: str (from DB)
            - sampling_success: bool
            - frame_metadata: List[Dict] if sampling succeeded
            - verification_result: str ("pass" or "fail") if sampling succeeded
            - verification_reason: Optional[str]
            - evidence_recorded: bool (whether semantic_role_qa validation was created)
            - validation_id: Optional[str] (if evidence was recorded)

    Raises:
        FrameSamplingError: If video is missing/corrupt/invalid.
    """
    conn = _db.connect(db_path)

    # Step 1: Get render_unit's current visual_role from DB
    unit = conn.execute(
        "SELECT id, visual_role FROM render_units WHERE id=?",
        (render_unit_id,),
    ).fetchone()

    if unit is None:
        raise FrameSamplingError(
            f"BLOCKED_SEMANTIC_PIPELINE_UNIT_NOT_FOUND: render_unit {render_unit_id} not found"
        )

    visual_role = unit["visual_role"]
    if not visual_role:
        # Non-publish-grade units may not have visual_role — this is allowed
        return {
            "render_unit_id": render_unit_id,
            "visual_role": None,
            "sampling_success": False,
            "frame_metadata": [],
            "verification_result": None,
            "verification_reason": "No visual_role assigned (non-publish-grade unit)",
            "evidence_recorded": False,
            "validation_id": None,
        }

    # Step 2: Sample frames from the render_unit's video artifact
    try:
        sampling_metadata = sample_frames_for_render_unit(
            production_id,
            render_unit_id,
            frame_output_base_dir,
            strategy=frame_strategy,
            count=frame_count,
            db_path=db_path,
        )
        frame_metadata = sampling_metadata["frames"]
        sampling_success = True
        artifact_uri = sampling_metadata["artifact_uri"]
    except FrameSamplingError as e:
        # Frame sampling failed — cannot create semantic-role QA evidence
        return {
            "render_unit_id": render_unit_id,
            "visual_role": visual_role,
            "sampling_success": False,
            "frame_metadata": [],
            "verification_result": None,
            "verification_reason": f"Frame sampling failed: {str(e)}",
            "evidence_recorded": False,
            "validation_id": None,
        }

    # Step 3: Verify semantic role using the verifier
    verification = verifier.verify(
        render_unit_id=render_unit_id,
        visual_role=visual_role,
        frame_metadata=frame_metadata,
        video_path=Path(artifact_uri),
    )

    # Step 4: Record semantic-role QA evidence
    try:
        validation = record_semantic_role_qa(
            production_id=production_id,
            render_unit_id=render_unit_id,
            visual_role=visual_role,
            status=verification["result"],
            reason=verification.get("reason"),
            details=verification.get("details"),
            db_path=db_path,
        )
        evidence_recorded = True
        validation_id = validation["id"]
    except (ValueError, TypeError) as e:
        # Recorder failed — this should not happen if verifier output is valid
        return {
            "render_unit_id": render_unit_id,
            "visual_role": visual_role,
            "sampling_success": sampling_success,
            "frame_metadata": frame_metadata,
            "verification_result": verification["result"],
            "verification_reason": verification.get("reason"),
            "evidence_recorded": False,
            "validation_id": None,
            "pipeline_error": f"Recorder failed: {str(e)}",
        }

    return {
        "render_unit_id": render_unit_id,
        "visual_role": visual_role,
        "sampling_success": sampling_success,
        "frame_metadata": frame_metadata,
        "verification_result": verification["result"],
        "verification_reason": verification.get("reason"),
        "evidence_recorded": evidence_recorded,
        "validation_id": validation_id,
    }

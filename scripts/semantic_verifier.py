"""TKT-202: Production semantic verifier for vision QA.

Provides VisionQAVerifier (production, calls vision_qa profile with frame
bundle + semantic contract) and FixtureVerifier (deterministic pass/fail for
tests) implementing the Verifier ABC from semantic_role_pipeline.py.

Backend selection via SEMANTIC_QA_BACKEND env var:
  vision   -> VisionQAVerifier (real vision model call)
  fixture  -> FixtureVerifier (deterministic test verdicts)
  none     -> RuntimeError (fail-closed, INV-3)
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import production_db as _db
from llm_call import llm_vision_call
from frame_bundle import build_frame_bundle
from semantic_role_pipeline import Verifier
from vision_budget import consume_vision_budget, record_vision_qa_cost

SEMANTIC_QA_BACKEND_ENV = "SEMANTIC_QA_BACKEND"
BACKEND_VISION = "vision"
BACKEND_FIXTURE = "fixture"
BACKEND_NONE = "none"
VALID_BACKENDS = (BACKEND_VISION, BACKEND_FIXTURE, BACKEND_NONE)

CONFIDENCE_THRESHOLD = 0.5

VQA_PROMPT_TEMPLATE = """You are a strict JSON-only semantic QA analyzer. Your task is to judge whether rendered video frames satisfy a semantic contract.

SEMANTIC CONTRACT:
- Visual role: {visual_role}
- Narrative claim: {narrative_claim}
- Acceptance criteria: {semantic_acceptance_criteria}
- Must show: {must_show}
- Must avoid: {must_avoid}

Examine the provided frames carefully. Return ONLY valid JSON with exactly these fields:
{{"claim_supported": true/false, "must_show_present": [...], "must_avoid_violations": [...], "described_content": "...", "confidence": 0.0-1.0}}

claim_supported: Does the visual content support the narrative claim?
must_show_present: Which of the required elements are clearly visible in the frames?
must_avoid_violations: Any forbidden elements that are present (empty list if none).
described_content: One-sentence description of what the frames show.
confidence: Your confidence in this assessment (0.0-1.0)."""


class VisionQAVerifier(Verifier):
    """Production verifier using vision_qa profile + frame bundle."""

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    def _load_unit_context(self, render_unit_id: str) -> dict:
        conn = _db.connect(self._db_path)
        row = conn.execute(
            """SELECT visual_role, narrative_claim, semantic_acceptance_criteria,
                      metadata_json, required_action, forbidden_cliches
               FROM render_units WHERE id=?""",
            (render_unit_id,),
        ).fetchone()
        conn.close()
        if not row:
            raise ValueError(f"render_unit {render_unit_id} not found")

        ctx = dict(row)
        meta = {}
        if row["metadata_json"]:
            try:
                meta = json.loads(row["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                meta = {}
        ctx["must_show"] = meta.get("must_show", []) or []
        ctx["must_avoid"] = meta.get("must_avoid", []) or []
        return ctx

    def _build_prompt(self, ctx: dict) -> str:
        return VQA_PROMPT_TEMPLATE.format(
            visual_role=ctx.get("visual_role", "unknown"),
            narrative_claim=ctx.get("narrative_claim", ""),
            semantic_acceptance_criteria=ctx.get("semantic_acceptance_criteria", ""),
            must_show=json.dumps(ctx.get("must_show", [])),
            must_avoid=json.dumps(ctx.get("must_avoid", [])),
        )

    @staticmethod
    def _frame_hashes(frame_paths: List[Path]) -> List[str]:
        hashes = []
        for fp in frame_paths:
            sha = hashlib.sha256()
            with open(fp, "rb") as f:
                sha.update(f.read(65536))
            hashes.append(sha.hexdigest()[:16])
        return hashes

    @staticmethod
    def _bundle_sha(video_path: Path) -> str:
        sha = hashlib.sha256()
        with open(video_path, "rb") as f:
            sha.update(f.read(65536))
        return sha.hexdigest()[:16]

    def _apply_verdict_rules(
        self, verdict: dict, must_show: List[str]
    ) -> tuple[str, Optional[str]]:
        confidence = verdict.get("confidence", 0.0)
        claim_supported = verdict.get("claim_supported", False)
        must_avoid_violations = verdict.get("must_avoid_violations", []) or []
        must_show_present = verdict.get("must_show_present", []) or []

        reasons = []

        if not claim_supported:
            reasons.append("claim_not_supported")

        if must_avoid_violations:
            reasons.append(f"must_avoid_violations: {must_avoid_violations}")

        if confidence < CONFIDENCE_THRESHOLD:
            reasons.append(f"confidence_{confidence:.2f}_below_threshold_{CONFIDENCE_THRESHOLD}")

        missing = []
        for required in must_show:
            found = any(required.lower() in (item or "").lower() for item in must_show_present)
            if not found:
                missing.append(required)
        if missing:
            reasons.append(f"must_show_missing: {missing}")

        if reasons:
            return ("fail", "; ".join(reasons))
        return ("pass", None)

    def verify(
        self,
        render_unit_id: str,
        visual_role: str,
        frame_metadata: List[Dict[str, Any]],
        video_path: Path,
    ) -> Dict[str, Any]:
        ctx = self._load_unit_context(render_unit_id)
        must_show = ctx.get("must_show", [])
        prompt = self._build_prompt(ctx)

        frame_paths = build_frame_bundle(video_path)

        frame_hashes = self._frame_hashes(frame_paths)
        bundle_sha = self._bundle_sha(video_path)

        try:
            data, raw_text, profile_name, model = llm_vision_call(
                task="semantic_role_qa",
                prompt=prompt,
                image_paths=frame_paths,
                model_profile="vision_qa",
                dry_run=False,
            )
        except RuntimeError:
            # One retry on failure
            data, raw_text, profile_name, model = llm_vision_call(
                task="semantic_role_qa",
                prompt=prompt,
                image_paths=frame_paths,
                model_profile="vision_qa",
                dry_run=False,
            )

        if data is None:
            return {
                "result": "fail",
                "reason": "unparseable_model_response",
                "details": {
                    "backend": "vision",
                    "model": model,
                    "frame_hashes": frame_hashes,
                    "bundle_sha": bundle_sha,
                    "verdict": None,
                    "raw_response_preview": (raw_text or "")[:500],
                },
            }

        verdict = data if isinstance(data, dict) else {}
        status, reason = self._apply_verdict_rules(verdict, must_show)

        return {
            "result": status,
            "reason": reason,
            "details": {
                "backend": "vision",
                "model": model,
                "visual_role": ctx.get("visual_role"),
                "narrative_claim": ctx.get("narrative_claim"),
                "verdict": verdict,
                "frame_hashes": frame_hashes,
                "bundle_sha": bundle_sha,
                "confidence_threshold": CONFIDENCE_THRESHOLD,
            },
        }


class FixtureVerifier(Verifier):
    """Deterministic fixture verifier for tests.

    Produces configurable verdicts matching the full verdict schema.
    Used when SEMANTIC_QA_BACKEND=fixture.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    def verify(
        self,
        render_unit_id: str,
        visual_role: str,
        frame_metadata: List[Dict[str, Any]],
        video_path: Path,
    ) -> Dict[str, Any]:
        fail_unit_ids = self.config.get("fail_on_unit_ids", [])
        fail_roles = self.config.get("fail_on_visual_roles", [])

        if render_unit_id in fail_unit_ids or visual_role in fail_roles:
            return {
                "result": "fail",
                "reason": "fixture_configured_fail",
                "details": {
                    "backend": "fixture",
                    "verdict": {
                        "claim_supported": False,
                        "must_show_present": [],
                        "must_avoid_violations": ["fixture_configured_violation"],
                        "described_content": "Fixture verifier configured to fail",
                        "confidence": 0.9,
                    },
                    "frame_hashes": [],
                    "bundle_sha": "fixture",
                    "confidence_threshold": CONFIDENCE_THRESHOLD,
                },
            }

        default_verdict = self.config.get(
            "default_verdict",
            {
                "claim_supported": True,
                "must_show_present": [],
                "must_avoid_violations": [],
                "described_content": "Fixture verifier default pass verdict",
                "confidence": 0.95,
            },
        )

        return {
            "result": "pass",
            "reason": None,
            "details": {
                "backend": "fixture",
                "model": "fixture_verifier",
                "verdict": default_verdict,
                "frame_hashes": [],
                "bundle_sha": "fixture",
                "confidence_threshold": CONFIDENCE_THRESHOLD,
            },
        }


def get_verifier(db_path: Optional[str] = None) -> Optional[Verifier]:
    """Factory: return a Verifier or None based on SEMANTIC_QA_BACKEND.

    Returns None when backend is 'none' (caller should record a fail
    validation per INV-3 fail-closed requirement).
    Raises ValueError on invalid backend name.
    """
    backend = os.environ.get(SEMANTIC_QA_BACKEND_ENV, BACKEND_NONE).strip().lower()
    if backend not in VALID_BACKENDS:
        raise ValueError(
            f"BLOCKED_SEMANTIC_QA_BACKEND: invalid backend {backend!r}. "
            f"Must be one of {VALID_BACKENDS}."
        )
    if backend == BACKEND_VISION:
        return VisionQAVerifier(db_path=db_path)
    elif backend == BACKEND_FIXTURE:
        return FixtureVerifier()
    return None

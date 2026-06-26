"""Sprint 7: DB-native assembly and deliverable registry.

ASM-701  DB timeline assembly query (no manifest file)
ASM-702  Assembly worker migration
ASM-703  Deliverable registry
QA-704   Final QA and Gate B
ASM-705  JSON export compatibility
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Optional
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import production_db as _db
import production_repo as _repo
from authoring_service import request_approval, record_approval_decision
from lipsync_policy import evaluate_lipsync, get_policy as get_lipsync_policy
from hero_framing import get_render_unit_hero_framing
from shot_mix_contract import (
    validate_shot_mix, ShotMixVerdict, get_contract, DEFAULT_CONTRACT_NAME,
)
from semantic_role_qa import SEMANTIC_ROLE_QA_VALIDATOR

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "Videos" / "Projects"

_HERO_LIPSYNC_POLICIES = frozenset({"HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync"})

# S15-T002: Allowed editorial visual roles (single source of truth for the gate).
# Mirrors the reference values seeded into the `visual_roles` table by migration 011.
# visual_role is the editorial FUNCTION of a shot and is independent of the technical
# asset_type and the audio/sync audio_policy.
ALLOWED_VISUAL_ROLES = frozenset({
    "hero_trust", "hero_hook", "hero_cta",
    "broll_evidence", "broll_metaphor", "broll_emotional_reset",
    "graphic_framework", "graphic_comparison", "graphic_process", "graphic_data",
})


# ---------------------------------------------------------------------------
# Audio Assembly Mode Mapping (S13-T001)
# ---------------------------------------------------------------------------

# Maps audio_policy values to audio_assembly_mode for future audio-island assembly.
# Hero lipsync units must preserve their compensated provider audio (hero_island).
# B-roll uses master narration slices (master_slice). Silent graphics use music bed only (silent_under_music).
_AUDIO_ASSEMBLY_MODE_MAP: dict[str, str] = {
    "HERO_SYNC_LOCKED": "hero_island",
    "keep_lipsync": "hero_island",
    "hero_lipsync": "hero_island",
    "BROLL_FLEX": "master_slice",
    "BROLL_SYNCED_ACTION": "master_slice",
    "SILENT_GRAPHIC": "silent_under_music",
    "AMBIENCE_OR_SFX": "master_slice",
    "MUSIC_BED": "silent_under_music",
    "narration_overlay": "master_slice",
    "silent": "silent_under_music",
    "baked_in": "hero_island",
    "generated_tts": "hero_island",
    "strip": "master_slice",
    "ambient": "silent_under_music",
}


def get_audio_assembly_mode(audio_policy: str) -> str:
    """Map audio_policy to audio_assembly_mode.

    Args:
        audio_policy: The audio_policy value from render_units (e.g., 'HERO_SYNC_LOCKED').

    Returns:
        The audio_assembly_mode: 'hero_island', 'master_slice', or 'silent_under_music'.

    Raises:
        ValueError: If audio_policy is not in the mapping.
    """
    if audio_policy not in _AUDIO_ASSEMBLY_MODE_MAP:
        raise ValueError(
            f"BLOCKED_AUDIO_ASSEMBLY_MODE_UNKNOWN: unknown audio_policy '{audio_policy}'. "
            f"Valid values: {sorted(_AUDIO_ASSEMBLY_MODE_MAP.keys())}"
        )
    return _AUDIO_ASSEMBLY_MODE_MAP[audio_policy]


# ---------------------------------------------------------------------------
# ASM-701  Build assembly manifest from DB
# ---------------------------------------------------------------------------

class AssemblyError(Exception):
    pass


# ---------------------------------------------------------------------------
# S15-T002  Visual role gate (editorial function, publish-grade only)
# ---------------------------------------------------------------------------

def _resolve_production_contract(conn, production_id: str):
    """Resolve the shot-mix contract that governs a production.

    Maps the production's `video_type` to a contract name. Unknown or NULL
    video types fall back to DEFAULT_CONTRACT_NAME (the publish-grade
    `short_educational` contract) so that real productions — whose video_type
    is a content archetype like 'short'/'explainer', not a contract name — are
    treated as publish-grade. Only an explicit non-publish contract
    ('test_local', 'diagnostic_legacy') opts out.
    """
    row = conn.execute(
        "SELECT video_type FROM productions WHERE id=?", (production_id,)
    ).fetchone()
    video_type = row["video_type"] if row else None
    contract_name = video_type or DEFAULT_CONTRACT_NAME
    try:
        return get_contract(contract_name)
    except ValueError:
        # Unknown video_type -> default to the publish-grade contract.
        return get_contract(DEFAULT_CONTRACT_NAME)


def validate_visual_roles(units, publish_grade: bool = True) -> None:
    """Enforce that every publish-grade render_unit carries a valid visual_role.

    visual_role is the EDITORIAL function of a shot (why it is on screen) and
    is deliberately independent of asset_type (technical) and audio_policy
    (audio/sync). It is sourced from the creative_beat via DB-native planning,
    never inferred from label text.

    Non-publish-grade contracts (test_local, diagnostic_legacy) are explicitly
    exempt: visual_role is a publish-grade editorial discipline.

    Raises AssemblyError(BLOCKED_VISUAL_ROLE_*) on the first offending unit.
    """
    if not publish_grade:
        return  # explicit exemption for non-publish contracts

    for u in units:
        role = u.get("visual_role")
        label = u.get("label") or ""
        if not role:
            raise AssemblyError(
                f"BLOCKED_VISUAL_ROLE_MISSING: render unit {u['id']} ({label}) has no "
                f"visual_role. Every publish-grade render unit must declare its editorial "
                f"function during storyboard planning (creative_beat.visual_role propagates "
                f"to the render_unit via the timeline span). Allowed values: "
                f"{', '.join(sorted(ALLOWED_VISUAL_ROLES))}."
            )
        if role not in ALLOWED_VISUAL_ROLES:
            raise AssemblyError(
                f"BLOCKED_VISUAL_ROLE_INVALID: render unit {u['id']} ({label}) has visual_role "
                f"'{role}' which is not an allowed editorial role. visual_role is the editorial "
                f"function of the shot and must be one of: "
                f"{', '.join(sorted(ALLOWED_VISUAL_ROLES))}."
            )


# ---------------------------------------------------------------------------
# S15-T003  Post-render semantic-role QA gate (publish-grade only)
# ---------------------------------------------------------------------------

def _semantic_role_qa_evidence(evidence_json, field):
    """Read a field from a semantic_role_qa validation's evidence_json.

    Returns None for missing/malformed evidence rather than raising, so the gate
    can treat malformed evidence as 'does not satisfy' (fail closed).
    """
    try:
        data = json.loads(evidence_json) if evidence_json else {}
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data.get(field)


def validate_semantic_role_qa(conn, units, publish_grade: bool = True) -> None:
    """S15-T003: Require passing post-render semantic-role QA on publish-grade units.

    A publish-grade render unit may NOT pass assembly merely because its
    ``asset_type``, label, or planned ``visual_role`` says it is b-roll, graphic,
    or hero. It must carry a passing ``semantic_role_qa`` validation whose
    recorded ``visual_role`` matches the unit's CURRENT visual_role — i.e. the
    rendered content was actually evaluated against the editorial role it claims.

    Evidence is looked up per render_unit via ``validations.subject_id`` and is
    never inferred from label text or ``asset_type``. Non-publish contracts
    (``test_local``, ``diagnostic_legacy``) are explicitly exempt: semantic-role
    QA is a publish-grade editorial discipline.

    Must run AFTER :func:`validate_visual_roles` so every publish-grade unit has
    a valid current visual_role to match evidence against.

    Raises AssemblyError(BLOCKED_SEMANTIC_ROLE_QA_MISSING | _FAILED) on the first
    offending unit.
    """
    if not publish_grade:
        return  # explicit exemption for non-publish contracts

    for u in units:
        uid = u["id"]
        role = u.get("visual_role")
        label = u.get("label") or ""

        rows = conn.execute(
            """SELECT status, evidence_json FROM validations
               WHERE subject_type='render_unit' AND subject_id=?
                 AND validator_name=?
               ORDER BY created_at DESC""",
            (uid, SEMANTIC_ROLE_QA_VALIDATOR),
        ).fetchall()

        if not rows:
            raise AssemblyError(
                f"BLOCKED_SEMANTIC_ROLE_QA_MISSING: render unit {uid} ({label}) with "
                f"visual_role '{role}' has no post-render semantic-role QA evidence. "
                f"Publish-grade render units must prove their rendered content satisfies "
                f"the declared visual_role; asset_type, label, or a planned role cannot "
                f"substitute for QA. Record a '{SEMANTIC_ROLE_QA_VALIDATOR}' validation "
                f"bound to this render unit and its current visual_role."
            )

        # Governing verdict = newest row whose recorded visual_role matches the
        # unit's CURRENT visual_role. Rows for other roles (stale / mismatched)
        # cannot satisfy the current role.
        governing = None
        found_roles = []
        for r in rows:
            ev_role = _semantic_role_qa_evidence(r["evidence_json"], "visual_role")
            if ev_role:
                found_roles.append(ev_role)
            if governing is None and ev_role == role:
                governing = r

        if governing is None:
            raise AssemblyError(
                f"BLOCKED_SEMANTIC_ROLE_QA_MISSING: render unit {uid} ({label}) has "
                f"semantic-role QA evidence but none matches its current visual_role "
                f"'{role}' (found evidence for: {sorted(set(found_roles)) or 'none'}). "
                f"The QA result must correspond to the unit's current declared "
                f"visual_role; stale or role-mismatched evidence does not satisfy it."
            )

        if governing["status"] != "pass":
            reason = _semantic_role_qa_evidence(governing["evidence_json"], "reason")
            raise AssemblyError(
                f"BLOCKED_SEMANTIC_ROLE_QA_FAILED: render unit {uid} ({label}) with "
                f"visual_role '{role}' failed post-render semantic-role QA"
                + (f": {reason}" if reason else "")
                + ". The rendered content does not satisfy the declared editorial "
                "role; a failing semantic-role QA verdict cannot pass assembly."
            )
        # governing is a passing verdict matching the current visual_role -> satisfied.


# ---------------------------------------------------------------------------
# ENG-0701 / ENG-0702 / ENG-0703  Assembly input validator + timeline heuristics
# ---------------------------------------------------------------------------

TIMELINE_GAP_TOLERANCE_MS = 100
LOCAL_GRAPHIC_MAX_DURATION_MS = 4000  # warn threshold (S03-T003)
LOCAL_GRAPHIC_FAIL_DURATION_MS = 6000  # fail threshold (S03-T003)
MICRO_CUT_MIN_DURATION_MS = 1000


def validate_assembly_inputs(production_id: str, variant: str = "16x9", db_path=None) -> dict:
    """Validate all assembly inputs before building the clip manifest.

    Checks:
    1. Active timeline spans exist.
    2. No gaps/overlaps beyond tolerance.
    3. Each span maps to exactly one active render unit.
    4. Each selected render unit has active artifact.
    5. Each selected render unit has latest passing contract QA.
    6. No stale render units selected.
    7. No provider-generated local graphic selected.
    8. Files exist on disk.
    9. Artifact set hash can be computed.
    10. Timeline heuristics (identical consecutive local_graphics, long holds, micro-cuts).

    Raises AssemblyError with descriptive message on first failure.
    Returns preflight evidence dict on success.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    evidence = {"production_id": production_id, "variant": variant}

    try:
        # 1. Active timeline spans exist
        spans = conn.execute(
            """SELECT id, ordinal, label, start_ms, end_ms, duration_ms, creative_beat_id
               FROM timeline_spans WHERE production_id=? AND status='active'
               ORDER BY ordinal""",
            (production_id,),
        ).fetchall()
        if not spans:
            raise AssemblyError(
                f"BLOCKED: assembly input validation failed - no active timeline spans"
            )
        evidence["span_count"] = len(spans)
        spans = [dict(s) for s in spans]

        # 2. No gaps/overlaps beyond tolerance
        for i in range(1, len(spans)):
            prev_end = spans[i - 1]["end_ms"]
            curr_start = spans[i]["start_ms"]
            gap = curr_start - prev_end
            if gap < 0:
                raise AssemblyError(
                    f"BLOCKED: assembly input validation failed - "
                    f"timeline overlap between span {spans[i-1]['id']} (end={prev_end}) "
                    f"and span {spans[i]['id']} (start={curr_start})"
                )
            if gap > TIMELINE_GAP_TOLERANCE_MS:
                raise AssemblyError(
                    f"BLOCKED: assembly input validation failed - "
                    f"timeline gap {gap}ms between span {spans[i-1]['id']} (end={prev_end}) "
                    f"and span {spans[i]['id']} (start={curr_start})"
                )

        # Load non-stale render units
        raw_units = conn.execute(
            """SELECT ru.*, a.uri as artifact_uri, a.sha256 as artifact_sha256,
                      a.has_audio as artifact_has_audio, a.duration_ms as artifact_duration_ms
               FROM render_units ru
               LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
               WHERE ru.production_id=?
              AND ru.status != 'stale'
              AND (ru.status IN ('valid', 'generated')                      OR ru.active_artifact_id IS NOT NULL)
               ORDER BY ru.ordinal""",
            (production_id,),
        ).fetchall()
        units = [dict(u) for u in raw_units]
        evidence["unit_count"] = len(units)

        # 3. Each span maps to exactly one active render unit
        # If multiple units share the same span (e.g., from a regeneration change
        # request), the unit with a valid artifact wins (preferred over one
        # without). If both have artifacts or both lack them, the latest wins.
        span_to_unit: dict[str, str] = {}
        span_to_priority: dict[str, int] = {}
        for u in units:
            tsid = u["timeline_span_id"]
            has_art = 1 if u.get("active_artifact_id") else 0
            ordinal = u.get("ordinal", 0)
            # Priority: has artifact (1) > no artifact (0), then ordinal higher = newer
            priority = (has_art, ordinal)
            if tsid not in span_to_unit or priority > span_to_priority.get(tsid, (0, 0)):
                span_to_unit[tsid] = u["id"]
                span_to_priority[tsid] = priority

        for s in spans:
            if s["id"] not in span_to_unit:
                # Check if this span has open change requests (re-generation in progress)
                open_cr = conn.execute(
                    "SELECT 1 FROM change_requests cr "
                    "JOIN render_units ru ON cr.subject_id = ru.id "
                    "WHERE ru.timeline_span_id=? AND cr.status='open' AND cr.target_stage='generate_media' "
                    "LIMIT 1",
                    (s["id"],),
                ).fetchone()
                if not open_cr:
                    raise AssemblyError(
                        f"BLOCKED: assembly input validation failed - "
                        f"no active render unit for timeline span {s['id']} ({s.get('label', '')})"
                    )
                # Span with open CR — skip (re-generation is pending)
                continue

        # 4. Each render unit has active artifact
        for u in units:
            if not u["active_artifact_id"]:
                raise AssemblyError(
                    f"BLOCKED: assembly input validation failed - "
                    f"render unit {u['id']} ({u.get('label', '')}) has no active artifact"
                )

        # 5. Each render unit has a passing QA (any validation entry, not just latest)
        for u in units:
            passing = conn.execute(
                """SELECT 1 FROM validations
                   WHERE subject_id=? AND validator_name IN ('qa_media_contract', 'qa_media')
                     AND status='pass'
                   LIMIT 1""",
                (u["id"],),
            ).fetchone()
            if not passing:
                # If the unit is change_requested, skip QA validation.
                # The unit has a FAIL validation from the QA that triggered
                # the change request. Its artifact is still valid for assembly.
                # The change request will be resolved in a future run.
                if u.get("status") == "change_requested":
                    continue
                # No passing validation. Check if there is a FAIL.
                has_fail = conn.execute(
                    """SELECT 1 FROM validations
                       WHERE subject_id=? AND validator_name IN ('qa_media_contract', 'qa_media')
                         AND status='fail'
                       LIMIT 1""",
                    (u["id"],),
                ).fetchone()
                if has_fail:
                    raise AssemblyError(
                        f"BLOCKED: assembly input validation failed - "
                        f"render unit {u['id']} ({u.get('label', '')}) has no passing QA"
                    )
                # No validations at all -> pre-QA artifact, allow assembly

                # S14-T003: Per-segment SyncNet mandatory for HERO_SYNC_LOCKED units
                # audio_offset is diagnostic-only and cannot satisfy publish-grade hero sync requirement
        for u in units:
            if u.get("audio_policy") in _HERO_LIPSYNC_POLICIES or u.get("lipsync_required"):
                # Check for per-segment SyncNet validation
                # Validation must be on the render_unit or its provider_job
                syncnet_validation = conn.execute(
                    """SELECT id, evidence_json FROM validations WHERE
                       (subject_id=? OR subject_id IN (SELECT id FROM provider_jobs WHERE render_unit_id=?))
                       AND validator_name='syncnet_offset'
                       AND status='pass'
                       LIMIT 1""", (u["id"], u["id"],),
                ).fetchone()

                if not syncnet_validation:
                    raise AssemblyError(
                        "BLOCKED_HERO_SYNCNET_PER_SEGMENT_MISSING: render unit " + u["id"] + " "
                        "(" + (u.get("label", "") or "") + ") has no passing per-segment SyncNet validation. "
                        "Publish-grade hero lip sync requires SyncNet evaluation for each hero segment. "
                        "audio_offset validation is diagnostic-only and cannot satisfy this requirement. "
                        "Whole-video or merged face-track SyncNet cannot satisfy per-segment requirement."
                    )

                # S14-T004: SyncNet confidence and offset threshold gate
                # Evaluate per-segment SyncNet evidence against tiered policy thresholds
                try:
                    # Parse SyncNet evidence from validation
                    evidence_json = json.loads(syncnet_validation["evidence_json"])
                    offset_ms = evidence_json.get("offset_ms")
                    confidence = evidence_json.get("confidence")

                    if offset_ms is None:
                        raise AssemblyError(
                            f"BLOCKED_HERO_SYNCNET_EVIDENCE_MALFORMED: render unit {u['id']} "
                            f"({u.get('label', '') or ''}) has SyncNet validation with missing offset_ms "
                            f"in evidence_json. Per-segment SyncNet evidence must include offset_ms field."
                        )

                    # Get hero framing metadata to select appropriate policy
                    try:
                        framing_meta = get_render_unit_hero_framing(u["id"], db_path=db_path)
                        policy_name = framing_meta.policy_name
                    except Exception as e:
                        # Fallback to close_hero if framing metadata is unavailable
                        policy_name = "close_hero"

                    # Get policy to check min_confidence separately
                    policy = get_lipsync_policy(policy_name)
                    min_confidence = policy.min_confidence

                    # Evaluate lipsync against tiered policy
                    verdict = evaluate_lipsync(
                        offset_ms=offset_ms,
                        confidence=confidence,
                        policy_name=policy_name,
                    )

                    # Check verdict - only FAIL is blocked at assembly
                    if verdict.verdict == "fail":
                        # Determine failure reason for clearer error message
                        if confidence is None or (confidence is not None and confidence < min_confidence):
                            raise AssemblyError(
                                f"BLOCKED_HERO_SYNCNET_LOW_CONFIDENCE: render unit {u['id']} "
                                f"({u.get('label', '') or ''}) SyncNet confidence {confidence if confidence is not None else 'None'} "
                                f"is below minimum threshold {min_confidence} for policy '{policy_name}'. "
                                f"Reason: {verdict.reason}"
                            )
                        else:
                            raise AssemblyError(
                                f"BLOCKED_HERO_SYNCNET_BELOW_THRESHOLD: render unit {u['id']} "
                                f"({u.get('label', '') or ''}) SyncNet offset {offset_ms}ms "
                                f"exceeds threshold for policy '{policy_name}'. "
                                f"Reason: {verdict.reason}"
                            )

                except json.JSONDecodeError:
                    raise AssemblyError(
                        f"BLOCKED_HERO_SYNCNET_EVIDENCE_MALFORMED: render unit {u['id']} "
                        f"({u.get('label', '') or ''}) has SyncNet validation with malformed evidence_json. "
                        f"Per-segment SyncNet evidence must be valid JSON with offset_ms and confidence fields."
                    )

        # S13-T002: Compensated hero artifact requirement for hero_island units
        for u in units:
            # Check if this unit requires hero_island assembly mode
            if u.get("audio_policy") in _HERO_LIPSYNC_POLICIES or u.get("lipsync_required"):
                mode = get_audio_assembly_mode(u.get("audio_policy", ""))
                if mode == "hero_island":
                    # Load compensated_artifact_path from provider_jobs
                    pj = conn.execute(
                        "SELECT compensated_artifact_path FROM provider_jobs "
                        "WHERE render_unit_id=? AND compensated_artifact_path IS NOT NULL "
                        "ORDER BY rowid DESC LIMIT 1",
                        (u["id"],),
                    ).fetchone()

                    if not pj or not pj["compensated_artifact_path"]:
                        raise AssemblyError(
                            f"BLOCKED_HERO_COMPENSATED_ARTIFACT_MISSING: render unit " + u["id"] + " "
                            f"(" + (u.get("label", "") or "") + ") requires compensated_artifact_path for "
                            f"hero_island assembly mode. Hero lip-sync units must use compensated "
                            f"provider audio to preserve sync. Raw provider video cannot be used."
                        )

                    cap_path = pj["compensated_artifact_path"]
                    if not Path(cap_path).exists():
                        raise AssemblyError(
                            f"BLOCKED_HERO_COMPENSATED_ARTIFACT_FILE_MISSING: render unit " + u["id"] + " "
                            f"(" + (u.get("label", "") or "") + ") compensated_artifact_path file not found: "
                            f"{cap_path}. Hero lip-sync units require the compensated artifact file to exist."
                        )

        # S15-T001: Shot-mix contract validation
        # Enforce format-level shot-mix requirements (e.g., minimum hero/broll/graphic counts)
        try:
            verdict: ShotMixVerdict = validate_shot_mix(units)

            if not verdict.passes:
                # Build clear error message with expected vs actual counts
                violations_str = "; ".join(verdict.violations)
                expected_str = ", ".join([f"{k}>={v}" for k, v in verdict.expected.items()])
                actual_str = ", ".join([f"{k}={v}" for k, v in verdict.actual.items()])

                raise AssemblyError(
                    f"BLOCKED_SHOT_MIX_CONTRACT: render units violate shot-mix contract '{verdict.contract_name}'. "
                    f"Expected: {expected_str}. Actual: {actual_str}. "
                    f"Violations: {violations_str}. "
                    f"Assembly requires minimum shot counts per format contract. "
                    f"Verify storyboard includes required shot types (hero_lipsync, broll, graphic)."
                )

            # Record shot-mix verdict in evidence for transparency
            evidence["shot_mix_verdict"] = verdict.to_dict()

        except Exception as e:
            # If contract config is missing/invalid, fail closed with clear error
            if "BLOCKED_SHOT_MIX" in str(e):
                # Re-raise our own errors
                raise AssemblyError(str(e)) from None
            else:
                # Unexpected error - fail closed
                raise AssemblyError(
                    f"BLOCKED_SHOT_MIX_CONTRACT_VALIDATION_FAILED: Shot-mix contract validation failed with error: {e}"
                ) from None

        # S15-T002: Visual role validation — publish-grade editorial discipline.
        # Runs AFTER shot-mix (structure) so a structurally valid publish-grade
        # batch reaches this gate. Non-publish contracts are explicitly exempt.
        contract = _resolve_production_contract(conn, production_id)
        validate_visual_roles(units, publish_grade=contract.publish_grade)
        evidence["visual_role_contract"] = contract.format_name
        evidence["visual_role_publish_grade"] = bool(contract.publish_grade)

        # S15-T003: Post-render semantic-role QA — publish-grade render units must
        # carry passing semantic-role QA evidence bound to the unit AND its current
        # visual_role, proving the RENDERED content satisfies the declared role.
        # Runs after visual_role so a valid current role exists to match against.
        # Non-publish contracts (test_local / diagnostic_legacy) are exempt.
        validate_semantic_role_qa(conn, units, publish_grade=contract.publish_grade)
        evidence["semantic_role_qa_publish_grade"] = bool(contract.publish_grade)

        # 6. No stale render units (already excluded by SQL WHERE status!=stale)

        # 7. No provider-generated local graphic selected
        for u in units:
            if u["asset_type"] == "local_graphic":
                pj = conn.execute(
                    "SELECT COUNT(*) as c FROM provider_jobs WHERE render_unit_id=?", (u["id"],)
                ).fetchone()
                if pj["c"] > 0:
                    raise AssemblyError(
                        f"BLOCKED: assembly input validation failed - "
                        f"local graphic {u['id']} has {pj['c']} provider job(s) - "
                        f"local_graphic assets must never be sent to paid providers"
                    )

        # 8. Files exist on disk
        for u in units:
            if u["artifact_uri"]:
                if not Path(u["artifact_uri"]).exists():
                    raise AssemblyError(
                        f"BLOCKED: assembly input validation failed - "
                        f"artifact file missing: {u['artifact_uri']}"
                    )

        # 9. Artifact set hash
        sha256s = [u["artifact_sha256"] for u in units if u["artifact_sha256"]]
        evidence["artifact_set_hash"] = hashlib.sha256(
            "|".join(sorted(sha256s)).encode()
        ).hexdigest()

        # 10. Timeline heuristics (ENG-0703)
        _validate_timeline_heuristics(units)

        evidence["validation_passed"] = True
        evidence["render_unit_ids"] = [u["id"] for u in units]
        evidence["artifact_ids"] = [u["active_artifact_id"] for u in units if u["active_artifact_id"]]
        return evidence

    finally:
        conn.close()


def _validate_timeline_heuristics(units: list) -> None:
    """ENG-0703: Validate timeline for loops, long holds, and micro-cuts.

    Raises AssemblyError on violation.
    """
    for i in range(1, len(units)):
        prev = units[i - 1]
        curr = units[i]

        # Reject identical consecutive local_graphic render units without explicit break.
        # Render unit IDs are unique, so we compare by label (content identity).
        # If two consecutive local_graphic units have the same label, they represent
        # the same graphic content repeating - likely a loop/assembly bug.
        if (prev["asset_type"] == "local_graphic" and curr["asset_type"] == "local_graphic"
                and prev.get("label") and prev["label"] == curr.get("label")):
            # Skip if both units share the same timeline_span_id — they are
            # sub-slots from the same beat (compile_media split), not a loop error.
            if prev.get("timeline_span_id") and prev["timeline_span_id"] == curr.get("timeline_span_id"):
                pass  # Same span -> sub-slots, allowed
            else:
                raise AssemblyError(
                    f"BLOCKED: assembly input validation failed - "
                    f"identical consecutive local_graphic render unit {prev['label']} "
                    f"at ordinal {prev['ordinal']} and {curr['ordinal']} without editorial break"
                )

        # Reject micro-cuts (< 1 second)
        dur = curr["required_duration_ms"] or 0
        if 0 < dur < MICRO_CUT_MIN_DURATION_MS:
            raise AssemblyError(
                f"BLOCKED: assembly input validation failed - "
                f"micro-cut detected: render unit {curr['id']} at ordinal {curr['ordinal']} "
                f"has duration {dur}ms (< {MICRO_CUT_MIN_DURATION_MS}ms)"
            )

    # S03-T003: Static graphic hold with graduated thresholds.
    # Warn at LOCAL_GRAPHIC_MAX_DURATION_MS (4s), fail at LOCAL_GRAPHIC_FAIL_DURATION_MS (6s).
    # Allow longer only if "hold" in label (explicit hold_policy=true).
    import logging as _logging
    _log = _logging.getLogger("assemble_db")
    for u in units:
        if u["asset_type"] == "local_graphic":
            dur = u["required_duration_ms"] or 0
            label = (u.get("label") or "").lower()
            is_hold = "hold" in label

            if dur > LOCAL_GRAPHIC_FAIL_DURATION_MS and not is_hold:
                raise AssemblyError(
                    f"BLOCKED: assembly input validation failed - "
                    f"local graphic {u['id']} duration {dur}ms exceeds "
                    f"{LOCAL_GRAPHIC_FAIL_DURATION_MS}ms fail threshold without 'hold' marker"
                )
            elif dur > LOCAL_GRAPHIC_MAX_DURATION_MS and not is_hold:
                _log.warning(
                    f"Local graphic {u['id']} duration {dur}ms exceeds "
                    f"{LOCAL_GRAPHIC_MAX_DURATION_MS}ms warn threshold without 'hold' marker"
                )
def build_assembly_inputs(production_id: str, variant: str = "16x9", db_path=None) -> dict:
    """Build a complete assembly input object purely from DB state.

    Returns the DB-native assembly contract (a list of clips with timing,
    artifact path/sha, and policy). This is NOT directly consumable by the
    legacy assemble.py; use build_assembly_manifest() to bridge to its
    continuous_voiceover manifest format.

    Raises AssemblyError if any render unit is not valid or has no artifact.
    """
    _db.migrate(db_path)
    conn = _db.connect(db_path)

    # Load active timeline spans in ordinal order
    spans = conn.execute(
        """SELECT * FROM timeline_spans WHERE production_id=? AND status='active'
           ORDER BY ordinal""",
        (production_id,),
    ).fetchall()
    if not spans:
        conn.close()
        raise AssemblyError(f"No active timeline spans for production {production_id}")

    # Load render units in ordinal order. Exclude 'stale' units (D-015): re-compiling
    # after invalidation supersedes the prior plan's units (status='stale'); assembly must
    # see only the current plan's units, not the stale duplicates.
    units = conn.execute(
        """SELECT ru.*, a.uri as artifact_uri, a.sha256 as artifact_sha256,
                  a.has_audio as artifact_has_audio, a.duration_ms as artifact_duration_ms
           FROM render_units ru
           LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
           WHERE ru.production_id=?
              AND ru.status != "stale"
              AND (ru.status IN ("valid", "generated")
                  OR ru.active_artifact_id IS NOT NULL)
           ORDER BY ru.ordinal""",
        (production_id,),
    ).fetchall()

    # Load production metadata
    production = conn.execute(
        "SELECT * FROM productions WHERE id=?", (production_id,)
    ).fetchone()
    conn.close()

    if not production:
        raise AssemblyError(f"Production {production_id} not found")

    # ENG-0702: Run preflight validation before building assembly inputs
    preflight_evidence = validate_assembly_inputs(production_id, variant=variant, db_path=db_path)

    # Validate: all units must be valid or local_graphic
    invalid = [
        u for u in units
        if u["status"] not in ("valid", "generated", "local_graphic", "change_requested")
        and u["asset_type"] != "local_graphic"
    ]
    if invalid:
        problems = [f"{u['label'] or u['id']}={u['status']}" for u in invalid[:5]]
        raise AssemblyError(
            f"Assembly blocked: {len(invalid)} render unit(s) not valid: {problems}"
        )

    missing_art = [u for u in units if not u["artifact_uri"]]
    if missing_art:
        labels = [u["label"] or u["id"] for u in missing_art[:5]]
        raise AssemblyError(f"Assembly blocked: {len(missing_art)} units missing artifact: {labels}")

    # Build segment/clip entries compatible with assemble.py manifest
    # Load compensated_artifact_paths for hero units
    units_dicts = [dict(u) for u in units]
    pj_conn = _db.connect(db_path)
    compensated = {}
    for u in units_dicts:
        if u.get("audio_policy") in _HERO_LIPSYNC_POLICIES or u.get("lipsync_required"):
            pj = pj_conn.execute(
                "SELECT compensated_artifact_path FROM provider_jobs "
                "WHERE render_unit_id=? AND compensated_artifact_path IS NOT NULL "
                "ORDER BY rowid DESC LIMIT 1",
                (u["id"],),
            ).fetchone()
            if pj and pj["compensated_artifact_path"]:
                compensated[u["id"]] = pj["compensated_artifact_path"]
    pj_conn.close()

    clips = []
    for u in units_dicts:
        cap = compensated.get(u["id"])
        clips.append({
            "clip_id": u["id"],
            "label": u["label"],
            "ordinal": u["ordinal"],
            "asset_type": u["asset_type"],
            "audio_policy": u["audio_policy"],
            "lipsync_required": bool(u["lipsync_required"]),
            "start_ms": u["required_start_ms"],
            "end_ms": u["required_end_ms"],
            "duration_ms": u["required_duration_ms"],
            "path": u["artifact_uri"],
            "compensated_artifact_path": cap,
            "sha256": u["artifact_sha256"],
            "has_audio": bool(u["artifact_has_audio"]),
            "hero_framing": u.get("hero_framing"),  # S14_T002: Hero framing metadata
        })

    return {
        "production_id": production_id,
        "project_slug": production["project_slug"],
        "variant": variant,
        "clips": clips,
        "span_count": len(spans),
        "unit_count": len(units),
        "preflight": preflight_evidence,
    }


def build_assembly_manifest(production_id: str, variant: str = "16x9", db_path=None) -> dict:
    """Bridge DB state to assemble.py's legacy continuous_voiceover manifest.

    In continuous_voiceover mode every clip is a muted visual and the single
    master narration (tts_master) is the sole audio spine, overlaid once across
    the concatenated visual bed. Each segment carries timing_in/timing_out (its
    window in the master timeline) so the assembler can contract clip durations
    to the narration. Hero-lipsync segments additionally carry speech_len_sec and
    lipsync_provenance, which validate_manifest requires for any HERO_SYNC_LOCKED
    span (the deep provenance check only runs in non-continuous mode).
    """
    inputs = build_assembly_inputs(production_id, variant=variant, db_path=db_path)

    _db.migrate(db_path)
    conn = _db.connect(db_path)
    master = conn.execute(
        """SELECT uri, sha256 FROM artifacts
           WHERE production_id=? AND kind='tts_master'
           ORDER BY created_at DESC LIMIT 1""",
        (production_id,),
    ).fetchone()
    conn.close()
    if not master:
        raise AssemblyError(
            f"No tts_master narration artifact for production {production_id}")

    segments = []
    for c in inputs["clips"]:
        start_sec = (c.get("start_ms") or 0) / 1000.0
        end_sec = (c.get("end_ms") or 0) / 1000.0
        dur_sec = (c.get("duration_ms") or 0) / 1000.0
        seg = {
            "id": c.get("label") or c.get("clip_id"),
            "beat_id": c.get("label"),
            "clip_id": c.get("clip_id"),
            "media": c.get("path"),
            "compensated_artifact_path": c.get("compensated_artifact_path"),
            "asset_type": c.get("asset_type"),
            "audio_policy": c.get("audio_policy"),
            "timing_in": start_sec,
            "timing_out": end_sec,
            "duration_required": dur_sec,
        }
        if (c.get("audio_policy") or "") in _HERO_LIPSYNC_POLICIES or c.get("lipsync_required"):
            seg["speech_len_sec"] = dur_sec if dur_sec > 0 else 1.0
            seg["lipsync_provenance"] = {
                "slice_sha256": c.get("sha256") or "",
                "parent_mp3_sha256": master["sha256"] or "",
            }
        else:
            # continuous_voiceover tolerates words=0 for silent visuals.
            seg["words"] = 0
        segments.append(seg)

    project_slug = inputs.get("project_slug") or "."

    # S9-C07: Query graphic beats for overlay layers
    conn2 = _db.connect(db_path)
    graphic_beats = conn2.execute(
        """SELECT cb.id, cb.label, cb.graphics_json
           FROM creative_beats cb
           JOIN timeline_spans ts ON cb.id = ts.creative_beat_id
           WHERE ts.production_id=? AND ts.status='active' AND cb.shot_type='local_graphic'
           ORDER BY cb.ordinal""",
        (production_id,),
    ).fetchall()
    conn2.close()

    graphics_layers = []
    for gb in graphic_beats:
        gfx = json.loads(gb["graphics_json"]) if gb["graphics_json"] else {}
        text = gfx.get("text", "")
        if text:
            graphics_layers.append({
                "beat_id": gb["id"],
                "label": gb["label"],
                "text": text,
                "layout": gfx.get("layout", "center"),
            })

    # S9-C07: Music bed config (deterministic, local synthesis via tools/generate_music)
    music_config = {
        "enabled": True,
        "mood": "calm",
        "seed": 7,
        "volume_db": -28,
        "fade_in": 1.5,
        "fade_out": 2.0,
    }

    return {
        "id": production_id,
        "project_slug": project_slug,
        "variant": variant,
        "narration_mode": "continuous_voiceover",
        "continuous_audio": master["uri"],
        "pacing": {"reference": 0, "baseline_speed": 1.0},
        "output": {"directory": str(PROJECTS / project_slug)},
        "segments": segments,
        "graphics": graphics_layers,
        "music": music_config,
    }


# ---------------------------------------------------------------------------
# ASM-703  Deliverable registry
# ---------------------------------------------------------------------------

def register_deliverable(
    production_id: str,
    variant: str,
    artifact_path: str | Path,
    assembly_revision: Optional[str] = None,
    qa_validation_id: Optional[str] = None,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> dict:
    """Register an assembled output as an immutable deliverable.

    Each call with the same (production_id, variant, artifact sha256) is idempotent.
    """
    art = _repo.register_artifact(
        production_id, artifact_path, f"deliverable_{variant}",
        stage_run_id=stage_run_id,
        db_path=db_path,
    )

    with _db.transaction(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM deliverables WHERE production_id=? AND variant=? AND artifact_id=?",
            (production_id, variant, art["id"]),
        ).fetchone()
        if existing:
            return dict(existing)

        del_id = _db._id("del")
        conn.execute(
            """INSERT INTO deliverables
               (id, production_id, variant, artifact_id, status, assembly_revision,
                qa_validation_id)
               VALUES (?,?,?,?,?,?,?)""",
            (
                del_id, production_id, variant, art["id"],
                "assembled",
                assembly_revision, qa_validation_id,
            ),
        )
        _db.append_event(
            production_id, "deliverable_registered",
            payload={"deliverable_id": del_id, "variant": variant},
            conn=conn,
        )
        return dict(conn.execute("SELECT * FROM deliverables WHERE id=?", (del_id,)).fetchone())


def get_deliverables(production_id: str, db_path=None) -> list[dict]:
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    rows = conn.execute(
        """SELECT d.*, a.uri AS artifact_uri, a.sha256 AS artifact_sha256
           FROM deliverables d
           LEFT JOIN artifacts a ON d.artifact_id = a.id
           WHERE d.production_id=? ORDER BY d.id""",
        (production_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# QA-704  Final QA + Gate B
# ---------------------------------------------------------------------------

def run_final_qa(
    production_id: str,
    deliverable_id: str,
    checks: dict,
    db_path=None,
) -> dict:
    """Store final QA evidence against a deliverable.

    checks: {
        "dimensions_ok": bool,
        "duration_ok": bool,
        "loudnorm_ok": bool,
        "no_black_frames": bool,
        "captions_present": bool,  # optional
        "details": {...}
        # ENG-0801: DB-contract evidence
        "contract_checks": {...}  # optional; if present, contract_version and all_contract_checks_pass are required
    }

    Returns validation row.
    """
    required = ["dimensions_ok", "duration_ok", "loudnorm_ok", "no_black_frames"]
    passed = all(bool(checks.get(k, True)) for k in required)

    # ENG-0801: DB-contract pass is required when contract_checks field is present
    contract = checks.get("contract_checks")
    if contract is not None:
        if not contract.get("all_contract_checks_pass", False):
            passed = False

    now = _db._now()
    with _db.transaction(db_path) as conn:
        val_id = _db._id("val")
        conn.execute(
            """INSERT INTO validations
               (id, production_id, subject_type, subject_id, validator_name, status,
                evidence_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                val_id, production_id, "deliverable", deliverable_id,
                "qa_final", "pass" if passed else "fail",
                _db._json(checks), now,
            ),
        )
        if passed:
            conn.execute(
                "UPDATE deliverables SET qa_validation_id=?, status='qa_passed' WHERE id=?",
                (val_id, deliverable_id),
            )
        else:
            conn.execute(
                "UPDATE deliverables SET status='qa_failed' WHERE id=?", (deliverable_id,)
            )
        return dict(conn.execute("SELECT * FROM validations WHERE id=?", (val_id,)).fetchone())


def request_gate_b(production_id: str, deliverable_id: str, db_path=None) -> dict:
    """Request Gate B (human final approval) for a deliverable."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT artifact_id, qa_validation_id FROM deliverables WHERE id=?", (deliverable_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise ValueError(f"deliverable {deliverable_id} not found")
    if not row["qa_validation_id"]:
        raise ValueError(
            f"Gate B requires passing qa_final validation for deliverable {deliverable_id}"
        )

    art = _repo.get_artifact(row["artifact_id"], db_path=db_path)
    return request_approval(
        production_id,
        gate_name="gate_b_review",
        subject_type="deliverable",
        subject_id=deliverable_id,
        subject_sha256=art["sha256"] if art else None,
        artifact_uri=art["uri"] if art else None,
        db_path=db_path,
    )


def is_gate_b_approved(production_id: str, db_path=None) -> bool:
    """Check whether Gate B is currently approved."""
    _db.migrate(db_path)
    conn = _db.connect(db_path)
    row = conn.execute(
        "SELECT status FROM approval_requests WHERE production_id=? AND gate_name='gate_b_review'",
        (production_id,),
    ).fetchone()
    conn.close()
    return bool(row and row["status"] == "pass")


# ---------------------------------------------------------------------------
# ASM-705  JSON export compatibility
# ---------------------------------------------------------------------------

def export_assembly_manifest(production_id: str, out_path: Path, variant: str = "16x9",
                              db_path=None) -> Path:
    """Export the DB-driven assembly manifest as JSON for audit/debug only.

    This file is never consumed as a live authority by any stage.
    """
    inputs = build_assembly_inputs(production_id, variant, db_path=db_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(inputs, indent=2))
    return out_path

"""S15-T002 shared test fixtures: seed visual_role onto creative_beats.

visual_role is the editorial function of a shot. It is sourced from the
creative_beat and propagated onto the render_unit through the timeline span
(DB-native planning). These helpers let publish-grade batch fixtures across
S13/S14/S15 tests carry a valid visual_role so the assembly visual_role gate
is satisfied, without each test file reimplementing the seeding.

The TEST FIXTURE chooses the role from the unit's technical kind (audio_policy /
asset_type). Production code never infers visual_role from a label.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from authoring_service import save_storyboard, get_creative_beats  # noqa: E402
from semantic_role_qa import record_semantic_role_qa  # noqa: E402
import production_db as _pdb  # noqa: E402

_HERO_POLICIES = ("HERO_SYNC_LOCKED", "keep_lipsync", "hero_lipsync")
_BROLL_POLICIES = ("BROLL_FLEX", "BROLL_SYNCED_ACTION")


def visual_role_for(audio_policy: str, asset_type: str) -> str:
    """Pick a valid editorial visual_role for a unit of this technical kind."""
    if audio_policy in _HERO_POLICIES:
        return "hero_trust"
    if audio_policy in _BROLL_POLICIES:
        return "broll_evidence"
    if asset_type == "local_graphic" or audio_policy == "SILENT_GRAPHIC":
        return "graphic_framework"
    return "hero_trust"


def seed_visual_roles(prod_id, db, span_specs, unit_specs) -> None:
    """Create creative_beats carrying visual_role and link each span to its beat.

    Must be called AFTER ``span_specs`` / ``unit_specs`` are built and BEFORE
    ``commit_timeline_spans`` is called, so each span carries ``creative_beat_id``
    and ``plan_render_units`` propagates ``visual_role`` onto every render unit.

    ``unit_specs`` items must expose ``audio_policy`` and ``asset_type``.
    """
    beats = {
        "beats": [
            {
                "label": sp["label"],
                "visual_role": visual_role_for(u["audio_policy"], u["asset_type"]),
            }
            for sp, u in zip(span_specs, unit_specs)
        ]
    }
    save_storyboard(prod_id, beats, stage_run_id=None, db_path=db)
    beat_ids = [b["id"] for b in get_creative_beats(prod_id, db_path=db)]
    for sp, bid in zip(span_specs, beat_ids):
        sp["creative_beat_id"] = bid


def _category_for(role: str) -> str:
    """Map an allowed visual_role to its category for evidence readability."""
    if role.startswith("hero_"):
        return "hero"
    if role.startswith("broll_"):
        return "broll"
    if role.startswith("graphic_"):
        return "graphic"
    return "unknown"


def seed_semantic_role_qa(prod_id, db, units, *, status="pass",
                          visual_role_override=None, reason=None):
    """Record deterministic post-render semantic-role QA evidence for each unit.

    Reads each unit's CURRENT visual_role from the DB (source of truth) and
    records a ``semantic_role_qa`` validation bound to the unit and that role,
    so a publish-grade batch satisfies the S15-T003 assembly gate.

    This is the post-render counterpart to :func:`seed_visual_roles`: planning
    declares the role (S15-T002), post-render QA proves the rendered content
    satisfies it (S15-T003). Production code never infers the role from a label.

    Args:
        prod_id, db: production id and DB path.
        units: iterable of render-unit dicts (must expose ``id``).
        status: 'pass' (default) or 'fail'.
        visual_role_override: record evidence for this role (or
            ``callable(unit) -> role``) instead of the unit's current DB role.
            Used by negative tests that need wrong-role evidence.
        reason: optional reason recorded with the evidence.

    Units with no current visual_role are skipped (they fail the visual_role gate
    before the semantic-role gate, so seeding them is moot). Returns the list of
    recorded validation rows.
    """
    conn = _pdb.connect(db)
    try:
        rows = {
            r["id"]: r["visual_role"]
            for r in conn.execute(
                "SELECT id, visual_role FROM render_units WHERE production_id=?",
                (prod_id,),
            ).fetchall()
        }
    finally:
        conn.close()

    recorded = []
    for u in units:
        uid = u["id"]
        if callable(visual_role_override):
            role = visual_role_override(u)
        elif visual_role_override is not None:
            role = visual_role_override
        else:
            role = rows.get(uid) or u.get("visual_role")
        if not role:
            continue
        recorded.append(record_semantic_role_qa(
            prod_id, uid, role, status,
            category=_category_for(role), reason=reason, db_path=db,
        ))
    return recorded

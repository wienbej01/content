"""Deterministic, hermetic budget allocation fixtures.

Two fixture generators for budget optimization tests (TKT-801/802):
  1. flat_allocation      — storyboard with 10 beats; flat $60 budget → $6/beat.
  2. weighted_allocation  — same storyboard; beat-attention classifier marks some
                            beats at 3× weight; others at 0.5×; budget is redistributed
                            to maximize weighted quality within the cap.

Plus a small allocator embedded in the fixture so the test can validate both the flat
and weighted formulas without requiring the production allocation module.

No paid calls, no network.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple


BEAT_MIN = 0.25
BEAT_MAX = 30.0
BEAT_CAP = 60.0


class BudgetFixture(NamedTuple):
    path: Path
    label: str  # 'flat' | 'weighted'


def _build_storyboard() -> list[dict]:
    return [
        {"beat_id": "b_hook_001",    "order": 0, "narrative_function": "hook",
         "shot_type": "hero_lipsync", "est_duration_sec": 8.0, "viewer_attention_weight": 3.0},
        {"beat_id": "b_archival_002", "order": 1, "narrative_function": "evidence_anchor",
         "shot_type": "broll_archival", "est_duration_sec": 6.0, "viewer_attention_weight": 1.0},
        {"beat_id": "b_background_003","order": 2, "narrative_function": "thesis_statement",
         "shot_type": "talking_head_standard", "est_duration_sec": 12.0, "viewer_attention_weight": 2.5},
        {"beat_id": "b_metaphorical_004","order": 3, "narrative_function": "visual_pause",
         "shot_type": "broll_metaphorical", "est_duration_sec": 4.0, "viewer_attention_weight": 0.5},
        {"beat_id": "b_pattern_005",  "order": 4, "narrative_function": "pattern_definition",
         "shot_type": "talking_head_standard", "est_duration_sec": 10.0, "viewer_attention_weight": 1.5},
        {"beat_id": "b_graphic_006",  "order": 5, "narrative_function": "framework_render",
         "shot_type": "graphic_progressive", "est_duration_sec": 7.0, "viewer_attention_weight": 0.75},
        {"beat_id": "b_system_007",   "order": 6, "narrative_function": "system_walkthrough",
         "shot_type": "talking_head_standard", "est_duration_sec": 9.0, "viewer_attention_weight": 1.0},
        {"beat_id": "b_environment_008","order": 7, "narrative_function": "tonal_reset",
         "shot_type": "broll_environment", "est_duration_sec": 5.0, "viewer_attention_weight": 0.5},
        {"beat_id": "b_giveback_009", "order": 8, "narrative_function": "thesis_close",
         "shot_type": "talking_head_standard", "est_duration_sec": 11.0, "viewer_attention_weight": 3.0},
        {"beat_id": "b_cta_010",      "order": 9, "narrative_function": "call_to_action",
         "shot_type": "talking_head_hero", "est_duration_sec": 6.0, "viewer_attention_weight": 1.5},
    ]


def _flat_allocate(beats: list[dict], cap: float) -> list[float]:
    n = len(beats)
    per = cap / n
    return [round(per, 4)] * n


def _weighted_allocate(beats: list[dict], cap: float, floor: float = BEAT_MIN, ceil: float = BEAT_MAX) -> list[float]:
    weights = [max(0.5, min(3.0, b.get("viewer_attention_weight", 1.0))) for b in beats]
    wsum = sum(weights)
    allocated = [cap * (w / wsum) for w in weights]
    # iterative clamp-and-redistribute (two-pass approach)
    for _ in range(5):
        clamped = [max(floor, min(ceil, a)) for a in allocated]
        total = sum(clamped)
        if abs(total - cap) < 0.001:
            break
        # redistribute slack to unclamped beats
        slack = cap - total
        unclamped_indexes = [i for i, a in enumerate(allocated)
                            if floor < a < ceil]
        if not unclamped_indexes:
            break
        per = slack / len(unclamped_indexes)
        for i in unclamped_indexes:
            allocated[i] += per
    return [round(max(floor, min(ceil, a)), 4) for a in allocated]


def make_flat_budget_fixture(tmp_path: Path, cap: float = BEAT_CAP) -> BudgetFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "flat_budget.json"
    beats = _build_storyboard()
    amounts = _flat_allocate(beats, cap)
    doc = {
        "cap": cap,
        "allocation_mode": "flat",
        "sum": round(sum(amounts), 2),
        "beats": [
            {"beat_id": b["beat_id"], "amount_usd": a}
            for b, a in zip(beats, amounts)
        ],
    }
    out.write_text(json.dumps(doc, indent=2))
    return BudgetFixture(out, "flat")


def make_weighted_budget_fixture(tmp_path: Path, cap: float = BEAT_CAP) -> BudgetFixture:
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "weighted_budget.json"
    beats = _build_storyboard()
    amounts = _weighted_allocate(beats, cap)
    doc = {
        "cap": cap,
        "allocation_mode": "weighted",
        "sum": round(sum(amounts), 2),
        "beats": [
            {"beat_id": b["beat_id"], "amount_usd": a, "weight": b["viewer_attention_weight"]}
            for b, a in zip(beats, amounts)
        ],
    }
    out.write_text(json.dumps(doc, indent=2))
    return BudgetFixture(out, "weighted")


_ALL_BUILDERS = {
    "flat": make_flat_budget_fixture,
    "weighted": make_weighted_budget_fixture,
}


def build_all_fixtures(tmp_path: Path) -> dict[str, BudgetFixture]:
    return {name: builder(tmp_path) for name, builder in _ALL_BUILDERS.items()}

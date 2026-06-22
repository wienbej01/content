# PTC-07 Audit Report

**Ticket:** PTC-07 — Coverage slots expand to separate media-plan assets with full lineage  
**Auditor:** kiro-cli subagent (read-only)  
**Date:** 2026-06-14  
**Verdict:** PASS

---

## Scope

Verify that `_expand_coverage_slots` in `scripts/compile_media_prompts.py`:

1. Expands multi-slot beats into separate media-plan assets.
2. B003/B005/B007 produce multiple assets (as specified).
3. Every expanded asset carries full lineage (`source_beat_id`, `production_beat_id`, `coverage_slot_id`, `media_plan_asset_id`).
4. Output paths are unique across all assets.
5. Backward compatibility preserved for beats without `coverage_plan`.

---

## Evidence

### 1. Slot expansion produces separate assets

Integration run against `using_ai_to_help_memory_retention_short` project:

```
total media-plan assets: 26
assets per source beat: {'B001': 3, None: 9, 'B003': 4, 'B005': 4, 'B007': 2, 'B009': 4}
```

Multi-slot beats expand; single-slot beats remain as one asset.

### 2. B003/B005/B007 multi-slot

| Source Beat | Slots Produced | Slot IDs |
|-------------|---------------|----------|
| B003 | 4 | B003-s0, B003-s1, B003-s2, B003-s3 |
| B005 | 4 | B005-s0, B005-s1, B005-s2, B005-s3 |
| B007 | 2 | B007-s0, B007-s1 |

All three beats correctly expand.

### 3. Full lineage present

Every asset with a `source_beat_id` also has:
- `media_plan_asset_id` (e.g., `B003-s0`)
- `production_beat_id` (e.g., `B003`)
- `coverage_slot_id` (e.g., `B003-s0`)

Lineage check: **True**

### 4. Unique output paths

```
unique output paths: True
```

Path format: `assets/media/{segment_id}/{beat_id}_{slot_id}.mp4` — guarantees uniqueness via slot_id suffix.

### 5. Backward compatibility

Test `test_no_coverage_plan_one_asset` confirms beats without `coverage_plan` produce exactly one asset (no expansion). Full suite passes (482 tests, 0 failures).

---

## Code location

- `scripts/compile_media_prompts.py` lines 637–694: `_expand_coverage_slots` function
- `scripts/compile_media_prompts.py` line 691: integration in `compile_plan` loop

---

## Test coverage

`tests/test_slot_expansion.py` — 9 tests, all passing:

| Test | Covers |
|------|--------|
| test_single_slot_one_asset | No-expansion case |
| test_four_slots_four_assets | Multi-slot expansion |
| test_lineage_complete | All lineage fields present |
| test_per_slot_cost | Cost calculated per slot |
| test_local_graphic_slot_free | Zero-cost local slots |
| test_slot_timing_carried | Timing fields per slot |
| test_audited_project_slot_counts | Integration with real project |
| test_unique_output_paths | Path uniqueness |
| test_no_coverage_plan_one_asset | Backward compat |

Full suite: **482 passed in 100.20s**

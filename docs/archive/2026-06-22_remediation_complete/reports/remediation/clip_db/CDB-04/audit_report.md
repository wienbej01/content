# CDB-04 Audit Report — reconcile_duration uses coverage_for_beat

**Auditor:** kiro-cli subagent  
**Date:** 2026-06-15  
**Scope:** READ-ONLY audit of `scripts/reconcile_duration.py` integration with `clip_db.coverage_for_beat`

---

## Requirement

`reconcile_duration.py` must use `clip_db.coverage_for_beat()` to resolve parent→children beat lineage (e.g. B005 → B005a + B005b), with ffprobe fallback for legacy projects without clip_db rows.

---

## Findings

### 1. coverage_for_beat integration (PASS)

`_reconcile_via_db()` (line 74) calls `clip_db.coverage_for_beat(project_id, beat_id)` for each beat in the timing map. The function queries clips by `source_beat_id`, which means children (B005a, B005b) ordered with `source_beat_id="B005"` are automatically aggregated when the parent B005 is queried.

### 2. Parent→children resolution (PASS)

`coverage_for_beat` (clip_db.py:399) selects all clips where `source_beat_id` matches, sums their `required_dur_sec` and `actual_dur_sec`, and returns `available`, `deficit`, `all_present`, and `slots`. This correctly resolves split beats without reconcile needing to know the split structure.

### 3. Failure reporting with named beat + deficit (PASS)

When `deficit > TOLERANCE` (0.25s), the beat is appended to `failures` as `(beat_id, deficit)`. The CLI prints each failure with beat name and deficit value: `{beat_id}: deficit {deficit:.3f}s`.

When a slot is not yet generated (`all_present=False`), status is set to `SLOT_MISSING` and failure is reported.

### 4. CSV output (PASS)

`write_csv()` (line 135) writes `duration_reconciliation.csv` with columns: `beat_id, required_sec, available_sec, deficit_sec, status, asset_type, output_path`. Called unconditionally after reconciliation.

### 5. Legacy ffprobe fallback (PASS)

`reconcile()` (line 172) checks `_has_clip_db_rows(project_id)` first. If no rows exist, `_reconcile_via_ffprobe()` is invoked, which uses `probe_duration()` on plan `output_path` files. The dual-path logic is clean: DB-first, ffprobe-fallback.

### 6. Routing logic

```python
if _has_clip_db_rows(project_id):
    return _reconcile_via_db(project_dir, timing, plan, project_id)
return _reconcile_via_ffprobe(project_dir, timing, plan)
```

Correct: projects with clip_db entries use the DB path; legacy projects without entries fall through to ffprobe.

---

## Schema verification

The `clips` table has `source_beat_id TEXT NOT NULL` as a first-class column. `order_clip()` accepts it as a required parameter. `coverage_for_beat()` queries on `(project_id, source_beat_id)` — matching the parent beat ID to find all child clips.

---

## Code quality notes

- Clear separation between DB and ffprobe paths.
- Module docstring explicitly states the parent→children resolution intent.
- TOLERANCE constant (0.25s) used consistently.
- Exit code 1 on failure, 0 on success — correct CLI contract.
- No side effects on clip_db (read-only consumption).

---

## Verdict

**PASS** — All six criteria satisfied. Implementation is clean and correct.

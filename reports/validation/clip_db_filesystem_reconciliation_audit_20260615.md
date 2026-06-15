# Clip DB ↔ Filesystem Reconciliation Audit

**Date:** 2026-06-15  
**Project:** `how_to_use_ai_to_better_organize_your_de_short`  
**Failure:** `assemble` step — `ERROR: could not probe duration (missing or unreadable): .../002_proof_a/B003_B003-s0.mp4`  
**Root cause:** DB stores `.mp4` output_path for `local_graphic` clips; render_graphics writes `.png`; assemble overrides the correct manifest path with the incorrect DB path AFTER validation passes.

---

## 1. Evidence Table: DB Status vs Filesystem

All 16 clips for this project. Every `local_graphic` clip is "valid" in the DB but the `.mp4` at `output_path` does NOT exist — only the `.png` equivalent exists.

| # | clip_id (suffix) | asset_type | db_path_ext | .mp4 exists | .png exists | DB status |
|---|---|---|---|---|---|---|
| 1 | whole (B001) | generated_video | .mp4 | ✅ | ❌ | valid |
| 2 | whole (B002) | generated_video | .mp4 | ✅ | ❌ | valid |
| 3 | **B003-s0** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 4 | **B003-s1** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 5 | **B003-s2** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 6 | **whole (B003b)** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 7 | **whole (B004)** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 8 | whole (B005) | generated_video | .mp4 | ✅ | ❌ | valid |
| 9 | **whole (B005c)** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 10 | whole (B006) | generated_video | .mp4 | ✅ | ❌ | valid |
| 11 | whole (B007) | generated_video | .mp4 | ✅ | ❌ | valid |
| 12 | whole (B008) | generated_video | .mp4 | ✅ | ❌ | valid |
| 13 | **whole (B009)** | **local_graphic** | **.mp4** | **❌** | **✅** | **valid** |
| 14 | whole (B010) | generated_video | .mp4 | ✅ | ❌ | valid |
| 15 | whole (B011a) | generated_video | .mp4 | ✅ | ❌ | valid |
| 16 | whole (B011b) | generated_video | .mp4 | ✅ | ❌ | valid |

**Summary:** 7/16 clips are `local_graphic` with status=valid in DB but NO file exists at the DB's `output_path`. The actual rendered `.png` file exists at the same path with `.png` extension.

---

## 2. Hole #1 — `mark_valid` Does Not Check Filesystem

**File:** `scripts/clip_db.py` line 287

```python
def mark_valid(clip_id, validated_by='qa_media', db_path=None):
    """Mark clip as valid (QA passed)."""
    conn = get_db(db_path)
    now = _now()
    conn.execute("UPDATE clips SET status='valid', last_validated_at=? WHERE clip_id=?", (now, clip_id))
    conn.commit()
    log_access(clip_id, validated_by, "validate", db_path=db_path)
    conn.close()
```

**Defect:** Unconditionally sets `status='valid'` without:
- Checking that the file at `output_path` exists on disk
- Verifying that `actual_sha256` matches the live file
- Verifying the extension of the actual file matches `output_path`

**Contrast:** `can_reuse()` (line 223) DOES check `full_path.exists()` and verifies SHA-256. The validation logic exists in the codebase — it's just not called by `mark_valid`.

---

## 3. Hole #2 — `assert_all_valid` Never Stats Filesystem

**File:** `scripts/clip_db.py` line 378

```python
def assert_all_valid(project_id, db_path=None):
    """GATE: True only if every clip is valid with no open change requests."""
    conn = get_db(db_path)
    invalid = conn.execute(
        "SELECT clip_id, status, status_reason FROM clips WHERE project_id=? AND status != 'valid'",
        (project_id,)).fetchall()
    open_reqs = conn.execute("""
        SELECT cr.* FROM clip_change_requests cr
        JOIN clips c ON cr.clip_id = c.clip_id
        WHERE c.project_id=? AND cr.status='open'
    """, (project_id,)).fetchall()
    conn.close()

    problems = [_row_to_dict(r) for r in invalid] + [_row_to_dict(r) for r in open_reqs]
    if problems:
        return False, problems
    return True, []
```

**Defect:** This is the "golden truth gate" that assemble relies on before muxing. It:
- Only queries DB `status != 'valid'` — a pure database check
- NEVER calls `os.path.exists()` on any `output_path`
- NEVER verifies SHA-256 against the filesystem
- Passes `True` even when 7/16 files are physically absent

---

## 4. Hole #3 — Extension Mismatch Contract Violation

### 4a. Who assigns `.mp4` to local_graphic output_path

**File:** `scripts/clip_db.py` line 132 — `_canonical_path()`

```python
def _canonical_path(project_id, segment_id, production_beat_id, slot_id=None):
    """THE single path rule. All clip paths are computed here and nowhere else."""
    filename = f"{production_beat_id}_{slot_id}.mp4" if slot_id else f"{production_beat_id}.mp4"
    return f"assets/media/{project_id}/{segment_id}/{filename}"
```

This unconditionally produces `.mp4` regardless of `asset_type`. Also confirmed in `compile_media_prompts.py` line 265 and 712 — both hardcode `.mp4`.

### 4b. Who writes `.png`

**File:** `scripts/render_graphics.py` line 242

```python
png_path = abs_out.with_suffix(".png")
png_path.parent.mkdir(parents=True, exist_ok=True)
render_spec(spec, png_path)
```

Then at line 254-258, it calls `record_generated` and `mark_valid` with the SHA of the **PNG file**, but the DB `output_path` column still holds the `.mp4` path (set at `order_clip` time, never updated).

### 4c. Who expects `.mp4` and fails

**File:** `scripts/assemble.py` line 1026

```python
# Resolve media paths from the clip DB (golden truth)
for seg in segments:
    cid = seg.get("clip_id")
    if cid:
        db_path = clip_db.get_path(cid)
        if db_path:
            seg["media"] = db_path
```

`get_path()` (line 431) returns `clip["output_path"]` verbatim — the `.mp4` path that never existed on disk.

**Critical ordering flaw:** `validate_manifest` runs at line 1007 (sees the correct `.png` paths from `build_manifest.py`'s workaround, passes). Then the DB override at line 1026 REPLACES those correct paths with wrong `.mp4` paths. There is NO second validation pass after the override.

### 4d. `build_manifest.py` has a workaround (line 228-230) that assemble UNDOES

```python
is_local_graphic = (b.get("model") == "local_graphic"
                    or b.get("asset_type") == "local_graphic")
if is_local_graphic and media_path_rel.endswith(".mp4"):
    media_path_rel = media_path_rel[:-4] + ".png"
```

This correctly patches the manifest. But `assemble.py`'s "golden truth" DB override (line 1026) overwrites it, reintroducing the bug.

---

## 5. How the Failure Materializes

### Execution flow:

1. `compile_media_plan` → `clip_db.order_clip()` → DB stores `output_path = ...B003_B003-s0.mp4`
2. `generate_media` → skips `local_graphic` (only processes `generated_video`)
3. `qa_media` → skips or passes local_graphic clips (they weren't generated by Higgsfield)
4. `render_graphics` → writes `.png`, calls `record_generated` (SHA of png) + `mark_valid` → DB says valid
5. `build_manifest` → patches `.mp4` → `.png` in manifest (workaround at line 228)
6. `assemble`:
   - `validate_manifest` → sees `.png` paths → files exist → PASS
   - DB override (line 1026) → replaces with `.mp4` paths from DB
   - `assert_all_valid` → checks only DB status column → PASS
   - `measure_pace` → calls `narrative_speed.probe_duration()` on `.mp4` path
   - `probe_duration` → ffprobe on non-existent file → empty stdout → raises `FileNotFoundError("could not probe duration (missing or unreadable): ...B003_B003-s0.mp4")`

### Step ordering in `produce.py` (STEPS list, lines 31-51):

```
13. generate_media    ← skips local_graphic (model != higgsfield)
14. qa_media          ← skips or passes local_graphic
15. reconcile_duration
16. render_graphics   ← writes .png, marks DB valid with .mp4 path
17. build_manifest    ← workaround patches to .png
18. assemble          ← DB override undoes the workaround → FAIL
```

### Timestamps confirm files were written THIS run:

- `render_graphics` generated_at: `2026-06-15T16:36:45+08:00`
- PNG files exist on disk at the expected location
- The DB status is NOT stale — it was set by `render_graphics` in this session

---

## 6. Full Blast Radius: Every `mark_valid` Caller

| Caller | File:Line | Checks file exists first? |
|--------|-----------|--------------------------|
| `render_graphics.py` | 258 | ❌ No (writes .png but DB has .mp4) |
| `qa_media.py` | 494 | ❌ No (trusts QA PASS result) |
| Tests (10+ call sites) | various | N/A (test fixtures) |

| Caller of `record_generated` | File:Line | Notes |
|------|-----------|-------|
| `render_graphics.py` | 254 | SHA of .png file stored, but output_path remains .mp4 |
| `generate_media.py` | 1183 | Correct (writes actual .mp4, SHA of .mp4) |

---

## 7. The Missing Invariant

**The clip DB has no filesystem reconciliation layer.** The contract `status=valid → file exists at output_path with matching SHA-256` is never enforced. Specifically:

1. `_canonical_path` is extension-blind (always `.mp4`)
2. `mark_valid` trusts the caller without verification
3. `assert_all_valid` trusts the DB without filesystem proof
4. `get_path` returns the canonical path without checking existence
5. `assemble.py`'s DB override happens AFTER manifest validation, creating a TOCTOU-style gap

The only function that does verify is `can_reuse()` (line 223) — but it's only called by `generate_media.py` to avoid re-rendering, never by the validation gates.

---

## 8. Prioritized Fixes

### P0 — Immediate blockers (assembly cannot succeed without these)

1. **Fix `_canonical_path` to be extension-aware.** Accept `asset_type` parameter; use `.png` for `local_graphic`, `.mp4` for generated types. This is the single source of truth and must be correct.

2. **Fix `assemble.py` DB override to NOT overwrite paths for `local_graphic` clips** — OR — after the DB override loop, re-validate that all `seg["media"]` paths exist on disk before proceeding. The simplest immediate fix: apply the same `.mp4 → .png` transform that `build_manifest.py` already does, inside the DB override loop (checking asset_type from the DB clip record).

### P1 — Systemic invariant enforcement

3. **Add filesystem existence check to `mark_valid`.** Before setting status=valid, verify `(ROOT / output_path).exists()`. Optionally verify SHA match. This prevents the contradiction at the source.

4. **Add filesystem verification to `assert_all_valid`.** For each clip with status=valid, verify the file at output_path exists (and optionally SHA matches). This is the gate that protects assembly and must be authoritative.

5. **Have `render_graphics` update `output_path` in the DB** after writing `.png` — OR — have `order_clip` accept the true extension at registration time. The path stored in the DB must match what's on disk.

### P2 — Defense in depth

6. **Add a post-DB-override validation pass in `assemble.py`** that re-checks all `seg["media"]` paths exist before proceeding to `measure_pace` / rendering.

7. **Unify the validation logic**: factor the filesystem check from `can_reuse()` into a shared `verify_clip_on_disk(clip_id)` utility, and call it from both `mark_valid` and `assert_all_valid`.

---

## Summary

The defect is a **contract violation across three layers**:

- **Data layer** (`_canonical_path`): always produces `.mp4`, even for assets that will be `.png`
- **Producer** (`render_graphics`): writes `.png`, marks DB valid without correcting the path
- **Consumer** (`assemble.py`): overrides correct manifest paths with incorrect DB paths, then has no second validation pass

The "golden truth" gate (`assert_all_valid`) is purely a database status check with zero filesystem awareness, making it unable to catch this class of bug. The DB's claim of "valid" is unfalsifiable — nothing ever tests it against reality.

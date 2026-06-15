# UCI-06 Audit Report

**Date:** 2026-06-15  
**Auditor:** Kiro CLI (read-only)  
**Scope:** Phantom sub-frame beats (<0.1s) merged into neighbor, logged, never emitted as standalone clips.

---

## Findings

### 1. MIN_BEAT_SEC constant & constraint loading

- `reconcile_production_storyboard.py` line 36: `MIN_BEAT_SEC_DEFAULT = 0.1`
- Loaded from `constraints.json → lipsync_render_rules.min_beat_duration_sec` (line 47), falling back to 0.1s.
- Passed as parameter to `_merge_phantom_beats(beats, min_beat_sec)`.

### 2. `_merge_phantom_beats` implementation (lines 278–330)

**Detection:**
- Identifies phantom indices: any beat with `audio_duration_sec < min_beat_sec`.

**Merge strategy:**
- Phantom beats merge into previous neighbor (preferred), or next neighbor if phantom is first.
- Avoids merging into another phantom (chain protection).

**Applied changes per merge:**
- Extends target beat's timing to cover phantom interval (`audio_start_sec`, `audio_end_sec`, `audio_duration_sec` recalculated).
- Appends phantom's `narration_text` to target (preserves all text).
- Rebuilds target's `coverage_plan` for new duration.
- Logs: `"PHANTOM_BEAT: {id} {dur}s merged into {target_id}"`.

**Output:**
- Returns `(cleaned_beats, log_entries)` tuple — phantoms removed from list.

### 3. Integration into reconcile main flow

Lines 546–549:
```python
min_beat_sec = constraints.get("min_beat_sec", MIN_BEAT_SEC_DEFAULT)
production_beats, phantom_log = _merge_phantom_beats(production_beats, min_beat_sec)
for entry in phantom_log:
    issues.append(entry)
```

Called as Step 4b after all beat construction, before building final production storyboard. Log entries propagated to caller's issues list.

### 4. No standalone sub-frame clip possible

After `_merge_phantom_beats`, any beat < MIN_BEAT_SEC is removed from the beat list. Downstream stages (compile_media_prompts, generate_media, assemble) only see the cleaned list — no sub-frame clip can be emitted.

### 5. Inline verification

```
beats after merge: ['B003a']
sub-frame clips remaining: 0 (should be 0)
Log: ['PHANTOM_BEAT: B003b 0.01s merged into B003a']
PASS: phantom merged, no sub-frame clip
```

---

## Conclusion

UCI-06 is correctly implemented: sub-frame beats are detected, merged with preservation of narration text and timing, logged for audit trail, and never passed to downstream clip generation or assembly.

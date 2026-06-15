# Command Log — Post-TTS Corrective Sprint Validation

## Phase 1: Orchestrator Trace

```
$ python3 -c "import sys; sys.path.insert(0,'scripts'); import produce; [print(i,s) for i,s in enumerate(produce.STEPS)]"
→ 21 steps mapped (0: research → 20: gate_b_review)

$ grep -n 'fallback\|creative.*storyboard\|WARNING' scripts/produce.py
→ Line 443: explicit guard "Creative storyboard fallback is NOT permitted in production."
→ No silent fallback found; all subprocess errors raise RuntimeError.
```

## Phase 2: Serialized Runtime Proof

```
$ python3 scripts/reconcile_production_storyboard.py \
    --storyboard $P/storyboard.json \
    --timing-map $P/narration/beat_timing_map.json \
    --audio $P/narration/continuous.mp3 \
    --output $VD/prod_sb.json
→ EXIT 0: 14 production beats, 7 splits (from 3 parents), 5 multi-slot coverage

$ python3 scripts/production_storyboard.py validate $VD/prod_sb.json
→ EXIT 0: PASS

$ python3 scripts/review_production_storyboard.py \
    --production-storyboard $VD/prod_sb.json \
    --creative-storyboard $P/storyboard.json \
    --output $VD/review.json
→ EXIT 0: PASS

$ python3 -c "...compile_plan(prod, c, r, project_dir=...)..."
→ 5 errors returned, 26 assets generated
→ produce.py would raise RuntimeError("Media plan compilation failed (5 errors)")
```

## Phase 3: Timing Authority

```
$ Verified master audio SHA-256: 2a817f4fd21619dd3e1e74a26ef5bc0e123f1f566b7c6106d38e741c7486e6ce
$ All split beats: method=silence_detection, confidence=high
$ No LLM-supplied timestamps found
$ Narration word-count match: all 10 source beats TRUE
```

## Phase 4: Coverage + Negative Injection

```
$ Coverage: 26 slots, 0.0→146.599s, 0 gaps, 0 overlaps: PASS
$ Gap injection: validate exit 1 (PASS)
$ Overlap injection: validate exit 1 (PASS)
$ Missing end_sec: validate exit 1 (PASS)
$ Duplicate slot_id: validate exit 1 (PASS)
```

## Phase 5-7: Repair, Graphics, State

```
$ Repair wired in produce.py: lines 364-368
$ STEP_ARTIFACTS includes production_storyboard, review_report, media_plan
$ Graphics carried as 'graphics' (plural) — NOT consumed by compile_beat (reads 'graphic' singular)
$ 6 required graphics silently lost at compile boundary
```

## Phase 9: Audited Preview

```
$ python3 scripts/qa_final.py $P/using_ai_to_help_memory_retention_short_16x9.mp4
→ EXIT 1:
  ✗ CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s
  ✗ LENGTH_MISMATCH: video 83.3s vs audio 146.6s
  ✗ TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s
```

## Phase 10: Full Regression

```
$ python3 -m pytest -q
→ 500 passed in 111.82s

$ python3 -m pytest tests/test_serialized_handoff.py tests/test_coverage_geometry.py \
    tests/test_split_narration_graphics.py tests/test_orchestrator_ordering.py \
    tests/test_repair_integration.py -v
→ 42 passed in 14.50s
```

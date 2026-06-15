# Command Log — Post-TTS Corrective Re-Validation

Date: 2026-06-14T18:52+08:00

## 1. Reconcile Production Storyboard
```
$ python3 scripts/reconcile_production_storyboard.py --storyboard $P/storyboard.json --timing-map $P/narration/beat_timing_map.json --audio $P/narration/continuous.mp3 --output $VD/prod_sb.json --dry-run
Reconciliation complete: 14 production beats
  Master audio: 146.599s
  Split beats: 7 (from 3 parents)
  Multi-slot coverage: 5 beats
[DRY-RUN] Writing preview output...
reconcile exit: 0
```

## 2. Validate Production Storyboard
```
$ python3 scripts/production_storyboard.py validate $VD/prod_sb.json
PASS — production storyboard is valid.
validate exit: 0
```

## 3. Review Production Storyboard
```
$ python3 scripts/review_production_storyboard.py --production-storyboard $VD/prod_sb.json --creative-storyboard $P/storyboard.json --output $VD/review.json
PASS — production storyboard review passed.
review exit: 0
```

## 4. Compile Guard (THE DECISIVE TEST)
```
$ python3 -c "[compile_plan replication]"
compile clean, assets: 26
assets carrying graphics: 26
compile guard exit: 0
```

## 5. Fix Verification — Warnings & Graphics
```
plan warnings: 13
  warn: TEXT_SURFACE_POLICY: beat B001 hero_cutaway neutralized 'notebook' in negative_prompt
  warn: TEXT_SURFACE_POLICY: beat B003 rerouted to local_graphic (visual_brief contains 'laptop screen')
  warn: TEXT_SURFACE_POLICY: beat B005 rerouted to local_graphic (visual_brief contains 'notebook')
  warn: TEXT_SURFACE_POLICY: beat B007 rerouted to local_graphic (visual_brief contains 'laptop screen')
  warn: TEXT_SURFACE_POLICY: beat B009 hero_cutaway neutralized 'notebook' in negative_prompt
  warn: B001: reference ... not in active set 'navy_sweater_library' — wardrobe/identity drift risk (x3)
total assets: 26
with graphics: 26
```

## 6. Narration Immutability & Coverage
```
narration all match: True
coverage: 0.0 -> 146.599 master 146.599
needs_repair: []
```

## 7. Costing Completeness
```
total beats: 26
all have cost: True
total est_usd: $17.60
total est_credits: 360.0
budget_cap_usd: 60.0
```

## 8. Defective MP4 Still Fails
```
$ python3 scripts/qa_final.py .../using_ai_to_help_memory_retention_short_16x9.mp4
  ✗ CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s
  ✗ LENGTH_MISMATCH: video 83.3s vs audio 146.6s
  ✗ TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s
qa_final exit: 1
```

## 9. Full Test Suite
```
$ python3 -m pytest -q
507 passed in 111.11s
```

## 10. Failure Injection
```
gap_injection,REJECTED
overlap_injection,REJECTED
narration_mutation,REJECTED
missing_shot_type,REJECTED
all_rejected: True
```

## 11. Side Effects Check
```
git status shows only PTC-FIX committed changes (31 files, +1963/-1039).
No untracked artifacts outside reports/validation/.
No .env, runtime.env, or credential changes.
```

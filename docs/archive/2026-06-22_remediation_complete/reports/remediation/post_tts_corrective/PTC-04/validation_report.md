# PTC-04 Validation Report

**Ticket:** PTC-04  
**Date:** 2026-06-14  
**Result:** PASS

---

## Validation Matrix

| # | Requirement | Method | Result |
|---|-------------|--------|--------|
| 1 | Repair wired into produce.py | grep + code read (lines 364-368) | ✅ PASS |
| 2 | Review invoked with --output | grep produce.py line 404 | ✅ PASS |
| 3a | No-audio → exit 1 (unresolved beats) | CLI run, 3 needs_repair beats, exit 1 | ✅ PASS |
| 3b | With-audio → exit 0 (all resolved) | CLI run, 0 needs_repair beats, exit 0 | ✅ PASS |
| 4 | Invalid output not promoted | Code read (lines 628-633), test_invalid_output_not_promoted | ✅ PASS |

---

## Evidence

### Exit code verification

```
# Without audio (no measured boundaries → cannot split)
$ python3 scripts/reconcile_production_storyboard.py \
    --storyboard .../storyboard.json --timing-map .../beat_timing_map.json \
    --output /tmp/ptc04_noaudio.json --dry-run
  Needs LLM repair: 3 (B006, B008, B010)
  Validation errors: 3
  EXIT: 1

# With audio (reroute resolves all)
$ python3 scripts/reconcile_production_storyboard.py \
    --storyboard .../storyboard.json --timing-map .../beat_timing_map.json \
    --audio .../continuous.mp3 --output /tmp/ptc04_audio.json --dry-run
  Total beats: 14, Unresolved: 0
  EXIT: 0
```

### Integration tests

```
tests/test_repair_integration.py: 6 passed
Full suite: 455 passed in 100.49s
```

---

## Verdict

**PASS** — PTC-04 is correctly implemented. Repair is wired, review uses --output, CLIs fail-closed on unresolved beats, and invalid output is never promoted over valid.

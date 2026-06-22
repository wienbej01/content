# PTC-10 Validation Report — Corrected Preview + Exit Gate

**Validator:** Kiro (automated)  
**Date:** 2026-06-14T18:17+08:00  
**Method:** Direct execution + code inspection (read-only)

## Validation Commands Executed

```bash
# 1. Preview artifacts exist
ls reports/remediation/post_tts_corrective/audited_project_preview/
# Result: 6 files (storyboard, media_plan, review_report, reconciliation, coverage CSV, field CSV)

# 2. Validate preview storyboard
python3 scripts/production_storyboard.py validate .../production_storyboard.preview.json
# Result: "PASS — production storyboard is valid." Exit: 0

# 3. Coverage geometry: 0→146.599, contiguous, no unresolved
python3 -c "<contiguity check>"
# Result: first=0.0, last=146.599, master=146.599, max gap ≤0.042, needs_repair=[]

# 4. Defective MP4 still fails
python3 scripts/qa_final.py .../using_ai_to_help_memory_retention_short_16x9.mp4
# Result: 3 issues detected, Exit: 1

# 5. Full test suite green
python3 -m pytest -q
# Result: 500 passed in 112.39s
```

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Preview artifacts valid | ✅ | 6 files present, validator PASS |
| B001 resolved | ✅ | Rerouted to hero_cutaway, needs_repair=false |
| B008 resolved | ✅ | Split 3-way at silence, needs_repair=false |
| B009 resolved | ✅ | Rerouted to hero_cutaway, needs_repair=false |
| Coverage 0→146.599 | ✅ | first=0.0, last=146.599, master=146.599 |
| No gaps > 1 frame | ✅ | Contiguity verified (all gaps ≤0.042s) |
| Defective MP4 fails (exit 1) | ✅ | 3 issues, exit 1 |
| Review passes | ✅ | status=PASS, blocks_production=false |
| Rounding fix doesn't weaken gates | ✅ | Validator + coverage gap test still enforced |
| Reviewer scoping doesn't weaken gates | ✅ | Default=explainer, all bands unchanged |
| Narration mutation still fatal | ✅ | Fingerprint test passes (SHA-256 detection) |
| Full suite green | ✅ | 500 passed |

## Gate Strength Confirmation

| Gate | Before PTC-10 | After PTC-10 | Weakened? |
|------|---------------|--------------|-----------|
| Coverage geometry (contiguous timeline) | FRAME_TOLERANCE=0.042 | FRAME_TOLERANCE=0.042 | No |
| Narration mutation detection | SHA-256 fingerprint | SHA-256 fingerprint | No |
| Shot-mix bands (explainer) | hero 25-40%, broll ≥25%, etc. | Identical (video_type default="explainer") | No |
| Graphics ≥10% | Always enforced | Always enforced (even for shorts) | No |
| Model duration limits | max=10s + FRAME_TOLERANCE | max=10s + FRAME_TOLERANCE | No |
| qa_final defective detection | exit 1 on mismatch | exit 1 on mismatch | No |

## Result

**VALIDATED** — Corrected preview is valid, B001/B008/B009 resolved, full coverage, defective MP4 still caught, no gate weakening from code fixes.

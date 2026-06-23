# Failure Analysis: Seed #7 / prod_2f9bb58c0508465fb51ac6b4578bba92

## Error
Gate 1 FAIL: Final video duration 56.6s exceeds 20-40s target.

## Findings
- Word count: 34 (within [20,40] budget) ✅
- Shot mix: 3 hero, 2 broll, 1 graphic ✅
- Hero lipsync alignment: all within 500ms ✅
- Render unit required durations sum: ~35.7s (within 20-40s)
- Final assembled duration: 56.6s (extra ~21s from assembly/transitions/graphics)

## Classification
- [ ] Code bug (pipeline logic) → fix code, re-run
- [x] Content issue (script timing, assembly padding) → retry stage
- [ ] External dependency (Higgsfield, ElevenLabs) → retry with backoff
- [ ] Test gap (missing test coverage) → write test, fix code

## Action
Re-create the production to get fresh LLM-generated script and timing.

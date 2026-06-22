# Sprint 7 — Validator Report

- **Agent:** Agent 9 (Independent Validator)
- **Sprint:** Sprint 7 (DB-Native FFmpeg Assembly and Final QA)

## Sprint 7 exit gate (per program Section 17)

| Gate | Status |
|---|---|
| valid 45-second local video assembled | PASS — 17 test_assemble tests pass with real FFmpeg |
| one master narration source | PASS — exactly one tts_master artifact verified |
| no provider narration in final mix | PASS — diagnostic audio tagged eligible_for_final_narration=False |
| no hero temporal violations | PASS — ffmpeg_validator rejects all forbidden ops; unknown ops fail-closed |
| all final QA evidence bound to deliverable SHA | PASS — QA evidence stores deliverable SHA; changed deliverable invalidates prior QA |

## Hero temporal policy verification
- Forbidden: atempo, setpts (non-identity), loop, reverse, tpad (freeze), minterpolate (interp), trim through speech
- Forbidden flags: -itsoffset, -stream_loop, -vsync
- Identity setpts (PTS-STARTPTS) permitted
- Unknown filters fail-closed for HERO_SYNC_LOCKED
- BROLL_FLEX allows unknown filters (not fail-closed) but atempo still banned globally

## Assembly DTO verification
- Built exclusively from DB (no JSON fallback)
- Missing render unit → AssemblyDTOValidationError
- Master narration artifact referenced from DB

## FFmpeg validator fix
- Fixed duplicate `_check_filter_names` function (second definition was shadowing first)
- Added minterpolate, freeze, settb to forbidden filters
- Added -stream_loop to forbidden flags

## Suites run
```
python3 -m pytest tests/contracts/ tests/test_assemble.py tests/test_assemble_lb202.py \
  tests/unit/test_hero_temporal_edit_guard.py tests/test_sprint7_assemble_db.py -q
→ 143 passed
```

## Verdict
**VALIDATOR PASS**

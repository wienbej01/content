# TKT-02 Audit Report

**Verdict: PASS**

---

## 1. `scripts/qa_final.py` — Stream-Level Probing

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `_video_duration()` probes `v:0` stream, NOT format | PASS | Line 40-42: `-select_streams v:0 -show_entries stream=duration` |
| Fallback via nb_frames/fps | PASS | Lines 49-61: parses `nb_frames,r_frame_rate`, returns `nb_frames / fps` |
| Tolerance is 0.25s | PASS | Line 31: `length_tol_sec: 0.25`, `tail_tol_sec: 0.25` |
| All three durations logged in report | PASS | Lines 196-198: `video_duration`, `audio_duration`, `container_duration` all in report dict |
| TERMINAL_FREEZE: audio outlasts video >0.25s → FAIL | PASS | Lines 191-193: `if adur - vdur > t["length_tol_sec"]` → appends TERMINAL_FREEZE issue |
| CONTAINER_MISMATCH: container - video >0.25s → FAIL | PASS | Lines 180-182: `if cdur - vdur > t["length_tol_sec"]` → appends CONTAINER_MISMATCH issue |
| NO_FRAMES: zero/missing frame count → FAIL | PASS | Line 164: `if frames is None or frames == 0` → appends NO_FRAMES issue |
| Exit code 1 on any issue | PASS | Line 249: `return 0 if ok else 1`; Line 252: `raise SystemExit(main())` |
| `final_qa_report.json` written beside video by default | PASS | Line 244: `output_path = args.output or str(Path(args.video).parent / "final_qa_report.json")` |

## 2. `scripts/produce.py` — Pipeline Integration

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `qa_final` step between `assemble` and `gate_b_review` | PASS | STEPS list lines 46-48: `"assemble"`, `"qa_final"`, `"gate_b_review"` |
| `step_qa_final` raises RuntimeError on non-zero exit | PASS | Line 380: `if r.returncode != 0: ... raise RuntimeError(...)` |
| Gate B cannot be reached without qa_final passing | PASS | Sequential STEPS execution; RuntimeError halts pipeline before `gate_b_review` (line 48) |

## 3. `tests/test_qa_final.py` — Test Coverage

| Criterion | Status | Evidence |
|-----------|--------|----------|
| `test_existing_defective_mp4_fails` uses ACTUAL audited MP4 | PASS | Line 10: path = `Videos/Projects/using_ai_to_help_memory_retention_short/...16x9.mp4` |
| Tests call production qa_final.py via subprocess | PASS | `_run_qa()` lines 16-19: subprocess invocation of `scripts/qa_final.py` |
| No dummy/silent fallbacks | PASS | All tests assert exit codes and report content; `skipif` only if MP4 absent |
| Valid pass test | PASS | `test_valid_fixture_passes` (line 28) |
| Short video + long audio | PASS | `test_short_video_long_audio_fails` (line 38) |
| No video stream | PASS | `test_no_frames_fails` (line 55) |
| Container mismatch | PASS | `test_container_exceeds_video_fails` (line 67) |
| Defective real MP4 | PASS | `test_existing_defective_mp4_fails` (line 79) — asserts video ~83s, audio ~146s, mismatch ~63s |

## 4. Negative Checks (Silent Degradation, Bypasses)

| Check | Status | Notes |
|-------|--------|-------|
| No code path turns failure into warning | PASS | `run_final_qa` returns `(report, not issues)` — any issue = fail |
| No format duration used as video duration | PASS | `_video_duration()` exclusively probes `v:0` stream; `_container_duration()` is separate |
| nb_frames check implemented | PASS | `_video_frame_count()` at line 78 + check at line 164 |
| Tolerance tightened to 0.25s | PASS | Hardcoded at line 31-32 |
| `_in_exempt()` does NOT affect TERMINAL_FREEZE | PASS | Exempt only used in freeze-span loop (line 168); TERMINAL_FREEZE (line 191) runs unconditionally |
| Gate B blocked if qa_final fails | PASS | RuntimeError at line 380 halts orchestrator |

## 5. Early Proof Command

```
$ python3 scripts/qa_final.py Videos/Projects/.../using_ai_to_help_memory_retention_short_16x9.mp4
  ✗ CONTAINER_MISMATCH: container 146.6s vs video stream 83.3s (delta 63.3s > 0.25s tolerance)
  ✗ LENGTH_MISMATCH: video 83.3s vs audio 146.6s (delta 63.3s > 0.25s tolerance)
  ✗ TERMINAL_FREEZE: video EOF at 83.3s but audio continues to 146.6s (audio outlasts video by 63.3s)
Exit: 1
```

- video_duration: 83.33s ✓ (expected ~83.333)
- audio_duration: 146.6s ✓ (expected ~146.600)
- mismatch: 63.27s ✓ (expected ~63.267)
- exit code: 1 ✓

## 6. Test Suite Results

- `tests/test_qa_final.py`: **5/5 passed**
- Full suite (excl. unrelated `test_review.py`): **282 passed**
- `test_review.py` has 4 pre-existing failures unrelated to TKT-02 (review_loop API mismatch — separate untracked file)

---

## Summary

All acceptance criteria met. The Engineer's implementation correctly probes `v:0` stream duration, detects the defective MP4 with exact expected values, blocks Gate B on failure, and has comprehensive test coverage.

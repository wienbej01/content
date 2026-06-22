# End-to-End Smoke Loop — Architecture & Rationale

**Created:** 2026-06-22
**Purpose:** Systematically harden the 19-stage pipeline by running 25 short smoke productions and fixing every failure at its root.

---

## Why This Approach

The previous approach — running a single production, fixing one bug, resuming, hitting the next bug — is not sustainable. Each fix addresses a symptom, but the next stage reveals another gap. The pipeline was designed in layers and never stress-tested end-to-end with diverse inputs.

This plan executes **25 diverse smoke productions** (25-second teasers with mixed shot types). Each failure is analyzed with the 3-Why method, a regression test is written, and an Engineer-Auditor-Validator loop ensures the fix is correct, minimal, and tested. By seed #25, the pipeline will have been hardened against the most common failure modes.

## Key Design Decisions

**⚠️ LIVE SMOKE TEST — All stages use real, billable API calls. No mocks. No test data. No dry-run.**

### Why 25 seconds?
Short enough to render quickly, long enough to exercise the full pipeline (research → storyboard → TTS → audio_timing → compile → generate → QA → repair → graphics → assemble → publish). A 25s video requires at least 4-6 render units across hero, b-roll, and graphics.

### Why 25 seeds?
Diverse inputs exercise different code paths. Some seeds will produce more hero shots, others more b-roll or graphics. Running 25 seeds with different content ensures broad coverage.

### Why auto-approve gates?
Gate A (content approval) and Gate A (spend cap) are designed for human-in-the-loop in production. During smoke testing, they add no value — they just block the pipeline. Auto-approve them so the pipeline can flow.

### Why a pass gate test for every fix?
Without a regression test, future changes can reintroduce the same bug. Each fix MUST have a unit test that reproduces the failure and passes after the fix.

### Why stop on every failure?
If we keep running after a failure, we accumulate unfixed bugs. Each failure gets root-caused and fixed before the loop continues. This ensures the pipeline gets progressively more robust.

## Live API Policy (EXPLICIT)

**This is a LIVE smoke test.** Every stage uses real, billable API calls:

| Stage | Provider | Type |
|-------|----------|------|
| `tts` | ElevenLabs | Real TTS audio generation |
| `generate_media` | Higgsfield Seedance 2.0 | Real hero lipsync video |
| `generate_media` | Higgsfield Kling 3.0 | Real b-roll video |
| `graphics_compositing` | render_graphics.py | Real PIL/Pillow compositing |
| `assemble` | FFmpeg | Real encoding, loudnorm |

**ABSOLUTELY FORBIDDEN:**
- `YT_TEST_MODE=1` — would skip TTS with pre-provided audio
- `HIGGSFIELD_DRY_RUN=1` — would skip video generation
- Any mock/fake/stub adapter

## ## Expected Bug Categories

Based on the errors observed so far, bugs will fall into these categories:

| Category | Example | Expected fixes needed |
|----------|---------|----------------------|
| Stage completion checks | generate_media blocks on units it can't handle (failed, local_graphic) | 2-3 |
| Provider boundary | Paid provider called for forbidden assets | 0 (already hardened) |
| Timing/conversion | ms→samples rounding, duration mismatches | 0 (already hardened) |
| Assembly constraints | Timeline heuristics reject valid sequences | 1-2 |
| State machine gaps | Repair doesn't see certain failure states | 2-3 |
| Config limits | Caps too low for real productions | 0 (already raised) |
| External dependencies | Higgsfield/ElevenLabs failures | 3-5 (retry/resilience) |

## Files in This Plan

```
docs/plans/e2e_smoke_loop/
├── _CONTEXT.md         ← this file
├── smoke_config.yaml   ← smoke test configuration
├── SEEDS.md            ← 25 seed topics
└── PROCEDURE.md        ← step-by-step executable playbook
```

## Post-Loop State

After all 25 seeds complete successfully:
- The test suite will have grown by 10-25 new tests
- 5-15 bugs will have been root-caused and fixed
- The pipeline will handle mixed shot types, provider failures, timing edge cases, and assembly constraints
- A final report in `smoke_logs/` will document all fixes, test coverage, and remaining known issues

## Commands Quick Reference

```bash
# Create a smoke production
python3 scripts/produce_db.py create --seed "<topic>" --format teaser

# Run/resume (auto-approve gates first)
python3 scripts/produce_db.py approve <id> gate_a_content --pass
python3 scripts/produce_db.py approve <id> gate_a_spend --pass  
python3 scripts/produce_db.py run <id>

# Check status
python3 scripts/produce_db.py status <id>

# Run full test suite
python3 -m pytest tests/unit tests/integration tests/regression -v
```

# POC Short — Corrected Pipeline Spec (verified ground truth)

**Date:** 2026-06-13
**Trigger:** User review of `flagship_001_short_16x9.mp4` — all defects confirmed by ffprobe.
**Decision:** Build a NEW purpose-written ≤3-min script + storyboard. Do NOT retrofit the flagship. No paid render until a short passes a REAL final-cut gate.

## Verified defects in the assembled short (ffprobe-confirmed)

| Defect | Evidence | Why it shipped |
|--------|----------|----------------|
| Audio timbre drop hero→broll | manifest `narration_mode=SEGMENT` | Assembled in segment mode — R2 continuous-master path BYPASSED |
| Freeze 42.6s → +50.5s | `freeze_start: 42.624, freeze_duration: 50.54` | B-roll clip shorter than narration; assembler held last frame (NO looping, but froze) |
| Black frame 26.6s + others | `black_start:26.66`, `6.41`, `93.16` | Gap/transition artifacts between segments |
| No graphics/overlays | B007/B008 produced 0 files | Graphics RENDERING stage does not exist (only beat injection) |
| Generic b-roll, hovering pen | prompts lack specificity | B-roll prompts not forced to be specific/action-verb |
| QA rubber stamp | `media_qa` gate = SOURCE scope only | No assembled-scope freeze/black gate ran on final cut |

## What the sprint ACTUALLY delivered vs. what's still missing

DELIVERED & WORKING (verified in tests):
- R1 perceptual checks (blank/frozen) — but only wired to SOURCE scope
- R2 continuous-master assembly code — exists but was bypassed by the hand-built segment manifest
- R3 lipsync split at 10s
- R4 stutter pre-filter
- B2/B3 prompt dedup + narration overlap

STILL MISSING (this is the real remaining work):
1. **Assembled-scope final-cut gate** — freeze/black/length-mismatch detection on the OUTPUT mp4, blocking delivery. (R1 must extend to assembled scope.)
2. **Graphics rendering stage** — a renderer that turns graphic/kinetic beats into actual overlay PNG/MOV assets (lower-thirds, stat callouts, Forgetting-Curve chart) timed to audio.
3. **B-roll prompt specificity** — storyboard/compile must force concrete nouns (Ebbinghaus, 1885, 67%) + action verbs.
4. **Continuous-master as the ONLY assembly path for finals** — remove the segment-mode escape hatch for delivery.
5. **B-roll duration ≥ narration span** — generate b-roll to cover its audio, never freeze.

## POC acceptance (must ALL pass before any flagship spend)
- One ≤3-min video, purpose-written script.
- Single continuous ElevenLabs master (one API call), sliced after.
- Every b-roll clip ≥ its narration span (no freeze).
- ≥3 graphic overlays rendered + composited (stat, principle, date).
- B-roll prompts cite specific nouns + action verbs.
- Final-cut gate PASSES: no freeze >1.5s, no black frame outside transitions, audio==video length.
- Human approves the final cut.

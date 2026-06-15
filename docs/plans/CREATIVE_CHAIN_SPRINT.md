> **✅ SPRINT COMPLETE (2026-06-14)** — All tickets implemented and integrated into
> `scripts/produce.py`, the single-command production orchestrator. The review loop,
> reviewer cast, feedback-driven revision, and compliance checks are all live.
> See **docs/PIPELINE.md** for the authoritative pipeline documentation.

# Sprint Plan — LLM Creative Chain + Reviewer Cast + Feedback Loop

**Date:** 2026-06-13
**Goal:** Rebuild the creative pipeline so the LLM owns script → storyboard → critique (with a
revise→re-review feedback loop), and Python owns compliance + mechanical production. Grounded in
the bibles + source text. Audience reviewer is primary, scored on YTextract watch/save/share.
**Approved scope:** reviewer cast + placement (this doc §2), retention split (LLM-judgment vs
enforced-rule per RETENTION_MECHANICS_SPEC.md). Build reviewers+loop first; show Round 1.

## 0. Architecture (target state)

```
content brief ─▶ [LLM] SCRIPT WRITER ──▶ script.json
                          │
                          ▼
            [LLM] SCRIPT REVIEW (Audience*, Brand-Voice)  ◀── feedback loop (max 2)
                          │  (fixes → writer revises → re-review)
                          ▼  PASS
            [LLM] STORYBOARD DIRECTOR (bibles + source) ──▶ storyboard.json
                          │
                          ▼
   [LLM] STORYBOARD REVIEW (Audience*, Filmmaker, Visual-Director, Technical) ◀── loop (max 2)
                          │  (fixes → director revises → re-review)
                          ▼  PASS
            [PYTHON] retention_rules validator (≤5s hold, motion-intro, multi-shot)
                          ▼
            [PYTHON] compile → generate → upscale → QA → assemble (+retention injections)
                          ▼
            [PYTHON] qa_final gate → human endorse
```
`*` = Audience is the highest-weighted reviewer at BOTH stages (veto power on hard blocks).

## 1. Reviewer personas (prompt files in docs/reviewer_prompts/)

| File | Stage | Remit (NO overlap) | Weight |
|------|-------|--------------------|--------|
| `audience.md` (REWRITE) | script + storyboard | YTextract: hook(3s open loop, delivers title promise), reason-to-stay every ~20-30s, save-worthy(useful), share-worthy(feeling), payoff lands. The 3 publish questions. | 2.0 (primary) |
| `brand_voice.md` (NEW, replaces universe.md) | script | James voice, on-brand, claims sourced (≥ verified), no hype, no forbidden language patterns | 1.2 |
| `filmmaker.md` (REWRITE → storyboard) | storyboard | shot rhythm, visual arc, push-ins at insight, cut pacing, energy curve, motion | 1.5 |
| `visual_director.md` (NEW) | storyboard | era/anachronism, James+studio fidelity, b-roll grounded-in-source+specific+in-motion, graphic LAYOUT (integrated not slide), continuity/seed-lock | 1.5 |
| `technical.md` (REWRITE → storyboard) | storyboard | generatability (seedance/kling), audio policy per beat, reference assignment, durations (≤6s broll/≤10s hero), assembly-readiness | 0.8 |
| ~~`audio.md`~~ (REMOVE) | — | speakability now handled by chunk-and-stitch + normalize_pacing (no reviewer needed) | — |

## 2. Tickets

### Phase 1 — Reviewer cast + aggregation (LLM judgments)
- **T1. Rewrite `audience.md`** around YTextract watch/save/share + 3 questions + hook/open-loop/reason-to-stay. Structured JSON output (scores 1-5 per dimension, blocking_issues, recommended_fixes, may_proceed). Works on BOTH a script and a storyboard (input-type aware).
- **T2. `brand_voice.md`** (new, script-stage) — voice + sourcing + forbidden-language.
- **T3. `visual_director.md`** (new, storyboard-stage) — era/James/studio/b-roll/graphic-layout/continuity, bible-referenced.
- **T4. Rewrite `filmmaker.md`** + **`technical.md`** to operate on the STORYBOARD (their inputs now exist), not the script.
- **T5. `review.py` generic reviewer runner** — runs a named persona set against an artifact (script OR storyboard), weighted aggregation (audience veto + threshold), emits aggregated report with all `recommended_fixes`. Replaces/refactors review_script.py's aggregation; keeps R4 deterministic stutter pre-filter for scripts.

### Phase 2 — Feedback loop (the gap)
- **T6. `revise_with_feedback()`** — an LLM call that takes (artifact + aggregated reviewer fixes + bibles/source) and returns a REVISED artifact. One for script (writer revises), one for storyboard (director revises).
- **T7. Loop controller** in the runner: create → review → if fail/low: revise → re-review → repeat (max 2) → else escalate to human with the trail. Log every round to `<project>/review_rounds/`.

### Phase 3 — LLM authors
- **T8. `write_script.py`** (new) — LLM script writer from content brief + source + bibles + SCRIPT_PROMPT_LIBRARY. (so the script-side loop has an author).
- **T9. `direct_storyboard.py`** (built) — wire its critic pass to use the new reviewer cast + the loop (replace the inline critic with T5/T6/T7).

### Phase 4 — Enforced retention rules (Python, per RETENTION_MECHANICS_SPEC §B)
- **T10. `retention_rules.py`** storyboard validator — ≤5s visual-hold, motion-intro, multi-shot b-roll, open-loop-present.
- **T11. Assembly injections** — zoom-punch pattern interrupts, SFX-on-overlay (stub asset), end-screen window, music duck −18dB.

### Phase 5 — Integration + the POC re-run
- **T12.** Run the full chain on poc_short_focus; show Round-1 (creation + review comments) at the script stage, then storyboard stage.

## 3. Build order (per owner: reviewers+loop first, see Round 1)
1. T1-T5 (personas + runner)  ← **build now**
2. T6-T7 (revise + loop)
3. **CHECKPOINT: run Round 1 on the existing approved script → show creation + reviewer comments** ← what you asked to see
4. T8 (script writer), T9 (director wired to loop)
5. T10-T11 (retention rules + injections)
6. T12 (full POC re-run)

## 4. Definition of done
- Reviewer cast rewritten, no overlapping remits; audio persona removed.
- Audience reviewer scored on YTextract metrics, highest weight, both stages.
- Feedback loop: author revises from reviewer fixes, max 2 rounds, human escalation, full trail logged.
- Retention enforced rules validate the storyboard + inject in assembly.
- Tests for: each persona's JSON contract (stubbed LLM), the loop controller (revise→re-review→escalate), the retention validator (≤5s hold / motion-intro / multi-shot).
- Round-1 review output shown to owner before full chain runs.

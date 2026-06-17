# Rectification Plan — Sprints R7 + R8 + R9

**Theme:** B-roll semantic contract (R7); prompt compiler, diversity & text-safe assets (R8); B-roll runtime QA & repair (R9).
**Depends on:** R6 complete (real hero QA; production no longer blocked by hero placeholders).
**Governance:** Coder → Auditor → Validator; reports under `reports/remediation/rectification/<TICKET-ID>/`.
**Audit note:** "Do not begin semantic B-roll work yet" until R0–R6 land. These sprints are `NOT IMPLEMENTED` in the audited branch — this is greenfield, not rectification.

---

## Context

The hero/lipsync path is the audited branch's focus; B-roll is largely absent of semantic intent. R7–R9 add the contract that every B-roll unit must carry informational purpose, a prompt compiler that prevents cliché/duplicate concepts and never delegates exact text to generative video, and runtime QA that rejects technically-valid-but-irrelevant B-roll. These build on the DB-native render-unit model (R2) and the structured FFmpeg/compositing work (R5).

**Hard rule (`.kiro/rules/no-hacks.md`):** semantic acceptance is enforced in code + DB constraints, not by reviewer goodwill.

## Touch points

| Area | Module | Sprint |
|---|---|---|
| Storyboard semantic fields | `storyboard.py` / `production_storyboard.py`, schemas/ | R7-001 |
| Render-mode routing | `shot_router.py` | R7-002 |
| Prompt compilation | `compile_media_prompts.py` | R8-001 |
| Deterministic graphics | `render_graphics.py` | R8-004 |
| Text policy enforcement | `production_repo.validate_text_policy` (R2) | R8-006 |
| Render-unit constraints | migrations (R2-001) + `production_repo` | R7-004 |

---

## Sprint R7 — B-Roll Semantic Contract

- **R7-001** storyboard semantic fields + constraints.
- **R7-002** render-mode router (decides generative video vs. deterministic graphic vs. post-composite screen).
- **R7-003** context / cliché quotas.
- **R7-004** migration/backfill + authoring-prompt update.

Every B-roll unit must define: visual function, narrative claim, information to show, viewer takeaway, required action, forbidden clichés, distinctness requirement, text policy, render mode, semantic acceptance criteria. All persisted as constrained render-unit fields (extend R2-001 migrations + repo validators).

**Exit:** no B-roll request compiles without informational purpose and a safe render mode.

## Sprint R8 — Prompt Compiler, Diversity & Text-Safe Assets

- **R8-001** action-specific prompt compiler (purpose → prompt, not boilerplate).
- **R8-002** semantic + visual memory (reject repeated concepts before spend).
- **R8-003** prompt preflight (validate against policy + memory pre-spend).
- **R8-004** deterministic graphics (exact text rendered, never generated).
- **R8-005** post-composite screen/page workflow (UI/screens composited deterministically over plate).
- **R8-006** text-policy runtime enforcement (R2 `validate_text_policy` on the live path).

**Exit:** repeated laptop/notebook concepts rejected before spend; exact text never delegated to generative video; deterministic graphic text exact; post-composite stable.

## Sprint R9 — B-Roll Runtime QA & Repair

- **R9-001** semantic relevance evidence (does the clip show the claimed information?).
- **R9-002** duplicate detection (visual near-duplicate across the episode).
- **R9-003** gibberish / malformed-object detection.
- **R9-004** cause-specific repair routing (reuse R6-004 repair service with B-roll causes).

**Exit:** technically valid but irrelevant or repetitive B-roll cannot pass.

---

## Verification

```bash
# R7: compiler refuses purpose-less B-roll
python3 -m pytest tests/contracts/test_broll_semantic_contract.py -q
# R8: duplicate concept + text-delegation rejected pre-spend
python3 -m pytest tests/contracts/test_prompt_compiler*.py tests/contracts/test_text_policy*.py -q
# R9: irrelevant/duplicate/gibberish B-roll fails QA; routes a repair
python3 -m pytest tests/integration/test_broll_runtime_qa.py -q
```

## Risks
- Semantic relevance + duplicate detection likely need an embedding/vision model — same licensing/CI weight-caching concerns as R6-002; confirm model choice before R9-001/002.
- Scope is genuinely new feature work; estimate larger than the rectification sprints. Recommend planning R7–R9 in a separate detailed pass once R0–R6 are green.

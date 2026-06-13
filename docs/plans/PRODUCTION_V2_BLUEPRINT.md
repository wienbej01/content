# PRODUCTION V2 BLUEPRINT — Directorial Layer, Gated Spend, Gold-Star Shot Mix

**Author:** Fable (executive producer / systems architect pass)
**Date:** 2026-06-12
**Status:** AUTHORITATIVE implementation blueprint for Opus + Sonnet. Supersedes the advisory storyboard path described in `PIPELINE_IMPLEMENTED.md` stages 6–9.
**Inputs digested:** `inspi/failed001.md`, `inspi/MITmonk.md`, `docs/PIPELINE_GAPS_AND_PENDING_STEPS.md`, `docs/PIPELINE_IMPLEMENTED.md`, `docs/REVIEW_AND_QUALITY_SYSTEM.md`, `docs/ARCHITECTURE.md`, `scripts/generated/flagship_001_learn_half_time.json`, `Videos/Projects/flagship_001_learn_half_time/manifest.json`, `configs/james/model_routing.yaml`, `docs/channel_universe/constraints.json`.

---

# 1. Executive Diagnosis

## What actually happened in flagship 001

The failure was not the avatar API and not the script. The script follows the master narrative formula correctly (hook → Ebbinghaus → Roediger/Karpicke → 3-principle framework → AI application → identity close). The failure is in the generation path:

1. **`visual_brief` is segment-scoped, and every segment's brief described the same shot.** All 9 segments in `flagship_001_learn_half_time.json` carry a `visual_brief` that is a variation of "James medium close-up at mahogany desk, bookshelves, brass lamp." There is no beat-level visual differentiation anywhere in the production data.
2. **`generate_media.py` chunked narration duration into N × 5.04s clips of that one prompt.** Segment `004_wrong_approach` (160 words) became 19 nearly identical James close-ups. Total: 151 clips, ~$70-80 of Higgsfield credits, rendering the same shot over and over.
3. **None of those 151 clips were lipsynced.** Only `001_hook` used seedance lipsync. The other 150 clips show James's face with arbitrary mouth motion while ElevenLabs narration plays over the top. A face on screen with wrong mouth movement reads as "lipsync badly off" — it is actually *no* lipsync at all, which is worse.
4. **Every quality system that could have caught this was advisory.** `review_storyboard.py`, `review_script.py`, `review_media_plan.py`, `qa_media.py` all exist and all produce reports nobody is required to read. `storyboard.py` output is not consumed by `generate_media.py`. `compile_media_prompts.py` is not in the production path and routes b-roll to a banned model (`wan2_7` in `constraints.json`). `constraints.json` even lists `credits_spent_before_storyboard_approved` as an automatic fail condition — and that exact condition occurred.

## The missing control layer

The system has a **script layer** and a **render layer** and nothing in between with authority. What's missing is the **directorial layer**: a component that

- breaks narration into visually-motivated beats (not duration-chunks of one prompt),
- assigns each beat a visual function, shot type, asset type, and model tier,
- enforces the gold-star shot mix (35% hero / 35% specific b-roll / 15% graphics / 10% metaphor / 5% kinetic text),
- caps hero blocks at 15s,
- prices the whole plan **before** a single credit is spent,
- and **blocks** `generate_media.py` until the plan is reviewed and approved.

Everything below builds that layer and wires the existing advisory tools into hard gates around it.

The second structural decision: **the on-camera/voiceover split must change.** "James visible but not lipsynced while narration plays" is forbidden for close-ups. James close/medium shots on screen during narration are either (a) true lipsync (seedance, ≤15s blocks), or (b) explicitly non-speaking cutaways (listening, writing, walking, profile/over-shoulder — `A_ROLL_CHARACTER_PRESENT_VOICEOVER` with face not delivering dialogue). Mouth-flapping voiceover close-ups are an automatic storyboard rejection.

---

# 2. Target Production Architecture

Strict gated flow. Each stage writes its artifact; gates are recorded in a per-project **gate ledger** (`Videos/Projects/{project_id}/gates.json`) by a shared library `scripts/gates.py`. Spending tools refuse to run unless required gates are `pass` **and** the SHA-256 recorded at approval matches the current artifact (edit-after-approval invalidates the gate).

```
S0 research brief
 → S1 script JSON
 → [G1 SCRIPT GATE]
 → S2 storyboard router (directorial layer)
 → [G2 STORYBOARD GATE]
 → S3 costed media plan (prompt compiler + cost estimator)
 → [G3 MEDIA PLAN GATE + G4 BUDGET GATE]
 → S4 dry-run + asset reuse check
 → [G5 HUMAN RENDER APPROVAL]
 → S5 TTS (cheap, may run after G1)
 → S6 Higgsfield generation (per-beat, from media plan ONLY)
 → [G6 MEDIA QA GATE]
 → S7 local graphics/overlay rendering (parallel to S6, zero Higgsfield cost)
 → S8 assembly
 → [G7 FINAL VIDEO QA — human]
 → publish
```

| Stage | Input | Output | Owner module | Blocking gate | Failure conditions | Higgsfield spend allowed |
|---|---|---|---|---|---|---|
| S0 Research brief | Human research, `generate_content_brief.py` | `research/briefs/{id}.json` | manual + existing tools | none | — | NO |
| S1 Script | Brief, hooks | `scripts/generated/{id}.json` | manual now; `generate_script.py` later (G01) | — | — | NO |
| **G1 Script gate** | Script JSON | `script_review.json` + gate ledger entry | `review_script.py` (existing) + `gates.py` | YES — blocks S2, S5 | Any persona blocking issue; weighted score < 3.0 | NO |
| S2 Storyboard router | Approved script JSON + narration timing estimates | `Videos/Projects/{id}/storyboard.json` (schema v2, §4) | `storyboard.py` (rewritten per §3) | — | Router cannot satisfy shot-mix constraints → emits errors, no storyboard written | NO |
| **G2 Storyboard gate** | storyboard.json | review report + gate ledger entry | `review_storyboard.py` (extended per §3/§7 rules) | YES — blocks S3 | Any hero block >15s (except tagged close); shot mix outside bands; untriggered anchor/graphic rules; mouth-flapping voiceover close-up; <12 distinct setups | NO |
| S3 Costed media plan | Approved storyboard + `constraints.json` + `model_routing.yaml` | `Videos/Projects/{id}/media_plan.json` | `compile_media_prompts.py` (promoted to production-authoritative) | — | Banned model in routing; missing reference image for identity shots; prompt fails vagueness lint | NO |
| **G3 Media plan gate** | media_plan.json | LLM review + gate ledger entry | `review_media_plan.py` (re-pointed at media plan, not script) | YES — blocks S4/S6 | Prompt/narration contradiction; forbidden patterns; text-surface risk unmitigated | NO |
| **G4 Budget gate** | media_plan.json cost fields | `budget_report.json` + gate ledger entry | `budget.py` (NEW) | YES — blocks S6 | `est_usd > budget_cap_usd` (default $60/explainer) without explicit human override; per-beat cost anomalies (>$3/beat) | NO |
| S4 Dry-run + reuse check | media_plan.json, asset library index | dry-run report: per-beat model, clip count, reuse hits, final spend | `generate_media.py --dry-run` (must consume media plan) | feeds G5 | Missing reference assets; Higgsfield auth failure | NO |
| **G5 Human render approval** | Dry-run report | gate ledger entry with approver | `approve.py` (NEW, thin CLI) | YES — last gate before spend | Human says no | NO |
| S5 TTS | Approved script | `narration/*.mp3`, `manifest.json`, timing map (`audio_timing.py`) | `tts.py` (+ `--require-gates`) | requires G1 | Review gate missing/stale | NO (ElevenLabs only, cheap) |
| S6 Generation | media_plan.json + gates G2–G5 pass | `assets/media/{project}/shots/*.mp4` + per-beat provenance | `generate_media.py` (refactored: media plan is sole prompt source) | HARD: refuses without G2+G3+G4+G5 | Gate missing/hash-mismatch; banned model; beat not `approved` | **YES — only stage allowed to spend** |
| **G6 Media QA gate** | Generated clips + media plan | `media_qa.json` + gate ledger entry | `qa_media.py` (fixed dims, wired pre-assembly) | YES — blocks S8 | Missing/corrupt clip; wrong audio policy; duration short; (later) identity-consistency fail | regeneration of failed beats only, capped (1 retry then fallback) |
| S7 Graphics/overlays | storyboard graphic specs + brand assets | `assets/media/{project}/graphics/*.png/.mp4` | `graphics.py` (NEW — local render, Pillow/ffmpeg) | feeds S8 | Template missing; text overflow | NO (zero-cost by design) |
| S8 Assembly | manifest + clips + graphics + timing map | `{id}_16x9.mp4`, `{id}_9x16.mp4`, log | `assemble.py` (+ graphic/overlay track support) | requires G6 | QA gate not passed; lipsync provenance check fail | NO |
| **G7 Final video QA** | Assembled video + review frames | human pass/fail vs `QA_RUBRIC.md` | human + `generate_media.py --review` frames | YES — blocks publish | Any `automatic_fail_conditions` in constraints.json | NO |

**Enforcement primitive (Opus implements once, everyone uses):** `scripts/gates.py` with `record_gate(project, gate, status, artifact_path, extra)` and `require_gates(project, [gate names], artifact_hashes)` → raises/exits 1 with a human-readable message naming the missing gate and the command to run. `--force-unsafe` exists for emergencies, prints a red warning, and writes `forced: true` into the ledger so it shows up in the production log.

---

# 3. Storyboard Router Specification (the directorial layer)

`storyboard.py` is rewritten as a two-pass router: a **deterministic pre-pass** (chunking, trigger detection, hard rules — pure Python, testable) followed by an **LLM directorial pass** (via `llm_call.py`) that refines visual briefs and act mapping within the deterministic skeleton. The LLM may never violate the deterministic constraints; the validator re-checks its output.

## 3.1 Chunking rules

- Input unit: script segment text. Split on sentence boundaries, then group into **beats of 4–10 seconds estimated duration** (`est_duration = words / wps`, wps from `constraints.json` audio_policy band, default 2.4).
- A beat never crosses a segment boundary, a framework-step boundary, or a trigger boundary (a sentence containing a trigger starts a new beat).
- After TTS exists, beat durations are re-resolved against the real timing map from `audio_timing.py`; estimated and actual must agree within ±20% or the storyboard is flagged stale.

## 3.2 Max duration rules

- **Hero lipsync beat: ≤ 15s** (≈ 35 words). Hard rule. Exception: exactly one `emotional_close` beat in Act 6 may run up to 25s and must carry `"justification"` in the beat JSON.
- Consecutive hero beats may not chain past 15s total — a hero beat must be followed by a non-hero beat unless it's the approved close.
- B-roll/graphic beats: 3–12s. Kinetic text: 1–3s.
- No two consecutive beats with the same `prompt_class` and same `shot_type` (forces angle/subject variation).

## 3.3 Visual tag taxonomy (`shot_type`)

| shot_type | Description | Maps to scene_type (constraints.json) |
|---|---|---|
| `hero_lipsync` | James speaking to camera, true lipsync | `A_ROLL_TALKING_HEAD` |
| `hero_cutaway` | James in frame, NOT speaking (writing, listening, profile, over-shoulder, hands) | `A_ROLL_CHARACTER_PRESENT_VOICEOVER` |
| `broll_archival` | Specific/period/institutional imagery for named people, dates, studies | `B_ROLL_SUPPORTING_VISUAL` |
| `broll_metaphorical` | Physical action mirroring an abstract concept | `B_ROLL_SYMBOLIC_VISUAL` |
| `broll_environment` | Grounded environmental footage (study, city, desk objects) | `B_ROLL_SUPPORTING_VISUAL` |
| `broll_tactical` | Demonstration of the practice (hands sketching, blank page, notebook) | `INSERT_HANDS_WRITING` / `INSERT_OBJECT_DETAIL` |
| `graphic_progressive` | Framework/list/curve build graphic, locally rendered | `TEXT_OVERLAY_POST_ONLY` |
| `graphic_title_card` | Chapter marker card | `TITLE_CARD` |
| `kinetic_text` | 1–3s center-screen stat/quote | `TEXT_OVERLAY_POST_ONLY` |
| `ui_insert` | Terminal/chat-style tactical screen, locally rendered | `TEXT_OVERLAY_POST_ONLY` |
| `still_kenburns` | Generated/reference still + pan-zoom in ffmpeg | `B_ROLL_SUPPORTING_VISUAL` |

## 3.4 Narrative act detection

Map beats to the 6-act structure by position + content markers:

1. **Act 1 Hook & authority gap** (0–5% runtime): opening segment(s); hook statement + promise.
2. **Act 2 Myth busting** (5–20%): myth language ("feels productive", "most people", "the problem is"), study citations invalidating defaults.
3. **Act 3 Framework reveal** (20–25%): "the system/framework", count words ("three principles").
4. **Act 4 Iteration loop** (25–85%): per-principle sections (ordinal markers: "the first principle…"). Each loop iteration gets the MITmonk micro-structure: title card → hero intro → anchor/tactical b-roll → hero takeaway.
5. **Act 5 Synthesis** (85–90%): recap language; full master graphic.
6. **Act 6 Identity shift + CTA** (90–100%): philosophical pivot + subscribe.

Deterministic pass proposes act boundaries; LLM pass may adjust ±1 beat; validator checks acts are sequential and complete.

## 3.5 Trigger rules (deterministic, regex/NLP — the "Keyword Trigger" system)

| Trigger detected in beat text | Forced assignment |
|---|---|
| Year (`\b1[5-9]\d{2}\b|\b20[0-2]\d\b`), proper name + study verb ("demonstrated", "showed", "documented"), institution names | `broll_archival` (and a `kinetic_text` if a % or number is cited) |
| Named framework / numbered principle ("The first principle is X") | `graphic_title_card` at section start + `graphic_progressive` build step |
| Lists, checklists, "three ways", enumerations | `graphic_progressive` |
| Abstract internal states (memory, friction, decay, focus, compounding) | `broll_metaphorical` |
| Tactical instruction ("write down", "sketch", "ask the model", "prompt it") | `broll_tactical` or `ui_insert` (AI/tool mentions → `ui_insert`) |
| Number ≥ 1,000, percentage, dollar amount, one-line quotable | `kinetic_text` overlay (1–3s) |
| Thesis ("the point is", "that difference is the entire mechanism"), direct question to viewer, emotional close | `hero_lipsync` |

Trigger coverage is a validation metric: every detected trigger must be satisfied by the assigned beat or an adjacent beat, else G2 fails with the list of unsatisfied triggers.

## 3.6 Shot mix targets (validated bands, per total runtime)

| Category | Target | Accept band (G2) |
|---|---|---|
| Hero (lipsync + cutaway) | 35% | 25–40% (lipsync alone ≤ 25%) |
| Specific/archival b-roll (incl. tactical, environment) | 35% | ≥ 25% |
| Educational graphics + UI inserts | 15% | ≥ 10% |
| Metaphorical b-roll | 10% | 5–15% |
| Kinetic text | 5% | 2–8% |

## 3.7 Pacing rules

- Act 1 + anchor stories: cut every 1.5–3s (beats may carry multiple sub-cuts via `shots_per_beat`).
- Acts 2–4 explanation: cut every 4–6s; graphics get ≥4s to breathe.
- Act 6: hold 10–15s+; music fade; the one approved long hero block lives here.
- Chapter markers: every Act 4 loop iteration starts with a `graphic_title_card` (1.5–2.5s) — also serves as a natural lipsync seam.

## 3.8 Hero shot rules

- `hero_lipsync` reserved for: thesis statements, the promise, direct rhetorical questions, principle takeaways, the close. Never for stretches of explanation/citation.
- Every `hero_lipsync` beat requires `reference_image` (canonical studio frame) + ElevenLabs audio file reference; renders via seedance `--image --audio` per-beat (never longer than the beat).
- `hero_cutaway` must specify a *non-speaking activity* and an angle from `approved_studio_angles` different from the previous hero beat. Briefs for cutaways must explicitly include "not speaking, mouth closed or neutral" framing language.
- **Forbidden:** James medium close-up, front-facing, while narration plays without lipsync. This is the flagship-001 failure mode; the validator rejects any `hero_cutaway` whose brief contains front-facing close-up framing.

## 3.9 B-roll rules

- Every b-roll beat carries `narrative_function` text: one sentence stating what the shot proves/anchors. Empty or generic ("supporting visual") → G2 fail.
- Archival: period-accurate, grounded, soft-focus on any documents (text policy), no readable generated text. For 1885 Ebbinghaus: "19th-century German study, oak desk, handwritten ledgers out of focus, daylight window" — not "old-timey scientist stock footage."
- Metaphorical: physical mirror of the cognitive concept (decay → sandcastle/eroding chalk; retrieval effort → climbing, pulling rope; layering → woodworking laminate). Must remain within universe palette/lighting constraints.
- No generic stock-footage logic: prompts that match the vagueness lint (e.g. contain "business people", "professional environment" with no specific subject/action/era) are rejected at S3.

## 3.10 Educational graphic rules

- Frameworks/lists/curves are **locally rendered** (`graphics.py`), never asked of Higgsfield (text hallucination risk + cost).
- Progressive builds mandatory: N-step framework → N+1 graphic states (intro + each step highlighted). Stored as PNG sequences or short MP4s with brand palette from `constraints.json` `allowed_palette` and brand fonts.
- The Forgetting Curve, Group A/B comparisons, and the master recap graphic are graphic beats, not video prompts.
- Act 5 must contain the fully-built master graphic ("screenshot this") beat.

## 3.11 Overlay rules

- Overlays (kinetic text, lower-thirds, citation credits) are post-production (`TEXT_OVERLAY_POST_ONLY`), composited by `assemble.py`, never generated in-scene.
- Every cited study gets a small citation overlay (e.g. "Roediger & Karpicke, 2006"). Every stat ≥ a threshold gets kinetic text.

## 3.12 Tactical UI insert rules

- AI-prompt/tool demonstrations render as dark-terminal/chat-style locally generated screens (templated, brand fonts, typewriter reveal). Real readable text is allowed here **because we render it ourselves** — text policy forbids *generated-in-scene* text, not post overlays.
- Act 4 Step D ("tactical application") and the Act "AI layer" sections must contain ≥1 `ui_insert` or `broll_tactical` each.

## 3.13 Audio / lipsync implications

- Master narration is one continuous ElevenLabs track per segment (or `continuous_voiceover` once validated — G07); visuals are cut to the timing map from `audio_timing.py`.
- Lipsync clips are generated per-beat with the exact narration slice for that beat (`--image --audio`), provenance-checked (`validate_lipsync_provenance()` wired at assembly, G6).
- B-roll/graphic beats: audio stripped (existing rule).
- Music ducking: storyboard marks `music_duck: true` on paradigm-shift and intimate-story beats; `assemble.py` honors it.

## 3.14 Anti-patterns (router must never emit; validator double-checks)

1. Front-facing James close-up under voiceover without lipsync.
2. Hero block > 15s (except the one tagged close).
3. Two consecutive beats with identical prompt_class + shot_type.
4. Framework or list delivered with no graphic beat.
5. Named study/person/date with no archival beat.
6. Any beat whose visual brief is a copy of the segment-level brief (segment-level `visual_brief` is dead as a generation input).
7. Generated-in-scene readable text.
8. >2 renders of the same prompt hash in one project.
9. Banned models anywhere.
10. A storyboard whose total estimated cost exceeds the budget cap without an explicit human override entry.

---

# 4. Storyboard JSON Schema (v2)

File: `Videos/Projects/{project_id}/storyboard.json`. JSON Schema definition goes in `schemas/storyboard_v2.schema.json` (the empty `schemas/` dir finally earns its keep). Validator: `review_storyboard.py`.

```json
{
  "schema_version": "2.0",
  "project_id": "flagship_002_example",
  "video_type": "explainer",
  "source_script": "scripts/generated/flagship_002_example.json",
  "source_script_sha256": "<sha256 of script at routing time>",
  "target_runtime_sec": 720,
  "created_at": "2026-06-12T00:00:00",
  "router_version": "2.0.0",

  "acts": [
    {"act": 1, "name": "hook_authority_gap", "beat_ids": ["B001", "B002", "B003"], "runtime_pct": 4.8}
  ],

  "beats": [
    {
      "beat_id": "B014",
      "segment_id": "004_wrong_approach",
      "act": 2,
      "order": 14,
      "narration_text": "Roediger and Karpicke demonstrated this in 2006...",
      "narration_word_span": [38, 84],
      "est_duration_sec": 9.2,
      "actual_duration_sec": null,

      "visual_function": "anchor_story",
      "narrative_function": "Grounds the retrieval-practice claim in the named 2006 study so the framework inherits institutional authority.",
      "shot_type": "broll_archival",
      "asset_type": "generated_video",
      "model_tier": "standard",
      "model": "kling3_0",
      "prompt_class": "archival_academic",
      "shots_per_beat": 2,

      "visual_brief": "University psychology lab circa mid-2000s, students at desks writing on paper from memory, warm practical lighting, papers and pencils, no readable text in focus, documentary style, shallow depth of field.",
      "reference_images": [],
      "reference_required": false,

      "audio_mode": "voiceover",
      "lipsync_required": false,
      "music_duck": false,

      "overlay": {
        "required": true,
        "type": "citation",
        "text": "Roediger & Karpicke, 2006",
        "timing": "beat_start"
      },
      "graphic": {
        "required": false,
        "kind": null,
        "build_step": null,
        "total_steps": null,
        "payload": null
      },

      "crop_safety": "center_safe",

      "cost": {
        "est_clips": 2,
        "est_credits": 20,
        "est_usd": 0.98
      },
      "reuse": {
        "allowed": true,
        "reused_asset_id": null
      },
      "fallback": {
        "on_generation_fail": "still_kenburns",
        "on_qa_fail": "regenerate_once_then_fallback"
      },

      "approval": {"status": "pending", "approved_by": null, "approved_at": null},
      "qa": {"status": "pending", "report_path": null}
    }
  ],

  "shot_mix_summary": {
    "hero_lipsync_pct": 18.0,
    "hero_cutaway_pct": 14.0,
    "broll_specific_pct": 33.0,
    "broll_metaphorical_pct": 11.0,
    "graphics_ui_pct": 16.0,
    "kinetic_text_pct": 5.0,
    "max_hero_block_sec": 14.2,
    "distinct_visual_setups": 19,
    "total_cuts_estimate": 178
  },

  "totals": {
    "est_higgsfield_credits": 720,
    "est_usd": 35.30,
    "budget_cap_usd": 60.00,
    "beats_requiring_generation": 61,
    "beats_local_or_reused": 34
  },

  "approval": {
    "status": "draft",
    "approved_by": null,
    "approved_at": null,
    "sha256_at_approval": null
  }
}
```

Notes for Opus:
- `graphic.payload` for `graphic_progressive` carries the structured content: `{"title": "...", "items": ["...","..."], "highlight_index": 1}` — consumed directly by `graphics.py`.
- `hero_lipsync` beats additionally carry `"audio_slice": {"file": "narration/00X.mp3", "start_sec": 12.4, "end_sec": 24.1}` once TTS timing exists.
- Beat-level `approval.status` lets G5 approve all beats while a human can pin individual beats to `rejected` (router revises only those).
- `media_plan.json` (S3 output) is the same beat list enriched with fully compiled `positive_prompt`/`negative_prompt`/`output_path`/final model + per-beat exact cost — i.e., the universal required prompt fields from `constraints.json`.

---

# 5. Cost-Aware Model Routing Policy

Cost basis (2026-06-11, $0.049/credit): seedance_2_0 lipsync 22.5cr/5s ≈ **$1.10/clip**; kling3_0 10cr/5s ≈ **$0.49/clip**; local graphics/stills-pan-zoom ≈ **$0**.

## 5.1 Routing matrix

| Shot type | Risk | Premium required (seedance_2_0 / cinematic_studio_3_0) | Standard OK (kling3_0) | Cheap path OK | No video model — local |
|---|---|---|---|---|---|
| `hero_lipsync` | identity + lipsync = highest | **YES — seedance_2_0 with `--image --audio`, always** | never | never | never |
| `hero_cutaway` (James non-speaking) | identity = high | seedance/kling3_0 with reference image; face visible → top routing | YES with reference + canonical angle | still_kenburns from canonical reference frames for ≤5s beats | n/a |
| Human close-up (non-James) | high (uncanny) | prefer avoiding entirely | kling3_0, faces soft/medium distance only | no | n/a |
| `broll_archival` | medium | only if faces prominent | **YES — default kling3_0** | still_kenburns for static-scene beats (archive photo look) | n/a |
| `broll_metaphorical` | low (no faces, no text) | no | YES | **still_kenburns preferred when motion isn't the point** | n/a |
| `broll_environment` | low | no | YES | still_kenburns | n/a |
| `broll_tactical` (hands/objects) | medium (hands!) | no | YES — hands prompts get extra negative constraints + 1 retry budget | no (hand stills look dead) | n/a |
| `graphic_progressive`, `graphic_title_card`, `kinetic_text`, `ui_insert` | text risk if generated | **never Higgsfield** | never | never | **YES — `graphics.py`, $0** |

## 5.2 Decision rules

1. **Still + pan/zoom instead of video** when: beat ≤ 5s AND subject is static or atmospheric (environment, archival tableau, object detail) AND no required motion verb in the brief. One generated still can serve multiple beats with different crops/moves.
2. **Local text/graphics instead of Higgsfield** for anything whose information content is textual or diagrammatic: frameworks, curves, lists, comparisons, terminals, quotes, stats, title cards. This is ~20% of runtime at $0 and eliminates the entire garbled-text failure class.
3. **Cached/reused approved assets:** before any generation, check the asset library index (`assets/media/library_index.json`, NEW — beat prompt-class + semantic-hash keyed registry of QA-passed clips). Studio establishing shots, lamp/bookshelf details, recurring metaphor families, and the endcard should never be regenerated per video. Reuse cap: a given asset appears max 2× per video.
4. **Block generation entirely** when: prompt fails the vagueness lint (<2 of {specific subject, specific action, era/place, lighting} present, or contains banned generic phrases); OR beat cost > $3 without `"justification"`; OR model resolves to `banned_models`; OR a face-bearing prompt lacks `reference_images`; OR project total exceeds cap.
5. **Premium exception list** (the only places premium is justified): James lipsync, James hero stills/inserts, emotionally important hero close, any clip where a human face is the subject in the center-safe zone.

## 5.3 Config changes

- `constraints.json` `model_routing_policy`: `grounded_broll: kling3_0`, `abstract_broll: kling3_0` (kills the wan2_7 landmine — G04).
- `model_routing.yaml`: add `still_kenburns` and `local_graphic` as routing targets with `cost_per_clip_usd: 0`; add `cost_per_clip_usd` per model so `budget.py` reads one source of truth; set `higgsfield.require_cost_estimate: true`.

---

# 6. Render-Spend Control Gates

All gates recorded in `Videos/Projects/{project_id}/gates.json` via `gates.py`. **`generate_media.py` checks the ledger at startup and per-beat. No ledger, no spend.**

| # | Gate | Tool | What it checks | Hard block behavior |
|---|---|---|---|---|
| G1 | Script gate | `review_script.py` | Persona blocking issues; weighted ≥3.0; word count/WPS bands | `tts.py` and `storyboard.py` refuse without pass (override: `--force-unsafe`, logged) |
| G2 | Storyboard gate | `review_storyboard.py` | Schema valid; shot-mix bands (§3.6); max hero block; trigger coverage; anti-patterns (§3.14); ≥12 distinct setups; James presence rules from constraints.json | `compile_media_prompts.py` refuses without pass + hash match |
| G3 | Media plan gate | `review_media_plan.py` | LLM check: prompt↔narration coherence, forbidden patterns, text-surface risk, reference completeness | `generate_media.py` refuses |
| G4 | Budget estimate gate | `budget.py` | `totals.est_usd ≤ budget_cap_usd` (default $60 explainer / $25 short, set in `model_routing.yaml`); per-beat ≤$3 unless justified; ≥15% of beats on $0 paths | `generate_media.py` refuses; override requires `approve.py --gate budget --cap-override <usd>` by a human |
| G5 | Asset reuse check + dry run | `generate_media.py --dry-run` | Prints per-beat: model, clips, reuse hit/miss, cost; verifies references exist, Higgsfield auth, no banned models; writes `dryrun_report.json` | A real run requires a dry-run report newer than the media plan |
| G6 | Identity/lipsync risk check | part of dry-run + `qa_media.py` | Every `hero_*` beat has reference image + audio slice + provenance (ElevenLabs file hash recorded); lipsync beats ≤15s | Per-beat block |
| G7 | Final human approval | `approve.py --gate render` | Human has read the dry-run report; records name + timestamp + media-plan hash | **The switch that arms `generate_media.py`.** No approval entry → exit 1 before any Higgsfield call |
| G8 | Media QA gate | `qa_media.py` (fixed dims, wired) | Every clip exists/probes/duration/audio-policy; failures → 1 retry then fallback path | `assemble.py` refuses without pass |

Hash-staleness rule everywhere: editing any upstream artifact after its gate invalidates that gate and all downstream gates automatically (ledger stores the artifact SHA-256; `require_gates()` re-hashes).

---

# 7. Acceptance Criteria for the Next Production Run

The next flagship render may be attempted only when ALL of the following are true, measured by `review_storyboard.py` / `budget.py` / the dry-run report:

| Criterion | Target |
|---|---|
| Max hero block duration | ≤ 15s; exactly ≤1 close beat ≤ 25s with justification |
| Hero lipsync total | ≤ 25% of runtime; hero total (lipsync + cutaway) 25–40% |
| Specific/archival + tactical + environment b-roll | ≥ 25% of runtime |
| Educational graphics + UI inserts | ≥ 10% of runtime |
| Metaphorical b-roll | 5–15% |
| Kinetic text | 2–8% |
| Repeated hero visual reuse | No identical prompt rendered >2×; ≥12 distinct visual setups; no two consecutive same-setup beats |
| Cut rhythm | Act 1 median shot ≤3s; Acts 2–4 median 4–6s; Act 6 holds ≥10s |
| Lipsync | 100% of `hero_lipsync` beats: seedance `--image --audio`, ElevenLabs provenance hash recorded, beat ≤15s; **zero** front-facing close-ups under voiceover without lipsync |
| Framework/graphic coverage | Every framework, list, and cited statistic has a graphic or kinetic-text beat; every named study/person/date has an archival beat; Act 5 master graphic present |
| Review pass thresholds | G1 weighted ≥3.0 + zero blocking; G2 zero errors; G3 pass; G4 `est_usd ≤ $60` |
| Spend discipline | Zero Higgsfield calls before G7 human approval entry exists (audited via ledger + Higgsfield job log); ≥15% of beats on $0 local/still paths |
| Tests | `pytest` green on shot_router, assemble, generate_media, storyboard, gates (G06 fixed) |

---

# 8. Implementation Roadmap for Opus and Sonnet

Sequenced. Each task names model, objective, files, gates/tests, output, block condition. Tasks 1–3 stop the bleeding; 4–6 build the directorial core; 7–9 wire spend control; 10–11 graphics + assembly; 12 the supervised rerun.

| # | Model | Objective | Files likely touched | Tests/gates | Expected output | Block condition |
|---|---|---|---|---|---|---|
| T1 | Sonnet | **Config hygiene:** fix `constraints.json` model_routing_policy (wan2_7→kling3_0 both keys); add per-model `cost_per_clip_usd` + `budget_cap_usd` to `model_routing.yaml`; set `require_cost_estimate: true`; mark `voice_spec.yaml` deprecated header | `docs/channel_universe/constraints.json`, `configs/james/model_routing.yaml`, `configs/james/voice_spec.yaml` | grep: zero wan2_7 outside banned list | clean configs | any tool still resolving a banned model |
| T2 | Sonnet | **Fix test suite (G06) + known bugs:** update `test_shot_router.py` to current models; fix `test_assemble.py` `log` fixture; fix `generate_media.py` `shot_type` UnboundLocalError; fix `qa_media.py` dimension constants (source 1280×720 vs assembled 1920×1080 — parameterize by scope) | `tests/test_shot_router.py`, `tests/test_assemble.py`, `scripts/generate_media.py`, `scripts/qa_media.py` | full `pytest` green | trustworthy CI signal | any red test remaining |
| T3 | Opus | **Gate ledger + spend lock:** implement `scripts/gates.py` (record/require, SHA-256 staleness, `--force-unsafe` logging) and `scripts/approve.py`; wire `require_gates()` into `generate_media.py` (G2+G3+G4+G7 before ANY Higgsfield call), `tts.py` (G1), `assemble.py` (G8) | `scripts/gates.py` (new), `scripts/approve.py` (new), `scripts/generate_media.py`, `scripts/tts.py`, `scripts/assemble.py`, `tests/test_gates.py` (new) | new tests: missing gate → exit 1; stale hash → exit 1; forced → ledger entry | **no un-gated spend possible from this point on** | generate_media reachable without ledger pass |
| T4 | Opus | **Storyboard Router v2:** rewrite `storyboard.py` per §3 — deterministic chunker, trigger engine, act mapper, shot-mix allocator, LLM directorial refinement via `llm_call.py`, schema v2 output; write `schemas/storyboard_v2.schema.json` | `scripts/storyboard.py`, `schemas/storyboard_v2.schema.json`, `tests/test_storyboard_router.py` (new) | unit tests on chunking, triggers (Ebbinghaus/1885/2006 cases from flagship 001 as fixtures), hero-block cap, mix bands | storyboard.json v2 for flagship 001 script that fixes the failure when routed | router emits any §3.14 anti-pattern |
| T5 | Opus | **Storyboard validator v2 (G2):** extend `review_storyboard.py` to validate schema v2 + §7 metrics + trigger coverage + anti-patterns; writes gate ledger entry | `scripts/review_storyboard.py`, `tests/test_review_storyboard.py` | flagship-001-style storyboard (all hero) must FAIL with named violations; a compliant fixture must PASS | enforceable G2 | validator passes the flagship 001 shape |
| T6 | Opus | **Media plan compiler (S3):** promote `compile_media_prompts.py` — consume storyboard v2 + constraints + routing yaml; emit `media_plan.json` with full prompt fields, per-beat cost, vagueness lint, reference checks; require G2 | `scripts/compile_media_prompts.py`, `tests/test_compile_media_prompts.py` | banned model → fail; vague prompt → fail; cost fields present for all beats | production-authoritative media plan | any beat missing required prompt fields |
| T7 | Sonnet | **Budget gate (G4):** implement `scripts/budget.py` reading media_plan totals vs caps; per-beat anomaly check; ledger entry; human override path via `approve.py` | `scripts/budget.py` (new), `tests/test_budget.py` | over-cap plan blocks; override writes audit entry | budget_report.json + gate | spend possible over cap without override entry |
| T8 | Opus | **generate_media.py refactor:** sole prompt source = `media_plan.json` (script `visual_brief` path deleted/hard-deprecated); per-beat generation incl. `hero_lipsync` audio slices (seedance `--image --audio`), `still_kenburns` path (image gen or reference still + ffmpeg zoompan), reuse-library lookup (`assets/media/library_index.json`), per-beat provenance log, `--dry-run` report (G5), retry-once-then-fallback | `scripts/generate_media.py`, `scripts/shot_router.py`, `tests/test_generate_media.py` | dry-run on approved plan = correct cost, zero API calls; live run blocked without G7 | beat-accurate generation, no orphan prompts | any code path that prompts from script JSON directly |
| T9 | Sonnet | **Media QA wiring (G8):** run `qa_media.py` against media plan beats pre-assembly; wire `validate_lipsync_provenance()` into `assemble.py`; ledger entry | `scripts/qa_media.py`, `scripts/assemble.py`, `tests/test_qa_media.py` | assemble refuses without QA pass | enforced pre-assembly QA | assemble runs on unchecked clips |
| T10 | Opus | **Local graphics engine (S7):** `scripts/graphics.py` — progressive node builds, title cards, kinetic text, citation overlays, terminal-style UI inserts from `graphic.payload`; brand palette/fonts from constraints + `brand/`; outputs PNG/MP4 sized for both crops | `scripts/graphics.py` (new), `brand/`, `tests/test_graphics.py` | golden-image-ish tests (dimensions, palette, text fits safe area) | $0 graphic assets for ~20% of runtime | readable text rendered by Higgsfield anywhere |
| T11 | Sonnet | **Assembly support for beats:** extend `assemble.py`/manifest for beat-level cuts from the timing map (`audio_timing.py`), graphic/overlay tracks, `music_duck`, citation overlays | `scripts/assemble.py`, `scripts/tts.py`, `scripts/audio_timing.py`, `tests/test_assemble.py` | beat timing within ±0.25s of plan on fixture | assembled video matches storyboard rhythm | drift > tolerance |
| T12 | Sonnet | **Runbook + docs:** rewrite `docs/OPERATING_GUIDE.md` production sequence around gates; update `PIPELINE_IMPLEMENTED.md`, `REVIEW_AND_QUALITY_SYSTEM.md`; add `docs/RUNBOOK_PRODUCTION_V2.md` with the exact command sequence | docs | doc review | one-page command runbook | docs contradict code |
| T13 | Human + pipeline | **Supervised rerun of flagship 001** through the full gated path (script already exists and passes the formula): route → review → plan → budget → dry-run → approve → generate → QA → assemble → G7 human | — | All §7 acceptance criteria | a publishable flagship | any gate fail |

Reuse note for T13: the existing 151 kling clips are mostly burned (single setup), but the QA-passed hook lipsync, studio establishing material, and any usable environment clips should be indexed into `library_index.json` to recover part of the spend.

---

# 9. Specific Implementation Prompts

## 9.1 Opus prompt — core architecture and wiring (T3, T4, T5, T6, T8)

```
You are implementing the directorial + gating layer for the YTchannel pipeline. The
authoritative spec is docs/plans/PRODUCTION_V2_BLUEPRINT.md — read it fully first,
especially §2 (gated flow), §3 (Storyboard Router spec), §4 (storyboard JSON schema v2),
§5 (model routing), §6 (gates). Do not deviate from the schema or gate semantics.

Context: flagship 001 failed because generate_media.py prompted 151 near-identical
James close-ups from segment-level visual_brief fields, none lipsynced. Your job is to
make that impossible.

Implement, in this order, committing per task:

1. scripts/gates.py + scripts/approve.py — per-project gate ledger
   (Videos/Projects/{id}/gates.json): record_gate(), require_gates() with SHA-256
   artifact staleness, --force-unsafe that logs forced:true. Wire require_gates() into
   generate_media.py (gates: storyboard_review, media_plan_review, budget, render_approval
   — checked BEFORE any Higgsfield CLI invocation), tts.py (script_review), assemble.py
   (media_qa). Add tests/test_gates.py.

2. Rewrite scripts/storyboard.py as the Storyboard Router per blueprint §3:
   deterministic pass (sentence chunking into 4–10s beats, trigger regex engine for
   years/names/institutions/frameworks/numbers, 6-act mapping, shot-mix allocation,
   hero-block ≤15s) then LLM refinement via llm_call.py constrained to the deterministic
   skeleton. Output must validate against schemas/storyboard_v2.schema.json (you write
   this schema file from blueprint §4). Use the flagship 001 script
   (scripts/generated/flagship_001_learn_half_time.json) as the primary test fixture:
   the router must produce archival beats for Ebbinghaus/1885 and Roediger/2006,
   graphic beats for the forgetting curve and the three principles, ui_insert beats for
   the AI-prompt section, and no hero block >15s.

3. Extend scripts/review_storyboard.py to validate schema v2 + the acceptance metrics
   in blueprint §7 + anti-patterns §3.14, writing a gate ledger entry. A storyboard
   shaped like flagship 001 (all hero) must fail with named violations.

4. Promote scripts/compile_media_prompts.py to produce media_plan.json: full prompt
   fields per constraints.json universal_required_prompt_fields, model routing per
   blueprint §5 (kling3_0 default b-roll, seedance_2_0 lipsync only, still_kenburns and
   local_graphic as $0 routes), per-beat cost from configs/james/model_routing.yaml
   cost fields, vagueness lint, reference-image checks. Requires storyboard gate pass.

5. Refactor scripts/generate_media.py: media_plan.json is the ONLY prompt source —
   delete/hard-deprecate the script visual_brief path. Per-beat generation including
   hero_lipsync via seedance --image --audio with narration slices, still_kenburns via
   ffmpeg zoompan, reuse lookup in assets/media/library_index.json, per-beat provenance
   logging, --dry-run that produces dryrun_report.json (per-beat model/clips/cost/reuse)
   with zero API calls, retry-once-then-fallback on failure.

Constraints: never route to banned_models in model_routing.yaml; never send readable
text prompts to Higgsfield; all new code gets pytest coverage; run the full suite green
before finishing. Verify end-to-end with: route flagship 001 → review → compile →
budget → dry-run, all gates recorded, zero Higgsfield calls.
```

## 9.2 Sonnet prompt — config, tests, gate cleanup (T1, T2, T7, T9)

```
You are doing config/test/gate cleanup for the YTchannel pipeline per
docs/plans/PRODUCTION_V2_BLUEPRINT.md §5.3, §6, and roadmap tasks T1, T2, T7, T9.

1. docs/channel_universe/constraints.json: model_routing_policy.grounded_broll and
   .abstract_broll → "kling3_0" (wan2_7 is banned).
2. configs/james/model_routing.yaml: add cost_per_clip_usd per model (seedance_2_0: 1.10,
   kling3_0: 0.49, still_kenburns: 0, local_graphic: 0), add budget caps
   (budget_cap_usd: explainer 60, short 25), set higgsfield.require_cost_estimate: true.
3. configs/james/voice_spec.yaml: add a clear DEPRECATED header — production voice is
   ElevenLabs eleven_v3 only.
4. Fix the test suite: tests/test_shot_router.py expects banned models (veo3,
   minimax_hailuo) — update to current routing; tests/test_assemble.py missing `log`
   fixture; scripts/generate_media.py shot_type UnboundLocalError in the segment
   fallback path; scripts/qa_media.py dimension constants — parameterize source clips
   (1280x720) vs assembled output (1920x1080 / 1080x1920) by a --scope flag.
5. Implement scripts/budget.py (gate G4): read media_plan.json totals vs caps, flag any
   beat >$3 without a justification field, require ≥15% of beats on $0 routes, write a
   gates.py ledger entry; human override only via approve.py --gate budget
   --cap-override, which writes an audit entry. Add tests/test_budget.py.
6. Wire qa_media.py as the pre-assembly gate (G8): validate every media-plan beat's
   clip, call validate_lipsync_provenance() for lipsync beats, write ledger entry;
   assemble.py must refuse without it.

Acceptance: pytest fully green; grep shows wan2_7 only in banned lists; an over-budget
media plan blocks generation; assemble refuses unchecked clips.
```

## 9.3 Sonnet prompt — documentation/runbook (T12)

```
Update YTchannel docs to match the gated production pipeline in
docs/plans/PRODUCTION_V2_BLUEPRINT.md (assume roadmap tasks T1–T11 are implemented;
verify against the actual code before writing).

1. Create docs/RUNBOOK_PRODUCTION_V2.md: the exact command sequence from research brief
   to published video, one command per step, with the gate that must pass before each
   step, what artifact it writes, and what to do on failure. Include the spend rule
   prominently: no Higgsfield call before approve.py --gate render.
2. Rewrite the production sequence in docs/OPERATING_GUIDE.md to match.
3. Update docs/PIPELINE_IMPLEMENTED.md stages 6–12 and the Wire State table in
   docs/REVIEW_AND_QUALITY_SYSTEM.md: storyboard/media-plan/budget/QA gates are now
   blocking, generate_media consumes media_plan.json only.
4. Mark superseded statements in docs/PIPELINE_GAPS_AND_PENDING_STEPS.md (G02, G03,
   G04, G06, G15) as resolved with references to the implementing code.

Keep docs factual and audit-style like the existing 2026-06-12 docs. No aspirational
claims: document only what the code actually enforces, and list anything still
advisory under a Known Gaps heading.
```

## 9.4 Fable-lite review prompt (only if needed, immediately before the first expensive render)

```
You are the final pre-spend reviewer for YTchannel flagship rerun. Inputs:
Videos/Projects/{id}/storyboard.json, media_plan.json, budget_report.json,
dryrun_report.json, gates.json, and docs/plans/PRODUCTION_V2_BLUEPRINT.md §7.

Answer only these questions, tersely:
1. Does the storyboard satisfy every §7 acceptance criterion? List any miss with beat IDs.
2. Scan the 10 most expensive beats: is each one's model tier justified by its visual
   function? Name any beat that should be downgraded to kling3_0, still_kenburns, or a
   local graphic.
3. Scan all hero_lipsync beats: any over 15s, missing reference image, or missing audio
   slice provenance?
4. Scan archival/metaphorical briefs for generic-stock smell or universe violations
   (palette, lighting, text-in-scene). Name offenders.
5. Verdict: APPROVE / REVISE (with the minimal beat-level change list). Do not redesign
   the system. Do not touch code.
```

---

# 10. Non-Negotiable Rules

1. **No Higgsfield spend without the full gate chain:** storyboard_review + media_plan_review + budget + render_approval present in `gates.json` with matching artifact hashes. `credits_spent_before_storyboard_approved` is already an automatic-fail condition in `constraints.json` — now it is mechanically impossible, not aspirational.
2. **`media_plan.json` is the only prompt source for generation.** Script-level `visual_brief` is dead as a generation input. Any code path that prompts Higgsfield from the script JSON is a defect.
3. **No hero block over 15 seconds**, except exactly one justified Act-6 close ≤25s.
4. **No front-facing James close-up under voiceover without true lipsync.** James on screen during narration is either seedance lipsync or an explicitly non-speaking cutaway. The 150 mouth-flapping clips of flagship 001 must never recur.
5. **No framework, list, or cited statistic delivered without a graphic or kinetic-text beat.** Locally rendered. Never ask Higgsfield to draw text.
6. **No named study, person, date, or institution without a specific archival/anchor b-roll beat.**
7. **No generic stock-footage prompts.** Every b-roll beat carries a one-sentence narrative function and passes the vagueness lint, or it doesn't compile.
8. **No identical prompt rendered more than twice per project; minimum 12 distinct visual setups per long-form video.**
9. **No banned models, ever** (`wan2_7`, `wan2_6`, `minimax_hailuo`, `seedance_2_0_fast`, `seedance1_5`). Routing configs and constraints must agree; tests enforce it.
10. **No stale cached TTS or media without provenance check.** Lipsync beats record the ElevenLabs file hash; `assemble.py` runs `validate_lipsync_provenance()`; cached assets enter a video only via the reuse index with QA status `pass`.
11. **No production render while the test suite is red or any gate tool exits non-zero.**
12. **Premium models only where they buy quality the viewer can see:** James's face, lipsync, human close-ups, hero emotional shots. Everything textual or diagrammatic is rendered locally for $0; everything static-atmospheric prefers stills + pan/zoom.
13. **Gate overrides exist but are loud:** `--force-unsafe` and budget overrides write audited ledger entries with who/when/why. Silent bypasses are defects.

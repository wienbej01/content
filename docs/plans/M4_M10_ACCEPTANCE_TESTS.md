# M4–M10 Acceptance Tests

**Companion to** `M4_M10_CREATIVE_CONTROL_WORKPLAN.md` §13. Concrete per-sprint test lists. All run with `python3`. None call live APIs; none spend credits.

## Global regression guard (every sprint must end green)
```
python3 tests/test_assemble.py Videos/Projects/trailer_demo/trailer_demo_log.json
python3 tests/test_tts.py
python3 tests/test_generate_media.py
python3 tests/test_media_pack.py
```
All four must pass unchanged after every sprint.

## Token-redaction guard (add as a reusable check)
- grep the captured stdout/stderr of any script run for `hf_`, `sk_`, `Bearer `, and any 20+ char base64-ish token; assert none present.

---

## M4.1 / M4.2 / M4.3 (docs)
- File-existence test: each required `docs/channel_universe/*.md` exists and is non-empty.
- Heading lint: each doc contains its required section headings (from `M4_M10_SCHEMA_DESIGN.md` checklists).
- Consistency: `constraints.json` parses as valid JSON; palette hex match BRAND_SPEC §3; the 7 studio angle IDs appear in both the studio bible and constraints.json.
- No-contradiction spot check: FORBIDDEN_PATTERNS items are not also "allowed" in TECHNICAL_BIBLE.
- M4.3: the six `assets/reference/*` folders exist with `.gitkeep`; manifest lists the 4 James seed entries with correct existing paths.

## M5.1
- Valid storyboard fixture → `--validate` exit 0.
- Missing `narrative_promise` → exit 1 with clear message.
- Unknown `scene_type` → exit 1.
- `--dry-run` makes no network call (assert by running offline) and creates no files.

## M5.2
- Teaser fixture with 70% James → ratio OK (no warning).
- Explainer fixture with 10% A-roll → WARN (exit 0, warning printed).
- Host-led fixture, 0% James present, `allow_all_broll` false → hard FAIL exit 1.
- `audio_continuity_group` referenced by 3 beats validates.

## M6.1
- Stub LLM returns pass JSON → `may_proceed` true.
- Stub returns one persona with `blocking_issues` → `may_proceed` false.
- All-b-roll storyboard fixture → universe/filmmaker reviewer blocks.
- `--dry-run` prints prompt, no API call (stub asserts not called).
- No API key present → dry-run still works; real-run fails cleanly with actionable message.

## M7.1
- ffmpeg-generated wav (known duration) → timing map total_duration within ±0.2s.
- WPS computed; flags `wps_below_2.0` triggers on a deliberately slow fixture.
- Schema-shape test on output JSON.

## M7.2
- Script without `narration_mode` → defaults to `segment_tts`; existing `test_tts.py` behavior unchanged (13/13).
- Script with `continuous_voiceover` + stubbed TTS → single narration call requested (assert call count == 1, stubbed).
- Reuse-cache: existing narration not regenerated without `--force`.

## M8.1
- Fixture storyboard → `media_prompt_plan.json` valid shape.
- Every prompt contains the default negative block.
- A-roll/James-present beat → entry references at least one approved James asset_id and model `seedance_2_0`.
- B-roll beat → model `wan2_7`, `audio_policy: strip`.
- text_policy default `post_overlay`; no prompt requests readable in-scene text.

## M9.1
- ffmpeg fixture clip (no audio) tagged `generated_tts` → technical pass.
- ffmpeg fixture clip (WITH audio) tagged `generated_tts` → FAIL (audio contamination).
- Wrong-dimension fixture → crop-safety/dimension flag.
- Unreadable file → `readable: false`, fail.
- `media_qa_report.{json,md}` written.

## M9.2
- `--creative` off by default (no vision call in default run).
- Stubbed vision call returns canned scores; aggregation correct.
- `--manual-review` path calls the Telegram sender stub (assert called), no auto-pass.

## M10.1
- `TEASER_02_REBUILD_RUNBOOK.md` exists with the full command sequence.
- `james_growth_system_teaser_02.json` exists, distinct project_id, no `media` files generated.
- teaser_01 media timestamps unchanged (assert mtime equal to pre-sprint snapshot).

## M10.2
- One temp clip produced via full new pipeline; QA pass; teaser_01/02 finals untouched (mtime check).
- Credits-spent reported.

## M10.3
- Only runs after explicit approval flag/file present; otherwise refuses.
- teaser_01 untouched; teaser_02 outputs produced; sent to Telegram.

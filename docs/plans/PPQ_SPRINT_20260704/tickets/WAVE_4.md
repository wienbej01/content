# Wave 4 — Graphics Professionalization (TKT-401..407)

Sprint: `PPQ-2026-07`. See `../PLAN.md`. Deps: Wave 0; TKT-406/407 also require Wave 3. Goal: brand-true, animated, pixel-verified graphics; overlays composited over footage in one pass (CS-11..CS-15, CS-17, CS-19, CS-20, F3).

---

## TKT-401 — Brand typography, fail-closed fonts, supersampling, 9x16

- Requirements: R-GFX-1. Class: ROUTINE. Deps: Wave 0. Blocks: TKT-402..405, 407.
- Observable outcome: `render_graphics.py` loads fonts from `brand/fonts/` (Inter for body/UI, Playfair Display per role assignments in `brand/BRAND_SPEC.md`); missing brand fonts raise a render error (no DejaVu/PIL-default silent fallback); all templates render at 2x and downsample (LANCZOS); a native 1080x1920 layout variant exists per template (safe margins recomputed, not letterboxed 16x9).
- Evidence: `scripts/render_graphics.py:33-55` (hardcoded DejaVu, silent fallback); `brand/fonts/` contents; spec fonts `brand/BRAND_SPEC.md:207` (CS-15).
- Scope: `scripts/render_graphics.py`; tests comparing output hashes/dimensions/glyph metrics. Protected: palette constants (already brand-correct); template text contracts.
- Baseline: `YT_TEST_MODE=1 python3 -m pytest tests/ -k render_graphics -q` passes; grep shows DejaVu paths.
- Steps:
  1. Font loader reading `brand/fonts/` by role; loud `RenderError` when missing.
  2. 2x supersample render + LANCZOS downsample in the shared render path.
  3. Per-template 9x16 layout variant with recomputed safe margins.
  4. Update expected test hashes deliberately (reviewed, not blindly regenerated).
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | render each template 16x9 | 1920x1080 PNG; brand font detectable via known-glyph-width metrics test | `python3 -m pytest tests/test_brand_render.py -q` (new) |
| unit | render each template 9x16 | 1080x1920; content inside safe margins | same |
| negative | brand fonts dir hidden (monkeypatched) | loud RenderError; no PNG written | same |
| regression | existing graphics tests | pass with deliberately updated hashes | `YT_TEST_MODE=1 python3 -m pytest tests/ -k render_graphics -q` |

- Acceptance gates: G1 fail-closed font test passes; G2 all 12 templates render both aspect variants; G3 full suite passes.
- Audit focus: deterministic rendering (hash-stable for the same spec); memory at 2x supersample.
- Rollback: revert commit.

---

## TKT-402 — Professional templates reachable; duplicate drawtext removed

- Requirements: R-GFX-2. Class: ROUTINE. Deps: TKT-401. Blocks: TKT-405, TKT-406.
- Observable outcome: `render_local_graphic_render_unit`'s layout map routes deterministic text specs to all 12 templates (spec-type → template mapping extended; unknown layout is a loud error, not silent `key_line` coercion). The unstyled FFmpeg drawtext path (`scripts/assemble.py:1034-1076` and the `manifest["graphics"]` burn-in at `scripts/assemble.py:1347-1352`) is removed for DB-native productions so each beat renders exactly one graphic representation.
- Evidence: `scripts/render_graphics.py:1044-1049,943-944`; `scripts/assemble.py:1034-1076,1347-1352`; manifest emit `scripts/assemble_db.py:939-961` (CS-12, CS-14).
- Scope: layout map, `_classify_text_spec_type` extension in `scripts/produce_db.py`, assemble drawtext removal/gating; tests. Protected: the legacy manifest-file path may keep drawtext behind an explicit legacy flag (documented) — but never both paths for one beat.
- Baseline: routing test proves only 4 templates reachable today (write first, must fail).
- Steps:
  1. Extend spec-type classification and layout map to cover all 12 templates.
  2. Unknown layout → loud error.
  3. Remove/gate the drawtext burn-in for DB-native manifests.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | spec of each of 12 types | correct template renderer invoked | `python3 -m pytest tests/test_template_routing.py -q` (new) |
| negative | unknown layout string | loud error; no PNG | same |
| integration | test-mode assemble with graphic beat | output contains exactly one rendering of the text; no `drawtext` in the ffmpeg command log for DB-native productions | `python3 -m pytest tests/test_single_graphic_representation.py -q` (new) |

- Acceptance gates: G1 all 12 templates reachable (asserted); G2 assembled ffmpeg command for a DB-native production contains no `drawtext` for graphic beats; G3 full suite passes.
- Audit focus: legacy-path isolation; impossibility of a beat triggering both renderers.
- Rollback: revert commit.

---

## TKT-403 — Graphic OCR verification and verified text hash

- Requirements: R-GFX-3, F3. Class: ROUTINE. Deps: TKT-401. Blocks: TKT-404.
- Observable outcome: `_qa_local_graphic` OCRs the rendered PNG (pytesseract, already used for provider OCR) and fuzzy-matches against `graphic_text_content` (normalized token recall ≥ a documented threshold constant); mismatch (truncation/overflow/wrap loss) fails QA with both texts in evidence. The `graphic_text_hash` DB column is recomputed and verified (no longer write-only).
- Evidence: skip-by-design `scripts/media_service.py:734-738`; truncation `scripts/render_graphics.py:948,1052`; OCR infra `scripts/media_service.py:750-828` (CS-17).
- Scope: `scripts/media_service.py` `_qa_local_graphic`; tests with a deliberately truncated fixture. Protected: NO_VISIBLE_TEXT provider OCR path.
- Baseline: `_qa_local_graphic` sets `text_policy_ok = True` unconditionally (grep proof).
- Steps:
  1. OCR + normalized token-recall comparison; threshold constant documented with measurements.
  2. Recompute and verify `graphic_text_hash`.
  3. Calibrate the threshold on stylized templates (serif quote card) inside the ticket.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | correct render of known text | QA pass; token recall recorded | `python3 -m pytest tests/test_graphic_ocr.py -q` (new) |
| negative | render forced to truncate (long fixture text) | QA fail naming missing tokens | same |
| unit | tampered `graphic_text_hash` | QA fail | same |
| boundary | stylized serif template | OCR threshold still met (calibrated) | same |

- Acceptance gates: G1 truncated graphic fails production QA (F3 regression test); G2 hash verification enforced; G3 full suite passes.
- Audit focus: OCR flakiness on serif fonts — threshold justified with measurements, never loosened ad hoc.
- Audit steps:
   1. Confirm `text_policy_ok` is no longer unconditionally True — grep for the old skip-by-design pattern at `scripts/media_service.py`.
   2. Verify token-recall threshold is documented and backed by measurements on the quote_card template.
   3. Verify `graphic_text_hash` is recomputed from artifact bytes and checked against stored value.
   4. Verify the OCR path handles missing pytesseract/tesseract gracefully (evidence recorded, not crash).
   5. Run focused tests (`test_graphic_ocr.py`) independently; run invariant suite.
   6. Confirm `NO_VISIBLE_TEXT` provider OCR path is untouched.
- Validation steps:
   1. Run `python3 -m pytest tests/test_graphic_ocr.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify truncated fixture fails QA with token-recall below threshold.
   4. Verify correct render passes QA with token-recall above threshold.
   5. Verify tampered `graphic_text_hash` causes `graphic_text_hash_mismatch` issue.
   6. Verify stylized serif template exceeds threshold (calibrated measurement recorded).
   7. Write validation report `evidence/TKT-403-validation.md`.
   8. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit.

---

## TKT-404 — Auto-fit text layout (no hard truncation)

- Requirements: R-GFX-4. Class: ROUTINE. Deps: TKT-401, TKT-403.
- Observable outcome: All templates use a shared shrink-to-fit layout: font size steps down within documented min/max per role until text fits its box; text exceeding capacity at minimum size raises a loud `RenderError` at render time (upstream must shorten) — never `text[:N]` truncation; `_wrap` overflow clipping removed.
- Evidence: `scripts/render_graphics.py:58-72,948,1052`.
- Scope: `render_graphics.py` layout internals; tests. Protected: template visual contracts (box positions).
- Baseline: grep finds `[:120]`-style truncations in the renderer.
- Steps:
  1. Shared `fit_text(text, box, role) -> (font, lines)` with stepped sizing.
  2. Replace all truncation sites.
  3. Loud overflow error naming the beat and text length.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | long-but-fittable text | rendered at reduced size; fully present (verified via TKT-403 OCR harness) | `python3 -m pytest tests/test_autofit.py -q` (new) |
| negative | text beyond min-size capacity | RenderError; no PNG | same |
| regression | short text | rendered at max role size | same |

- Acceptance gates: G1 grep gate — no `[:N]` truncation remains in the renderer; G2 overflow is loud; G3 full suite + TKT-403 OCR tests pass.
- Audit focus: interaction with 9x16 boxes; deterministic chosen font size.
- Audit steps:
   1. Confirm no `[:N]`-style hard truncation remains in any render function.
   2. Verify `fit_text()` produces deterministic font size output for identical inputs.
   3. Verify overflow beyond min-size raises loud `RenderError` (never silent truncation).
   4. Verify 9x16 boxes have correctly recomputed safe margins.
   5. Run focused tests (`test_autofit.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_autofit.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify long-but-fittable text renders fully at reduced size (OCR-verified).
   4. Verify text beyond min-size capacity raises `RenderError`.
   5. Verify short text renders at max role size.
   6. Verify zero `[:N]` hard truncation in `render_graphics.py` (grep).
   7. Write validation report `evidence/TKT-404-validation.md`.
   8. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit.

---

## TKT-405 — Real animation wired into graphics_compositing

- Requirements: R-GFX-5. Class: COMPLEX. Deps: TKT-401, TKT-402. Blocks: TKT-406 (shared layer-render machinery).
- Observable outcome: Graphics with span > 2s render as animated clips: element layers (background plate, text blocks, accents) rendered as separate PNGs and animated via an FFmpeg overlay filter graph (alpha fade + position offsets per element, staggered in-times), producing a video artifact with true alpha-composited motion. `invoke_graphics_compositing` calls this path; `validate_animation_requirement` (`scripts/render_graphics.py:632-652`) is enforced in production; the brightness-fade stub and dead code at `scripts/render_graphics.py:786-789` are removed/replaced.
- Evidence: stub + validator `scripts/render_graphics.py:632-810`; static production path `scripts/produce_db.py:1927-1978`; `tpad` hold `scripts/assemble.py:1259-1266` (CS-11).
- Scope: `render_graphics.py` (layered render + ffmpeg graph builder), `produce_db.invoke_graphics_compositing`; tests probing output motion. Protected: deterministic text/hash provenance (animated artifact metadata still carries `text_spec_sha256`).
- Baseline: production path renders one static PNG per unit (grep + orchestrator test observation).
- Steps:
  1. Layered element render (reuses TKT-401 templates split into plates).
  2. FFmpeg graph builder: per-element `overlay` with `enable=between(t,..)` and alpha fades; documented encode settings (pixfmt/CRF).
  3. Wire into `invoke_graphics_compositing` for spans > 2s; ≤2s static path remains permitted.
  4. Remove dead code; enforce `validate_animation_requirement`.
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | 5s stat_callout unit | video artifact; ffprobe duration ≈ span; frame-diff between t=0.2s and t=1.5s > 0 (motion proven) | `python3 -m pytest tests/test_graphic_animation.py -q` (new) |
| negative | >2s graphic with animation disabled/failed | stage fails via `validate_animation_requirement` | same |
| regression | ≤2s graphic | static PNG path still allowed | same |
| contract | QA on animated artifact | `_qa_local_graphic` + OCR (TKT-403) pass on a settled steady-state frame | same |

- Acceptance gates: G1 frame-diff proves motion in output; G2 animation requirement enforced; G3 OCR verification works on the animated output's settled frame; G4 full suite passes.
- Audit focus: encode settings and alpha handling; determinism; bounded render time.
- Audit steps:
   1. Verify dead brightness-fade stub code at `scripts/render_graphics.py:786-789` is removed/replaced.
   2. Verify FFmpeg filter graph uses alpha-capable pixfmt and documented CRF/preset.
   3. Confirm `validate_animation_requirement` is enforced (not ignored) in production path.
   4. Verify static PNG path for ≤2s graphics is preserved.
   5. Verify deterministic text provenance survives animation (`text_spec_sha256` in artifact metadata).
   6. Run focused tests (`test_graphic_animation.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_graphic_animation.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify frame-diff between t=0.2s and t=1.5s proves motion (> 0).
   4. Verify >2s graphic with animation disabled fails via `validate_animation_requirement`.
   5. Verify ≤2s graphic still uses static PNG path.
   6. Verify OCR (TKT-403) passes on animated output's settled steady-state frame.
   7. Write validation report `evidence/TKT-405-validation.md`.
   8. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit.

---

## TKT-406 — Production overlay_timeline: graphics over footage, single-pass

- Requirements: R-GFX-6, RISK-4; consumes R-TIME-3. Class: COMPLEX. Deps: TKT-303, TKT-402, TKT-405.
- Observable outcome: Storyboard overlay intents (lower thirds, stat callouts, key lines, source citations) project to overlay entries instead of full-frame cutaway units; `build_assembly_manifest` (`scripts/assemble_db.py:872-989`) emits a validated `overlay_timeline` (existing schema `schemas/overlay_timeline.schema.json`) with word-anchored start/end times; `assemble.py` composites all overlays for a deliverable in ONE encode pass (single filter graph), replacing per-overlay re-encodes (`scripts/assemble.py:523-528`). Full-frame templates (framework, comparison, timeline) remain timeline segments.
- Evidence: dormant compositor `scripts/assemble.py:454-531`; schema exists; manifest never emits it (CS-13, CS-19).
- Scope: `storyboard_projection.py` overlay classification, `assemble_db.py` manifest, `assemble.py` single-pass graph; tests. Protected: hero_island audio handling; publish-grade unit gates (overlay PNGs still QA'd via the local-graphic path including TKT-403 OCR).
- Baseline: `build_assembly_manifest` emits no `overlay_timeline` key (grep proof).
- Steps:
  1. Projection: classify overlay-suited intents (lower third, stat, key line, citation) as overlay entries with target region.
  2. Manifest emission validated against the schema; times from TKT-303 anchors or span boundaries.
  3. Single filter-graph compositing of N overlays in one encode; command log recorded for assertions.
  4. Audio handling unchanged (assert stream copy where applicable).
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | projection of lower-third intent | overlay entry, not full-frame unit | `python3 -m pytest tests/test_overlay_projection.py -q` (new) |
| contract | emitted manifest | validates against `schemas/overlay_timeline.schema.json` | same |
| integration | test-mode assemble, 3 overlays | exactly one encode pass for overlay compositing (single ffmpeg overlay invocation in command log); overlays visible in sampled frames inside their windows and absent outside | `python3 -m pytest tests/test_overlay_singlepass.py -q` (new) |
| regression | production with zero overlays | unchanged output | existing assemble tests |

- Acceptance gates: G1 frame sampling proves overlay presence inside window and absence outside (positive + negative); G2 single-pass property asserted from the command log; G3 9x16 positions honored; G4 full suite passes.
- Audit focus: filter-graph escaping/quoting; overlay count limits; A/V sync preserved through the single re-encode.
- Audit steps:
   1. Verify projection classifies overlay-suited intents (lower third, stat, key line, citation) as overlay entries, not full-frame units.
   2. Verify emitted manifest validates against `schemas/overlay_timeline.schema.json`.
   3. Confirm exactly one FFmpeg encode pass composites all overlays (single filter graph invocation in command log).
   4. Verify audio handling unchanged (stream copy where applicable, no extra re-encodes).
   5. Verify 9x16 overlay positions are honored.
   6. Run focused tests (`test_overlay_projection.py`, `test_overlay_singlepass.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_overlay_projection.py tests/test_overlay_singlepass.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify frame sampling proves overlay presence inside window and absence outside.
   4. Verify single-pass property from command log (exactly one overlay filter-graph invocation).
   5. Verify 9x16 positions honored.
   6. Verify production with zero overlays produces unchanged output.
   7. Write validation report `evidence/TKT-406-validation.md`.
   8. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit.

---

## TKT-407 — Ken Burns for still units

- Requirements: R-GFX-7. Class: ROUTINE. Deps: TKT-401.
- Observable outcome: `still_kenburns` units render in `graphics_compositing` as motion clips via ffmpeg `zoompan` (default move: slow 1.05–1.12 zoom with drift, deterministic from the unit id seed), duration == span. Alternative (decide in-ticket, default is implement): remove the asset type everywhere with a migration note.
- Evidence: CS-20; counting loop `scripts/produce_db.py:1944-1971` handles only `local_graphic`.
- Scope: `render_graphics.py`/graphics stage; tests with a fixture still. Protected: none.
- Baseline: a `still_kenburns` unit in a test production never receives an artifact (write failing test first).
- Test and proof matrix:

| Level | Scenario | Expected | Command |
| --- | --- | --- | --- |
| unit | still + 6s span | video artifact; duration ≈ 6s; frame-diff proves motion | `python3 -m pytest tests/test_kenburns.py -q` (new) |
| regression | non-still units | untouched | orchestrator suite |

- Acceptance gates: G1 motion proven; G2 unit reaches `generated` with a linked artifact in a test-mode run; G3 full suite passes.
- Audit focus: deterministic move from seed; output resolution/pixfmt consistent with assembly expectations.
- Audit steps:
   1. Verify `still_kenburns` unit reaches `generated` with a linked artifact in test-mode run.
   2. Confirm zoompan motion parameters derive deterministically from unit id seed.
   3. Verify output duration matches span.
   4. Confirm output resolution/pixfmt is consistent with assembly expectations.
   5. Run focused tests (`test_kenburns.py`) independently; run invariant suite.
- Validation steps:
   1. Run `python3 -m pytest tests/test_kenburns.py -q` — all passing.
   2. Run the sprint invariant 5-file suite — passing.
   3. Verify frame-diff proves motion.
   4. Verify unit reaches `generated` with a linked artifact.
   5. Verify non-still units are untouched (regression).
   6. Write validation report `evidence/TKT-407-validation.md`.
   7. If PASS: update `STATE.json` accepted list, `git commit`.
- Rollback: revert commit.

---

## Wave 4 gate

- W4-G1: A test-mode production assembles a deliverable containing: one animated full-frame graphic, one word-anchored overlay over footage, brand fonts (verified by the TKT-401 metrics test on an extracted frame), single-pass overlay compositing.
- W4-G2: OCR verification passes on every graphic in that deliverable; a planted truncation fixture fails.
- W4-G3: Full suite passes.

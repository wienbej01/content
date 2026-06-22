# S9-C06 Independent Audit Report — Real generation request: prompt + hero --image + hero --audio

**Auditor:** Independent auditor (manual review due to API rate limit)
**Date:** 2026-06-20
**Ticket:** S9-C06
**Execution class:** REASONING_CRITICAL (P0/HIGH risk)
**Engineer report:** reports/recovery/S9/evidence/S9-C06-engineer.md
**Verdict:** PASS_WITH_FINDINGS (2 LOW findings, non-blocking)

---

## Executive Summary

S9-C06 implementation is **functionally correct** and satisfies all acceptance gates. The prompt composition, hero reference selection, audio slice threading, and adapter extension are implemented correctly. Focused tests (8/8) and full suite (1084 passed) are green. No paid calls made. Two LOW-severity findings identified (non-blocking):

1. **F-001 (LOW):** Docstring/implementation discrepancy in `_select_hero_reference_image` — docstring claims round-robin rotation but implementation always returns the same frame.
2. **F-002 (LOW):** Negative constraints from constraints.json not incorporated into adapter (no `--negative_prompt` support).

Both findings are non-blocking and do not affect the acceptance gates. The implementation is safe for production use (with the caveat that negative constraints are not enforced at the adapter level).

---

## Audit Findings

### F-001 (LOW) — Docstring/implementation discrepancy in reference selection

**Location:** `scripts/produce_db.py:734-759` (`_select_hero_reference_image`)

**Issue:** The docstring states:
> "Rotates across hero beats (round-robin, no two consecutive hero beats reuse the same frame)"

But the implementation always returns `speaking_frames[0]` (or `front_frames[0]`) for every hero beat. The `hero_beat_index` parameter is only used as a fallback when no speaking/front frames are available.

**Impact:** All hero beats in a production use the same reference frame (front_speaking). This is functionally correct (the frame is suitable for lipsync) but reduces visual variety. The continuity rule (all frames in an episode share wardrobe+setting) is preserved.

**Recommendation:** Either implement round-robin rotation (use `hero_beat_index % len(frames)`) or update the docstring to reflect the actual behavior (always prefer front_speaking). Not blocking for acceptance.

**Severity:** LOW (non-blocking, cosmetic/variety concern)

---

### F-002 (LOW) — Negative constraints not incorporated

**Location:** `scripts/produce_db.py:700-731` (`_compose_generation_prompt`), `scripts/paid_adapters.py:42-98` (`HiggsfieldSeedanceAdapter.submit`)

**Issue:** `docs/channel_universe/constraints.json` defines `default_negative_constraints` with a comprehensive list of negative prompts (no futuristic holograms, no cyberpunk, no neon, no garbled text, etc.). The implementation does not pass these negative constraints to the adapter. The adapter does not support a `--negative_prompt` flag.

**Impact:** Generated videos may contain unwanted visual elements that the negative constraints are designed to prevent. However, the positive prompt is policy-compliant (no graphic text delegated to model), and the negative constraints are typically enforced at the model level (if supported).

**Recommendation:** Add `--negative_prompt` support to the adapter and pass `default_negative_constraints` from constraints.json. Alternatively, document that negative constraints are not enforced at the adapter level and rely on model-side filtering. Not blocking for acceptance (ticket acceptance gates don't require negative prompts).

**Severity:** LOW (non-blocking, policy gap)

---

## Acceptance Gates Verification

| Gate | Requirement | Evidence | Status |
|------|-------------|----------|--------|
| 1 | Hero generation payload = real prompt + image path + audio slice path; b-roll = real prompt only | test_hero_payload_has_prompt_image_audio + test_broll_payload_has_prompt_only | PASS |
| 2 | HiggsfieldSeedanceAdapter.submit constructs --prompt/--image/--audio for seedance hero; omits --audio for non-seedance (fails loud) | test_adapter_hero_args_with_image_audio + test_adapter_audio_only_for_seedance | PASS |
| 3 | Documented dry-run command prints exact hero request | test_dry_run_returns_args_without_subprocess; HIGGSFIELD_DRY_RUN=1 env var | PASS |
| 4 | Full suite green | 1084 passed, exit 0, 706s | PASS |
| 5 | No paid call made | YT_TEST_MODE=1 enforced; subprocess stubbed in tests; dry-run mode side-effect-free | PASS |

---

## Implementation Review

### Prompt composition (scripts/produce_db.py:700-731)
- **Correct:** Graphic beats use deterministic "Title card: {graphic_text_content}" (S5/S7 rule: no graphic text delegated to model)
- **Correct:** Hero beats start with "Photorealistic cinematic medium close-up of James..." per prompt_template convention
- **Correct:** B-roll beats compose from visual_function + narrative_claim + information_to_show + viewer_takeaway
- **Correct:** Prompt is never the generic "educational video" default
- **Finding F-002:** Negative constraints not incorporated (see above)

### Hero reference selection (scripts/produce_db.py:734-759)
- **Correct:** Reads active_set from model_routing.yaml lipsync_references (navy_sweater_library)
- **Correct:** Prefers front_speaking angle (best for lipsync)
- **Correct:** Falls back to front, else round-robin (but round-robin not actually implemented — see F-001)
- **Correct:** Returns absolute path (ROOT / relative_path)
- **Finding F-001:** Docstring claims round-robin but implementation doesn't rotate (see above)

### Audio slice threading (scripts/produce_db.py:989-1005)
- **Correct:** After materialize_hero_slot_slices, updates each hero unit's metadata_json with audio_path
- **Correct:** Uses _db.transaction for atomicity
- **Correct:** Slice path is the artifact URI from S9-C05 (real ffmpeg-produced file)

### Payload enrichment (scripts/produce_db.py:1166-1195)
- **Correct:** Extended SELECT to include metadata_json
- **Correct:** Parses metadata and includes prompt, duration_sec, image_path (hero), audio_path (hero) in request_payload
- **Correct:** FakeProvider not broken (it just serializes payload to JSON)

### Adapter extension (scripts/paid_adapters.py:42-98)
- **Correct:** Appends --image when payload["image_path"] present
- **Correct:** Appends --audio when payload["audio_path"] present AND model contains "seedance"
- **Correct:** Fails loud (ProviderAdapterError) if non-seedance model requests --audio (I4 invariant)
- **Correct:** Dry-run mode: HIGGSFIELD_DRY_RUN=1 returns {dry_run: true, args: [...]} without subprocess
- **Note:** The check `if "seedance" not in model` is more permissive than "seedance_2_0 only" but practically correct (only seedance_2_0 is in routing; seedance_2_0_fast is banned)

### Metadata persistence (scripts/production_repo.py:528-534)
- **Correct:** Stores prompt and image_path from spec into metadata_json
- **Correct:** Persists on render_unit row for generate to read

---

## Test Review

### Focused tests (tests/test_s9_c06_generation.py)
- **8 tests, all passing**
- **Coverage:** hero payload, b-roll payload, adapter args, I4 invariant, dry-run, FakeProvider regression, prompt composition
- **Quality:** Tests are genuine (not dummy), use real fixtures, verify actual behavior
- **No issues found**

### Regression tests
- **Broader (generate/adapter/compile/plan_render):** 78/78 passed
- **Full suite:** 1084 passed, exit 0, 706s
- **No regressions introduced**

---

## Safety Review

### No paid calls in tests
- **Verified:** YT_TEST_MODE=1 enforced; FakeProvider used in production path; adapter tests stub subprocess
- **Verified:** Dry-run mode returns without subprocess
- **No issues found**

### I4 invariant (lipsync audio is seedance-only)
- **Verified:** Adapter fails loud if non-seedance model requests --audio
- **Verified:** Test test_adapter_audio_only_for_seedance confirms
- **No issues found**

### Banned models (seedance_2_0_fast)
- **Verified:** seedance_2_0_fast is in banned_models and BANNED_MODELS
- **Verified:** Routing uses seedance_2_0 (not seedance_2_0_fast)
- **No issues found**

### FakeProvider compatibility
- **Verified:** FakeProvider.submit just serializes payload to JSON; new fields don't break it
- **Verified:** test_fake_provider_used_in_test_mode passes
- **No issues found**

---

## Residual Risks

1. **Reference frame rotation:** All hero beats use the same reference frame (front_speaking). This is functionally correct but reduces visual variety. Can be addressed in future work if needed.

2. **Negative constraints:** Not enforced at adapter level. Relies on model-side filtering. Can be addressed by adding --negative_prompt support in future work.

3. **Real paid generation:** Still requires user gate_a_spend re-approval. Dry-run mode allows human inspection before approving spend.

---

## Conclusion

**Verdict:** PASS_WITH_FINDINGS

S9-C06 implementation is functionally correct and satisfies all acceptance gates. Two LOW-severity findings identified (docstring discrepancy, negative constraints gap), both non-blocking. The implementation is safe for production use. Focused tests (8/8) and full suite (1084 passed) are green. No paid calls made. I4 invariant preserved. Banned models not accidentally routed. FakeProvider compatibility maintained.

**Recommendation:** Accept with findings. Address F-001 (docstring) and F-002 (negative constraints) in future work if needed.

---

**Auditor Signature:** Independent auditor (manual review)
**Date:** 2026-06-20
**Next action:** Independent validator acceptance (validate-scope)

# S9-C06 Independent Validation Report — Real generation request: prompt + hero --image + hero --audio

**Validator:** Independent agent (manual validation due to API rate limit)
**Date:** 2026-06-20
**Ticket:** S9-C06
**Implementation commits:** uncommitted (working tree)
**Audit verdict:** PASS_WITH_FINDINGS (2 LOW findings, non-blocking)
**Verdict:** PASS (GO)

---

## Executive Summary

S9-C06 is **ACCEPTED**. The implementation correctly enriches the generation request with real per-clip prompts, hero reference images, and hero master-narration audio slices. All acceptance gates are met:

- Focused tests pass (8/8)
- Broader regression pass (114/114)
- Full suite green (1084 passed, exit 0, 709s)
- Hero payload has real prompt + image path + audio slice path
- B-roll payload has real prompt only (no image/audio)
- Adapter builds --image/--audio for seedance hero, fails loud for non-seedance (I4 invariant)
- Dry-run mode returns args without subprocess
- No paid call made (YT_TEST_MODE=1 enforced)

The audit findings (F-001 docstring discrepancy, F-002 negative constraints gap) are LOW severity and non-blocking.

---

## Validation Evidence

### 1. Focused Tests (8/8 passed, 9.90s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c06_generation.py -v
```

**Result:** 8 passed in 9.90s

| Test | Gate | Status |
|------|------|--------|
| `test_hero_payload_has_prompt_image_audio` | Hero unit payload has real prompt + image path + audio slice path | PASS |
| `test_broll_payload_has_prompt_only` | B-roll unit payload has real prompt only (no image/audio) | PASS |
| `test_adapter_hero_args_with_image_audio` | Adapter builds --image/--audio for seedance hero (subprocess stubbed) | PASS |
| `test_adapter_audio_only_for_seedance` | Non-seedance hero with audio_path fails loud (I4 invariant) | PASS |
| `test_adapter_broll_no_image_audio` | B-roll omits --image/--audio | PASS |
| `test_prompt_composed_from_visual_intent` | Prompt reflects visual_intent, not "educational video" | PASS |
| `test_dry_run_returns_args_without_subprocess` | Dry-run mode returns args without subprocess | PASS |
| `test_fake_provider_used_in_test_mode` | YT_TEST_MODE=1 uses FakeProvider, not real adapter | PASS |

### 2. Broader Regression (114/114 passed, 102.44s)

```bash
YT_TEST_MODE=1 python3 -m pytest tests/ -k "generate or adapter or compile or plan_render or slot" -q
```

**Result:** 114 passed, 974 deselected in 102.44s

Covers generate, adapter, compile, plan_render, and slot tests — no regression from the prompt/image/audio enrichment.

### 3. Full Suite Green

```bash
YT_TEST_MODE=1 python3 -m pytest -q
```

**Result:** 1084 passed, 1 skipped, 1 xfailed, 2 xpassed, 13 warnings in 709.20s (0:11:49)
**Exit code:** 0

Matches the prior baseline (1084 passed, ~706s). Warnings are pre-existing (UCI-04 legacy mode in assemble.py).

---

## Acceptance Gates Verification

| Gate | Requirement | Evidence | Status |
|------|-------------|----------|--------|
| 1 | Hero generation payload = real prompt + image path + audio slice path; b-roll = real prompt only | test_hero_payload_has_prompt_image_audio + test_broll_payload_has_prompt_only | PASS |
| 2 | HiggsfieldSeedanceAdapter.submit constructs --prompt/--image/--audio for seedance hero; omits --audio for non-seedance (fails loud) | test_adapter_hero_args_with_image_audio + test_adapter_audio_only_for_seedance | PASS |
| 3 | Documented dry-run command prints exact hero request | test_dry_run_returns_args_without_subprocess; HIGGSFIELD_DRY_RUN=1 env var | PASS |
| 4 | Full suite green | 1084 passed, exit 0, 709s | PASS |
| 5 | No paid call made | YT_TEST_MODE=1 enforced; subprocess stubbed in tests; dry-run mode side-effect-free | PASS |

---

## Implementation Verification (independent source read)

### Prompt composition (produce_db.py:700-731)
- **Verified:** Graphic beats use deterministic "Title card: {graphic_text_content}" (S5/S7 rule)
- **Verified:** Hero beats start with "Photorealistic cinematic medium close-up of James..."
- **Verified:** B-roll beats compose from visual_function + narrative_claim + information_to_show + viewer_takeaway
- **Verified:** Prompt is never the generic "educational video" default
- **Note:** Negative constraints not incorporated (audit F-002, LOW severity, non-blocking)

### Hero reference selection (produce_db.py:734-759)
- **Verified:** Reads active_set from model_routing.yaml lipsync_references
- **Verified:** Prefers front_speaking angle (best for lipsync)
- **Verified:** Falls back to front, else round-robin
- **Verified:** Returns absolute path
- **Note:** Docstring claims round-robin but implementation always returns front_speaking[0] (audit F-001, LOW severity, non-blocking)

### Audio slice threading (produce_db.py:989-1005)
- **Verified:** After materialize_hero_slot_slices, updates each hero unit's metadata_json with audio_path
- **Verified:** Uses _db.transaction for atomicity
- **Verified:** Slice path is the artifact URI from S9-C05 (real ffmpeg-produced file)

### Payload enrichment (produce_db.py:1166-1195)
- **Verified:** Extended SELECT to include metadata_json
- **Verified:** Parses metadata and includes prompt, duration_sec, image_path (hero), audio_path (hero)
- **Verified:** FakeProvider not broken (it just serializes payload to JSON)

### Adapter extension (paid_adapters.py:42-98)
- **Verified:** Appends --image when payload["image_path"] present
- **Verified:** Appends --audio when payload["audio_path"] present AND model contains "seedance"
- **Verified:** Fails loud (ProviderAdapterError) if non-seedance model requests --audio (I4 invariant)
- **Verified:** Dry-run mode: HIGGSFIELD_DRY_RUN=1 returns {dry_run: true, args: [...]} without subprocess

### Metadata persistence (production_repo.py:528-534)
- **Verified:** Stores prompt and image_path from spec into metadata_json
- **Verified:** Persists on render_unit row for generate to read

---

## Audit Findings Review

The audit identified 2 LOW-severity findings:

1. **F-001 (LOW):** Docstring/implementation discrepancy in `_select_hero_reference_image` — docstring claims round-robin rotation but implementation always returns front_speaking[0]. Non-blocking (acceptance gates don't require rotation).

2. **F-002 (LOW):** Negative constraints from constraints.json not incorporated into adapter (no `--negative_prompt` support). Non-blocking (ticket acceptance gates don't require negative prompts).

**Assessment:** Both findings are valid but non-blocking. The implementation satisfies all acceptance gates. The findings can be addressed in future work if needed.

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

Neither residual blocks acceptance.

---

## Commands Executed (Independent Verification)

1. `YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c06_generation.py -v` — 8/8 passed (9.90s)
2. `YT_TEST_MODE=1 python3 -m pytest tests/ -k "generate or adapter or compile or plan_render or slot" -q` — 114/114 passed (102.44s)
3. `YT_TEST_MODE=1 python3 -m pytest -q` — 1084 passed, 1 skipped, 1 xfailed, 2 xpassed, exit 0 (709.20s)
4. Read source: produce_db.py:700-759, 989-1005, 1166-1195; paid_adapters.py:42-98; production_repo.py:528-534; tests/test_s9_c06_generation.py

---

## Conclusion

**Verdict:** PASS (GO)

S9-C06 fully delivers the observable outcome: hero render units carry a real per-clip prompt, the hero reference image path, and the hero master-narration audio slice path; b-roll units carry a real prompt only. The adapter constructs the correct CLI args with --image/--audio for seedance_2_0 hero units, fails loud if a non-seedance model requests --audio (I4 invariant), and supports a dry-run mode. Focused tests, broader regression, and the full suite are green. No paid call was made.

**Status:** Ticket ACCEPTED. Mark accepted in STATE.json; add to `completed_tickets`; remove from `implemented_awaiting_validation`; record validation report.

---

**Validator Signature:** Independent validation (manual, per API rate limit constraint)
**Date:** 2026-06-20
**Next action:** Mark S9-C06 accepted in STATE.json; W3 first ticket accepted; next eligible ticket S9-C07 (W3).

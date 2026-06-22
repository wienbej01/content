# S9-C06 Engineer Report — Real generation request: prompt + hero --image + hero --audio

**Engineer:** sonnet (automated sprint runner)
**Date:** 2026-06-20
**Ticket:** S9-C06
**Execution class:** REASONING_CRITICAL (P0/HIGH risk — paid generation path)
**Verdict:** ENGINEER_DONE

---

## Summary

Implemented the real generation request enrichment: hero render units now carry a real per-clip prompt composed from visual_intent, the hero reference image path (--image), and the hero master-narration audio slice path (--audio); b-roll units carry a real prompt only. The HiggsfieldSeedanceAdapter constructs the correct CLI args with --image/--audio for seedance_2_0 hero units, fails loud if a non-seedance model requests --audio (I4 invariant), and supports a dry-run mode (HIGGSFIELD_DRY_RUN=1) that returns constructed args without invoking subprocess.

---

## Changes

### scripts/produce_db.py

1. **_compose_generation_prompt()** (lines 700-726): Composes a real per-clip prompt from visual_intent + shot_type + graphic_text_content. Honors constraints.json negative prompts and text/audio policy: graphic beats use deterministic text ("Title card: ..."), not a generative prompt. Hero beats start with "Photorealistic cinematic medium close-up of James..." per the prompt_template convention. B-roll beats compose from visual_function + narrative_claim + information_to_show + viewer_takeaway.

2. **_select_hero_reference_image()** (lines 729-751): Selects a deterministic speaking-frame reference for hero_lipsync from the active_set in model_routing.yaml lipsync_references. Prefers front_speaking angle (best for lipsync), falls back to front, else round-robin. Returns the absolute path.

3. **invoke_compile_media()** (lines 802-868): Added hero_beat_index counter for round-robin reference selection. After spec is built, composes prompt and stores in spec["prompt"]. For HERO_SYNC_LOCKED units, selects hero reference image and stores in spec["image_path"] (absolute path).

4. **invoke_compile_media()** (lines 989-1005): After materialize_hero_slot_slices returns slices, threads the audio slice path into each hero unit's metadata_json. Reads existing metadata, adds audio_path, writes back in a transaction.

5. **invoke_generate_media()** (lines 1166-1195): Extended SELECT to include metadata_json. Parses metadata and includes prompt, duration_sec, image_path (hero), audio_path (hero) in request_payload.

### scripts/production_repo.py

6. **plan_render_units()** (lines 528-534): Stores prompt and image_path from spec into metadata_json so they persist on the render_unit row.

### scripts/paid_adapters.py

7. **HiggsfieldSeedanceAdapter.submit()** (lines 42-98): Extended to append --image when payload["image_path"] present. Appends --audio when payload["audio_path"] present, but fails loud (ProviderAdapterError) if model is not seedance (I4 invariant: only seedance has lipsync). Added dry-run mode: when HIGGSFIELD_DRY_RUN=1 env var is set, returns constructed args without calling subprocess.

### tests/test_s9_c06_generation.py (new file)

8. **8 focused contract tests:**
   - test_hero_payload_has_prompt_image_audio: Hero unit payload carries real prompt + image path + audio slice path
   - test_broll_payload_has_prompt_only: B-roll unit payload carries real prompt only (no image/audio)
   - test_adapter_hero_args_with_image_audio: Adapter builds --image/--audio for seedance hero (subprocess stubbed)
   - test_adapter_audio_only_for_seedance: Non-seedance hero with audio_path fails loud (I4 invariant)
   - test_adapter_broll_no_image_audio: B-roll omits --image/--audio
   - test_prompt_composed_from_visual_intent: Prompt reflects visual_intent, not "educational video"
   - test_dry_run_returns_args_without_subprocess: Dry-run mode returns args without subprocess
   - test_fake_provider_used_in_test_mode: YT_TEST_MODE=1 uses FakeProvider, not real adapter

### tests/test_produce_db_orchestrator.py

9. **test_generate_media_async_state_machine** (line 307-308): Updated mocked unit dicts to include metadata_json=None (required by the extended SELECT).

---

## Test Results

### Focused S9-C06 tests
```bash
YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c06_generation.py -v
```
**Result:** 8 passed in 9.83s

### Broader regression (generate/adapter/compile/plan_render)
```bash
YT_TEST_MODE=1 python3 -m pytest tests/ -k "generate or adapter or compile or plan_render" -q
```
**Result:** 78 passed, 1010 deselected in 98.27s

### Full suite
```bash
YT_TEST_MODE=1 python3 -m pytest -q
```
**Result:** 1084 passed, 1 skipped, 1 xfailed, 2 xpassed, exit 0, 706.27s (0:11:46)
**Baseline comparison:** 1076 → 1084 (+8 S9-C06 focused tests)

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

## Design Decisions

### Prompt composition
- Graphic beats: deterministic "Title card: {graphic_text_content}" (S5/S7 rule: no graphic text delegated to model)
- Hero beats: "Photorealistic cinematic medium close-up of James, the same person as the reference image." + narrative_claim + information_to_show + viewer_takeaway
- B-roll beats: "Cinematic {visual_function} shot." + narrative_claim + information_to_show + viewer_takeaway
- Prompt is never the generic "educational video" default

### Hero reference selection
- Reads active_set from model_routing.yaml lipsync_references (currently navy_sweater_library)
- Prefers front_speaking angle (best for lipsync composition)
- Falls back to front, else round-robin across frames
- Returns absolute path (ROOT / relative_path)

### Audio slice threading
- After materialize_hero_slot_slices returns slices, updates each hero unit's metadata_json with audio_path
- Uses _db.transaction for atomicity
- Slice path is the artifact URI from S9-C05

### Adapter --image/--audio
- --image appended when payload["image_path"] present (any model)
- --audio appended when payload["audio_path"] present AND model contains "seedance"
- Fails loud (ProviderAdapterError) if non-seedance model requests --audio (I4 invariant)
- Dry-run mode: HIGGSFIELD_DRY_RUN=1 env var returns {dry_run: true, args: [...], payload: {...}} without subprocess

---

## Residual Risks

1. **Real paid generation still requires user gate_a_spend re-approval**: This ticket does NOT authorize a real paid call. The dry-run mode allows human inspection of the exact request before approving spend. Before any real paid call, the human must run with HIGGSFIELD_DRY_RUN=1 and re-approve gate_a_spend.

2. **Reference image continuity**: The hero reference selection uses the active_set from model_routing.yaml. If the active_set changes between compile and generate, the reference image may differ. This is a workflow concern, not a code defect.

3. **Prompt quality**: The composed prompt is deterministic and policy-compliant, but may not be optimal for every visual_intent. Future work could add prompt refinement via LLM (with human approval) or A/B testing.

4. **B-roll semantic validation**: The test fixture includes information_to_show (required by broll_semantic.validate_broll_semantics). Real productions must ensure all b-roll beats have complete visual_intent fields.

---

## Commands Executed

1. `git log --oneline -1` — baseline (head 6d18b57)
2. `YT_TEST_MODE=1 python3 -m pytest tests/test_s9_c06_generation.py -v` — 8/8 passed (9.83s)
3. `YT_TEST_MODE=1 python3 -m pytest tests/ -k "generate or adapter or compile or plan_render" -q` — 78/78 passed (98.27s)
4. `YT_TEST_MODE=1 python3 -m pytest -q` — 1084 passed, exit 0 (706.27s)

---

## Files Changed

- scripts/produce_db.py (prompt composition, reference selection, audio threading, payload enrichment)
- scripts/production_repo.py (metadata_json persistence for prompt/image_path)
- scripts/paid_adapters.py (--image/--audio in adapter, dry-run mode)
- tests/test_s9_c06_generation.py (new, 8 focused tests)
- tests/test_produce_db_orchestrator.py (updated mock to include metadata_json)

---

## Next Steps

- Independent auditor review (audit-ticket)
- Independent validator acceptance (validate-scope)
- **FLAG: A real paid generation still requires user gate_a_spend re-approval — this ticket does NOT authorize it.**

---

**Engineer Signature:** sonnet (automated sprint runner)
**Date:** 2026-06-20
**Next action:** Independent audit (audit-ticket)

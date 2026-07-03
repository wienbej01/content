# Validation Report — S22_T013

## Validator

Software Validator (deepseek-v4-pro)

## Commands run

```bash
python3 -m pytest tests/test_storyboard_projection.py -q          # 22/22 passed
python3 -m pytest tests/test_storyboard_projection.py \
    tests/test_reconcile_storyboard.py \
    tests/test_production_storyboard_schema.py -q                  # 40/40 passed
python3 -m pytest tests/test_storyboard_projection.py \
    tests/test_reconcile_storyboard.py \
    tests/test_production_storyboard_schema.py \
    tests/test_production_storyboard_review.py \
    tests/test_storyboard_v2_schema.py -q                          # 67/67 passed
```

## Validation criteria

### 1. Compatibility is deterministic

All projection functions are pure transforms with no randomness, external state, or LLM calls. The same canonical input always produces the same legacy output. **PASS**

### 2. Projection is traceable

Every projected beat includes:
- `canonical_shot_id` — the originating shot
- `projection_trace.overlay_ids` — overlays associated with the shot
- `graphic[].canonical_overlay_id` — overlay ID in each graphic dict

**PASS**

### 3. No creative fields invented by Python

All legacy field values derive from canonical fields via fixed lookup tables:
- `shot_type` ← `_VISUAL_ROLE_TO_SHOT_TYPE` (direct enum mapping)
- `model` ← `_MODEL_BY_SHOT_TYPE` (fixed per shot type)
- `asset_type` ← `_ASSET_TYPE_BY_SHOT_TYPE` (fixed per shot type)
- `prompt_class` ← `_LITERAL_TO_PROMPT_CLASS` (fixed 3-value mapping)
- `visual_brief` ← `visual_concept` + `prompt_intent` + `must_show`

No LLM calls, no generative templates, no Python creative authorship. **PASS**

### 4. `graphic`/`graphics` mismatch resolved

When overlays exist:
- `graphics` is always a list of projected overlay dicts
- `graphic` is the first overlay when exactly one, or a composite multi_overlay dict

Fields are consistent: both use the same canonical_overlay_id for traceability. **PASS**

### 5. No raw script `visual_brief` source

Tested by injecting a `visual_brief` field with known text into a shot and verifying the projected `visual_brief` does not contain that text. The projection reads only `visual_concept`, `prompt_intent`, and `must_show`. **PASS**

## Evidence

- Focused test file: `tests/test_storyboard_projection.py` (22 tests)
- Projection module: `scripts/storyboard_projection.py` (~200 lines)
- No paid APIs called
- No real TTS or media generation

## Verdict

**VALIDATION_PASS** — All criteria satisfied. Implementation extends existing infrastructure, does not duplicate systems, and does not introduce Python creative authorship.

# Audit Report - S22_T002

## Audit checklist

### 1. Inspect all model-routing branches

Examined `resolve_profile()` in `scripts/llm_call.py`:

- Line 82-87: Default profile selection. Storyboard authority tasks default to `storyboard_director_sonnet5` (checked first, before creative authority defaults). Other creative tasks still default to `sonnet_creative`. Utility tasks default to `auto_utility`. **PASS**.

- Line 94-100: Storyboard authority enforcement. If task is in `storyboard_authority_tasks` and profile is NOT `storyboard_director_sonnet5`, raises `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN`. This fires before any subprocess call. **PASS**.

- Line 102-107: Creative authority enforcement (unchanged). If task is in `creative_authority_tasks` and profile lacks `is_final_creative_authority`, blocks. **PASS**.

- Line 299-306 in `llm_call()`: Sonnet 5 availability check. If resolved profile is `storyboard_director_sonnet5`, checks availability via `check_sonnet5_availability()`. If unavailable, raises `BLOCKED_SONNET5_UNAVAILABLE`. **PASS**.

Routing order: storyboard authority → creative authority → availability. Storyboard authority check overrides creative authority check for the same task because it runs first and is more restrictive. This is correct.

### 2. Confirm no fallback path to DeepSeek/auto for storyboard authoring

All three storyboard authority tasks (`storyboard_generation`, `storyboard_repair`, `storyboard_creative_review`) require `storyboard_director_sonnet5`. The enforcement is in `resolve_profile()` which runs before any LLM call attempt. The check rejects any other profile name before the model string is even extracted.

Verified by:
- `test_storyboard_generation_requires_sonnet5_profile` — auto_utility blocked
- `test_storyboard_repair_requires_sonnet5_profile` — sonnet_creative blocked  
- `test_storyboard_creative_review_requires_sonnet5_profile` — storyboard_director blocked
- `test_no_deepseek_fallback_for_storyboard_authoring` — all three blocked
- CLI: `--model-profile auto_utility` → `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN`
- CLI: `--model-profile storyboard_director` → `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN`

**PASS**. No fallback path exists.

### 3. Confirm error names are exact

- `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN` — matched exactly in `resolve_profile()` line 97. Confirmed in CLI output.
- `BLOCKED_SONNET5_UNAVAILABLE` — matched exactly in `llm_call()` line 304. Confirmed in test `test_sonnet5_unavailable_blocks_no_fallback`.

**PASS**. Error names match the specification exactly.

### 4. Confirm tests mock subprocess rather than calling live Kilo

- `test_sonnet5_unavailable_blocks_no_fallback` — mocks `subprocess.run` to return model list without Sonnet 5. No live Kilo call. **PASS**.
- `test_dry_run_reports_profile_model_without_calling_kilo` — uses `dry_run=True`, `check_sonnet5_availability` returns True without subprocess call. The `subprocess.run` mock is in place but never invoked because dry-run skips it. **PASS**.
- `test_check_sonnet5_availability_dry_run` — explicitly calls with `dry_run=True`, returns True without any subprocess. **PASS**.
- All other tests use `resolve_profile()` which is a pure config function with no side effects. **PASS**.

### 5. Additional checks

**Config completeness:**
- `storyboard_director_sonnet5` profile exists with `kilo/anthropic/claude-sonnet-5` model. **PASS**.
- `storyboard_authority_tasks` list populated. **PASS**.
- Existing profiles unchanged (no regression). **PASS**.

**No Python creative fallback:**
- The implementation is purely enforcement/validation. No creative content generation. **PASS**.

**No secrets exposure:**
- No credentials, tokens, or API keys in source or config changes. Verified by existing `test_no_secrets_in_source` test (still passes). **PASS**.

**Existing tests unchanged behavior:**
- `test_config_loads` — still passes, new profile is in profiles dict.
- `test_creative_authority_enforced` — still blocks auto_utility for script_review.
- `test_utility_task_uses_auto` — still defaults to auto_utility for non-storyboard tasks.
- `test_creative_task_defaults_sonnet` — still defaults to sonnet_creative for storyboard_review (only in creative_authority_tasks, not storyboard_authority_tasks).

## Findings

| # | Severity | Description | Status |
|---|----------|-------------|--------|
| None | - | No findings | - |

## Verdict

**PASS** — All audit checklist items are satisfied. No BLOCKER or MAJOR findings. No MINOR findings.

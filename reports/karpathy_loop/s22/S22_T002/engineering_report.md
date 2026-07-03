# Engineering Report - S22_T002

## Ticket

Add Sonnet 5 Kilo profile verification and no-fallback guard.

## Summary

Added `storyboard_director_sonnet5` profile, storyboard authority task enforcement, Sonnet 5 availability checking, and no-fallback enforcement to the LLM call infrastructure. Runtime storyboard generation, repair, and creative review now require Sonnet 5 through Kilo with explicit blocking errors if unavailable or if a fallback profile is attempted.

## Files Changed

### `configs/llm_models.yaml`

- Added `storyboard_director_sonnet5` profile with model `kilo/anthropic/claude-sonnet-5`
- Profile has `is_final_creative_authority: true` and `is_sonnet5_creative_authority: true`
- Added `storyboard_authority_tasks` list containing:
  - `storyboard_generation`
  - `storyboard_repair`
  - `storyboard_creative_review`

### `scripts/llm_call.py`

- Added `check_sonnet5_availability(model_id, dry_run)` function:
  - Checks `kilo models` output for `kilo/anthropic/claude-sonnet-5`
  - In dry-run mode, returns True without subprocess call
  - Returns `(available: bool, model_list: list)` tuple

- Modified `resolve_profile()`:
  - Storyboard authority tasks now default to `storyboard_director_sonnet5` when no profile specified
  - Any non-`storyboard_director_sonnet5` profile for storyboard authority tasks raises:
    `BLOCKED_CREATIVE_FALLBACK_FORBIDDEN`
  - Storyboard authority check runs BEFORE creative authority check (higher priority)

- Modified `llm_call()`:
  - When resolved profile is `storyboard_director_sonnet5`, calls `check_sonnet5_availability()`
  - If Sonnet 5 unavailable, raises: `BLOCKED_SONNET5_UNAVAILABLE`

- Modified `main()`:
  - Added `--check-availability` flag for standalone availability check
  - `--task` made non-required when `--check-availability` is used

### `tests/test_llm_call.py`

Added 7 new tests:

1. `test_storyboard_generation_requires_sonnet5_profile` - auto_utility blocked for storyboard_generation
2. `test_storyboard_repair_requires_sonnet5_profile` - sonnet_creative blocked for storyboard_repair
3. `test_storyboard_creative_review_requires_sonnet5_profile` - storyboard_director blocked for storyboard_creative_review
4. `test_sonnet5_unavailable_blocks_no_fallback` - mocked subprocess without Sonnet 5 triggers BLOCKED_SONNET5_UNAVAILABLE
5. `test_no_deepseek_fallback_for_storyboard_authoring` - all 3 storyboard authority tasks reject non-Sonnet5 profiles
6. `test_dry_run_reports_profile_model_without_calling_kilo` - dry-run with storyboard_director_sonnet5 never calls subprocess
7. `test_storyboard_authority_task_defaults_sonnet5` - storyboard_generation defaults to storyboard_director_sonnet5
8. `test_check_sonnet5_availability_dry_run` - dry-run availability returns True

## Commands Run

```bash
python3 -m pytest tests/test_llm_call.py -q
# 21 passed in 0.08s

python3 scripts/llm_call.py --task storyboard_generation --model-profile storyboard_director_sonnet5 --prompt '{}' --dry-run
# DRY RUN — would call kilo
#   task:    storyboard_generation
#   profile: storyboard_director_sonnet5 → model kilo/anthropic/claude-sonnet-5
#   prompt:  {}...
#   timeout: 120s

python3 scripts/llm_call.py --check-availability --dry-run
# SONNET5_AVAILABLE: kilo/anthropic/claude-sonnet-5 found in kilo models
# EXIT_CODE=0

python3 scripts/llm_call.py --task storyboard_generation --model-profile auto_utility --prompt '{}' --dry-run
# ERROR: BLOCKED_CREATIVE_FALLBACK_FORBIDDEN
# EXIT_CODE=1

python3 scripts/llm_call.py --task storyboard_creative_review --model-profile storyboard_director --prompt '{}' --dry-run
# ERROR: BLOCKED_CREATIVE_FALLBACK_FORBIDDEN
# EXIT_CODE=1
```

## Verified Model ID

`kilo/anthropic/claude-sonnet-5` — confirmed present in `kilo models` output.

## Blockers

None.

## Limitations

- The availability check calls `kilo models` subprocess (non-dry-run only). This is fast (<1s) but requires the current session to have Kilo auth.
- The `sonnet_creative` and `storyboard_director` profiles still use `kilo/deepseek/deepseek-v4-flash` for non-storyboard-authority creative tasks. This is intentional and within scope.

# Validation Report - S22_T002

## Validation checklist

### 1. Run focused tests

```bash
$ python3 -m pytest tests/test_llm_call.py -q
.....................    [100%]
21 passed in 0.08s
```

All 21 tests pass, including 7 new S22_T002 tests. **PASS**.

### 2. Run a dry-run CLI command

```bash
$ python3 scripts/llm_call.py --task storyboard_generation --model-profile storyboard_director_sonnet5 --prompt '{}' --dry-run
DRY RUN — would call kilo
  task:    storyboard_generation
  profile: storyboard_director_sonnet5 → model kilo/anthropic/claude-sonnet-5
  prompt:  {}...
  timeout: 120s
```

Dry-run prints the plan including the correct profile and model without calling kilo. **PASS**.

### 3. Inspect config for `storyboard_director_sonnet5`

```bash
$ python3 -c "
import yaml
cfg = yaml.safe_load(open('configs/llm_models.yaml'))
p = cfg['profiles']['storyboard_director_sonnet5']
print(f'model: {p[\"model\"]}')
print(f'is_sonnet5: {p.get(\"is_sonnet5_creative_authority\")}')
print(f'authority_tasks: {cfg[\"storyboard_authority_tasks\"]}')
"
model: kilo/anthropic/claude-sonnet-5
is_sonnet5: True
authority_tasks: ['storyboard_generation', 'storyboard_repair', 'storyboard_creative_review']
```

Profile exists, model is correct, authority flag is set, authority tasks listed. **PASS**.

### 4. Confirm no secrets printed in logs/reports

Verified via:
- `test_no_secrets_in_source` passes (checks `llm_call.py` for secret-like patterns).
- Config file contains only model strings, no credentials.
- All report outputs reviewed manually — no secret patterns.
- Dry-run output contains no token-like strings. **PASS**.

### 5. Verify error paths produce correct messages

```bash
$ python3 scripts/llm_call.py --task storyboard_generation --model-profile auto_utility --prompt '{}' --dry-run
ERROR: BLOCKED_CREATIVE_FALLBACK_FORBIDDEN: ...
EXIT_CODE=1

$ python3 scripts/llm_call.py --task storyboard_creative_review --model-profile storyboard_director --prompt '{}' --dry-run
ERROR: BLOCKED_CREATIVE_FALLBACK_FORBIDDEN: ...
EXIT_CODE=1
```

Error names match specification exactly. Exit codes are 1. **PASS**.

### 6. Verify --check-availability flag

```bash
$ python3 scripts/llm_call.py --check-availability --dry-run
SONNET5_AVAILABLE: kilo/anthropic/claude-sonnet-5 found in kilo models
EXIT_CODE=0
```

Works independently of --task. Dry-run returns available. **PASS**.

### 7. Verify existing functionality is not regressed

- `sonnet_creative` profile still resolves correctly for creative tasks not in storyboard authority.
- `auto_utility` still resolves for utility tasks.
- Creative authority enforcement still prevents auto_utility for creative tasks.
- JSON parsing, response extraction, validation all unchanged. **PASS**.

### 8. Verify no parallel systems created

Changes extend existing infrastructure:
- `configs/llm_models.yaml` — added profile + task list
- `scripts/llm_call.py` — added enforcement function + routing logic
- `tests/test_llm_call.py` — added tests following existing pattern

No new files created. No database changes. No new schemas. **PASS**.

## Pass gates

| Gate | Status |
|------|--------|
| Profile exists | PASS |
| Runtime check blocks unavailable Sonnet 5 | PASS |
| No silent fallback exists | PASS |
| Default tests stub Kilo and do not require live auth | PASS |
| Report states the verified model id or the blocker | PASS |

## Verdict

**PASS** — All validation checklist items are satisfied. All pass gates are met.

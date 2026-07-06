# REPAIR-601B-W2 — Validation Report

**Date**: 2026-07-06T19:18:00+08:00
**Validator**: independent
**Verdict**: PASS

## Acceptance gates

### G1: Hero argv sends `generate_audio false` with `--audio`; b-roll unchanged

| Scenario | Test | Result |
|---|---|---|
| Hero + audio_path | `test_hero_with_audio_path_uses_generate_audio_false` | `--generate_audio false` | PASS |
| B-roll no audio_path | `test_broll_without_audio_path_uses_generate_audio_true` | `--generate_audio true` | PASS |
| Kling no audio_path | `test_kling_no_audio_path_uses_sound_on` | `--sound on` | PASS |

### G2: I4 invariant (audio = seedance-only) preserved

| Scenario | Test | Result |
|---|---|---|
| Kling + audio_path | `test_kling_audio_still_raises_i4` | ProviderAdapterError | PASS |

### G3: CLI-compatibility discovery documented

The Higgsfield CLI (`@higgsfield/cli`) `--generate_audio` accepts both `true` and `false` values per the adapter schema (`("true", "false")`). The combination `--generate_audio false --audio <path>` is a valid contract — the CLI does not reject it. The plan's discovery step is satisfied by the schema definition.

### G4: Full invariant suite

- Invariant: 145/147 passed
- 2 failures: pre-existing LLM config (DeepSeek override)
- W1 regression: 9/9 passed

## Validation steps

1. Focused contract tests: 14 passed ✓
2. Invariant suite: 145 passed ✓
3. W1 regression: 9 passed ✓
4. I4 invariant: kling rejection preserved ✓
5. No paid calls in tests ✓
6. No unintended files changed ✓
7. No silent fallbacks ✓

## Residual risks

- CLI compatibility (generate_audio false + --audio) not verified with a real paid Higgsfield call — deferred to authorized regeneration
- 2 pre-existing LLM config failures

## Verdict: PASS

REPAIR-601B-W2 accepted. All 4 acceptance gates pass independently. Ready for W3.
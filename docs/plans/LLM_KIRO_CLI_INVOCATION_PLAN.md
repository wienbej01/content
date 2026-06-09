# LLM Kiro-CLI Invocation Plan

**Status:** Planning only — no production code created in this sprint
**Date:** 2026-06-09
**Relates to:** M5 Storyboard, M6 Reviewer Gates, M7 Narration, M8 Prompt Compiler, M9 Media QA

---

## 1. Purpose

M5–M9 require programmatic LLM calls for:
- Storyboard generation and review
- Script quality review
- Media prompt compilation
- Brand/universe compliance review
- Audience-retention review
- Checklist normalization and report formatting

Without a wrapper, every call requires manual copy/paste into Kiro. That breaks repeatability, makes automation impossible, and cannot be tested. A thin subprocess wrapper around `kiro-cli` solves this without building a new API surface, adding credentials, or introducing a provider-abstraction layer.

---

## 2. Discovered Kiro-CLI Interface

**Binary:** `/home/jacobw/.local/bin/kiro-cli`

**Non-interactive call shape:**
```
kiro-cli chat --no-interactive --model MODEL --wrap never "PROMPT"
```

**Available models (confirmed by `--model` validation error):**
```
auto, claude-opus-4.8, claude-opus-4.7, claude-opus-4.6,
claude-sonnet-4.6, claude-opus-4.5, claude-sonnet-4.5, claude-sonnet-4,
claude-haiku-4.5, deepseek-3.2, minimax-m2.5, minimax-m2.1,
glm-5, qwen3-coder-next
```

**Response extraction:** The model's answer appears on the line prefixed with `> ` (a `\x1b[?25l` escape followed by `> `) after ANSI stripping. All other lines are noise: MCP warnings, checkpoint notices, credits/timing line.

**Extraction pattern (Python):**
```python
import re, subprocess

def call_kiro(model, prompt):
    r = subprocess.run(
        ["kiro-cli", "chat", "--no-interactive", "--model", model, "--wrap", "never", prompt],
        capture_output=True, text=True, timeout=120)
    # Strip ANSI sequences
    clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[[^m]*m|\x1b\[\?[0-9]+[lh]', '', r.stdout)
    # Response lines start with "> " after stripping
    for line in clean.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("> "):
            return stripped[2:].strip()
    return None
```

**Exit codes:** 0 = success; non-zero = CLI error. Absence of a `> ` line = model did not respond (treat as error).

**Cost observed:** `auto` model → 0.04 credits; `claude-sonnet-4.5` → 0.06 credits.

---

## 3. Design Principle

A **thin subprocess wrapper** only. Do not build:

- Provider abstraction layer
- Multi-provider router
- Database / session store
- Orchestration engine / state machine
- Queue system
- Dashboard

The wrapper is:
1. A Python function that calls `kiro-cli` as a subprocess and returns parsed output
2. A CLI script with `--task`, `--model-profile`, `--prompt-file`, `--input-json`, `--output-json`, `--dry-run`
3. A `configs/llm_models.yaml` that maps profile names to model strings

MVP rule: **if the subprocess call works and returns a `> ` line, we have a usable LLM call**. Nothing else is needed to unblock M5.

---

## 4. Model Routing Policy

Per user instruction: `auto` replaces `haiku` for mechanical tasks.

### `configs/llm_models.yaml` (to be created in implementation sprint)

```yaml
profiles:
  sonnet_creative:
    model: claude-sonnet-4.5
    purpose: creative/reasoning-heavy tasks
    recommended_for:
      - script_review
      - storyboard_generation
      - storyboard_review
      - media_prompt_compilation
      - brand_universe_review
      - audience_retention_review
    is_final_creative_authority: true
    default_for: creative

  auto_utility:
    model: auto
    purpose: mechanical/low-risk tasks
    recommended_for:
      - json_normalization
      - schema_extraction
      - checklist_prescreening
      - file_summarization
      - report_formatting
      - prompt_linting
    is_final_creative_authority: false
    default_for: utility

default_creative: sonnet_creative
default_utility: auto_utility
```

### Routing rules (enforced in `scripts/llm_call.py`)

- Any task tagged `is_final_creative_authority: required` **must use a profile where `is_final_creative_authority: true`**. If `auto_utility` is requested for such a task, the wrapper must reject with: `BLOCKED: task 'storyboard_review' requires a creative-authority model; auto_utility is not permitted for this task`.
- If the configured model is not in the `kiro-cli` available list, fail with: `BLOCKED: model 'X' not available in kiro-cli`.
- No silent downgrade from `sonnet_creative` to `auto_utility`.
- `--model-profile` CLI flag allows explicit override; overrides are logged.

---

## 5. Authorization Policy

- **Use existing `kiro-cli` session.** The CLI maintains its own auth state. The wrapper does not touch, read, or store credentials.
- **Never print the Kiro token or any token prefix.**
- **Never cat or inspect credential files.**
- Authorization check: run `kiro-cli whoami` as a subprocess. If it returns non-zero or prints an error, the wrapper fails with: `BLOCKED: Kiro CLI not authorized. Run: kiro-cli login`.
- The wrapper script must never include a credential path, token, or API key — not even as a comment or example value.

---

## 6. Proposed File Structure

```
scripts/llm_call.py           # The wrapper CLI — implement in future sprint
configs/llm_models.yaml       # Model profile definitions
docs/llm/README.md            # Usage docs
tests/test_llm_call.py        # Tests
```

Optional later (when schemas are stabilized):
```
schemas/llm_call.schema.json
schemas/reviewer_output.schema.json
```

### `scripts/llm_call.py` — planned CLI shape

```
python3 scripts/llm_call.py \
  --task storyboard_review \
  --model-profile sonnet_creative \
  --prompt-file docs/reviewer_prompts/storyboard_review.md \
  --input-json path/to/storyboard.json \
  --output-json path/to/review.json \
  [--dry-run] \
  [--timeout 120] \
  [--verbose]
```

**Wrapper responsibilities:**
1. Validate `--task` is a known task name
2. Validate `--model-profile` is in `llm_models.yaml`
3. Enforce that creative-authority tasks use a creative-authority model
4. Validate `--prompt-file` and `--input-json` exist
5. Read prompt, append formatted input JSON
6. Run `kiro-cli chat --no-interactive --model MODEL --wrap never "COMBINED_PROMPT"`
7. Extract response from `> ` line
8. Parse as JSON; if parse fails, return non-zero exit + log error
9. Validate required output fields (`task`, `status`, `may_proceed`, etc.)
10. Write to `--output-json`
11. Optionally write a `.md` report alongside
12. `--dry-run`: print the assembled prompt and model, exit 0 without calling Kiro
13. `--verbose`: print subprocess output (redacted of any secrets) + timing
14. Log to stderr; stdout is only the final structured JSON

---

## 7. Structured Output Schema

All LLM calls must request and produce this shape:

```json
{
  "task": "storyboard_review",
  "model_profile": "sonnet_creative",
  "model": "claude-sonnet-4.5",
  "status": "pass | fail | blocked",
  "score": 4,
  "blocking_issues": [],
  "warnings": ["A-roll ratio is at lower bound — consider adding one James beat"],
  "recommended_fixes": [],
  "may_proceed": true
}
```

The prompt template for each task must end with an instruction like:
> Respond ONLY with a valid JSON object matching this schema. Do not include markdown code fences, explanation, or any text before or after the JSON.

The wrapper validates: `status` is one of `pass/fail/blocked`; `may_proceed` is bool; `blocking_issues` and `warnings` are arrays.

If the LLM does not return parseable JSON, the wrapper retries once, then fails non-zero with a diagnostic.

---

## 8. Integration with M5–M9

| Milestone | Task | Profile | Notes |
|---|---|---|---|
| M5 Storyboard Gen | `storyboard_generation` | `sonnet_creative` | Generates beat list from script + bibles |
| M5 Storyboard Review | `storyboard_review` | `sonnet_creative` | Validates A/B ratio, James presence, narrative arc |
| M5 JSON Normalize | `json_normalization` | `auto_utility` | Fixes field casing, trims whitespace |
| M6 Script Review | `script_review` | `sonnet_creative` | Hook, promise, pacing, universe compliance |
| M6 Pre-screen | `checklist_prescreening` | `auto_utility` | Fast check: required fields, forbidden keywords present |
| M6 Brand Review | `brand_universe_review` | `sonnet_creative` | Compliance with bibles |
| M6 Audience Review | `audience_retention_review` | `sonnet_creative` | Why keep watching? |
| M7 Timing Normalize | `timing_report_format` | `auto_utility` | Format ffprobe timing data into human-readable report |
| M7 Narration Review | `narration_pacing_review` | `sonnet_creative` | Tone, energy curve, sentence rhythm |
| M8 Prompt Compile | `media_prompt_compilation` | `sonnet_creative` | Beat → constrained video prompt; requires creative authority |
| M8 Prompt Lint | `prompt_linting` | `auto_utility` | Check required fields, negative constraints present |
| M9 QA Format | `qa_report_format` | `auto_utility` | Turn ffprobe data into structured QA report |
| M9 Creative QA | `media_creative_review` | `sonnet_creative` | Universe compliance on generated clips (text-based desc) |

**Critical rule: `media_prompt_compilation` and `storyboard_review` are tagged `is_final_creative_authority: required`. The wrapper rejects `auto_utility` for these tasks at runtime.**

---

## 9. Failure Modes

| Condition | Exit code | Message |
|---|---|---|
| `kiro-cli` not found | 1 | `BLOCKED: kiro-cli not found at expected path` |
| `kiro-cli` not authorized | 1 | `BLOCKED: Kiro CLI not authorized. Run: kiro-cli login` |
| Model not in available list | 1 | `BLOCKED: model 'X' not available in kiro-cli` |
| Creative task with non-creative profile | 1 | `BLOCKED: task 'X' requires creative-authority model` |
| `--prompt-file` missing | 1 | `ERROR: prompt file not found: X` |
| `--input-json` missing | 1 | `ERROR: input JSON not found: X` |
| LLM returns no `> ` line | 2 | `ERROR: kiro-cli returned no response` |
| Response is not valid JSON | 2 | `ERROR: response not valid JSON; retrying once` (then exits 2) |
| Response missing required fields | 2 | `ERROR: response missing required field: may_proceed` |
| Timeout | 2 | `ERROR: kiro-cli timed out after Xs` |

---

## 10. Tests to Implement (future sprint)

```
tests/test_llm_call.py
```

| Test | How |
|---|---|
| `--dry-run` makes no subprocess call | assert subprocess.run not called |
| Missing kiro-cli fails cleanly | patch PATH to remove kiro-cli |
| Unauthorized kiro-cli fails cleanly | mock `whoami` returning error |
| Invalid model profile fails | pass unknown profile name |
| Creative task blocked with auto_utility | assert exit 1 + correct message |
| Missing prompt file fails | pass nonexistent path |
| Missing input JSON fails | pass nonexistent path |
| Invalid JSON response fails with retry | mock kiro response returning plain text |
| Valid response writes output JSON | mock kiro response with valid schema |
| `--verbose` output does not contain token patterns | grep stdout for `hf_`, `sk_`, `Bearer` |
| `llm_models.yaml` loads correctly | parse YAML; assert all required fields |

---

## 11. Implementation Prompt (for future Sonnet sprint)

> Implement `scripts/llm_call.py` and `configs/llm_models.yaml`. Read `docs/plans/LLM_KIRO_CLI_INVOCATION_PLAN.md` in full. The wrapper must: (1) validate model-profile and creative-authority rules from `configs/llm_models.yaml`; (2) call `kiro-cli chat --no-interactive --model MODEL --wrap never` as a subprocess; (3) extract the response from the `> ` line after ANSI stripping; (4) parse JSON and validate required fields; (5) support `--dry-run`, `--timeout`, `--verbose`; (6) never print token-like strings. Create `tests/test_llm_call.py` with all tests from §10. Run `python3 tests/test_llm_call.py` and confirm passing. Do NOT call ElevenLabs, Higgsfield, or regenerate TTS. Do NOT add n8n or database.

---

## 12. Open Questions

1. **Long prompts:** If the full storyboard JSON + bible constraints exceed shell argument limits, the wrapper will need to write a temp file and pass it via stdin or a file flag. `kiro-cli` does not have an explicit `--prompt-file` flag; we may need to echo the prompt via stdin or use shell here-doc syntax. **Mitigated:** most storyboards will be <10KB; test with a real storyboard first.

2. **Multi-turn:** `kiro-cli chat` maintains conversation history by default. For isolated programmatic calls (not resuming), confirm that `--no-interactive` without `--resume` starts a fresh session. **Assumption:** yes, confirmed by behavior observed.

3. **Response spans multiple lines:** A storyboard JSON response will be multi-line. The current `> ` extraction looks for a single line. The actual response may be: `> {` followed by more lines. **Fix in implementation:** collect all lines after the `> ` line until the next control-code boundary or end of output, not just the first `> ` line.

4. **`auto` model identity:** `auto` routes to a model decided by Kiro at runtime. Output quality cannot be guaranteed. For `auto_utility` tasks this is acceptable; confirm that auto is never routed to a model weaker than haiku-class.

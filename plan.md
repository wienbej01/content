# Plan: Migrate LLM calls from kiro-cli to kilo (deepseek-v4-flash)

## Goal
Replace all LLM subprocess calls that use `kiro-cli` (Claude models) with `kilo run` (deepseek-v4-flash). Archive the kiro-cli methods for future use — do not delete.

## Scope (2 files + 1 config)

### 1. `scripts/llm_call.py` — the general LLM wrapper
- **Current:** `KIRO_CLI = "kiro-cli"`, calls `kiro-cli chat --no-interactive --model <claude>`
- **Change:** Add a new `call_kilo()` function that uses `kilo run --model kilo/deepseek/deepseek-v4-flash --format json` and parses the JSON event stream to extract the text response.
- **Archive:** Rename `call_kiro()` → `call_kiro_archived()`, keep the function body intact (unused). Add a comment `# ARCHIVED: kiro-cli method, not called. Re-enable by switching llm_call() to use call_kiro_archived().`
- **Wire:** Update `llm_call()` to call `call_kilo()` instead of `call_kiro()`.
- **Config:** `configs/llm_models.yaml` — change all profile models to `kilo/deepseek/deepseek-v4-flash` (keep profile names + creative authority rules; only the `model:` field changes).

### 2. `scripts/research.py` — research synthesis
- **Current:** `KIRO = "kiro-cli"`, `model="claude-sonnet-4.6"`, calls `kiro-cli chat --model claude-sonnet-4.6`
- **Change:** Add a `call_kilo_synthesis()` function that uses `kilo run --model kilo/deepseek/deepseek-v4-flash --format json`.
- **Archive:** Keep the existing `kiro-cli` subprocess call block as a commented-out archive block with a clear `# ARCHIVED:` marker.
- **Wire:** Update `research()` to call `call_kilo_synthesis()` instead of the kiro-cli subprocess.
- **Default model:** Change `model` default from `"claude-sonnet-4.6"` to `"kilo/deepseek/deepseek-v4-flash"`.

## kilo CLI integration details

The `kilo run` command outputs NDJSON events. The relevant event for extracting the response text is:
```json
{"type":"text","part":{"text":"the model response here"}}
```
Multiple `text` events may arrive (streaming chunks). Concatenate all `text` parts for the full response.

Command format:
```bash
echo "<prompt>" | kilo run --model kilo/deepseek/deepseek-v4-flash --format json
```

Key differences from kiro-cli:
- kilo reads prompt from positional args or stdin (not a trailing arg)
- kilo outputs JSON events on stdout (not plain text)
- No `--trust-tools` flag needed (research synthesis is tool-less)
- No `--no-interactive` flag (kilo run is non-interactive by default)

## Test plan
1. Unit test: `call_kilo()` with a simple prompt returns extracted text (mock subprocess or real call)
2. Unit test: `call_kilo()` handles multiple text chunks (concatenation)
3. Unit test: `call_kilo()` raises on timeout / non-zero exit
4. Integration: run a real research call with `python3 scripts/research.py "test topic" --timeout 60`
5. Full suite: `YT_TEST_MODE=1 python3 -m pytest -q` (should remain green — tests mock the subprocess)

## Out of scope
- No changes to `write_script.py`, `direct_storyboard.py`, `repair_storyboard_beats.py`, `run_episode.py` callers (they call `llm_call()` which auto-routes to kilo)
- No changes to `produce_db.py` (calls `research()` which auto-routes to kilo)
- No changes to paid adapters (Higgsfield/ElevenLabs are separate from LLM calls)

## Verification
- `grep -rn "kiro-cli\|KIRO_CLI\|KIRO =" scripts/*.py` shows only archived/commented references
- `grep -rn "kilo run" scripts/*.py` shows the new active call sites
- `python3 scripts/research.py "deep work" --timeout 60` returns a parsed brief
- Full test suite green

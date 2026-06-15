#!/usr/bin/env python3
"""llm_call.py — Thin subprocess wrapper around kiro-cli for programmatic LLM calls.

Calls kiro-cli as a subprocess, extracts the model response, validates JSON output,
and enforces model-routing/creative-authority policy from configs/llm_models.yaml.

Usage:
  python3 scripts/llm_call.py --task script_review --prompt "Review this script..." --output-json out.json
  python3 scripts/llm_call.py --task json_normalization --model-profile auto_utility --prompt "Normalize..."
  python3 scripts/llm_call.py --task storyboard_review --prompt-file prompts/review.md --input-json sb.json
  python3 scripts/llm_call.py --dry-run --task hook_generation --prompt "Generate hooks for..."

No API tokens stored or printed. Uses existing kiro-cli session auth.
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIGS = ROOT / "configs" / "llm_models.yaml"
KIRO_CLI = "kiro-cli"


def load_config():
    """Load model routing config. Requires PyYAML."""
    import yaml
    if not CONFIGS.exists():
        raise FileNotFoundError(f"Config not found: {CONFIGS}")
    return yaml.safe_load(CONFIGS.read_text())


def resolve_profile(config, task, profile_name=None):
    """Resolve which model profile to use; enforce creative authority."""
    profiles = config["profiles"]
    ca_tasks = config.get("creative_authority_tasks", [])

    # Default profile selection
    if not profile_name:
        if task in ca_tasks:
            profile_name = config["default_creative"]
        else:
            profile_name = config["default_utility"]

    if profile_name not in profiles:
        raise ValueError(f"Unknown profile: {profile_name!r}. Available: {list(profiles)}")

    profile = profiles[profile_name]

    # Enforce creative authority
    if task in ca_tasks and not profile.get("is_final_creative_authority"):
        raise RuntimeError(
            f"BLOCKED: task {task!r} requires a creative-authority model; "
            f"{profile_name!r} is not permitted for this task. "
            f"Use '{config['default_creative']}' instead.")

    return profile_name, profile


def extract_response(stdout):
    """Extract LLM response from kiro-cli output (after ANSI stripping)."""
    clean = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\[[^m]*m|\x1b\[\?[0-9]+[lh]', '', stdout)
    lines = []
    capture = False
    for line in clean.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("> "):
            lines.append(stripped[2:])
            capture = True
        elif capture and stripped:
            # continuation lines after the first > line
            lines.append(stripped)
        elif capture and not stripped:
            lines.append("")
    return "\n".join(lines).strip() if lines else None


def parse_json_response(text):
    """Parse JSON from response, stripping markdown fences if present."""
    if not text:
        return None
    # Strip ```json ... ``` fences (closing fence optional — may be truncated)
    m = re.search(r'```(?:json)?\s*\n?(.*?)(?:\n?\s*```|$)', text, re.DOTALL)
    if m and m.group(1).strip():
        text = m.group(1)
    # Also strip a bare leading 'json' line (kiro-cli sometimes prefixes this)
    text = re.sub(r'^\s*json\s*\n', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find a JSON array first, then an object
    for pattern in (r'\[.*\]', r'\{.*\}'):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                obj = json.loads(m.group())
                # Reject fragments: empty arrays, nested sub-objects without expected keys
                if isinstance(obj, list) and len(obj) == 0:
                    continue
                if isinstance(obj, dict) and not any(k in obj for k in ('status', 'persona', 'beat_id', 'beats', 'task', 'angle', 'key_claims')):
                    continue
                return obj
            except json.JSONDecodeError:
                continue
    # Last resort: repair truncated JSON (LLM hit token limit mid-output).
    # Cut at the last complete array/object boundary to salvage critical fields.
    start = text.find('{')
    if start >= 0:
        blob = text[start:]
        # Strategy: find last '], ' or '},' and close the object
        for marker in ('],', '},'):
            idx = blob.rfind(marker)
            if idx > len(blob) // 3:
                candidate = blob[:idx + len(marker) - 1]  # include the ] or } but not comma
                for closer in ('}', ']}', ''):
                    try:
                        obj = json.loads(candidate + closer)
                        if isinstance(obj, dict) and obj:
                            return obj
                    except json.JSONDecodeError:
                        continue
    return None


def validate_output(data):
    """Validate structured LLM output.

    Both JSON objects and JSON arrays are valid parsed responses. Arrays are used
    by callers that expect a list (e.g. a storyboard beat list or a list of reviewer
    verdicts), so a successfully parsed list must NOT be flagged. The reviewer-style
    field checks (status/may_proceed) only apply to dict responses. Anything that is
    neither a dict nor a list (e.g. a bare string/number that slipped through parsing)
    is invalid.
    """
    if isinstance(data, list):
        return []
    if not isinstance(data, dict):
        return ["response is not a JSON object or array"]
    errors = []
    if "status" in data and data["status"] not in ("pass", "fail", "blocked"):
        errors.append(f"status must be pass/fail/blocked, got: {data['status']!r}")
    if "may_proceed" in data and not isinstance(data["may_proceed"], bool):
        errors.append(f"may_proceed must be bool, got: {type(data['may_proceed']).__name__}")
    return errors


def call_kiro(model, prompt, timeout=120, verbose=False):
    """Run kiro-cli subprocess and return raw stdout.

    Hardening (2026-06-12): the default agent (ytbuilder) runs spawn/stop hooks on
    every chat invocation, which adds latency and can stall a non-interactive call.
    We trust NO tools (--trust-tools=) so the model cannot trigger tool/hook
    execution. Prompt is piped via stdin to avoid OS arg-length limits on large prompts.
    A timeout raises a clear error instead of hanging.
    """
    cmd = [KIRO_CLI, "chat", "--no-interactive", "--model", model,
           "--wrap", "never", "--trust-tools=", "--agent", "pipeline"]
    if verbose:
        print(f"  cmd: {KIRO_CLI} chat --no-interactive --model {model} --trust-tools= "
              f"[stdin: {len(prompt)} chars]", file=sys.stderr)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           input=prompt)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"kiro-cli did not respond within {timeout}s (model {model}). "
            "Check `kiro-cli chat --list-models` and that your session is authenticated.")
    elapsed = time.time() - t0
    if verbose:
        print(f"  elapsed: {elapsed:.1f}s, exit: {r.returncode}", file=sys.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"kiro-cli exited {r.returncode}: {r.stderr[:200]}")
    return r.stdout


def llm_call(task, prompt, model_profile=None, input_json=None, timeout=120,
             dry_run=False, verbose=False, expect_json=True):
    """High-level: resolve profile, build prompt, call, parse, validate.

    Returns (parsed_data, raw_text, profile_name, model).
    """
    config = load_config()
    profile_name, profile = resolve_profile(config, task, model_profile)
    model = profile["model"]

    # Append input JSON if provided
    full_prompt = prompt
    if input_json:
        if isinstance(input_json, (dict, list)):
            input_json = json.dumps(input_json, indent=2)
        full_prompt = f"{prompt}\n\nINPUT:\n```json\n{input_json}\n```"

    if dry_run:
        print(f"DRY RUN — would call kiro-cli")
        print(f"  task:    {task}")
        print(f"  profile: {profile_name} → model {model}")
        print(f"  prompt:  {full_prompt[:200]}...")
        print(f"  timeout: {timeout}s")
        return None, None, profile_name, model

    raw = call_kiro(model, full_prompt, timeout=timeout, verbose=verbose)
    text = extract_response(raw)

    if not text:
        raise RuntimeError("No response extracted from kiro-cli output")

    if not expect_json:
        return text, text, profile_name, model

    data = parse_json_response(text)
    if data is None:
        raise RuntimeError(f"Failed to parse JSON from response:\n{text[:500]}")

    errors = validate_output(data)
    if errors:
        print(f"  WARN: output validation issues: {errors}", file=sys.stderr)

    return data, text, profile_name, model


def main():
    ap = argparse.ArgumentParser(description="Programmatic LLM calls via kiro-cli.")
    ap.add_argument("--task", required=True, help="Task name (for routing/authority)")
    ap.add_argument("--prompt", default=None, help="Prompt text (inline)")
    ap.add_argument("--prompt-file", default=None, help="Prompt from file")
    ap.add_argument("--input-json", default=None, help="JSON input file to append to prompt")
    ap.add_argument("--output-json", "-o", default=None, help="Write parsed JSON output to file")
    ap.add_argument("--model-profile", default=None, help="Override model profile")
    ap.add_argument("--timeout", type=int, default=120, help="Subprocess timeout (seconds)")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without calling kiro-cli")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-json", action="store_true", help="Don't expect JSON response (return raw text)")
    args = ap.parse_args()

    # Build prompt
    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        pf = Path(args.prompt_file)
        if not pf.exists():
            print(f"ERROR: prompt file not found: {pf}", file=sys.stderr)
            sys.exit(1)
        prompt = pf.read_text()
    else:
        ap.error("--prompt or --prompt-file required")

    # Input JSON
    input_data = None
    if args.input_json:
        input_data = Path(args.input_json).read_text()

    try:
        data, text, profile_name, model = llm_call(
            task=args.task, prompt=prompt, model_profile=args.model_profile,
            input_json=input_data, timeout=args.timeout,
            dry_run=args.dry_run, verbose=args.verbose,
            expect_json=not args.no_json)
    except (RuntimeError, ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        return

    if args.output_json and data:
        Path(args.output_json).write_text(json.dumps(data, indent=2))
        print(f"  output: {args.output_json}", file=sys.stderr)

    # stdout = the result
    if data:
        print(json.dumps(data, indent=2))
    else:
        print(text)


if __name__ == "__main__":
    main()

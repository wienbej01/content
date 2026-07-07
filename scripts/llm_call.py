#!/usr/bin/env python3
"""llm_call.py — Thin subprocess wrapper around kilo for programmatic LLM calls.

Calls kilo as a subprocess (model: deepseek-v4-flash), extracts the model response,
validates JSON output, and enforces model-routing/creative-authority policy from
configs/llm_models.yaml.

Usage:
  python3 scripts/llm_call.py --task script_review --prompt "Review this script..." --output-json out.json
  python3 scripts/llm_call.py --task json_normalization --model-profile auto_utility --prompt "Normalize..."
  python3 scripts/llm_call.py --task storyboard_review --prompt-file prompts/review.md --input-json sb.json
  python3 scripts/llm_call.py --dry-run --task hook_generation --prompt "Generate hooks for..."

No API tokens stored or printed. Uses existing kilo session auth.
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
KILO_CLI = "kilo"
KILO_MODEL = "kilo/deepseek/deepseek-v4-flash"

# System prompt enforcing strict JSON-only output from the model.
# Prepended as "SYSTEM:\n...\n\nUSER:\n..." so deepseek treats it as a system instruction.
# Applied automatically to all expect_json=True calls in the pipeline.
PIPELINE_SYSTEM_PROMPT = """You are a JSON-only API for the production pipeline.

ABSOLUTE OUTPUT RULE: Your entire response MUST be valid JSON and nothing else.
- No prose. No markdown. No bullet points. No preamble. No explanation.
- Do NOT write sentences like "Here is the result" or "I have analyzed...".
- Do NOT use ```json fences. Output raw JSON directly.
- The ONLY acceptable response format is a JSON object or array.
- If you cannot produce valid JSON, output exactly: ERROR

Any response that is not raw JSON or the string ERROR is a critical failure."""


class AvailabilityResult:
    """Backward-compatible Sonnet availability result with diagnostics."""

    def __init__(self, available, models, error=None):
        self.available = available
        self.models = models
        self.error = error

    def __iter__(self):
        yield self.available
        yield self.models


def load_config():
    """Load model routing config. Requires PyYAML."""
    import yaml
    if not CONFIGS.exists():
        raise FileNotFoundError(f"Config not found: {CONFIGS}")
    return yaml.safe_load(CONFIGS.read_text())


def check_sonnet5_availability(model_id="claude-sonnet-5", dry_run=False):
    """Check if Sonnet 5 is available via kilo models.

    In dry-run mode, skips subprocess call and returns True (assume available
    for static verification). Returns an iterable result compatible with
    `(available, model_list)` unpacking and carrying `.error` diagnostics.
    """
    if dry_run:
        return AvailabilityResult(True, [])

    try:
        r = subprocess.run([KILO_CLI, "models"], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return AvailabilityResult(False, [], "kilo models timed out after 30s")
    except FileNotFoundError:
        return AvailabilityResult(False, [], "kilo executable not found on PATH")

    if r.returncode != 0:
        detail = (r.stderr or r.stdout or "").strip()
        if detail:
            detail = detail[:500]
        else:
            detail = f"kilo models exited {r.returncode} without stderr"
        return AvailabilityResult(False, [], detail)

    models = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    matching = [m for m in models if model_id in m]
    if not matching:
        return AvailabilityResult(False, models, f"{model_id} not listed by kilo models")
    return AvailabilityResult(True, models)


def resolve_profile(config, task, profile_name=None):
    """Resolve which model profile to use; enforce creative + storyboard authority."""
    profiles = config["profiles"]
    ca_tasks = config.get("creative_authority_tasks", [])
    sa_tasks = config.get("storyboard_authority_tasks", [])

    # Default profile selection
    if not profile_name:
        if task in sa_tasks:
            profile_name = "storyboard_director_sonnet5"
        elif task in ca_tasks:
            profile_name = config["default_creative"]
        else:
            profile_name = config["default_utility"]

    if profile_name not in profiles:
        raise ValueError(f"Unknown profile: {profile_name!r}. Available: {list(profiles)}")

    profile = profiles[profile_name]

    # Enforce storyboard authority: only storyboard_director_sonnet5 allowed
    if task in sa_tasks and profile_name != "storyboard_director_sonnet5":
        raise RuntimeError(
            f"BLOCKED_CREATIVE_FALLBACK_FORBIDDEN: task {task!r} requires Sonnet 5 "
            f"through Kilo (profile 'storyboard_director_sonnet5'). "
            f"Profile {profile_name!r} is not permitted for runtime storyboard authoring. "
            f"No fallback to another model is allowed.")

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


def extract_kilo_response(stdout):
    """Extract LLM response from kilo JSON event stream.

    kilo run --format json outputs NDJSON events. The relevant event for extracting
    the response text is: {"type":"text","part":{"text":"the model response here"}}.
    Multiple text events may arrive (streaming chunks). Concatenate all text parts.
    """
    parts = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("type") == "text":
                text = event.get("part", {}).get("text", "")
                if text:
                    parts.append(text)
        except json.JSONDecodeError:
            continue
    return "".join(parts).strip() if parts else None


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


# ARCHIVED: kiro-cli method, not called. Re-enable by switching llm_call() to use call_kiro_archived().
def call_kiro_archived(model, prompt, timeout=120, verbose=False):
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


def call_kilo_vision(model, prompt, image_paths, timeout=120, verbose=False, system_prompt=None):
    """Run kilo subprocess with image attachments and return raw stdout (NDJSON).

    Uses `kilo run --model <model> --format json -f <image> ...` with prompt
    piped via stdin. Image files are attached via the -f flag so vision-capable
    models can inspect them.
    """
    if system_prompt:
        full_prompt = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{prompt}"
    else:
        full_prompt = prompt

    cmd = [KILO_CLI, "run", "--model", model, "--format", "json"]
    for img in image_paths:
        cmd.extend(["-f", str(img)])
    cmd.append("--")
    cmd.append(full_prompt)

    if verbose:
        print(f"  cmd: {' '.join(c for c in cmd if c != full_prompt)} "
              f"[prompt: {len(full_prompt)} chars]", file=sys.stderr)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"kilo vision call did not respond within {timeout}s (model {model}).")
    elapsed = time.time() - t0
    if verbose:
        print(f"  elapsed: {elapsed:.1f}s, exit: {r.returncode}", file=sys.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"kilo vision call exited {r.returncode}: {r.stderr[:200]}")
    return r.stdout


def call_kilo(model, prompt, timeout=120, verbose=False, system_prompt=None):
    """Run kilo subprocess and return raw stdout (NDJSON event stream).

    Uses `kilo run --model <model> --format json` with prompt piped via stdin.
    kilo outputs NDJSON events on stdout. The caller (llm_call) uses
    extract_kilo_response() to parse the text events.

    If system_prompt is provided, it is prepended as "SYSTEM:\n...\n\nUSER:\n..."
    so deepseek treats it as a system-level instruction.
    """
    if system_prompt:
        full_prompt = f"SYSTEM:\n{system_prompt}\n\nUSER:\n{prompt}"
    else:
        full_prompt = prompt

    cmd = [KILO_CLI, "run", "--model", model, "--format", "json"]
    if verbose:
        print(f"  cmd: {KILO_CLI} run --model {model} --format json "
              f"[stdin: {len(full_prompt)} chars]", file=sys.stderr)
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           input=full_prompt)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"kilo did not respond within {timeout}s (model {model}). "
            "Check `kilo models` and that your session is authenticated.")
    elapsed = time.time() - t0
    if verbose:
        print(f"  elapsed: {elapsed:.1f}s, exit: {r.returncode}", file=sys.stderr)
    if r.returncode != 0:
        raise RuntimeError(f"kilo exited {r.returncode}: {r.stderr[:200]}")
    return r.stdout


def llm_call(task, prompt, model_profile=None, input_json=None, timeout=120,
             dry_run=False, verbose=False, expect_json=True, persona_model=None):
    """High-level: resolve profile, build prompt, call, parse, validate.

    Returns (parsed_data, raw_text, profile_name, model).
    """
    config = load_config()
    # TKT-701: use persona_model as model_profile override when provided
    effective_profile = persona_model if persona_model else model_profile
    profile_name, profile = resolve_profile(config, task, effective_profile)
    model = profile["model"]

    # Check Sonnet 5 availability for storyboard authority tasks
    if profile_name == "storyboard_director_sonnet5":
        availability = check_sonnet5_availability(dry_run=dry_run)
        available, _ = availability
        if not available:
            reason = getattr(availability, "error", None)
            detail = f" Detail: {reason}" if reason else ""
            raise RuntimeError(
                "BLOCKED_SONNET5_UNAVAILABLE: Sonnet 5 (claude-sonnet-5) "
                "is not available through Kilo. Storyboard authoring cannot proceed "
                f"without Sonnet 5. No fallback is permitted.{detail}")

    # Append input JSON if provided
    full_prompt = prompt
    if input_json:
        if isinstance(input_json, (dict, list)):
            input_json = json.dumps(input_json, indent=2)
        full_prompt = f"{prompt}\n\nINPUT:\n```json\n{input_json}\n```"

    if dry_run:
        print(f"DRY RUN — would call kilo")
        print(f"  task:    {task}")
        print(f"  profile: {profile_name} → model {model}")
        print(f"  prompt:  {full_prompt[:200]}...")
        print(f"  timeout: {timeout}s")
        return None, None, profile_name, model

    # Apply system prompt for JSON enforcement when expect_json=True
    system_prompt = PIPELINE_SYSTEM_PROMPT if expect_json else None
    raw = call_kilo(model, full_prompt, timeout=timeout, verbose=verbose,
                    system_prompt=system_prompt)
    text = extract_kilo_response(raw)

    if not text:
        raise RuntimeError("No response extracted from kilo output")

    if not expect_json:
        return text, text, profile_name, model

    data = parse_json_response(text)
    if data is None:
        raise RuntimeError(f"Failed to parse JSON from response:\n{text[:500]}")

    errors = validate_output(data)
    if errors:
        print(f"  WARN: output validation issues: {errors}", file=sys.stderr)

    return data, text, profile_name, model


def llm_vision_call(task, prompt, image_paths, model_profile="vision_qa", timeout=120,
                    dry_run=False, verbose=False):
    """High-level vision call: resolve profile, attach images, call, parse, validate.

    Args:
        task: Task name for routing (e.g. 'semantic_role_qa').
        prompt: Text prompt describing what to analyze in the images.
        image_paths: List of Path or str to image files to attach.
        model_profile: Profile name (default 'vision_qa').
        timeout: Subprocess timeout in seconds.
        dry_run: Print plan without calling kilo.
        verbose: Print diagnostic info to stderr.

    Returns:
        (parsed_data, raw_text, profile_name, model)
    """
    config = load_config()
    profile_name, profile = resolve_profile(config, task, model_profile)

    if not profile.get("supports_vision"):
        raise RuntimeError(
            f"BLOCKED_VISION_PROFILE: profile {profile_name!r} does not declare "
            f"supports_vision: true. Use a vision-capable profile.")

    model = profile["model"]

    # Validate all image paths exist
    for img in image_paths:
        p = Path(img)
        if not p.exists():
            raise RuntimeError(
                f"BLOCKED_VISION_IMAGE_MISSING: image file not found: {p}")

    if dry_run:
        print(f"DRY RUN — would call kilo vision")
        print(f"  task:        {task}")
        print(f"  profile:     {profile_name} -> model {model}")
        print(f"  images:      {len(image_paths)} file(s)")
        print(f"  prompt:      {prompt[:200]}...")
        print(f"  timeout:     {timeout}s")
        return None, None, profile_name, model

    system_prompt = PIPELINE_SYSTEM_PROMPT
    raw = call_kilo_vision(model, prompt, image_paths, timeout=timeout,
                           verbose=verbose, system_prompt=system_prompt)
    text = extract_kilo_response(raw)

    if not text:
        raise RuntimeError("No response extracted from kilo vision output")

    data = parse_json_response(text)
    if data is None:
        raise RuntimeError(f"Failed to parse JSON from vision response:\n{text[:500]}")

    return data, text, profile_name, model


def main():
    ap = argparse.ArgumentParser(description="Programmatic LLM calls via kilo.")
    ap.add_argument("--task", default=None, help="Task name (for routing/authority)")
    ap.add_argument("--prompt", default=None, help="Prompt text (inline)")
    ap.add_argument("--prompt-file", default=None, help="Prompt from file")
    ap.add_argument("--input-json", default=None, help="JSON input file to append to prompt")
    ap.add_argument("--output-json", "-o", default=None, help="Write parsed JSON output to file")
    ap.add_argument("--model-profile", default=None, help="Override model profile")
    ap.add_argument("--timeout", type=int, default=120, help="Subprocess timeout (seconds)")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without calling kilo")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no-json", action="store_true", help="Don't expect JSON response (return raw text)")
    ap.add_argument("--check-availability", action="store_true", help="Check Sonnet 5 availability via kilo models")
    args = ap.parse_args()

    if args.check_availability:
        availability = check_sonnet5_availability(dry_run=args.dry_run)
        available, models = availability
        if available:
            print("SONNET5_AVAILABLE: claude-sonnet-5 found in kilo models")
            sys.exit(0)
        else:
            reason = getattr(availability, "error", None)
            print("BLOCKED_SONNET5_UNAVAILABLE: claude-sonnet-5 not found in kilo models",
                  file=sys.stderr)
            if reason:
                print(f"DETAIL: {reason}", file=sys.stderr)
            sys.exit(1)

    if not args.task:
        ap.error("--task is required")

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

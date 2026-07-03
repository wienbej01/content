#!/usr/bin/env python3
"""sonnet_storyboard_wrapper.py — Sonnet 5 storyboard wrapper.

Assembles the approved script context packet, invokes Sonnet 5 via Kilo using the
storyboard_director_sonnet5 profile, parses the canonical storyboard JSON, and
records authoring metadata. Python does not create creative choices — it only
builds the context, invokes the LLM, validates the contract, and stores metadata.

Usage:
  python3 scripts/sonnet_storyboard_wrapper.py --script <approved_script.json> \
        --source <research.txt> --output <storyboard_output.json> [--dry-run]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
CU = ROOT / "docs" / "channel_universe"
PROMPTS_DIR = ROOT / "docs" / "prompts"
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "storyboard_v2"
SCHEMA_PATH = ROOT / "schemas" / "storyboard_v2.schema.json"

from llm_call import llm_call as _llm_call

BIBLE_FILES = [
    "UNIVERSE_BIBLE.md",
    "JAMES_CHARACTER_BIBLE.md",
    "JAMES_RECORDING_STUDIO_LIBRARY.md",
    "FORBIDDEN_PATTERNS.md",
]

REQUIRED_SONNET5_PROFILE = "storyboard_director_sonnet5"

CREATIVE_FALLBACK_BLOCKED = "BLOCKED_CREATIVE_FALLBACK_FORBIDDEN"
NON_SONNET_BLOCKED = "BLOCKED_NON_SONNET_AUTHOR"
EMPTY_RESPONSE_BLOCKED = "BLOCKED_EMPTY_STORYBOARD_RESPONSE"
UNPARSEABLE_BLOCKED = "BLOCKED_UNPARSEABLE_STORYBOARD_JSON"
NARRATION_MUTATION_BLOCKED = "BLOCKED_SCRIPT_NARRATION_MUTATION"


def _read(p):
    p = Path(p)
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _load_script(script_input):
    if isinstance(script_input, dict):
        return script_input
    p = Path(script_input)
    if not p.exists():
        raise FileNotFoundError(f"Script file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _compute_script_sha256(script_data):
    canonical = json.dumps(script_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_bibles():
    out = []
    for name in BIBLE_FILES:
        txt = _read(CU / name)
        if not txt:
            continue
        out.append(f"===== {name} =====\n{txt}")
    return "\n\n".join(out)


def load_prompt_template():
    path = PROMPTS_DIR / "STORYBOARD_SONNET5_DIRECTOR.md"
    if not path.exists():
        raise FileNotFoundError(f"Director prompt template not found: {path}")
    return _read(path)


def load_schema_text():
    if SCHEMA_PATH.exists():
        return _read(SCHEMA_PATH)
    return "{}"


def load_source_text(source_path):
    if not source_path:
        return ""
    p = Path(source_path)
    return _read(p)


def assemble_context_packet(script_data, source_text=None, bibles_text=None):
    context = {
        "approved_script_json": json.dumps(script_data, indent=2, ensure_ascii=False),
        "approved_script_sha256": _compute_script_sha256(script_data),
        "approved_script_revision_id": script_data.get("approved_script_revision_id", ""),
        "project_id": script_data.get("project_id", ""),
        "title": script_data.get("title", ""),
        "segments": script_data.get("segments", []),
        "source_research_text": source_text or "",
        "bible_texts": bibles_text or load_bibles(),
        "reference_manifest_text": "",
        "canonical_schema_json": load_schema_text(),
    }
    return context


def build_sonnet5_storyboard_prompt(context_packet):
    template = load_prompt_template()

    idx = template.find("=== APPROVED SCRIPT ===")
    if idx == -1:
        raise RuntimeError(
            "Prompt template missing '=== APPROVED SCRIPT ===' marker. "
            "The template must contain the section '## INPUT DATA' followed by "
            "=== APPROVED SCRIPT === marker.")
    prompt_prefix = template[:idx].rstrip()

    approved_script_json = context_packet.get("approved_script_json", "{}")
    source_text = context_packet.get("source_research_text", "")
    bible_texts = context_packet.get("bible_texts", "")
    reference_manifest = context_packet.get("reference_manifest_text", "")
    schema_json = context_packet.get("canonical_schema_json", "{}")

    prompt = f"""{prompt_prefix}

=== APPROVED SCRIPT ===
{approved_script_json}

=== SOURCE RESEARCH ===
{source_text}

=== BIBLES ===
{bible_texts}

=== REFERENCE ASSET MANIFEST ===
{reference_manifest}

=== SCHEMA (for reference) ===
{schema_json}

Generate the complete storyboard JSON now. Remember: RAW JSON ONLY. No fences. No prose."""
    return prompt


def validate_sonnet_authoring(data, profile_name, model):
    errors = []

    if profile_name != REQUIRED_SONNET5_PROFILE:
        errors.append({
            "severity": "BLOCKER",
            "code": NON_SONNET_BLOCKED,
            "message": (
                f"Storyboard was authored with profile '{profile_name}', "
                f"not '{REQUIRED_SONNET5_PROFILE}'. "
                "Runtime storyboard authorship requires Sonnet 5 through Kilo."
            ),
        })

    if not isinstance(data, dict):
        errors.append({
            "severity": "BLOCKER",
            "code": NON_SONNET_BLOCKED,
            "message": (
                f"Storyboard response is not a JSON object (got {type(data).__name__}). "
                "Canonical storyboard must be a JSON object with authoring metadata."
            ),
        })
        return errors

    authoring_profile = (data.get("authoring_model_profile") or "").lower()
    authoring_model = (data.get("authoring_model") or "").lower()
    is_sonnet = "sonnet" in authoring_profile or "claude-sonnet" in authoring_model
    if not is_sonnet:
        errors.append({
            "severity": "BLOCKER",
            "code": NON_SONNET_BLOCKED,
            "message": (
                f"authoring_model_profile='{data.get('authoring_model_profile')}' and "
                f"authoring_model='{data.get('authoring_model')}' do not reference Sonnet 5."
            ),
        })

    return errors


def detect_narration_mutation(script_data, storyboard_data):
    """Check that narration text in storyboard matches approved script segments.

    Returns list of mutation errors. Only applies when storyboard has
    segment_work_orders with narration_text_exact fields.
    """
    mutations = []
    if not isinstance(storyboard_data, dict):
        return mutations

    approved_segments = {
        s["id"]: s.get("text", "")
        for s in script_data.get("segments", [])
        if "id" in s
    }
    if not approved_segments:
        return mutations

    work_orders = storyboard_data.get("segment_work_orders", [])
    for wo in work_orders:
        seg_id = wo.get("segment_id", "")
        actual = wo.get("narration_text_exact", "")
        expected = approved_segments.get(seg_id)
        if expected is None:
            continue
        if actual != expected:
            mutations.append({
                "severity": "BLOCKER",
                "code": NARRATION_MUTATION_BLOCKED,
                "segment_id": seg_id,
                "expected": expected,
                "actual": actual,
                "message": (
                    f"Narration mutation in segment_work_order {seg_id}: "
                    f"expected '{expected[:80]}...', got '{actual[:80]}...'"
                ),
            })
    return mutations


def generate_canonical_storyboard(script_input, source_path=None, dry_run=False,
                                  verbose=False, timeout=300):
    script_data = _load_script(script_input)
    source_text = load_source_text(source_path) if source_path else ""
    bibles_text = load_bibles()
    context = assemble_context_packet(script_data, source_text, bibles_text)
    prompt = build_sonnet5_storyboard_prompt(context)

    authoring_metadata = {
        "profile": REQUIRED_SONNET5_PROFILE,
        "script_sha256": context["approved_script_sha256"],
        "prompt_chars": len(prompt),
        "bibles_chars": len(context["bible_texts"]),
        "source_chars": len(context["source_research_text"]),
    }

    if dry_run:
        return _dry_run_result(prompt, authoring_metadata)

    try:
        data, raw_text, profile_name, model = _llm_call(
            task="storyboard_generation",
            prompt=prompt,
            model_profile=REQUIRED_SONNET5_PROFILE,
            timeout=timeout,
            verbose=verbose,
            expect_json=True,
        )
    except RuntimeError as e:
        msg = str(e)
        if "BLOCKED_SONNET5_UNAVAILABLE" in msg:
            return {
                "status": "BLOCKED",
                "error_code": "BLOCKED_SONNET5_UNAVAILABLE",
                "error": msg,
                "authoring_metadata": authoring_metadata,
            }
        raise

    if data is None:
        return {
            "status": "BLOCKED",
            "error_code": EMPTY_RESPONSE_BLOCKED,
            "error": "Sonnet 5 returned no data. Storyboard generation cannot proceed.",
            "authoring_metadata": authoring_metadata,
        }

    authoring_metadata["model"] = model
    authoring_metadata["profile_used"] = profile_name
    authoring_metadata["raw_response_chars"] = len(raw_text) if raw_text else 0

    authoring_errors = validate_sonnet_authoring(data, profile_name, model)
    narration_errors = detect_narration_mutation(script_data, data)

    if isinstance(data, dict):
        data["_authoring_metadata"] = authoring_metadata

    return {
        "status": "BLOCKED" if (authoring_errors or narration_errors) else "SUCCESS",
        "storyboard": data,
        "authoring_metadata": authoring_metadata,
        "authoring_errors": authoring_errors,
        "narration_mutations": narration_errors,
    }


def _dry_run_result(prompt, authoring_metadata):
    return {
        "status": "DRY_RUN",
        "storyboard": None,
        "authoring_metadata": authoring_metadata,
        "authoring_errors": [],
        "narration_mutations": [],
        "dry_run": {
            "prompt_chars": authoring_metadata["prompt_chars"],
            "model_profile": authoring_metadata["profile"],
            "script_sha256": authoring_metadata["script_sha256"],
            "prompt_preview": prompt[:500],
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Sonnet 5 storyboard wrapper — canonical SSOT storyboard generation.")
    ap.add_argument("--script", required=True,
                    help="Approved script JSON file path.")
    ap.add_argument("--source", default=None,
                    help="Source research text file.")
    ap.add_argument("--output", "-o", default=None,
                    help="Write storyboard JSON output to file.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan without calling Kilo/Sonnet 5.")
    ap.add_argument("--verbose", action="store_true",
                    help="Verbose subprocess output.")
    ap.add_argument("--timeout", type=int, default=300,
                    help="Kilo subprocess timeout (seconds).")
    args = ap.parse_args(argv)

    result = generate_canonical_storyboard(
        script_input=args.script,
        source_path=args.source,
        dry_run=args.dry_run,
        verbose=args.verbose,
        timeout=args.timeout,
    )

    if args.dry_run:
        meta = result["authoring_metadata"]
        dry = result["dry_run"]
        print(f"  DRY RUN — profile {meta['profile']}")
        print(f"    prompt: {dry['prompt_chars']} chars")
        print(f"    bibles: {meta['bibles_chars']} chars")
        print(f"    source: {meta['source_chars']} chars")
        print(f"    script_sha256: {meta['script_sha256']}")
        print(f"    prompt preview: {dry['prompt_preview'][:200]}...")
        return 0

    status = result["status"]
    print(f"  Sonnet 5 storyboard wrapper: {status}")

    if status == "BLOCKED":
        for err in result.get("authoring_errors", []):
            print(f"    BLOCKED: {err.get('code', 'UNKNOWN')} — {err.get('message', '')}")
        for err in result.get("narration_mutations", []):
            print(f"    BLOCKED: {err.get('code', 'UNKNOWN')} — {err.get('message', '')}")
        if result.get("error_code"):
            print(f"    BLOCKED: {result['error_code']} — {result.get('error', '')}")
    else:
        meta = result["authoring_metadata"]
        sb = result["storyboard"]
        if sb:
            n_shots = len(sb.get("shots", []))
            n_beats = len(sb.get("narrative_beats", []))
            print(f"    model: {meta.get('model', '?')}")
            print(f"    shots: {n_shots}, beats: {n_beats}")
            print(f"    prompt: {meta['prompt_chars']} chars")

    if args.output and status != "BLOCKED":
        Path(args.output).write_text(
            json.dumps(result["storyboard"], indent=2, ensure_ascii=False))
        print(f"  wrote {args.output}")

    return 0 if status != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Production safety interlock — blocks release when known-placeholder code is live.

Detects: placeholder lipsync scorer, simulated/stubbed providers, auto-approved
gates, deleted-produce.py imports, master-range padding slicer, publish/analytics
stubs.  Fake/simulated providers are allowed ONLY when YT_TEST_MODE=1 or under
pytest (PYTEST_CURRENT_TEST).

Usage:
  python3 scripts/release_guard.py status   # machine-readable JSON, non-zero when blocked
  python3 scripts/release_guard.py check    # exits 0/1 silently unless --verbose

Also exposes:
  require_production_ready()  — wire into produce_db.run_production before TTS/media.
"""
import ast
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BLOCKER_CODES = {
    "PLACEHOLDER_SCORER": "Lipsync scorer uses fixed-PASS placeholder (0.85/0.90 heuristic)",
    "STUBBED_PROVIDER": "Provider execution writes stubbed content bytes or simulated results",
    "AUTO_APPROVED_GATE": "Human gate returns auto_approved without actual approval request",
    "DELETED_PRODUCE_IMPORT": "Orchestrator imports from deleted produce.py module",
    "PADDING_SLICER": "Master-range padding slicer crosses speech boundaries",
    "STUBBED_PUBLISH": "Publish stage returns stubbed status",
    "STUBBED_ANALYTICS": "Analytics stage returns stubbed status",
    "LEGACY_FILE_AUTHORITY": "Production services still read legacy JSON authority files",
}

PRODUCE_DB = ROOT / "scripts" / "produce_db.py"
LIPSYNC_SCORING = ROOT / "scripts" / "lipsync_scoring.py"
SLICE_CONTINUOUS = ROOT / "scripts" / "slice_continuous_lipsync.py"


def _resolved_paths():
    """Resolve the production modules to scan.

    Defaults to the real production modules, but honors environment overrides so
    the release interlock can be tested deterministically: tests inject fixture
    files (containing a single blocker pattern) and point the override env vars
    at them, then assert each blocker fires. The production path is never
    bypassed — overrides only redirect WHICH file is scanned, not whether the
    scan runs.
    """
    return {
        "produce_db": Path(os.environ.get("RELEASE_GUARD_PRODUCE_DB", PRODUCE_DB)),
        "lipsync": Path(os.environ.get("RELEASE_GUARD_LIPSYNC", LIPSYNC_SCORING)),
        "slice": Path(os.environ.get("RELEASE_GUARD_SLICE", SLICE_CONTINUOUS)),
    }


def _parse_file(filepath: Path):
    try:
        return ast.parse(filepath.read_text(), filename=str(filepath))
    except SyntaxError:
        return None


def _is_constant(node, value):
    return isinstance(node, ast.Constant) and node.value == value


def _dict_has_key_val(dict_node, key, val):
    """Check if an ast.Dict node has a specific key-value pair."""
    for k, v in zip(dict_node.keys, dict_node.values):
        if _is_constant(k, key) and _is_constant(v, val):
            return True
    return False


def _check_placeholder_scorer() -> list[dict]:
    blockers = []
    lipsync = _resolved_paths()["lipsync"]
    tree = _parse_file(lipsync)
    if tree is None:
        blockers.append({
            "code": "PLACEHOLDER_SCORER",
            "detail": "Could not parse lipsync_scoring.py",
            "location": str(lipsync),
        })
        return blockers

    found_score_0_85 = False
    found_confidence_0_90 = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript):
                    if (isinstance(target.value, ast.Name) and target.value.id == "result" and
                        isinstance(target.slice, ast.Constant)):
                        key = target.slice.value
                        if key == "score" and isinstance(node.value, ast.Constant) and node.value.value == 0.85:
                            found_score_0_85 = True
                        if key == "confidence" and isinstance(node.value, ast.Constant) and node.value.value == 0.90:
                            found_confidence_0_90 = True

    if found_score_0_85 and found_confidence_0_90:
        blockers.append({
            "code": "PLACEHOLDER_SCORER",
            "detail": "Lipsync scorer assigns fixed PASS score=0.85, confidence=0.90 — not a real ML model",
            "location": f"{lipsync}:score_lipsync",
        })

    return blockers


def _check_stubbed_provider() -> list[dict]:
    blockers = []
    produce_db = _resolved_paths()["produce_db"]
    tree = _parse_file(produce_db)
    if tree is None:
        return blockers

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "write":
                for arg in node.args:
                    if _is_constant(arg, b"stubbed video content for CI"):
                        blockers.append({
                            "code": "STUBBED_PROVIDER",
                            "detail": "generate_media writes b\"stubbed video content for CI\" — not real provider output",
                            "location": f"{produce_db}:{node.lineno}",
                        })
            if isinstance(func, ast.Attribute) and func.attr == "complete_provider_job":
                pass

    return blockers


def _check_auto_approved_gates() -> list[dict]:
    blockers = []
    produce_db = _resolved_paths()["produce_db"]
    tree = _parse_file(produce_db)
    if tree is None:
        return blockers

    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict):
            if _dict_has_key_val(node.value, "status", "auto_approved"):
                # Check if this is inside a gate function
                for func_node in ast.walk(tree):
                    if (isinstance(func_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                        "gate" in func_node.name):
                        if node in (list(ast.walk(func_node))):
                            blockers.append({
                                "code": "AUTO_APPROVED_GATE",
                                "detail": f"Gate '{func_node.name}' returns auto_approved without actual approval flow",
                                "location": f"{produce_db}:{node.lineno} (function {func_node.name})",
                            })
                            break
    return blockers


def _check_deleted_produce_import() -> list[dict]:
    blockers = []
    produce_db = _resolved_paths()["produce_db"]
    tree = _parse_file(produce_db)
    if tree is None:
        return blockers

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "produce":
                imports = [alias.name for alias in node.names]
                blockers.append({
                    "code": "DELETED_PRODUCE_IMPORT",
                    "detail": f"Orchestrator imports from deleted produce.py: {', '.join(imports)}",
                    "location": f"{produce_db}:{node.lineno}",
                })

    return blockers


def _check_padding_slicer() -> list[dict]:
    blockers = []
    slice_mod = _resolved_paths()["slice"]
    tree = _parse_file(slice_mod)
    if tree is None:
        return blockers

    found_pad_needed = False
    found_speech_start_shift = False
    found_speech_end_shift = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "pad_needed":
                    found_pad_needed = True
                if isinstance(target, ast.Name) and target.id == "slice_start":
                    # Check if it includes leading_silence
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "max":
                        found_speech_start_shift = True
                if isinstance(target, ast.Name) and target.id == "slice_end":
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "min":
                        found_speech_end_shift = True

    if found_pad_needed and found_speech_start_shift:
        blockers.append({
            "code": "PADDING_SLICER",
            "detail": "slice_continuous_lipsync uses pad_needed/silence_padding that widens beyond speech boundaries into adjacent master audio",
            "location": f"{slice_mod}:slice_hero_from_master",
        })

    return blockers


def _check_stubbed_publish_analytics() -> list[dict]:
    blockers = []
    produce_db = _resolved_paths()["produce_db"]
    tree = _parse_file(produce_db)
    if tree is None:
        return blockers

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name == "invoke_publish":
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                        if _dict_has_key_val(child.value, "status", "stubbed"):
                            blockers.append({
                                "code": "STUBBED_PUBLISH",
                                "detail": "invoke_publish returns status: 'stubbed' — not integrated with publishing platform",
                                "location": f"{produce_db}:{child.lineno}",
                            })
            if node.name == "invoke_analytics":
                for child in ast.walk(node):
                    if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                        if _dict_has_key_val(child.value, "status", "stubbed"):
                            blockers.append({
                                "code": "STUBBED_ANALYTICS",
                                "detail": "invoke_analytics returns status: 'stubbed' — not integrated with analytics platform",
                                "location": f"{produce_db}:{child.lineno}",
                            })

    return blockers


def _check_legacy_file_authority() -> list[dict]:
    """Block release when production services still read legacy JSON as authority.

    Delegates to the existing forbidden-file-reads CI gate so the release
    interlock and the CI gate agree on what constitutes legacy authority.
    """
    blockers = []
    gate_path = ROOT / "tools" / "check_forbidden_file_reads.py"
    if not gate_path.exists():
        return blockers
    r = subprocess.run([sys.executable, str(gate_path)], capture_output=True, text=True)
    if r.returncode != 0:
        blockers.append({
            "code": "LEGACY_FILE_AUTHORITY",
            "detail": "Production services still read legacy JSON authority files "
                      "(see tools/check_forbidden_file_reads.py output)",
            "location": str(gate_path),
        })
    return blockers


def assess_release_readiness():
    """Scan production code for known-placeholder patterns.

    Returns:
        dict with keys:
            ready (bool): True if no blockers found
            blockers (list[dict]): each with code, detail, location
    """
    blockers = []
    blockers.extend(_check_placeholder_scorer())
    blockers.extend(_check_stubbed_provider())
    blockers.extend(_check_auto_approved_gates())
    blockers.extend(_check_deleted_produce_import())
    blockers.extend(_check_padding_slicer())
    blockers.extend(_check_stubbed_publish_analytics())
    blockers.extend(_check_legacy_file_authority())

    return {"ready": len(blockers) == 0, "blockers": blockers}


def require_production_ready():
    """Raise RuntimeError if production code contains known-placeholder patterns.

    Fake/simulated providers are permitted ONLY when YT_TEST_MODE=1 or under
    pytest (PYTEST_CURRENT_TEST is set).  No exceptions for production: every
    placeholder returned by assess_release_readiness is a hard block.

    Raises:
        RuntimeError: BLOCKED: PRODUCTION_RELEASE_INVARIANTS_UNMET
    """
    if _is_test_mode():
        return

    assessment = assess_release_readiness()
    if not assessment["ready"]:
        msg = "BLOCKED: PRODUCTION_RELEASE_INVARIANTS_UNMET\n"
        for b in assessment["blockers"]:
            msg += f"  [{b['code']}] {b['detail']} ({b['location']})\n"
        raise RuntimeError(msg)


def _is_test_mode():
    return os.environ.get("YT_TEST_MODE") == "1" or "PYTEST_CURRENT_TEST" in os.environ


def _cli_status():
    assessment = assess_release_readiness()
    print(_json_out(assessment))
    if not assessment["ready"]:
        raise SystemExit(1)


def _cli_check():
    assessment = assess_release_readiness()
    if "--verbose" in sys.argv:
        print(_json_out(assessment))
    if not assessment["ready"]:
        raise SystemExit(1)


def _json_out(obj):
    import json
    return json.dumps(obj, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Usage: release_guard.py <status|check> [--verbose]", file=sys.stderr)
        raise SystemExit(2)
    cmd = sys.argv[1]
    if cmd == "status":
        _cli_status()
    elif cmd == "check":
        _cli_check()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

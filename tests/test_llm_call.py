#!/usr/bin/env python3
"""tests/test_llm_call.py — P4-07 tests (no live API calls)."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def _load():
    spec = importlib.util.spec_from_file_location("llm_call", ROOT / "scripts" / "llm_call.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_config_loads():
    lc = _load()
    cfg = lc.load_config()
    assert "profiles" in cfg
    assert "sonnet_creative" in cfg["profiles"]
    assert "auto_utility" in cfg["profiles"]
    assert cfg["profiles"]["sonnet_creative"]["is_final_creative_authority"] is True
    assert cfg["profiles"]["auto_utility"]["is_final_creative_authority"] is False
    print("  ✓ config loads with correct profiles")


def test_creative_authority_enforced():
    lc = _load()
    cfg = lc.load_config()
    try:
        lc.resolve_profile(cfg, "script_review", "auto_utility")
        assert False, "should block"
    except RuntimeError as e:
        assert "BLOCKED" in str(e) and "creative-authority" in str(e)
    print("  ✓ creative_authority tasks blocked from auto_utility")


def test_utility_task_uses_auto():
    lc = _load()
    cfg = lc.load_config()
    name, profile = lc.resolve_profile(cfg, "json_normalization")
    assert name == "auto_utility"
    assert profile["model"] == "auto"
    print("  ✓ utility tasks default to auto_utility")


def test_creative_task_defaults_sonnet():
    lc = _load()
    cfg = lc.load_config()
    name, profile = lc.resolve_profile(cfg, "storyboard_review")
    assert name == "sonnet_creative"
    assert profile["model"] == "claude-sonnet-4.6"
    print("  ✓ creative tasks default to sonnet_creative")


def test_unknown_profile_raises():
    lc = _load()
    cfg = lc.load_config()
    try:
        lc.resolve_profile(cfg, "test", "nonexistent_profile")
        assert False
    except ValueError as e:
        assert "Unknown profile" in str(e)
    print("  ✓ unknown profile raises ValueError")


def test_extract_response_simple():
    lc = _load()
    stdout = 'some noise\n> {"status":"pass","may_proceed":true}\nmore noise\n'
    r = lc.extract_response(stdout)
    assert r and '"status"' in r
    print(f"  ✓ extract_response extracts > line")


def test_extract_response_multiline():
    lc = _load()
    stdout = 'noise\n> {\n>   "status": "pass"\n> }\nend\n'
    r = lc.extract_response(stdout)
    assert "pass" in r
    print("  ✓ extract_response handles multi-line > output")


def test_parse_json_response_clean():
    lc = _load()
    text = '{"status": "pass", "may_proceed": true, "warnings": []}'
    data = lc.parse_json_response(text)
    assert data["status"] == "pass"
    assert data["may_proceed"] is True
    print("  ✓ parse_json_response: clean JSON")


def test_parse_json_response_fenced():
    lc = _load()
    text = '```json\n{"status": "fail", "blocking_issues": ["x"]}\n```'
    data = lc.parse_json_response(text)
    assert data["status"] == "fail"
    print("  ✓ parse_json_response: strips markdown fences")


def test_parse_json_response_embedded():
    lc = _load()
    text = 'Here is the review:\n{"status": "pass", "score": 4}\nDone.'
    data = lc.parse_json_response(text)
    assert data["score"] == 4
    print("  ✓ parse_json_response: extracts embedded JSON")


def test_validate_output():
    lc = _load()
    assert lc.validate_output({"status": "pass", "may_proceed": True}) == []
    assert lc.validate_output({"status": "invalid"}) != []
    assert lc.validate_output({"may_proceed": "yes"}) != []
    assert lc.validate_output("not a dict") != []
    # A successfully-parsed JSON array is valid (storyboard beats / reviewer lists)
    assert lc.validate_output([{"beat_id": "B001"}]) == []
    assert lc.validate_output([]) == []
    print("  ✓ validate_output catches bad status/may_proceed/non-dict, accepts arrays")


def test_dry_run_no_subprocess(capsys=None):
    lc = _load()
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        data, text, profile, model = lc.llm_call(
            task="storyboard_review", prompt="test", dry_run=True)
    out = buf.getvalue()
    assert data is None  # no actual call
    assert "sonnet_creative" in out
    assert "claude-sonnet-4.6" in out
    print("  ✓ dry_run prints plan without calling kiro-cli")


def test_no_secrets_in_source():
    src = (ROOT / "scripts" / "llm_call.py").read_text()
    for pattern in ["sk-", "xai-", "KIRO_TOKEN", "api_key =", "token ="]:
        assert pattern not in src, f"found secret-like pattern: {pattern!r}"
    print("  ✓ no secrets/tokens in llm_call.py source")


def main():
    print("LLM Call Tests (P4-07)")
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'PASSED' if failed == 0 else 'FAILED'}: {passed}/{passed+failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()

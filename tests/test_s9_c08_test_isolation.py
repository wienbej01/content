"""S9-C08 — test-isolation guard (D-017).

Static check: no test module sets PRODUCTION_DB_PATH / CLIP_DB_PATH at module-import
scope. A module-level os.environ[...] = ... leaks across the pytest session (conftest's
per-test monkeypatch restores the value to the leaked one after each test), breaking
order-independence. DB env must be set inside an autouse fixture (with a matching
teardown) or via conftest's per-test monkeypatch.

This guard parses the AST of every test file and flags module-level DB-env assignments —
a real check, not a comment. (The companion fix is the STAGE_INVOKERS snapshot/restore in
test_produce_db_orchestrator's autouse fixture, which stopped the invoker-mock leak that
was the actual e2e-breaker.)
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # tests/
DB_ENV_KEYS = {"PRODUCTION_DB_PATH", "CLIP_DB_PATH"}


def _subscript_str_constant(subscript_node):
    """Return the string constant indexing os.environ[...], or None (Python 3.9+)."""
    sl = subscript_node.slice
    if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
        return sl.value
    return None


def _module_level_db_env_assigns(path: Path):
    """Yield (lineno, key) for module-level os.environ[<DB_KEY>] = ... assignments only.

    Assignments nested inside functions/classes (i.e. fixture-scoped) are in those nodes'
    bodies, NOT tree.body, so they are correctly ignored.
    """
    tree = ast.parse(path.read_text())
    for node in tree.body:  # module-level statements only
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not (isinstance(tgt, ast.Subscript)
                    and isinstance(tgt.value, ast.Attribute)
                    and isinstance(tgt.value.value, ast.Name)
                    and tgt.value.value.id == "os"
                    and tgt.value.attr == "environ"):
                continue
            key = _subscript_str_constant(tgt)
            if key in DB_ENV_KEYS:
                yield node.lineno, key


def test_no_module_level_db_env_override_in_tests():
    """No test file sets PRODUCTION_DB_PATH/CLIP_DB_PATH at module scope (D-017)."""
    offenders = []
    for p in sorted(ROOT.rglob("test_*.py")):
        for lineno, key in _module_level_db_env_assigns(p):
            offenders.append(f"{p.relative_to(ROOT.parent)}:{lineno} sets os.environ[{key!r}] at module scope")
    assert not offenders, (
        "module-level DB env override leaks across the session (D-017):\n  " + "\n  ".join(offenders)
    )

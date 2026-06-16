"""Tests for tools/check_forbidden_file_reads.py (ALN-H1 CI Gate)."""
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECK_SCRIPT = ROOT / "tools" / "check_forbidden_file_reads.py"


def test_check_file_catches_open_forbidden_file():
    """Verify the AST parser catches open('state.json') calls."""
    code = """
def read_state():
    with open("Videos/Projects/test/state.json", "r") as f:
        return f.read()
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        filepath = Path(f.name)
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_gate", CHECK_SCRIPT)
    check_gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_gate)
    
    violations = check_gate.check_file(filepath)
    filepath.unlink()
    
    assert len(violations) == 1
    assert "Forbidden open() of legacy file" in violations[0]
    assert "state.json" in violations[0]


def test_check_file_catches_path_read_text():
    """Verify the AST parser catches Path('manifest.json').read_text() calls."""
    code = """
from pathlib import Path
def read_manifest():
    return Path("Videos/Projects/test/manifest.json").read_text()
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        filepath = Path(f.name)
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_gate", CHECK_SCRIPT)
    check_gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_gate)
    
    violations = check_gate.check_file(filepath)
    filepath.unlink()
    
    assert len(violations) == 1
    assert "Forbidden Path().read_text()/read_bytes() of legacy file" in violations[0]
    assert "manifest.json" in violations[0]


def test_check_file_catches_json_loads_path_read():
    """Verify the AST parser catches json.loads(Path('media_plan.json').read_text())."""
    code = """
import json
from pathlib import Path
def read_plan():
    return json.loads(Path("media_plan.json").read_text())
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        filepath = Path(f.name)
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_gate", CHECK_SCRIPT)
    check_gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_gate)
    
    violations = check_gate.check_file(filepath)
    filepath.unlink()
    
    # It catches both the json.loads and the inner Path().read_text() as separate violations
    assert len(violations) >= 1
    assert any("Forbidden json.loads(Path().read_text()) of legacy file" in v and "media_plan.json" in v for v in violations)


def test_check_file_allows_safe_reads():
    """Verify the AST parser allows reading safe, non-forbidden files."""
    code = """
import json
from pathlib import Path
def read_config():
    return json.loads(Path("config.json").read_text())
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        filepath = Path(f.name)
    
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_gate", CHECK_SCRIPT)
    check_gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_gate)
    
    violations = check_gate.check_file(filepath)
    filepath.unlink()
    
    assert len(violations) == 0

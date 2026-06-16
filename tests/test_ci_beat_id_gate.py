"""Tests for tools/check_forbidden_beat_id_lookups.py (ALN-B1 CI Gate)."""
import ast
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECK_SCRIPT = ROOT / "tools" / "check_forbidden_beat_id_lookups.py"


def test_check_file_catches_subscript_lookup():
    """Verify the AST parser catches dict['beat_id'] lookups."""
    code = """
def process(beat):
    return beat["beat_id"]
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        f.flush()
        filepath = Path(f.name)
    
    # Import the function dynamically to avoid script execution side effects
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_gate", CHECK_SCRIPT)
    check_gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_gate)
    
    violations = check_gate.check_file(filepath)
    filepath.unlink()
    
    assert len(violations) == 1
    assert "Forbidden dictionary lookup ['beat_id']" in violations[0]


def test_check_file_catches_get_lookup():
    """Verify the AST parser catches dict.get('beat_id') lookups."""
    code = """
def process(beat):
    return beat.get("beat_id")
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
    assert "Forbidden .get('beat_id')" in violations[0]


def test_check_file_allows_other_keys():
    """Verify the AST parser allows legitimate keys like 'render_unit_id'."""
    code = """
def process(beat):
    return beat["render_unit_id"]
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


def test_check_file_allows_variable_subscript():
    """Verify the AST parser allows dict[beat_id] where beat_id is a variable."""
    code = """
def process(beat, beat_id):
    return beat[beat_id]
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
    
    # The gate specifically targets the string literal "beat_id", not the variable
    assert len(violations) == 0

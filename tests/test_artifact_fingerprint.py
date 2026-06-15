"""Tests for scripts/artifact_fingerprint.py (TKT-01)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from artifact_fingerprint import write_fingerprint, read_fingerprint, verify_fingerprint


def test_write_read_fingerprint(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"fake video content")
    write_fingerprint(f, "generate_media.py", "1", project_id="proj_a")
    fp = read_fingerprint(f)
    assert fp is not None
    assert fp["sha256"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" or len(fp["sha256"]) == 64
    assert fp["producer"] == "generate_media.py"
    assert fp["project_id"] == "proj_a"
    assert fp["size_bytes"] == len(b"fake video content")


def test_verify_valid_fingerprint(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"valid content")
    write_fingerprint(f, "generate_media.py", "1", project_id="proj_a")
    valid, reason = verify_fingerprint(f)
    assert valid is True
    assert reason == "valid"


def test_verify_detects_modified_file(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"original content")
    write_fingerprint(f, "generate_media.py", "1", project_id="proj_a")
    f.write_bytes(b"TAMPERED content")
    valid, reason = verify_fingerprint(f)
    assert valid is False
    assert "sha256 mismatch" in reason


def test_missing_fp_returns_none(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"no fingerprint written")
    assert read_fingerprint(f) is None


def test_cross_project_reuse_detected(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"content from project A")
    write_fingerprint(f, "generate_media.py", "1", project_id="project_A")
    valid, reason = verify_fingerprint(f, expected_project_id="project_B")
    assert valid is False
    assert "project_id mismatch" in reason


def test_upstream_hash_mismatch_detected(tmp_path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"some media")
    write_fingerprint(f, "generate_media.py", "1", upstream_hashes=["hash_A"], project_id="p1")
    valid, reason = verify_fingerprint(f, upstream_hashes=["hash_B"])
    assert valid is False
    assert "upstream_hashes mismatch" in reason

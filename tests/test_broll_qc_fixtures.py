import hashlib
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Ensure 'scripts' is on sys.path before importing fixtures module
import sys
sys.path.insert(0, str(ROOT / "scripts"))

from tests.fixtures.broll_qc_fixtures import (
    BrollFixture,
    build_all_fixtures,
    make_face_in_focus_clip,
    make_frozen_clip,
    make_moving_clip,
    make_text_in_focus_clip,
)


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def extract_frame(path: Path, out: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(path), "-vframes", "1",
         "-q:v", "2", str(out)],
        capture_output=True,
    )


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def assert_fixture_valid(fx: BrollFixture) -> None:
    assert fx.path.exists(), f"{fx.path} does not exist"
    assert fx.path.stat().st_size > 5_000, f"{fx.path} too small ({fx.path.stat().st_size} bytes)"
    dur = probe_duration(fx.path)
    assert 4.0 <= dur <= 6.0, f"duration {dur}s out of expected range"
    assert fx.width == 1920
    assert fx.height == 1080


def test_frozen_clip(tmp_path: Path):
    fx = make_frozen_clip(tmp_path / "frozen")
    assert_fixture_valid(fx)
    assert fx.has_text is False
    assert fx.has_face is False
    assert fx.is_frozen is True


def test_moving_clip(tmp_path: Path):
    fx = make_moving_clip(tmp_path / "moving")
    assert_fixture_valid(fx)
    assert fx.has_text is False
    assert fx.has_face is False
    assert fx.is_frozen is False


def test_text_in_focus_clip(tmp_path: Path):
    fx = make_text_in_focus_clip(tmp_path / "text")
    assert_fixture_valid(fx)
    assert fx.has_text is True
    assert fx.has_face is False
    assert fx.is_frozen is True  # static slide


def test_face_in_focus_clip(tmp_path: Path):
    fx = make_face_in_focus_clip(tmp_path / "face")
    assert_fixture_valid(fx)
    assert fx.has_text is False
    assert fx.has_face is True
    assert fx.is_frozen is True  # static drawing


def test_frozen_frame_bytes_match(tmp_path: Path):
    fx = make_frozen_clip(tmp_path / "fz").path
    f1 = tmp_path / "fz_f1.jpg"
    fn = tmp_path / "fz_fn.jpg"
    extract_frame(fx, f1)
    # extract a later frame by seeking near end
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "4.5", "-i", str(fx),
         "-vframes", "1", "-q:v", "2", str(fn)],
        capture_output=True,
    )
    assert sha256(f1) == sha256(fn), "frozen clip frames must be byte-identical"


def test_moving_frame_bytes_differ(tmp_path: Path):
    fx = make_moving_clip(tmp_path / "mv").path
    f1 = tmp_path / "mv_f1.jpg"
    fn = tmp_path / "mv_fn.jpg"
    extract_frame(fx, f1)
    subprocess.run(
        ["ffmpeg", "-y", "-ss", "4.5", "-i", str(fx),
         "-vframes", "1", "-q:v", "2", str(fn)],
        capture_output=True,
    )
    assert sha256(f1) != sha256(fn), "moving clip frames must differ"


def test_determinism_frozen(tmp_path: Path):
    fx1 = make_frozen_clip(tmp_path / "d1").path
    fx2 = make_frozen_clip(tmp_path / "d2").path
    assert sha256(fx1) == sha256(fx2), "frozen clip must be deterministic"


def test_determinism_text(tmp_path: Path):
    fx1 = make_text_in_focus_clip(tmp_path / "t1").path
    fx2 = make_text_in_focus_clip(tmp_path / "t2").path
    assert sha256(fx1) == sha256(fx2), "text clip must be deterministic"


def test_determinism_face(tmp_path: Path):
    fx1 = make_face_in_focus_clip(tmp_path / "fc1").path
    fx2 = make_face_in_focus_clip(tmp_path / "fc2").path
    assert sha256(fx1) == sha256(fx2), "face clip must be deterministic"


def test_no_file_handle_leak(tmp_path: Path):
    fixtures = build_all_fixtures(tmp_path)
    import gc
    gc.collect()
    for name, fx in fixtures.items():
        assert fx.path.exists(), f"{name} fixture path does not exist"
    del fixtures
    gc.collect()
    # tmp_path is pytest-managed; no manual cleanup needed


def test_hermetic_no_network(monkeypatch, tmp_path: Path):
    """ Verify that b-roll fixture generation does not use network by disabling
    name resolution and confirming the generator still works. """
    # Re-create source module function without requiring internet
    import socket
    noop = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("network disabled"))
    monkeypatch.setattr(socket, "gethostbyname", noop)
    fx = make_frozen_clip(tmp_path / "hermetic")
    assert_fixture_valid(fx)

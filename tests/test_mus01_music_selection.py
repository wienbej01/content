"""MUS-01: Music library selection — deterministic per project_id."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_manifest.py"
ROOT = Path(__file__).resolve().parent.parent


def _load_module(tmp_root):
    """Load build_manifest with ROOT patched to tmp_root."""
    spec = importlib.util.spec_from_file_location("build_manifest", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    mod.ROOT = tmp_root
    spec.loader.exec_module(mod)
    mod.ROOT = tmp_root
    return mod


def _make_library(tmp_path, tracks=("a.mp3", "b.mp3", "c.mp3")):
    """Create a fake music library with tiny files."""
    lib = tmp_path / "assets" / "music"
    lib.mkdir(parents=True, exist_ok=True)
    for name in tracks:
        (lib / name).write_bytes(b"\xff" * 64)
    return lib


def _write_constraints(tmp_path, music_cfg):
    """Write a minimal constraints.json."""
    d = tmp_path / "docs" / "channel_universe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "constraints.json").write_text(json.dumps({"music": music_cfg}))


class TestMusicSelection:
    def test_selects_track_from_library(self):
        """A project with no default_path picks a real track from assets/music."""
        mod = _load_module(ROOT)
        cfg, err = mod.load_music_config(
            "Videos/Projects/some_project", "short", project_id="test_proj"
        )
        assert err is None
        assert cfg["enabled"] is True
        assert cfg["path"].startswith("assets/music/")
        assert Path(ROOT / cfg["path"]).exists()

    def test_deterministic_per_project(self, tmp_path):
        """Same project_id always selects the SAME track."""
        _make_library(tmp_path)
        _write_constraints(tmp_path, {
            "required_for_formats": ["short"],
            "library_dir": "assets/music",
            "selection": "deterministic_per_project",
        })
        mod = _load_module(tmp_path)

        cfg1, _ = mod.load_music_config(tmp_path / "proj", "short", project_id="stable_id")
        cfg2, _ = mod.load_music_config(tmp_path / "proj", "short", project_id="stable_id")
        assert cfg1["path"] == cfg2["path"]

    def test_different_projects_different_tracks(self, tmp_path):
        """Several distinct project_ids spread across the library (not all same)."""
        _make_library(tmp_path, tracks=[f"track_{i}.mp3" for i in range(6)])
        _write_constraints(tmp_path, {
            "required_for_formats": ["short"],
            "library_dir": "assets/music",
            "selection": "deterministic_per_project",
        })
        mod = _load_module(tmp_path)

        selected = set()
        for pid in [f"project_{i}" for i in range(20)]:
            cfg, _ = mod.load_music_config(tmp_path / "proj", "short", project_id=pid)
            selected.add(cfg["path"])
        # With 6 tracks and 20 project_ids, expect at least 3 different tracks
        assert len(selected) >= 3

    def test_explicit_default_path_override(self, tmp_path):
        """If default_path set + exists, it's used instead of library selection."""
        _make_library(tmp_path)
        override = tmp_path / "brand" / "music" / "override.mp3"
        override.parent.mkdir(parents=True)
        override.write_bytes(b"\xff" * 64)

        _write_constraints(tmp_path, {
            "required_for_formats": ["short"],
            "library_dir": "assets/music",
            "default_path": "brand/music/override.mp3",
        })
        mod = _load_module(tmp_path)

        cfg, err = mod.load_music_config(tmp_path / "proj", "short", project_id="any")
        assert err is None
        assert cfg["path"] == "brand/music/override.mp3"
        assert "selected_by" not in cfg  # not library-selected

    def test_required_music_empty_library_fails(self, tmp_path):
        """format=short, empty library_dir → error."""
        lib = tmp_path / "assets" / "music"
        lib.mkdir(parents=True)
        # Empty library — no tracks

        _write_constraints(tmp_path, {
            "required_for_formats": ["short"],
            "library_dir": "assets/music",
        })
        mod = _load_module(tmp_path)

        cfg, err = mod.load_music_config(tmp_path / "proj", "short", project_id="x")
        assert cfg is None
        assert "required" in err.lower()

    def test_selected_track_in_manifest(self, tmp_path):
        """The manifest music block carries the resolved selected track path."""
        _make_library(tmp_path, tracks=["song.mp3"])
        _write_constraints(tmp_path, {
            "required_for_formats": ["short"],
            "library_dir": "assets/music",
            "selection": "deterministic_per_project",
        })
        mod = _load_module(tmp_path)

        cfg, err = mod.load_music_config(tmp_path / "proj", "short", project_id="vid_1")
        assert err is None
        assert cfg["enabled"] is True
        assert "song.mp3" in cfg["path"]
        assert cfg["selected_by"] == "deterministic_per_project"
        assert cfg["project_id"] == "vid_1"

"""Tests for scripts/build_quality_report.py."""
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_quality_report.py"


def _make_final_qa(project, status="pass", issues=None, video_dur=83.3, audio_dur=83.3):
    data = {
        "video_duration": video_dur,
        "audio_duration": audio_dur,
        "container_duration": audio_dur,
        "issues": issues or [],
        "status": status,
    }
    (project / "final_qa_report.json").write_text(json.dumps(data))


def _make_media_qa(project, failed_beats=None):
    results = []
    for bid in ["B001", "B002", "B003"]:
        is_fail = failed_beats and bid in failed_beats
        results.append({
            "id": bid, "status": "fail" if is_fail else "pass",
            "issues": ["some issue"] if is_fail else [],
        })
    fail_count = len(failed_beats) if failed_beats else 0
    data = {"results": results, "passed": fail_count == 0, "total": len(results), "fail": fail_count}
    (project / "media_qa_report.json").write_text(json.dumps(data))


def _make_duration_csv(project, failed_beats=None):
    rows = []
    for bid in ["B001", "B002", "B003"]:
        is_fail = failed_beats and bid in failed_beats
        rows.append({
            "beat_id": bid,
            "required_sec": "10.0",
            "available_sec": "5.0" if is_fail else "10.0",
            "deficit_sec": "5.0" if is_fail else "0.0",
            "status": "INSUFFICIENT" if is_fail else "OK",
            "asset_type": "generated_video",
            "output_path": f"assets/media/seg/{bid}.mp4",
        })
    out = project / "duration_reconciliation.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def _make_manifest(project):
    data = {"id": project.name, "segments": [{"id": "B001", "overlay": {"required": True}}]}
    (project / "manifest.json").write_text(json.dumps(data))


def _make_assembly_log(project, music_enabled=False):
    data = {"id": project.name, "music": {"enabled": music_enabled}}
    (project / f"{project.name}_log.json").write_text(json.dumps(data))


def _valid_project(tmp_path):
    """Create a fully passing project fixture."""
    p = tmp_path / "test_project"
    p.mkdir()
    _make_final_qa(p)
    _make_media_qa(p)
    _make_duration_csv(p)
    _make_manifest(p)
    _make_assembly_log(p)
    return p


def test_valid_project_produces_pass(tmp_path):
    project = _valid_project(tmp_path)
    r = subprocess.run([sys.executable, str(SCRIPT), str(project)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    report = json.loads((project / "run_quality_report.json").read_text())
    assert report["status"] == "PASS"
    assert "Ready for Gate B review" in report["recommendation"]
    assert (project / "run_quality_report.md").exists()


def test_missing_final_qa_fails(tmp_path):
    project = _valid_project(tmp_path)
    (project / "final_qa_report.json").unlink()
    r = subprocess.run([sys.executable, str(SCRIPT), str(project)],
                       capture_output=True, text=True)
    assert r.returncode != 0
    report = json.loads((project / "run_quality_report.json").read_text())
    assert report["status"] == "FAIL"
    assert "stream_integrity" in report["dominant_failures"]


def test_failed_media_qa_fails(tmp_path):
    project = _valid_project(tmp_path)
    _make_media_qa(project, failed_beats=["B001", "B002"])
    r = subprocess.run([sys.executable, str(SCRIPT), str(project)],
                       capture_output=True, text=True)
    assert r.returncode != 0
    report = json.loads((project / "run_quality_report.json").read_text())
    assert report["status"] == "FAIL"
    assert "media_qa" in report["dominant_failures"]


def test_stream_mismatch_fails(tmp_path):
    project = _valid_project(tmp_path)
    _make_final_qa(project, status="fail", issues=["LENGTH_MISMATCH"],
                   video_dur=83.3, audio_dur=146.6)
    r = subprocess.run([sys.executable, str(SCRIPT), str(project)],
                       capture_output=True, text=True)
    assert r.returncode != 0
    report = json.loads((project / "run_quality_report.json").read_text())
    assert report["status"] == "FAIL"
    assert "stream_integrity" in report["dominant_failures"]


def test_missing_section_is_fail_closed(tmp_path):
    """Any required section absent = FAIL (media_qa_report.json missing)."""
    project = _valid_project(tmp_path)
    (project / "media_qa_report.json").unlink()
    r = subprocess.run([sys.executable, str(SCRIPT), str(project)],
                       capture_output=True, text=True)
    assert r.returncode != 0
    report = json.loads((project / "run_quality_report.json").read_text())
    assert report["status"] == "FAIL"
    assert "media_qa" in report["dominant_failures"]

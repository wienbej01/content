#!/usr/bin/env python3
"""preflight.py — System dependency checker for the production pipeline.

Checks all required system dependencies and API keys before any paid call.
Returns 0 if all checks pass, non-zero with actionable diagnostics otherwise.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    required: bool = True


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)
    all_passed: bool = True
    actionable: list[str] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.checks.append(result)
        if not result.passed and result.required:
            self.all_passed = False
            self.actionable.append(f"[{result.name}] {result.detail}")

    def print_report(self) -> None:
        for c in self.checks:
            status = "PASS" if c.passed else ("WARN" if not c.required else "FAIL")
            detail = f" — {c.detail}" if c.detail else ""
            print(f"  {status} {c.name}{detail}")
        print()
        if self.all_passed:
            print("All required dependencies satisfied.")
        else:
            print("MISSING DEPENDENCIES:", file=sys.stderr)
            for a in self.actionable:
                print(f"  - {a}", file=sys.stderr)


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _run_version(cmd: list[str], timeout: int = 10) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (result.returncode == 0, (result.stdout or result.stderr).strip().split("\n")[0])
    except FileNotFoundError:
        return (False, f"command not found: {cmd[0]}")
    except subprocess.TimeoutExpired:
        return (False, "timeout")
    except Exception as exc:
        return (False, str(exc))


def check_tesseract() -> CheckResult:
    if _which("tesseract"):
        ok, line = _run_version(["tesseract", "--version"])
        if ok:
            return CheckResult("tesseract", True, line.split("\n")[0][:80])
        return CheckResult("tesseract", False, f"found but --version failed: {line}", required=True)
    return CheckResult("tesseract", False, "tesseract binary not found on PATH — install: apt install tesseract-ocr tesseract-ocr-eng", required=True)


def check_pytesseract() -> CheckResult:
    try:
        import pytesseract
        _ = pytesseract
        return CheckResult("pytesseract", True, "importable")
    except ImportError:
        return CheckResult("pytesseract", False, "pip install pytesseract", required=True)


def check_ffmpeg() -> CheckResult:
    if _which("ffmpeg"):
        ok, line = _run_version(["ffmpeg", "-version"])
        if ok:
            return CheckResult("ffmpeg", True, line[:80])
    return CheckResult("ffmpeg", False, "ffmpeg not found on PATH", required=True)


def check_ffprobe() -> CheckResult:
    if _which("ffprobe"):
        ok, line = _run_version(["ffprobe", "-version"])
        if ok:
            return CheckResult("ffprobe", True, line[:80])
    return CheckResult("ffprobe", False, "ffprobe not found on PATH", required=True)


def check_mediapipe() -> CheckResult:
    try:
        import mediapipe
        _ = mediapipe
        return CheckResult("mediapipe", True, "importable")
    except ImportError:
        return CheckResult("mediapipe", False, "pip install mediapipe", required=False)


def check_elevenlabs() -> CheckResult:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if key and len(key) > 8:
        return CheckResult("elevenlabs_api_key", True, "set")
    return CheckResult("elevenlabs_api_key", False, "ELEVENLABS_API_KEY not set or too short", required=False)


def check_higgsfield() -> CheckResult:
    if _which("higgsfield") or _which("npm"):
        return CheckResult("higgsfield_cli", True, "npm/higgsfield found")
    return CheckResult("higgsfield_cli", False, "npm install @higgsfield/cli", required=False)


def check_smoke_config() -> CheckResult:
    cfg_path = Path(__file__).resolve().parent.parent / "configs" / "strict_smoke.yaml"
    if cfg_path.exists():
        return CheckResult("strict_smoke.yaml config", True, str(cfg_path))
    return CheckResult("strict_smoke.yaml config", False, "configs/strict_smoke.yaml not found", required=False)


def check_python() -> CheckResult:
    version = sys.version_info
    if version >= (3, 9):
        return CheckResult("python", True, f"{version.major}.{version.minor}.{version.micro}")
    return CheckResult("python", False, f"Python 3.9+ required, found {version.major}.{version.minor}", required=True)


def check_all() -> PreflightReport:
    report = PreflightReport()
    report.add(check_python())
    report.add(check_ffmpeg())
    report.add(check_ffprobe())
    report.add(check_tesseract())
    report.add(check_pytesseract())
    report.add(check_mediapipe())
    report.add(check_elevenlabs())
    report.add(check_higgsfield())
    report.add(check_smoke_config())
    return report


def main() -> int:
    report = check_all()
    report.print_report()
    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

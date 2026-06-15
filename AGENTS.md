# Repository Guidelines

## Project Structure & Module Organization

This repository is a Python-first production pipeline for educational YouTube videos. Core pipeline stages live in `scripts/`; each stage is generally a standalone CLI that reads JSON and writes JSON or media artifacts. Shared utilities are in `tools/`, planning and milestone tracking are in `strategy/`, and runtime/model settings are in `configs/`. JSON contracts belong in `schemas/`. Keep creative rules and operational documentation under `docs/`, source research under `research/`, and reusable brand or music files under `brand/` and `assets/`. Tests mirror pipeline behavior in `tests/test_<stage>.py`. Generated videos, media, databases, and local secrets are intentionally ignored by Git.

## Build, Test, and Development Commands

- `pip install pyyaml` installs the documented Python dependency.
- `npm install` installs the Higgsfield CLI dependency from `package-lock.json`.
- `python3 strategy/plan.py status` shows completed and upcoming production milestones.
- `python3 -m pytest -q` runs the full test suite.
- `python3 -m pytest tests/test_assemble.py -k lipsync` runs a focused test subset.
- `python3 scripts/storyboard.py <script.json> --dry-run` validates a stage without producing billable output.
- `python3 scripts/assemble.py <manifest.json> --formats 16x9` assembles a selected output format; FFmpeg and FFprobe must be available.

## Coding Style & Naming Conventions

Use Python 3, four-space indentation, `snake_case` for functions and modules, and `UPPER_SNAKE_CASE` for constants. Preserve the existing CLI pattern: `argparse`, `pathlib.Path`, explicit exit codes, and useful stderr errors. Add short module and function docstrings where behavior is not obvious. Prefer structured JSON/YAML parsing over text manipulation. No repository-wide formatter is configured, so match nearby code and keep imports grouped as standard library, third-party, then local.

## Testing Guidelines

Tests use `pytest` and are named `test_<behavior>`. Add focused regression tests for every behavior change, especially gate checks, schema validation, audio timing, routing, and generated-file side effects. Use temporary directories and subprocess calls when testing CLI contracts. Tests must avoid paid APIs and should use `--dry-run`, mocks, or deterministic fixtures.

## Commit & Pull Request Guidelines

Recent history uses concise imperative subjects, commonly Conventional Commit prefixes such as `feat:`, `fix:`, and `docs:`; scoped milestone labels such as `T4+T5` are also used. Keep commits limited to one coherent change. Pull requests should explain the affected pipeline stage, list validation commands, link the relevant plan or issue, and include before/after screenshots or media samples for visual changes. Never commit `.env` files, `runtime.env`, credentials, generated media, or database contents.

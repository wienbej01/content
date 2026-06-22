# Auditor Report — S1-T02: Enforce one database authority

- **Ticket:** S1-T02
- **Agent:** Agent 8 (Independent Software Auditor) — read & test only.
- **Subject:** uncommitted working tree on fix/flagship-001-end-to-end-recovery

## Diff inspection
- scripts/produce_db.py: removed two fallback-read blocks (invoke_write_script lines 84-90, invoke_review_script lines 120-130). Both now raise RuntimeError on missing DB document. Verified no other DB-native invoker reads legacy JSON (generate_media, assemble, compile_media, audio_timing all read from DB). invoke_assemble writes a temp manifest in tmp_path (transient DTO, not an authority file) — acceptable.
- tools/check_forbidden_file_reads.py: enhanced AST path resolution. Reviewed `_extract_string_constants` — correctly handles Constant, BinOp (Div/Add), JoinedStr, Call (Path), Attribute. No false negatives on the common patterns. ALLOWLIST additions are legacy CLIs confirmed NOT in STAGE_REGISTRY.

## Forbidden-pattern search (post-change)
Ran the mandatory search across scripts/:
- No NEW legacy JSON reads introduced in produce_db.py (fallback reads removed, exports remain write-only).
- `script.json` write references remain (lines 105, 155) — these are `write_text` (exports), not reads. Gate only checks read operations.
- CI gate passes clean.

## Tests run
- `python3 tools/check_forbidden_file_reads.py` → PASS
- `python3 -m pytest tests/contracts/test_db_authority.py` → 4 passed
- `python3 -m pytest tests/test_produce_db_orchestrator.py tests/test_sprint2_production_repo.py tests/contracts/` → 91 passed
- `python3 tools/check_test_quality.py` → PASS

## Mocked-evidence check
- test_db_authority uses REAL production_db, REAL authoring_service, REAL produce_db.invoke_storyboard. No mocks of DB connections.
- test_runtime_file_trace patches builtins.open (tracing), not the DB — the DB is real SQLite.
- test_stale_json writes a REAL stale file to disk and verifies the DB value wins — real filesystem, real DB.

## Verdict
**AUDITOR PASS** — legacy fallback reads removed; dynamic-read CI gate strengthened and verified; 4 named tests pass with real DB; no regressions in 91 orchestrator/authoring tests.

## BLOCKED conditions
None.

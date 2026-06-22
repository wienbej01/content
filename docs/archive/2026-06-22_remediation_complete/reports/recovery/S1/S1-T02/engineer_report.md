# Engineer Report — S1-T02: Enforce one database authority

- **Ticket:** S1-T02
- **Agent:** Agent 1 (Database and Data-Lineage Engineer)
- **Objective:** Remove live fallback reads from legacy JSON in DB-native stages; strengthen the forbidden-file-reads CI gate to detect dynamic path construction; prove DB-native execution succeeds with all export JSON deleted.
- **Base SHA:** 68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f
- **Result SHA:** (uncommitted on fix/flagship-001-end-to-end-recovery)

## Files changed
- scripts/produce_db.py — removed legacy JSON fallback reads in `invoke_write_script` (research_brief.json) and `invoke_review_script` (script.json + research_brief.json). Both now fail closed if the DB doesn't have the document.
- tools/check_forbidden_file_reads.py — enhanced with AST constant-folding (`_extract_string_constants`) that catches dynamic path construction (Path division, f-strings, concatenation); added script.json, storyboard.json, research_brief.json, production_storyboard.json to FORBIDDEN_FILES; added legacy CLIs to ALLOWLIST.
- tests/contracts/test_db_authority.py (NEW) — 4 named S1-T02 tests.

## Implementation summary
- **Fallback removal:** The DB-native invokers `invoke_write_script` and `invoke_review_script` previously fell back to reading `research_brief.json` / `script.json` from disk when the DB lacked the document. This created a silent authority conflict (D-001): a stale file could override the DB. Both now raise `RuntimeError` directing the operator to run the prerequisite stage. The DB is the sole authority; exports are write-only projections.
- **Dynamic-read CI gate:** The old gate only caught literal-string `open("state.json")` / `Path("media_plan.json").read_text()`. Dynamic construction (`project_dir / "media_plan.json"`) bypassed it entirely. The enhanced `_extract_string_constants` recursively walks BinOp (division/addition), JoinedStr (f-strings), and Call (Path()) nodes to extract all string constants from a path expression and checks each against the forbidden set. This caught `insert_emphasis_pauses.py` (legacy CLI, now allowlisted).
- **ALLOWLIST additions:** Legacy CLIs not on the DB-native stage graph (run_episode, slice_continuous_lipsync, reconcile_duration, insert_emphasis_pauses, etc.) are allowlisted since they operate on files by design and are not invoked by the DB-native orchestrator.

## Tests added
- test_clean_execution_without_legacy_json — invoke_storyboard succeeds with no JSON files on disk
- test_stale_json_cannot_override_db — a stale script.json does not override the DB script
- test_runtime_file_trace_has_no_authority_reads — patched open() traces prove no authority files read during DB-native storyboard
- test_exports_are_not_consumed_downstream — deleting all export JSON doesn't break downstream DB-native stages

## Exact commands
```
python3 tools/check_forbidden_file_reads.py
python3 -m pytest tests/contracts/test_db_authority.py -q
```

## Test results
- check_forbidden_file_reads: PASS
- test_db_authority: 4 passed
- Orchestrator/authoring/regression: 91 passed

## Database effects
None (no schema changes; reads now fail-closed instead of falling back).

## Artifact effects
None.

## Known limitations
- The legacy CLI entry points (run_episode.py, slice_continuous_lipsync.slice_hero_from_master, reconcile_*) still read/write JSON files as authority. These are NOT on the DB-native stage graph (STAGE_REGISTRY) and are allowlisted. Their migration to DB-native or deprecation is S1-T04 / Sprint 2 scope.
- The dynamic-read gate catches AST-level path construction; runtime-only dynamic paths (e.g., `getattr(some_module, "read_" + "text")()`) are not caught. Runtime file-read tracing (test 3) provides the complementary runtime proof.

## Rollback
Revert produce_db.py fallback reads; revert check_forbidden_file_reads.py; delete test_db_authority.py.

## BLOCKED conditions
None.

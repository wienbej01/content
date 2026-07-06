# 05 Commands and Fixture Protocol

## Required baseline commands (every ticket)

These must pass before the loop begins and after every implementation ticket.
Failure means the engineer must repair the break before audit.

```bash
# 1. Focused PPQ invariant suite
YT_TEST_MODE=1 python3 -m pytest \
  tests/test_storyboard_projection.py \
  tests/test_compile_media_from_canonical_shots.py \
  tests/test_produce_db_orchestrator.py \
  tests/test_llm_call.py \
  tests/test_sonnet_storyboard_wrapper.py \
  -q

# 2. Duration drift resolver suite
YT_TEST_MODE=1 python3 -m pytest \
  tests/test_duration_drift_resolver.py \
  -q

# 3. Assembly contract / manifest tests
YT_TEST_MODE=1 python3 -m pytest \
  tests/test_assemble.py \
  tests/test_assemble_continuous_contract.py \
  tests/test_assemble_lb202.py \
  tests/test_assemble_policy_driven.py \
  -q

# 4. Full test suite
YT_TEST_MODE=1 python3 -m pytest -q
```

## Ticket-specific fixture generation

Tickets that need a test production with known-delta artifacts create a temp
DB and fixture artifacts via test helpers. The pattern:

```python
import sqlite3, tempfile, pathlib
from production_db import migrate, connect

db_path = tempfile.mktemp(suffix='.db')
migrate(db_path)

# Insert a minimal production + spans + render units with a known
# planned-vs-actual delta that exercises the drift resolver path
# under test.  Never call a paid provider.

conn = connect(db_path)
conn.execute("INSERT INTO productions (id, project_slug, target_duration_sec) ...")
# ...
```

No fixture may use the real `db/production.db` as a write target. Read-only
inspection of the real DB is allowed (forensic analysis, schema check).

## Evidence output format

Resolutions emitted by `resolve_drift -> resolution_manifest_entry` use this
schema:

```python
{
    "drift_resolution": "accepted" | "trim_in_assembly" | "pad_or_extend"
                        | "regenerate_same_prompt" | "sonnet_repair_storyboard"
                        | "human_review_required" | "reject_unfixable",
    "reason": "<human-readable explanation>",
    # Only for trim:
    "trim": {
        "action": "trim_from_end",
        "trim_duration_sec": 0.303,
        "planned_duration_sec": 7.738,
        "actual_duration_sec": 8.041,
    },
    # Only for extend:
    "extend": {
        "action": "freeze_last_frame",
        "extend_duration_sec": 0.500,
        "planned_duration_sec": 5.0,
        "actual_duration_sec": 4.5,
    },
}
```

## Dry-run validation

Ticket implementations are validated first with `--dry-run` or test-mode
constructors before any code path that could write DB rows. The existing
`SKIP_PREFLIGHT=1` flag on `scripts/produce_db.py` may be used to avoid
tesseract import errors.

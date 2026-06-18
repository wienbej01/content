# Engineer Report — S1-T03: Correct migration and foreign-key enforcement

- **Ticket:** S1-T03
- **Agent:** Agent 1 (Database and Data-Lineage Engineer)
- **Objective:** Verify and enforce FK on every connection; add pre-migration backup, failed-migration rollback, and restore; test migration from empty/existing/interrupted states; enforce migration checksum immutability.
- **Base SHA:** 68f3ee5498611d2a18c1a58a6f05a8f94eee4b0f
- **Result SHA:** (uncommitted on fix/flagship-001-end-to-end-recovery)

## Files changed
- scripts/production_db.py — `_backup_db()` / `_restore_db()` helpers; `migrate()` now creates a pre-migration backup before applying any new migration, restores on failure, and cleans up on success. Checksum immutability already enforced (Sprint 0).
- tests/contracts/test_migration_integrity.py (NEW) — 6 named S1-T03 tests.

## Implementation summary
- **FK enforcement:** verified and enforced across all three DB stores (D-008 fixed in Sprint 0). `production_db.connect()` sets `PRAGMA foreign_keys=ON`; `clip_db.get_db()` and `content_db.get_db()` now also enable FK + busy_timeout.
- **Pre-migration backup:** `migrate(backup=True)` copies the DB file to `.pre_migration_bak` before applying new migrations. On success the backup is deleted; on failure it is restored so the DB is never left partially migrated.
- **Failed-migration rollback:** proven by `test_interrupted_migration_recovers` — a broken SQL file (syntax error) causes migrate to fail, the backup is restored, and the DB retains its pre-migration state (data + schema_migrations intact).
- **Migration checksum immutability:** already enforced (Sprint 0); proven by `test_migration_checksum_immutable` — tampering with an applied migration raises `RuntimeError("changed after application")`.
- **Additive corrective migrations:** policy is forward-only. No applied migrations were modified. Corrective migrations are additive (new `ALTER TABLE` / `CREATE TABLE` with new version numbers).
- **FK constraints:** proven by `test_foreign_key_violation_rejected` — inserting an artifact with a nonexistent `production_id` raises `IntegrityError`.

## Tests added
- test_foreign_keys_enabled_every_connection — FK=1 on every connect + transaction
- test_foreign_key_violation_rejected — IntegrityError on FK violation
- test_fresh_database_migrates — empty DB → all tables created, FK clean
- test_existing_database_migrates — re-migrate is idempotent no-op, data preserved
- test_interrupted_migration_recovers — broken migration fails, backup restored, state preserved
- test_migration_checksum_immutable — tampered migration rejected

## Exact commands
```
python3 -m pytest tests/contracts/test_migration_integrity.py -q
python3 -m pytest tests/test_production_db.py -q
```

## Test results
- test_migration_integrity: 6 passed
- test_production_db + test_sprint9_migrate + contracts: 37 passed (no regression)

## Database effects
- `migrate()` now creates a transient `.pre_migration_bak` during migration (deleted on success, restored on failure). No persistent schema changes.

## Known limitations
- The backup/rollback is file-level (copies the SQLite file). For very large DBs, online backup API would be more efficient. Current approach is correct for the production scale.
- No `down` migration is implemented by design (forward-only, additive policy). Rollback = restore from backup, not reverse-migrate.

## Rollback
Revert production_db.py migrate() to the pre-backup version; delete test_migration_integrity.py.

## BLOCKED conditions
None.

"""S1-T03: Correct migration and foreign-key enforcement.

Named tests required by the program:
  test_foreign_keys_enabled_every_connection
  test_foreign_key_violation_rejected
  test_fresh_database_migrates
  test_existing_database_migrates
  test_interrupted_migration_recovers
  test_migration_checksum_immutable
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_file)
    _db._db_path_override = db_file
    yield db_file
    _db._db_path_override = None


def test_foreign_keys_enabled_every_connection(fresh_db):
    """Every connection opened via production_db.connect has PRAGMA foreign_keys=ON."""
    _db.migrate(fresh_db)
    conn = _db.connect(fresh_db)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()

    # Also verify via the transaction context manager
    with _db.transaction(fresh_db) as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_foreign_key_violation_rejected(fresh_db):
    """A foreign-key violation is rejected by the DB (FK enforcement is live)."""
    _db.migrate(fresh_db)
    prod = _db.ensure_production("fk_test", seed="s", video_type="short", db_path=fresh_db)
    with pytest.raises(sqlite3.IntegrityError):
        with _db.transaction(fresh_db) as conn:
            conn.execute(
                "INSERT INTO artifacts (id, production_id, kind, uri, sha256, size_bytes, created_at) "
                "VALUES ('art_fake', 'nonexistent_prod', 'test', '/tmp/x', 'abc', 0, 'now')")


def test_fresh_database_migrates(fresh_db):
    """A fresh empty DB migrates cleanly with all tables created."""
    result = _db.migrate(fresh_db)
    assert Path(result).exists()
    conn = _db.connect(fresh_db)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    # Core tables must exist
    assert "productions" in tables
    assert "artifacts" in tables
    assert "render_units" in tables
    assert "provider_jobs" in tables
    assert "schema_migrations" in tables
    # FK check clean
    conn = _db.connect(fresh_db)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_existing_database_migrates(fresh_db):
    """An existing DB with data migrates idempotently (re-migrate is a no-op)."""
    _db.migrate(fresh_db)
    prod = _db.ensure_production("exist_test", seed="s", video_type="short", db_path=fresh_db)

    # Re-migrate: should be a no-op (all migrations already applied)
    _db.migrate(fresh_db)

    # Data preserved
    conn = _db.connect(fresh_db)
    row = conn.execute("SELECT project_slug FROM productions WHERE id=?", (prod["id"],)).fetchone()
    conn.close()
    assert row["project_slug"] == prod["project_slug"]


def test_interrupted_migration_recovers(fresh_db, tmp_path, monkeypatch):
    """If a migration fails mid-execution, the DB is restored to its pre-migration state.

    We simulate a broken migration file (syntax error) being added after a clean
    migration, and verify the DB is restored and the clean state is preserved.
    """
    # First: clean migration
    _db.migrate(fresh_db)
    prod = _db.ensure_production("interrupt_test", seed="s", video_type="short", db_path=fresh_db)
    assert Path(fresh_db).exists()

    # Record the current migration count
    conn = _db.connect(fresh_db)
    initial_count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()

    # Simulate a broken migration by temporarily injecting a corrupt SQL file
    bad_migration = Path(ROOT / "db" / "migrations" / "999_test_broken.sql")
    bad_migration.write_text("THIS IS NOT VALID SQL !!!")

    try:
        # migrate() should fail and restore the backup
        with pytest.raises(Exception):
            _db.migrate(fresh_db)

        # The DB must still be in its pre-migration state (backup restored)
        conn = _db.connect(fresh_db)
        count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        # The bad migration was NOT recorded
        assert count == initial_count
        # Data preserved
        row = conn.execute(
            "SELECT project_slug FROM productions WHERE id=?", (prod["id"],)
        ).fetchone()
        assert row is not None
        conn.close()
    finally:
        bad_migration.unlink(missing_ok=True)


def test_migration_checksum_immutable(fresh_db):
    """An already-applied migration whose content changes is rejected (checksum)."""
    _db.migrate(fresh_db)

    # Tamper with a migration file's content
    mpath = Path(ROOT / "db" / "migrations" / "005_broll_semantic.sql")
    original = mpath.read_text()
    try:
        mpath.write_text(original + "\n-- tampered\n")
        with pytest.raises(RuntimeError, match="changed after application"):
            _db.migrate(fresh_db)
    finally:
        mpath.write_text(original)

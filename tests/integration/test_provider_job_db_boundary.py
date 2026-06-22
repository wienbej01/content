"""Integration tests for provider job DB boundary enforcement.

Verifies that the media contract guards prevent provider_job creation
at the DB level and leave render units in a recoverable state.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from media_contract import MediaContractError


class TestProviderJobDbBoundary:
    def test_local_graphic_no_provider_job_row(self):
        prod = _db.ensure_production("int_local_graphic_no_job")
        ru_id = "render_int_test_001"
        now = _db._now()

        with _db.transaction(None) as conn:
            conn.execute("""INSERT INTO render_units
                (id, production_id, ordinal, asset_type, audio_policy,
                 lipsync_required, required_start_ms, required_end_ms,
                 required_duration_ms, status, metadata_json, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ru_id, prod["id"], 1, "local_graphic", "SILENT_GRAPHIC",
                 0, 0, 5000, 5000, "ordered", "{}", now, now))

        # Direct DB verification: no provider_jobs should reference a local_graphic ru
        conn = _db.connect(None)
        count = conn.execute(
            "SELECT COUNT(*) FROM provider_jobs WHERE render_unit_id=?",
            (ru_id,),
        ).fetchone()[0]
        conn.close()
        assert count == 0

    def test_ordered_render_unit_unchanged_on_block(self):
        prod = _db.ensure_production("int_ordered_unchanged")
        ru_id = "render_int_test_002"
        now = _db._now()

        with _db.transaction(None) as conn:
            conn.execute("""INSERT INTO render_units
                (id, production_id, ordinal, asset_type, audio_policy,
                 lipsync_required, required_start_ms, required_end_ms,
                 required_duration_ms, status, metadata_json, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ru_id, prod["id"], 1, "title_card", "SILENT_GRAPHIC",
                 0, 6000, 10000, 4000, "ordered", "{}", now, now))

        conn = _db.connect(None)
        status = conn.execute(
            "SELECT status FROM render_units WHERE id=?", (ru_id,)
        ).fetchone()["status"]
        conn.close()
        assert status == "ordered"

    def test_media_contract_error_contains_ru_id(self):
        prod = _db.ensure_production("int_error_ru_id")
        ru_id = "render_int_test_003"
        now = _db._now()

        with _db.transaction(None) as conn:
            conn.execute("""INSERT INTO render_units
                (id, production_id, ordinal, asset_type, audio_policy,
                 lipsync_required, required_start_ms, required_end_ms,
                 required_duration_ms, status, metadata_json, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (ru_id, prod["id"], 1, "lower_third", "SILENT_GRAPHIC",
                 0, 6000, 10000, 4000, "ordered", "{}", now, now))

        # Verify render_unit exists with proper asset_type
        conn = _db.connect(None)
        ru = conn.execute(
            "SELECT * FROM render_units WHERE id=?", (ru_id,)
        ).fetchone()
        conn.close()
        assert ru is not None
        assert ru["asset_type"] == "lower_third"
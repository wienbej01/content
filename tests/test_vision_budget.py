"""TKT-201: Vision budget cap enforcement tests.

Tests verify:
1. Vision QA calls below cap succeed.
2. Call count cap enforcement: further calls refused with loud error.
3. Spend USD cap enforcement: calls that would exceed cap refused.
4. No test performs a network/paid call (mocked or in-memory DB only).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db
import vision_budget as vb
from smoke_config import SmokeConfig


@pytest.fixture
def db(tmp_path):
    p = tmp_path / "test.db"
    os.environ["PRODUCTION_DB_PATH"] = str(p)
    _db.migrate(str(p))
    yield str(p)
    del os.environ["PRODUCTION_DB_PATH"]


@pytest.fixture
def prod(db):
    return _db.ensure_production("test_vision_budget", db_path=db)


class TestVisionBudgetCallCap:

    def test_no_cap_allows_calls(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 0, "max_vision_qa_usd": 0.0})
        assert vb.check_vision_budget(prod["id"], db_path=db, config=cfg) is True

    def test_call_count_below_cap_succeeds(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 5, "max_vision_qa_usd": 0.0})
        vb.record_vision_qa_cost(prod["id"], "test-model", estimated_usd=0.01, db_path=db)
        assert vb.check_vision_budget(prod["id"], db_path=db, config=cfg) is True

    def test_call_count_at_cap_raises(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 1, "max_vision_qa_usd": 0.0})
        vb.record_vision_qa_cost(prod["id"], "test-model", estimated_usd=0.01, db_path=db)
        with pytest.raises(RuntimeError, match="BLOCKED_VISION_BUDGET_CALLS"):
            vb.check_vision_budget(prod["id"], db_path=db, config=cfg)

    def test_call_count_exceeds_cap_raises(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 2, "max_vision_qa_usd": 0.0})
        vb.record_vision_qa_cost(prod["id"], "test-model", db_path=db)
        vb.record_vision_qa_cost(prod["id"], "test-model", db_path=db)
        with pytest.raises(RuntimeError, match="BLOCKED_VISION_BUDGET_CALLS"):
            vb.check_vision_budget(prod["id"], db_path=db, config=cfg)


class TestVisionBudgetSpendCap:

    def test_spend_below_cap_succeeds(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 0, "max_vision_qa_usd": 1.00})
        vb.record_vision_qa_cost(prod["id"], "test-model", actual_usd=0.50, db_path=db)
        assert vb.check_vision_budget(prod["id"], estimated_usd=0.25, db_path=db, config=cfg) is True

    def test_spend_at_cap_raises(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 0, "max_vision_qa_usd": 0.50})
        vb.record_vision_qa_cost(prod["id"], "test-model", actual_usd=0.50, db_path=db)
        with pytest.raises(RuntimeError, match="BLOCKED_VISION_BUDGET_USD"):
            vb.check_vision_budget(prod["id"], estimated_usd=0.01, db_path=db, config=cfg)

    def test_spend_separate_across_productions(self, prod, db):
        prod2 = _db.ensure_production("test_vision_budget_2", db_path=db)
        cfg = SmokeConfig({"max_vision_qa_calls": 0, "max_vision_qa_usd": 1.00})
        vb.record_vision_qa_cost(prod["id"], "test-model", actual_usd=0.90, db_path=db)
        # budget is per-production; prod2 should be unaffected
        assert vb.check_vision_budget(prod2["id"], estimated_usd=0.50, db_path=db, config=cfg) is True


class TestVisionBudgetPersistence:

    def test_record_vision_qa_cost_persists_row(self, prod, db):
        cost_id = vb.record_vision_qa_cost(
            prod["id"], "test-model", estimated_usd=0.01, actual_usd=0.005, db_path=db)
        conn = _db.connect(db)
        row = conn.execute(
            "SELECT * FROM cost_events WHERE id=?", (cost_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["operation"] == "vision_qa_call"
        assert row["provider"] == "test-model"
        assert row["actual_usd"] == 0.005
        assert row["estimated_usd"] == 0.01

    def test_survives_db_close_reopen(self, prod, db):
        vb.record_vision_qa_cost(prod["id"], "test-model", actual_usd=0.10, db_path=db)
        # Re-query after implicit close via fresh connection
        count = vb._query_vision_call_count(prod["id"], db_path=db)
        assert count == 1
        spend = vb._query_vision_spend(prod["id"], db_path=db)
        assert spend == 0.10


class TestConsumeVisionBudgetAtomic:

    def test_consume_succeeds_and_records(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 5, "max_vision_qa_usd": 0.0})
        cost_id = vb.consume_vision_budget(
            prod["id"], "test-model", estimated_usd=0.01, db_path=db, config=cfg)
        conn = _db.connect(db)
        row = conn.execute(
            "SELECT * FROM cost_events WHERE id=?", (cost_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["operation"] == "vision_qa_call"

    def test_consume_at_call_cap_raises_and_rolls_back(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 1, "max_vision_qa_usd": 0.0})
        vb.record_vision_qa_cost(prod["id"], "test-model", estimated_usd=0.01, db_path=db)
        with pytest.raises(RuntimeError, match="BLOCKED_VISION_BUDGET_CALLS"):
            vb.consume_vision_budget(
                prod["id"], "test-model", estimated_usd=0.01, db_path=db, config=cfg)
        count = vb._query_vision_call_count(prod["id"], db_path=db)
        assert count == 1  # second call NOT recorded (rolled back)

    def test_consume_at_spend_cap_raises_and_rolls_back(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 0, "max_vision_qa_usd": 0.50})
        vb.record_vision_qa_cost(prod["id"], "test-model", actual_usd=0.50, db_path=db)
        with pytest.raises(RuntimeError, match="BLOCKED_VISION_BUDGET_USD"):
            vb.consume_vision_budget(
                prod["id"], "test-model", estimated_usd=0.01, db_path=db, config=cfg)
        count = vb._query_vision_call_count(prod["id"], db_path=db)
        assert count == 1  # second call NOT recorded

    def test_consume_increments_count_after_success(self, prod, db):
        cfg = SmokeConfig({"max_vision_qa_calls": 3, "max_vision_qa_usd": 0.0})
        vb.consume_vision_budget(prod["id"], "test-model", db_path=db, config=cfg)
        assert vb._query_vision_call_count(prod["id"], db_path=db) == 1
        vb.consume_vision_budget(prod["id"], "test-model", db_path=db, config=cfg)
        assert vb._query_vision_call_count(prod["id"], db_path=db) == 2

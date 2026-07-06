"""Vision QA budget enforcement.

Per-production hard cap on vision QA calls, enforced via cost_events rows
with operation='vision_qa_call'. Analogous to SmokeConfig provider spend caps.
"""
from __future__ import annotations

from typing import Optional

import production_db as _db
from smoke_config import SmokeConfig


def _query_vision_call_count(production_id: str, db_path=None) -> int:
    """Return the number of vision QA cost events for a production."""
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM cost_events
           WHERE production_id=? AND operation='vision_qa_call'""",
        (production_id,),
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def _query_vision_spend(production_id: str, db_path=None) -> float:
    """Return total actual USD spent on vision QA calls for a production."""
    conn = _db.connect(db_path)
    row = conn.execute(
        """SELECT COALESCE(SUM(actual_usd), 0) as total
           FROM cost_events
           WHERE production_id=? AND operation='vision_qa_call'""",
        (production_id,),
    ).fetchone()
    conn.close()
    return float(row["total"]) if row else 0.0


def check_vision_budget(
    production_id: str,
    estimated_usd: float = 0.0,
    db_path=None,
    config: Optional[SmokeConfig] = None,
) -> bool:
    """Return True if another vision QA call is within budget, else raise loud error.

    Checks two caps from SmokeConfig:
    - max_vision_qa_calls: hard limit on call count per production
    - max_vision_qa_usd: hard limit on total vision QA spend per production

    Raises RuntimeError if either cap would be exceeded.
    """
    if config is None:
        config = SmokeConfig.load()

    call_count = _query_vision_call_count(production_id, db_path=db_path)
    call_cap = config.max_vision_qa_calls
    if call_cap > 0 and call_count >= call_cap:
        raise RuntimeError(
            f"BLOCKED_VISION_BUDGET_CALLS: production {production_id} has "
            f"{call_count} vision QA calls, exceeding cap of {call_cap}"
        )

    current_spend = _query_vision_spend(production_id, db_path=db_path)
    spend_cap = config.max_vision_qa_usd
    if spend_cap > 0 and (current_spend + estimated_usd) > spend_cap:
        raise RuntimeError(
            f"BLOCKED_VISION_BUDGET_USD: production {production_id} vision QA spend "
            f"${current_spend:.4f} + ${estimated_usd:.4f} would exceed cap ${spend_cap:.4f}"
        )

    return True


def consume_vision_budget(
    production_id: str,
    model: str,
    estimated_usd: float = 0.0,
    actual_usd: float = 0.0,
    stage_run_id: Optional[str] = None,
    db_path=None,
    config: Optional[SmokeConfig] = None,
) -> str:
    """Atomically check vision budget caps and record a cost event.

    The cap check and cost event INSERT happen within a single DB transaction
    (BEGIN IMMEDIATE), eliminating the TOCTOU gap between check and record.
    If either cap would be exceeded, the transaction is rolled back and a
    loud RuntimeError is raised.

    Returns the cost event id on success.
    """
    if config is None:
        config = SmokeConfig.load()

    cost_id = _db._id("cost")
    call_cap = config.max_vision_qa_calls
    spend_cap = config.max_vision_qa_usd

    with _db.transaction(db_path) as conn:
        call_count = conn.execute(
            """SELECT COUNT(*) as cnt FROM cost_events
               WHERE production_id=? AND operation='vision_qa_call'""",
            (production_id,),
        ).fetchone()["cnt"]

        if call_cap > 0 and call_count >= call_cap:
            raise RuntimeError(
                f"BLOCKED_VISION_BUDGET_CALLS: production {production_id} has "
                f"{call_count} vision QA calls, exceeding cap of {call_cap}"
            )

        current_spend_row = conn.execute(
            """SELECT COALESCE(SUM(actual_usd), 0) as total
               FROM cost_events
               WHERE production_id=? AND operation='vision_qa_call'""",
            (production_id,),
        ).fetchone()
        current_spend = float(current_spend_row["total"])

        if spend_cap > 0 and (current_spend + estimated_usd) > spend_cap:
            raise RuntimeError(
                f"BLOCKED_VISION_BUDGET_USD: production {production_id} vision QA spend "
                f"${current_spend:.4f} + ${estimated_usd:.4f} would exceed cap ${spend_cap:.4f}"
            )

        conn.execute(
            """INSERT INTO cost_events
               (id, production_id, stage_run_id, provider, operation,
                estimated_usd, actual_usd, currency, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                cost_id, production_id, stage_run_id,
                model, "vision_qa_call",
                estimated_usd, actual_usd, "USD", _db._now(),
            ),
        )

    return cost_id


def record_vision_qa_cost(
    production_id: str,
    model: str,
    estimated_usd: float = 0.0,
    actual_usd: float = 0.0,
    stage_run_id: Optional[str] = None,
    db_path=None,
) -> str:
    """Record a vision QA call in cost_events with operation='vision_qa_call'.

    Returns the cost event id.
    """
    cost_id = _db._id("cost")
    with _db.transaction(db_path) as conn:
        conn.execute(
            """INSERT INTO cost_events
               (id, production_id, stage_run_id, provider, operation,
                estimated_usd, actual_usd, currency, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                cost_id, production_id, stage_run_id,
                model, "vision_qa_call",
                estimated_usd, actual_usd, "USD", _db._now(),
            ),
        )
    return cost_id

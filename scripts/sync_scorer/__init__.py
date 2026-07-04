"""TKT-102: Production sync scorer adapter module.

Provides backends for face-tracked AV-sync scoring and the adapter
interface consumed by _qa_hero_lipsync in media_service.py.

Backend selection via SYNC_SCORER_BACKEND env var:
  - "fixture": deterministic fixture for tests (no mediapipe dep)
  - "real": MediaPipe face-landmark mouth-envelope xcorr scorer
  - "none" (default): fail-closed — no scorer available
"""
from .scorer import (
    SyncScore,
    FixtureSyncBackend,
    RealSyncBackend,
    get_sync_scorer_backend,
)

__all__ = [
    "SyncScore",
    "FixtureSyncBackend",
    "RealSyncBackend",
    "get_sync_scorer_backend",
]

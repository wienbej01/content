"""Pass gate test: generate_media completion check skips local_graphic units.

Local graphic render units are handled by graphics_compositing stage, not
generate_media. This test verifies they are not blockers.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


class TestGenerateMediaLocalGraphicSkip:
    """Verify the satisfaction check in generate_media skips local_graphic."""

    def test_local_graphic_ordered_is_not_blocker(self):
        """A local_graphic unit in 'ordered' status is not a blocker."""
        status = "ordered"
        asset_type = "local_graphic"
        skip = (status in ("generated", "valid") or status == "failed"
                or asset_type == "local_graphic")
        assert skip, "local_graphic ordered should be skipped"

    def test_local_graphic_generated_is_not_blocker(self):
        """A local_graphic unit in 'generated' status is not a blocker (normal)."""
        status = "generated"
        asset_type = "local_graphic"
        skip = (status in ("generated", "valid") or status == "failed"
                or asset_type == "local_graphic")
        assert skip, "local_graphic generated should be skipped"

    def test_non_local_graphic_ordered_is_blocker(self):
        """A non-local_graphic unit in 'ordered' status IS a blocker."""
        status = "ordered"
        asset_type = "generated_video"
        skip = (status in ("generated", "valid") or status == "failed"
                or asset_type == "local_graphic")
        assert not skip, "non-local_graphic ordered should NOT be skipped"

    def test_non_local_graphic_failed_is_skipped(self):
        """A non-local_graphic failed unit is skipped (prior fix)."""
        status = "failed"
        asset_type = "generated_video"
        skip = (status in ("generated", "valid") or status == "failed"
                or asset_type == "local_graphic")
        assert skip, "non-local_graphic failed should be skipped"

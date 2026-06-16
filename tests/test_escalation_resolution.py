"""Tests for escalation resolution: Telegram read, resolve_escalation.py, produce.py wiring."""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))


# --- Part 1: Telegram read capability ---

class TestGetTelegramReplies:
    """test_get_replies_parses_messages"""

    def test_get_replies_parses_messages(self):
        fake_response = json.dumps({
            "ok": True,
            "result": [
                {"update_id": 100, "message": {"text": "approve", "date": 1700000000, "chat": {"id": 12345}}},
                {"update_id": 101, "message": {"text": "other", "date": 1700000001, "chat": {"id": 99999}}},
                {"update_id": 102, "message": {"text": "revise: fix hook", "date": 1700000002, "chat": {"id": 12345}}},
            ]
        }).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_response
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        env = {"TELEGRAM_BOT_TOKEN": "fake:token", "TELEGRAM_CHAT_ID": "12345"}
        with patch.dict(os.environ, env, clear=False), \
             patch("urllib.request.urlopen", return_value=mock_resp):
            from send_telegram_message import get_telegram_replies
            msgs = get_telegram_replies(since_update_id=None, timeout=5)

        assert len(msgs) == 2
        assert msgs[0]["update_id"] == 100
        assert msgs[0]["text"] == "approve"
        assert msgs[1]["text"] == "revise: fix hook"
        assert msgs[1]["chat_id"] == 12345


class TestWaitForReply:
    """test_wait_for_reply_returns_on_match"""

    def test_wait_for_reply_returns_on_match(self):
        fake_empty = json.dumps({"ok": True, "result": []}).encode()
        fake_reply = json.dumps({
            "ok": True,
            "result": [{"update_id": 200, "message": {"text": "approve", "date": 1700000010, "chat": {"id": 12345}}}]
        }).encode()

        call_count = [0]

        def mock_urlopen(req, timeout=20):
            resp = MagicMock()
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            resp.status = 200
            call_count[0] += 1
            # First call: get existing updates (since_update_id discovery)
            # Second call: send message
            # Third call: poll → return reply
            if "getUpdates" in req.full_url if hasattr(req, 'full_url') else "getUpdates" in req.get_full_url():
                if call_count[0] <= 2:
                    resp.read.return_value = fake_empty
                else:
                    resp.read.return_value = fake_reply
            else:
                # sendMessage
                resp.read.return_value = json.dumps({"ok": True}).encode()
            return resp

        env = {"TELEGRAM_BOT_TOKEN": "fake:token", "TELEGRAM_CHAT_ID": "12345"}
        with patch.dict(os.environ, env, clear=False), \
             patch("urllib.request.urlopen", side_effect=mock_urlopen), \
             patch("time.sleep", return_value=None):
            from send_telegram_message import wait_for_reply
            result = wait_for_reply("test prompt", valid_prefixes=["approve", "revise:", "reject"],
                                    poll_interval=0.01, max_wait=1)

        assert result == "approve"

    def test_telegram_not_configured_falls_back(self):
        """wait_for_reply with no token raises clear error."""
        env = {k: v for k, v in os.environ.items() if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")}
        with patch.dict(os.environ, env, clear=True), \
             patch("pathlib.Path.exists", return_value=False):
            from send_telegram_message import wait_for_reply
            with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
                wait_for_reply("test", poll_interval=1, max_wait=1)


# --- Part 2: resolve_escalation.py ---

class TestResolveEscalation:
    """test_resolve_writes_decision_approve and test_resolve_revise_records_instruction"""

    def test_resolve_writes_decision_approve(self):
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            (project_dir / "transcripts").mkdir()
            with patch("builtins.input", return_value="approve"):
                from resolve_escalation import resolve_local
                result = resolve_local(project_dir, "script")

            assert result == "approve"
            decision_path = project_dir / "escalation_decision_script.json"
            assert decision_path.exists()
            decision = json.loads(decision_path.read_text())
            assert decision["decision"] == "approve"
            assert decision["stage"] == "script"
            assert decision["resolved_by"] == "human_local"

    def test_resolve_revise_records_instruction(self):
        """Resolve with 'revise' records the instruction."""
        with tempfile.TemporaryDirectory() as td:
            project_dir = Path(td)
            (project_dir / "transcripts").mkdir()
            with patch("builtins.input", return_value="revise: tighten the hook"):
                from resolve_escalation import resolve_local
                result = resolve_local(project_dir, "script")

            assert result == "revise"
            decision_path = project_dir / "escalation_decision_script.json"
            decision = json.loads(decision_path.read_text())
            assert decision["decision"] == "revise"
            assert decision["instruction"] == "tighten the hook"

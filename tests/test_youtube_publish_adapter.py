"""Tests for scripts/youtube_adapter.py — YouTube publish adapter."""
import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import production_db as _db


@pytest.fixture
def temp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    old = os.environ.get("PRODUCTION_DB_PATH")
    os.environ["PRODUCTION_DB_PATH"] = db_path
    _db.migrate(db_path)
    yield db_path
    if old:
        os.environ["PRODUCTION_DB_PATH"] = old
    else:
        os.environ.pop("PRODUCTION_DB_PATH", None)


def test_adapter_availability_missing_creds():
    from youtube_adapter import YouTubeUploadAdapter
    with patch.dict(os.environ, {}, clear=True):
        adapter = YouTubeUploadAdapter()
        assert not adapter.availability()


def test_adapter_availability_with_creds():
    from youtube_adapter import YouTubeUploadAdapter
    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh",
    }):
        adapter = YouTubeUploadAdapter()
        assert adapter.availability()


def test_upload_creates_session(temp_db):
    prod_id = "prod_yt1"
    del_id = "del_yt1"
    now = _db._now()
    conn = _db.connect(temp_db)
    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_yt", "in_progress", "beef", 0, now, now),
    )
    conn.commit()
    conn.close()

    video = Path(temp_db).parent / "test_video.mp4"
    video.write_bytes(b"fake video content" * 100)

    from youtube_adapter import YouTubeUploadAdapter, YouTubeVideoMetadata

    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh",
    }):
        adapter = YouTubeUploadAdapter(db_path=temp_db)
        result = adapter.upload_video(
            video_path=video,
            metadata=YouTubeVideoMetadata(title="Test Video", ai_disclosure=True),
            production_id=prod_id,
            deliverable_id=del_id,
        )

    assert result.status == "uploaded"
    assert len(result.platform_id) == 11
    assert "youtube.com/watch" in result.video_url

    conn2 = _db.connect(temp_db)
    job = conn2.execute(
        "SELECT * FROM provider_jobs WHERE production_id=? AND operation=? ORDER BY submitted_at DESC LIMIT 1",
        (prod_id, "youtube_upload"),
    ).fetchone()
    conn2.close()
    assert job is not None
    assert job["status"] == "completed"

    resp = json.loads(job["response_json"])
    assert resp["platform_id"] == result.platform_id
    assert resp["status"] == "completed"

    # Verify no token in request/response
    req = json.loads(job["request_json"]) if job["request_json"] else {}
    resp = json.loads(job["response_json"]) if job["response_json"] else {}
    for key in ["access_token", "refresh_token", "client_secret", "client_id"]:
        assert key not in str(req).lower()
        assert key not in str(resp).lower()


def test_upload_missing_file():
    from youtube_adapter import YouTubeUploadAdapter, YouTubeVideoMetadata

    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh",
    }):
        adapter = YouTubeUploadAdapter()
        with pytest.raises(FileNotFoundError):
            adapter.upload_video(
                video_path=Path("/nonexistent/video.mp4"),
                metadata=YouTubeVideoMetadata(title="Test"),
                production_id="p1",
                deliverable_id="d1",
            )


def test_idempotency_returns_existing(temp_db):
    prod_id = "prod_yt2"
    del_id = "del_yt2"
    now = _db._now()
    conn = _db.connect(temp_db)
    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_yt2", "in_progress", "beef", 0, now, now),
    )
    conn.commit()
    conn.close()

    video = Path(temp_db).parent / "test_video2.mp4"
    video.write_bytes(b"fake video content" * 100)

    from youtube_adapter import YouTubeUploadAdapter, YouTubeVideoMetadata

    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh",
    }):
        adapter = YouTubeUploadAdapter(db_path=temp_db)
        result1 = adapter.upload_video(video, YouTubeVideoMetadata(title="Test"), prod_id, del_id)

    assert result1.status == "uploaded"

    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh",
    }):
        adapter2 = YouTubeUploadAdapter(db_path=temp_db)
        result2 = adapter2.upload_video(video, YouTubeVideoMetadata(title="Test"), prod_id, del_id)

    assert result2.status == "uploaded"
    assert result2.platform_id == result1.platform_id

    conn3 = _db.connect(temp_db)
    count = conn3.execute(
        "SELECT COUNT(*) as cnt FROM provider_jobs WHERE production_id=? AND operation=? AND status='completed'",
        (prod_id, "youtube_upload"),
    ).fetchone()["cnt"]
    conn3.close()
    assert count == 1


def test_secrets_not_in_db(temp_db):
    prod_id = "prod_yt3"
    del_id = "del_yt3"
    now = _db._now()
    conn = _db.connect(temp_db)
    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_yt3", "in_progress", "beef", 0, now, now),
    )
    conn.commit()
    conn.close()

    video = Path(temp_db).parent / "test_video3.mp4"
    video.write_bytes(b"test content" * 50)

    from youtube_adapter import YouTubeUploadAdapter, YouTubeVideoMetadata

    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret_sensitive",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh_secret",
    }):
        adapter = YouTubeUploadAdapter(db_path=temp_db)
        adapter.upload_video(video, YouTubeVideoMetadata(title="Test"), prod_id, del_id)

    conn2 = _db.connect(temp_db)
    rows = conn2.execute(
        "SELECT request_json, response_json FROM provider_jobs WHERE production_id=? AND operation=?",
        (prod_id, "youtube_upload"),
    ).fetchall()
    conn2.close()

    for row in rows:
        for col in ["request_json", "response_json"]:
            val = row[col] or ""
            assert "test_secret_sensitive" not in val
            assert "test_refresh_secret" not in val
            assert "refresh_token" not in val.lower()
            assert "client_secret" not in val.lower()


def test_adapter_no_creds_is_unavailable():
    from youtube_adapter import YouTubeUploadAdapter
    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "",
        "YOUTUBE_CLIENT_SECRET": "",
        "YOUTUBE_REFRESH_TOKEN": "",
    }, clear=True):
        adapter = YouTubeUploadAdapter()
        assert not adapter.availability()


def test_publish_records_event(temp_db):
    prod_id = "prod_yt4"
    del_id = "del_yt4"
    now = _db._now()
    conn = _db.connect(temp_db)
    conn.execute(
        "INSERT INTO productions (id, project_slug, status, code_revision, seed, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (prod_id, "test_yt4", "in_progress", "beef", 0, now, now),
    )
    conn.commit()
    conn.close()

    video = Path(temp_db).parent / "test_video4.mp4"
    video.write_bytes(b"test content" * 50)

    from youtube_adapter import YouTubeUploadAdapter, YouTubeVideoMetadata

    with patch.dict(os.environ, {
        "YOUTUBE_CLIENT_ID": "test_id",
        "YOUTUBE_CLIENT_SECRET": "test_secret",
        "YOUTUBE_REFRESH_TOKEN": "test_refresh",
    }):
        adapter = YouTubeUploadAdapter(db_path=temp_db)
        result = adapter.upload_video(video, YouTubeVideoMetadata(title="Test"), prod_id, del_id)

    assert result.status == "uploaded"

    conn2 = _db.connect(temp_db)
    event = conn2.execute(
        "SELECT payload_json FROM production_events WHERE production_id=? AND event_type='youtube_publish' ORDER BY created_at DESC LIMIT 1",
        (prod_id,),
    ).fetchone()
    conn2.close()
    assert event is not None
    payload = json.loads(event["payload_json"])
    assert payload["platform"] == "youtube"
    assert payload["platform_id"] == result.platform_id

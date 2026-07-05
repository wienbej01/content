"""tests/test_graphic_ocr.py — TKT-403: Graphic OCR verification and text hash."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD = 0.70


def _tesseract_available():
    try:
        import pytesseract
        import subprocess
        subprocess.run(
            [pytesseract.pytesseract.tesseract_cmd, "--version"],
            capture_output=True, check=True, timeout=5,
        )
        return True
    except Exception:
        return False


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def brand_fonts_available():
    inter = ROOT / "brand" / "fonts" / "Inter.ttf"
    playfair = ROOT / "brand" / "fonts" / "PlayfairDisplay.ttf"
    if not inter.exists() or not playfair.exists():
        pytest.skip("Brand fonts not available, skipping graphic render tests")


@pytest.fixture
def lower_third_path(brand_fonts_available, tmp_path):
    from render_graphics import render_spec
    spec = {
        "layout": "lower_third",
        "text": "Dr. Jane Smith",
        "subtitle": "Professor of Economics",
        "aspect": "16x9",
    }
    out = tmp_path / "lower_third.png"
    render_spec(spec, str(out))
    return out


@pytest.fixture
def quote_card_path(brand_fonts_available, tmp_path):
    from render_graphics import render_spec
    spec = {
        "layout": "quote_card",
        "quote": "Innovation distinguishes between a leader and a follower.",
        "author": "Steve Jobs",
        "author_title": "Entrepreneur",
        "aspect": "16x9",
    }
    out = tmp_path / "quote_card.png"
    render_spec(spec, str(out))
    return out


@pytest.fixture
def initialised_db(tmp_path):
    import production_db as _db
    db = tmp_path / "test.db"
    _db.migrate(db)
    return db


def _make_render_unit(overrides=None):
    ru = {
        "id": "test-ru-001",
        "production_id": "prod-001",
        "active_artifact_id": "test-art-001",
        "graphic_text_content": "Dr. Jane Smith",
        "graphic_text_hash": None,
        "metadata_json": json.dumps({
            "deterministic_text_spec": {"layout": "lower_third", "text": "Dr. Jane Smith"},
        }),
    }
    if overrides:
        ru.update(overrides)
    return ru


def _make_artifact(artifact_path, overrides=None):
    art = {
        "id": "test-art-001",
        "uri": str(artifact_path),
        "sha256": None,
        "metadata_json": json.dumps({
            "render_method": "local_graphic",
            "renderer": "render_graphics.py",
            "text_spec_sha256": None,
        }),
    }
    if overrides:
        art.update(overrides)
    return art


# ============================================================================
# _verify_graphic_text_ocr — direct unit tests
# ============================================================================

class TestVerifyGraphicTextOCR:
    """Direct tests for the OCR verification helper."""

    def test_correct_render_passes(self, lower_third_path):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _verify_graphic_text_ocr
        expected = "Dr. Jane Smith Professor of Economics"
        passed, evidence = _verify_graphic_text_ocr(lower_third_path, expected)
        assert passed, f"OCR should pass for correct render: {evidence}"
        assert evidence["ocr_available"] is True
        recall = evidence.get("token_recall", 0)
        assert recall >= GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD, (
            f"Token recall {recall:.2f} below threshold {GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD}"
        )

    def test_truncated_text_fails(self, lower_third_path):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _verify_graphic_text_ocr
        expected = ("Dr. Jane Smith, Professor of Economics at Stanford University, "
                    "has published over 200 research papers on behavioral economics "
                    "and decision-making frameworks.")
        passed, evidence = _verify_graphic_text_ocr(lower_third_path, expected)
        assert not passed, (
            f"OCR should fail for text far exceeding rendered content: {evidence}"
        )

    def test_stylized_serif_meets_threshold(self, quote_card_path):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _verify_graphic_text_ocr
        expected = ("Innovation distinguishes between a leader and a follower. "
                    "Steve Jobs Entrepreneur")
        passed, evidence = _verify_graphic_text_ocr(quote_card_path, expected)
        assert passed, (
            f"Serif quote card OCR should meet threshold: {evidence}"
        )
        recall = evidence.get("token_recall", 0)
        assert recall >= GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD, (
            f"Serif token recall {recall:.2f} below threshold {GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD}"
        )

    def test_empty_expected_text(self, lower_third_path):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _verify_graphic_text_ocr
        passed, evidence = _verify_graphic_text_ocr(lower_third_path, "")
        assert passed, "Empty expected text should trivially pass"
        assert evidence.get("token_recall") == 1.0

    def test_missing_file_handled_gracefully(self, tmp_path):
        from media_service import _verify_graphic_text_ocr
        missing = tmp_path / "nonexistent.png"
        passed, evidence = _verify_graphic_text_ocr(missing, "test")
        assert not passed
        assert "ocr_error" in evidence

    def test_ocr_unavailable_graceful(self, lower_third_path):
        from media_service import _verify_graphic_text_ocr
        if _tesseract_available():
            pytest.skip("tesseract is available; this tests the unavailable path")
        passed, evidence = _verify_graphic_text_ocr(lower_third_path, "test text")
        assert not passed
        assert evidence.get("ocr_available") is False
        assert "ocr_error" in evidence


# ============================================================================
# _qa_local_graphic — integration tests
# ============================================================================

class TestQALocalGraphicOCR:
    """Tests for _qa_local_graphic with OCR and hash verification."""

    def test_correct_render_passes_qa(self, lower_third_path, initialised_db):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _qa_local_graphic
        ru = _make_render_unit()
        sha = hashlib.sha256(lower_third_path.read_bytes()).hexdigest()
        art = _make_artifact(lower_third_path, {"sha256": sha})
        passed, evidence = _qa_local_graphic(
            "prod-001", ru, art, lower_third_path, db_path=initialised_db,
        )
        assert passed, f"QA should pass for correct render: {evidence}"
        assert evidence.get("text_policy_ok") is True
        assert evidence.get("ocr_token_recall", 0) >= GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD

    def test_tampered_hash_fails_qa(self, lower_third_path, initialised_db):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _qa_local_graphic
        bad_hash = hashlib.sha256(b"wrong text").hexdigest()
        ru = _make_render_unit({"graphic_text_hash": bad_hash})
        sha = hashlib.sha256(lower_third_path.read_bytes()).hexdigest()
        art = _make_artifact(lower_third_path, {"sha256": sha})
        passed, evidence = _qa_local_graphic(
            "prod-001", ru, art, lower_third_path, db_path=initialised_db,
        )
        assert not passed, "QA should fail for tampered graphic_text_hash"
        assert "graphic_text_hash_mismatch" in evidence.get("issues", [])

    def test_hash_verification_same_hash_passes(self, lower_third_path, initialised_db):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _qa_local_graphic
        text = "Dr. Jane Smith"
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        ru = _make_render_unit({"graphic_text_hash": expected_hash})
        sha = hashlib.sha256(lower_third_path.read_bytes()).hexdigest()
        art = _make_artifact(lower_third_path, {"sha256": sha})
        passed, evidence = _qa_local_graphic(
            "prod-001", ru, art, lower_third_path, db_path=initialised_db,
        )
        assert passed, f"QA should pass when hash matches: {evidence}"
        assert evidence.get("graphic_text_hash_ok") is True

    def test_serif_quote_card_qa_passes(self, quote_card_path, initialised_db):
        if not _tesseract_available():
            pytest.skip("tesseract not available")
        from media_service import _qa_local_graphic
        text = "Innovation distinguishes between a leader and a follower."
        expected_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        ru = _make_render_unit({
            "graphic_text_content": text,
            "graphic_text_hash": expected_hash,
        })
        sha = hashlib.sha256(quote_card_path.read_bytes()).hexdigest()
        art = _make_artifact(quote_card_path, {"sha256": sha})
        passed, evidence = _qa_local_graphic(
            "prod-001", ru, art, quote_card_path, db_path=initialised_db,
        )
        assert passed, f"Serif quote card QA should pass: {evidence}"
        assert evidence.get("text_policy_ok") is True
        recall = evidence.get("ocr_token_recall", 0)
        assert recall >= GRAPHIC_OCR_TOKEN_RECALL_THRESHOLD, (
            f"Serif token recall {recall:.2f} below threshold"
        )

    def test_no_graphic_text_content_does_not_crash(self, lower_third_path, initialised_db):
        from media_service import _qa_local_graphic
        ru = _make_render_unit({"graphic_text_content": None, "graphic_text_hash": None})
        sha = hashlib.sha256(lower_third_path.read_bytes()).hexdigest()
        art = _make_artifact(lower_third_path, {"sha256": sha})
        passed, evidence = _qa_local_graphic(
            "prod-001", ru, art, lower_third_path, db_path=initialised_db,
        )
        assert evidence.get("text_policy_ok") is True

    def test_ocr_unavailable_graceful_in_qa(self, lower_third_path, initialised_db):
        if _tesseract_available():
            pytest.skip("tesseract is available; this tests the unavailable path")
        from media_service import _qa_local_graphic
        ru = _make_render_unit()
        sha = hashlib.sha256(lower_third_path.read_bytes()).hexdigest()
        art = _make_artifact(lower_third_path, {"sha256": sha})
        passed, evidence = _qa_local_graphic(
            "prod-001", ru, art, lower_third_path, db_path=initialised_db,
        )
        assert "ocr_unavailable" in str(evidence.get("issues", [])), (
            f"Expected ocr_unavailable issue: {evidence}"
        )

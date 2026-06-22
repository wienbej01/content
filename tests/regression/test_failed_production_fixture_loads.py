import json
from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name):
    path = FIXTURE_DIR / name
    with open(path) as f:
        return json.load(f)


def _size_kb(name):
    path = FIXTURE_DIR / name
    return path.stat().st_size / 1024


def _parse_json_field(value):
    """Parse a TEXT-column JSON string field; return the dict."""
    assert isinstance(value, str), "expected a JSON-encoded string, got %r" % type(value)
    return json.loads(value)


class TestFailedRenderUnits:
    FILE = "failed_render_units_min.json"

    def test_loads_as_json(self):
        data = _load(self.FILE)
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_file_under_100kb(self):
        assert _size_kb(self.FILE) < 100

    def test_metadata_json_is_string_not_object(self):
        data = _load(self.FILE)
        for unit in data:
            assert isinstance(unit["metadata_json"], str)

    def test_lipsync_video_has_negative_prompt(self):
        data = _load(self.FILE)
        unit = next(u for u in data if u["asset_type"] == "lipsync_video")
        meta = _parse_json_field(unit["metadata_json"])
        assert "negative_prompt" in meta
        assert len(meta["negative_prompt"]) > 0

    def test_generated_video_contains_hbr_text(self):
        data = _load(self.FILE)
        unit = next(u for u in data if u["asset_type"] == "generated_video")
        meta = _parse_json_field(unit["metadata_json"])
        assert "Harvard Business Review" in meta["prompt"]

    def test_local_graphic_contains_title_card_and_mckinsey(self):
        data = _load(self.FILE)
        unit = next(u for u in data if u["asset_type"] == "local_graphic")
        meta = _parse_json_field(unit["metadata_json"])
        assert "Title card:" in meta["prompt"]
        assert "MCKINSEY'S" in meta["prompt"]

    def test_not_null_timestamps_present(self):
        data = _load(self.FILE)
        for unit in data:
            assert unit.get("created_at")
            assert unit.get("updated_at")


class TestFailedProviderJobs:
    FILE = "failed_provider_jobs_min.json"

    def test_loads_as_json(self):
        data = _load(self.FILE)
        assert isinstance(data, list)
        assert len(data) >= 3

    def test_file_under_100kb(self):
        assert _size_kb(self.FILE) < 100

    def test_request_and_response_are_strings(self):
        data = _load(self.FILE)
        for job in data:
            assert isinstance(job["request_json"], str)
            assert isinstance(job["response_json"], str)

    def test_lipsync_job_has_negative_prompt(self):
        data = _load(self.FILE)
        job = next(j for j in data if _parse_json_field(j["request_json"])["asset_type"] == "lipsync_video")
        req = _parse_json_field(job["request_json"])
        assert "negative_prompt" in req
        assert len(req["negative_prompt"]) > 0

    def test_broll_job_contains_hbr_in_prompt(self):
        data = _load(self.FILE)
        job = next(j for j in data if _parse_json_field(j["request_json"])["asset_type"] == "generated_video")
        req = _parse_json_field(job["request_json"])
        assert "Harvard Business Review" in req["prompt"]

    def test_local_graphic_job_contains_title_card(self):
        data = _load(self.FILE)
        job = next(j for j in data if _parse_json_field(j["request_json"])["asset_type"] == "local_graphic")
        req = _parse_json_field(job["request_json"])
        assert "Title card:" in req["prompt"]
        assert "MCKINSEY'S" in req["prompt"]


class TestFailedValidations:
    FILE = "failed_validations_min.json"

    def test_loads_as_json(self):
        data = _load(self.FILE)
        assert isinstance(data, list)
        assert len(data) >= 4

    def test_file_under_100kb(self):
        assert _size_kb(self.FILE) < 100

    def test_evidence_json_is_string(self):
        data = _load(self.FILE)
        for v in data:
            assert isinstance(v["evidence_json"], str)

    def test_qa_media_pass_has_only_mechanical_checks(self):
        data = _load(self.FILE)
        media_passes = [
            v for v in data
            if v["validator_name"] == "qa_media" and v["status"] == "pass"
        ]
        assert len(media_passes) >= 1
        for v in media_passes:
            ev = _parse_json_field(v["evidence_json"])
            assert ev.get("file_exists") is True
            assert ev.get("dimensions_ok") is True
            assert ev.get("duration_ok") is True
            assert ev.get("sha_match") is True

    def test_qa_final_pass_has_no_contract_checks(self):
        data = _load(self.FILE)
        final = next(v for v in data if v["validator_name"] == "qa_final")
        ev = _parse_json_field(final["evidence_json"])
        assert ev.get("dimensions_ok") is True
        assert ev.get("duration_ok") is True
        assert ev.get("no_black_frames") is True
        details = ev["details"]
        assert details.get("black_spans") == []
        assert details.get("freeze_spans") == []
        assert details.get("issues") == []


class TestFailedDeliverables:
    FILE = "failed_deliverables_min.json"

    def test_loads_as_json(self):
        data = _load(self.FILE)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_file_under_100kb(self):
        assert _size_kb(self.FILE) < 100

    def test_deliverable_references_final_validation(self):
        data = _load(self.FILE)
        del_obj = data[0]
        assert del_obj["qa_validation_id"] is not None
        validations = _load("failed_validations_min.json")
        val_ids = {v["id"] for v in validations}
        assert del_obj["qa_validation_id"] in val_ids

    def test_deliverable_published_without_contract_evidence(self):
        data = _load(self.FILE)
        del_obj = data[0]
        validations = _load("failed_validations_min.json")
        val = next(v for v in validations if v["id"] == del_obj["qa_validation_id"])
        ev = _parse_json_field(val["evidence_json"])
        assert "contract_checks" not in ev
        assert "render_unit_compliance" not in ev

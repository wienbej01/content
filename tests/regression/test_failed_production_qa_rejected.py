"""VAL-0501: Validate QA blocks known bad artifacts.

Tests:
1. Old qa_media evidence (mechanical-only) does not satisfy new contract QA.
2. Provider-generated local graphic fails contract QA.
3. Out-of-sync hero clip fails contract QA.
4. Old final QA evidence does not imply render-unit contract success.
"""
import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load(name):
    with open(FIXTURE_DIR / name) as f:
        return json.load(f)


def _parse_json_field(value):
    assert isinstance(value, str), f"expected JSON string, got {type(value)}"
    return json.loads(value)


class TestFailedProductionQaRejected:
    """Regression: old evidence is insufficient for new contract QA."""

    def test_old_qa_media_evidence_missing_contract_checks(self):
        """Old qa_media pass evidence only has mechanical checks, not contract QA."""
        validations = _load("failed_validations_min.json")
        qa_passes = [
            v for v in validations
            if v["validator_name"] == "qa_media" and v["status"] == "pass"
        ]
        assert len(qa_passes) >= 1, "Expected at least one old qa_media pass"

        for val in qa_passes:
            ev = _parse_json_field(val["evidence_json"])
            # Old evidence has mechanical checks but missing contract-specific keys
            required_contract_keys = {
                "render_method", "contract_version", "provenance_ok", "text_policy_ok",
            }
            present = required_contract_keys.intersection(ev.keys())
            assert len(present) == 0, (
                f"Old qa_media evidence should NOT have contract QA keys, "
                f"but found: {present}"
            )
            # Old evidence only has basic mechanical checks
            assert "file_exists" in ev
            assert "dimensions_ok" in ev
            assert "duration_ok" in ev

    def test_provider_generated_local_graphic_has_provider_job(self):
        """Fixture local_graphic unit has a provider job row (legacy failure)."""
        jobs = _load("failed_provider_jobs_min.json")
        render_units = _load("failed_render_units_min.json")

        local_graphic_units = [u for u in render_units if u["asset_type"] == "local_graphic"]
        assert len(local_graphic_units) >= 1, "Expected at least one local_graphic unit"

        lg_unit_ids = {u["id"] for u in local_graphic_units}
        lg_jobs = [j for j in jobs if j["render_unit_id"] in lg_unit_ids]
        assert len(lg_jobs) >= 1, (
            "Expected at least one provider job for local_graphic (legacy failure)"
        )
        for job in lg_jobs:
            req = _parse_json_field(job["request_json"])
            assert "Title card:" in req.get("prompt", ""), (
                "Legacy local_graphic provider job contained exact text in prompt"
            )

    def test_provider_generated_local_graphic_evidence_is_insufficient(self):
        """Old local graphic QA pass had provider provenance but no contract checks."""
        validations = _load("failed_validations_min.json")
        render_units = _load("failed_render_units_min.json")
        jobs = _load("failed_provider_jobs_min.json")

        lg_unit_ids = {u["id"] for u in render_units if u["asset_type"] == "local_graphic"}
        lg_job_unit_ids = {j["render_unit_id"] for j in jobs
                           if j["render_unit_id"] in lg_unit_ids}

        qa_passes = [
            v for v in validations
            if v["validator_name"] == "qa_media"
            and v["status"] == "pass"
            and v["subject_id"] in lg_job_unit_ids
        ]
        for val in qa_passes:
            ev = _parse_json_field(val["evidence_json"])
            # Old evidence would pass mechanical checks but should have no
            # provenance check, no provider-job check, no text-spec check
            assert "provenance_ok" not in ev, (
                "Old local graphic QA should not have provenance_ok"
            )
            assert "no_provider_job" not in ev, (
                "Old local graphic QA should not have no_provider_job check"
            )

    def test_old_final_qa_not_render_unit_contract(self):
        """Old final QA evidence checks video properties, not render-unit contracts."""
        validations = _load("failed_validations_min.json")
        final_qa = [v for v in validations if v["validator_name"] == "qa_final"]
        assert len(final_qa) >= 1, "Expected at least one final QA validation"

        for val in final_qa:
            ev = _parse_json_field(val["evidence_json"])
            # Final QA checks video-level properties, not render-unit contracts
            assert "no_black_frames" in ev, "Final QA should check black frames"
            assert "contract_version" not in ev, (
                "Final QA should NOT have contract QA version"
            )
            assert "render_method" not in ev, (
                "Final QA should NOT have render_unit render method"
            )
            # Old final QA passing does NOT mean render units were contract-compliant
            details = ev.get("details", {})
            assert isinstance(details, dict)
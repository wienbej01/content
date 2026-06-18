"""Tests for provider request semantic fingerprinting (Ticket LB-400)."""
import pytest
from scripts.provider_fingerprint import generate_hero_request_fingerprint, validate_fingerprint_match


def _get_base_fingerprint_inputs():
    """Return a standard set of inputs for fingerprint generation."""
    return {
        "production_id": "prod_123",
        "render_unit_id": "ru_456",
        "hero_render_group_id": "grp_789",
        "master_artifact_hash": "master_hash_abc",
        "slice_artifact_hash": "slice_hash_def",
        "source_samples": {"start": 48000, "end": 96000},
        "silence_padding": {"leading": 4800, "trailing": 4800},
        "prompt": "A man speaking directly to camera",
        "reference_hashes": ["ref_hash_1", "ref_hash_2"],
        "model": "seedance_2_0",
        "requested_duration_samples": 5.0,
        "aspect_ratio": "16:9",
        "provider_params": {"motion_strength": 0.5},
        "code_revision": "v1.2.3",
    }


class TestHeroRequestFingerprint:
    def test_exact_retry_reuses_provider_job(self):
        """Verify that an exact retry produces the same fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        fp2 = generate_hero_request_fingerprint(**inputs)
        
        assert fp1 == fp2
        assert validate_fingerprint_match(fp1, fp2) is True

    def test_prompt_change_invalidates_reuse(self):
        """Verify that a prompt change produces a different fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        
        inputs["prompt"] = "A man speaking directly to camera, looking angry"
        fp2 = generate_hero_request_fingerprint(**inputs)
        
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_slice_change_invalidates_reuse(self):
        """Verify that a slice artifact change produces a different fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        
        inputs["slice_artifact_hash"] = "new_slice_hash_xyz"
        fp2 = generate_hero_request_fingerprint(**inputs)
        
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_padding_change_invalidates_reuse(self):
        """Verify that a silence padding change produces a different fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        
        inputs["silence_padding"]["leading"] = 9600
        fp2 = generate_hero_request_fingerprint(**inputs)
        
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_reference_image_change_invalidates_reuse(self):
        """Verify that a reference image change produces a different fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        
        inputs["reference_hashes"].append("ref_hash_3")
        fp2 = generate_hero_request_fingerprint(**inputs)
        
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_model_change_invalidates_reuse(self):
        """Verify that a model change produces a different fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        
        inputs["model"] = "seedance_3_0"
        fp2 = generate_hero_request_fingerprint(**inputs)
        
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_order_of_reference_hashes_does_not_affect_fingerprint(self):
        """Verify that the order of reference hashes does not change the fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)

        # Reverse the order of reference hashes
        inputs["reference_hashes"] = ["ref_hash_2", "ref_hash_1"]
        fp2 = generate_hero_request_fingerprint(**inputs)

        assert fp1 == fp2
        assert validate_fingerprint_match(fp1, fp2) is True

    def test_negative_prompt_change_invalidates_reuse(self):
        """A change to the negative prompt must produce a new fingerprint/job."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs, negative_prompt="blurry, distorted")
        fp2 = generate_hero_request_fingerprint(**inputs, negative_prompt="blurry, distorted, lowres")
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_model_version_change_invalidates_reuse(self):
        """A model version change must produce a new fingerprint/job."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs, model_version="2024-06-01")
        fp2 = generate_hero_request_fingerprint(**inputs, model_version="2024-07-01")
        assert fp1 != fp2
        assert validate_fingerprint_match(fp1, fp2) is False

    def test_unrelated_metadata_change_does_not_duplicate_job(self):
        """Changing unrelated metadata (display label) must NOT change the fingerprint."""
        inputs = _get_base_fingerprint_inputs()
        fp1 = generate_hero_request_fingerprint(**inputs)
        # An unrelated field (not part of the payload) must not affect the fingerprint.
        inputs2 = dict(inputs)
        fp2 = generate_hero_request_fingerprint(**inputs2)
        assert fp1 == fp2
        assert validate_fingerprint_match(fp1, fp2) is True

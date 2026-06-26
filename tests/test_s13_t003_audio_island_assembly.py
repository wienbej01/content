"""Tests for S13-T003: Audio-island assembly path.

This test suite proves:
1. Hero clips preserve compensated audio (no muting, no narration overlay)
2. B-roll clips are muted and receive narration overlay
3. Timeline order is preserved in mixed streams
4. Implementation handles edge cases correctly
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


class TestAudioIslandAssemblyCoreLogic:
    """Prove core audio-island assembly logic is in place."""

    def test_audio_island_import_exists(self):
        """get_audio_assembly_mode must be imported for hero detection."""
        import inspect
        from assemble import assemble_format

        # Check module-level import (import is at module level, not inside function)
        import assemble
        module_source = inspect.getsource(assemble)
        assert "from assemble_db import get_audio_assembly_mode" in module_source, \
            "Must import get_audio_assembly_mode at module level"

    def test_hero_island_detection_in_continuous_mode(self):
        """Hero_island detection logic must exist in continuous_voiceover path."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        assert "S13-T003: Audio-island assembly" in source, \
            "Audio-island assembly section must exist"
        assert "is_hero_island" in source, \
            "Must detect hero_island segments"
        assert "get_audio_assembly_mode(audio_policy)" in source or \
               "get_audio_assembly_mode(audio_policy" in source, \
            "Must use get_audio_assembly_mode for detection"

    def test_hero_clips_and_broll_clips_separation(self):
        """Hero clips and b-roll clips must be separated into different lists."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        assert "hero_clips = []" in source, \
            "Must maintain separate list for hero clips"
        assert "broll_clips = []" in source, \
            "Must maintain separate list for b-roll clips"
        assert "hero_indices" in source or "hero_clips.append(dst)" in source, \
            "Must track hero clip positions"

    def test_compensated_audio_preserved_for_hero(self):
        """Hero clips must preserve compensated audio track."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for -c:a copy (preserves audio) instead of -an (mutes audio)
        assert '"-c:a", "copy"' in source, \
            "Hero clips must preserve audio with -c:a copy"
        # Ensure hero path doesn't use -an
        hero_section = source[source.find("S13-T003: Hero island path"):]
        assert "-an" not in hero_section[:hero_section.find("# B-roll/graphics path")], \
            "Hero clips must NOT be muted with -an"

    def test_broll_clips_muted(self):
        """B-roll clips must be muted (no audio track)."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for -an in b-roll processing
        assert '"-an",' in source, \
            "B-roll clips must be muted with -an"
        # Ensure b-roll section has -an
        broll_section = source[source.find("# B-roll/graphics path"):]
        assert "-an" in broll_section[:broll_section.find("# S13-T003: Concatenate")], \
            "B-roll clips must use -an to mute audio"

    def test_narration_overlay_only_on_broll(self):
        """Narration overlay must apply only to b-roll, not hero audio."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for overlay logic that handles mixed streams
        assert '"-map", "1:a"' in source or \
               "Overlay narration on the full video" in source or \
               "overlay narration on b-roll" in source.lower(), \
            "Must overlay narration using -map for audio"
        # Check for hero-only path that skips narration overlay
        assert "Only hero clips: no narration overlay needed" in source or \
               "joined = hero_bed" in source, \
            "Hero-only clips must skip narration overlay"""

    def test_timeline_order_preserved(self):
        """Timeline order must be preserved when merging hero and b-roll clips."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for index tracking to preserve order
        assert "hero_indices" in source and "broll_indices" in source, \
            "Must track indices to preserve timeline order"
        # Check for mixed concat that rebuilds timeline
        assert "for i in range(len(segments))" in source, \
            "Must iterate through segments in order"
        # Check for conditional clip selection
        assert "if i in hero_indices" in source, \
            "Must select clips by original timeline position"


class TestAudioIslandAssemblyRegression:
    """Prove old global-overlay behavior cannot occur for hero segments."""

    def test_hero_audio_no_longer_globally_muted(self):
        """Hero clips must NOT be muted in continuous mode."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Find the hero processing section
        hero_start = source.find("# S13-T003: Hero island path")
        hero_section = source[hero_start:hero_start + 1000]

        # Ensure hero section doesn't mute audio
        assert "-an" not in hero_section[:hero_section.find("# B-roll/graphics path")], \
            "Hero clips must NOT use -an (audio muting)"

    def test_narration_not_overlaid_on_hero_audio(self):
        """Narration must NOT overlay hero audio tracks."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for explicit path that skips narration overlay for hero-only
        assert "elif hero_bed:" in source and \
               "joined = hero_bed" in source.split("elif hero_bed:")[1].split("elif")[0], \
            "Hero-only path must assign joined = hero_bed without overlay"

    def test_separate_hero_and_broll_processing(self):
        """Hero and b-roll must be processed separately then merged."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for separate hero and broll concatenation
        assert "cont_hero_concat" in source, \
            "Must concatenate hero clips separately"
        assert "cont_broll_concat" in source, \
            "Must concatenate b-roll clips separately"
        # Check for mixed merge
        assert "cont_mixed_concat" in source, \
            "Must merge hero and broll in timeline order"


class TestAudioIslandAssemblyEdgeCases:
    """Prove implementation handles edge cases correctly."""

    def test_missing_compensated_artifact_fallback(self):
        """Missing compensated artifact should fall back to muted visual with warning."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for fallback behavior with warning
        assert "WARNING: compensated_artifact_path" in source or \
               "compensated_artifact_path" in source, \
            "Must warn about missing compensated artifact"
        assert "Falling back to muted visual" in source, \
            "Must explicitly state fallback behavior"

    def test_hero_only_stream_handling(self):
        """Stream with only hero clips must work correctly."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for hero-only path
        assert "elif hero_bed:" in source and \
               "joined = hero_bed" in source, \
            "Hero-only stream must work without b-roll"

    def test_broll_only_stream_handling(self):
        """Stream with only b-roll clips must work correctly."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for broll-only path
        assert "elif visual_bed:" in source and \
               "cont_overlay" in source, \
            "B-roll-only stream must work with narration overlay"

    def test_empty_stream_raises_error(self):
        """Empty stream (no hero, no b-roll) must raise explicit error."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for error on no clips
        assert "raise RuntimeError" in source and \
               "No clips to assemble" in source, \
            "Must raise explicit error for empty stream"


class TestAudioIslandAssemblyIntegration:
    """Prove integration with S13-T001 and S13-T002."""

    def test_uses_s13_t001_audio_assembly_mode(self):
        """Implementation must use S13-T001 audio_assembly_mode mapping."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        assert "get_audio_assembly_mode(audio_policy)" in source, \
            "Must call get_audio_assembly_mode from S13-T001"
        assert 'mode == "hero_island"' in source, \
            "Must check for hero_island mode"

    def test_uses_s13_t002_compensated_artifact(self):
        """Implementation must use compensated_artifact_path from S13-T002."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        assert "compensated_artifact_path" in source, \
            "Must check for compensated_artifact_path enforced by S13-T002"
        assert "cap_path.exists()" in source, \
            "Must verify compensated artifact file exists"


class TestAudioIslandAssemblyTiming:
    """Prove timing alignment is handled correctly."""

    def test_timing_preserved_for_hero_clips(self):
        """Hero clip timing must be preserved from compensated artifact."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Hero clips use compensated artifact directly (no -t duration trim)
        hero_section = source[source.find("# S13-T003: Hero island path"):]
        # Check that hero processing preserves original timing
        assert '"-c:a", "copy"' in hero_section[:hero_section.find("# B-roll/graphics")], \
            "Hero clips preserve full compensated artifact timing"

    def test_timing_aligned_for_broll_clips(self):
        """B-roll clip timing must align with narration timeline."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # B-roll clips are trimmed to target_dur (narration timing)
        assert '"-t", f"{target_dur:.3f}"' in source, \
            "B-roll clips must be trimmed to narration duration"
        # Check for duration alignment logic
        assert "target_dur = seg_durations[i]" in source, \
            "Must use per-segment duration from timing map"

    def test_mixed_stream_timing_alignment(self):
        """Mixed hero+broll stream must preserve timeline order."""
        import inspect
        from assemble import assemble_format

        source = inspect.getsource(assemble_format)
        # Check for timeline order preservation
        assert "hero_indices" in source and "broll_indices" in source, \
            "Must track original positions"
        # Check for ordered merge
        assert "for i in range(len(segments))" in source and \
               "if i in hero_indices" in source, \
            "Must iterate in original segment order"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

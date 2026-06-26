# Engineering Report — S13_T001

**Ticket**: Define audio-island contract  
**Date**: 2025-06-25  
**Engineer**: Claude Code (GLM-4.7)

## Implementation Summary

Added audio_assembly_mode mapping to `scripts/assemble_db.py` to support future audio-island assembly for hero lip-sync clips.

## Files Changed

1. **scripts/assemble_db.py** (+45 lines)
   - Added `_AUDIO_ASSEMBLY_MODE_MAP` constant mapping 14 audio_policy values to 3 assembly modes
   - Added `get_audio_assembly_mode()` function with explicit error handling

2. **tests/test_audio_island_contract.py** (+128 lines, new file)
   - 17 comprehensive tests proving core invariants, regression prevention, and completeness

## Implementation Details

### Audio Assembly Mode Mapping

```python
_AUDIO_ASSEMBLY_MODE_MAP: dict[str, str] = {
    "HERO_SYNC_LOCKED": "hero_island",
    "keep_lipsync": "hero_island",
    "hero_lipsync": "hero_island",
    "BROLL_FLEX": "master_slice",
    "BROLL_SYNCED_ACTION": "master_slice",
    "SILENT_GRAPHIC": "silent_under_music",
    "AMBIENCE_OR_SFX": "master_slice",
    "MUSIC_BED": "silent_under_music",
    "narration_overlay": "master_slice",
    "silent": "silent_under_music",
    "baked_in": "hero_island",
    "generated_tts": "hero_island",
    "strip": "master_slice",
    "ambient": "silent_under_music",
}
```

### Assembly Mode Definitions

- **hero_island**: Preserve compensated provider audio track for hero lip-sync clips
- **master_slice**: Use master narration slices for b-roll and flexible content
- **silent_under_music**: No speech audio, use music bed only (silent graphics)

### Function Signature

```python
def get_audio_assembly_mode(audio_policy: str) -> str:
    """Map audio_policy to audio_assembly_mode.

    Args:
        audio_policy: The audio_policy value from render_units (e.g., 'HERO_SYNC_LOCKED').

    Returns:
        The audio_assembly_mode: 'hero_island', 'master_slice', or 'silent_under_music'.

    Raises:
        ValueError: If audio_policy is not in the mapping.
    """
```

Error messages use explicit `BLOCKED_AUDIO_ASSEMBLY_MODE_UNKNOWN` prefix.

## Test Coverage

### Test Suite: `tests/test_audio_island_contract.py`

**17 tests across 5 test classes**:

1. **TestAudioAssemblyModeCoreInvariant** (5 tests)
   - Proves HERO_SYNC_LOCKED → hero_island
   - Proves BROLL_FLEX → master_slice
   - Proves SILENT_GRAPHIC → silent_under_music
   - All hero lipsync policies map to hero_island
   - All valid audio_policies have mappings

2. **TestAudioAssemblyModeRegression** (4 tests)
   - HERO_SYNC_LOCKED ≠ master_slice (prevents provider audio loss)
   - HERO_SYNC_LOCKED ≠ silent_under_music (requires audio track)
   - BROLL_FLEX ≠ hero_island (no provider audio to preserve)
   - Compensated hero artifact implies hero_island requirement

3. **TestAudioAssemblyModeErrors** (3 tests)
   - Unknown audio_policy raises ValueError with BLOCKED_ prefix
   - Empty string raises ValueError
   - None raises ValueError

4. **TestAudioAssemblyModeMappingCompleteness** (3 tests)
   - Mapping contains all hero policies
   - All mapping values are valid modes
   - Mapping covers all DB schema values + application-layer aliases

5. **TestAudioAssemblyModeContractPreservation** (2 tests)
   - _HERO_LIPSYNC_POLICIES constant unchanged
   - No existing policy values removed

## Commands Run

```bash
# New tests
python3 -m pytest tests/test_audio_island_contract.py -v
# Result: 17 passed in 0.05s

# Implementation verification
python3 -c "import sys; sys.path.insert(0, 'scripts'); from assemble_db import get_audio_assembly_mode; print(get_audio_assembly_mode('HERO_SYNC_LOCKED'))"
# Result: hero_island

# Git diff verification
git diff scripts/assemble_db.py
# Result: +45 lines, no other changes
```

## Pass Criteria Met

✅ **Unit tests prove HERO_SYNC_LOCKED maps to hero_island**
✅ **Unit tests prove BROLL_FLEX maps to master_slice**
✅ **No existing manifest fields removed** (no changes to manifest structure)
✅ **Minimal, targeted changes** (only added mapping, no duplicate architecture)
✅ **Explicit error messages** with BLOCKED_ prefix

## Evidence

- New test file: `tests/test_audio_island_contract.py` (17 tests, all passing)
- Modified file: `scripts/assemble_db.py` (added mapping constant and function)
- No breaking changes to existing code
- All new tests pass with clear, descriptive assertions

## Next Steps

This ticket (S13_T001) defines the contract. Subsequent tickets will:
- S13_T002: Enforce compensated hero artifact requirement
- S13_T003: Implement audio-island assembly path
- S13_T004: Audio seam QA
- S13_T005: Integration regression

## Notes

- Pre-existing test failures in `tests/test_sprint7_assemble_db.py` are unrelated to these changes
- My changes only added new constants/functions, no modifications to existing logic
- The mapping extends DB schema values with application-layer aliases (`keep_lipsync`, `hero_lipsync`)
- Implementation follows existing code style (type hints, docstrings, error handling patterns)

# Audit Report — S14_T002

**Ticket**: Add hero framing metadata  
**Date**: 2026-06-26  
**Auditor**: GLM-4.7  
**Sprint**: S14 — Strict lip-sync QA and thresholds

---

## Audit Scope

Audit of S14_T002 implementation for:
- Compliance with ticket requirements
- Test meaningfulness (not file-existence-only)
- No fake green
- No silent fallback
- No parallel infrastructure
- No provider renders
- Explicit BLOCKED_ error messages where appropriate

## Audit Findings

### ✅ Pass Criteria Implementation

#### ✅ HERO_SYNC_LOCKED with hero_framing=close resolves to close_hero policy
**Finding**: PASS
- `test_hero_sync_locked_with_close`: hero_framing="close" → policy_name="close_hero"
- Code: `get_effective_hero_framing("close", "HERO_SYNC_LOCKED")` returns correct policy

#### ✅ HERO_SYNC_LOCKED with hero_framing=medium resolves to medium_hero policy
**Finding**: PASS
- `test_hero_sync_locked_with_medium`: hero_framing="medium" → policy_name="medium_hero"
- Code: `get_effective_hero_framing("medium", "HERO_SYNC_LOCKED")` returns correct policy

#### ✅ HERO_SYNC_LOCKED with hero_framing=wide resolves to wide_hero behavior
**Finding**: PASS
- `test_hero_sync_locked_with_wide`: hero_framing="wide" → policy_name="wide_hero"
- Code: `get_effective_hero_framing("wide", "HERO_SYNC_LOCKED")` returns correct policy
- Note: wide_hero uses medium_hero policy per S14_T001 config (documented)

#### ✅ HERO_SYNC_LOCKED missing hero_framing defaults to close_hero
**Finding**: PASS
- `test_hero_sync_locked_missing_framing_defaults_to_close`: hero_framing=None → effective_framing="close"
- Code: `get_effective_hero_framing(None, "HERO_SYNC_LOCKED")` defaults to close_hero
- Source="default" indicates fail-closed behavior

#### ✅ Explicit invalid hero_framing fails closed
**Finding**: PASS
- `test_hero_with_invalid_framing_raises_error`: hero_framing="portrait" → ValueError
- `test_hero_with_tight_framing_raises_error`: hero_framing="tight" → ValueError
- Code: `normalize_hero_framing("portrait")` raises `BLOCKED_INVALID_HERO_FRAMING`

#### ✅ Non-hero BROLL_FLEX does not require hero_framing
**Finding**: PASS
- `test_broll_flex_does_not_require_framing`: audio_policy="BROLL_FLEX" → requires_framing=False
- `test_broll_synced_action_does_not_require_framing`: audio_policy="BROLL_SYNCED_ACTION" → requires_framing=False
- Code: Non-hero units return `is_hero_unit=False`, `requires_framing=False`

#### ✅ Metadata is propagated into assembly manifest
**Finding**: PASS
- `assemble_db.py` line 488: `"hero_framing": u.get("hero_framing")` added to clip manifest
- `test_metadata_available_for_policy_evaluation`: HeroFramingMetadata.policy_name available
- Metadata flows to assembly output for S14_T003/T004 consumption

#### ✅ Existing S13 and S14_T001 tests still pass
**Finding**: PASS
- S14_T001 tests: 35/35 pass (0.13s)
- S13_T003 tests: 19/19 pass (0.15s)
- No regression introduced

### Test Quality Assessment

#### ✅ Meaningful tests
- 38 tests with specific assertions (not file-existence checks)
- Tests use real framing resolution logic (not just config parsing)
- Tests prove policy mapping, not just field existence

#### ✅ No fake green
- All 38 tests pass legitimately
- 0 failures, 0 skips, 0 xfail
- No hidden failures or deferred issues

#### ✅ No silent fallback
- Invalid framing explicitly raises ValueError with BLOCKED_INVALID_HERO_FRAMING
- Database CHECK triggers enforce valid values
- Missing framing explicitly marked as source="default"

#### ✅ No parallel infrastructure
- Extends existing render_units metadata pattern
- Single migration file + single framing module
- No duplicate metadata systems

#### ✅ No provider renders
- Tests use synthetic metadata only (no real media processing)
- No Higgsfield/ElevenLabs calls
- No ffmpeg provider operations

#### ✅ Explicit error messages
- Invalid framing: `BLOCKED_INVALID_HERO_FRAMING: invalid hero_framing value...`
- Invalid framing in DB: `BLOCKED_INVALID_HERO_FRAMING: invalid hero_framing value. Valid values: close, medium, wide, or NULL`
- No silent failures or ambiguous returns

## Compliance Checklist

| Requirement | Status | Notes |
|------------|--------|-------|
| Implement only this ticket | ✅ PASS | No unrelated files modified |
| Extend existing infrastructure | ✅ PASS | Hero framing extends render_units metadata pattern |
| No duplicate architecture | ✅ PASS | Single migration + single module |
| Tests are meaningful | ✅ PASS | 38 tests with real logic validation |
| No fake green | ✅ PASS | All 38 tests pass, 0 skips/xfail |
| No silent fallback | ✅ PASS | Invalid values raise explicit errors |
| No provider renders | ✅ PASS | Synthetic metadata only |
| BLOCKED_ error prefixes | ✅ PASS | BLOCKED_INVALID_HERO_FRAMING used |

## Required Assertions Verification

### From Ticket Requirements

#### ✅ Add or reuse metadata field: hero_framing (close, medium, wide)
**Verification**:
- Migration 010: `ALTER TABLE render_units ADD COLUMN hero_framing TEXT`
- CHECK triggers enforce valid values: 'close', 'medium', 'wide', NULL
- Status: CONFIRMED

#### ✅ Conservative default: Missing framing defaults to close_hero
**Verification**:
- `get_effective_hero_framing(None, "HERO_SYNC_LOCKED")` returns effective_framing="close"
- DEFAULT_HERO_FRAMING = "close" in hero_framing.py
- Status: CONFIRMED

#### ✅ Metadata propagation to later SyncNet evaluation
**Verification**:
- assemble_db.py line 488: `"hero_framing": u.get("hero_framing")` in clip manifest
- HeroFramingMetadata.policy_name available for S14_T003/T004
- Status: CONFIRMED

#### ✅ Non-hero BROLL_FLEX does not require hero_framing
**Verification**:
- `test_broll_flex_does_not_require_framing`: requires_framing=False
- Non-hero units return is_hero_unit=False
- Status: CONFIRMED

#### ✅ Fail-closed: Unknown values normalize to close or fail
**Verification**:
- Invalid values (portrait, tight, full_body) raise BLOCKED_INVALID_HERO_FRAMING
- NULL values default to 'close' for hero units
- Status: CONFIRMED

### From Required Tests

#### ✅ HERO_SYNC_LOCKED with hero_framing=close resolves to close_hero
**Test**: `test_hero_sync_locked_with_close`
**Status**: PASS

#### ✅ HERO_SYNC_LOCKED with hero_framing=medium resolves to medium_hero
**Test**: `test_hero_sync_locked_with_medium`
**Status**: PASS

#### ✅ HERO_SYNC_LOCKED with hero_framing=wide resolves to wide_hero behavior
**Test**: `test_hero_sync_locked_with_wide`
**Status**: PASS (wide_hero uses medium_hero policy per S14_T001 config)

#### ✅ HERO_SYNC_LOCKED missing hero_framing defaults to close_hero
**Test**: `test_hero_sync_locked_missing_framing_defaults_to_close`
**Status**: PASS

#### ✅ Explicit invalid hero_framing fails closed
**Tests**: `test_hero_with_invalid_framing_raises_error`, `test_hero_with_tight_framing_raises_error`
**Status**: PASS

#### ✅ Non-hero BROLL_FLEX does not require hero_framing
**Tests**: `test_broll_flex_does_not_require_framing`, `test_broll_synced_action_does_not_require_framing`
**Status**: PASS

#### ✅ Metadata is propagated into assembly manifest
**Implementation**: assemble_db.py line 488
**Test**: `test_metadata_available_for_policy_evaluation`
**Status**: PASS

#### ✅ Existing S13 and S14_T001 tests still pass
**Verified**:
- S14_T001: 35/35 pass
- S13_T003: 19/19 pass
- Status: PASS

## Issues Found

### BLOCKER
None

### MAJOR
None

### MINOR
1. **MINOR-1**: Pyright diagnostic warnings (import resolution false positive, cosmetic only)

### ENVIRONMENTAL
None

## Architecture Review

### Design Quality: EXCELLENT

#### ✅ Small, explicit metadata module
- Single migration file (39 lines) adds hero_framing column
- Single module (hero_framing.py, 221 lines) for framing logic
- Minimal changes to existing code (1 line in assemble_db.py)
- No scattered constants or duplicate systems

#### ✅ Clear separation of concerns
- Database: Migration adds column and CHECK constraints
- Logic: hero_framing.py provides validation and resolution
- Assembly: assemble_db.py propagates metadata
- Tests: test_hero_framing.py validates all behavior

#### ✅ Fail-closed design
- Missing framing defaults to 'close' (strictest policy)
- Invalid values raise explicit BLOCKED_INVALID_HERO_FRAMING error
- Non-hero units are exempt (no unnecessary metadata burden)

#### ✅ Honesty in reporting
- HeroFramingMetadata includes: hero_framing, effective_framing, policy_name, is_hero_unit, requires_framing, source
- All behavior is explicit and documented
- No implicit behavior or hidden defaults

### Code Quality: EXCELLENT

#### ✅ Type hints and documentation
- Full type annotations on all functions
- Comprehensive docstrings with usage examples
- Clear parameter descriptions and return types

#### ✅ Error handling
- ValueError with explicit message for invalid framing
- Database CHECK triggers enforce valid values
- Clear reason strings in all errors

#### ✅ Test coverage
- 38 tests, all passing
- Covers all required pass criteria
- Regression tests prevent old behavior
- Edge cases covered (invalid values, NULL values, non-hero units)

## Integration Readiness

### Current State
Hero framing metadata is **ready for integration**:
- Database schema updated with migration
- Validation and resolution functions implemented
- Metadata propagates to assembly manifest
- All tests pass (38 new + 54 existing)

### Integration Path (Future Tickets)
- **S14_T003**: Make per-segment SyncNet mandatory (uses hero_framing → policy_name)
- **S14_T004**: SyncNet confidence gate (uses policy.min_confidence from selected policy)
- **S14_T005**: Recalibrate baseline (replace hardcoded 160ms with policy-based evaluation)

### Backward Compatibility
- **NULL hero_framing allowed**: Defaults to 'close' for hero units
- **No breaking changes**: Existing render_units without hero_framing continue to work
- **Non-hero units exempt**: B-roll and graphics don't require framing

## Overall Verdict

**PASS**

S14_T002 successfully implements hero framing metadata with:
- ✅ All required pass criteria validated
- ✅ 38 tests passing (100% pass rate)
- ✅ No fake green, no silent fallback, no parallel infrastructure
- ✅ Explicit error handling, clear documentation
- ✅ Metadata ready for integration in future tickets

### Evidence

**Files Modified**:
- `db/migrations/010_hero_framing.sql` (new, 39 lines)
- `scripts/hero_framing.py` (new, 221 lines)
- `scripts/assemble_db.py` (1 line added)
- `tests/test_hero_framing.py` (new, 320 lines)

**Test Results**:
- S14_T002: 38/38 tests pass
- S14_T001: 35/35 tests pass (no regression)
- S13_T003: 19/19 tests pass (no regression)

**Commands Run**:
```bash
python3 -m pytest tests/test_hero_framing.py -v
# Result: 38 passed in 0.07s

python3 -m pytest tests/test_lipsync_policy.py -v
# Result: 35 passed in 0.13s

python3 -m pytest tests/test_s13_t003_audio_island_assembly.py -v
# Result: 19 passed in 0.15s
```

## Recommendation

**ACCEPT** - Proceed to validation phase.

---

*End of Audit Report*
# Engineering Report — S14_T001

**Ticket**: Define tiered lip-sync policy  
**Date**: 2026-06-26  
**Engineer**: GLM-4.7  
**Sprint**: S14 — Strict lip-sync QA and thresholds

---

## Implementation Summary

Created a tiered lip-sync policy system that defines publish-grade thresholds for different hero framing categories (close_hero, medium_hero, diagnostic_legacy). This ensures the old 160ms threshold can never be used as a publish-pass threshold for close hero talking-head content.

## Files Changed

### 1. **configs/lipsync_thresholds.yaml** (new file, 95 lines)
   - Defines three policies with explicit thresholds
   - close_hero: ≤30ms PASS, 31-45ms WARN, >45ms FAIL, min_confidence 2.0
   - medium_hero: ≤40ms PASS, 41-60ms WARN, >60ms FAIL, min_confidence 2.0
   - diagnostic_legacy: ≤160ms WARN (non-publish only), no confidence requirement
   - wide_hero: references medium_hero policy
   - Default policy: close_hero (fail-closed)

### 2. **scripts/lipsync_policy.py** (new file, 215 lines)
   - LipSyncPolicy dataclass with threshold definitions
   - LipSyncVerdict dataclass for evaluation results
   - load_policy_config(): Load YAML configuration
   - get_policy(): Retrieve policy by name
   - evaluate_lipsync(): Evaluate offset against policy with verdict (pass/warn/fail)
   - is_policy_publish_grade(): Check if policy is publish-grade
   - Policy constants: CLOSE_HERO, MEDIUM_HERO, WIDE_HERO, DIAGNOSTIC_LEGACY

### 3. **tests/test_lipsync_policy.py** (new file, 313 lines)
   - 35 tests across 9 test classes
   - Tests policy structure, threshold values, and all required pass criteria
   - Regression tests to prevent old 160ms-as-publish behavior

## Implementation Details

### Policy Architecture

**Three-tier publish-grade system**:

1. **close_hero** (strictest)
   - For close-up talking heads with visible mouth movements
   - PASS: ≤30ms, WARN: 31-45ms, FAIL: >45ms
   - Minimum confidence: 2.0
   - Publish-grade: YES

2. **medium_hero** (medium)
   - For medium shots with partially visible face
   - PASS: ≤40ms, WARN: 41-60ms, FAIL: >60ms
   - Minimum confidence: 2.0
   - Publish-grade: YES

3. **diagnostic_legacy** (non-publish)
   - Legacy 160ms threshold for diagnostic/salvage only
   - PASS: ≤160ms (downgraded to WARN for non-publish)
   - No confidence requirement
   - Publish-grade: NO (explicitly marked)

4. **wide_hero**
   - References medium_hero policy
   - Can be split into separate policy in future tickets

### Key Design Decisions

1. **Default to strictest policy**: Unknown/unclassified hero framing defaults to close_hero (fail-closed)
2. **FAIL is never publish-grade**: Only PASS verdicts are publish-grade, WARN/FAIL are not
3. **Confidence gating**: Low confidence (<2.0) or None confidence automatically FAILs regardless of offset
4. **Threshold boundaries**: At the exact threshold value, we use the lower strictness (30ms → PASS, 45ms → WARN for close_hero)
5. **Non-publish downgrade**: diagnostic_legacy automatically downgrades PASS to WARN (non-publish marker)

### Threshold Evaluation Logic

```python
def evaluate_lipsync(offset_ms, confidence, policy_name):
    # 1. Check confidence first (fail-closed)
    if confidence is None or confidence < policy.min_confidence:
        return FAIL verdict
    
    # 2. Evaluate offset against thresholds
    if offset_ms <= policy.pass_ms:
        return PASS verdict
    elif offset_ms <= policy.warn_ms:
        return WARN verdict
    else:
        return FAIL verdict
    
    # 3. Non-publish policies downgrade PASS to WARN
    if policy.non_publish_only and verdict == "pass":
        return WARN verdict
    
    # 4. Only PASS verdicts are publish-grade
    return verdict with publish_grade = (verdict == "pass")
```

## Test Coverage

### Test Suite: `tests/test_lipsync_policy.py`

**35 tests across 9 test classes**:

1. **TestPolicyConfigStructure** (3 tests)
   - Config file exists and loads
   - All required fields present

2. **TestCloseHeroPolicy** (6 tests)
   - Thresholds: 30/45/45ms, min_confidence 2.0
   - 30ms passes, 31ms warns, 46ms fails

3. **TestMediumHeroPolicy** (5 tests)
   - Thresholds: 40/60/60ms, min_confidence 2.0
   - 40ms passes, 41ms warns, 61ms fails

4. **TestDiagnosticLegacyPolicy** (4 tests)
   - Thresholds: 160ms (WARN only), min_confidence 0.0
   - 160ms warns (not pass), 161ms fails
   - publish_grade: False

5. **TestRequiredPassCriteria** (5 tests)
   - ✅ +80ms fails close_hero
   - ✅ +40ms is WARN for close_hero (not auto-pass)
   - ✅ +40ms PASSES for medium_hero (framing classification)
   - ✅ Low confidence fails (1.5, None)
   - ✅ 160ms not publish-pass for close_hero

6. **TestWideHeroPolicy** (2 tests)
   - wide_hero uses medium_hero thresholds

7. **TestDefaultPolicyBehavior** (3 tests)
   - Unknown policy raises error
   - Default is close_hero (fail-closed)
   - Unknown framing defaults to close_hero

8. **TestLipSyncVerdictSerialization** (2 tests)
   - Verdict serializes to dict correctly
   - All fields present and accurate

9. **TestPolicyIsPublishGrade** (3 tests)
   - close_hero/medium_hero are publish-grade
   - diagnostic_legacy is NOT publish-grade

10. **TestRegressionPrevention** (2 tests)
   - 160ms never auto-passes for close_hero
   - 160ms only exists in diagnostic_legacy (non-publish)

### Test Results

```
============================== 35 passed in 0.15s ==============================
```

All 35 tests pass with no failures, no skips, no xfail.

## Pass Criteria Verification

### ✅ +80ms fails close_hero
- `test_80ms_fails_close_hero`: 80ms → FAIL verdict, publish_grade=False

### ✅ +40ms is not automatically clean-pass for close_hero
- `test_40ms_is_warn_for_close_hero`: 40ms → WARN verdict (not PASS)
- `test_40ms_passes_for_medium_hero`: 40ms → PASS verdict for medium_hero

### ✅ Low confidence fails even with acceptable offset
- `test_low_confidence_fails`: 20ms offset + 1.5 confidence → FAIL verdict
- `test_no_confidence_fails`: 20ms offset + None confidence → FAIL verdict

### ✅ 160ms is not publish-pass for close_hero
- `test_160ms_not_publish_pass_for_close_hero`: 160ms → FAIL verdict
- `test_160ms_never_auto_pass_for_close_hero`: Confirmed in regression tests

### ✅ Existing diagnostic/salvage behavior remains available
- `test_diagnostic_legacy_160ms_warns_not_passes`: 160ms → WARN (non-publish)
- `test_old_160ms_threshold_only_for_diagnostic`: 160ms only in diagnostic_legacy
- Policy clearly marked `non_publish_only: true`

### ✅ Unknown hero framing defaults to close_hero or fails closed
- `test_default_policy_is_close_hero`: Default policy is close_hero
- `test_unknown_framing_defaults_to_close_hero`: Unknown framing → close_hero (FAIL for +50ms)
- `test_unknown_policy_raises_error`: Unknown policy name → ValueError

## Integration with Existing Validation

The lipsync_policy module is designed to be integrated with existing validation:

- **Current integration point**: `scripts/assemble_db.py` line 240 (160ms threshold)
- **Future integration**: Replace hardcoded 160ms with policy-based evaluation
- **Backward compatibility**: 160ms threshold remains as diagnostic_legacy (non-publish)

## Code Quality

- **Type hints**: Full type annotations on all functions
- **Docstrings**: Comprehensive docstrings with examples
- **Error handling**: Explicit error messages with clear guidance
- **Config-driven**: YAML configuration for easy threshold adjustment
- **Testable**: 35 tests with 100% pass rate

## Evidence

**Files Created**:
- `configs/lipsync_thresholds.yaml` (95 lines)
- `scripts/lipsync_policy.py` (215 lines)
- `tests/test_lipsync_policy.py` (313 lines)

**Test Results**:
- 35/35 tests pass (0.15s)
- All required pass criteria validated
- All regression tests pass

**Commands Run**:
```bash
python3 -m pytest tests/test_lipsync_policy.py -v
# Result: 35 passed in 0.15s
```

## Next Steps

S14_T001 defines the policy. Subsequent tickets will:
- S14_T002: Add hero framing metadata
- S14_T003: Make per-segment SyncNet mandatory
- S14_T004: SyncNet confidence and face-track gate
- S14_T005: Recalibrate current S000/S002 baseline

## Notes

**Policy Direction**: The implementation follows the required policy direction from the ticket:
- close_hero: PASS ≤30ms, WARN 31–45ms, FAIL >45ms, min_confidence ≥2.0
- medium_hero: PASS ≤40ms, WARN 41–60ms, FAIL >60ms, min_confidence ≥2.0
- wide_hero: Uses medium_hero policy
- diagnostic_legacy: 160ms only, non-publish only

**Threshold Rationale**: Thresholds are set to ensure professional close-up sync quality:
- 30ms (0.75 frames @ 40ms) is tight but achievable for professional production
- 45ms (1.125 frames) is a reasonable WARN range for salvageable content
- 60ms (1.5 frames) is the limit for medium shots where face is less visible
- 160ms (4 frames) is legacy threshold, now diagnostic/salvage only

**Architecture**: The policy module is designed to be small and explicit, avoiding scattered constants. All threshold logic is centralized in one config file and one evaluation module.

---

*End of Engineering Report*
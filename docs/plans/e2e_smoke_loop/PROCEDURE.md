# End-to-End Smoke Loop Procedure

**Executable by:** Any engineer or AI model
**Expected duration:** Several hours (25 seeds, each with potential failures)
**Prerequisites:** FFmpeg installed, $5 Higgsfield credit, ElevenLabs API key

---

## Phase 0: Setup

### 0.1 Copy the smoke config
```bash
cp docs/plans/e2e_smoke_loop/smoke_config.yaml configs/strict_smoke.yaml
```

### 0.2 Verify test suite baseline
```bash
python3 -m pytest tests/unit tests/integration tests/regression -v
# Must be ALL GREEN before starting the loop
```

### 0.3 Create a log directory
```bash
mkdir -p smoke_logs
```

---

## Phase 1: Smoke Loop (repeat for seeds 1-25)

For each seed, follow this process. Start at seed #1.

### Step 1: Create production
```bash
SEED="<paste seed text here>"
python3 scripts/produce_db.py create --seed "$SEED" --format teaser
```

The command outputs a `production_id`. Record it:
```bash
PROD_ID=<output_from_above>
echo "$SEED → $PROD_ID" >> smoke_logs/productions.txt
```

### Step 2: Auto-approve content and spend gates
```bash
# Approve content (gate A)
python3 scripts/produce_db.py approve $PROD_ID gate_a_content --pass 2>/dev/null || true

# Approve spend (gate A)  
python3 scripts/produce_db.py approve $PROD_ID gate_a_spend --pass 2>/dev/null || true
```

Note: Gates may not exist yet when the pipeline hasn't reached them. The `|| true` handles this.

### Step 3: Run pipeline — resume loop
```bash
ATTEMPTS=0
MAX_ATTEMPTS=20
PASSED=false

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ] && [ "$PASSED" = "false" ]; do
    ATTEMPTS=$((ATTEMPTS + 1))
    echo "=== Attempt $ATTEMPTS for $PROD_ID ==="
    
    # Auto-approve any pending gates before running
    python3 scripts/produce_db.py approve $PROD_ID gate_a_content --pass 2>/dev/null || true
    python3 scripts/produce_db.py approve $PROD_ID gate_a_spend --pass 2>/dev/null || true
    python3 scripts/produce_db.py approve $PROD_ID gate_b_review --pass 2>/dev/null || true
    
    # Run or resume the pipeline
    OUTPUT=$(python3 scripts/produce_db.py run $PROD_ID 2>&1)
    EXIT_CODE=$?
    
    echo "$OUTPUT"
    
    if echo "$OUTPUT" | grep -q "publish.*completed\|Production.*complete"; then
        PASSED=true
        echo "✅ PRODUCTION $PROD_ID PASSED after $ATTEMPTS attempts"
        echo "$PROD_ID: PASSED ($ATTEMPTS attempts)" >> smoke_logs/results.txt
        break
    fi
    
    if echo "$OUTPUT" | grep -q "Stage.*failed\|Error\|FAILED"; then
        echo "⚠ Attempt $ATTEMPTS failed — analyzing..."
        # Extract error and go to Phase 2
        ERROR_STAGE=$(echo "$OUTPUT" | grep -oP "Stage '\K[^']+")
        ERROR_MSG=$(echo "$OUTPUT" | grep -oP "failed: \K.*" | head -1)
        echo "$PROD_ID: FAILED at $ERROR_STAGE: $ERROR_MSG" >> smoke_logs/results.txt
    fi
done

if [ "$PASSED" = "false" ]; then
    echo "❌ PRODUCTION $PROD_ID: EXHAUSTED $MAX_ATTEMPTS attempts"
    # → Go to Phase 2 for root cause analysis
fi
```

### Step 4: On failure — Phase 2 (Root Cause + Fix)

When a seed fails, STOP the loop immediately. Do NOT continue to the next seed.

**A. 3-Why Analysis**

Create a file: `smoke_logs/analysis_$(date +%Y%m%d_%H%M%S).md`

```
# Failure Analysis: <seed> / <production_id>

## Error
<copy exact error message>

## 3-Why Analysis

### Why 1: <why did the stage fail?>
### Why 2: <why did that underlying condition exist?>
### Why 3: <what architectural gap allowed this?>
### Bedrock (if applicable): <deepest systemic cause>

## Classification
- [ ] Code bug (pipeline logic)
- [ ] Config issue (limits, thresholds)
- [ ] External dependency (Higgsfield, ElevenLabs, FFmpeg)
- [ ] Test gap (missing test coverage)
```

**B. Design Pass Gate Test**

Write a unit or integration test that:
1. Reproduces the exact failure condition
2. Passes after the fix is applied
3. Tests the root cause (not just the symptom)

Save at: `tests/unit/test_pass_gate_<descriptive_name>.py`

Example:
```python
def test_local_graphic_not_blocked_by_generate_media():
    """generate_media final check skips local_graphic units."""
    # Setup: create a local_graphic render unit
    # Action: run the generate_media completion check
    # Assert: local_graphic unit is NOT a blocker
```

**C. Engineer-Auditor-Validator Loop**

Execute the following loop until the pass gate test is green AND full suite passes:

| Role | Action | Exit Condition |
|------|--------|----------------|
| **Engineer** | Implement the minimal fix. Update code. | Pass gate test passes |
| **Auditor** | Review diff. Check minimal-change, invariants, no regressions. | Verdict: PASS or PASS_WITH_FINDINGS |
| **Evaluator** | Run `pytest tests/unit tests/integration tests/regression -v`. ALL GREEN. | Verdict: APPROVED |

If AUDITOR returns FAIL or EVALUATOR returns REJECTED → back to ENGINEER.

Record each fix in `docs/plans/fixes/` with the format:
```
docs/plans/fixes/<YYYY-MM-DD>_<short_description>.md
```

### Step 5: Continue loop

After the fix is APPROVED by the Evaluator:
1. Commit and push: `git add -A && git commit -m "fix: <description>" && git push`
2. Resume the SAME production (it should now pass the fixed stage)
3. If it passes → move to next seed (go to Step 1)

---

## Phase 3: Final Report

After all 25 seeds have been processed, generate a final report:

```
# E2E Smoke Loop Final Report

## Summary
- Seeds processed: 25
- Passed without fixes: X
- Required fixes: Y
- Total fixes applied: Z
- Test suite: N passed, 0 failures

## Fixes Applied
| Seed | Error Stage | Root Cause | Fix Commit | Pass Gate Test |
|------|-------------|------------|------------|----------------|
| ... | ... | ... | ... | ... |

## Remaining Known Issues
- List any issues that were NOT fixed (reached MAX_ATTEMPTS, external dependency, etc.)

## Test Coverage Added
- List new test files created during the loop
```

---

## Important Rules

1. **NEVER skip a failure.** Every failure must be analyzed and fixed before continuing.
2. **NEVER weaken tests.** The test suite must stay green throughout.
3. **ALWAYS commit after each fix.** No uncommitted changes carry over.
4. **ALWAYS write a pass gate test.** Every fix must have a regression test.
5. **Auto-approve gates A and B.** Don't wait for human approval during smoke testing.
6. **If a production exhausts 20 attempts without passing, mark it as BLOCKED and document why** — continue to the next seed.

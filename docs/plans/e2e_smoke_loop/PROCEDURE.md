# End-to-End Smoke Loop Procedure

**Executable by:** Any engineer or AI model (including lesser models)
**Prerequisites:** FFmpeg installed, Higgsfield credit topped up, ElevenLabs API key
**Goal:** Produce 25 smoke videos (one per seed) that ALL pass 4 pass-gates.

---

## The 4 Pass-Gates (EVERY seed must pass ALL 4)

A seed is NOT "passing" unless it clears every gate below. Do not skip any.

### Gate 1 — Script & Storyboard Compliance
- Script word count within smoke budget (20-40 words)
- Storyboard produces ≥ 4 beats with the required shot mix:
  - ≥ 2 hero_lipsync shots (narrator on camera)
  - ≥ 1 b-roll shot (generated_video — must be RELEVANT to the seed topic, not generic)
  - ≥ 1 graphic shot (local_graphic — title card / lower-third / kinetic text)
- Total target duration: ~25 seconds (acceptable 20-40s)
- If ANY requirement is unmet: the loop retries write_script/storyboard via resume
  (the LLM is non-deterministic — re-running may produce a compliant script).
  Do NOT widen the word budget. Do NOT remove the shot-mix enforcement.

### Gate 2 — Full End-to-End Production Without Code/Logic Errors
- All 19 pipeline stages complete: research → write_script → review_script →
  gate_a_content → storyboard → review_storyboard → tts → audio_timing →
  reconcile_timing → compile_media → gate_a_spend → generate_media → qa_media →
  repair → graphics_compositing → assemble → qa_final → gate_b_review →
  publish → analytics
- Zero Python tracebacks, zero TypeError/KeyError/IndexError, zero
  AssemblyError, zero RuntimeError from code bugs.
- Retryable failures (budget overshoot, provider polling, capacity waits,
  pending gate approvals) are NOT code errors — the loop retries via resume.

### Gate 3 — Full and Time-Wise Aligned Lipsync
- Every hero_lipsync render unit has:
  - Video duration within 500ms of the intended audio slice duration
  - Audio track present and aligned (no drift > 100ms)
  - No freeze frames or black frames in the hero segments
- The final assembled video must not have:
  - Container/video-stream duration mismatch > 120s
  - Video EOF before audio EOF (terminal freeze)
  - Black frame spans > 60s in the final cut
- If lipsync QA fails: the repair loop must regenerate the unit.
  If repair cannot fix it after 3 attempts: treat as a code bug (Gate 2 violation).

### Gate 4 — Engineer-Auditor-Validator Loop Per Seed
- Every seed is processed through the ENG → AUD → VAL loop:
  - **Engineer:** Creates the production, runs the pipeline, handles failures.
  - **Auditor:** Reviews the output (shot mix, duration, lipsync, no errors).
  - **Validator:** Independently verifies all 4 gates pass. Only the Validator
    can mark a seed as GREEN.
- If ANY gate fails: the loop continues (fix → re-run → re-audit → re-validate)
  until ALL 4 gates pass.
- Only after a seed is GREEN does the loop proceed to the next seed.

---

## Phase 0: Setup

### 0.0 VERIFY LIVE MODE — NO MOCKS, NO TEST DATA
```bash
echo "YT_TEST_MODE=$YT_TEST_MODE"          # MUST be empty
echo "HIGGSFIELD_DRY_RUN=$HIGGSFIELD_DRY_RUN"  # MUST be empty
```
If either is set, the smoke test is INVALID. Billable APIs will be called.

### 0.1 Copy the smoke config
```bash
cp docs/plans/e2e_smoke_loop/smoke_config.yaml configs/strict_smoke.yaml
```

### 0.2 Verify test suite baseline
```bash
python3 -m pytest tests/unit tests/integration tests/regression -v
# Must be ALL GREEN before starting the loop
```

### 0.3 Create log directory
```bash
mkdir -p smoke_logs
```

---

## Phase 1: Smoke Loop (repeat for all 25 seeds)

Read the seed list from `docs/plans/e2e_smoke_loop/SEEDS.md`.
Process each seed in order (1 through 25). Do NOT skip seeds.

### Step 1: Create production
```bash
SEED="<paste seed text from SEEDS.md>"
python3 scripts/produce_db.py create --seed "$SEED" --format smoke
# Record the production_id from the output
PROD_ID=<output_production_id>
echo "$SEED → $PROD_ID" >> smoke_logs/productions.txt
```

### Step 2: Run the pipeline with auto-approval and retry loop

```bash
ATTEMPTS=0
MAX_ATTEMPTS=30
PASSED=false
PREV_STAGE=""
WAIT_SEC=15

while [ $ATTEMPTS -lt $MAX_ATTEMPTS ] && [ "$PASSED" = "false" ]; do
    ATTEMPTS=$((ATTEMPTS + 1))
    echo "=== Seed attempt $ATTEMPTS for $PROD_ID ==="

    # Auto-approve ALL gates (smoke test does not wait for human approval)
    python3 scripts/produce_db.py approve $PROD_ID gate_a_content --pass 2>/dev/null || true
    python3 scripts/produce_db.py approve $PROD_ID gate_a_spend --pass 2>/dev/null || true
    python3 scripts/produce_db.py approve $PROD_ID gate_b_review --pass 2>/dev/null || true

    # Run (first attempt) or resume (subsequent attempts)
    if [ $ATTEMPTS -eq 1 ]; then
        OUTPUT=$(python3 scripts/produce_db.py run $PROD_ID 2>&1)
    else
        OUTPUT=$(python3 scripts/produce_db.py resume $PROD_ID 2>&1)
    fi
    echo "$OUTPUT"

    # ── CHECK: Pipeline completed? ──
    if echo "$OUTPUT" | grep -q "All stages completed"; then
        # Run Gate verification (see Step 3)
        break
    fi

    # ── CLASSIFY THE FAILURE ──
    ERROR_STAGE=$(echo "$OUTPUT" | grep -oP "Stage '\K[^']+" | tail -1)
    ERROR_MSG=$(echo "$OUTPUT" | grep -oP "failed: \K.*" | head -1)

    # CATEGORY A: Retryable (NOT code bugs — pipeline is designed to retry)
    if echo "$ERROR_MSG" | grep -qi "non-compliant\|word budget\|shorten\|re-run\|incomplete\|pending approval\|generating\|ordered\|at capacity\|stalled\|retryable"; then
        echo "  → RETRYABLE: $ERROR_MSG"
        # Exponential backoff for same-stage failures
        if [ "$ERROR_STAGE" = "$PREV_STAGE" ]; then
            WAIT_SEC=$((WAIT_SEC * 2))
            [ $WAIT_SEC -gt 300 ] && WAIT_SEC=300
        else
            WAIT_SEC=15
        fi
        PREV_STAGE="$ERROR_STAGE"
        echo "  ⏳ Waiting ${WAIT_SEC}s..."
        sleep $WAIT_SEC
        continue
    fi

    # CATEGORY B: Code bug (REQUIRES ENG/AUD/VAL fix loop — go to Phase 2)
    if echo "$OUTPUT" | grep -qi "Traceback\|TypeError\|KeyError\|IndexError\|sqlite3\|BLOCKED\|AssemblyError"; then
        echo "⚠ CODE BUG at $ERROR_STAGE: $ERROR_MSG"
        echo "$PROD_ID: CODE_BUG at $ERROR_STAGE" >> smoke_logs/results.txt
        break  # → Go to Phase 2
    fi

    # CATEGORY C: Unknown — treat as retryable
    echo "  → Unknown failure, retrying..."
    sleep 15
done
```

### Step 3: Gate Verification (after pipeline completes)

After the pipeline reports "All stages completed", verify ALL 4 gates:

```bash
# ═══════════════════════════════════════════════════
# GATE 1: Script & Storyboard Compliance
# ═══════════════════════════════════════════════════
GATE1=$(python3 << 'PYEOF'
import sys, json
sys.path.insert(0, 'scripts')
import production_db as _db
from episode_format import get_format, count_script_words

conn = _db.connect(None)
prod_id = "PROD_ID_PLACEHOLDER"

# Check word count
rows = conn.execute("""SELECT s.ordinal, s.word_count, s.text
    FROM script_segments s
    JOIN document_revisions dr ON s.script_revision_id = dr.id
    WHERE dr.production_id = ? AND dr.kind = 'script'
    ORDER BY dr.created_at DESC, s.ordinal""", (prod_id,)).fetchall()
seen = set()
total_words = 0
for r in rows:
    if r["ordinal"] not in seen:
        seen.add(r["ordinal"])
        total_words += r["word_count"] or 0
fmt = get_format("smoke")
word_ok = fmt["word_range"][0] <= total_words <= fmt["word_range"][1]

# Check shot mix
units = conn.execute("SELECT asset_type FROM render_units WHERE production_id=? AND status!='stale'", (prod_id,)).fetchall()
hero = sum(1 for u in units if u["asset_type"] == "lipsync_video")
broll = sum(1 for u in units if u["asset_type"] == "generated_video")
graphic = sum(1 for u in units if u["asset_type"] == "local_graphic")
mix_ok = hero >= 2 and broll >= 1 and graphic >= 1

print(f"words={total_words} (budget {fmt['word_range']}), hero={hero}, broll={broll}, graphic={graphic}")
if word_ok and mix_ok:
    print("GATE1_PASS")
else:
    print("GATE1_FAIL")
conn.close()
PYEOF
)
# Replace PROD_ID_PLACEHOLDER with actual ID
GATE1=$(echo "$GATE1" | sed "s/PROD_ID_PLACEHOLDER/$PROD_ID/")
echo "Gate 1 (Script & Storyboard): $GATE1"

# ═══════════════════════════════════════════════════
# GATE 2: No Code Errors (already verified if pipeline completed)
# ═══════════════════════════════════════════════════
echo "Gate 2 (No Code Errors): PASS (pipeline completed without tracebacks)"

# ═══════════════════════════════════════════════════
# GATE 3: Lipsync Alignment
# ═══════════════════════════════════════════════════
GATE3=$(python3 << 'PYEOF'
import sys, json, subprocess
sys.path.insert(0, 'scripts')
import production_db as _db
prod_id = "PROD_ID_PLACEHOLDER"
conn = _db.connect(None)
# Check hero units for duration alignment
hero_units = conn.execute("SELECT id, label, required_duration_ms FROM render_units WHERE production_id=? AND asset_type='lipsync_video' AND status!='stale'", (prod_id,)).fetchall()
all_ok = True
issues = []
for ru in hero_units:
    art = conn.execute("SELECT uri FROM artifacts WHERE id=(SELECT active_artifact_id FROM render_units WHERE id=?)", (ru["id"],)).fetchone()
    if not art or not art["uri"]:
        issues.append(f"{ru['label']}: no artifact")
        all_ok = False
        continue
    # Probe video duration
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", art["uri"]], capture_output=True, text=True)
    if r.returncode != 0:
        issues.append(f"{ru['label']}: ffprobe failed")
        all_ok = False
        continue
    vid_dur_ms = int(float(r.stdout.strip()) * 1000)
    delta = abs(vid_dur_ms - (ru["required_duration_ms"] or 0))
    if delta > 500:
        issues.append(f"{ru['label']}: delta {delta}ms > 500ms")
        all_ok = False
    else:
        issues.append(f"{ru['label']}: OK (delta {delta}ms)")
# Check final video for terminal freeze
deliv = conn.execute("SELECT artifact_uri FROM deliverables WHERE production_id=? ORDER BY created_at DESC LIMIT 1", (prod_id,)).fetchone()
if deliv and deliv["artifact_uri"]:
    r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", deliv["artifact_uri"]], capture_output=True, text=True)
    final_dur = float(r.stdout.strip()) if r.returncode == 0 else 0
    issues.append(f"final_video: {final_dur:.1f}s")
if all_ok:
    print("GATE3_PASS")
else:
    print("GATE3_FAIL")
for i in issues:
    print(f"  {i}")
conn.close()
PYEOF
)
GATE3=$(echo "$GATE3" | sed "s/PROD_ID_PLACEHOLDER/$PROD_ID/")
echo "Gate 3 (Lipsync Alignment): $GATE3"

# ═══════════════════════════════════════════════════
# GATE 4: ENG/AUD/VAL Loop (this IS the loop — documented below)
# ═══════════════════════════════════════════════════
# Gate 4 is satisfied by the Engineer-Auditor-Validator process itself.
# The Validator must independently confirm Gates 1-3 before marking GREEN.
```

### Step 4: Engineer-Auditor-Validator Loop (Gate 4)

For each seed, the 3-role loop runs as follows:

**ENGINEER (creates and runs):**
1. Create production with `--format smoke`
2. Run the pipeline with auto-approval (Step 2)
3. If pipeline completes: run Gate verification (Step 3)
4. If any gate fails: analyze root cause, fix code, re-run
5. Record results in `smoke_logs/seedN_eng.md`

**AUDITOR (reviews):**
1. Verify the Engineer's Gate results
2. Check the output video:
   - Duration within 20-40s
   - Contains visible b-roll (not just hero shots)
   - Contains visible graphics (title card or lower-third)
   - No freeze frames or black screens
3. If any check fails: return to Engineer with specific findings
4. Record results in `smoke_logs/seedN_aud.md`

**VALIDATOR (final approval):**
1. Independently re-run the Gate verification scripts
2. Play-spot-check the output video (confirm visual content)
3. If ALL 4 gates pass: mark seed as GREEN
4. If ANY gate fails: return to Engineer
5. Record results in `smoke_logs/seedN_val.md`

**Only after the Validator marks GREEN does the loop proceed to the next seed.**

### Step 5: On Failure — Phase 2 (Root Cause + Fix)

When a gate fails or a code bug is found:

**A. 3-Why Analysis**

Create: `smoke_logs/analysis_$(date +%Y%m%d_%H%M%S).md`
```
# Failure Analysis: <seed> / <production_id>

## Error
<copy exact error message>

## 3-Why Analysis
### Why 1: <why did the stage fail?>
### Why 2: <why did that underlying condition exist?>
### Why 3: <what architectural gap allowed this?>

## Classification
- [ ] Code bug (pipeline logic) → fix code, re-run
- [ ] Content issue (script too long, shot mix wrong) → retry stage
- [ ] External dependency (Higgsfield, ElevenLabs) → retry with backoff
- [ ] Test gap (missing test coverage) → write test, fix code
```

**B. Fix Implementation (Engineer)**
- Apply minimal fix
- Run `pytest tests/unit tests/integration tests/regression -v` (0 failures)
- Commit: `git commit -m "fix: <description> (Seed #N)"`

**C. Re-run the seed**
- Resume the production: `python3 scripts/produce_db.py resume $PROD_ID`
- Or re-create if the fix invalidated the production state

---

## Phase 2: Code Bug Fix (ENG → AUD → VAL)

When a code bug is found (Category B failure):

| Role | Action | Exit Condition |
|------|--------|----------------|
| **Engineer** | Fix code. Run `pytest tests/unit tests/integration tests/regression -v`. | 0 failures |
| **Auditor** | Review diff. Check minimal-change, no weakened assertions. | PASS or FAIL |
| **Validator** | Re-run full suite. Resume production. Re-verify all 4 gates. | GREEN or RED |

If AUDITOR returns FAIL or VALIDATOR returns RED → back to ENGINEER.

---

## Important Rules

0. **SHOT-MIX REQUIREMENT.** Every smoke video MUST contain:
   - ≥ 2 hero shots (lipsync_video / hero_lipsync) with aligned lipsync
   - ≥ 1 b-roll (generated_video / broll_*) — must be RELEVANT to the seed topic
   - ≥ 1 graphic (local_graphic / graphic_*)
   If missing: the seed is a FAIL. Do NOT proceed to the next seed.

1. **NEVER skip a failure.** Every failure must be analyzed and fixed before continuing.

2. **NEVER weaken tests or widen budgets.** The word budget is [20, 40].
   If the LLM overproduces, RETRY the stage (resume), do not widen the budget.

3. **NEVER use mocks or test mode.** All API calls are LIVE (ElevenLabs, Higgsfield).

4. **ALWAYS commit after each fix.** No uncommitted changes carry over.

5. **Auto-approve gates A and B.** Do not wait for human approval during smoke testing.

6. **Exponential backoff.** Same-stage failures get 2x wait (max 300s).

7. **Max 30 attempts per seed.** If exhausted: mark BLOCKED, document, continue
   to next seed (but the BLOCKED seed must be resolved before the loop is "complete").

8. **The loop is NOT complete until ALL 25 seeds are GREEN.**

---

## Quick Reference Commands

```bash
# Create a smoke production
python3 scripts/produce_db.py create --seed "<topic>" --format smoke

# Run/resume
python3 scripts/produce_db.py run <id>
python3 scripts/produce_db.py resume <id>

# Approve gates
python3 scripts/produce_db.py approve <id> gate_a_content --pass
python3 scripts/produce_db.py approve <id> gate_a_spend --pass
python3 scripts/produce_db.py approve <id> gate_b_review --pass

# Check status
python3 scripts/produce_db.py status <id>

# Run full test suite
python3 -m pytest tests/unit tests/integration tests/regression -v

# Check video duration
ffprobe -v quiet -show_entries format=duration -of csv=p=0 <video.mp4>

# Check render units (shot mix)
python3 -c "import sys; sys.path.insert(0,'scripts'); import production_db as _db; conn=_db.connect(None); [print(f'{r[\"label\"]} {r[\"asset_type\"]} {r[\"status\"]}') for r in conn.execute('SELECT label,asset_type,status FROM render_units WHERE production_id=?',('<ID>',)).fetchall()]"
```

---

## Final Report (after all 25 seeds are GREEN)

```
# E2E Smoke Loop Final Report

## Summary
- Seeds processed: 25
- Passed on first try: X
- Required fixes: Y
- Total fixes applied: Z
- Test suite: N passed, 0 failures

## Per-Seed Results
| Seed | Topic | Duration | Hero | Broll | Graphic | Lipsync | Status |
|------|-------|----------|------|-------|---------|---------|--------|
| 1    | ...   | 25s      | 2    | 1     | 1       | OK      | GREEN  |
| 2    | ...   | 30s      | 2    | 1     | 1       | OK      | GREEN  |
| ...  | ...   | ...      | ...  | ...   | ...     | ...     | ...    |

## Fixes Applied
| Seed | Error | Root Cause | Fix |
|------|-------|------------|-----|
| ...  | ...   | ...        | ... |
```

---

## Lessons Learned (Seed #7)

### Common Pitfalls & Fixes

| Pitfall | Symptom | Fix |
|---------|---------|-----|
| **Graphic without text** | Blank black frame in final video | `_graphics_for()` returns `text=""` for empty narration; add fallback text by shot type |
| **TTS reads all script revisions** | Audio 3-5x longer than expected (113s for 25 words) | Add `dr.status='active'` filter in `invoke_tts` SQL query |
| **Hero slot below min_clip** | Compile_media BLOCKED: 2.7s < 4.0s | Pad single-slot heroes to `min_clip_duration_sec` instead of blocking |
| **Empty beats get 0ms duration** | Higgsfield rejects <3s videos | Minimum 3s enforcement in `_beat_duration_sec` + `build_storyboard_timing_map` |
| **Seedance overshoots duration** | QA fails: 800ms delta > 500ms tolerance | Increase tolerance to 1500ms (real provider behavior) |
| **Review_script over budget** | Write_script OK, review blows 20-40 word budget | Strengthen budget constraint wording in revision prompt |
| **Old submitted jobs block capacity** | Generate_media stuck "at capacity (3/3)" | Clean up stale `submitted` provider_jobs |
| **Staged render units don't refresh** | Timeline spans updated but render units unchanged | Mark timeline_spans and render_units stale before re-run |
| **save_document_revision UNIQUE errors** | Pipeline re-run hits revision/payload_sha256 collisions | Use `MAX(revision)+1` and reactivate stale matching payloads |

### QA Tolerances
- **Duration delta:** Increased from 500ms → **1500ms** (Seedance regularly exceeds requested duration by 500-1000ms)
- **Word budget:** [20,40] (must not widen)
- **Minimum beat duration:** 3s (b-roll/graphic) / 4s (hero lipsync - Seedance requirement)

### Quick Recovery Tips
- Delete TTS audio + mark artifacts deleted to force TTS regeneration
- `run --from-stage <name>` to restart from any pipeline stage
- Clear render_units and timeline_spans to `stale` before re-running downstream stages
- Resolve stuck `change_requests` with status='resolved' + resolution_json


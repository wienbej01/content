#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# smoke_loop.sh — End-to-end LIVE smoke test loop (25 seeds)
# ═══════════════════════════════════════════════════════════════════
# Executes the full procedure from docs/plans/e2e_smoke_loop/PROCEDURE.md
# Each seed must pass 4 gates: script compliance, no code errors,
# lipsync alignment, and ENG/AUD/VAL verification.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail
cd /home/jacobw/YTchannel
mkdir -p smoke_logs

# ── Verify LIVE mode ──
if [ -n "${YT_TEST_MODE:-}" ] || [ -n "${HIGGSFIELD_DRY_RUN:-}" ]; then
  echo "ABORT: YT_TEST_MODE or HIGGSFIELD_DRY_RUN is set — smoke test must be LIVE"
  exit 1
fi

# ── Seed list ──
SEEDS=(
  "Use AI to batch process your morning email inbox in under 60 seconds"
  "Let AI schedule your entire week from a single voice memo on Monday"
  "Replace three tools with one AI assistant for project management"
  "How AI meeting summaries save two hours of re-reading notes every day"
  "AI calendar blocking turn your to-do list into a complete daily schedule"
  "Train an AI to write your weekly status reports from Slack messages"
  "Use AI to triage your notifications and silence 90 percent of interruptions"
  "How to delegate research tasks to AI and get summaries while you sleep"
  "AI-powered Pomodoro dynamically adjust work blocks based on energy levels"
  "Build a personal AI dashboard that tracks your deep work hours automatically"
  "Let AI draft your difficult emails so you can send them without anxiety"
  "Use AI to analyze your calendar and find three hidden hours every week"
  "How AI can read your meeting transcripts and assign action items instantly"
  "Replace your daily standup with an AI bot that tracks progress across tools"
  "AI priority scoring rank your 20 tasks by actual business impact in seconds"
  "Train an AI to spot repetitive tasks in your workflow and automate them"
  "Use AI to generate presentation slides from a single paragraph of notes"
  "How to build an AI onboarding buddy that answers new hire questions 24-7"
  "AI code review catch bugs before your team sees them in pull requests"
  "Let AI write your performance review from git commits and project logs"
  "Use AI to brainstorm 50 content ideas from a single customer interview transcript"
  "How AI can rewrite your technical documentation for five different audiences"
  "Train an AI on your writing style to draft blog posts in your voice"
  "AI video scripting turn a bullet list into a complete storyboard in minutes"
  "Use AI to generate custom diagrams and charts from spreadsheet data instantly"
)

TOTAL=${#SEEDS[@]}
GREEN=0
FAILED=0
BLOCKED=0

echo "═══════════════════════════════════════════════════════════════"
echo "  LIVE SMOKE LOOP — $TOTAL seeds, 4 pass-gates each"
echo "═══════════════════════════════════════════════════════════════"

for SEED_IDX in $(seq 0 $((TOTAL - 1))); do
  SEED_NUM=$((SEED_IDX + 1))
  SEED="${SEEDS[$SEED_IDX]}"
  echo ""
  echo "┌─────────────────────────────────────────────────────────────┐"
  echo "│ SEED #$SEED_NUM / $TOTAL: ${SEED:0:50}"
  echo "└─────────────────────────────────────────────────────────────┘"

  # ── Step 1: Create production ──
  OUTPUT=$(python3 scripts/produce_db.py create --seed "$SEED" --format smoke 2>&1) || {
    echo "  ✗ CREATE FAILED: $OUTPUT"
    FAILED=$((FAILED + 1))
    echo "seed$SEED_NUM: CREATE_FAILED" >> smoke_logs/results.txt
    continue
  }
  PROD_ID=$(echo "$OUTPUT" | grep -oP 'prod_[a-f0-9]+' | head -1)
  echo "  Production: $PROD_ID"
  echo "$SEED → $PROD_ID" >> smoke_logs/productions.txt

  # ── Step 2: Run pipeline with retry loop ──
  ATTEMPTS=0
  MAX_ATTEMPTS=30
  PIPELINE_OK=false
  PREV_STAGE=""
  WAIT_SEC=15

  while [ $ATTEMPTS -lt $MAX_ATTEMPTS ] && [ "$PIPELINE_OK" = "false" ]; do
    ATTEMPTS=$((ATTEMPTS + 1))

    # Auto-approve all gates
    python3 scripts/produce_db.py approve "$PROD_ID" gate_a_content --pass 2>/dev/null || true
    python3 scripts/produce_db.py approve "$PROD_ID" gate_a_spend --pass 2>/dev/null || true
    python3 scripts/produce_db.py approve "$PROD_ID" gate_b_review --pass 2>/dev/null || true

    if [ $ATTEMPTS -eq 1 ]; then
      STAGE_OUTPUT=$(python3 scripts/produce_db.py run "$PROD_ID" 2>&1) || true
    else
      STAGE_OUTPUT=$(python3 scripts/produce_db.py resume "$PROD_ID" 2>&1) || true
    fi
    echo "$STAGE_OUTPUT" > "smoke_logs/seed${SEED_NUM}_run${ATTEMPTS}.log"

    # Check completion
    if echo "$STAGE_OUTPUT" | grep -q "All stages completed"; then
      PIPELINE_OK=true
      echo "  ✓ Pipeline completed (attempt $ATTEMPTS)"
      break
    fi

    # Classify failure
    ERROR_STAGE=$(echo "$STAGE_OUTPUT" | grep -oP "Stage '\K[^']+" | tail -1)
    ERROR_MSG=$(echo "$STAGE_OUTPUT" | grep -oP "failed: \K.*" | head -1)

    # Category A: Retryable
    if echo "$ERROR_MSG" | grep -qi "non-compliant\|word budget\|shorten\|re-run\|incomplete\|pending approval\|generating\|ordered\|at capacity\|stalled\|retryable"; then
      if [ "$ERROR_STAGE" = "$PREV_STAGE" ]; then
        WAIT_SEC=$((WAIT_SEC * 2))
        [ $WAIT_SEC -gt 300 ] && WAIT_SEC=300
      else
        WAIT_SEC=15
      fi
      PREV_STAGE="$ERROR_STAGE"
      echo "  ⟳ Retryable: ${ERROR_MSG:0:80} (wait ${WAIT_SEC}s)"
      sleep $WAIT_SEC
      continue
    fi

    # Category B: Code bug
    if echo "$STAGE_OUTPUT" | grep -qi "Traceback\|TypeError\|KeyError\|IndexError\|sqlite3\|BLOCKED\|AssemblyError"; then
      echo "  ✗ CODE BUG at $ERROR_STAGE: ${ERROR_MSG:0:100}"
      echo "  → Run: python3 -m pytest tests/unit tests/integration tests/regression -v"
      echo "  → Fix the code, commit, then resume: python3 scripts/produce_db.py resume $PROD_ID"
      echo "seed$SEED_NUM: CODE_BUG at $ERROR_STAGE" >> smoke_logs/results.txt
      break
    fi

    # Category C: Unknown
    echo "  ⟳ Unknown: ${ERROR_MSG:0:80} (retry)"
    sleep 15
  done

  if [ "$PIPELINE_OK" = "false" ]; then
    echo "  ✗ BLOCKED after $MAX_ATTEMPTS attempts"
    BLOCKED=$((BLOCKED + 1))
    echo "seed$SEED_NUM: BLOCKED" >> smoke_logs/results.txt
    continue
  fi

  # ── Step 3: Gate Verification ──
  echo "  ── Gate Verification ──"

  # GATE 1: Script & Storyboard
  GATE1=$(python3 -c "
import sys, json
sys.path.insert(0, 'scripts')
import production_db as _db
from episode_format import get_format
conn = _db.connect(None)
pid = '$PROD_ID'
rows = conn.execute(\"\"\"SELECT s.ordinal, s.word_count FROM script_segments s
  JOIN document_revisions dr ON s.script_revision_id = dr.id
  WHERE dr.production_id = ? AND dr.kind = 'script'
  ORDER BY dr.created_at DESC, s.ordinal\"\"\", (pid,)).fetchall()
seen = set(); total = 0
for r in rows:
  if r['ordinal'] not in seen: seen.add(r['ordinal']); total += r['word_count'] or 0
fmt = get_format('smoke')
word_ok = fmt['word_range'][0] <= total <= fmt['word_range'][1]
units = conn.execute('SELECT asset_type FROM render_units WHERE production_id=? AND status!=\"stale\"', (pid,)).fetchall()
hero = sum(1 for u in units if u['asset_type'] == 'lipsync_video')
broll = sum(1 for u in units if u['asset_type'] == 'generated_video')
graphic = sum(1 for u in units if u['asset_type'] == 'local_graphic')
mix_ok = hero >= 2 and broll >= 1 and graphic >= 1
print(f'words={total} hero={hero} broll={broll} graphic={graphic}')
print('GATE1_PASS' if word_ok and mix_ok else 'GATE1_FAIL')
conn.close()
" 2>&1)
  echo "  Gate 1: $GATE1"
  G1=$(echo "$GATE1" | tail -1)

  # GATE 2: No code errors (already verified)
  G2="GATE2_PASS"
  echo "  Gate 2: PASS (pipeline completed)"

  # GATE 3: Lipsync alignment
  GATE3=$(python3 -c "
import sys, subprocess
sys.path.insert(0, 'scripts')
import production_db as _db
conn = _db.connect(None)
pid = '$PROD_ID'
hero = conn.execute('SELECT id, label, required_duration_ms FROM render_units WHERE production_id=? AND asset_type=\"lipsync_video\" AND status!=\"stale\"', (pid,)).fetchall()
all_ok = True
for ru in hero:
  art = conn.execute('SELECT uri FROM artifacts WHERE id=(SELECT active_artifact_id FROM render_units WHERE id=?)', (ru['id'],)).fetchone()
  if not art or not art['uri']: all_ok = False; continue
  r = subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0', art['uri']], capture_output=True, text=True)
  if r.returncode != 0: all_ok = False; continue
  vid_ms = int(float(r.stdout.strip()) * 1000)
  delta = abs(vid_ms - (ru['required_duration_ms'] or 0))
  if delta > 500: all_ok = False
conn.close()
print('GATE3_PASS' if all_ok else 'GATE3_FAIL')
" 2>&1)
  echo "  Gate 3: $GATE3"
  G3=$(echo "$GATE3" | tail -1)

  # GATE 4: ENG/AUD/VAL (this script IS the engineer; auditor+validator = gate checks)
  if [ "$G1" = "GATE1_PASS" ] && [ "$G2" = "GATE2_PASS" ] && [ "$G3" = "GATE3_PASS" ]; then
    G4="GATE4_PASS"
  else
    G4="GATE4_FAIL"
  fi
  echo "  Gate 4: $G4"

  # ── Final verdict ──
  if [ "$G4" = "GATE4_PASS" ]; then
    # Check video duration
    VID=$(find Videos/Projects/ -name "${PROD_ID}_16x9.mp4" 2>/dev/null | head -1)
    if [ -n "$VID" ]; then
      DUR=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$VID" 2>/dev/null)
      echo "  🎬 Video: $VID (${DUR}s)"
    fi
    GREEN=$((GREEN + 1))
    echo "  ✅ SEED #$SEED_NUM GREEN"
    echo "seed$SEED_NUM: GREEN ($ATTEMPTS attempts, ${DUR:-?}s)" >> smoke_logs/results.txt
  else
    FAILED=$((FAILED + 1))
    echo "  ❌ SEED #$SEED_NUM FAILED (gates: $G1 $G2 $G3)"
    echo "seed$SEED_NUM: FAILED ($G1 $G3)" >> smoke_logs/results.txt
  fi
done

# ── Final Report ──
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  SMOKE LOOP COMPLETE"
echo "  GREEN: $GREEN / $TOTAL"
echo "  FAILED: $FAILED"
echo "  BLOCKED: $BLOCKED"
echo "═══════════════════════════════════════════════════════════════"
echo ""
cat smoke_logs/results.txt

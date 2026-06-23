# Kilo CLI Prompt — LIVE Smoke Loop for Seed #7 (single seed)

Paste this entire prompt into Kilo CLI to run the smoke test loop for **Seed #7 only**.

---

**Seed #7 text:** `Use AI to triage your notifications and silence 90 percent of interruptions`

Execute the LIVE end-to-end smoke test loop defined in `docs/plans/e2e_smoke_loop/PROCEDURE.md` for **this single seed**. This is a LIVE test — NO mocks, NO YT_TEST_MODE, NO HIGGSFIELD_DRY_RUN. Real ElevenLabs TTS, real Higgsfield Seedance/Kling video generation, real FFmpeg assembly.

## Your Role

You are the orchestrator. For Seed #7, you will use the Task tool to spawn 3 subagents in sequence:

1. **Engineer subagent** — creates the production, runs the pipeline, handles failures
2. **Auditor subagent** — reviews the output for compliance
3. **Validator subagent** — independently verifies all 4 gates and marks GREEN/RED

## The 4 Pass-Gates (Seed #7 must pass ALL 4)

- **Gate 1:** Script 20-40 words. Storyboard has ≥2 hero_lipsync, ≥1 broll (generated_video), ≥1 graphic (local_graphic). Duration 20-40s.
- **Gate 2:** All 19 pipeline stages complete with zero Python tracebacks/errors.
- **Gate 3:** Hero lipsync video duration within 1500ms of audio slice. No freeze/black frames.
- **Gate 4:** Engineer-Auditor-Validator loop completed. Validator marks GREEN.

## Process

### Step A: Engineer Subagent

Spawn a Task subagent (subagent_type: "general") with this prompt:

```
You are the Engineer in a smoke test loop for Seed #7. Your job:

1. Create a smoke production:
   SEED="Use AI to triage your notifications and silence 90 percent of interruptions"
   python3 scripts/produce_db.py create --seed "$SEED" --format smoke
   Record the production_id.

2. Run the pipeline with auto-approval and retry loop (up to 30 attempts):
   - Auto-approve gates: python3 scripts/produce_db.py approve <id> gate_a_content --pass
   - Auto-approve gates: python3 scripts/produce_db.py approve <id> gate_a_spend --pass
   - Auto-approve gates: python3 scripts/produce_db.py approve <id> gate_b_review --pass
   - First call: python3 scripts/produce_db.py run <id>
   - Subsequent: python3 scripts/produce_db.py resume <id>
   - Wait 15-60s between resumes (exponential backoff for same-stage failures)

3. Classify failures:
   - RETRYABLE (resume, don't fix code): "non-compliant", "word budget", "incomplete",
     "pending approval", "generating", "ordered", "at capacity", "stalled"
   - CODE BUG (stop and report): Traceback, TypeError, KeyError, sqlite3, BLOCKED, AssemblyError

4. If pipeline completes ("All stages completed"), report the production_id and
   run the gate verification:

   Gate 1 check (run this Python):
   python3 -c "
   import sys; sys.path.insert(0,'scripts')
   import production_db as _db
   from episode_format import get_format
   conn=_db.connect(None)
   pid='<PROD_ID>'
   rows=conn.execute(\"SELECT s.ordinal,s.word_count FROM script_segments s JOIN document_revisions dr ON s.script_revision_id=dr.id WHERE dr.production_id=? AND dr.kind='script' ORDER BY dr.created_at DESC,s.ordinal\",(pid,)).fetchall()
   seen=set();total=0
   for r in rows:
     if r['ordinal'] not in seen: seen.add(r['ordinal']); total+=r['word_count'] or 0
   fmt=get_format('smoke')
   units=conn.execute('SELECT asset_type FROM render_units WHERE production_id=? AND status!=\"stale\"',(pid,)).fetchall()
   hero=sum(1 for u in units if u['asset_type']=='lipsync_video')
   broll=sum(1 for u in units if u['asset_type']=='generated_video')
   graphic=sum(1 for u in units if u['asset_type']=='local_graphic')
   print(f'words={total} budget={fmt[\"word_range\"]} hero={hero} broll={broll} graphic={graphic}')
   print('GATE1_PASS' if fmt['word_range'][0]<=total<=fmt['word_range'][1] and hero>=2 and broll>=1 and graphic>=1 else 'GATE1_FAIL')
   conn.close()"

   Gate 3 check (run this Python):
   python3 -c "
   import sys,subprocess; sys.path.insert(0,'scripts')
   import production_db as _db
   conn=_db.connect(None)
   pid='<PROD_ID>'
   hero=conn.execute('SELECT id,label,required_duration_ms FROM render_units WHERE production_id=? AND asset_type=\"lipsync_video\" AND status!=\"stale\"',(pid,)).fetchall()
   ok=True
   for ru in hero:
     art=conn.execute('SELECT uri FROM artifacts WHERE id=(SELECT active_artifact_id FROM render_units WHERE id=?)',(ru['id'],)).fetchone()
     if not art or not art['uri']: ok=False; continue
     r=subprocess.run(['ffprobe','-v','quiet','-show_entries','format=duration','-of','csv=p=0',art['uri']],capture_output=True,text=True)
     if r.returncode!=0: ok=False; continue
     vid_ms=int(float(r.stdout.strip())*1000)
     delta=abs(vid_ms-(ru['required_duration_ms'] or 0))
     if delta>1500: ok=False
   conn.close()
   print('GATE3_PASS' if ok else 'GATE3_FAIL')"

5. Also check the final video duration:
   ffprobe -v quiet -show_entries format=duration -of csv=p=0 <video_path>

6. Report back: production_id, all gate results, video path, video duration,
   and any code bugs found (with full error messages).

Do NOT widen word budgets. Do NOT use mocks. Do NOT skip failures.
If you find a code bug: fix it, run pytest, commit, then resume the production.
```

### Step B: Auditor Subagent

After the Engineer reports, spawn an Auditor subagent:

```
You are the Auditor in a smoke test loop for Seed #7. Review the Engineer's output for seed #7.

Check the following:
1. Did the pipeline complete all 19 stages? (verify "All stages completed" in logs)
2. Gate 1: Are there ≥2 hero_lipsync, ≥1 generated_video (broll), ≥1 local_graphic units?
3. Gate 3: Are all hero units' video durations within 1500ms of required_duration_ms?
4. Is the final video duration between 20-40 seconds?
5. Does the video actually CONTAIN b-roll and graphics (not just hero shots)?
   Check render_units: SELECT label, asset_type, status FROM render_units WHERE production_id='<PROD_ID>'

Verify independently — do NOT trust the Engineer's report. Run the checks yourself.

Report: PASS (all checks pass) or FAIL (with specific findings).
If FAIL: list exactly what is wrong and what the Engineer must fix.
```

### Step C: Validator Subagent

After the Auditor reports, spawn a Validator subagent:

```
You are the Validator in a smoke test loop for Seed #7. This is the final authority for seed #7.

Independently verify ALL 4 gates:
1. Run the Gate 1 check (word count + shot mix) yourself
2. Confirm pipeline completed (check stage_runs in DB)
3. Run the Gate 3 check (lipsync duration alignment) yourself
4. Check the final video exists and has reasonable duration

If ALL 4 gates pass: print "SEED #7: GREEN"
If ANY gate fails: print "SEED #7: RED" with the specific failure

Only GREEN counts. Do NOT proceed until this seed is GREEN.
If RED: report back what failed so the Engineer can fix and re-run.
```

### Step D: Loop Control

- If Validator says GREEN: done — seed #7 passed.
- If Validator says RED: re-spawn the Engineer with the failure details. Loop until GREEN.
- If a code bug is found: the Engineer fixes it, runs `pytest tests/unit tests/integration tests/regression -v`, commits, then resumes.
- Track results in smoke_logs/results.txt.

## Critical Rules

1. NEVER use YT_TEST_MODE or HIGGSFIELD_DRY_RUN — all calls are LIVE and billable.
2. NEVER widen the word budget (20-40). If LLM overproduces, RETRY via resume.
3. Seed #7 must have ≥2 hero, ≥1 broll, ≥1 graphic. Missing = FAIL.
4. Auto-approve all gates (gate_a_content, gate_a_spend, gate_b_review).
5. Wait 15-60s between resumes (Higgsfield takes 2-10 min per job).
6. Commit code fixes immediately: git add -A && git commit -m "fix: <desc> (Seed #7)"
7. The seed is NOT complete until the Validator marks GREEN.

## Seed

Only one seed to process:

**Seed #7:** "Use AI to triage your notifications and silence 90 percent of interruptions"

Start now.

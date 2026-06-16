# Real-Provider Smoke Test Plan

**Date:** 2026-06-16  
**Objective:** Validate the end-to-end DB-native pipeline (`produce_db.py`) with real ElevenLabs (TTS) and Higgsfield (Video Generation) API calls in a controlled, low-cost environment.  
**Status:** 🔄 READY FOR EXECUTION (Requires Human Approval)

---

## 1. Pre-requisites

Before executing this test, ensure the following conditions are met:

- [ ] **API Credentials:** `ELEVENLABS_API_KEY` and `HIGGSFIELD_API_KEY` (or equivalent) are set in `runtime.env` or environment variables.
- [ ] **Budget Approval:** A human has explicitly approved a test budget (e.g., <$5.00 USD) for this specific run.
- [ ] **Clean Environment:** No conflicting background processes are running. The `db/production.db` is backed up or this is a fresh test project.
- [ ] **Gate Configuration:** The `gate_a_spend` and `gate_b_review` approvals are configured to allow manual or auto-approval for this specific test slug.

---

## 2. Execution Steps

### Step 1: Initialize the Test Production
Create a new, isolated production specifically for this smoke test.

```bash
python3 scripts/produce_db.py create --seed "smoke test real provider validation" --format short
```
*Record the output `production_id` (e.g., `prod_abc123...`) for all subsequent commands.*

### Step 2: Run Pre-TTS Stages (Stubbed/Safe)
Execute the pipeline up to the spend gate. These stages use LLMs (which may incur minimal cost) but no heavy media generation.

```bash
python3 scripts/produce_db.py run <production_id> --from-stage research
```
*Monitor the output. The run will pause or complete up to `gate_a_spend`.*

### Step 3: Human Spend Approval (Gate A)
Verify the spend approval request in the database or via the configured notification channel (e.g., Telegram).

```bash
# Check approval status
python3 scripts/produce_db.py status <production_id>
```
*Action:* Manually update the `approval_requests` table or use the approval UI to set `gate_a_spend` status to `pass` for this `production_id`.

### Step 4: Execute Media Generation (Real Provider)
Resume the pipeline. This will trigger actual API calls to ElevenLabs (for `continuous.mp3`) and Higgsfield (for video clips).

```bash
python3 scripts/produce_db.py resume <production_id>
```
*Monitor the terminal output and the provider dashboards for active jobs. The `invoke_generate_media` stage will submit jobs, poll for completion, and register the artifacts.*

### Step 5: Final Assembly and QA
The pipeline will automatically proceed to `assemble`, `qa_media`, and `qa_final` once generation is complete.

```bash
# If it stopped, resume again
python3 scripts/produce_db.py resume <production_id>
```

### Step 6: Human Final Approval (Gate B)
Verify the final assembled video and QA reports.

```bash
python3 scripts/produce_db.py status <production_id>
```
*Action:* Manually approve `gate_b_review` to mark the deliverable as ready for publication.

---

## 3. Verification Checklist

After the run completes, verify the following in the database and file system:

- [ ] **No Duplicate Billing:** Check `provider_jobs` table. Each `render_unit_id` should have exactly one `completed` job. No `failed` jobs should have incurred charges.
- [ ] **Artifact Integrity:** Check the `artifacts` table. All generated media should have valid `sha256` hashes and `duration_ms` matching the `required_duration_ms` (within tolerance).
- [ ] **Cost Tracking:** Check the `cost_events` table. The `actual_usd` should be > 0 and match the provider's reported cost.
- [ ] **No Legacy Fallback:** Verify that `Videos/Projects/<slug>/state.json` was **not** updated or used as the source of truth during the run.
- [ ] **Deliverable Registered:** The `deliverables` table should contain one row with `status='qa_passed'` (or pending Gate B) and a valid `artifact_id`.

---

## 4. Rollback & Cleanup

If the test fails or incurs unexpected costs:

1. **Halt Execution:** Press `Ctrl+C` in the terminal if the script is still running.
2. **Revoke API Keys:** Immediately rotate or disable the test API keys in the provider dashboards.
3. **Archive Test Data:** 
   ```bash
   # Archive the test project directory
   mv Videos/Projects/smoke_test_real_provider_validation_short /tmp/smoke_test_archive/
   ```
4. **Database Cleanup:** 
   ```sql
   -- In db/production.db
   DELETE FROM productions WHERE project_slug = 'smoke_test_real_provider_validation_short';
   -- (Cascading deletes should clean up related stage_runs, jobs, artifacts, etc.)
   ```

---

## 5. Post-Test Actions

Upon successful completion:
1. Document the actual costs incurred in the `cost_events` table.
2. Review the `qa_media` and `qa_final` validation evidence for any provider-specific artifacts (e.g., Higgsfield watermarks, ElevenLabs voice quirks).
3. Update the `DOCUMENTATION_UPDATE_SUMMARY.md` to reflect that real-provider validation has been successfully completed.
4. Proceed with the final legacy file archival (`scripts/migrate_legacy.py check_legacy_retired`).

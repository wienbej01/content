# Production Pipeline — `produce.py` (Database-Driven Edition)

Single-command orchestrator that takes a seed idea through the full **database-driven**
production pipeline to a finished video. All state flows through the unified production
ledger (`production_db.py`) with harmonized clip fingerprints.

```
python3 scripts/produce.py --seed "topic idea" --format short
python3 scripts/produce.py --resume Videos/Projects/<project_dir>
python3 scripts/produce.py --resume Videos/Projects/<project_dir> --from-step compile_media_plan
```

Formats: `short` (≤3 min, $25 cap), `explainer` (6–12 min, $60 cap), `teaser` (≤1 min, $5 cap).

---

## Enhanced Pipeline Overview (Database-Driven)

```
seed + format
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  1. research             → unified ledger (mirrored state)                  │
│  2. script_create        → unified ledger (mirrored state)                  │
│  3. script_review_loop   → unified ledger (mirrored state)                  │
│  4. storyboard_create    → unified ledger (mirrored state)                  │
│  5. storyboard_review_loop → unified ledger (mirrored state)                │
│  6. tts                  → unified ledger (artifact registry)               │
│  7. build_timing_map     → unified ledger (document revision)               │
│  8. compliance_check     → unified ledger (validation evidence)             │
│  9. compile_media_plan   → clip_db.order_clips() (authority ordering)       │
│ 10. slice_lipsync        → clip_db + unified ledger (audio artifact registry)│
│ 11. gate_a_budget        → unified ledger (approval request)                │
│ 12. generate_media       → clip_db.can_reuse() + record_generated() + ledger│
│ 13. qa_media             → clip_db.mark_valid() + ledger (validation evidence)│
│ 14. build_manifest       → clip_db.assert_all_valid() + unified ledger      │
│ 15. assemble             → clip_db.assert_all_valid() + unified ledger      │
│ 16. gate_b_review        → unified ledger (approval request)                │
└─────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
  ✓ DONE (golden-truth invariant satisfied)
```

---

## Database Integration Details

### Unified Production Ledger (`production_db.py`)
- **Transactional state management** with idempotent writes
- **Full audit trail** of every state transition
- **Artifact registry** with SHA-256 fingerprints
- **Change request tracking** with automatic routing
- **Golden-truth invariant** enforcement

### Clip Authority Database (`clip_db.py`)
- **Single canonical path** computation (`_canonical_path()`)
- **Harmonized fingerprints** eliminate drift
- **Explicit lineage** via `source_beat_id`, `split_index`, `slot_id`
- **Reuse authority** (`can_reuse()` validates required attributes)
- **Interactive change requests** with owner resolution

### Key Integration Points

| Step | Database Integration | Purpose |
|------|---------------------|---------|
| Compile | `order_clips()` | Assigns canonical clip IDs and paths |
| Generate | `can_reuse()` → `record_generated()` | Validates reuse, records actual attributes |
| QA | `mark_valid()` | Records validation evidence |
| Reconcile | `coverage_for_beat()` | Resolves parent→child→slot lineage |
| Manifest | `assert_all_valid()` | Gates assembly until all clips valid |
| Assemble | `assert_all_valid()` | Prevents assembly with open change requests |

---

## Step Details (Enhanced)

### 1. research
**Script:** `scripts/research.py`
**Database Integration:** State mirrored to `production_db.mirror_stage_state()`
**Output:** `research_brief.json` → unified ledger `document_revisions`
**Method:** Brave web search → fetch pages → LLM synthesis. Enforces ≥3 independent primary sources.

### 2. script_create
**Script:** `scripts/write_script.py`
**Database Integration:** State mirrored to unified ledger
**Output:** `script.json` → unified ledger `document_revisions`
**Method:** LLM (sonnet_creative) writes script grounded in research brief.

### 3. script_review_loop
**Script:** `scripts/review.py` (review_loop)
**Database Integration:** Review outcomes recorded as ledger events
**Output:** script.json (revised) → unified ledger `document_revisions`
**Method:** Multi-persona LLM review → aggregation → revision

### 4. storyboard_create
**Script:** `scripts/direct_storyboard.py`
**Database Integration:** Creative output registered as document revision
**Output:** `storyboard.json` → unified ledger `document_revisions`
**Method:** LLM director outputs creative fields; `hydrate_beats()` fills routing fields deterministically.

### 5. storyboard_review_loop
**Script:** `scripts/review.py` (review_loop)
**Database Integration:** Review evidence recorded in ledger
**Output:** storyboard.json (revised) → unified ledger `document_revisions`
**Method:** Same loop model as script review

### 6. tts
**Script:** `scripts/tts.py`
**Database Integration:** Audio artifacts registered in `artifacts` table
**Output:** `narration/continuous.mp3` → unified ledger `artifacts`
**Method:** ElevenLabs API (eleven_v3 model, James Harrington voice).

### 7. build_timing_map
**Script:** `scripts/audio_timing.py`
**Database Integration:** Timing map registered as document revision
**Output:** `narration/beat_timing_map.json` → unified ledger `document_revisions`
**Method:** ffmpeg silencedetect → sentence boundary detection → word-proportional alignment.

### 8. compliance_check
**Script:** `scripts/direct_storyboard.py` (validate_director_output)
**Database Integration:** Validation evidence recorded in ledger
**Output:** None (pass/fail gate) → unified ledger `validations`
**Method:** Python-side structural validation — shot_type validity, duration limits, etc.

### 9. compile_media_plan
**Script:** `scripts/compile_media_prompts.py`
**Database Integration:** Calls `clip_db.order_clips()` for canonical ordering
**Output:** `media_plan.json` → `clip_db` clips + unified ledger `document_revisions`
**Method:** Deterministic compilation with canonical path assignment.

### 10. slice_lipsync
**Script:** `scripts/slice_continuous_lipsync.py`
**Database Integration:** Audio slices registered as artifacts with SHA-256
**Output:** `media_plan.json` (updated) → `clip_db` + unified ledger `artifacts`
**Method:** Extracts audio slices from continuous master; records provenance.

### 11. gate_a_budget (HUMAN GATE)
**Database Integration:** Approval request recorded in `approval_requests` table
**Output:** Human approval → unified ledger `approval_requests`
**Method:** Displays beat count, estimated cost, budget cap. Sends Telegram notification.

### 12. generate_media
**Script:** `scripts/generate_media.py`
**Database Integration:** Uses `clip_db.can_reuse()` → `record_generated()` → mirrored to ledger
**Output:** MP4 clips at canonical paths → `clip_db` + unified ledger `artifacts`
**Method:** Higgsfield CLI calls with reuse validation and actual attribute recording.

### 13. qa_media
**Script:** `scripts/qa_media.py`
**Database Integration:** Calls `clip_db.mark_valid()` → mirrored validation evidence
**Output:** `media_qa_report.json` → unified ledger `validations`
**Method:** Per-clip validation against clip authority DB; raises change requests on mismatch.

### 14. build_manifest
**Database Integration:** Calls `clip_db.assert_all_valid()` gates assembly
**Output:** `manifest.json` → unified ledger `document_revisions`
**Method:** Pure Python mapping using canonical paths from `clip_db`.

### 15. assemble
**Script:** `scripts/assemble.py`
**Database Integration:** Calls `clip_db.assert_all_valid()` before assembly
**Output:** `{project}_16x9.mp4` → unified ledger `artifacts`
**Method:** ffmpeg-driven deterministic assembly with golden-truth gate.

### 16. gate_b_review (HUMAN GATE)
**Database Integration:** Approval request recorded in `approval_requests` table
**Output:** Video sent to Telegram → unified ledger `approval_requests`
**Method:** If ≤50MB, sends video directly via Telegram bot.

---

## Change Request Lifecycle

```
Problem detected (e.g., clip too short, path mismatch, stale reuse)
    │
    ▼
clip_db.request_change(
    clip_id="project::B004::s0",
    requested_by="qa_media",
    target_step="generate_media",
    change_type="regenerate",
    reason="actual 10.1s < required 14.0s"
)
    │
    ▼
production_db.mirror_change_request()  # Tracked in unified ledger
    │
    ▼
Clip status → "change_requested"
assert_all_valid() returns False
Assembly blocked
    │
    ▼
generate_media polls open_change_requests()
    │
    ▼
Regenerates clip → clip_db.record_generated()
    │
    ▼
clip_db.resolve_change(...)
production_db.resolve_mirrored_changes()
    │
    ▼
Clip status → "valid"
assert_all_valid() passes → assembly proceeds
```

---

## Harmonized Clip Fingerprints

**Key Benefit:** Eliminates "fingerprint drift" where each step independently derived paths.

| Before (Drift) | After (Harmonized) | Result |
|----------------|-------------------|--------|
| 5 files, 3 path formats | Single `_canonical_path()` rule | No path mismatch |
| Reuse by file-exists | `can_reuse()` validates attributes | No stale reuse |
| Guess parent→child | Explicit `source_beat_id` lineage | No parent/child confusion |
| Slot paths ignored | Distinct `slot_id` clip IDs | Slot files always generated |
| Mixed directory conventions | Consistent `{project_id}/{segment_id}/` | No wrong directory |

---

## Resume / Recovery (Database-Enhanced)

State is persisted to **both** `<project_dir>/state.json` **and** unified production ledger.
On failure:

```bash
# Resume from where it stopped (ledger tracks state):
python3 scripts/produce.py --resume Videos/Projects/my_project_short

# Resume from a specific step (re-run that step):
python3 scripts/produce.py --resume Videos/Projects/my_project_short --from-step compile_media_plan
```

**Enhanced Recovery:** Unified ledger provides:
- Transactional state consistency
- Idempotent operation retry
- Change request tracking across sessions
- Full audit trail for debugging

---

## Cost Model (Unchanged)

| Model | Use | Tokens/sec | Cost |
|-------|-----|-----------|------|
| seedance_2_0 | Hero lipsync | 9 tok/s | $0.049/token |
| kling3_0 | B-roll, hero cutaway | 6 tok/s | $0.049/token |
| local_graphic | Graphics, kinetic text | 0 | Free |

**Budget caps by format:**
| Format | Token cap | USD cap |
|--------|----------|---------|
| short | ~510 | $25 |
| explainer | ~1224 | $60 |
| teaser | ~200 | $5 |

---

## Architectural Decisions (Enhanced)

### Database-First Design
All state flows through unified ledger first, files are derived artifacts. This provides:
- Transactional consistency across distributed operations
- Idempotent writes with deterministic event keys
- Full audit trail for compliance and debugging
- Interactive change request routing and resolution

### Golden-Truth Invariant
`assert_all_valid()` gates every downstream step. A clip is valid only when:
1. File exists at canonical path with matching SHA-256
2. All required attributes satisfied (duration, audio policy, etc.)
3. No open change requests pending
4. Status = "valid" in clip authority DB

### Legacy State Mirroring
File-based state is mirrored to unified ledger for:
- Backwards compatibility with existing scripts
- Gradual migration path
- Dual-layer verification (file + ledger)
- Historical continuity

---

## Project Directory Layout (Enhanced)

```
Videos/Projects/<slug>_<format>/
├── state.json              # Legacy state (mirrored to ledger)
├── transcripts/            # LLM prompt/output logs per step
├── research_brief.json     # Step 1 output → ledger document_revisions
├── script.json             # Steps 2-3 output → ledger document_revisions
├── storyboard.json         # Steps 4-5 output → ledger document_revisions
├── narration/
│   ├── continuous.mp3      # Step 6 output → ledger artifacts
│   └── beat_timing_map.json # Step 7 output → ledger document_revisions
├── media_plan.json         # Steps 9-10 output → clip_db + ledger
├── media_qa_report.json    # Step 13 output → ledger validations
├── manifest.json           # Step 14 output → ledger document_revisions
├── review_rounds/          # Review loop transcripts
├── *_16x9.mp4             # Final assembled video → ledger artifacts
└── assets/media/           # Generated clips (step 12) → clip_db + ledger artifacts

# Database State (canonical source)
db/
├── production.db          # Unified production ledger
├── clips.db              # Clip authority database
└── leverage_mind.db      # Content performance database
```

---

## First Successful Database-Driven Run

- **Topic:** "using AI to help memory retention"
- **Format:** short
- **Beats:** 10
- **Spend:** $6.48
- **Database Records:** 142 ledger entries, 10 clip authority records, 15 artifacts
- **Output:** 44.7MB MP4 with golden-truth invariant satisfied
- **Status:** Zero fingerprint drift, zero stale reuse, zero parent/child confusion

# Rectification Plan — Sprints R2 + R3

**Theme:** Schema & repository enforcement (R2); canonical master audio + true-silence slicing (R3).
**Depends on:** R0 + R1 complete (orchestrator runs to spend approval).
**Contains BLOCKER:** R3-002 (true-silence slicer — the real B001/B008 contamination fix).
**Governance:** Coder → Auditor → Validator; reports under `reports/remediation/rectification/<TICKET-ID>/`.

---

## Context

R1 makes the orchestrator *run*; R2/R3 make its data *trustworthy*. The audit found that policy validators exist (`production_repo.py:91-150`) but the live write path doesn't call them or populate all fields; constraints live only in app code (migrations 002/003 note SQLite can't `ALTER TABLE ADD CONSTRAINT`); and the headline "generated silence" fix (`slice_continuous_lipsync.py`) actually widens the extraction window into the master audio, so adjacent speech still contaminates hero conditioning audio. R3 replaces that with sample-exact speech extraction + synthesized silence.

**Hard rule (`.kiro/rules/no-hacks.md`):** fix the producing/consuming code; never hand-edit DB rows or JSON to pass.

## Existing primitives to reuse / harden

| Need | Existing | Location |
|---|---|---|
| Policy validators | `validate_audio_policy`, `validate_text_policy`, `validate_render_unit`, `validate_hero_slicing_intervals` | `production_repo.py:91-203` |
| Render-unit write | `plan_render_units`, `invalidate_render_units` | `production_repo.py:326,425` |
| Media probe | `_probe_media` | `production_repo.py:49` |
| Sample columns (already added) | `speech_*_sample`, `visible_*_sample`, `generation_*_sample`, `leading/trailing_silence_samples` | migration `003_hero_slicing.sql` |
| Canonical sample utils | integer sample-time helpers | `scripts/timeline_utils.py` |
| Existing (broken) slicer | `slice_continuous_lipsync.py` | scripts/ |

---

## Sprint R2 — Schema & Repository Enforcement

### R2-001 — Corrective migrations (new files only; never edit applied ones)
New `db/migrations/004_*.sql` … enforcing, via CHECK constraints / triggers / shadow-validation tables (working around SQLite limits with `CREATE TRIGGER ... BEFORE INSERT ... SELECT RAISE(ABORT,...)`):
- valid audio policy, final audio source, provider-audio usage, text policy, hero-policy combinations;
- sample interval ordering (`speech_start ≤ speech_end`, `generation_start ≤ speech_start`), nonnegative padding, visible-interval containment;
- hero master artifact id + SHA present for hero units;
- new **hero-group tables** (group, membership, covered intervals) — see R3-003;
- validation artifact SHA + algorithm version + threshold version columns;
- change-request failure/replacement evidence fields (sets up R6-004).
Plus: tested rollback (`down` SQL or documented reverse migration that the test actually executes), deterministic backfill of legacy policies, and **block ambiguous backfill** (abort migration if a row can't be classified).

**Tests** (`tests/contracts/`): migrate 001→latest; fresh→latest; direct invalid SQL rejected by trigger; rollback restores data; `PRAGMA foreign_key_check` clean.

### R2-002 — Repository-only write contract
- Typed repo APIs for render units, hero groups, validations, replacements (extend `production_repo.py`).
- `plan_render_units` (and all writers) call `validate_render_unit` **inside** the transaction; populate every required field; reject unknown/missing fields; remove legacy defaults.
- Prohibit changing an active artifact except through a qualified replacement (R6-004 path).
- New CI gate `tools/check_direct_db_writes.py` (from R0-003) statically forbids direct `INSERT/UPDATE` to `render_units`/`change_requests`/`approval_requests` outside `production_repo`/`authoring_service`.

### R2-003 — Repair media probing
- Typed probe output: `{duration, width, height, has_audio, sample_rate, channels}` from `_probe_media`; convert raw ffprobe correctly (no string-truthiness bugs).
- Fail expected-media registration on probe failure; permit non-media only for explicit kinds; verify SHA at consumption (`verify_artifact_on_disk`, `production_repo.py:549`).

**Sprint R2 exit:** invalid policy rows and fake media cannot enter active production state.

---

## Sprint R3 — Canonical Master Audio & True Silence

### R3-001 — Canonicalize master narration
- Preserve provider master; create a canonical **lossless PCM/WAV** derivative at a fixed enforced sample rate.
- Store conversion lineage: sample_rate, channels, total samples, duration, SHA, source artifact id.
- All authoritative intervals expressed in **samples**; milliseconds become a projection only (use `timeline_utils`).

### R3-002 — Sample-exact speech + generated silence — **BLOCKER**
Rewrite `slice_continuous_lipsync.py` (currently `:100-108` widens master window + `-c copy`):
1. Read exact speech sample bounds from DB (`speech_start_sample`/`speech_end_sample`).
2. Extract **only** the assigned speech samples (sample-accurate; re-encode, never `-c copy` on MP3).
3. Generate lead/trail **silence separately** (`anullsrc`/zero PCM) or approved speech-free room tone — never copy adjacent master samples.
4. Concatenate `lead_silence + speech + trail_silence`; pad to `LIPSYNC_MIN`.
5. Register full provenance; DB service is authoritative (not JSON).
6. Fail on ambiguous/overlapping speech; prohibit MP3 stream-copy hero slicing.

**Required regressions** (promote the R0-002 `xfail` anchors to passing): B001/B002, B008a/b/c, zero-padding, minimum duration, final-master boundary, adjacent continuous speech.
**Tests:** zero speech energy in pads (assert via VAD/energy on pad regions only); exact sample counts; deterministic checksum; master change invalidates slices; interval change invalidates only dependents.

### R3-003 — Persist deterministic hero groups
Rewrite `hero_grouping.py` (audit: random group IDs, not persisted, can skip intervening narration):
- Deterministic semantic group id (hash of members + master slice + prompt revision).
- Persist group, members, visible intervals, covered intervals, prompt revision, master slice, model, duration, blast radius (tables from R2-001).
- Include intervening narration in merge decisions; block unrelated speech / scene changes / resets / invalid duration.
- One slice generated per full group; validate master bounds.

**Sprint R3 exit:** B001/B008 contain **no neighbouring speech**, and every hero group has deterministic DB lineage.

---

## Verification

```bash
rm -f db/validation.db && export PRODUCTION_DB_PATH="$PWD/db/validation.db"
python3 scripts/production_db.py migrate           # 001 → latest (incl. 004+)
python3 -c "import sqlite3,os;c=sqlite3.connect(os.environ['PRODUCTION_DB_PATH']);print(c.execute('PRAGMA foreign_key_check').fetchall())"
python3 -m pytest tests/contracts -q               # migrations, repo enforcement, probe
python3 -m pytest tests/integration/test_defect_reproduction.py -q   # now PASS (was xfail)
python3 tools/check_direct_db_writes.py
# Inspect a hero slice: assert silent pad regions, sample-exact length, no adjacent words
```

## Risks
- SQLite trigger-based enforcement is verbose; validate each trigger actually aborts on bad SQL.
- Re-encoding slices changes checksums vs. the old `-c copy` outputs — expected; update any golden fixtures.
- Backfill must abort (not guess) on ambiguous legacy rows.

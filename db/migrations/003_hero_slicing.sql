-- Sprint 3: Clean Hero Slicing and Hero Render Groups (Ticket LB-300)
-- Adds precise sample-level interval tracking and master audio provenance to render_units.

-- 1. Add speech and visible interval columns (in samples, at MASTER_SAMPLE_RATE)
ALTER TABLE render_units ADD COLUMN speech_start_sample INTEGER;
ALTER TABLE render_units ADD COLUMN speech_end_sample INTEGER;
ALTER TABLE render_units ADD COLUMN visible_start_sample INTEGER;
ALTER TABLE render_units ADD COLUMN visible_end_sample INTEGER;

-- 2. Add generation interval and silence padding columns (in samples)
ALTER TABLE render_units ADD COLUMN generation_start_sample INTEGER;
ALTER TABLE render_units ADD COLUMN generation_end_sample INTEGER;
ALTER TABLE render_units ADD COLUMN leading_silence_samples INTEGER;
ALTER TABLE render_units ADD COLUMN trailing_silence_samples INTEGER;

-- 3. Add master audio provenance columns
ALTER TABLE render_units ADD COLUMN master_audio_artifact_id TEXT REFERENCES artifacts(id);
ALTER TABLE render_units ADD COLUMN master_audio_sha256 TEXT;

-- 4. Add boundary metadata columns
ALTER TABLE render_units ADD COLUMN boundary_reason TEXT;
ALTER TABLE render_units ADD COLUMN boundary_confidence REAL;

-- 5. Add CHECK constraints to ensure logical consistency (where applicable)
-- Note: SQLite ALTER TABLE does not support ADD CONSTRAINT, so these are enforced 
-- at the application layer (production_repo.py) and via triggers if needed.

-- Rollback instructions (for reference, do not execute):
-- ALTER TABLE render_units DROP COLUMN speech_start_sample;
-- ALTER TABLE render_units DROP COLUMN speech_end_sample;
-- ALTER TABLE render_units DROP COLUMN visible_start_sample;
-- ALTER TABLE render_units DROP COLUMN visible_end_sample;
-- ALTER TABLE render_units DROP COLUMN generation_start_sample;
-- ALTER TABLE render_units DROP COLUMN generation_end_sample;
-- ALTER TABLE render_units DROP COLUMN leading_silence_samples;
-- ALTER TABLE render_units DROP COLUMN trailing_silence_samples;
-- ALTER TABLE render_units DROP COLUMN master_audio_artifact_id;
-- ALTER TABLE render_units DROP COLUMN master_audio_sha256;
-- ALTER TABLE render_units DROP COLUMN boundary_reason;
-- ALTER TABLE render_units DROP COLUMN boundary_confidence;

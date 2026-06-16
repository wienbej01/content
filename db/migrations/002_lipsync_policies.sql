-- Sprint 1: Audio and Text Policy Schema (Tickets LB-100, LB-101)
-- Adds explicit policy columns to render_units. 
-- Note: Enum constraints are enforced at the application layer (production_repo.py) 
-- because SQLite does not support ALTER TABLE ADD CONSTRAINT.

-- 1. Add audio policy provenance columns to render_units
ALTER TABLE render_units ADD COLUMN final_audio_source TEXT;
ALTER TABLE render_units ADD COLUMN provider_audio_usage TEXT;

-- 2. Add text policy column to render_units
ALTER TABLE render_units ADD COLUMN text_policy TEXT;

-- 3. Backfill existing records conservatively
-- Visible speaking units (lipsync_required=1) default to HERO_SYNC_LOCKED
UPDATE render_units 
SET audio_policy = 'HERO_SYNC_LOCKED',
    final_audio_source = 'master_narration',
    provider_audio_usage = 'diagnostic_only'
WHERE lipsync_required = 1 AND (audio_policy = '' OR audio_policy IS NULL);

-- B-roll units default to BROLL_FLEX with discarded provider audio
UPDATE render_units 
SET audio_policy = 'BROLL_FLEX',
    final_audio_source = 'none',
    provider_audio_usage = 'discarded',
    text_policy = 'NO_VISIBLE_TEXT'
WHERE lipsync_required = 0 AND (audio_policy = '' OR audio_policy IS NULL);

-- Rollback instructions (for reference, do not execute):
-- ALTER TABLE render_units DROP COLUMN final_audio_source;
-- ALTER TABLE render_units DROP COLUMN provider_audio_usage;
-- ALTER TABLE render_units DROP COLUMN text_policy;

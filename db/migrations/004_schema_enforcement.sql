-- Sprint R2: Schema Enforcement & Repository Guard Rails (Tickets R2-001, R2-002)
-- Adds hero-group tables, validation integrity columns, change-request evidence,
-- and SQLite trigger-based CHECK constraints for render_units policy enforcement.
--
-- Rollback: see end of file. Tests in tests/contracts/ must execute the rollback.

-- ---------------------------------------------------------------------------
-- 1. Hero Render Groups (R2-001 hero-group tables, supports R3-003)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS hero_render_groups (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    group_ordinal INTEGER NOT NULL,
    group_hash TEXT NOT NULL,
    generation_start_sample INTEGER NOT NULL,
    generation_end_sample INTEGER NOT NULL,
    generation_duration_samples INTEGER NOT NULL,
    source_audio_artifact_id TEXT REFERENCES artifacts(id),
    source_audio_sha256 TEXT,
    prompt_revision_id TEXT REFERENCES document_revisions(id),
    prompt_sha256 TEXT,
    model TEXT NOT NULL,
    requested_duration_sec REAL NOT NULL,
    regeneration_blast_radius_json TEXT,
    temporal_edit_policy TEXT NOT NULL DEFAULT 'HERO_SYNC_LOCKED',
    continuity_benefit TEXT,
    scene_consistent INTEGER NOT NULL DEFAULT 1,
    master_audio_artifact_id TEXT REFERENCES artifacts(id),
    master_audio_sha256 TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(production_id, group_ordinal),
    CHECK(generation_end_sample > generation_start_sample),
    CHECK(generation_duration_samples = generation_end_sample - generation_start_sample)
);

CREATE TABLE IF NOT EXISTS hero_group_members (
    id TEXT PRIMARY KEY,
    hero_render_group_id TEXT NOT NULL REFERENCES hero_render_groups(id) ON DELETE CASCADE,
    render_unit_id TEXT NOT NULL REFERENCES render_units(id) ON DELETE CASCADE,
    member_ordinal INTEGER NOT NULL,
    visible_start_sample INTEGER NOT NULL,
    visible_end_sample INTEGER NOT NULL,
    beat_id TEXT,
    UNIQUE(hero_render_group_id, member_ordinal)
);

CREATE INDEX IF NOT EXISTS idx_hero_group_members_render_unit
    ON hero_group_members(render_unit_id);

CREATE TABLE IF NOT EXISTS hero_covered_intervals (
    id TEXT PRIMARY KEY,
    hero_render_group_id TEXT NOT NULL REFERENCES hero_render_groups(id) ON DELETE CASCADE,
    interval_ordinal INTEGER NOT NULL,
    start_sample INTEGER NOT NULL,
    end_sample INTEGER NOT NULL,
    beat_id TEXT,
    interval_kind TEXT NOT NULL DEFAULT 'broll_covered',
    UNIQUE(hero_render_group_id, interval_ordinal)
);

-- ---------------------------------------------------------------------------
-- 2. Validation integrity columns (R2-001)
--    Artifact SHA, algorithm version, and threshold version for reproducibility.
-- ---------------------------------------------------------------------------

ALTER TABLE validations ADD COLUMN artifact_sha256 TEXT;
ALTER TABLE validations ADD COLUMN algorithm_version TEXT;
ALTER TABLE validations ADD COLUMN threshold_version TEXT;

-- ---------------------------------------------------------------------------
-- 3. Change-request evidence columns (R2-001, sets up R6-004)
-- ---------------------------------------------------------------------------

ALTER TABLE change_requests ADD COLUMN failure_evidence_json TEXT;
ALTER TABLE change_requests ADD COLUMN replacement_subject_type TEXT;
ALTER TABLE change_requests ADD COLUMN replacement_subject_id TEXT;
ALTER TABLE change_requests ADD COLUMN repair_routing_stage TEXT;

-- ---------------------------------------------------------------------------
-- 4. Trigger-based CHECK enforcement (R2-001)
--    SQLite does not support ALTER TABLE ADD CONSTRAINT, so we use BEFORE
--    INSERT and BEFORE UPDATE triggers that SELECT RAISE(ABORT, ...).
-- ---------------------------------------------------------------------------

-- 4a. Render unit interval ordering: speech_start_sample <= speech_end_sample
CREATE TRIGGER IF NOT EXISTS trg_ru_speech_ordering
    BEFORE INSERT ON render_units
    WHEN NEW.speech_start_sample IS NOT NULL AND NEW.speech_end_sample IS NOT NULL
     AND NEW.speech_start_sample > NEW.speech_end_sample
BEGIN
    SELECT RAISE(ABORT, 'speech_start_sample must be <= speech_end_sample');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_speech_ordering_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.speech_start_sample IS NOT NULL AND NEW.speech_end_sample IS NOT NULL
     AND NEW.speech_start_sample > NEW.speech_end_sample
BEGIN
    SELECT RAISE(ABORT, 'speech_start_sample must be <= speech_end_sample');
END;

-- 4b. Generation interval ordering
CREATE TRIGGER IF NOT EXISTS trg_ru_gen_ordering
    BEFORE INSERT ON render_units
    WHEN NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND NEW.generation_start_sample > NEW.generation_end_sample
BEGIN
    SELECT RAISE(ABORT, 'generation_start_sample must be <= generation_end_sample');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_gen_ordering_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND NEW.generation_start_sample > NEW.generation_end_sample
BEGIN
    SELECT RAISE(ABORT, 'generation_start_sample must be <= generation_end_sample');
END;

-- 4c. Nonnegative padding
CREATE TRIGGER IF NOT EXISTS trg_ru_nonneg_lead_silence
    BEFORE INSERT ON render_units
    WHEN NEW.leading_silence_samples IS NOT NULL AND NEW.leading_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'leading_silence_samples must be >= 0');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_nonneg_lead_silence_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.leading_silence_samples IS NOT NULL AND NEW.leading_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'leading_silence_samples must be >= 0');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_nonneg_trail_silence
    BEFORE INSERT ON render_units
    WHEN NEW.trailing_silence_samples IS NOT NULL AND NEW.trailing_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'trailing_silence_samples must be >= 0');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_nonneg_trail_silence_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.trailing_silence_samples IS NOT NULL AND NEW.trailing_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'trailing_silence_samples must be >= 0');
END;

-- 4d. Visible interval containment within generation interval
CREATE TRIGGER IF NOT EXISTS trg_ru_visible_containment
    BEFORE INSERT ON render_units
    WHEN NEW.visible_start_sample IS NOT NULL AND NEW.visible_end_sample IS NOT NULL
     AND NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND (NEW.visible_start_sample < NEW.generation_start_sample
          OR NEW.visible_end_sample > NEW.generation_end_sample)
BEGIN
    SELECT RAISE(ABORT, 'visible interval must be contained within generation interval');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_visible_containment_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.visible_start_sample IS NOT NULL AND NEW.visible_end_sample IS NOT NULL
     AND NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND (NEW.visible_start_sample < NEW.generation_start_sample
          OR NEW.visible_end_sample > NEW.generation_end_sample)
BEGIN
    SELECT RAISE(ABORT, 'visible interval must be contained within generation interval');
END;

-- 4e. Valid audio_policy values
CREATE TRIGGER IF NOT EXISTS trg_ru_audio_policy
    BEFORE INSERT ON render_units
    WHEN NEW.audio_policy IS NOT NULL
     AND NEW.audio_policy NOT IN ('HERO_SYNC_LOCKED','BROLL_FLEX','BROLL_SYNCED_ACTION',
                                  'AMBIENCE_OR_SFX','MUSIC_BED','SILENT_GRAPHIC',
                                  'narration_overlay','silent','baked_in','generated_tts',
                                  'strip','ambient')
BEGIN
    SELECT RAISE(ABORT, 'invalid audio_policy');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_audio_policy_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.audio_policy IS NOT NULL
     AND NEW.audio_policy NOT IN ('HERO_SYNC_LOCKED','BROLL_FLEX','BROLL_SYNCED_ACTION',
                                  'AMBIENCE_OR_SFX','MUSIC_BED','SILENT_GRAPHIC',
                                  'narration_overlay','silent','baked_in','generated_tts',
                                  'strip','ambient')
BEGIN
    SELECT RAISE(ABORT, 'invalid audio_policy');
END;

-- 4f. Valid final_audio_source values
CREATE TRIGGER IF NOT EXISTS trg_ru_final_audio_source
    BEFORE INSERT ON render_units
    WHEN NEW.final_audio_source IS NOT NULL
     AND NEW.final_audio_source NOT IN ('master_narration','provider_audio','none')
BEGIN
    SELECT RAISE(ABORT, 'invalid final_audio_source');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_final_audio_source_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.final_audio_source IS NOT NULL
     AND NEW.final_audio_source NOT IN ('master_narration','provider_audio','none')
BEGIN
    SELECT RAISE(ABORT, 'invalid final_audio_source');
END;

-- 4g. Valid provider_audio_usage values
CREATE TRIGGER IF NOT EXISTS trg_ru_provider_audio_usage
    BEFORE INSERT ON render_units
    WHEN NEW.provider_audio_usage IS NOT NULL
     AND NEW.provider_audio_usage NOT IN ('diagnostic_only','final_mix','discarded')
BEGIN
    SELECT RAISE(ABORT, 'invalid provider_audio_usage');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_provider_audio_usage_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.provider_audio_usage IS NOT NULL
     AND NEW.provider_audio_usage NOT IN ('diagnostic_only','final_mix','discarded')
BEGIN
    SELECT RAISE(ABORT, 'invalid provider_audio_usage');
END;

-- 4h. Valid text_policy values
CREATE TRIGGER IF NOT EXISTS trg_ru_text_policy
    BEFORE INSERT ON render_units
    WHEN NEW.text_policy IS NOT NULL
     AND NEW.text_policy NOT IN ('NO_VISIBLE_TEXT','UNREADABLE_BACKGROUND','POST_COMPOSITE',
                                  'REAL_SCREEN_CAPTURE','DETERMINISTIC_GRAPHIC')
BEGIN
    SELECT RAISE(ABORT, 'invalid text_policy');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_text_policy_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.text_policy IS NOT NULL
     AND NEW.text_policy NOT IN ('NO_VISIBLE_TEXT','UNREADABLE_BACKGROUND','POST_COMPOSITE',
                                  'REAL_SCREEN_CAPTURE','DETERMINISTIC_GRAPHIC')
BEGIN
    SELECT RAISE(ABORT, 'invalid text_policy');
END;

-- 4i. HERO_SYNC_LOCKED: if master_audio fields are set, both must be present
CREATE TRIGGER IF NOT EXISTS trg_ru_hero_master_consistent
    BEFORE INSERT ON render_units
    WHEN NEW.audio_policy = 'HERO_SYNC_LOCKED'
     AND (NEW.master_audio_artifact_id IS NOT NULL AND NEW.master_audio_sha256 IS NULL
          OR NEW.master_audio_artifact_id IS NULL AND NEW.master_audio_sha256 IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'HERO_SYNC_LOCKED: master_audio_artifact_id and master_audio_sha256 must both be set or both null');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_hero_master_consistent_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.audio_policy = 'HERO_SYNC_LOCKED'
     AND (NEW.master_audio_artifact_id IS NOT NULL AND NEW.master_audio_sha256 IS NULL
          OR NEW.master_audio_artifact_id IS NULL AND NEW.master_audio_sha256 IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'HERO_SYNC_LOCKED: master_audio_artifact_id and master_audio_sha256 must both be set or both null');
END;

-- ============================================================================
-- ROLLBACK (for reference; execute via test harness)
-- ============================================================================
--
-- DROP TRIGGER IF EXISTS trg_ru_speech_ordering;
-- DROP TRIGGER IF EXISTS trg_ru_speech_ordering_upd;
-- DROP TRIGGER IF EXISTS trg_ru_gen_ordering;
-- DROP TRIGGER IF EXISTS trg_ru_gen_ordering_upd;
-- DROP TRIGGER IF EXISTS trg_ru_nonneg_lead_silence;
-- DROP TRIGGER IF EXISTS trg_ru_nonneg_lead_silence_upd;
-- DROP TRIGGER IF EXISTS trg_ru_nonneg_trail_silence;
-- DROP TRIGGER IF EXISTS trg_ru_nonneg_trail_silence_upd;
-- DROP TRIGGER IF EXISTS trg_ru_visible_containment;
-- DROP TRIGGER IF EXISTS trg_ru_visible_containment_upd;
-- DROP TRIGGER IF EXISTS trg_ru_audio_policy;
-- DROP TRIGGER IF EXISTS trg_ru_audio_policy_upd;
-- DROP TRIGGER IF EXISTS trg_ru_final_audio_source;
-- DROP TRIGGER IF EXISTS trg_ru_final_audio_source_upd;
-- DROP TRIGGER IF EXISTS trg_ru_provider_audio_usage;
-- DROP TRIGGER IF EXISTS trg_ru_provider_audio_usage_upd;
-- DROP TRIGGER IF EXISTS trg_ru_text_policy;
-- DROP TRIGGER IF EXISTS trg_ru_text_policy_upd;
-- DROP TRIGGER IF EXISTS trg_ru_hero_master_consistent;
-- DROP TRIGGER IF EXISTS trg_ru_hero_master_consistent_upd;
-- DROP TABLE IF EXISTS hero_covered_intervals;
-- DROP TABLE IF EXISTS hero_group_members;
-- DROP TABLE IF EXISTS hero_render_groups;
-- ALTER TABLE validations DROP COLUMN artifact_sha256;
-- ALTER TABLE validations DROP COLUMN algorithm_version;
-- ALTER TABLE validations DROP COLUMN threshold_version;
-- ALTER TABLE change_requests DROP COLUMN failure_evidence_json;
-- ALTER TABLE change_requests DROP COLUMN replacement_subject_type;
-- ALTER TABLE change_requests DROP COLUMN replacement_subject_id;
-- ALTER TABLE change_requests DROP COLUMN repair_routing_stage;

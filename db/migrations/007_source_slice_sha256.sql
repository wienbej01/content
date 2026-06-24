-- Sprint S01-T001: Source audio slice ledger.
--
-- Additive migration: adds source_slice_sha256 column to render_units.
-- This stores the SHA256 of the per-hero-unit audio slice file (distinct
-- from master_audio_sha256 which stores the hash of the full TTS master).
-- The column must be populated before a HERO_SYNC_LOCKED unit can be
-- submitted to a provider (enforced in media_service.py).

ALTER TABLE render_units ADD COLUMN source_slice_sha256 TEXT;

-- Sprint S08-T001: Provider audio offset ledger.
--
-- Additive migration: adds offset measurement columns to provider_jobs
-- and a source_slice_artifact_id for provenance linking.
-- The actual offset evidence is stored as 'audio_offset' validations;
-- these columns are convenience pointers to the latest approved validation.

ALTER TABLE provider_jobs ADD COLUMN source_slice_vs_diagnostic_offset_ms INTEGER;
ALTER TABLE provider_jobs ADD COLUMN audio_offset_confidence REAL;
ALTER TABLE provider_jobs ADD COLUMN source_slice_artifact_id TEXT;
ALTER TABLE provider_jobs ADD COLUMN diagnostic_audio_artifact_id TEXT;

-- Sprint S08-T002: Compensated hero remux artifact path.
--
-- Additive migration: adds compensated_artifact_path to provider_jobs
-- for storing the path to the locally-generated compensated remux MP4.

ALTER TABLE provider_jobs ADD COLUMN compensated_artifact_path TEXT;

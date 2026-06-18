-- Sprint S1-T04: Enforce canonical identities and active revisions.
--
-- Additive corrective migration (no applied migration is modified).
--
-- Partial unique index: at most ONE active revision per (production, kind).
-- Application-level superseding (save_document_revision) is the primary
-- enforcement; this index makes it impossible for two active revisions to
-- coexist even if a bug or concurrent write tries to insert a second one.

CREATE UNIQUE INDEX IF NOT EXISTS one_active_revision_per_kind
    ON document_revisions (production_id, kind)
    WHERE status = 'active';

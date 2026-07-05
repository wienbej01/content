-- 013_asset_library: curated asset library for reusable footage
-- TKT-503: immutable indexed repository with license provenance enforcement

CREATE TABLE IF NOT EXISTS asset_library (
    id TEXT PRIMARY KEY,
    uri TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    media_kind TEXT NOT NULL DEFAULT 'video',
    tags TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    license TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT '',
    indexed_by TEXT,
    file_size_bytes INTEGER,
    duration_ms INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(uri)
);

CREATE INDEX IF NOT EXISTS idx_asset_library_tags ON asset_library(tags);
CREATE INDEX IF NOT EXISTS idx_asset_library_license ON asset_library(license);

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS content_items (
    id TEXT PRIMARY KEY,
    external_key TEXT UNIQUE,
    topic TEXT NOT NULL,
    pillar TEXT,
    format_archetype TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    target_publish_at TEXT,
    created_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS config_snapshots (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS productions (
    id TEXT PRIMARY KEY,
    content_item_id TEXT REFERENCES content_items(id),
    project_slug TEXT NOT NULL UNIQUE,
    video_type TEXT,
    seed TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    current_stage TEXT,
    code_revision TEXT,
    config_snapshot_id TEXT REFERENCES config_snapshots(id),
    parent_production_id TEXT REFERENCES productions(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS stage_runs (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    input_fingerprint TEXT,
    started_at TEXT,
    heartbeat_at TEXT,
    finished_at TEXT,
    worker_id TEXT,
    error_class TEXT,
    error_message TEXT,
    result_summary_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(production_id, stage_name, attempt)
);

CREATE INDEX IF NOT EXISTS idx_stage_runs_production_status
    ON stage_runs(production_id, status);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    leased_by TEXT,
    lease_expires_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_available
    ON jobs(status, available_at, priority);

CREATE TABLE IF NOT EXISTS production_events (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_key TEXT UNIQUE,
    payload_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_production_created
    ON production_events(production_id, created_at);

CREATE TABLE IF NOT EXISTS document_revisions (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    schema_version TEXT,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    created_by_stage_run_id TEXT REFERENCES stage_runs(id),
    supersedes_id TEXT REFERENCES document_revisions(id),
    source_uri TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(production_id, kind, revision),
    UNIQUE(production_id, kind, payload_sha256)
);

CREATE INDEX IF NOT EXISTS idx_documents_active
    ON document_revisions(production_id, kind, status);

CREATE TABLE IF NOT EXISTS document_dependencies (
    document_revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
    depends_on_document_revision_id TEXT NOT NULL REFERENCES document_revisions(id),
    dependency_role TEXT NOT NULL,
    PRIMARY KEY(document_revision_id, depends_on_document_revision_id, dependency_role)
);

CREATE TABLE IF NOT EXISTS source_citations (
    id TEXT PRIMARY KEY,
    document_revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    source_type TEXT,
    published_at TEXT,
    accessed_at TEXT,
    excerpt_sha256 TEXT,
    how_used TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS script_segments (
    id TEXT PRIMARY KEY,
    script_revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    label TEXT,
    text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    UNIQUE(script_revision_id, ordinal)
);

CREATE TABLE IF NOT EXISTS creative_beats (
    id TEXT PRIMARY KEY,
    storyboard_revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
    script_segment_id TEXT REFERENCES script_segments(id),
    ordinal INTEGER NOT NULL,
    label TEXT,
    shot_type TEXT,
    visual_intent_json TEXT,
    graphics_json TEXT,
    narration_text_sha256 TEXT,
    UNIQUE(storyboard_revision_id, ordinal)
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    uri TEXT NOT NULL,
    storage_backend TEXT NOT NULL DEFAULT 'local',
    mime_type TEXT,
    sha256 TEXT,
    size_bytes INTEGER,
    duration_ms INTEGER,
    width INTEGER,
    height INTEGER,
    has_audio INTEGER,
    created_by_stage_run_id TEXT REFERENCES stage_runs(id),
    provider_job_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    deleted_at TEXT,
    UNIQUE(production_id, uri, sha256)
);

CREATE TABLE IF NOT EXISTS artifact_dependencies (
    artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    depends_on_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
    dependency_role TEXT NOT NULL,
    PRIMARY KEY(artifact_id, depends_on_artifact_id, dependency_role)
);

CREATE TABLE IF NOT EXISTS timeline_spans (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    creative_beat_id TEXT REFERENCES creative_beats(id),
    parent_span_id TEXT REFERENCES timeline_spans(id),
    ordinal INTEGER NOT NULL,
    label TEXT,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    split_index INTEGER,
    split_total INTEGER,
    narration_text_sha256 TEXT,
    timing_source_artifact_id TEXT REFERENCES artifacts(id),
    status TEXT NOT NULL,
    CHECK(end_ms > start_ms),
    CHECK(duration_ms = end_ms - start_ms),
    UNIQUE(production_id, ordinal)
);

CREATE TABLE IF NOT EXISTS render_units (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    timeline_span_id TEXT REFERENCES timeline_spans(id),
    parent_render_unit_id TEXT REFERENCES render_units(id),
    ordinal INTEGER NOT NULL,
    label TEXT,
    legacy_clip_id TEXT UNIQUE,
    asset_type TEXT NOT NULL,
    model TEXT,
    audio_policy TEXT NOT NULL,
    lipsync_required INTEGER NOT NULL DEFAULT 0,
    required_start_ms INTEGER NOT NULL,
    required_end_ms INTEGER NOT NULL,
    required_duration_ms INTEGER NOT NULL,
    slot_index INTEGER,
    slot_total INTEGER,
    status TEXT NOT NULL,
    active_artifact_id TEXT REFERENCES artifacts(id),
    approved_validation_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(required_end_ms > required_start_ms),
    CHECK(required_duration_ms = required_end_ms - required_start_ms),
    UNIQUE(production_id, ordinal)
);

CREATE TABLE IF NOT EXISTS validations (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    validator_name TEXT NOT NULL,
    status TEXT NOT NULL,
    ruleset_version TEXT,
    evidence_json TEXT,
    created_by_stage_run_id TEXT REFERENCES stage_runs(id),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validations_subject
    ON validations(subject_type, subject_id, created_at);

CREATE TABLE IF NOT EXISTS change_requests (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    change_type TEXT NOT NULL,
    requested_by_stage TEXT NOT NULL,
    target_stage TEXT NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL,
    resolution_json TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_change_requests_open
    ON change_requests(production_id, status, target_stage);

CREATE TABLE IF NOT EXISTS approval_requests (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    gate_name TEXT NOT NULL,
    subject_type TEXT,
    subject_id TEXT,
    subject_sha256 TEXT,
    artifact_uri TEXT,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    actor TEXT,
    decision_note TEXT,
    forced INTEGER NOT NULL DEFAULT 0,
    legacy_payload_json TEXT,
    UNIQUE(production_id, gate_name)
);

CREATE TABLE IF NOT EXISTS provider_jobs (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    render_unit_id TEXT REFERENCES render_units(id),
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    external_job_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    request_json TEXT,
    response_json TEXT,
    submitted_at TEXT,
    polled_at TEXT,
    completed_at TEXT,
    error_json TEXT
);

CREATE TABLE IF NOT EXISTS cost_events (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    stage_run_id TEXT REFERENCES stage_runs(id),
    provider_job_id TEXT REFERENCES provider_jobs(id),
    provider TEXT,
    operation TEXT NOT NULL,
    estimated_usd REAL,
    actual_usd REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliverables (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    variant TEXT NOT NULL,
    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
    status TEXT NOT NULL,
    assembly_revision TEXT,
    qa_validation_id TEXT REFERENCES validations(id),
    approved_at TEXT,
    UNIQUE(production_id, variant, artifact_id)
);

CREATE TABLE IF NOT EXISTS publications (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    deliverable_id TEXT NOT NULL REFERENCES deliverables(id),
    platform TEXT NOT NULL,
    platform_object_id TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    scheduled_at TEXT,
    published_at TEXT,
    url TEXT,
    disclosure_json TEXT NOT NULL,
    metadata_revision_id TEXT REFERENCES document_revisions(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_publications_platform_object
    ON publications(platform, platform_object_id)
    WHERE platform_object_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS metric_snapshots (
    id TEXT PRIMARY KEY,
    publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    views INTEGER,
    impressions INTEGER,
    watch_time_seconds REAL,
    avg_view_pct REAL,
    ctr REAL,
    subscribers_gained INTEGER,
    likes INTEGER,
    comments INTEGER,
    conversions INTEGER,
    revenue REAL,
    raw_payload_json TEXT,
    UNIQUE(publication_id, observed_at)
);

CREATE TABLE IF NOT EXISTS experiments (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    experiment_type TEXT NOT NULL,
    status TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    assignment_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS outbox_messages (
    id TEXT PRIMARY KEY,
    production_id TEXT REFERENCES productions(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL,
    sent_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON outbox_messages(status, available_at);

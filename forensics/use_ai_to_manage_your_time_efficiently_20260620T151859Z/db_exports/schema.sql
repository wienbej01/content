CREATE TABLE schema_migrations (
               version TEXT PRIMARY KEY,
               filename TEXT NOT NULL,
               sha256 TEXT NOT NULL,
               applied_at TEXT NOT NULL
           );
CREATE TABLE content_items (
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
CREATE TABLE config_snapshots (
    id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE productions (
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
CREATE TABLE stage_runs (
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
CREATE INDEX idx_stage_runs_production_status
    ON stage_runs(production_id, status);
CREATE TABLE jobs (
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
CREATE INDEX idx_jobs_available
    ON jobs(status, available_at, priority);
CREATE TABLE production_events (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    event_key TEXT UNIQUE,
    payload_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX idx_events_production_created
    ON production_events(production_id, created_at);
CREATE TABLE document_revisions (
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
CREATE INDEX idx_documents_active
    ON document_revisions(production_id, kind, status);
CREATE TABLE document_dependencies (
    document_revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
    depends_on_document_revision_id TEXT NOT NULL REFERENCES document_revisions(id),
    dependency_role TEXT NOT NULL,
    PRIMARY KEY(document_revision_id, depends_on_document_revision_id, dependency_role)
);
CREATE TABLE source_citations (
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
CREATE TABLE script_segments (
    id TEXT PRIMARY KEY,
    script_revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    label TEXT,
    text TEXT NOT NULL,
    word_count INTEGER NOT NULL,
    UNIQUE(script_revision_id, ordinal)
);
CREATE TABLE creative_beats (
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
CREATE TABLE artifacts (
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
CREATE TABLE artifact_dependencies (
    artifact_id TEXT NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    depends_on_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
    dependency_role TEXT NOT NULL,
    PRIMARY KEY(artifact_id, depends_on_artifact_id, dependency_role)
);
CREATE TABLE timeline_spans (
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
CREATE TABLE render_units (
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
    updated_at TEXT NOT NULL, final_audio_source TEXT, provider_audio_usage TEXT, text_policy TEXT, speech_start_sample INTEGER, speech_end_sample INTEGER, visible_start_sample INTEGER, visible_end_sample INTEGER, generation_start_sample INTEGER, generation_end_sample INTEGER, leading_silence_samples INTEGER, trailing_silence_samples INTEGER, master_audio_artifact_id TEXT REFERENCES artifacts(id), master_audio_sha256 TEXT, boundary_reason TEXT, boundary_confidence REAL, visual_function TEXT, narrative_claim TEXT, information_to_show TEXT, viewer_takeaway TEXT, required_action TEXT, forbidden_cliches TEXT, distinctness_requirement TEXT, semantic_acceptance_criteria TEXT, render_mode TEXT NOT NULL DEFAULT 'generated_video', concept_key TEXT, concept_hash TEXT, graphic_text_content TEXT, graphic_text_hash TEXT,
    CHECK(required_end_ms > required_start_ms),
    CHECK(required_duration_ms = required_end_ms - required_start_ms),
    UNIQUE(production_id, ordinal)
);
CREATE TABLE validations (
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
, artifact_sha256 TEXT, algorithm_version TEXT, threshold_version TEXT);
CREATE INDEX idx_validations_subject
    ON validations(subject_type, subject_id, created_at);
CREATE TABLE change_requests (
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
, failure_evidence_json TEXT, replacement_subject_type TEXT, replacement_subject_id TEXT, repair_routing_stage TEXT);
CREATE INDEX idx_change_requests_open
    ON change_requests(production_id, status, target_stage);
CREATE TABLE approval_requests (
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
CREATE TABLE provider_jobs (
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
CREATE TABLE cost_events (
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
CREATE TABLE deliverables (
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
CREATE TABLE publications (
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
CREATE UNIQUE INDEX idx_publications_platform_object
    ON publications(platform, platform_object_id)
    WHERE platform_object_id IS NOT NULL;
CREATE TABLE metric_snapshots (
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
CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    experiment_type TEXT NOT NULL,
    status TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    assignment_json TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE outbox_messages (
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
CREATE INDEX idx_outbox_pending
    ON outbox_messages(status, available_at);
CREATE TABLE hero_render_groups (
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
CREATE TABLE hero_group_members (
    id TEXT PRIMARY KEY,
    hero_render_group_id TEXT NOT NULL REFERENCES hero_render_groups(id) ON DELETE CASCADE,
    render_unit_id TEXT NOT NULL REFERENCES render_units(id) ON DELETE CASCADE,
    member_ordinal INTEGER NOT NULL,
    visible_start_sample INTEGER NOT NULL,
    visible_end_sample INTEGER NOT NULL,
    beat_id TEXT,
    UNIQUE(hero_render_group_id, member_ordinal)
);
CREATE INDEX idx_hero_group_members_render_unit
    ON hero_group_members(render_unit_id);
CREATE TABLE hero_covered_intervals (
    id TEXT PRIMARY KEY,
    hero_render_group_id TEXT NOT NULL REFERENCES hero_render_groups(id) ON DELETE CASCADE,
    interval_ordinal INTEGER NOT NULL,
    start_sample INTEGER NOT NULL,
    end_sample INTEGER NOT NULL,
    beat_id TEXT,
    interval_kind TEXT NOT NULL DEFAULT 'broll_covered',
    UNIQUE(hero_render_group_id, interval_ordinal)
);
CREATE TRIGGER trg_ru_speech_ordering
    BEFORE INSERT ON render_units
    WHEN NEW.speech_start_sample IS NOT NULL AND NEW.speech_end_sample IS NOT NULL
     AND NEW.speech_start_sample > NEW.speech_end_sample
BEGIN
    SELECT RAISE(ABORT, 'speech_start_sample must be <= speech_end_sample');
END;
CREATE TRIGGER trg_ru_speech_ordering_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.speech_start_sample IS NOT NULL AND NEW.speech_end_sample IS NOT NULL
     AND NEW.speech_start_sample > NEW.speech_end_sample
BEGIN
    SELECT RAISE(ABORT, 'speech_start_sample must be <= speech_end_sample');
END;
CREATE TRIGGER trg_ru_gen_ordering
    BEFORE INSERT ON render_units
    WHEN NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND NEW.generation_start_sample > NEW.generation_end_sample
BEGIN
    SELECT RAISE(ABORT, 'generation_start_sample must be <= generation_end_sample');
END;
CREATE TRIGGER trg_ru_gen_ordering_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND NEW.generation_start_sample > NEW.generation_end_sample
BEGIN
    SELECT RAISE(ABORT, 'generation_start_sample must be <= generation_end_sample');
END;
CREATE TRIGGER trg_ru_nonneg_lead_silence
    BEFORE INSERT ON render_units
    WHEN NEW.leading_silence_samples IS NOT NULL AND NEW.leading_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'leading_silence_samples must be >= 0');
END;
CREATE TRIGGER trg_ru_nonneg_lead_silence_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.leading_silence_samples IS NOT NULL AND NEW.leading_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'leading_silence_samples must be >= 0');
END;
CREATE TRIGGER trg_ru_nonneg_trail_silence
    BEFORE INSERT ON render_units
    WHEN NEW.trailing_silence_samples IS NOT NULL AND NEW.trailing_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'trailing_silence_samples must be >= 0');
END;
CREATE TRIGGER trg_ru_nonneg_trail_silence_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.trailing_silence_samples IS NOT NULL AND NEW.trailing_silence_samples < 0
BEGIN
    SELECT RAISE(ABORT, 'trailing_silence_samples must be >= 0');
END;
CREATE TRIGGER trg_ru_visible_containment
    BEFORE INSERT ON render_units
    WHEN NEW.visible_start_sample IS NOT NULL AND NEW.visible_end_sample IS NOT NULL
     AND NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND (NEW.visible_start_sample < NEW.generation_start_sample
          OR NEW.visible_end_sample > NEW.generation_end_sample)
BEGIN
    SELECT RAISE(ABORT, 'visible interval must be contained within generation interval');
END;
CREATE TRIGGER trg_ru_visible_containment_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.visible_start_sample IS NOT NULL AND NEW.visible_end_sample IS NOT NULL
     AND NEW.generation_start_sample IS NOT NULL AND NEW.generation_end_sample IS NOT NULL
     AND (NEW.visible_start_sample < NEW.generation_start_sample
          OR NEW.visible_end_sample > NEW.generation_end_sample)
BEGIN
    SELECT RAISE(ABORT, 'visible interval must be contained within generation interval');
END;
CREATE TRIGGER trg_ru_audio_policy
    BEFORE INSERT ON render_units
    WHEN NEW.audio_policy IS NOT NULL
     AND NEW.audio_policy NOT IN ('HERO_SYNC_LOCKED','BROLL_FLEX','BROLL_SYNCED_ACTION',
                                  'AMBIENCE_OR_SFX','MUSIC_BED','SILENT_GRAPHIC',
                                  'narration_overlay','silent','baked_in','generated_tts',
                                  'strip','ambient')
BEGIN
    SELECT RAISE(ABORT, 'invalid audio_policy');
END;
CREATE TRIGGER trg_ru_audio_policy_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.audio_policy IS NOT NULL
     AND NEW.audio_policy NOT IN ('HERO_SYNC_LOCKED','BROLL_FLEX','BROLL_SYNCED_ACTION',
                                  'AMBIENCE_OR_SFX','MUSIC_BED','SILENT_GRAPHIC',
                                  'narration_overlay','silent','baked_in','generated_tts',
                                  'strip','ambient')
BEGIN
    SELECT RAISE(ABORT, 'invalid audio_policy');
END;
CREATE TRIGGER trg_ru_final_audio_source
    BEFORE INSERT ON render_units
    WHEN NEW.final_audio_source IS NOT NULL
     AND NEW.final_audio_source NOT IN ('master_narration','provider_audio','none')
BEGIN
    SELECT RAISE(ABORT, 'invalid final_audio_source');
END;
CREATE TRIGGER trg_ru_final_audio_source_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.final_audio_source IS NOT NULL
     AND NEW.final_audio_source NOT IN ('master_narration','provider_audio','none')
BEGIN
    SELECT RAISE(ABORT, 'invalid final_audio_source');
END;
CREATE TRIGGER trg_ru_provider_audio_usage
    BEFORE INSERT ON render_units
    WHEN NEW.provider_audio_usage IS NOT NULL
     AND NEW.provider_audio_usage NOT IN ('diagnostic_only','final_mix','discarded')
BEGIN
    SELECT RAISE(ABORT, 'invalid provider_audio_usage');
END;
CREATE TRIGGER trg_ru_provider_audio_usage_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.provider_audio_usage IS NOT NULL
     AND NEW.provider_audio_usage NOT IN ('diagnostic_only','final_mix','discarded')
BEGIN
    SELECT RAISE(ABORT, 'invalid provider_audio_usage');
END;
CREATE TRIGGER trg_ru_text_policy
    BEFORE INSERT ON render_units
    WHEN NEW.text_policy IS NOT NULL
     AND NEW.text_policy NOT IN ('NO_VISIBLE_TEXT','UNREADABLE_BACKGROUND','POST_COMPOSITE',
                                  'REAL_SCREEN_CAPTURE','DETERMINISTIC_GRAPHIC')
BEGIN
    SELECT RAISE(ABORT, 'invalid text_policy');
END;
CREATE TRIGGER trg_ru_text_policy_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.text_policy IS NOT NULL
     AND NEW.text_policy NOT IN ('NO_VISIBLE_TEXT','UNREADABLE_BACKGROUND','POST_COMPOSITE',
                                  'REAL_SCREEN_CAPTURE','DETERMINISTIC_GRAPHIC')
BEGIN
    SELECT RAISE(ABORT, 'invalid text_policy');
END;
CREATE TRIGGER trg_ru_hero_master_consistent
    BEFORE INSERT ON render_units
    WHEN NEW.audio_policy = 'HERO_SYNC_LOCKED'
     AND (NEW.master_audio_artifact_id IS NOT NULL AND NEW.master_audio_sha256 IS NULL
          OR NEW.master_audio_artifact_id IS NULL AND NEW.master_audio_sha256 IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'HERO_SYNC_LOCKED: master_audio_artifact_id and master_audio_sha256 must both be set or both null');
END;
CREATE TRIGGER trg_ru_hero_master_consistent_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.audio_policy = 'HERO_SYNC_LOCKED'
     AND (NEW.master_audio_artifact_id IS NOT NULL AND NEW.master_audio_sha256 IS NULL
          OR NEW.master_audio_artifact_id IS NULL AND NEW.master_audio_sha256 IS NOT NULL)
BEGIN
    SELECT RAISE(ABORT, 'HERO_SYNC_LOCKED: master_audio_artifact_id and master_audio_sha256 must both be set or both null');
END;
CREATE TABLE concept_memory (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    concept_key TEXT NOT NULL,
    concept_hash TEXT NOT NULL,
    visual_brief TEXT,
    render_unit_id TEXT REFERENCES render_units(id),
    created_at TEXT NOT NULL,
    UNIQUE(production_id, concept_hash)
);
CREATE INDEX idx_concept_memory_production ON concept_memory(production_id);
CREATE TRIGGER trg_ru_render_mode
    BEFORE INSERT ON render_units
    WHEN NEW.render_mode NOT IN ('generated_video', 'deterministic_graphic', 'post_composite', 'still_kenburns', 'hero_lipsync')
BEGIN
    SELECT RAISE(ABORT, 'invalid render_mode');
END;
CREATE TRIGGER trg_ru_render_mode_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.render_mode NOT IN ('generated_video', 'deterministic_graphic', 'post_composite', 'still_kenburns', 'hero_lipsync')
BEGIN
    SELECT RAISE(ABORT, 'invalid render_mode');
END;
CREATE UNIQUE INDEX one_active_revision_per_kind
    ON document_revisions (production_id, kind)
    WHERE status = 'active';

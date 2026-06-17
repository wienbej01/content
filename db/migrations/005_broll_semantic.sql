-- Sprint R7+R8: B-Roll Semantic Contract Schema (R7-004)
-- Adds semantic fields to render_units for B-roll purpose enforcement,
-- concept deduplication, and render-mode routing.
--
-- Rollback: see end of file.

-- ---------------------------------------------------------------------------
-- 1. B-roll semantic intent columns
-- ---------------------------------------------------------------------------

ALTER TABLE render_units ADD COLUMN visual_function TEXT;
ALTER TABLE render_units ADD COLUMN narrative_claim TEXT;
ALTER TABLE render_units ADD COLUMN information_to_show TEXT;
ALTER TABLE render_units ADD COLUMN viewer_takeaway TEXT;
ALTER TABLE render_units ADD COLUMN required_action TEXT;
ALTER TABLE render_units ADD COLUMN forbidden_cliches TEXT;
ALTER TABLE render_units ADD COLUMN distinctness_requirement TEXT;
ALTER TABLE render_units ADD COLUMN semantic_acceptance_criteria TEXT;
ALTER TABLE render_units ADD COLUMN render_mode TEXT NOT NULL DEFAULT 'generated_video';
ALTER TABLE render_units ADD COLUMN concept_key TEXT;
ALTER TABLE render_units ADD COLUMN concept_hash TEXT;

-- ---------------------------------------------------------------------------
-- 2. Concept memory table — reject repeated concepts before spend
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS concept_memory (
    id TEXT PRIMARY KEY,
    production_id TEXT NOT NULL REFERENCES productions(id) ON DELETE CASCADE,
    concept_key TEXT NOT NULL,
    concept_hash TEXT NOT NULL,
    visual_brief TEXT,
    render_unit_id TEXT REFERENCES render_units(id),
    created_at TEXT NOT NULL,
    UNIQUE(production_id, concept_hash)
);

CREATE INDEX IF NOT EXISTS idx_concept_memory_production ON concept_memory(production_id);

-- ---------------------------------------------------------------------------
-- 3. Render-mode constraint trigger
-- ---------------------------------------------------------------------------

CREATE TRIGGER IF NOT EXISTS trg_ru_render_mode
    BEFORE INSERT ON render_units
    WHEN NEW.render_mode NOT IN ('generated_video', 'deterministic_graphic', 'post_composite', 'still_kenburns', 'hero_lipsync')
BEGIN
    SELECT RAISE(ABORT, 'invalid render_mode');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_render_mode_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.render_mode NOT IN ('generated_video', 'deterministic_graphic', 'post_composite', 'still_kenburns', 'hero_lipsync')
BEGIN
    SELECT RAISE(ABORT, 'invalid render_mode');
END;

-- ---------------------------------------------------------------------------
-- 4. Deterministic graphic text validation columns
-- ---------------------------------------------------------------------------

ALTER TABLE render_units ADD COLUMN graphic_text_content TEXT;
ALTER TABLE render_units ADD COLUMN graphic_text_hash TEXT;

-- ============================================================================
-- ROLLBACK
-- ============================================================================
--
-- DROP TRIGGER IF EXISTS trg_ru_render_mode;
-- DROP TRIGGER IF EXISTS trg_ru_render_mode_upd;
-- DROP INDEX IF EXISTS idx_concept_memory_production;
-- DROP TABLE IF EXISTS concept_memory;
-- ALTER TABLE render_units DROP COLUMN graphic_text_hash;
-- ALTER TABLE render_units DROP COLUMN graphic_text_content;
-- ALTER TABLE render_units DROP COLUMN concept_hash;
-- ALTER TABLE render_units DROP COLUMN concept_key;
-- ALTER TABLE render_units DROP COLUMN render_mode;
-- ALTER TABLE render_units DROP COLUMN semantic_acceptance_criteria;
-- ALTER TABLE render_units DROP COLUMN distinctness_requirement;
-- ALTER TABLE render_units DROP COLUMN forbidden_cliches;
-- ALTER TABLE render_units DROP COLUMN required_action;
-- ALTER TABLE render_units DROP COLUMN viewer_takeaway;
-- ALTER TABLE render_units DROP COLUMN information_to_show;
-- ALTER TABLE render_units DROP COLUMN narrative_claim;
-- ALTER TABLE render_units DROP COLUMN visual_function;

-- Sprint 14: Hero Framing Metadata for Lip-sync Policy Selection (Ticket S14_T002)
-- Adds hero_framing column to render_units to support tiered lip-sync policy evaluation.
-- Hero framing determines which lip-sync threshold policy to apply (close_hero, medium_hero, wide_hero).
--
-- Rollback: see end of file.

-- ---------------------------------------------------------------------------
-- 1. Add hero_framing column to render_units
-- ---------------------------------------------------------------------------

ALTER TABLE render_units ADD COLUMN hero_framing TEXT;

-- ---------------------------------------------------------------------------
-- 2. Add CHECK constraint for hero_framing values
-- ---------------------------------------------------------------------------

-- Valid values: 'close', 'medium', 'wide', or NULL (NULL defaults to 'close' for hero units)
CREATE TRIGGER IF NOT EXISTS trg_ru_hero_framing
    BEFORE INSERT ON render_units
    WHEN NEW.hero_framing IS NOT NULL
     AND NEW.hero_framing NOT IN ('close', 'medium', 'wide')
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED_INVALID_HERO_FRAMING: invalid hero_framing value. Valid values: close, medium, wide, or NULL');
END;

CREATE TRIGGER IF NOT EXISTS trg_ru_hero_framing_upd
    BEFORE UPDATE ON render_units
    WHEN NEW.hero_framing IS NOT NULL
     AND NEW.hero_framing NOT IN ('close', 'medium', 'wide')
BEGIN
    SELECT RAISE(ABORT, 'BLOCKED_INVALID_HERO_FRAMING: invalid hero_framing value. Valid values: close, medium, wide, or NULL');
END;

-- ============================================================================
-- ROLLBACK (for reference; execute via test harness)
-- ============================================================================
--
-- DROP TRIGGER IF EXISTS trg_ru_hero_framing;
-- DROP TRIGGER IF EXISTS trg_ru_hero_framing_upd;
-- ALTER TABLE render_units DROP COLUMN hero_framing;

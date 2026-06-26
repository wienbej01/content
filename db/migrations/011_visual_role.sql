-- S15-T002: Add visual_role field to creative beats and render units
-- Separates editorial/semantic function from technical asset_type.
-- Allows publish-grade validation to require meaningful visual roles.

-- Add visual_role to creative_beats
ALTER TABLE creative_beats ADD COLUMN visual_role TEXT;

-- Add visual_role to render_units
ALTER TABLE render_units ADD COLUMN visual_role TEXT;

-- Create allowed roles enum for referential integrity
CREATE TABLE IF NOT EXISTS visual_roles (
    role TEXT PRIMARY KEY,
    category TEXT NOT NULL,  -- 'hero', 'broll', 'graphic'
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Insert required visual roles
INSERT INTO visual_roles (role, category, description) VALUES
    ('hero_trust', 'hero', 'Hero establishing speaker credibility or expertise'),
    ('hero_hook', 'hero', 'Hero opening hook to grab attention'),
    ('hero_cta', 'hero', 'Hero call-to-action frame'),
    ('broll_evidence', 'broll', 'B-roll demonstrating factual claims or evidence'),
    ('broll_metaphor', 'broll', 'B-roll illustrating abstract concepts via metaphor'),
    ('broll_emotional_reset', 'broll', 'B-roll emotional palette shift or pacing reset'),
    ('graphic_framework', 'graphic', 'Framework graphic establishing conceptual structure'),
    ('graphic_comparison', 'graphic', 'Comparison graphic showing two or more items'),
    ('graphic_process', 'graphic', 'Process graphic showing steps or flow'),
    ('graphic_data', 'graphic', 'Data graphic showing statistics or charts');

-- Add foreign key constraints (deferred for compatibility, enforced in application layer)
-- Note: SQLite doesn't support ALTER TABLE ADD FOREIGN KEY, so constraints are app-enforced

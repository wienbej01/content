"""Shared fixture helpers for Sprint 8 E2E tests.

Builds a deterministic production (no LLM, no paid TTS) and drives it through the
DB-native stage graph in YT_TEST_MODE. Used by test_s8_full_production (T02),
test_s8_projections_resume (T03), and test_s8_crash_matrix (T04).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

PROJECTS = ROOT / "Videos" / "Projects"

NARRATION_SECONDS = 45.0


def _ffmpeg_audio(path: Path, duration: float):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=200:duration={duration}:sample_rate=48000",
         "-ac", "1", "-ar", "48000", str(path)],
        capture_output=True, check=True)


def build_production(slug: str = "s8_e2e"):
    """Seed a deterministic production and return (pid, slug, project_dir).

    Research/script/storyboard are authored directly (LLM stages get marked done
    and skipped); the master narration is a deterministic ffmpeg fixture.
    """
    import production_db as _db
    from authoring_service import save_research_brief, save_script, save_storyboard

    _db.migrate()
    prod = _db.ensure_production(slug, seed="compound interest explained simply",
                                 video_type="short")
    pid = prod["id"]

    save_research_brief(
        pid, {"title": "Compound Interest", "summary": "explainer"},
        citations=[{"url": "https://a", "title": "A", "source_type": "web", "is_primary": True},
                   {"url": "https://b", "title": "B", "source_type": "web", "is_primary": True},
                   {"url": "https://c", "title": "C", "source_type": "web", "is_primary": True}])

    segs = [
        {"label": "B1", "text": "Compound interest is the most powerful force in personal finance, and it works whether you understand it or not."},
        {"label": "B2", "text": "Here is how a small deposit grows over decades through reinvestment."},
        {"label": "B3", "text": "The key insight is that your earnings start earning their own earnings, year after year."},
        {"label": "B4", "text": "Over thirty years, even a modest monthly contribution becomes a substantial sum."},
        {"label": "B5", "text": "Start early, stay consistent, and let time do the heavy lifting for you."},
    ]
    save_script(pid, {"segments": segs})

    beats = [
        {"label": "B1", "shot_type": "talking_head_hero", "narration_text": segs[0]["text"]},
        {"label": "B2", "shot_type": "broll_environment", "narration_text": segs[1]["text"],
         "visual_intent": {
            "visual_function": "illustrate", "concept_key": "b2_growth_curve",
            "concept_hash": "b2_growth_curve",
            "narrative_claim": "Small deposits grow multiplicatively over time.",
            "information_to_show": "Upward curving growth chart on a desk.",
            "viewer_takeaway": "Compounding turns small inputs into large outputs.",
            "required_action": "Slow push-in on the rising curve.",
            "distinctness_requirement": "Real chart with grid, not an abstract icon.",
            "semantic_acceptance_criteria": "Curve rises left-to-right; axis labels visible."}},
        {"label": "B3", "shot_type": "talking_head_hero", "narration_text": segs[2]["text"]},
        {"label": "B4", "shot_type": "broll_human", "narration_text": segs[3]["text"],
         "visual_intent": {
            "visual_function": "contextualize", "concept_key": "b4_calendar_passing",
            "concept_hash": "b4_calendar_passing",
            "narrative_claim": "Decades of consistent contributions add up.",
            "information_to_show": "Hands turning calendar pages across years.",
            "viewer_takeaway": "Time is the lever that amplifies saving.",
            "required_action": "Calendar pages flip forward in time-lapse.",
            "distinctness_requirement": "Wall calendar, not a phone or screen UI.",
            "semantic_acceptance_criteria": "Multiple months visible flipping; no laptops."}},
        {"label": "B5", "shot_type": "local_graphic", "narration_text": segs[4]["text"],
         "graphics": {"text": "COMPOUND INTEREST"}},
    ]
    save_storyboard(pid, {"beats": beats})

    for stage in ["research", "write_script", "review_script", "gate_a_content",
                  "storyboard", "review_storyboard"]:
        _db.mirror_stage_state(slug, stage, "done")

    project_dir = PROJECTS / slug
    (project_dir / "narration").mkdir(parents=True, exist_ok=True)
    (project_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    (project_dir / "transcripts" / "0_research.md").write_text("# compound interest")
    _ffmpeg_audio(project_dir / "narration" / "continuous.mp3", NARRATION_SECONDS)

    return pid, slug, project_dir


def run_to_completion(pid: str, max_passes: int = 12) -> bool:
    """Drive run_production (resume loop) until the production is 'completed'."""
    import production_db as _db
    import produce_db

    for _ in range(max_passes):
        try:
            produce_db.run_production(pid)
        except SystemExit:
            pass
        conn = _db.connect()
        row = conn.execute("SELECT status FROM productions WHERE id=?", (pid,)).fetchone()
        conn.close()
        if row and row["status"] == "completed":
            return True
    return False


def latest_stage_status(pid: str, stage: str) -> str | None:
    import production_db as _db
    conn = _db.connect()
    row = conn.execute(
        "SELECT status FROM stage_runs WHERE production_id=? AND stage_name=? "
        "ORDER BY attempt DESC LIMIT 1", (pid, stage)).fetchone()
    conn.close()
    return row["status"] if row else None

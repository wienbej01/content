"""Sprint 8 — Full local 45-second E2E production (S8-T01 / S8-T02).

Drives a real production through the entire DB-native stage graph via
run_production() in YT_TEST_MODE=1 and asserts a valid 16:9 deliverable.

No paid calls: research/script/storyboard are authored deterministically (the LLM
stages are marked done and skipped), the master narration is a deterministic
ffmpeg fixture (TTS refuses paid calls in test mode — see test_s8_tts_paid_guard),
and YT_TEST_MODE substitutes FakeProviderAdapter (real moving ffmpeg media) for
media generation.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

PROJECTS = ROOT / "Videos" / "Projects"


def _ffmpeg_audio(path: Path, duration: float):
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=200:duration={duration}:sample_rate=48000",
         "-ac", "1", "-ar", "48000", str(path)],
        capture_output=True, check=True)


@pytest.mark.slow
def test_full_45s_production_e2e(tmp_path, monkeypatch):
    monkeypatch.setenv("YT_TEST_MODE", "1")

    import production_db as _db
    from authoring_service import save_research_brief, save_script, save_storyboard
    import produce_db

    _db.migrate()
    prod = _db.ensure_production("s8_e2e", seed="compound interest explained simply",
                                 video_type="short")
    pid = prod["id"]
    slug = prod["project_slug"]

    # 1) Research brief (>=3 primary sources enforced)
    save_research_brief(
        pid, {"title": "Compound Interest", "summary": "explainer"},
        citations=[{"url": "https://a", "title": "A", "source_type": "web", "is_primary": True},
                   {"url": "https://b", "title": "B", "source_type": "web", "is_primary": True},
                   {"url": "https://c", "title": "C", "source_type": "web", "is_primary": True}])

    # 2) Script — 5 segments
    segs = [
        {"label": "B1", "text": "Compound interest is the most powerful force in personal finance, and it works whether you understand it or not."},
        {"label": "B2", "text": "Here is how a small deposit grows over decades through reinvestment."},
        {"label": "B3", "text": "The key insight is that your earnings start earning their own earnings, year after year."},
        {"label": "B4", "text": "Over thirty years, even a modest monthly contribution becomes a substantial sum."},
        {"label": "B5", "text": "Start early, stay consistent, and let time do the heavy lifting for you."},
    ]
    save_script(pid, {"segments": segs})

    # 3) Storyboard — 2 hero, 2 broll (distinct semantic functions), 1 graphic,
    #    with a hero -> broll -> hero continuity chain (B1 -> B2 -> B3).
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

    # 4) Skip the LLM authoring stages — their DB output is already seeded above.
    for stage in ["research", "write_script", "review_script", "gate_a_content",
                  "storyboard", "review_storyboard"]:
        _db.mirror_stage_state(slug, stage, "done")

    # 5) Pre-provide the deterministic master narration (TTS refuses paid calls in
    #    test mode). Must live in the SAME project dir the orchestrator uses
    #    (PROJECTS / project_slug) — this was the probe's pitfall.
    project_dir = PROJECTS / slug
    (project_dir / "narration").mkdir(parents=True, exist_ok=True)
    (project_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    (project_dir / "transcripts" / "0_research.md").write_text("# compound interest")
    _ffmpeg_audio(project_dir / "narration" / "continuous.mp3", 45.0)

    # 6) Drive the full stage graph (resume loop handles the multi-step
    #    generate_media lifecycle and any boundary re-runs).
    completed = False
    for _ in range(10):
        try:
            produce_db.run_production(pid)
        except SystemExit:
            pass
        conn = _db.connect()
        status = conn.execute("SELECT status FROM productions WHERE id=?", (pid,)).fetchone()
        conn.close()
        if status and status["status"] == "completed":
            completed = True
            break

    assert completed, "production did not reach 'completed'"

    # 7) Assert a valid 16:9 deliverable with audio + motion (no freeze).
    outputs = sorted(PROJECTS.glob(f"{slug}/*_16x9.mp4"))
    assert outputs, f"no 16x9 deliverable produced in {PROJECTS / slug}"
    out = outputs[0]

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,codec_type",
         "-of", "json", str(out)], capture_output=True, text=True, check=True)
    import json
    info = json.loads(probe.stdout)
    vs = [s for s in info["streams"] if s.get("codec_type") == "video"][0]
    assert vs["width"] == 1920 and vs["height"] == 1080, \
        f"expected 1920x1080, got {vs['width']}x{vs['height']}"
    dur = float(info["format"]["duration"])
    assert 30.0 <= dur <= 60.0, f"deliverable duration {dur:.1f}s outside 30-60s"
    has_audio = any(s.get("codec_type") == "audio" for s in info["streams"])
    assert has_audio, "deliverable has no audio stream"

    # No frozen span > 1.5s (S8-T05 criterion: no frozen media).
    fd = subprocess.run(
        ["ffmpeg", "-i", str(out), "-vf",
         "freezedetect=noise=0.001:duration=1.5", "-f", "null", "-"],
        capture_output=True, text=True)
    assert "lavfi.freezedetect.freeze_start" not in fd.stderr, \
        "deliverable contains a frozen span > 1.5s"

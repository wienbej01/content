"""S9-C01 — Deterministic script-duration compliance.

Defect (D-DUR): the real `ai_notes_teaser` production accepted a 356-word teaser
script (active revision in db/s9_real.db) that narrates to 198s — far over the
teaser target_sec_range of [50,100]s and the word_range of [140,230] words.
Nothing rejected it: `invoke_write_script` saved the writer output verbatim and
`invoke_review_script` ran an LLM review_loop then saved the result, with no
programmatic budget gate.

Root cause: the format budget lived only in prompt text (`episode_format.format_block`),
not in a deterministic gate. (Note: the James voice measures ~138 wpm on the clean
s9_paid sample [70 words -> 30.35s], so the teaser word_range [140,230] is already
pace-consistent with target_sec_range [50,100]s — the budget is NOT miscalibrated;
the missing piece is enforcement.)

This test pins the gate. The gate-logic tests are fully real (real word counts vs
the format spec). The invoker-wiring tests stub `llm_call` only because a real LLM
call is not possible in CI — that is the irreducible I/O stub; the gate logic itself
is exercised for real.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import produce_db
from authoring_service import save_research_brief, get_script
from episode_format import (
    FORMAT_PROFILES,
    count_script_words,
    script_within_budget,
)


def _words(n: int) -> str:
    """Real n-word spoken string."""
    return " ".join(["word"] * n)


# --- gate logic: REAL word counts vs the format spec (no mocks) ---

def test_count_script_words_sums_segments():
    payload = {"segments": [{"text": _words(50)}, {"text": "x", "word_count": 30}]}
    assert count_script_words(payload) == 80  # 50 from text + 30 from word_count


def test_within_budget_rejects_over_length_real_defect():
    """The actual ai_notes_teaser defect: 356 words vs a 140-230 budget."""
    over = {"segments": [{"text": _words(356)}]}
    assert script_within_budget(over, "teaser") is False


def test_within_budget_accepts_in_range():
    ok = {"segments": [{"text": _words(180)}]}
    assert script_within_budget(ok, "teaser") is True


def test_within_budget_boundary():
    lo, hi = FORMAT_PROFILES["teaser"]["word_range"]
    assert script_within_budget({"segments": [{"text": _words(lo)}]}, "teaser") is True
    assert script_within_budget({"segments": [{"text": _words(hi)}]}, "teaser") is True
    assert script_within_budget({"segments": [{"text": _words(hi + 1)}]}, "teaser") is False
    assert script_within_budget({"segments": [{"text": _words(lo - 1)}]}, "teaser") is False


def test_within_budget_unknown_format_does_not_crash():
    # get_format() falls back to the explainer profile; the gate must still return a bool.
    assert isinstance(script_within_budget({"segments": [{"text": _words(100)}]}, "bogus"), bool)


# --- invoker wiring: llm_call stubbed (irreducible — no real LLM in CI); gate logic real ---

def _seed(slug: str, video_type: str) -> str:
    prod = _db.ensure_production(slug, seed=slug, video_type=video_type)
    pid = prod["id"]
    citations = [
        {"url": f"https://src.example/{i}", "title": f"src{i}", "source_type": "paper",
         "is_primary": True}
        for i in range(3)
    ]
    save_research_brief(pid, {"research_text": "context", "key_claims": [], "sources": []},
                        citations=citations)
    return pid


def _inputs(pid: str, slug: str, video_type: str) -> dict:
    return {"production_id": pid, "project_slug": slug, "video_type": video_type}


def _script(video_type: str, n_words: int) -> dict:
    return {
        "title": "t", "video_type": video_type, "narration_mode": "continuous_voiceover",
        "segments": [{"id": "001_hook", "audio_mode": "generated_tts", "text": _words(n_words)}],
    }


@pytest.fixture
def _clean_project_dirs():
    yield
    import shutil
    for slug in ("c01_over", "c01_ok", "c01_review_over"):
        p = ROOT / "Videos" / "Projects" / slug
        if p.exists():
            shutil.rmtree(p)


def test_invoke_write_script_rejects_over_budget(tmp_path, _clean_project_dirs):
    """REPRODUCES the defect then pins the fix: an over-budget writer output must
    raise and must NOT be saved."""
    pid = _seed("c01_over", "teaser")
    over = _script("teaser", 356)
    with patch("llm_call.llm_call", return_value=(over, "{}", None, None)):
        with pytest.raises(RuntimeError):
            produce_db.invoke_write_script(_inputs(pid, "c01_over", "teaser"), tmp_path)
    assert get_script(pid) is None  # nothing persisted


def test_invoke_write_script_accepts_compliant(tmp_path, _clean_project_dirs):
    """Happy path stays green: a within-budget script is saved."""
    pid = _seed("c01_ok", "teaser")
    ok = _script("teaser", 180)
    with patch("llm_call.llm_call", return_value=(ok, "{}", None, None)):
        res = produce_db.invoke_write_script(_inputs(pid, "c01_ok", "teaser"), tmp_path)
    assert res["status"] == "saved"
    assert get_script(pid) is not None


def test_invoke_review_script_rejects_over_budget(tmp_path, _clean_project_dirs):
    """The reviewed/reviSed final must also satisfy the budget or the stage fails."""
    pid = _seed("c01_review_over", "teaser")
    # Seed an in-budget current script, then have the reviewer loop "revise" into an over-budget final.
    from authoring_service import save_script
    save_script(pid, _script("teaser", 180))
    over_final = _script("teaser", 356)

    # review_loop is driven by llm_call (reviewer verdicts) + the reviser (write_script -> llm_call).
    # Stub llm_call so the reviewer passes and the reviser emits the over-budget final.
    call = {"n": 0}

    def fake_llm(**kwargs):
        call["n"] += 1
        # First calls: reviewer verdicts (pass). Then the reviser write_script call returns over_final.
        return (over_final, "{}", "sonnet_creative", "claude-sonnet-4.5")

    with patch("llm_call.llm_call", side_effect=fake_llm):
        with pytest.raises(RuntimeError):
            produce_db.invoke_review_script(_inputs(pid, "c01_review_over", "teaser"), tmp_path)

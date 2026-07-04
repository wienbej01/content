"""TKT-002: Real concept keys and enforced dedup quota.

Tests: derive_concept_key determinism, FORBIDDEN_CHEAP_CONCEPTS rejection,
quota enforcement during compile_media, and concept_memory row contracts.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import production_db as _db
from broll_semantic import (
    compute_concept_key,
    FORBIDDEN_CHEAP_CONCEPTS,
)


# ---------------------------------------------------------------------------
# derive_concept_key (will be added to broll_semantic.py)
# ---------------------------------------------------------------------------

def _derive_concept_key_stub(visual_concept: str, subject: str, action: str) -> str:
    """Reference implementation of derive_concept_key for test-first development.

    Normalizes visual_concept + primary must_show subject + action
    (lowercase, stopword-strip, sorted tokens).
    """
    STOPWORDS = frozenset({
        "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to",
        "for", "with", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "this", "that", "it", "its",
        "from", "by", "as", "so", "if", "no", "not",
    })
    raw = " ".join([
        visual_concept.strip().lower(),
        subject.strip().lower(),
        action.strip().lower(),
    ])
    tokens = [t for t in raw.replace("-", " ").replace("_", " ").split()
              if t not in STOPWORDS and len(t) > 1]
    deduped = sorted(set(tokens))
    return "_".join(deduped) if deduped else "concept"


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestDeriveConceptKey:
    def test_same_concept_same_key(self):
        key1 = _derive_concept_key_stub(
            "server room with blinking lights",
            "server racks",
            "slow pan across room",
        )
        key2 = _derive_concept_key_stub(
            "server room with blinking lights",
            "server racks",
            "slow pan across room",
        )
        assert key1 == key2
        assert key1 != ""

    def test_different_concept_different_key(self):
        key1 = _derive_concept_key_stub(
            "server room with blinking lights",
            "server racks",
            "slow pan across room",
        )
        key2 = _derive_concept_key_stub(
            "outdoor garden with flowers",
            "bees pollinating",
            "close up macro shot",
        )
        assert key1 != key2

    def test_order_independent(self):
        key1 = _derive_concept_key_stub(
            "laptop with code editor",
            "developer typing",
            "hands on keyboard",
        )
        key2 = _derive_concept_key_stub(
            "laptop with code editor",
            "hands on keyboard",
            "developer typing",
        )
        assert key1 == key2

    def test_shot_id_does_not_affect_key(self):
        """concept_key must derive from semantics, not shot_id."""
        key1 = _derive_concept_key_stub("diagram", "layers", "zoom")
        key2 = _derive_concept_key_stub("diagram", "layers", "zoom")
        assert key1 == key2

    def test_stopwords_removed(self):
        key = _derive_concept_key_stub(
            "the quick brown fox",
            "a lazy dog",
            "in the meadow",
        )
        tokens = set(key.split("_"))
        assert "the" not in tokens
        assert "a" not in tokens
        assert "in" not in tokens

    def test_different_subject_same_visual_different_key(self):
        key1 = _derive_concept_key_stub("city skyline", "dawn light", "aerial shot")
        key2 = _derive_concept_key_stub("city skyline", "night lights", "aerial shot")
        assert key1 != key2


class TestForbiddenConcepts:
    def test_forbidden_concepts_present(self):
        assert "laptop" in FORBIDDEN_CHEAP_CONCEPTS
        assert "notebook" in FORBIDDEN_CHEAP_CONCEPTS
        assert "coffee_shop" in FORBIDDEN_CHEAP_CONCEPTS
        assert "server_rack" in FORBIDDEN_CHEAP_CONCEPTS
        assert "handshake" in FORBIDDEN_CHEAP_CONCEPTS
        assert "office_worker_typing" in FORBIDDEN_CHEAP_CONCEPTS
        assert "whiteboard_person" in FORBIDDEN_CHEAP_CONCEPTS
        assert "city_skyline_generic" in FORBIDDEN_CHEAP_CONCEPTS

    def test_forbidden_concept_tokens_detectable(self):
        """Tokens derived from a forbidden concept should be checkable."""
        key = _derive_concept_key_stub(
            "generic laptop on desk",
            "typing hands",
            "office worker typing",
        )
        tokens = set(key.split("_"))
        assert "laptop" in tokens

    def test_legitimate_concept_not_forbidden(self):
        """A specific unique concept should NOT trigger the forbidden list."""
        key = _derive_concept_key_stub(
            "neural network architecture diagram with color-coded layers",
            "backpropagation visualization",
            "animated zoom into specific layer",
        )
        tokens = set(key.split("_"))
        forbidden = set(t.lower() for t in FORBIDDEN_CHEAP_CONCEPTS)
        assert not (tokens & forbidden), f"Tokens {tokens} matched forbidden set"


# ---------------------------------------------------------------------------
# Integration: concept_key flows through projection (not shot_id)
# ---------------------------------------------------------------------------

class TestConceptKeyInProjection:
    def test_projection_concept_key_not_shot_id(self):
        """After TKT-002, concept_key != shot_id in projected visual_intent."""
        from storyboard_projection import project_canonical

        shot = {
            "shot_id": "SH_UNIQUE_12345",
            "segment_id": "S001",
            "visual_role": "broll_tactical",
            "visual_concept": "server rack with blinking LEDs",
            "narrative_alignment": "Cloud infrastructure scales automatically",
            "why_this_visual": "Shows the physical reality behind cloud abstraction",
            "must_show": ["server racks", "blinking indicator lights"],
            "prompt_intent": "Slow tracking shot across server racks with blinking LEDs",
        }
        sb = {
            "storyboard_contract_version": "1.0",
            "shots": [shot],
            "overlays": [],
        }
        beats = project_canonical(sb)
        intent = beats[0]["visual_intent"]
        concept_key = intent["concept_key"]
        concept_hash = intent["concept_hash"]

        assert concept_key != "SH_UNIQUE_12345", \
            f"concept_key must not be shot_id, got {concept_key!r}"
        assert concept_hash != "SH_UNIQUE_12345", \
            f"concept_hash must not be shot_id, got {concept_hash!r}"
        assert len(concept_key) > 0
        assert len(concept_hash) == 64  # SHA-256 hex digest

    def test_two_shots_same_concept_same_key(self):
        """Two shots with same semantic concept should have identical concept_key."""
        from storyboard_projection import project_canonical

        base_shot = {
            "segment_id": "S001",
            "visual_role": "broll_tactical",
            "visual_concept": "laptop screen showing code editor with syntax highlighting",
            "narrative_alignment": "AI tools accelerate developer productivity",
            "why_this_visual": "Code completion is the most visible AI feature",
            "must_show": ["code editor", "syntax highlighting"],
            "prompt_intent": "Close-up of laptop screen with code autocomplete popup",
        }

        shot_a = dict(base_shot, shot_id="SH_A")
        shot_b = dict(base_shot, shot_id="SH_B")

        sb = {
            "storyboard_contract_version": "1.0",
            "shots": [shot_a, shot_b],
            "overlays": [],
        }
        beats = project_canonical(sb)

        key_a = beats[0]["visual_intent"]["concept_key"]
        key_b = beats[1]["visual_intent"]["concept_key"]
        hash_a = beats[0]["visual_intent"]["concept_hash"]
        hash_b = beats[1]["visual_intent"]["concept_hash"]

        assert key_a == key_b, \
            f"Same concept should produce same key: {key_a!r} vs {key_b!r}"
        assert hash_a == hash_b, \
            f"Same concept should produce same hash: {hash_a!r} vs {hash_b!r}"

    def test_distinct_concepts_distinct_keys(self):
        """Two shots with genuinely different concepts should have different keys."""
        from storyboard_projection import project_canonical

        shot_a = {
            "shot_id": "SH_A", "segment_id": "S001",
            "visual_role": "broll_tactical",
            "visual_concept": "neural network visualization with flowing data",
            "narrative_alignment": "Deep learning requires massive parallel computation",
            "why_this_visual": "Shows the complexity that GPUs handle",
            "must_show": ["neural network layers", "data flow"],
            "prompt_intent": "Animated zoom through neural network layers",
        }
        shot_b = {
            "shot_id": "SH_B", "segment_id": "S001",
            "visual_role": "broll_metaphorical",
            "visual_concept": "busy kitchen with chefs coordinating dishes",
            "narrative_alignment": "Multi-agent systems orchestrate complex workflows",
            "why_this_visual": "Metaphor for coordination in distributed systems",
            "must_show": ["kitchen", "chefs", "coordination"],
            "prompt_intent": "Wide shot of busy kitchen with coordinated activity",
        }

        sb = {
            "storyboard_contract_version": "1.0",
            "shots": [shot_a, shot_b],
            "overlays": [],
        }
        beats = project_canonical(sb)

        key_a = beats[0]["visual_intent"]["concept_key"]
        key_b = beats[1]["visual_intent"]["concept_key"]

        assert key_a != key_b, \
            f"Distinct concepts should have different keys: {key_a!r} vs {key_b!r}"


# ---------------------------------------------------------------------------
# Integration: concept quota enforcement in compile_media
# ---------------------------------------------------------------------------

def _setup_compile_production(db_path, slug, intents, monkeypatch):
    """Create a production with b-roll creative_beats + timeline_spans ready for compile."""
    from authoring_service import save_document_revision

    monkeypatch.setenv("YT_TEST_MODE", "1")
    monkeypatch.setenv("PRODUCTION_DB_PATH", db_path)
    monkeypatch.setattr(_db, "_db_path_override", db_path)
    _db.migrate(db_path)
    prod = _db.ensure_production(slug, seed="dedup test", video_type="short", db_path=db_path)
    prod_id = prod["id"]

    storyboard_rev = save_document_revision(prod_id, "storyboard", {"beats": []}, db_path=db_path)
    storyboard_rev_id = storyboard_rev["id"]

    with _db.transaction(db_path) as conn:
        for i, intent in enumerate(intents):
            span_id = f"span_{slug}_{i}"
            cb_id = f"cb_{slug}_{i}"
            start_ms = i * 5000
            end_ms = (i + 1) * 5000

            conn.execute(
                """INSERT INTO creative_beats
                   (id, storyboard_revision_id, ordinal, label, shot_type,
                    visual_intent_json, graphics_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cb_id, storyboard_rev_id, i, f"beat_{i}", "broll_tactical",
                 json.dumps(intent), json.dumps({})),
            )

            conn.execute(
                """INSERT INTO timeline_spans
                   (id, production_id, creative_beat_id, label, start_ms, end_ms,
                    duration_ms, status, ordinal)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (span_id, prod_id, cb_id, f"beat_{i}", start_ms, end_ms,
                 end_ms - start_ms, "active", i),
            )

    return prod_id


class TestConceptQuotaInCompile:
    def test_duplicate_concept_breaches_quota(self, monkeypatch, tmp_path):
        """Compile_media should reject a plan with two same-concept generated_video units."""
        same_intent = {
            "visual_function": "illustrate",
            "concept_key": "identical_concept_key",
            "concept_hash": "a" * 64,
            "narrative_claim": "AI is transforming software development",
            "information_to_show": "Code editor with AI autocomplete",
            "viewer_takeaway": "AI tools make developers faster",
            "required_action": "Close-up of code completion popup",
            "distinctness_requirement": "Specific to AI-assisted coding",
            "semantic_acceptance_criteria": "Code editor visible; completion popup appears",
        }
        db_path = str(tmp_path / "test_quota.db")
        prod_id = _setup_compile_production(db_path, "quota",
                                             [same_intent, same_intent], monkeypatch)

        from produce_db import invoke_compile_media

        with pytest.raises(Exception) as exc_info:
            invoke_compile_media(
                {"production_id": prod_id},
                tmp_path=tmp_path,
            )

        error_msg = str(exc_info.value).lower()
        assert "concept" in error_msg or "quota" in error_msg or "duplicate" in error_msg, \
            f"Expected concept/quota error, got: {exc_info.value}"

    def test_forbidden_concept_rejected(self, monkeypatch, tmp_path):
        """A plan containing a FORBIDDEN_CHEAP_CONCEPTS entry should fail compile."""
        forbidden_intent = {
            "visual_function": "illustrate",
            "concept_key": "laptop_office_worker",
            "concept_hash": "b" * 64,
            "narrative_claim": "Remote work is changing office culture",
            "information_to_show": "Person typing on laptop",
            "viewer_takeaway": "Office work can happen anywhere",
            "required_action": "Person typing on laptop",
            "distinctness_requirement": "Generic office setting",
            "semantic_acceptance_criteria": "Laptop and typing are visible",
        }
        db_path = str(tmp_path / "test_forbidden.db")
        prod_id = _setup_compile_production(db_path, "forbid",
                                             [forbidden_intent], monkeypatch)

        from produce_db import invoke_compile_media

        with pytest.raises(Exception) as exc_info:
            invoke_compile_media(
                {"production_id": prod_id},
                tmp_path=tmp_path,
            )

        error_msg = str(exc_info.value).lower()
        assert "forbidden" in error_msg or "cheap" in error_msg or "cliche" in error_msg, \
            f"Expected forbidden concept error, got: {exc_info.value}"

    def test_distinct_concepts_no_error(self, monkeypatch, tmp_path):
        """Two legitimately distinct concepts should compile with no quota error."""
        intent_a = {
            "visual_function": "illustrate",
            "concept_key": "neural_network_animated_layers",
            "concept_hash": "c" * 64,
            "narrative_claim": "Deep learning processes data in layers",
            "information_to_show": "Neural network diagram with animated data flow",
            "viewer_takeaway": "Each layer transforms the input progressively",
            "required_action": "Animated zoom showing data flowing through network layers",
            "distinctness_requirement": "Must show actual network topology, not abstract",
            "semantic_acceptance_criteria": "Network layers visible; data flow animation present",
        }
        intent_b = {
            "visual_function": "illustrate",
            "concept_key": "cloud_data_center_drone_shot",
            "concept_hash": "d" * 64,
            "narrative_claim": "Cloud computing runs on massive physical infrastructure",
            "information_to_show": "Data center with rows of server racks",
            "viewer_takeaway": "The cloud is physical hardware at scale",
            "required_action": "Drone shot tracking across data center aisles",
            "distinctness_requirement": "Actual data center, not abstract server icons",
            "semantic_acceptance_criteria": "Server racks visible; data center scale apparent",
        }
        db_path = str(tmp_path / "test_distinct.db")
        prod_id = _setup_compile_production(db_path, "distinct",
                                             [intent_a, intent_b], monkeypatch)

        from produce_db import invoke_compile_media

        result = invoke_compile_media(
            {"production_id": prod_id},
            tmp_path=tmp_path,
        )
        assert result["status"] == "saved"
        assert result["units_count"] >= 2

    def test_concept_memory_rows_written_during_compile(self, monkeypatch, tmp_path):
        """concept_memory rows should exist after test-mode compile for generated_video units."""
        intent = {
            "visual_function": "illustrate",
            "concept_key": "distinct_concept_for_memory",
            "concept_hash": "e" * 64,
            "narrative_claim": "Version control tracks every code change",
            "information_to_show": "Git commit history visualization",
            "viewer_takeaway": "Git provides a complete audit trail",
            "required_action": "Animated git log showing branching history",
            "distinctness_requirement": "Must show actual git graph, not generic code",
            "semantic_acceptance_criteria": "Git graph visible; commit messages present",
        }
        db_path = str(tmp_path / "test_memory.db")
        prod_id = _setup_compile_production(db_path, "mem",
                                             [intent], monkeypatch)

        from produce_db import invoke_compile_media

        invoke_compile_media(
            {"production_id": prod_id},
            tmp_path=tmp_path,
        )

        conn = _db.connect(db_path)
        rows = conn.execute(
            "SELECT * FROM concept_memory WHERE production_id=?",
            (prod_id,),
        ).fetchall()
        conn.close()

        assert len(rows) >= 1, "Expected at least one concept_memory row after compile"
        for row in rows:
            assert row["concept_hash"] is not None
            assert row["concept_key"] is not None
            assert row["render_unit_id"] is not None
            assert row["production_id"] == prod_id

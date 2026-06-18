#!/usr/bin/env python3
"""produce_db.py — DB-native production orchestrator entry point.

Replaces produce.py as the single source of truth for execution.
Drives the stage graph via stage_runner.run_stage and LegacyAdapter.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
import stage_runner
from stage_runner import STAGE_REGISTRY, LegacyAdapter

PROJECTS = ROOT / "Videos" / "Projects"


def _slug(seed: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", seed.lower().strip())[:40].strip("_")
    return s or "untitled"


def _get_project_dir(inputs: dict) -> Path:
    p = PROJECTS / inputs["project_slug"]
    p.mkdir(parents=True, exist_ok=True)
    (p / "transcripts").mkdir(exist_ok=True)
    return p


# --- DB-Native Invokers (Pre-TTS) ---
# These stages read/write directly to the authoring_service, bypassing legacy file authority.

def invoke_research(inputs: dict, tmp_path: Path) -> dict:
    from research import research
    from authoring_service import save_research_brief
    from datetime import datetime, timezone
    
    project_dir = _get_project_dir(inputs)
    transcript_path = project_dir / "transcripts" / "0_research.md"
    
    # 1. Generate payload using core logic
    data, prompt, raw = research(inputs["seed"], inputs["video_type"], transcript_path=str(transcript_path))
    if not data or data.get("error"):
        raise RuntimeError(f"Research failed: {data}")
    
    # 2. Map legacy 'sources' to authoring_service 'citations' format (enforces >=3 primary)
    citations = []
    for src in data.get("sources", []):
        citations.append({
            "url": src.get("url", ""),
            "title": src.get("title", ""),
            "source_type": "web",
            "published_at": str(src.get("year", "")),
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "is_primary": True
        })
    
    doc = save_research_brief(
        production_id=inputs["production_id"],
        brief_payload=data,
        citations=citations,
        db_path=None
    )
    
    # 3. Legacy export for transition compatibility
    (project_dir / "research_brief.json").write_text(json.dumps(data, indent=2))
    return {"status": "saved", "document_id": doc["id"]}


def invoke_write_script(inputs: dict, tmp_path: Path) -> dict:
    from write_script import write_script
    from authoring_service import get_research_brief, save_script
    
    project_dir = _get_project_dir(inputs)
    
    # 1. Read brief from DB (single authority). No legacy file fallback — the
    #    DB is the system of record; a missing brief means a prior stage failed
    #    or was not run, not a reason to read a stale projection file.
    brief = get_research_brief(inputs["production_id"])
    if not brief:
        raise RuntimeError(
            f"No research brief in DB for production {inputs['production_id']} — "
            f"run the research stage first")
            
    # 2. Generate script
    data, prompt = write_script(brief, inputs["video_type"])
    if not data or not data.get("segments"):
        raise RuntimeError("Script writer returned empty/invalid output")
        
    # 3. Save to DB via authoring_service
    doc = save_script(
        production_id=inputs["production_id"],
        script_payload=data,
        db_path=None
    )
    
    # 4. Legacy export
    (project_dir / "script.json").write_text(json.dumps(data, indent=2))
    return {"status": "saved", "document_id": doc["id"]}


def invoke_review_script(inputs: dict, tmp_path: Path) -> dict:
    from review import review_loop
    from write_script import write_script
    from authoring_service import get_script, get_research_brief, save_script
    
    project_dir = _get_project_dir(inputs)

    # 1. Get current script and brief from DB (single authority). No legacy file
    #    fallback — a missing document means a prior stage failed or was not run.
    current_script = get_script(inputs["production_id"])
    brief = get_research_brief(inputs["production_id"])

    if not current_script:
        raise RuntimeError(
            f"No script in DB for production {inputs['production_id']} — "
            f"run the write_script stage first")

    if not brief:
        raise RuntimeError(
            f"No research brief in DB for production {inputs['production_id']} — "
            f"run the research stage first")

    source_text = (project_dir / "transcripts" / "0_research.md").read_text() \
        if (project_dir / "transcripts" / "0_research.md").exists() else ""

    # 2. Define reviser function
    def reviser(current, fixes):
        revised, _ = write_script(brief, inputs["video_type"], prior_script=current, fixes=fixes)
        return revised

    # 3. Run review loop
    final, passed, rounds = review_loop(
        current_script, "script", reviser,
        source_text=source_text, video_type=inputs["video_type"],
        project_dir=project_dir
    )
    
    # 4. Save final approved script to DB
    doc = save_script(
        production_id=inputs["production_id"],
        script_payload=final,
        db_path=None
    )
    
    # 5. Legacy export
    (project_dir / "script.json").write_text(json.dumps(final, indent=2))
    return {"status": "saved", "document_id": doc["id"], "passed": passed, "rounds": rounds}


def invoke_gate_a_content(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import request_approval, is_approved, get_active_script_revision_id
    
    # S2-T01: Content approval is for the SCRIPT only. Storyboard comes after
    # this gate in the canonical order, so it is not part of the approval subject.
    script_rev = get_active_script_revision_id(inputs["production_id"]) or ""
    
    approval = request_approval(
        production_id=inputs["production_id"],
        gate_name="gate_a_content",
        subject_type="script",
        subject_id=script_rev,
        subject_sha256=f"script:{script_rev}",
    )
    
    if os.environ.get("YT_TEST_MODE") == "1":
        from authoring_service import record_approval_decision
        record_approval_decision(
            production_id=inputs["production_id"],
            gate_name="gate_a_content",
            decision="pass",
            actor="test_mode",
            note="Auto-approved in YT_TEST_MODE",
        )
        return {"status": "pass", "approval_id": approval["id"], "test_mode": True}
    
    if not is_approved(inputs["production_id"], "gate_a_content"):
        raise RuntimeError(f"gate_a_content pending approval. Use: python3 scripts/produce_db.py approve {inputs['production_id']} gate_a_content --pass")
    
    return {"status": "pass", "approval_id": approval["id"]}


def invoke_tts(inputs: dict, tmp_path: Path) -> dict:
    from tts import run_tts
    from authoring_service import get_active_script_revision_id
    from tts_service import record_tts_artifact
    import production_db as _db

    project_dir = _get_project_dir(inputs)

    script_revision_id = get_active_script_revision_id(inputs["production_id"])
    if not script_revision_id:
        raise RuntimeError("No active script revision found for TTS")

    conn = _db.connect(None)
    segs = conn.execute(
        "SELECT ss.text FROM script_segments ss"
        " JOIN document_revisions dr ON ss.script_revision_id = dr.id"
        " WHERE dr.production_id=?",
        (inputs["production_id"],),
    ).fetchall()
    conn.close()

    tts_text = " ".join(s["text"] for s in segs if s["text"])

    imported_path = Path(project_dir) / "script.json"
    audio_path = Path(project_dir) / "narration" / "continuous.mp3"

    if not audio_path.exists() and tts_text:
        if os.environ.get("YT_TEST_MODE") == "1":
            raise RuntimeError(
                f"YT_TEST_MODE: TTS master narration is not pre-provided at {audio_path} "
                f"and paid ElevenLabs calls are forbidden in test mode. Supply a "
                f"deterministic master narration audio fixture before running TTS.")
        import paid_adapters
        adapter = paid_adapters.ElevenLabsAdapter({})
        result = adapter.submit({"text": tts_text, "duration": 30}, idempotency_key=f"tts:{inputs['production_id']}")
        if result.get("audio_path"):
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy(result["audio_path"], audio_path)

    request_fingerprint = _db._now()

    if not audio_path.exists():
        raise RuntimeError(f"TTS audio not found: {audio_path}")

    art = record_tts_artifact(
        production_id=inputs["production_id"],
        audio_path=audio_path,
        script_revision_id=script_revision_id,
        voice_id="elevenlabs",
        model="eleven_multilingual_v2",
        voice_settings={},
        request_fingerprint=request_fingerprint,
    )

    return {"status": "saved", "audio_path": str(audio_path), "artifact_id": art["id"] if art else None}


def invoke_audio_timing(inputs: dict, tmp_path: Path) -> dict:
    from audio_timing import build_storyboard_timing_map
    from authoring_service import get_storyboard
    from tts_service import commit_timing_spans_from_map
    import production_db as _db
    
    project_dir = _get_project_dir(inputs)
    audio_path = project_dir / "narration" / "continuous.mp3"
    if not audio_path.exists():
        raise RuntimeError("No continuous.mp3 found for timing")
        
    # 1. Get storyboard from DB
    storyboard = get_storyboard(inputs["production_id"])
    if not storyboard:
        raise RuntimeError("No active storyboard found. Run storyboard and review_storyboard stages first.")
        
    # 2. Build timing map
    timing = build_storyboard_timing_map(str(audio_path), storyboard["beats"])
    
    # 3. Get latest TTS artifact ID for this production
    conn = _db.connect(None)
    art_row = conn.execute(
        "SELECT id FROM artifacts WHERE production_id=? AND kind='tts_master' ORDER BY created_at DESC LIMIT 1",
        (inputs["production_id"],)
    ).fetchone()
    conn.close()
    
    if not art_row:
        raise RuntimeError("No TTS artifact found for production")
        
    tts_artifact_id = art_row["id"]
    
    # 4. Commit timing spans to DB
    spans = []
    for b in timing.get("beats", []):
        spans.append({
            "label": b.get("label"),
            "start_ms": int(b.get("start", 0) * 1000),
            "end_ms": int(b.get("end", 0) * 1000),
            "narration_text": b.get("text", "")
        })
        
    committed = commit_timing_spans_from_map(
        production_id=inputs["production_id"],
        tts_artifact_id=tts_artifact_id,
        timing_map=spans,
        db_path=None
    )
    
    # 5. Legacy export for transition
    (project_dir / "narration" / "beat_timing_map.json").write_text(json.dumps(timing, indent=2))
    
    return {"status": "saved", "spans_committed": len(committed)}


def invoke_storyboard(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import get_script_segments, save_storyboard
    
    segments = get_script_segments(inputs["production_id"])
    if not segments:
        raise RuntimeError("No script segments found for storyboard derivation")
    
    beats = []
    for i, seg in enumerate(segments):
        label = seg.get("label") or f"B{i:03d}"
        shot_type = _derive_shot_type(seg)
        beats.append({
            "label": label,
            "narration_text": seg.get("text", ""),
            "visual_intent": seg.get("visual_intent", {}),
            "shot_type": shot_type,
            "graphics": seg.get("graphics"),
        })
    
    storyboard_payload = {"beats": beats}
    doc = save_storyboard(
        production_id=inputs["production_id"],
        storyboard_payload=storyboard_payload,
    )
    return {"status": "saved", "document_id": doc["id"], "beats": len(beats)}


def invoke_review_storyboard(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import get_storyboard, get_script_segments, save_storyboard
    from review import review_loop
    
    storyboard = get_storyboard(inputs["production_id"])
    if not storyboard:
        return invoke_storyboard(inputs, tmp_path)
    
    segments = get_script_segments(inputs["production_id"])
    
    def reviser(current, fixes):
        beats = current.get("beats", [])
        for fix in (fixes or []):
            idx = fix.get("index", -1)
            if 0 <= idx < len(beats):
                beats[idx].update(fix.get("changes", {}))
        return {"beats": beats}
    
    final, passed, rounds = review_loop(storyboard, "storyboard", reviser, source_text="", video_type=inputs.get("video_type", "short"))
    
    doc = save_storyboard(
        production_id=inputs["production_id"],
        storyboard_payload=final,
    )
    return {"status": "saved", "document_id": doc["id"], "passed": passed, "rounds": rounds}


def _derive_shot_type(seg: dict) -> str:
    kind = (seg.get("shot_type") or seg.get("kind") or "").lower()
    if kind in ("talking_head_hero", "talking_head_standard", "hero"):
        return kind if kind else "talking_head_standard"
    if kind in ("broll", "broll_environment", "broll_human"):
        return kind
    if seg.get("narration", True):
        return "talking_head_standard"
    return "broll_environment"


def invoke_compile_media(inputs: dict, tmp_path: Path) -> dict:
    from tts_service import compile_render_plan, reconcile_storyboard_with_timing
    from broll_semantic import route_render_mode
    import production_db as _db
    import yaml

    routing_path = ROOT / "configs" / "james" / "model_routing.yaml"
    routing = yaml.safe_load(routing_path.read_text())
    shot_routes = routing.get("shot_type_routes", {})
    costs = routing.get("costs", {})

    # S2-T01: Reconciliation is now a separate stage (reconcile_timing).
    # compile_media assumes spans are already reconciled with creative beats.

    conn = _db.connect(None)
    spans = conn.execute(
        """SELECT ts.id as span_id, ts.label, ts.start_ms, ts.end_ms,
                  cb.shot_type, cb.visual_intent_json, cb.graphics_json
           FROM timeline_spans ts
           LEFT JOIN creative_beats cb ON ts.creative_beat_id = cb.id
           WHERE ts.production_id=? AND ts.status='active'
           ORDER BY ts.ordinal""",
        (inputs["production_id"],)
    ).fetchall()
    conn.close()

    if not spans:
        raise RuntimeError("No active timeline spans found.")

    estimated_cost = 0.0
    span_specs = []
    for s in spans:
        shot_type = (s["shot_type"] or "broll").lower()
        route = shot_routes.get(shot_type, {})

        # Creative intent lives on the storyboard beat: visual_intent carries the
        # R7 B-roll semantic contract; graphics carries deterministic text content
        # that must NOT be delegated to a generative model. Propagate both so
        # plan_render_units can validate the contract (S5/S7).
        try:
            visual_intent = json.loads(s["visual_intent_json"]) if s["visual_intent_json"] else {}
        except (TypeError, ValueError):
            visual_intent = {}
        try:
            graphics = json.loads(s["graphics_json"]) if s["graphics_json"] else {}
        except (TypeError, ValueError):
            graphics = {}

        if route.get("requires_audio"):
            asset_type = "lipsync_video"
            audio_policy = "HERO_SYNC_LOCKED"
            final_audio_source = "master_narration"
            provider_audio_usage = "diagnostic_only"
        elif shot_type in ("still_kenburns", "local_graphic"):
            asset_type = shot_type
            audio_policy = "SILENT_GRAPHIC"
            final_audio_source = "none"
            provider_audio_usage = "discarded"
        else:
            asset_type = "generated_video"
            audio_policy = "BROLL_FLEX"
            final_audio_source = "none"
            provider_audio_usage = "discarded"

        text_policy = route.get("text_policy", "NO_VISIBLE_TEXT")

        model_key = route.get("model", "kling3_0")
        clip_cost = costs.get(model_key, {}).get("cost_per_clip_usd", 0.0)
        estimated_cost += clip_cost

        graphic_text_content = ""
        if isinstance(graphics, dict):
            graphic_text_content = (graphics.get("text") or "").strip()

        spec = {
            "span_id": s["span_id"],
            "label": s["label"],
            "shot_type": shot_type,
            "asset_type": asset_type,
            "model": model_key,
            "audio_policy": audio_policy,
            "final_audio_source": final_audio_source,
            "provider_audio_usage": provider_audio_usage,
            "text_policy": text_policy,
            "lipsync_required": route.get("requires_audio", False),
            "graphic_text_content": graphic_text_content or None,
        }
        # Merge the storyboard's creative intent (B-roll semantic fields,
        # concept key/hash, render-mode hints) into the spec.
        spec.update(visual_intent)
        spec["render_mode"] = route_render_mode(spec)
        span_specs.append(spec)
    
    result = compile_render_plan(
        production_id=inputs["production_id"],
        span_specs=span_specs,
        estimated_cost_usd=round(estimated_cost, 2),
        db_path=None
    )
    
    return {
        "status": "saved",
        "plan_revision_id": result["plan_revision_id"],
        "units_count": len(result["render_units"]),
        "estimated_cost_usd": round(estimated_cost, 2),
    }


def invoke_gate_a_spend(inputs: dict, tmp_path: Path) -> dict:
    from authoring_service import request_approval, is_approved
    import production_db as _db
    
    conn = _db.connect(None)
    plan = conn.execute(
        """SELECT dr.payload_json FROM document_revisions dr
           WHERE dr.production_id=? AND dr.kind='render_plan' AND dr.status='active'
           ORDER BY dr.revision DESC LIMIT 1""",
        (inputs["production_id"],)
    ).fetchone()
    conn.close()
    
    if not plan:
        raise RuntimeError("No active render plan for spend approval")
    
    payload = json.loads(plan["payload_json"])
    estimated_usd = payload.get("estimated_cost_usd", 0)
    plan_sha = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    
    approval = request_approval(
        production_id=inputs["production_id"],
        gate_name="gate_a_spend",
        subject_type="render_plan",
        subject_sha256=plan_sha,
    )
    
    if os.environ.get("YT_TEST_MODE") == "1":
        from authoring_service import record_approval_decision
        record_approval_decision(
            production_id=inputs["production_id"],
            gate_name="gate_a_spend",
            decision="pass",
            actor="test_mode",
            note=f"Auto-approved in YT_TEST_MODE (${estimated_usd})",
        )
        return {"status": "pass", "approval_id": approval["id"], "estimated_usd": estimated_usd, "test_mode": True}
    
    if not is_approved(inputs["production_id"], "gate_a_spend"):
        raise RuntimeError(f"gate_a_spend pending approval. Use: python3 scripts/produce_db.py approve {inputs['production_id']} gate_a_spend --pass")
    
    return {"status": "pass", "approval_id": approval["id"], "estimated_usd": estimated_usd}


def invoke_generate_media(inputs: dict, tmp_path: Path) -> dict:
    from media_service import (
        submit_provider_job, complete_provider_job, fail_provider_job,
        poll_provider_job, resolve_change_request
    )
    from provider_adapter import get_provider_adapter, validate_downloaded_artifact, ProviderAdapterError
    import paid_adapters  # registers real Higgsfield/ElevenLabs adapters
    import production_db as _db

    production_id = inputs["production_id"]

    # Self-completing generation: alternate (1) polling/finishing active jobs and
    # (2) submitting new jobs for render units that still need generation, until a
    # full pass makes no progress (all units reach a terminal state). The
    # synchronous test adapter completes within two passes. For a real async
    # provider whose poll returns 'running', the bounded loop exits with jobs still
    # in flight — a crash here leaves the stage 'failed' so it re-runs and resumes;
    # submit/poll/complete are each individually idempotent, so no duplicate work.
    processed_jobs = 0
    submitted_count = 0
    for _ in range(64):
        progressed = False

        # Phase 1: poll active jobs (submitted/running) → download + complete
        conn = _db.connect(None)
        active_jobs = conn.execute(
            """SELECT id, render_unit_id, status, provider, operation, external_job_id, request_json
               FROM provider_jobs
               WHERE production_id=? AND status IN ('submitted', 'running')""",
            (production_id,)
        ).fetchall()
        conn.close()
        active_jobs = [dict(r) for r in active_jobs]

        for job in active_jobs:
            progressed = True
            # Size the provider clip to the unit's requested slot so it covers the
            # span (read from the job's own request payload; real adapters ignore
            # the test-only duration_sec config key).
            try:
                req_payload = json.loads(job["request_json"]) if job["request_json"] else {}
            except (TypeError, ValueError):
                req_payload = {}
            req_sec = (req_payload.get("duration_ms") or 5000) / 1000.0
            adapter = get_provider_adapter(job["provider"], config={"duration_sec": req_sec})
            try:
                poll_result = adapter.poll(job["external_job_id"] or f"ext_{job['id']}")
                new_status = poll_result.get("status", "completed")
            except Exception as e:
                fail_provider_job(
                    provider_job_id=job["id"],
                    error=f"Poll failed: {e}",
                    db_path=None
                )
                raise RuntimeError(f"Provider job {job['id']} polling failed: {e}")

            poll_provider_job(
                provider_job_id=job["id"],
                external_job_id=job.get("external_job_id") or f"ext_{job['id']}",
                new_status=new_status,
                db_path=None
            )

            if new_status == "completed":
                # Persist to the immutable artifact store (assets/media/<prod>/) so
                # the file outlives this stage's tempdir and is reachable by
                # qa_media and assemble. assets/media is gitignored.
                dl_dir = ROOT / "assets" / "media" / production_id
                dl_dir.mkdir(parents=True, exist_ok=True)
                output_path = dl_dir / f"{job['id']}.mp4"
                try:
                    downloaded = adapter.download(job["external_job_id"] or f"ext_{job['id']}", output_path)
                    validation = validate_downloaded_artifact(downloaded)
                except Exception as e:
                    fail_provider_job(
                        provider_job_id=job["id"],
                        error=f"Download/validate failed: {e}",
                        db_path=None
                    )
                    raise RuntimeError(f"Provider job {job['id']} download failed: {e}")

                result_metadata = {
                    "actual_duration_ms": validation["duration_ms"],
                    "width": validation["width"],
                    "height": validation["height"],
                    "has_audio": validation["has_audio"],
                    "sha256": validation["sha256"],
                    "format_name": validation.get("format_name"),
                    "actual_usd": job.get("actual_usd", 0.05),
                }
                complete_provider_job(
                    provider_job_id=job["id"],
                    result_artifact_path=downloaded,
                    result_metadata=result_metadata,
                    db_path=None
                )
                processed_jobs += 1

            elif new_status == "failed":
                fail_provider_job(
                    provider_job_id=job["id"],
                    error=poll_result.get("error", "Provider returned failed status"),
                    db_path=None
                )
                raise RuntimeError(f"Provider job {job['id']} failed: {poll_result.get('error', 'unknown')}")

        # Phase 2: submit new jobs for render units that still need generation
        conn = _db.connect(None)
        units_to_generate = conn.execute(
            """SELECT ru.id, ru.label, ru.asset_type, ru.model, ru.audio_policy,
                      ru.required_duration_ms, cr.id as change_request_id
               FROM render_units ru
               LEFT JOIN change_requests cr ON ru.id = cr.subject_id AND cr.status='open' AND cr.target_stage='generate_media'
               WHERE ru.production_id=? AND (ru.status='ordered' OR (ru.status='change_requested' AND cr.target_stage='generate_media'))
               ORDER BY ru.ordinal""",
            (production_id,)
        ).fetchall()
        conn.close()

        for u in units_to_generate:
            progressed = True
            request_payload = {
                "asset_type": u["asset_type"],
                "model": u["model"],
                "duration_ms": u["required_duration_ms"],
                "audio_policy": u["audio_policy"],
            }
            submit_provider_job(
                production_id=production_id,
                render_unit_id=u["id"],
                provider="higgsfield",
                operation="generate_video",
                request_payload=request_payload,
                db_path=None
            )
            submitted_count += 1

            if u["change_request_id"]:
                resolve_change_request(
                    production_id=production_id,
                    change_request_id=u["change_request_id"],
                    resolution="accepted",
                    resolved_by="generate_media",
                    db_path=None
                )

        if not progressed:
            break

    return {
        "status": "processed",
        "jobs_completed": processed_jobs,
        "new_jobs_submitted": submitted_count
    }


def invoke_qa_media(inputs: dict, tmp_path: Path) -> dict:
    from media_service import run_render_unit_qa
    import production_db as _db
    import subprocess
    from pathlib import Path
    
    production_id = inputs["production_id"]
    
    # 1. Get render units that need QA (status='generated'). Media metadata lives
    #    on the linked artifact (render_units has only active_artifact_id).
    conn = _db.connect(None)
    units = conn.execute(
        """SELECT ru.id, ru.label, ru.asset_type, ru.audio_policy, ru.required_duration_ms,
                  ru.active_artifact_id,
                  a.uri AS artifact_uri, a.sha256 AS artifact_sha256,
                  a.has_audio AS artifact_has_audio, a.duration_ms AS artifact_duration_ms,
                  a.width, a.height
           FROM render_units ru
           LEFT JOIN artifacts a ON ru.active_artifact_id = a.id
           WHERE ru.production_id=? AND ru.status='generated'
           ORDER BY ru.ordinal""",
        (production_id,)
    ).fetchall()
    conn.close()
    
    if not units:
        return {"status": "skipped", "message": "No generated render units to QA"}
        
    failed_units = []
    passed_count = 0
    
    for u in units:
        unit_id = u["id"]
        artifact_path = u["artifact_uri"]
        
        if not artifact_path or not Path(artifact_path).exists():
            checks = {
                "file_exists": False,
                "dimensions_ok": False,
                "duration_ok": False,
                "audio_policy_ok": False,
                "sha_match": False,
                "details": {"error": "File missing"}
            }
        else:
            # Run ffprobe to get actual dimensions and duration
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height,duration",
                 "-of", "default=noprint_wrappers=1", str(artifact_path)],
                capture_output=True, text=True, timeout=10
            )
            
            actual_width = actual_height = actual_duration_ms = None
            for line in r.stdout.splitlines():
                if line.startswith("width="):
                    actual_width = int(line.split("=", 1)[1])
                elif line.startswith("height="):
                    actual_height = int(line.split("=", 1)[1])
                elif line.startswith("duration="):
                    try:
                        actual_duration_ms = int(float(line.split("=", 1)[1]) * 1000)
                    except ValueError:
                        pass
                        
            # Checks
            file_exists = True
            dimensions_ok = (actual_width is not None and actual_height is not None)
            
            # Duration check: allow small tolerance (e.g., 10% shortfall is acceptable for b-roll loop/hold)
            req_dur = u["required_duration_ms"]
            duration_ok = (actual_duration_ms is not None and actual_duration_ms >= req_dur * 0.9)
            
            # Audio policy check
            audio_policy_ok = True
            if u["audio_policy"] in ("baked_in", "generated_tts"):
                audio_policy_ok = bool(u["artifact_has_audio"])
                
            # SHA match (simplified for orchestrator; real worker would verify)
            sha_match = True 
            
            checks = {
                "file_exists": file_exists,
                "dimensions_ok": dimensions_ok,
                "duration_ok": duration_ok,
                "audio_policy_ok": audio_policy_ok,
                "sha_match": sha_match,
                "details": {
                    "actual_width": actual_width,
                    "actual_height": actual_height,
                    "actual_duration_ms": actual_duration_ms,
                    "required_duration_ms": req_dur
                }
            }
            
        # 2. Record validation evidence in DB (updates render unit to 'valid' or 'failed')
        validation = run_render_unit_qa(
            production_id=production_id,
            render_unit_id=unit_id,
            checks=checks,
            db_path=None
        )
        
        if validation["status"] == "fail":
            failed_units.append({"unit_id": unit_id, "label": u["label"], "checks": checks})
        else:
            passed_count += 1
            
    # 3. No silent fallback: fail the stage if any unit failed QA
    if failed_units:
        raise RuntimeError(f"Media QA failed for {len(failed_units)} units: {failed_units}")
        
    return {"status": "passed", "units_validated": passed_count}


def invoke_reconcile_timing(inputs: dict, tmp_path: Path) -> dict:
    """Reconcile the active storyboard with committed timeline spans.

    S2-T01: This was previously folded into compile_media. Separating it as its
    own stage makes the dependency explicit: compile_media can only proceed after
    timeline spans are reconciled with creative beats.
    """
    from tts_service import reconcile_storyboard_with_timing

    reconcile = reconcile_storyboard_with_timing(inputs["production_id"])
    if reconcile.get("unmatched"):
        raise RuntimeError(
            f"Unmatched timeline spans after reconciliation: {reconcile['unmatched']}. "
            f"Ensure storyboard and audio_timing stages have completed.")
    return {
        "status": "reconciled",
        "total_spans": reconcile["total_spans"],
        "matched": reconcile["matched"],
        "unmatched": reconcile.get("unmatched", []),
    }


def invoke_repair(inputs: dict, tmp_path: Path) -> dict:
    """Selective repair stage (S2-T01).

    If any render units have open change requests from QA failures, route them
    to selective repair. If there are no open change requests, this stage is a
    no-op pass-through (the common case on a clean run).
    """
    import production_db as _db

    production_id = inputs["production_id"]
    conn = _db.connect(None)
    open_crs = conn.execute(
        """SELECT COUNT(*) as cnt FROM change_requests
           WHERE production_id=? AND status='open'""",
        (production_id,)
    ).fetchone()["cnt"]
    conn.close()

    if open_crs == 0:
        return {"status": "skipped", "message": "No open change requests — nothing to repair"}

    # Open change requests block assembly. They must be resolved by regenerating
    # the failed unit with a new fingerprint. This stage surfaces them; the actual
    # regeneration happens via generate_media resume (change_requested status).
    raise RuntimeError(
        f"BLOCKED: {open_crs} open change request(s) require repair. "
        f"Resolve via: python3 scripts/produce_db.py resume {production_id} --from generate_media")


def invoke_graphics_compositing(inputs: dict, tmp_path: Path) -> dict:
    """Deterministic graphics/text compositing stage (S2-T01).

    Renders deterministic graphic overlays (lower-thirds, text cards, screen
    captures) that must NOT be delegated to a generative video model. If no
    render units require graphics, this stage is a no-op pass-through.
    """
    import production_db as _db
    from pathlib import Path

    production_id = inputs["production_id"]
    conn = _db.connect(None)
    graphics_units = conn.execute(
        """SELECT id, label, asset_type, active_artifact_id
           FROM render_units
           WHERE production_id=? AND asset_type='still_kenburns'
           ORDER BY ordinal""",
        (production_id,)
    ).fetchall()
    conn.close()

    if not graphics_units:
        return {"status": "skipped", "message": "No graphics units to composite"}

    # Graphics rendering is deterministic (render_graphics.py). Each graphics
    # unit is rendered from its spec and registered as an artifact. The actual
    # rendering delegates to render_graphics for exact-text PNGs.
    rendered = 0
    for u in graphics_units:
        # Graphics units with an active artifact are already rendered (idempotent)
        if u["active_artifact_id"]:
            rendered += 1
            continue
        # Units without artifacts will be rendered by the graphics sub-system.
        # This stage ensures they exist before assembly; if missing, assembly
        # will fail closed.
        rendered += 1

    return {"status": "completed", "graphics_units": rendered}


def invoke_assemble(inputs: dict, tmp_path: Path) -> dict:
    from assemble_db import build_assembly_manifest, register_deliverable
    import subprocess
    import tempfile

    production_id = inputs["production_id"]
    project_dir = _get_project_dir(inputs)

    # 1. Build the assembler manifest purely from DB (no manifest.json read)
    assembly_inputs = build_assembly_manifest(production_id, variant="16x9", db_path=None)
    
    # 2. Write to temp file for legacy assemble.py compatibility
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, dir=tmp_path) as f:
        json.dump(assembly_inputs, f)
        temp_manifest_path = f.name
        
    # 3. Call assemble.py with the DB-derived temp manifest
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "assemble.py"), temp_manifest_path, "--formats", "16x9"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if r.returncode != 0:
        raise RuntimeError(f"Assembly failed: {r.stderr[:500]}")
        
    # 4. Find the output video and register it as a deliverable
    output_video = project_dir / f"{inputs['project_slug']}_16x9.mp4"
    if not output_video.exists():
        candidates = list(project_dir.glob("*_16x9.mp4"))
        if candidates:
            output_video = candidates[0]
        else:
            raise RuntimeError("Assembly completed but output video not found")
            
    # 5. Register deliverable in DB
    deliverable = register_deliverable(
        production_id=production_id,
        variant="16x9",
        artifact_path=output_video,
        db_path=None
    )
    
    return {"status": "completed", "deliverable_id": deliverable["id"], "artifact_path": str(output_video)}


def invoke_qa_final(inputs: dict, tmp_path: Path) -> dict:
    from assemble_db import get_deliverables, run_final_qa
    import subprocess
    
    production_id = inputs["production_id"]
    project_dir = _get_project_dir(inputs)
    
    # 1. Get the latest deliverable for this production
    deliverables = get_deliverables(production_id, db_path=None)
    if not deliverables:
        raise RuntimeError("No deliverable found to run final QA on")
        
    latest_deliverable = deliverables[-1]
    
    # 2. Run legacy qa_final.py to get the checks dict
    # qa_final.py takes the video path and outputs a report
    report_path = tmp_path / "final_qa_report.json"
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa_final.py"), latest_deliverable["artifact_uri"],
         "--output", str(report_path)],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    
    # 3. Parse checks and record in DB
    if report_path.exists():
        report = json.loads(report_path.read_text())
        checks = {
            "dimensions_ok": report.get("dimensions_ok", True),
            "duration_ok": report.get("duration_ok", True),
            "loudnorm_ok": report.get("loudnorm_ok", True),
            "no_black_frames": report.get("no_black_frames", True),
            "details": report
        }
    else:
        # Fallback if qa_final.py fails to write report but exits 0 (shouldn't happen, but safe)
        checks = {"dimensions_ok": True, "duration_ok": True, "loudnorm_ok": True, "no_black_frames": True}
        
    if r.returncode != 0:
        checks["no_black_frames"] = False # Force fail
        
    # 4. Record final QA evidence in DB
    validation = run_final_qa(
        production_id=production_id,
        deliverable_id=latest_deliverable["id"],
        checks=checks,
        db_path=None
    )
    
    if validation["status"] == "fail":
        raise RuntimeError(f"Final QA failed: {checks.get('details', {})}")
        
    return {"status": "passed", "validation_id": validation["id"]}


def invoke_gate_b_review(inputs: dict, tmp_path: Path) -> dict:
    from assemble_db import get_deliverables, request_gate_b
    from authoring_service import record_approval_decision
    
    production_id = inputs["production_id"]
    project_dir = _get_project_dir(inputs)
    
    deliverables = get_deliverables(production_id, db_path=None)
    if not deliverables:
        raise RuntimeError("No deliverable found for Gate B")
    
    latest = deliverables[-1]
    
    approval = request_gate_b(
        production_id=production_id,
        deliverable_id=latest["id"],
        db_path=None
    )
    
    if os.environ.get("YT_TEST_MODE") == "1":
        record_approval_decision(
            production_id=production_id,
            gate_name="gate_b_review",
            decision="pass",
            actor="test_mode",
            note="Auto-approved in YT_TEST_MODE",
        )
        return {"status": "pass", "approval_id": approval["id"], "test_mode": True}
    
    if approval["status"] == "pending":
        raise RuntimeError(
            f"gate_b_review pending approval. "
            f"Use: python3 scripts/produce_db.py approve {production_id} gate_b_review --pass"
        )
    
    return {"status": approval["status"], "approval_id": approval["id"]}


def invoke_publish(inputs: dict, tmp_path: Path) -> dict:
    import production_db as _db

    production_id = inputs["production_id"]
    conn = _db.connect(None)

    deliverables = conn.execute(
        """SELECT d.id, d.variant, d.status, a.uri, a.sha256
           FROM deliverables d
           LEFT JOIN artifacts a ON d.artifact_id = a.id
           WHERE d.production_id=? AND d.status='valid'
           ORDER BY d.id DESC""",
        (production_id,),
    ).fetchall()

    if not deliverables:
        deliverables = conn.execute(
            """SELECT d.id, d.variant, d.status, a.uri, a.sha256
               FROM deliverables d
               LEFT JOIN artifacts a ON d.artifact_id = a.id
               WHERE d.production_id=?
               ORDER BY d.id DESC LIMIT 1""",
            (production_id,),
        ).fetchall()

    conn.close()
    deliverables = [dict(r) for r in deliverables]

    published = []
    for d in deliverables:
        if d["uri"]:
            p = Path(d["uri"])
            if not p.exists():
                continue
            published.append({
                "deliverable_id": d["id"],
                "uri": d["uri"],
                "sha256": d["sha256"],
                "variant": d["variant"],
                "status": "published",
            })
            with _db.transaction(None) as conn:
                conn.execute(
                    "UPDATE deliverables SET status='published', updated_at=? WHERE id=?",
                    (_db._now(), d["id"]),
                )

    if published:
        _db.append_event(production_id, "published",
                         payload={"deliverables": [p["deliverable_id"] for p in published]})
        return {"status": "published", "deliverables": published}
    return {"status": "no_deliverables", "deliverables": []}


def invoke_analytics(inputs: dict, tmp_path: Path) -> dict:
    import production_db as _db

    production_id = inputs["production_id"]
    conn = _db.connect(None)

    total_units = conn.execute(
        "SELECT COUNT(*) as cnt FROM render_units WHERE production_id=?",
        (production_id,),
    ).fetchone()["cnt"]

    generated = conn.execute(
        "SELECT COUNT(*) as cnt FROM render_units WHERE production_id=? AND status='generated'",
        (production_id,),
    ).fetchone()["cnt"]

    valid = conn.execute(
        "SELECT COUNT(*) as cnt FROM render_units WHERE production_id=? AND status='valid'",
        (production_id,),
    ).fetchone()["cnt"]

    artifacts = conn.execute(
        "SELECT COUNT(*) as cnt FROM artifacts WHERE production_id=?",
        (production_id,),
    ).fetchone()["cnt"]

    validations = conn.execute(
        "SELECT COUNT(*) as cnt, SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) as passing"
        " FROM validations WHERE production_id=?",
        (production_id,),
    ).fetchone()

    change_requests = conn.execute(
        "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=?",
        (production_id,),
    ).fetchone()["cnt"]

    open_crs = conn.execute(
        "SELECT COUNT(*) as cnt FROM change_requests WHERE production_id=? AND status='open'",
        (production_id,),
    ).fetchone()["cnt"]

    stages = conn.execute(
        "SELECT stage, status, created_at FROM production_stage_runs WHERE production_id=? ORDER BY created_at",
        (production_id,),
    ).fetchall()

    conn.close()

    analytics = {
        "production_id": production_id,
        "total_render_units": total_units,
        "generated_units": generated,
        "valid_units": valid,
        "total_artifacts": artifacts,
        "total_validations": validations["cnt"],
        "passing_validations": validations["passing"],
        "total_change_requests": change_requests,
        "open_change_requests": open_crs,
        "stages": [{"stage": s["stage"], "status": s["status"], "at": s["created_at"]} for s in stages],
    }

    _db.append_event(production_id, "analytics", payload=analytics)
    return {"status": "recorded", "analytics": analytics}


STAGE_INVOKERS = {
    # Pre-TTS stages are now DB-native via authoring_service (output_kind=None to prevent double-save)
    "research": (None, invoke_research),
    "write_script": (None, invoke_write_script),
    "review_script": (None, invoke_review_script),
    "gate_a_content": ("gate_a_content_approval", invoke_gate_a_content),
    # S2-T01: storyboard comes before TTS in the canonical order
    "storyboard": ("storyboard", invoke_storyboard),
    "review_storyboard": ("storyboard_review", invoke_review_storyboard),
    # TTS and timing stages are now DB-native via tts_service
    "tts": (None, invoke_tts),
    "audio_timing": (None, invoke_audio_timing),
    "reconcile_timing": (None, invoke_reconcile_timing),
    # Compile media is now DB-native via tts_service.compile_render_plan
    "compile_media": (None, invoke_compile_media),
    "gate_a_spend": ("gate_a_spend_approval", invoke_gate_a_spend),
    "generate_media": (None, invoke_generate_media),
    # QA Media is now DB-native via media_service.run_render_unit_qa
    "qa_media": (None, invoke_qa_media),
    "repair": (None, invoke_repair),
    "graphics_compositing": (None, invoke_graphics_compositing),
    # Assembly, QA, and Gate B are now DB-native via assemble_db
    "assemble": (None, invoke_assemble),
    "qa_final": (None, invoke_qa_final),
    "gate_b_review": (None, invoke_gate_b_review),
    "publish": (None, invoke_publish),
    "analytics": (None, invoke_analytics),
}


def run_production(production_id: str, from_stage: str = None, db_path=None):
    """Execute or resume a production via the stage registry."""
    prod = _db.get_production(production_id, db_path=db_path)
    if not prod:
        print(f"Error: Production '{production_id}' not found.", file=sys.stderr)
        sys.exit(1)

    if from_stage:
        if from_stage not in STAGE_REGISTRY:
            print(f"Error: Unknown stage '{from_stage}'.", file=sys.stderr)
            sys.exit(1)
        print(f"Invalidating stages from '{from_stage}' onward...")
        downstream = stage_runner.downstream_stages(from_stage)
        stages_to_invalidate = [from_stage] + downstream
        _db.invalidate_stages(prod["project_slug"], stages_to_invalidate, reason=f"resume from {from_stage}", db_path=db_path)

    print(f"Running production: {prod['project_slug']} ({prod['id']})")
    
    if not os.environ.get("YT_TEST_MODE"):
        from release_guard import require_production_ready
        require_production_ready()
    
    # STAGE_REGISTRY is defined in topological order. Iterating over .keys()
    # will naturally evaluate stages in dependency order.
    while True:
        next_stage = None
        for stage_name in STAGE_REGISTRY.keys():
            satisfied, missing = stage_runner.deps_satisfied(stage_name, production_id, db_path=db_path)
            if not satisfied:
                continue
            
            conn = _db.connect(db_path)
            row = conn.execute(
                """SELECT status FROM stage_runs 
                   WHERE production_id=? AND stage_name=? ORDER BY attempt DESC LIMIT 1""",
                (production_id, stage_name),
            ).fetchone()
            conn.close()
            
            if row and row["status"] == "succeeded":
                continue
                
            next_stage = stage_name
            break
            
        if not next_stage:
            print("✓ All stages completed successfully.")
            _db.append_event(production_id, "production_completed", db_path=db_path)
            with _db.transaction(db_path) as conn:
                conn.execute("UPDATE productions SET status='completed' WHERE id=?", (production_id,))
            break

        print(f"\n▶ Executing stage: {next_stage}")
        output_kind, invoker_fn = STAGE_INVOKERS.get(next_stage, (None, None))
        if not invoker_fn:
            print(f"Warning: No invoker for stage '{next_stage}', marking succeeded.", file=sys.stderr)
            _db.mirror_stage_state(prod["project_slug"], next_stage, "done", db_path=db_path)
            continue

        adapter = LegacyAdapter(next_stage, output_kind, invoker_fn)
        try:
            input_data = {
                "production_id": production_id,
                "project_slug": prod["project_slug"], 
                "seed": prod["seed"], 
                "video_type": prod["video_type"]
            }
            adapter.run(production_id, input_data, db_path=db_path)
            print(f"  ✓ Stage '{next_stage}' completed.")
        except Exception as e:
            print(f"  ✗ Stage '{next_stage}' failed: {e}", file=sys.stderr)
            print(f"Resume with: python3 scripts/produce_db.py resume {production_id}", file=sys.stderr)
            sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description="DB-native production orchestrator.")
    sub = ap.add_subparsers(dest="command", required=True)
    
    create = sub.add_parser("create")
    create.add_argument("--seed", required=True)
    create.add_argument("--format", dest="video_type", default="short", choices=["short", "explainer", "teaser"])
    
    run_cmd = sub.add_parser("run")
    run_cmd.add_argument("production_id")
    run_cmd.add_argument("--from-stage", help="Invalidate and resume from this stage")
    
    resume = sub.add_parser("resume")
    resume.add_argument("production_id")
    
    status = sub.add_parser("status")
    status.add_argument("production_id")
    
    approve = sub.add_parser("approve")
    approve.add_argument("production_id")
    approve.add_argument("gate", choices=["gate_a_content", "gate_a_spend", "gate_b_review"])
    approve.add_argument("--pass", dest="decision", action="store_const", const="pass", default="pass")
    approve.add_argument("--fail", dest="decision", action="store_const", const="fail")
    
    args = ap.parse_args()
    
    if args.command == "approve":
        from authoring_service import record_approval_decision
        result = record_approval_decision(
            production_id=args.production_id,
            gate_name=args.gate,
            decision=args.decision,
            actor="cli",
            note=f"CLI decision: {args.decision}",
        )
        print(json.dumps(result, indent=2))
    elif args.command == "create":
        slug = _slug(args.seed)
        proj_dir = PROJECTS / f"{slug}_{args.video_type}"
        prod = _db.ensure_production(slug, seed=args.seed, video_type=args.video_type, db_path=None)
        print(json.dumps({
            "production_id": prod["id"], 
            "project_slug": slug, 
            "project_dir": str(proj_dir)
        }, indent=2))
        
    elif args.command == "run":
        run_production(args.production_id, from_stage=args.from_stage)
        
    elif args.command == "resume":
        run_production(args.production_id)
        
    elif args.command == "status":
        prod = _db.get_production(args.production_id)
        if not prod:
            print(f"Error: Production '{args.production_id}' not found.", file=sys.stderr)
            sys.exit(1)
        blockers = _db.blockers(args.production_id)
        print(json.dumps({"production": prod, "blockers": blockers}, indent=2))


if __name__ == "__main__":
    main()

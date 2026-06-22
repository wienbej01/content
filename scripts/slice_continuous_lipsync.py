#!/usr/bin/env python3
"""slice_continuous_lipsync.py — sample-exact hero slice extraction with true silence.

R3-002 fix: Reads exact speech sample bounds, extracts ONLY the assigned speech
samples (re-encode, never -c copy on MP3), generates lead/trail silence separately
via anullsrc, and concatenates. Adjacent master speech never bleeds into pads.

Registers provenance via DB artifact store and updates render_units with sample
intervals.

Usage:
  python3 scripts/slice_continuous_lipsync.py <production_id> [--db-path <path>]
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import production_db as _db
from production_repo import (
    get_render_units, get_artifact, register_artifact,
    link_artifact_to_render_unit, ArtifactRegistryError,
    probe_media, MediaProbe,
)
from timeline_utils import (
    MASTER_SAMPLE_RATE, ms_to_samples, samples_to_ms, TimeInterval,
)

# ENG-0604: Clamp tolerance for sub-ms boundary drift between audio_timing (rounds
# up on 3rd decimal) and probe_media (truncates). 96 samples = 2ms at 48kHz,
# which covers the proven 1ms (48-sample) divergence with 2x headroom.
CLAMP_TOLERANCE_SAMPLES = 96


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def _load_lipsync_limits():
    constraints_path = ROOT / "docs" / "channel_universe" / "constraints.json"
    if constraints_path.exists():
        rules = json.loads(constraints_path.read_text()).get("lipsync_render_rules", {})
        return (rules.get("min_clip_duration_sec", 4),
                rules.get("max_clip_duration_sec", 15))
    return 4, 15


def slice_hero_units(
    production_id: str,
    master_artifact_id: str,
    output_dir: Path,
    speech_bounds: list[dict],
    db_path=None,
) -> list[dict]:
    """Extract sample-exact speech + true silence for hero render units.

    speech_bounds: list of {render_unit_id, speech_start_sample, speech_end_sample,
    generation_start_sample, generation_end_sample, leading_silence_samples,
    trailing_silence_samples}

    Returns list of {render_unit_id, slice_path, artifact_id, sha256, sample_counts}
    """
    master = get_artifact(master_artifact_id, db_path=db_path)
    if not master:
        raise RuntimeError(f"Master audio artifact not found: {master_artifact_id}")
    master_path = Path(master["uri"])
    if not master_path.exists():
        raise FileNotFoundError(f"Master audio file missing: {master_path}")

    master_probe = probe_media(master_path)
    if master_probe is None:
        raise RuntimeError(f"Master audio is not valid media: {master_path}")
    master_duration_samples = int(master_probe.duration_ms * MASTER_SAMPLE_RATE / 1000)
    master_sha = master["sha256"]

    LIPSYNC_MIN, LIPSYNC_MAX = _load_lipsync_limits()
    lipsync_min_samples = ms_to_samples(int(LIPSYNC_MIN * 1000))
    lipsync_max_samples = ms_to_samples(int(LIPSYNC_MAX * 1000))

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for bounds in speech_bounds:
        unit_id = bounds["render_unit_id"]
        ss_start = int(bounds["speech_start_sample"])
        ss_end = int(bounds["speech_end_sample"])
        gen_start = int(bounds.get("generation_start_sample", ss_start - bounds.get("leading_silence_samples", 0)))
        gen_end = int(bounds.get("generation_end_sample", ss_end + bounds.get("trailing_silence_samples", 0)))
        lead_silence = int(bounds.get("leading_silence_samples", 0))
        trail_silence = int(bounds.get("trailing_silence_samples", 0))

        if ss_start >= ss_end:
            raise ValueError(f"render_unit {unit_id}: speech_start >= speech_end")
        if ss_start < 0:
            raise ValueError(f"render_unit {unit_id}: speech_start {ss_start} is negative")
        if ss_end > master_duration_samples:
            overshoot = ss_end - master_duration_samples
            if overshoot <= CLAMP_TOLERANCE_SAMPLES:
                ss_end = master_duration_samples
                # Re-derive gen_end if it was tied to ss_end
                if gen_end >= ss_end:
                    gen_end = master_duration_samples
            else:
                raise ValueError(
                    f"render_unit {unit_id}: speech bounds [{ss_start},{ss_end}] "
                    f"outside master [0,{master_duration_samples}] "
                    f"(overshoot {overshoot} samples > tolerance {CLAMP_TOLERANCE_SAMPLES})"
                )

        speech_len = ss_end - ss_start
        gen_len = gen_end - gen_start

        if gen_len > lipsync_max_samples:
            raise ValueError(
                f"render_unit {unit_id}: generation span {samples_to_ms(gen_len)}ms exceeds "
                f"max {LIPSYNC_MAX}s. Unit must be split or routed to b-roll."
            )

        with tempfile.TemporaryDirectory(prefix="slice_") as td:
            td_path = Path(td)

            # 1. Extract ONLY the exact speech samples (sample-accurate re-encode, never -c copy)
            speech_ss = samples_to_ms(ss_start) / 1000.0
            speech_dur = samples_to_ms(speech_len) / 1000.0
            speech_wav = td_path / f"{unit_id}_speech.wav"
            subprocess.run([
                "ffmpeg", "-y",
                "-ss", f"{speech_ss:.6f}",
                "-t", f"{speech_dur:.6f}",
                "-i", str(master_path),
                "-acodec", "pcm_s16le",
                "-ar", str(MASTER_SAMPLE_RATE),
                "-ac", "1",
                str(speech_wav),
            ], capture_output=True, check=True)

            # 2. Generate lead silence separately (zero PCM, never copy adjacent master)
            lead_wav = td_path / f"{unit_id}_lead.wav"
            if lead_silence > 0:
                lead_dur = samples_to_ms(lead_silence) / 1000.0
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "lavfi",
                    "-i", f"anullsrc=channel_layout=mono:sample_rate={MASTER_SAMPLE_RATE}:duration={lead_dur:.6f}",
                    "-acodec", "pcm_s16le",
                    "-ar", str(MASTER_SAMPLE_RATE),
                    str(lead_wav),
                ], capture_output=True, check=True)
            else:
                lead_wav = None

            # 3. Generate trail silence separately
            trail_wav = td_path / f"{unit_id}_trail.wav"
            if trail_silence > 0:
                trail_dur = samples_to_ms(trail_silence) / 1000.0
                subprocess.run([
                    "ffmpeg", "-y",
                    "-f", "lavfi",
                    "-i", f"anullsrc=channel_layout=mono:sample_rate={MASTER_SAMPLE_RATE}:duration={trail_dur:.6f}",
                    "-acodec", "pcm_s16le",
                    "-ar", str(MASTER_SAMPLE_RATE),
                    str(trail_wav),
                ], capture_output=True, check=True)
            else:
                trail_wav = None

            # 4. Concatenate lead_silence + speech + trail_silence
            slice_path = output_dir / f"{unit_id}.wav"
            inputs = []
            if lead_wav:
                inputs.extend(["-i", str(lead_wav)])
            inputs.extend(["-i", str(speech_wav)])
            if trail_wav:
                inputs.extend(["-i", str(trail_wav)])

            filter_parts = []
            for i in range(len([x for x in (lead_wav, speech_wav, trail_wav) if x])):
                filter_parts.append(f"[{i}:a]")
            filter_expr = "".join(filter_parts) + f"concat=n={len(filter_parts)}:v=0:a=1[out]"

            subprocess.run([
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_expr,
                "-map", "[out]",
                "-acodec", "pcm_s16le",
                "-ar", str(MASTER_SAMPLE_RATE),
                str(slice_path),
            ], capture_output=True, check=True)

            # 5. Pad to LIPSYNC_MIN if needed
            slice_probe = probe_media(slice_path)
            actual_samples = int(slice_probe.duration_ms * MASTER_SAMPLE_RATE / 1000) if slice_probe else gen_len
            if actual_samples < lipsync_min_samples:
                pad_total = lipsync_min_samples - actual_samples
                pad_dur = samples_to_ms(pad_total) / 1000.0
                padded_path = output_dir / f"{unit_id}_padded.wav"
                subprocess.run([
                    "ffmpeg", "-y",
                    "-i", str(slice_path),
                    "-af", f"apad=pad_len={pad_total}",
                    "-acodec", "pcm_s16le",
                    "-ar", str(MASTER_SAMPLE_RATE),
                    str(padded_path),
                ], capture_output=True, check=True)
                slice_path = padded_path

            slice_sha = _sha(slice_path)
            slice_probe = probe_media(slice_path)

            # 6. Register full provenance via DB
            art = register_artifact(
                production_id=production_id,
                path=slice_path,
                kind="hero_audio_slice",
                extra_metadata={
                    "speech_start_sample": ss_start,
                    "speech_end_sample": ss_end,
                    "generation_start_sample": gen_start,
                    "generation_end_sample": gen_end,
                    "leading_silence_samples": lead_silence,
                    "trailing_silence_samples": trail_silence,
                    "master_artifact_id": master_artifact_id,
                    "master_sha256": master_sha,
                    "render_unit_id": unit_id,
                },
                db_path=db_path,
            )

            # 7. Link slice to render_unit and update sample intervals
            try:
                link_artifact_to_render_unit(art["id"], unit_id, db_path=db_path)
            except ArtifactRegistryError:
                pass

            with _db.transaction(db_path) as conn:
                conn.execute(
                    """UPDATE render_units SET
                       speech_start_sample=?, speech_end_sample=?,
                       generation_start_sample=?, generation_end_sample=?,
                       leading_silence_samples=?, trailing_silence_samples=?,
                       master_audio_artifact_id=?, master_audio_sha256=?,
                       updated_at=?
                       WHERE id=?""",
                    (
                        ss_start, ss_end,
                        gen_start, gen_end,
                        lead_silence, trail_silence,
                        master_artifact_id, master_sha,
                        _db._now(), unit_id,
                    ),
                )

            results.append({
                "render_unit_id": unit_id,
                "slice_path": slice_path,
                "artifact_id": art["id"],
                "sha256": slice_sha,
                "speech_start_sample": ss_start,
                "speech_end_sample": ss_end,
                "generation_start_sample": gen_start,
                "generation_end_sample": gen_end,
                "leading_silence_samples": lead_silence,
                "trailing_silence_samples": trail_silence,
            })

    return results


def materialize_hero_slot_slices(
    production_id: str,
    master_artifact_id: str,
    slot_bounds: list[dict],
    db_path=None,
) -> list[dict]:
    """S9-C05: Materialize exact master-narration slices for hero render-unit slots.

    Called by invoke_compile_media AFTER render units are planned. For each
    HERO_SYNC_LOCKED slot it extracts the master audio's [speech_start_sample,
    speech_end_sample] range as a sample-exact PCM WAV via ffmpeg, registers it as an
    immutable artifact (kind ``hero_audio_slice``), and writes master-audio provenance
    (``master_audio_artifact_id`` + ``master_audio_sha256``) plus the speech sample
    interval onto the render_unit row — the slice generation (S9-C06) passes to
    seedance ``--audio``.

    This is distinct from ``slice_hero_units`` (the beat-level, legacy file-led path
    that pads short beats with silence and advances the unit to 'generated'). Slot
    slicing TILES a long hero span exactly: no silence padding, and it deliberately
    does NOT set ``active_artifact_id`` / advance status — setting the generated media
    artifact is generation's job (R6-004). Per-slot min duration is guaranteed upstream
    by invoke_compile_media, so no min-padding is applied here.

    Slices are written next to the immutable master (``<master_dir>/hero_audio_slices``)
    so they survive across the compile→generate stages of one run and are regenerable
    from the master on re-plan (supersession, S9-C02).

    slot_bounds: list of ``{render_unit_id, speech_start_sample, speech_end_sample}``
    (samples at ``MASTER_SAMPLE_RATE``).

    Returns one dict per slot:
    ``{render_unit_id, slice_path, artifact_id, sha256, speech_start_sample, speech_end_sample}``
    """
    master = get_artifact(master_artifact_id, db_path=db_path)
    if not master:
        raise RuntimeError(f"Master audio artifact not found: {master_artifact_id}")
    master_path = Path(master["uri"])
    if not master_path.exists():
        raise FileNotFoundError(f"Master audio file missing: {master_path}")
    master_probe = probe_media(master_path)
    if master_probe is None:
        raise RuntimeError(f"Master audio is not valid media: {master_path}")
    master_duration_samples = int(master_probe.duration_ms * MASTER_SAMPLE_RATE / 1000)
    master_sha = master["sha256"]

    output_dir = master_path.parent / "hero_audio_slices"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for bounds in slot_bounds:
        unit_id = bounds["render_unit_id"]
        ss_start = int(bounds["speech_start_sample"])
        ss_end = int(bounds["speech_end_sample"])
        if ss_start >= ss_end:
            raise ValueError(f"render_unit {unit_id}: speech_start >= speech_end")
        if ss_start < 0:
            raise ValueError(f"render_unit {unit_id}: speech_start {ss_start} is negative")
        if ss_end > master_duration_samples:
            overshoot = ss_end - master_duration_samples
            if overshoot <= CLAMP_TOLERANCE_SAMPLES:
                ss_end = master_duration_samples
            else:
                raise ValueError(
                    f"render_unit {unit_id}: speech bounds [{ss_start},{ss_end}] "
                    f"outside master [0,{master_duration_samples}] "
                    f"(overshoot {overshoot} samples > tolerance {CLAMP_TOLERANCE_SAMPLES})"
                )

        # Sample-exact extraction (re-encode to PCM, never -c copy on a master that
        # may be MP3). -ss/-t before -i matches the slice_hero_units convention.
        speech_ss = samples_to_ms(ss_start) / 1000.0
        speech_dur = samples_to_ms(ss_end - ss_start) / 1000.0
        slice_path = output_dir / f"{unit_id}.wav"
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{speech_ss:.6f}",
            "-t", f"{speech_dur:.6f}",
            "-i", str(master_path),
            "-acodec", "pcm_s16le",
            "-ar", str(MASTER_SAMPLE_RATE),
            "-ac", "1",
            str(slice_path),
        ], capture_output=True, check=True)

        slice_probe = probe_media(slice_path)
        if slice_probe is None:
            raise RuntimeError(f"Slice is not valid media: {slice_path}")

        slice_sha = _sha(slice_path)
        art = register_artifact(
            production_id=production_id,
            path=slice_path,
            kind="hero_audio_slice",
            extra_metadata={
                "speech_start_sample": ss_start,
                "speech_end_sample": ss_end,
                "master_artifact_id": master_artifact_id,
                "master_sha256": master_sha,
                "render_unit_id": unit_id,
            },
            db_path=db_path,
        )

        # Provenance + speech interval on the unit row. Deliberately NOT touching
        # active_artifact_id / status — that is generation's responsibility (S9-C06).
        with _db.transaction(db_path) as conn:
            conn.execute(
                """UPDATE render_units SET
                   speech_start_sample=?, speech_end_sample=?,
                   master_audio_artifact_id=?, master_audio_sha256=?,
                   updated_at=?
                   WHERE id=?""",
                (ss_start, ss_end, master_artifact_id, master_sha, _db._now(), unit_id),
            )

        results.append({
            "render_unit_id": unit_id,
            "slice_path": slice_path,
            "artifact_id": art["id"],
            "sha256": slice_sha,
            "speech_start_sample": ss_start,
            "speech_end_sample": ss_end,
        })

    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sample-exact hero slice extraction with true silence")
    ap.add_argument("production_id", help="Production DB id")
    ap.add_argument("--db-path", help="Override DB path")
    ap.add_argument("--output-dir", help="Output directory for slices", default=None)
    args = ap.parse_args(argv)

    _db.migrate(args.db_path)

    # Find the master audio artifact
    conn = _db.connect(args.db_path)
    master_row = conn.execute(
        "SELECT id FROM artifacts WHERE production_id=? AND kind='master_audio' ORDER BY created_at DESC LIMIT 1",
        (args.production_id,),
    ).fetchone()
    if not master_row:
        # Fallback: find tts_master artifact
        master_row = conn.execute(
            "SELECT id FROM artifacts WHERE production_id=? AND kind='tts_master' ORDER BY created_at DESC LIMIT 1",
            (args.production_id,),
        ).fetchone()
    conn.close()

    if not master_row:
        print("No master audio artifact found. Run TTS first.", file=sys.stderr)
        return 1

    # Get hero render units with speech bounds from DB
    units = get_render_units(args.production_id, db_path=args.db_path)
    hero_units = [u for u in units if u.get("audio_policy") == "HERO_SYNC_LOCKED" and u.get("status") == "ordered"]
    if not hero_units:
        print("No ordered HERO_SYNC_LOCKED render units found")
        return 0

    output_dir = Path(args.output_dir) if args.output_dir else (ROOT / "Videos" / "slices")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Derive speech bounds from render_units (must be pre-populated by timing/compile)
    speech_bounds = []
    for u in hero_units:
        speech_bounds.append({
            "render_unit_id": u["id"],
            "speech_start_sample": u.get("speech_start_sample"),
            "speech_end_sample": u.get("speech_end_sample"),
            "generation_start_sample": u.get("generation_start_sample"),
            "generation_end_sample": u.get("generation_end_sample"),
            "leading_silence_samples": u.get("leading_silence_samples") or 0,
            "trailing_silence_samples": u.get("trailing_silence_samples") or 0,
        })

    results = slice_hero_units(
        production_id=args.production_id,
        master_artifact_id=master_row["id"],
        output_dir=output_dir,
        speech_bounds=speech_bounds,
        db_path=args.db_path,
    )

    print(json.dumps(results, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def slice_hero_from_master(project_dir, production_id=None, db_path=None):
    """Backward-compatible wrapper: slice from project_dir using canonical master.

    R3-002: This is a transition helper. It reads master audio from
    narration/continuous.mp3 inside project_dir, canonicalizes to PCM/WAV,
    and slices using sample-exact boundaries + true silence.

    Returns the media_plan dict with audio_slice populated for each hero beat.
    """
    from canonical_master import canonicalize_master
    import production_db as _db

    project_dir = Path(project_dir).resolve()
    nar = project_dir / "narration"
    master_mp3 = nar / "continuous.mp3"

    # If no official production_id, derive from dir name
    if production_id is None:
        try:
            production_id = _db.ensure_production(project_dir.name, db_path=db_path)["id"]
        except Exception:
            production_id = project_dir.name

    # Canonicalize the master audio (R3-001)
    canonical = canonicalize_master(
        production_id=production_id,
        source_path=master_mp3,
        output_dir=nar,
        db_path=db_path,
    )
    master_artifact_id = canonical["artifact_id"]
    master_duration_samples = canonical["total_samples"]

    # Read media_plan and timing map (legacy JSON fallback for transition)
    plan_path = project_dir / "media_plan.json"
    plan = json.loads(plan_path.read_text()) if plan_path.exists() else None
    bt_path = nar / "beat_timing_map.json"
    bt = json.loads(bt_path.read_text()) if bt_path.exists() else None

    if not plan or not bt:
        raise RuntimeError("media_plan.json and beat_timing_map.json required for legacy slicing")

    bt_by_id = {b["beat_id"]: b for b in bt["beats"]} if bt else {}

    target_beats = []
    if plan:
        target_beats = [b for b in plan["beats"] if b.get("lipsync_required")]
    if not target_beats:
        return plan

    LIPSYNC_MIN, LIPSYNC_MAX = _load_lipsync_limits()
    lipsync_min_samples = ms_to_samples(int(LIPSYNC_MIN * 1000))
    slices_dir = nar / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)

    for b in target_beats:
        bid = b["beat_id"]
        t = bt_by_id.get(bid)
        if not t:
            if b.get("audio_start_sec") is not None and b.get("audio_end_sec") is not None:
                t = {"start": b["audio_start_sec"], "end": b["audio_end_sec"]}
            else:
                continue

        speech_start_sec = t["start"]
        speech_end_sec = t["end"]
        speech_len = round(speech_end_sec - speech_start_sec, 3)

        if speech_len > LIPSYNC_MAX:
            raise ValueError(f"Beat {bid}: speech span {speech_len:.3f}s exceeds Seedance max {LIPSYNC_MAX:.1f}s")

        pad_needed_sec = max(0.0, LIPSYNC_MIN - speech_len)
        pad_needed_ms = round(pad_needed_sec * 1000)
        pad_samples = ms_to_samples(pad_needed_ms)
        lead_silence = pad_samples // 2
        trail_silence = pad_samples - lead_silence

        ss_start = int(speech_start_sec * 48000)
        ss_end = int(speech_end_sec * 48000)
        gen_start = max(0, ss_start - lead_silence)
        gen_end = min(master_duration_samples, ss_end + trail_silence)

        try:
            results = slice_hero_units(
                production_id=production_id,
                master_artifact_id=master_artifact_id,
                output_dir=slices_dir,
                speech_bounds=[{
                    "render_unit_id": bid,
                    "speech_start_sample": ss_start,
                    "speech_end_sample": ss_end,
                    "generation_start_sample": gen_start,
                    "generation_end_sample": gen_end,
                    "leading_silence_samples": gen_start >= 0 and (ss_start - gen_start) or 0,
                    "trailing_silence_samples": gen_end - ss_end,
                }],
                db_path=db_path,
            )
            if results:
                r = results[0]
                b["audio_slice"] = {
                    "file": str(r["slice_path"].relative_to(project_dir)),
                    "path": str(r["slice_path"].relative_to(project_dir)),
                    "sha256": r["sha256"],
                    "slice_sha256": r["sha256"],
                    "start_sec": round(gen_start / 48000, 3),
                    "end_sec": round(gen_end / 48000, 3),
                    "speech_start_sec": round(ss_start / 48000, 3),
                    "speech_end_sec": round(ss_end / 48000, 3),
                    "speech_len_sec": speech_len,
                    "padded_len_sec": round((gen_end - gen_start) / 48000, 3),
                    "leading_silence_sec": round((ss_start - gen_start) / 48000, 3),
                    "trailing_silence_sec": round((gen_end - ss_end) / 48000, 3),
                    "master_sha256": canonical["sha256"],
                    "master_start_sec": round(gen_start / 48000, 3),
                    "master_end_sec": round(gen_end / 48000, 3),
                    "parent_mp3_sha256": canonical["sha256"],
                    "parent_mp3": "narration/continuous.mp3",
                }
        except Exception as e:
            print(f"  WARN: failed to slice {bid}: {e}")
            continue

    plan_path.write_text(json.dumps(plan, indent=2))
    return plan

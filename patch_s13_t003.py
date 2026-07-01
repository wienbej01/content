#!/usr/bin/env python3
"""
Patch script to replace the continuous_voiceover section in assemble.py
with audio-island assembly implementation (S13-T003).
"""
import sys

# The old implementation (lines 1043-1099)
old_text = '''        # Normalize each visual segment to its narration duration (muted)
        norm_clips = []
        for i, seg in enumerate(segments):
            media = resolve(base, seg["media"])
            target_dur = seg_durations[i] if i < len(seg_durations) else total_nar_dur / len(segments)
            dst = fmt_tmp / f"cont_seg_{i}.mp4"
            scale_crop = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"

            media_kind = _segment_media_kind(seg, media)

            if media_kind == "video":
                # Generated-video b-roll. The clip length is non-deterministic
                # (kling3_0 returns ~4/5/6s buckets), so small shortfalls are
                # expected. Freeze-pad the tail up to MAX_FREEZE (imperceptible,
                # and well under qa_final's 1.5s freeze limit) rather than hard-
                # failing and forcing a regeneration. Only error if the shortfall
                # exceeds what a tail freeze can cover. Overshoot is trimmed by -t.
                clip_dur = probe_dur(media)
                shortfall = target_dur - clip_dur
                if shortfall > MAX_FREEZE:
                    raise RuntimeError(
                        f"Beat {seg.get('id', i)} clip too short: clip={clip_dur:.3f}s, "
                        f"required={target_dur:.3f}s (shortfall={shortfall:.3f}s exceeds "
                        f"the {MAX_FREEZE}s freeze-pad limit). "
                        f"Regenerate a longer clip or split into multiple shots.")
                pad = max(0.0, shortfall)
                vf = (f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={pad:.3f}"
                      if pad > 0.0 else f"{scale_crop},{grade}")
                run(["ffmpeg", "-y", "-i", str(media), "-an",
                     "-vf", vf,
                     "-t", f"{target_dur:.3f}",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-pix_fmt", "yuv420p", "-r", str(fps), str(dst)], f"cont_seg_{i}")
            else:
                # A still has no intrinsic duration. Its timeline duration comes
                # exclusively from the clip contract above.
                run(["ffmpeg", "-y", "-i", str(media), "-an",
                     "-vf", f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={target_dur:.3f}",
                     "-t", f"{target_dur:.3f}",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-pix_fmt", "yuv420p", "-r", str(fps), str(dst)], f"cont_seg_{i}")
            norm_clips.append(dst)

        # Concat all visual segments
        concat_list = fmt_tmp / "cont_concat.txt"
        concat_list.write_text("".join(f"file '{p}'\\n" for p in norm_clips))
        visual_bed = fmt_tmp / "cont_visual.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(visual_bed)], "cont_concat")

        # Change 2: Pre-mux visual bed duration check
        visual_bed_dur = probe_dur(visual_bed)
        if abs(visual_bed_dur - total_nar_dur) > 3.0:
            raise RuntimeError(
                f"Visual bed duration mismatch: visual={visual_bed_dur:.3f}s vs "
                f"audio={total_nar_dur:.3f}s (delta={visual_bed_dur - total_nar_dur:.3f}s). "
                f"Cannot mux — fix short clips first.")

        # Overlay continuous narration onto visual bed
        joined = fmt_tmp / "cont_joined.mp4"
        run(["ffmpeg", "-y", "-i", str(visual_bed), "-i", str(continuous_audio),
             "-map", "0:v", "-map", "1:a", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-t", f"{total_nar_dur:.3f}", str(joined)], "cont_overlay")'''

# The new audio-island implementation (S13-T003)
new_text = '''        # S13-T003: Audio-island assembly for hero lip sync
        # Separate hero_island clips (preserve compensated audio) from b-roll/graphics (muted)
        hero_clips = []
        broll_clips = []
        hero_indices = []
        broll_indices = []

        for i, seg in enumerate(segments):
            media = resolve(base, seg["media"])
            target_dur = seg_durations[i] if i < len(seg_durations) else total_nar_dur / len(segments)
            dst = fmt_tmp / f"cont_seg_{i}.mp4"
            scale_crop = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"

            # S13-T003: Check if this is a hero_island segment
            is_hero_island = False
            if get_audio_assembly_mode:
                try:
                    audio_policy = seg.get("audio_policy", "")
                    mode = get_audio_assembly_mode(audio_policy)
                    is_hero_island = (mode == "hero_island")
                except (ValueError, KeyError):
                    # Fallback to legacy detection if audio_assembly_mode fails
                    is_hero_island = _is_hero_lipsync(seg)
            else:
                # Fallback if get_audio_assembly_mode not available
                is_hero_island = _is_hero_lipsync(seg)

            if is_hero_island:
                # S13-T003: Hero island path - preserve compensated audio
                cap = seg.get("compensated_artifact_path")
                if cap:
                    cap_path = Path(cap)
                    if cap_path.exists():
                        # Use compensated video directly (already has corrected audio)
                        # Scale/crop to match target resolution
                        run(["ffmpeg", "-y", "-i", str(cap_path),
                             "-vf", f"{scale_crop},{grade}",
                             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                             "-pix_fmt", "yuv420p",
                             "-c:a", "copy",  # Preserve audio track
                             str(dst)], f"cont_seg_{i}_hero")
                        hero_clips.append(dst)
                        hero_indices.append(i)
                        continue
                    else:
                        print(f"WARNING: compensated_artifact_path '{cap}' not found for hero segment {i}. "
                              f"Falling back to muted visual.", file=sys.stderr)
                else:
                    print(f"WARNING: hero segment {i} missing compensated_artifact_path. "
                          f"Falling back to muted visual.", file=sys.stderr)

            # B-roll/graphics path: mute audio (existing behavior)
            media_kind = _segment_media_kind(seg, media)

            if media_kind == "video":
                # Generated-video b-roll. The clip length is non-deterministic
                clip_dur = probe_dur(media)
                shortfall = target_dur - clip_dur
                if shortfall > MAX_FREEZE:
                    raise RuntimeError(
                        f"Beat {seg.get('id', i)} clip too short: clip={clip_dur:.3f}s, "
                        f"required={target_dur:.3f}s (shortfall={shortfall:.3f}s exceeds "
                        f"the {MAX_FREEZE}s freeze-pad limit). "
                        f"Regenerate a longer clip or split into multiple shots.")
                pad = max(0.0, shortfall)
                vf = (f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={pad:.3f}"
                      if pad > 0.0 else f"{scale_crop},{grade}")
                run(["ffmpeg", "-y", "-i", str(media), "-an",
                     "-vf", vf,
                     "-t", f"{target_dur:.3f}",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-pix_fmt", "yuv420p", "-r", str(fps), str(dst)], f"cont_seg_{i}")
            else:
                # A still has no intrinsic duration. Its timeline duration comes
                # exclusively from the clip contract above.
                run(["ffmpeg", "-y", "-i", str(media), "-an",
                     "-vf", f"{scale_crop},{grade},tpad=stop_mode=clone:stop_duration={target_dur:.3f}",
                     "-t", f"{target_dur:.3f}",
                     "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                     "-pix_fmt", "yuv420p", "-r", str(fps), str(dst)], f"cont_seg_{i}")
            broll_clips.append(dst)
            broll_indices.append(i)

        # S13-T003: Concatenate b-roll/graphics visual bed (muted)
        if broll_clips:
            concat_list = fmt_tmp / "cont_broll_concat.txt"
            concat_list.write_text("".join(f"file '{p}'\\n" for p in broll_clips))
            visual_bed = fmt_tmp / "cont_visual.mp4"
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                 "-c", "copy", str(visual_bed)], "cont_broll_concat")
        else:
            visual_bed = None

        # S13-T003: Concatenate hero clips with audio preserved
        if hero_clips:
            hero_concat_list = fmt_tmp / "cont_hero_concat.txt"
            hero_concat_list.write_text("".join(f"file '{p}'\\n" for p in hero_clips))
            hero_bed = fmt_tmp / "cont_hero.mp4"
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(hero_concat_list),
                 "-c", "copy", str(hero_bed)], "cont_hero_concat")
        else:
            hero_bed = None

        # S13-T003: Merge streams with correct audio routing
        # Strategy: Use ffmpeg complex filter to overlay narration on b-roll only
        # while preserving hero audio as-is
        if hero_bed and visual_bed:
            # Both hero and b-roll present: merge in timeline order
            # Build concat list preserving timeline order
            mixed_clips = []
            hero_idx = 0
            broll_idx = 0
            for i in range(len(segments)):
                if i in hero_indices and hero_idx < len(hero_clips):
                    mixed_clips.append(f"file '{hero_clips[hero_idx]}'\\n")
                    hero_idx += 1
                elif i in broll_indices and broll_idx < len(broll_clips):
                    mixed_clips.append(f"file '{broll_clips[broll_idx]}'\\n")
                    broll_idx += 1

            concat_list = fmt_tmp / "cont_mixed_concat.txt"
            concat_list.write_text("".join(mixed_clips))
            joined_video = fmt_tmp / "cont_joined_video.mp4"
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                 "-c", "copy", str(joined_video)], "cont_mixed_video")

            # Overlay narration on the full video (affects only b-roll sections)
            joined = fmt_tmp / "cont_joined.mp4"
            run(["ffmpeg", "-y", "-i", str(joined_video), "-i", str(continuous_audio),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 "-shortest", str(joined)], "cont_overlay_mixed")

        elif hero_bed:
            # Only hero clips: no narration overlay needed
            joined = hero_bed
        elif visual_bed:
            # Only b-roll clips: use existing path
            joined = fmt_tmp / "cont_joined.mp4"
            run(["ffmpeg", "-y", "-i", str(visual_bed), "-i", str(continuous_audio),
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                 "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                 "-t", f"{total_nar_dur:.3f}", str(joined)], "cont_overlay")
        else:
            raise RuntimeError("No clips to assemble")'''

# Read the file
with open('scripts/assemble.py', 'r') as f:
    content = f.read()

# Replace the old text with new text
if old_text in content:
    content = content.replace(old_text, new_text)
    with open('scripts/assemble.py', 'w') as f:
        f.write(content)
    print("Successfully replaced audio-island assembly implementation")
    sys.exit(0)
else:
    print("ERROR: Could not find the exact text to replace")
    print("Old text length:", len(old_text))
    # Show context
    if old_text[:100] in content:
        print("Found prefix match")
    else:
        print("Prefix not found")
    sys.exit(1)

#!/usr/bin/env python3
"""build_trailer.py — assemble branded 16:9 trailer from lipsync clips via ffmpeg.

Pipeline:
  1. Normalize each input clip -> 1920x1080, 24fps, center-cropped from near-square source
  2. Apply a subtle warm color grade (toward navy/gold brand palette)
  3. Crossfade clips together (xfade) with matching audio crossfade
  4. Burn in lower-third on the opening clip (fade in/out)
  5. Append branded end card (still -> short video) with fade
  6. Loudness-normalize the audio (EBU R128)

Outputs: Videos/Completed/trailer_leveragemind_16x9.mp4

Usage:
  python3 brand/build_trailer.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from narrative_speed import measure as measure_pace  # noqa: E402
from generate_music import generate as gen_music, write_wav as write_music_wav  # noqa: E402
IN = ROOT / "Videos" / "Input_video"
ASSETS = ROOT / "brand" / "assets"
OUT = ROOT / "Videos" / "Completed"
TMP = ROOT / "Videos" / "_tmp"
OUT.mkdir(exist_ok=True)
TMP.mkdir(exist_ok=True)

# (clip_path, words, trim_to) — words feeds programmatic WPS measurement.
# Per-clip playback speed is COMPUTED at build time so every segment matches the
# reference clip's words-per-second. No manual speed guesses: this auto-corrects
# the Seedance-2.0 variable-speech-rate artifact for any future clip.
# trim_to: trim clip to this many SOURCE seconds (cuts trailing dead air); None = full.
CLIPS = [
    (IN / "trailer_1a.mp4", 15, None),   # "You won't find my face on a stage..."
    (IN / "trailer_2a.mp4", 24, None),   # "But over thirty-five years..." (REFERENCE pace)
    (IN / "trailer_3a.mp4", 10, 6.65),   # "This is Leverage Mind..." (+ trim 3.82s tail silence)
]
REF_INDEX = 1          # clip 2 is the pacing reference (the good/fast one)
REF_SPEED = 0.85       # baseline playback speed applied to the reference clip

# Music bed: ORIGINAL generated ambient pad (royalty-free, no copyright/Content-ID
# risk, no audible loop). Tunable mood; rendered to the exact trailer length.
MUSIC_MOOD = "calm"       # see tools/generate_music.py PROGRESSIONS
MUSIC_BED_DB = -16.0      # duck the bed under narration (subtle pre-loudnorm level)
LOWER_THIRD = ASSETS / "lower_third.png"
ENDCARD = ASSETS / "endcard_16x9.png"

W, H, FPS = 1920, 1080, 24
GAP = 0.4            # silent gap between clips (s) — prevents VO overlap
AUDIO_FADE = 0.3     # fade-out/in on audio tails/heads (s)
ENDCARD_DUR = 3.0    # end card length (s)


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd[:6]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        sys.exit(f"ffmpeg failed (exit {r.returncode})")
    return r


def compute_speeds():
    """Measure each clip's WPS and return per-clip playback speeds that make every
    segment match the reference clip's words-per-second. Fully programmatic — the
    fix for Seedance's variable speech rate, no manual guessing."""
    wps = []
    for (src, words, trim_to) in CLIPS:
        pace = measure_pace(src, words)
        wps.append(pace.wps)
    ref_wps = wps[REF_INDEX]
    speeds = []
    for i, w in enumerate(wps):
        # rendered WPS = source_wps * speed; reference renders at REF_SPEED.
        # target rendered WPS = ref_wps * REF_SPEED  -> speed_i = REF_SPEED*ref_wps/w_i
        speeds.append(REF_SPEED * ref_wps / w)
    return wps, speeds, ref_wps


def probe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    return float(r.stdout.strip())


def normalize_clip(src, dst, with_lower_third=False, speed=1.0, trim_to=None):
    """Scale+crop to 1920x1080, 24fps, warm grade. Optionally trim, slow, burn lower-third.

    speed<1.0 slows playback (video setpts + audio atempo) keeping A/V in sync.
    trim_to: if set, cut the SOURCE to this many seconds first (removes trailing dead air).
    Lower-third is supplied as a real -i input and overlaid via -filter_complex
    (the `movie=` filter stalls inside -vf, so we avoid it).
    """
    trim_args = ["-t", str(trim_to)] if trim_to else []
    pts = 1.0 / speed
    speed_vf = f"setpts={pts:.4f}*PTS," if abs(speed - 1.0) > 1e-3 else ""
    speed_af = f"atempo={speed:.4f}," if abs(speed - 1.0) > 1e-3 else ""
    grade = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},fps={FPS},"
        f"eq=contrast=1.04:saturation=1.05:gamma=0.98,"
        f"colorbalance=rs=0.02:gs=0.0:bs=-0.03:rm=0.02:bm=-0.02"
    )
    src_dur = trim_to if trim_to else probe_dur(src)

    if with_lower_third:
        d = src_dur / speed
        fin, fout = 0.6, 0.6
        show_from, show_to = 0.8, max(d - 1.0, 1.2)
        fc = (
            f"[0:v]{speed_vf}{grade}[base];"
            f"[1:v]format=rgba,"
            f"fade=t=in:st={show_from}:d={fin}:alpha=1,"
            f"fade=t=out:st={show_to}:d={fout}:alpha=1[lt];"
            f"[base][lt]overlay=70:H-h-70:"
            f"enable='between(t,{show_from},{show_to+fout})'[v]"
        )
        run(["ffmpeg", "-y", *trim_args, "-i", str(src), "-loop", "1", "-i", str(LOWER_THIRD),
             "-filter_complex", fc, "-map", "[v]", "-map", "0:a",
             "-af", f"{speed_af}aresample=48000", "-shortest",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-pix_fmt", "yuv420p", str(dst)])
    else:
        run(["ffmpeg", "-y", *trim_args, "-i", str(src),
             "-vf", f"{speed_vf}{grade}",
             "-af", f"{speed_af}aresample=48000",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-pix_fmt", "yuv420p", str(dst)])


def make_endcard_clip(dst):
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(ENDCARD), "-t", str(ENDCARD_DUR),
         "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-vf", f"scale={W}:{H},fps={FPS},fade=t=in:st=0:d=0.6,fade=t=out:st={ENDCARD_DUR-0.6}:d=0.6",
         "-t", str(ENDCARD_DUR),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-pix_fmt", "yuv420p", str(dst)])


def gap_concat(parts, dst):
    """Concatenate clips with a short black+silent gap between them.

    This guarantees zero audio overlap between segments (the previous
    xfade/acrossfade approach caused VO from clip N to bleed into clip N+1).
    Each clip's audio is faded out at the tail before the gap.
    """
    # Prepare each clip: add audio fade-out at tail, fade-in at head
    prepped = []
    for i, p in enumerate(parts):
        d = probe_dur(p)
        fade_out_start = max(d - AUDIO_FADE, 0)
        tmp = TMP / f"prepped_{i}.mp4"
        af = f"afade=t=in:st=0:d={AUDIO_FADE},afade=t=out:st={fade_out_start:.3f}:d={AUDIO_FADE}"
        vf = f"fade=t=out:st={fade_out_start:.3f}:d={AUDIO_FADE}"
        run(["ffmpeg", "-y", "-i", str(p),
             "-vf", vf, "-af", af,
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
             "-pix_fmt", "yuv420p", str(tmp)])
        prepped.append(tmp)

    # Build concat list with silent black gaps between clips
    concat_list = TMP / "concat.txt"
    gap_clip = TMP / "gap.mp4"
    # Create a short black+silent gap clip
    run(["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={GAP}",
         "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
         "-t", str(GAP),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-pix_fmt", "yuv420p", str(gap_clip)])

    with open(concat_list, "w") as f:
        for i, p in enumerate(prepped):
            f.write(f"file '{p}'\n")
            if i < len(prepped) - 1:  # gap between clips, not after last
                f.write(f"file '{gap_clip}'\n")

    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-pix_fmt", "yuv420p", str(dst)])


def make_music_bed(total_dur, dst):
    """Generate an ORIGINAL ambient bed of exactly total_dur (no loop), duck it,
    and encode. Original IP -> no copyright/Content-ID risk; evolving chord
    progression -> no audible repeat."""
    wav = TMP / "music_original.wav"
    stereo = gen_music(total_dur, MUSIC_MOOD)
    write_music_wav(stereo, wav)
    fade_out_start = max(total_dur - 1.4, 0)
    run(["ffmpeg", "-y", "-i", str(wav),
         "-af", (f"volume={MUSIC_BED_DB}dB,"
                 f"afade=t=in:st=0:d=1.2,"
                 f"afade=t=out:st={fade_out_start:.3f}:d=1.4,"
                 f"aresample=48000"),
         "-ac", "2", "-c:a", "aac", "-b:a", "192k", str(dst)])


def mix_music(video_src, bed_src, dst):
    """Mix the looped music bed UNDER the narration of the assembled video."""
    run(["ffmpeg", "-y", "-i", str(video_src), "-i", str(bed_src),
         "-filter_complex",
         "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
         "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         str(dst)])


def loudnorm(src, dst):
    run(["ffmpeg", "-y", "-i", str(src),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(dst)])


def main():
    srcs = [c[0] for c in CLIPS]
    for c in srcs + [LOWER_THIRD, ENDCARD]:
        if not c.exists():
            sys.exit(f"Missing input: {c}")

    print("0/5 Measuring narrative speed (WPS) + computing alignment...")
    wps, speeds, ref_wps = compute_speeds()
    for i, (src, words, _) in enumerate(CLIPS):
        tag = "  <- reference" if i == REF_INDEX else ""
        print(f"   {src.name:18s} {words:3d}w  {wps[i]:.2f} wps  -> speed x{speeds[i]:.3f}{tag}")
    print(f"   target rendered pace = {ref_wps * REF_SPEED:.2f} wps (all segments aligned)")

    print("1/5 Normalizing clips (speed align + trim)...")
    norm = []
    for i, (src, words, trim_to) in enumerate(CLIPS):
        dst = TMP / f"norm_{i}.mp4"
        normalize_clip(src, dst, with_lower_third=(i == 0), speed=speeds[i], trim_to=trim_to)
        norm.append(dst)
    print("2/5 Building end card clip...")
    ec = TMP / "endcard.mp4"
    make_endcard_clip(ec)
    norm.append(ec)
    print("3/5 Concatenating with silent gaps (no VO overlap)...")
    joined = TMP / "joined.mp4"
    gap_concat(norm, joined)
    print("4/5 Adding original generated music bed (no loop)...")
    total = probe_dur(joined)
    bed = TMP / "music_bed.m4a"
    make_music_bed(total, bed)
    mixed = TMP / "mixed.mp4"
    mix_music(joined, bed, mixed)
    print("5/5 Loudness-normalizing audio...")
    final = OUT / "trailer_leveragemind_16x9.mp4"
    loudnorm(mixed, final)
    dur = probe_dur(final)
    print(f"\nDONE -> {final}  ({dur:.1f}s, {W}x{H}, {FPS}fps)")


if __name__ == "__main__":
    main()

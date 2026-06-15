#!/usr/bin/env python3
"""upscale_media.py — pipeline stage 6.5: upscale + enhance raw generation outputs.

Raw Seedance/Kling outputs are soft 720p (the model spends compute on lipsync, not
texture). For a premium channel they must be crisp 1080p. This stage runs between
generate_media.py and qa_media.py:

    [6 Generation] -> [6.5 Upscale] -> [7 QA] -> [8 Assembly]

Engine chain (first available wins):
  1. Real-ESRGAN (realesrgan-ncnn-vulkan) — best AI detail recovery, if installed.
  2. ffmpeg high-quality pass (always available) — lanczos upscale to 1080p +
     light nlmeans denoise + contrast-adaptive sharpen (cas). Recovers perceived
     sharpness/detail without the AI-soft look; no new dependency.

Idempotent: writes <name>_1080.mp4 next to the source and (optionally) replaces the
beat's output_path so QA/assembly use the upscaled file. Hero (lipsync) clips get a
gentler sharpen to avoid mouth-artifact crunch.

Usage:
  python3 scripts/upscale_media.py <media_plan.json> [--target 1080|2160] [--in-place]
  python3 scripts/upscale_media.py <single_clip.mp4> --out <out.mp4>
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {"1080": (1920, 1080), "2160": (3840, 2160)}


def _has_realesrgan():
    return shutil.which("realesrgan-ncnn-vulkan") is not None


def _probe_dims(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path)],
                       capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split("x")
        return int(w), int(h)
    except ValueError:
        return None, None


def upscale_ffmpeg(src, dst, target=(1920, 1080), gentle=False):
    """High-quality ffmpeg upscale: lanczos scale + light denoise + contrast-adaptive
    sharpen. gentle=True (hero/lipsync) uses a softer sharpen to avoid mouth crunch.
    Preserves audio."""
    tw, th = target
    # nlmeans light denoise removes the AI 'swimming', cas restores micro-contrast.
    sharp = "cas=strength=0.35" if gentle else "cas=strength=0.55"
    denoise = "nlmeans=s=1.0:p=3:r=7" if not gentle else "nlmeans=s=1.0:p=3:r=5"
    vf = (f"scale={tw}:{th}:flags=lanczos:force_original_aspect_ratio=decrease,"
          f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,{denoise},{sharp},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-i", str(src), "-vf", vf,
           "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p"]
    # preserve audio if present
    cmd += ["-c:a", "copy", "-map", "0:v:0", "-map", "0:a?", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg upscale failed: {r.stderr[-400:]}")
    return dst


def upscale_realesrgan(src, dst, target=(1920, 1080), gentle=False):
    """Real-ESRGAN per-frame upscale (if installed). Falls back to ffmpeg on any error.
    NOTE: extracts frames, upscales, re-muxes with original audio. Heavier but best
    detail. Only used when the binary is present."""
    import tempfile
    tw, th = target
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        fin, fout = td / "in", td / "out"
        fin.mkdir(); fout.mkdir()
        # extract frames + fps
        subprocess.run(["ffmpeg", "-y", "-i", str(src), str(fin / "f%06d.png")], capture_output=True)
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(src)],
                           capture_output=True, text=True)
        fps = r.stdout.strip() or "24"
        model = "realesrgan-x4plus"
        rc = subprocess.run(["realesrgan-ncnn-vulkan", "-i", str(fin), "-o", str(fout),
                             "-n", model, "-s", "4"], capture_output=True)
        if rc.returncode != 0 or not any(fout.iterdir()):
            return upscale_ffmpeg(src, dst, target, gentle)
        # downscale the 4x frames to the exact target + reassemble + remux audio
        vf = (f"scale={tw}:{th}:flags=lanczos:force_original_aspect_ratio=decrease,"
              f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-framerate", fps, "-i", str(fout / "f%06d.png"),
                        "-i", str(src), "-vf", vf, "-map", "0:v:0", "-map", "1:a?",
                        "-c:v", "libx264", "-crf", "16", "-preset", "slow",
                        "-c:a", "copy", "-pix_fmt", "yuv420p", str(dst)], capture_output=True)
    return dst


def upscale_clip(src, dst, target=(1920, 1080), gentle=False):
    if _has_realesrgan():
        return upscale_realesrgan(src, dst, target, gentle)
    return upscale_ffmpeg(src, dst, target, gentle)


def upscale_plan(plan_path, target=(1920, 1080), in_place=False):
    """Upscale every generated (non-local) clip referenced by the media plan.
    Hero/lipsync clips get the gentle sharpen. Returns a report."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text())
    engine = "realesrgan" if _has_realesrgan() else "ffmpeg-hq"
    results = []
    for b in plan.get("beats", []):
        if b.get("asset_type") not in ("generated_video", "generated_still"):
            continue
        op = b.get("output_path")
        if not op:
            continue
        src = ROOT / op
        if not src.exists():
            results.append({"beat_id": b["beat_id"], "status": "missing"})
            continue
        w, h = _probe_dims(src)
        if w and w >= target[0]:
            results.append({"beat_id": b["beat_id"], "status": "already_hires", "dims": f"{w}x{h}"})
            continue
        gentle = bool(b.get("lipsync_required"))
        dst = src.with_name(src.stem + f"_{target[1]}.mp4")
        upscale_clip(src, dst, target, gentle)
        nw, nh = _probe_dims(dst)
        if in_place:
            # point the plan at the upscaled file so QA/assembly use it
            up_rel = str(dst.relative_to(ROOT))
            b["output_path"] = up_rel
        results.append({"beat_id": b["beat_id"], "status": "upscaled",
                        "from": f"{w}x{h}", "to": f"{nw}x{nh}", "gentle": gentle,
                        "file": str(dst.relative_to(ROOT))})
    if in_place:
        plan_path.write_text(json.dumps(plan, indent=2))
    return {"engine": engine, "target": f"{target[0]}x{target[1]}", "results": results}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Upscale generation outputs (stage 6.5).")
    ap.add_argument("input", help="media_plan.json OR a single clip path")
    ap.add_argument("--target", choices=list(TARGETS), default="1080")
    ap.add_argument("--in-place", action="store_true",
                    help="repoint the media plan's output_path to upscaled files")
    ap.add_argument("--out", help="output path (single-clip mode)")
    ap.add_argument("--gentle", action="store_true", help="gentle sharpen (single-clip mode)")
    args = ap.parse_args(argv)
    target = TARGETS[args.target]

    p = Path(args.input)
    if p.suffix == ".json":
        rep = upscale_plan(p, target, args.in_place)
        up = [r for r in rep["results"] if r["status"] == "upscaled"]
        print(f"  upscale [{rep['engine']}] → {rep['target']}: {len(up)} clips upscaled")
        for r in rep["results"]:
            print(f"    {r['beat_id']}: {r['status']}" +
                  (f" {r.get('from')}→{r.get('to')}" if r["status"] == "upscaled" else ""))
    else:
        out = Path(args.out) if args.out else p.with_name(p.stem + f"_{args.target}.mp4")
        upscale_clip(p, out, target, args.gentle)
        print(f"  upscaled {p.name} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Append an HP outro/end-card onto any social video with a clean crossfade.

The last mile: turn "I have a 3s end-card" into "it's on my post." Handles the
messy parts automatically — different fps, odd SAR, missing audio tracks, any
input size — by normalizing the clip to 1080x1920/30fps (+ a silent track if
needed), then crossfading into the chosen outro style.

    # one clip
    python3 services/media/append_outro.py reel.mp4 --style slam
    # pick the transition + crossfade length
    python3 services/media/append_outro.py reel.mp4 --style chrome --transition slideup --crossfade 0.5
    # cover-crop instead of letterbox-pad; custom output
    python3 services/media/append_outro.py reel.mp4 --style neon --fit cover -o ready/reel_out.mp4
    # batch a whole folder -> <folder>/_with_outro/
    python3 services/media/append_outro.py content/preview --style ember --batch

Outputs an MP4 ready to post (h264 / yuv420p / faststart).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUTRO_DIR = os.path.join(ROOT, "content", "brand", "outro")
STYLES = ("neon", "ember", "glitch", "chrome", "slam")
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".mkv", ".webm")

W, H, FPS = 1080, 1920, 30


def outro_path(style: str, silent: bool) -> str:
    suffix = f"hp-outro-{style}-silent.mp4" if silent else f"hp-outro-{style}.mp4"
    p = os.path.join(OUTRO_DIR, style, suffix)
    if not os.path.exists(p):  # the original un-styled clip lives one level up
        alt = os.path.join(OUTRO_DIR, "hp-outro.mp4")
        if style == "neon" and os.path.exists(alt):
            return alt
        raise FileNotFoundError(f"outro not found: {p}")
    return p


def probe(path: str) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type", "-of", "json", path],
        check=True, capture_output=True, text=True).stdout
    d = json.loads(out)
    dur = float(d.get("format", {}).get("duration", 0) or 0)
    has_audio = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    return {"duration": dur, "has_audio": has_audio}


def normalize(src: str, dst: str, fit: str) -> None:
    """Re-encode src to 1080x1920 / 30fps / yuv420p with a guaranteed AAC track."""
    if fit == "cover":
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H}")
    else:  # pad / letterbox (never crops content)
        vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
              f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black")
    vf += f",fps={FPS},format=yuv420p,setsar=1"

    info = probe(src)
    cmd = ["ffmpeg", "-y", "-i", src]
    if not info["has_audio"]:
        cmd += ["-f", "lavfi", "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000"]
    cmd += ["-vf", vf, "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    if not info["has_audio"]:
        cmd += ["-shortest", "-map", "0:v:0", "-map", "1:a:0"]
    cmd += [dst]
    subprocess.run(cmd, check=True, capture_output=True)


def append(src: str, style: str, out: str, crossfade: float,
           transition: str, fit: str, silent_outro: bool) -> str:
    outro = outro_path(style, silent_outro)
    with tempfile.TemporaryDirectory() as tmp:
        norm = os.path.join(tmp, "norm.mp4")
        normalize(src, norm, fit)
        dur = probe(norm)["duration"]
        offset = max(0.0, dur - crossfade)
        fc = (
            f"[0:v][1:v]xfade=transition={transition}:duration={crossfade}:"
            f"offset={offset:.3f}[v];"
            f"[0:a][1:a]acrossfade=d={crossfade}[a]"
        )
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        subprocess.run(
            ["ffmpeg", "-y", "-i", norm, "-i", outro, "-filter_complex", fc,
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "17",
             "-preset", "slow", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out],
            check=True, capture_output=True)
    return out


def default_out(src: str, style: str) -> str:
    d, base = os.path.split(src)
    stem, _ = os.path.splitext(base)
    return os.path.join(d or ".", "_with_outro", f"{stem}__{style}.mp4")


def main() -> int:
    ap = argparse.ArgumentParser(description="Append an HP outro to a video.")
    ap.add_argument("input", help="Video file, or a folder when --batch.")
    ap.add_argument("--style", choices=STYLES, default="slam")
    ap.add_argument("-o", "--out", default=None, help="Output path (single file).")
    ap.add_argument("--crossfade", type=float, default=0.4, help="Seconds.")
    ap.add_argument("--transition", default="fade",
                    help="xfade transition (fade, fadeblack, slideup, wipeleft, "
                         "smoothup, circleopen, ...).")
    ap.add_argument("--fit", choices=("pad", "cover"), default="pad",
                    help="pad = letterbox (no crop); cover = fill + center-crop.")
    ap.add_argument("--silent-outro", action="store_true",
                    help="Use the no-audio outro (keeps only the clip's audio).")
    ap.add_argument("--batch", action="store_true",
                    help="Treat input as a folder; process every video in it.")
    a = ap.parse_args()

    if a.batch:
        srcs = [os.path.join(a.input, f) for f in sorted(os.listdir(a.input))
                if f.lower().endswith(VIDEO_EXTS)]
        if not srcs:
            print(f"no videos in {a.input}")
            return 1
        for s in srcs:
            out = default_out(s, a.style)
            append(s, a.style, out, a.crossfade, a.transition, a.fit, a.silent_outro)
            print(f"  {os.path.basename(s)} -> {out}")
        print(f"DONE {len(srcs)} clips")
    else:
        out = a.out or default_out(a.input, a.style)
        append(a.input, a.style, out, a.crossfade, a.transition, a.fit, a.silent_outro)
        print(f"DONE -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

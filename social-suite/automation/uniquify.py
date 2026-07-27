"""Make a per-account UNIQUE copy of a clip so multi-account posting isn't spammy.

Posting the byte-identical file to several accounts on the same platform is the
#1 ban/shadowban trigger. This re-renders the clip with tiny, deterministic
per-account tweaks so every account's copy has a **different fingerprint** while
looking the same to a viewer:

  * re-encode (new hash on its own)
  * a few pixels cropped then scaled back (shifts the visual hash)
  * micro brightness/saturation shift
  * a few ms trimmed off the head
  * optional horizontal mirror (for accounts flagged ``mirror``)
  * all metadata stripped + a unique comment tag

Deterministic per ``seed`` (use the account id + clip name) so re-runs are stable.
Runs ffmpeg via subprocess — the machine that posts already has it (moviepy).
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile


def _ffmpeg_bin() -> str:
    """Prefer a system ffmpeg; fall back to the one moviepy/imageio bundles."""
    from shutil import which
    exe = which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        return "ffmpeg"


def _knobs(seed: str) -> dict:
    """Deterministic tiny variations from a seed string."""
    h = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    return {
        "crop": 2 + (h % 6),                     # 2..7 px off each edge
        "bright": ((h >> 4) % 9 - 4) / 100.0,    # -0.04..0.04
        "sat": 1.0 + (((h >> 8) % 9 - 4) / 100.0),  # 0.96..1.04
        "trim": ((h >> 12) % 6) / 100.0,         # 0..0.05 s off the head
        "tag": h % 1_000_000,
    }


def uniquify(src: str, dst: str | None = None, seed: str = "",
             mirror: bool = False, width: int = 1080, height: int = 1920) -> str:
    """Render a unique variant of ``src`` to ``dst`` (a temp file if dst is None).

    Args:
        src: source video path.
        dst: output path; if None, a temp .mp4 is created and returned.
        seed: per-account seed (e.g. f"{account_id}:{os.path.basename(src)}").
        mirror: horizontally flip (use for *some* accounts, not all).
        width/height: output size (defaults to vertical 1080x1920).

    Returns the output path. Raises CalledProcessError if ffmpeg fails.
    """
    k = _knobs(seed or os.path.basename(src))
    if dst is None:
        fd, dst = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)

    c = k["crop"]
    vf = [f"crop=in_w-{2 * c}:in_h-{2 * c}", f"scale={width}:{height}"]
    if mirror:
        vf.append("hflip")
    vf.append(f"eq=brightness={k['bright']:.3f}:saturation={k['sat']:.3f}")

    cmd = [
        _ffmpeg_bin(), "-y", "-ss", f"{k['trim']:.3f}", "-i", src,
        "-vf", ",".join(vf),
        "-map_metadata", "-1",
        "-metadata", f"comment=hp-{k['tag']}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        dst,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst


def file_fingerprint(path: str) -> str:
    """SHA-256 of the file bytes — for confirming two renders really differ."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":  # quick self-test: uniquify a clip a few ways, show hashes
    import sys
    if len(sys.argv) < 2:
        print("usage: python uniquify.py <video.mp4>")
        raise SystemExit(1)
    src = sys.argv[1]
    print("source     :", file_fingerprint(src)[:16])
    for acct in ("hp-ig", "pools-tt", "design-tt"):
        out = uniquify(src, seed=f"{acct}:{os.path.basename(src)}", mirror=(acct == "design-tt"))
        print(f"{acct:10}:", file_fingerprint(out)[:16], out)
        os.remove(out)

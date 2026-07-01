"""Locked HP montage styling — serif beats, logo watermark, outro append.

Productionizes the owner-approved recipe (STYLE_PROFILE.md "LOCKED MONTAGE
RECIPE") so it runs on the GitHub Actions runner instead of by hand:

* **Shifting layouts** per segment via :func:`plan_layouts` (3-rows -> 2-rows ->
  single -> 2-cols -> single; never 3-cols).
* **Serif text beats** (Libre-Baskerville-style; we ship DejaVu Serif Bold as the
  committed TTF the runner needs) — white + soft shadow, centered ~0.44 height,
  every-other beat revealing one word at a time.
* **Logo top-right** the whole clip; **outro end-card** crossfaded on.

The pure helpers (``plan_layouts``, ``pick_top_shots``, ``build_serif_filter``)
are unit-tested; the ffmpeg ops degrade gracefully (missing logo/outro = skip).
Montages stay **silent** (owner adds trending audio); talking clips keep audio.
"""
from __future__ import annotations

import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SERIF_FONT = os.path.join(ROOT, "assets", "fonts", "DejaVuSerif-Bold.ttf")

W, H = 1080, 1920
# Layout rotation for an energetic, changing-views montage. No 3-columns (owner).
LAYOUT_CYCLE = ("rows3", "rows2", "single", "cols2", "single", "rows2")


def plan_layouts(n: int) -> list[str]:
    """Return ``n`` layout names following the locked rotation (pure)."""
    return [LAYOUT_CYCLE[i % len(LAYOUT_CYCLE)] for i in range(max(0, n))]


def pick_top_shots(scored: list[dict], k: int = 6, min_gap: float = 0.0) -> list[dict]:
    """Pick the ``k`` highest ``fire_score`` shots, kept in time order (pure).

    ``min_gap`` (seconds) optionally enforces spacing between picks so the
    montage doesn't grab three near-identical adjacent shots.
    """
    ranked = sorted(scored, key=lambda s: s.get("fire_score", 0), reverse=True)
    picked: list[dict] = []
    for s in ranked:
        if len(picked) >= k:
            break
        if min_gap > 0 and any(abs(s.get("start", 0) - p.get("start", 0)) < min_gap
                               for p in picked):
            continue
        picked.append(s)
    picked.sort(key=lambda s: s.get("start", 0))
    return picked


def _beat_window(shot: dict, beat: float) -> tuple[float, float]:
    """A ``beat``-second window centered in ``shot`` (or the whole shot if shorter)."""
    s = float(shot.get("start", 0.0))
    e = float(shot.get("end", s + beat))
    if (e - s) <= beat:
        return (round(s, 2), round(e, 2))
    mid = (s + e) / 2.0
    return (round(mid - beat / 2, 2), round(mid + beat / 2, 2))


def _layout_for(n: int, preferred: str) -> str:
    """A valid layout for ``n`` shots, honouring the rotation's intent."""
    if n <= 1:
        return "single"
    if n == 2:
        return preferred if preferred in ("rows2", "cols2") else "rows2"
    return "rows3"


def select_for_montage(scored: list[dict], *, target_s: float = 15.0,
                       beat_s: float = 3.0, min_score: float = 50.0,
                       min_gap: float = 1.0, xfade: float = 0.45) -> list[dict]:
    """Plan a montage that lands in the 10–20s zone using ONLY good shots (pure).

    Drops every shot below ``min_score`` (the "all good content" floor), then fills
    layout-shifting segments — each trimmed to a ``beat_s`` beat — until the
    accumulated runtime reaches ``target_s``. Returns a list of segments:
    ``{layout, windows:[(start,end)...], scores:[...]}``. Empty if nothing clears
    the bar, so a weak video yields no clip rather than bad content.
    """
    good = sorted((s for s in scored if s.get("fire_score", 0) >= min_score),
                  key=lambda s: s.get("fire_score", 0), reverse=True)
    if not good:
        return []
    sizes = {"single": 1, "rows2": 2, "cols2": 2, "rows3": 3}
    pool = list(good)
    chosen_starts: list[float] = []
    plan: list[dict] = []
    acc = 0.0
    li = 0

    def far_enough(s) -> bool:
        return min_gap <= 0 or all(
            abs(float(s.get("start", 0)) - c) >= min_gap for c in chosen_starts)

    while acc < target_s and pool:
        want = sizes[LAYOUT_CYCLE[li % len(LAYOUT_CYCLE)]]
        li += 1
        seg, k = [], 0
        while len(seg) < want and k < len(pool):
            if far_enough(pool[k]):
                s = pool.pop(k)
                seg.append(s)
                chosen_starts.append(float(s.get("start", 0)))
            else:
                k += 1
        if not seg:                       # spacing blocked everything left
            seg = [pool.pop(0)]
        layout = _layout_for(len(seg), LAYOUT_CYCLE[(li - 1) % len(LAYOUT_CYCLE)])
        plan.append({
            "layout": layout,
            "windows": [_beat_window(s, beat_s) for s in seg],
            "scores": [s.get("fire_score") for s in seg],
        })
        acc += beat_s - xfade
    return plan


# ---- serif text beats ------------------------------------------------------
def _esc(text: str) -> str:
    """Escape a string for ffmpeg drawtext ``text=`` (quotes/colons/backslashes)."""
    return (text.replace("\\", "\\\\").replace(":", "\\:")
            .replace("'", "’").replace("%", "\\%"))


def build_serif_filter(beats: list[dict], *, w: int = W, h: int = H,
                       font: str = SERIF_FONT) -> str:
    """Build a drawtext filter chain for timed serif text beats (pure).

    Each beat: ``{text, start, end, mode}`` where ``mode`` is ``"fade"`` (the
    whole line crossfades in/out) or ``"word"`` (words appear one at a time).
    White, soft shadow, centered horizontally at ~0.44 height.
    """
    fontfile = font.replace("\\", "/").replace(":", "\\:")
    common = (f"fontfile='{fontfile}':fontcolor=white:fontsize=64:"
              f"shadowcolor=black@0.6:shadowx=2:shadowy=3:x=(w-text_w)/2:y=h*0.44")
    parts: list[str] = []
    for b in beats:
        start = float(b.get("start", 0.0))
        end = float(b.get("end", start + 2.0))
        mode = b.get("mode", "fade")
        words = str(b.get("text", "")).split()
        if not words:
            continue
        if mode == "word":
            # Reveal cumulative word groups; each shows from its own time to end.
            n = len(words)
            step = max(0.18, (end - start) / max(1, n))
            for i in range(n):
                t0 = start + i * step
                txt = _esc(" ".join(words[: i + 1]))
                parts.append(f"drawtext={common}:text='{txt}':"
                             f"enable='between(t,{t0:.2f},{end:.2f})'")
        else:
            f = 0.4  # crossfade seconds
            txt = _esc(" ".join(words))
            alpha = (f"alpha='if(lt(t,{start:.2f}),0,"
                     f"if(lt(t,{start + f:.2f}),(t-{start:.2f})/{f},"
                     f"if(lt(t,{end - f:.2f}),1,"
                     f"if(lt(t,{end:.2f}),({end:.2f}-t)/{f},0))))'")
            parts.append(f"drawtext={common}:text='{txt}':{alpha}:"
                         f"enable='between(t,{start:.2f},{end:.2f})'")
    return ",".join(parts)


def serif_beats(src: str, out: str, beats: list[dict]) -> str:
    """Burn timed serif text beats onto ``src`` (talking clips skip this)."""
    flt = build_serif_filter(beats)
    vf = flt if flt else "null"
    subprocess.run(["ffmpeg", "-y", "-i", src, "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "copy", "-movflags", "+faststart", out],
                   check=True, capture_output=True)
    return out


# ---- logo watermark (top-right, whole clip) --------------------------------
def logo_path() -> str | None:
    p = os.path.join(ROOT, "content", "brand", "hp-logo.png")
    return p if os.path.exists(p) else None


def add_logo(src: str, out: str, logo: str | None = None, *, width: int = 130,
             margin: int = 30) -> str:
    """Overlay the brand logo top-right for the whole clip. No logo -> copy."""
    logo = logo or logo_path()
    if not logo:
        import shutil
        shutil.copy(src, out)
        return out
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-i", logo, "-filter_complex",
         f"[1:v]scale={width}:-1[lg];[0:v][lg]overlay=W-w-{margin}:{margin}[v]",
         "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", out],
        check=True, capture_output=True)
    return out


# ---- outro end-card append (crossfade) -------------------------------------
def outro_path() -> str | None:
    p = os.path.join(ROOT, "content", "brand", "outro.mp4")
    return p if os.path.exists(p) else None


def _probe_dur(path: str) -> float:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "default=nw=1:nk=1", path],
                           capture_output=True, text=True, check=True)
        return max(0.1, float(r.stdout.strip()))
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0.1


def _has_audio(path: str) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=index", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    return bool((r.stdout or "").strip())


def append_outro(src: str, out: str, outro: str | None = None,
                 xfade: float = 0.5) -> str:
    """Crossfade the outro end-card onto ``src`` (two-pass, robust).

    Pass 1 normalizes ``src`` to 1080x1920/30fps with a guaranteed stereo audio
    track (silence if the montage was silent) so pass 2 can audio-crossfade the
    outro's slam audio onto the end. No outro -> copy."""
    import tempfile  # lazy, stdlib
    outro = outro or outro_path()
    if not outro:
        import shutil
        shutil.copy(src, out)
        return out
    norm_vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
               f"crop={W}:{H},fps=30,format=yuv420p,setsar=1")
    with tempfile.TemporaryDirectory() as td:
        norm = os.path.join(td, "norm.mp4")
        cmd = ["ffmpeg", "-y", "-i", src]
        silent = not _has_audio(src)
        if silent:
            cmd += ["-f", "lavfi", "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000"]
        cmd += ["-vf", norm_vf, "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "19", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
        # -shortest ALWAYS: some source clips have a video track that ends before
        # their audio (phone/screen recordings). Without this the norm clip keeps
        # audio the video can't cover, the tail freezes, and the xfade below fails
        # (outro silently skipped, leaving a frozen frame + trailing audio). Clamp
        # to the shorter stream so video and audio match and the outro splices.
        cmd += ["-shortest"]
        if silent:
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
        cmd += [norm]
        subprocess.run(cmd, check=True, capture_output=True)

        off = max(0.0, _probe_dur(norm) - xfade)
        # settb=AVTB unifies timebases so xfade doesn't reject mismatched inputs.
        fc = (f"[0:v]fps=30,settb=AVTB,setsar=1[v0];"
              f"[1:v]{norm_vf},settb=AVTB[o];"
              f"[v0][o]xfade=transition=fade:duration={xfade}:offset={off:.3f}[v];"
              f"[0:a][1:a]acrossfade=d={xfade}[a]")
        subprocess.run(
            ["ffmpeg", "-y", "-i", norm, "-i", outro, "-filter_complex", fc,
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "19", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out],
            check=True, capture_output=True)
    return out

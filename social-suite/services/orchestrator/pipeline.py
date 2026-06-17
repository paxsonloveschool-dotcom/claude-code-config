"""Pipeline orchestration: ingest -> clip -> caption -> write -> publish.

Chains the stages into one automated run:

    ingest.list_new_files -> ingest.download -> clip.clip
        -> (per clip) caption.transcribe -> caption.burn_captions
        -> write.generate_caption -> publish.schedule_post

``run_pipeline(dry_run=True)`` (the default) runs the SAME control flow but with
every external stage swapped for an in-memory fake, so the whole chain is
exercisable with no Dropbox, no ffmpeg, no whisper, no Claude, and no Postiz. It
returns a structured per-stage summary (counts) either way.

TODO(impl): move the in-line per-file loop onto a queue (Redis/RQ) so ingest
enqueues per-file jobs and a worker runs the rest; persist a cursor +
processed-set; add retries/backoff and structured logging per stage.
"""

from __future__ import annotations

import os

from services.caption import burn_captions, transcribe
from services.clip import clip
from services.ingest import download, list_new_files
from services.publish import schedule_post
from services.write import generate_caption


def _compose_caption(copy) -> str:
    """Compose the final caption string (hook + body + hashtags)."""
    return f"{copy.hook}\n\n{copy.caption}\n\n" + " ".join(copy.hashtags)


def _dry_run_stages() -> dict:
    """In-memory fakes for every stage so the chain runs with no externals.

    Returns a name->callable map mirroring the real stage signatures. Yields one
    fake file -> two fake clips -> each fully captioned, written, and "scheduled"
    — enough to assert the chaining end-to-end.
    """
    from dataclasses import dataclass

    from services.caption.transcribe import Segment
    from services.clip import Clip
    from services.publish import ScheduledPost
    from services.write import GeneratedCopy

    @dataclass
    class _FakeFile:
        name: str

    def _list_new_files(*_a, **_k):
        return ([_FakeFile("raw_demo.mp4")], "cursor-1")

    def _download(file, *_a, **_k):
        return f"/tmp/{file.name}"

    def _clip(raw_path, *_a, **_k):
        return [
            Clip(
                source_path=raw_path,
                output_path=f"/tmp/clip{i}.mp4",
                start_seconds=float(i * 30),
                end_seconds=float(i * 30 + 25),
                title=f"clip {i}",
            )
            for i in (1, 2)
        ]

    def _transcribe(path, *_a, **_k):
        return [Segment(text="hello world", start_seconds=0.0, end_seconds=2.0)]

    def _burn_captions(path, segments, *_a, **_k):
        return path.replace(".mp4", "_captioned.mp4")

    def _generate_caption(context, *_a, **_k):
        return GeneratedCopy(
            hook="Watch this",
            caption="A demo clip.",
            hashtags=["#demo", "#shorts"],
        )

    def _schedule_post(clip_path, caption, *_a, **_k):
        return ScheduledPost(
            post_id="dryrun",
            channels=["chan_demo"],
            status="dry-run",
        )

    return {
        "list_new_files": _list_new_files,
        "download": _download,
        "clip": _clip,
        "transcribe": _transcribe,
        "burn_captions": _burn_captions,
        "generate_caption": _generate_caption,
        "schedule_post": _schedule_post,
    }


def _execute(
    *,
    list_new_files,
    download,
    clip,
    transcribe,
    burn_captions,
    generate_caption,
    schedule_post,
    dry_run: bool,
) -> dict:
    """Run the chain with the given (real or fake) stage callables.

    Returns a structured summary with per-stage counts.
    """
    counts = {
        "files": 0,
        "clips": 0,
        "captioned": 0,
        "written": 0,
        "scheduled": 0,
    }

    new_files, _cursor = list_new_files()
    counts["files"] = len(new_files)

    for f in new_files:
        raw_path = download(f)
        for c in clip(raw_path):
            counts["clips"] += 1
            segments = transcribe(c.output_path)
            captioned = burn_captions(c.output_path, segments)
            counts["captioned"] += 1
            copy = generate_caption({"title": c.title, "clip": c.output_path})
            counts["written"] += 1
            caption_text = _compose_caption(copy)
            schedule_post(captioned, caption_text)
            counts["scheduled"] += 1

    return {
        "status": "ok",
        "dry_run": dry_run,
        "stages": ["ingest", "clip", "caption", "write", "publish"],
        "counts": counts,
        "processed": counts["scheduled"],
        "published": counts["scheduled"],
    }


def run_pipeline(dry_run: bool = True) -> dict:
    """Run one full pass of the content pipeline.

    Args:
        dry_run: When True (default), run the full chain with every stage
            replaced by an in-memory fake — no external services touched. When
            False, call the real stage functions.

    Returns:
        A structured summary: ``status``, ``dry_run``, ``stages``, per-stage
        ``counts``, and ``processed`` / ``published`` totals.
    """
    if dry_run:
        return _execute(dry_run=True, **_dry_run_stages())

    _poll_folder = os.getenv("DROPBOX_WATCH_FOLDER", "/raw-video")  # noqa: F841
    return _execute(
        list_new_files=list_new_files,
        download=download,
        clip=clip,
        transcribe=transcribe,
        burn_captions=burn_captions,
        generate_caption=generate_caption,
        schedule_post=schedule_post,
        dry_run=False,
    )


if __name__ == "__main__":
    # Placeholder worker entrypoint (see docker-compose `worker` service).
    # A real worker would consume jobs from the queue instead of one dry run.
    print(run_pipeline(dry_run=True))

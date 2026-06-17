"""Pipeline orchestration: ingest -> clip -> caption -> write -> publish.

Chains the stages into one automated run. This skeleton lays out the control
flow with clear TODOs; the stage functions it calls are themselves stubs.

TODO(impl): make this real once the stages are implemented.
    - Replace the in-line loop with a queue (Redis/RQ): ingest enqueues per-file
      jobs; a worker runs the rest. See docker-compose `worker` service.
    - Persist a cursor (ingest) and a processed-set so files aren't redone.
    - Add retries/backoff and structured logging per stage.
    - Schedule it (POLL_INTERVAL_SECONDS) or trigger via the API `/run`.
"""

from __future__ import annotations

import os

from services.caption import burn_captions, transcribe
from services.clip import clip
from services.ingest import download, list_new_files
from services.publish import schedule_post
from services.write import generate_caption


def run_pipeline(dry_run: bool = True) -> dict:
    """Run one full pass of the content pipeline.

    Args:
        dry_run: When True (default for the skeleton), do not execute the stage
            stubs (which raise NotImplementedError); just report intent. Set
            False once the stages are implemented.

    Returns:
        A summary dict describing what ran (mock data in skeleton mode).

    TODO(impl): when dry_run is False, execute the chain below for real.
    """
    if dry_run:
        return {
            "status": "ok",
            "dry_run": True,
            "stages": ["ingest", "clip", "caption", "write", "publish"],
            "processed": 0,
            "note": "Skeleton: stage stubs not executed. See pipeline.py TODOs.",
        }

    # --- Real chain (each call is currently a NotImplementedError stub) -------
    poll_folder = os.getenv("DROPBOX_WATCH_FOLDER", "/raw-video")  # noqa: F841
    new_files, _cursor = list_new_files()
    published = 0
    for f in new_files:
        raw_path = download(f)
        for c in clip(raw_path):
            segments = transcribe(c.output_path)
            captioned = burn_captions(c.output_path, segments)
            copy = generate_caption({"title": c.title, "clip": c.output_path})
            caption_text = f"{copy.hook}\n\n{copy.caption}\n\n" + " ".join(
                copy.hashtags
            )
            schedule_post(captioned, caption_text)
            published += 1
    return {"status": "ok", "dry_run": False, "published": published}


if __name__ == "__main__":
    # Placeholder worker entrypoint (see docker-compose `worker` service).
    # A real worker would consume jobs from the queue instead of one dry run.
    print(run_pipeline(dry_run=True))

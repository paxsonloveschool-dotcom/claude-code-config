"""FastAPI surface for the orchestrator.

Endpoints:
    GET  /health  -> liveness probe.
    POST /run     -> trigger one pipeline pass (returns its summary).

Run with: uvicorn services.orchestrator.api:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from .pipeline import run_pipeline

app = FastAPI(title="Social Suite Orchestrator", version="0.1.0")


class RunRequest(BaseModel):
    """Body for POST /run.

    Attributes:
        dry_run: If True, don't execute stage stubs — report intent only.
            Defaults True while stages are unimplemented.
    """

    dry_run: bool = True


@app.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/run")
def run(req: RunRequest | None = None) -> dict:
    """Trigger one pipeline pass.

    TODO(impl): for long runs, enqueue a job and return 202 + a job id instead
    of running synchronously.
    """
    dry_run = True if req is None else req.dry_run
    return run_pipeline(dry_run=dry_run)

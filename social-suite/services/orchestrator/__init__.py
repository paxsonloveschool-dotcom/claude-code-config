"""Orchestrator: ties every stage together and exposes an HTTP trigger."""

from .pipeline import run_pipeline

__all__ = ["run_pipeline"]

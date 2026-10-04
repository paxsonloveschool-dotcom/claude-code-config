"""modal_deploy.py — template for deploying a WAT workflow to Modal.

Fill in the placeholders marked <FIXME>. Delete either the cron OR the
webhook example depending on which you need — don't ship both unless
this workflow legitimately has both entrypoints.

Deploy:
    modal deploy modal_deploy.py

Trigger cron manually (for testing):
    modal run modal_deploy.py::run_scheduled

Tail logs:
    modal app logs <FIXME-app-name>
"""
from __future__ import annotations
import sys
from pathlib import Path

import modal

# --- App identity ---
APP_NAME = "<FIXME-app-name>"   # kebab-case, e.g. "hp-landscaping-morning-digest"

# --- Image: install deps from requirements.txt; mount code ---
REPO_ROOT = Path(__file__).parent
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements(str(REPO_ROOT / "requirements.txt"))
    # Add apt packages here if a tool needs them:
    # .apt_install("ffmpeg")
)

app = modal.App(name=APP_NAME, image=image)

# --- Secrets: created via `modal secret create <APP_NAME>-secrets --from-dotenv .env` ---
secrets = [modal.Secret.from_name(f"{APP_NAME}-secrets")]

# --- Mount the tools/ and workflows/ dirs into the container ---
mounts = [
    modal.Mount.from_local_dir(str(REPO_ROOT / "tools"), remote_path="/root/tools"),
    modal.Mount.from_local_dir(str(REPO_ROOT / "workflows"), remote_path="/root/workflows"),
]


def _bootstrap_path():
    """Make /root importable so `from tools.foo import bar` works."""
    if "/root" not in sys.path:
        sys.path.insert(0, "/root")


# =============================================================================
# EXAMPLE 1: Scheduled (cron) — every Monday 06:00 UTC
# Cron format: minute hour day-of-month month day-of-week (all in UTC).
# =============================================================================
@app.function(
    schedule=modal.Cron("0 6 * * MON"),
    secrets=secrets,
    mounts=mounts,
    timeout=60 * 15,          # 15 min max per run
    container_idle_timeout=60,  # tear down 60s after finishing (cost saver)
)
def run_scheduled():
    _bootstrap_path()
    from tools.example_tool import main   # <FIXME: import your orchestrator>
    result = main()
    print(f"scheduled run done: {result}")
    return result


# =============================================================================
# EXAMPLE 2: Webhook — POST endpoint with JSON payload
# After deploy, Modal prints the public URL. Test with:
#   curl -X POST -H "content-type: application/json" \
#        -d '{"key": "value"}' <printed-url>
# =============================================================================
@app.function(
    secrets=secrets,
    mounts=mounts,
    timeout=60 * 2,
)
@modal.web_endpoint(method="POST", label=f"{APP_NAME}-hook")
def run_webhook(payload: dict):
    _bootstrap_path()
    from tools.example_tool import main   # <FIXME: same or different orchestrator>
    # OPTIONAL: cap payload size to avoid surprise cost / DoS
    if len(str(payload)) > 100_000:
        return {"error": "payload too large"}, 413
    result = main(**payload)
    return {"ok": True, "result": result}


# =============================================================================
# LOCAL SMOKE TEST — `modal run modal_deploy.py::_local_test`
# Runs inside a Modal container so you validate the image, secrets, and
# mounts before pushing a real deploy.
# =============================================================================
@app.local_entrypoint()
def _local_test():
    print("Running scheduled entrypoint in a Modal container (dry-run)...")
    result = run_scheduled.remote()
    print(f"Result: {result}")

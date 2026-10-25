---
name: modal-deploy
description: >
  Deploy a WAT workflow to Modal for scheduled (cron) or webhook-triggered
  execution. Handles the security audit, secrets migration from .env to
  Modal Secrets, and the modal_deploy.py packaging.
  Use when the user says "deploy to Modal", "push this to Modal",
  "make this run on a schedule", "expose this as a webhook",
  "deploy the <name> workflow", or when a workflow proven locally needs
  to become a serverless cron/HTTP endpoint.
  Triggers: "deploy to modal", "modal deploy", "push to modal",
  "run on schedule", "expose as webhook", "cron this workflow",
  "serverless deploy".
---

# modal-deploy — Ship a workflow to Modal

## Prerequisites (verify BEFORE writing any deploy code)

1. **Modal account + CLI**:
   ```bash
   pip install modal
   modal token new        # opens browser to auth
   modal token current    # confirm authed
   ```
2. **Workflow works locally.** If it doesn't, fix that first — don't
   debug remote runs when local is broken.
3. **All secrets in `.env`**, none hardcoded (see step 1 of the
   security audit below).
4. **`requirements.txt` complete** — every import in `tools/` is listed.

## Step 1 — Security audit (MANDATORY, non-skippable)

Never deploy without this. Prompt to run:

```
Run the security review on this codebase before deploy. Check:

1. Grep tools/ and workflows/ for hardcoded secrets:
   - API keys (sk-*, xoxb-*, ghp_*, AKIA*, AIza*, key-*, tok-*)
   - Passwords in URLs (://user:pass@)
   - AWS access keys, GCP service-account JSON blobs
   - JWT tokens, bearer tokens
2. Verify .env is in .gitignore and NOT tracked (git ls-files | grep env).
3. Verify .env.example is committed and lists every var the code reads.
4. Grep for `print(<secret_var>)` / `logging.*<secret_var>` — never
   log secrets even in DEBUG.
5. Check tool subprocess.run calls for shell=True on user-controlled
   input (command injection risk).
6. Check any URL fetches use https:// and validate hostnames if
   user-controlled.

Report findings in a table. HALT the deploy if any HIGH-severity finding.
```

Use the built-in **`security-review`** skill for this — it's more
thorough than an ad-hoc grep.

## Step 2 — Generate modal_deploy.py

Start from `references/modal_deploy_template.py`. Customize for the
workflow being deployed:

- App name = `<repo-name>-<workflow-name>` (kebab-case, lowercase).
- Image: `modal.Image.debian_slim().pip_install_from_requirements("requirements.txt")`.
- Mount `tools/` and `workflows/<name>.md` into the container.
- Function entrypoint = the tool orchestrator (usually a
  `workflows/<name>_runner.py` if one exists, else the tool sequence
  inline).

## Step 3 — Migrate secrets

For every var in `.env`:

```bash
modal secret create <APP>-secrets ENV_VAR=value ENV_VAR2=value2
```

Or batch from .env:
```bash
modal secret create <APP>-secrets --from-dotenv .env
```

Reference the secret in the function:
```python
@app.function(secrets=[modal.Secret.from_name("<APP>-secrets")])
def run(): ...
```

Never `--from-dotenv` a file that hasn't been through the security
audit — you'll ship secrets you didn't mean to.

## Step 4 — Deploy

**Scheduled (cron)**:
```python
@app.function(schedule=modal.Cron("0 6 * * MON"))  # every Mon 6am UTC
def run_weekly():
    from tools.some_tool import main
    main()
```
Deploy:
```bash
modal deploy modal_deploy.py
```

**Webhook**:
```python
@app.function()
@modal.web_endpoint(method="POST")
def hook(payload: dict):
    from tools.some_tool import main
    return main(**payload)
```
After deploy, Modal prints the URL. Test with:
```bash
curl -X POST -H "content-type: application/json" \
     -d '{"foo": "bar"}' <printed-url>
```

## Step 5 — Verify

```bash
modal app list                 # see the deployed app
modal app logs <app-name>      # tail logs
modal app stats <app-name>     # invocation count / cost
```

For cron: Modal shows `next_run_at`. Wait for it or trigger a manual
run:
```bash
modal run modal_deploy.py::run_weekly
```

## Cost gotchas

- Each container cold-starts. Cron every-minute + heavy imports = $$.
  Batch or set `@app.function(container_idle_timeout=300)` to keep warm.
- Webhook with unbounded request size = surprise bill. Add payload
  size caps in the function body.
- Modal charges CPU-seconds and memory-seconds. `modal.Image.debian_slim()`
  is smaller than the default — use it unless you need CUDA.

## Rollback

Modal keeps history — redeploy the previous commit to roll back:
```bash
git checkout <old-sha> -- modal_deploy.py
modal deploy modal_deploy.py
```
Or stop the app:
```bash
modal app stop <app-name>
```

## When NOT to use Modal

- Long-running (>1h) processes → use a proper VM/Fly.io/Railway.
- GPU workloads with sub-second latency needs → Modal has GPUs but
  cold starts hurt.
- Local dev tools nobody else needs to run.

## Complementary skills

- **wat-init** — the source project structure this expects.
- **security-review** (built-in) — the audit gate.
- **session-handoff** — the deploy flow is verbose; handoff after
  audit if context is getting large.

Source: Nate Herk, "Master 95% of Claude Code in 36 Mins" +
Modal docs at https://modal.com/docs/

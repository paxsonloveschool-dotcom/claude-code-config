# Free, no-card, no-always-on-computer posting

This is the "robot that posts for you while your Mac is off and your wallet is
closed." It uses **GitHub Actions** (free compute on GitHub's servers) as a cron
job that fires your finished posts straight at the Instagram + Facebook APIs.

## The pieces (in plain terms)

- **GitHub Actions = the free always-on robot.** A workflow
  (`.github/workflows/social-post.yml`) wakes up every 30 minutes on GitHub's
  servers. You don't run a server and your Mac doesn't need to be on.
- **The queue file = your outbox.** `content/queue.json` is a plain list of
  finished posts (text + media URL + which platforms + an optional time). You
  build content on the Mac, append entries, commit, and push.
- **Secrets = your keys, kept safe.** Your Meta tokens/ids live in GitHub
  repository **Secrets**, never in the code or the queue.
- **Media must be a PUBLIC URL.** Meta fetches your image/video server-side, so
  it must be reachable on the open internet. Easiest: commit the rendered clip
  into the repo and use its `raw.githubusercontent.com/...` URL, or use any
  public host (Dropbox direct link, S3, etc.). A localhost/private path fails.

## Scheduling: the catch

- **Facebook can pre-schedule server-side.** `post_facebook(...)` with a
  `scheduled_time` (unix ts) hands the post to Facebook with `published=false` +
  `scheduled_publish_time`; Facebook publishes it later on its own.
- **Instagram CANNOT pre-schedule via the API.** It posts immediately when
  called. So for IG, the *Action* does the scheduling: the cron runs every 30
  min, and a post with a `schedule` time goes out on the first run at/after that
  time. (Granularity = the cron interval, currently 30 min.)

## GitHub Secrets to set

Repo → Settings → Secrets and variables → Actions → **New repository secret**:

| Secret | What it is |
|---|---|
| `META_ACCESS_TOKEN` | Long-lived Meta token with `pages_manage_posts` + `instagram_content_publish`. Drives both FB and IG. |
| `IG_USER_ID` | Your Instagram **Professional** account user id (required for `instagram` posts). |
| `FB_PAGE_ID` | Your Facebook **Page** id (required for `facebook` posts). |

## The weekly flow

1. **Mac creates content** — clip → caption → AI copy (the rest of social-suite).
2. **Mac writes the queue** — append `QueuedPost` entries to `content/queue.json`
   (status `"pending"`, a public `media_url`, the target `platforms`, and an
   optional ISO-8601 UTC `schedule`). Commit + push.
3. **GitHub posts on cron** — every 30 min the Action runs
   `python social-suite/services/publish/run_due.py`, which:
   - loads the queue, finds **due** posts (pending AND schedule passed/empty),
   - posts each to its platforms using the secrets,
   - marks each `"sent"` or `"failed"` (with an `error`),
   - commits the updated `queue.json` back with a `[skip ci]` message.
4. You can watch results in the Action logs and in the queue file's statuses.

## Run it yourself

- **Dry run (no posting):** `python services/publish/run_due.py --dry-run`
- **Real run:** set the three env vars, then
  `python services/publish/run_due.py content/queue.json`
- **Manual trigger:** the workflow also has `workflow_dispatch` — hit "Run
  workflow" in the Actions tab.

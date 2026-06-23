# Full-Stack Deploy — go live on any host

One bundle that runs the **whole system**: the Postiz posting engine + the
social-suite pipeline, behind automatic HTTPS. Pick any Docker host (a $5 VPS,
Oracle Always Free, a home box) and these steps are identical.

## What runs
| Service | Role |
|---|---|
| caddy | Auto-HTTPS reverse proxy → Postiz (the public URL OAuth needs) |
| postiz (+ postgres, redis) | Posting engine, pinned v2.11.2 |
| suite-orchestrator | FastAPI API for the pipeline (`/health`, `/run`) — localhost-only |
| suite-worker | Runs the Dropbox → clip → caption → write → publish pipeline |
| suite-redis | Job queue for the suite |

## Steps
1. **Point DNS:** an A record `social.yourdomain.com → <server IP>`.
2. **Install Docker** on the host: `curl -fsSL https://get.docker.com | sh`
3. **Get the code + configure:**
   ```bash
   git clone https://github.com/paxsonloveschool-dotcom/claude-code-config.git
   cd claude-code-config/social-suite/deploy
   cp .env.example .env
   nano .env        # set DOMAIN, JWT_SECRET, POSTGRES_PASSWORD; keys can wait
   #   echo "JWT_SECRET=$(openssl rand -hex 32)"
   #   echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
   ```
4. **Launch:**
   ```bash
   docker compose -f docker-compose.full.yml up -d
   ```
5. **Set up Postiz:** open `https://social.yourdomain.com`, register your admin
   account, and **connect your social channels** (this is where the platform
   developer-app credentials from `../PLATFORM_SETUP.md` go).
6. **Wire the suite to Postiz:** in Postiz → Settings → API key. Put it in `.env`
   as `POSTIZ_API_KEY`, set `POSTIZ_DEFAULT_CHANNELS` (from
   `GET /public/v1/integrations`), add your `ANTHROPIC_API_KEY` and `DROPBOX_*`,
   then `docker compose -f docker-compose.full.yml up -d` again.
7. **Run the pipeline:** drop a video in your Dropbox folder. To trigger manually,
   SSH-tunnel to the API and POST `/run`:
   ```bash
   ssh -L 8000:127.0.0.1:8000 user@server   # then, locally:
   curl -X POST http://localhost:8000/run
   ```

## Notes
- The suite API is bound to **127.0.0.1** on the host (not public) — reach it via
  SSH tunnel. Only Postiz (via Caddy) is exposed publicly.
- ARM host (e.g. Oracle A1)? Postiz v2.11.2 is amd64; it runs under emulation, or
  swap to BrightBean (see `../RESEARCH.md`). The suite itself is arch-agnostic.
- After registering your Postiz admin, set `DISABLE_REGISTRATION=true` in `.env`
  and re-run `up -d` to lock signups.
- Day-2: `docker compose -f docker-compose.full.yml logs -f suite-worker` to watch
  the pipeline; `... pull && ... up -d` to update.

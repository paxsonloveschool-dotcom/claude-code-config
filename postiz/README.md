# Postiz — Self-Hosted Social Media Scheduler

One-command, HTTPS-ready deployment of [Postiz](https://github.com/gitroomhq/postiz-app)
for scheduling + AI-assisted content across X, Instagram, Facebook, LinkedIn,
TikTok, YouTube, Pinterest, Threads, Bluesky, Mastodon, and more.

This setup runs 4 containers: **Postiz**, **Postgres**, **Redis**, and **Caddy**
(which auto-provisions a free Let's Encrypt HTTPS certificate).

---

## What you need first

1. **A cheap Linux VPS** — Hetzner (~$5/mo), DigitalOcean, Vultr, etc.
   2 GB RAM minimum, Ubuntu 22.04/24.04. Note its public IP.
2. **A domain or subdomain** you control (e.g. `social.hplandscaping.com`).
3. **Docker** installed on the VPS (see step 1 below if not).

---

## Deploy in 6 steps

### 1. Install Docker on the VPS (skip if already installed)
```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Point your domain at the server
In your DNS provider, add an **A record**:
`social.yourdomain.com  →  <your VPS public IP>`
Wait a few minutes for it to propagate (test: `ping social.yourdomain.com`).

### 3. Get these files onto the server
```bash
git clone https://github.com/paxsonloveschool-dotcom/claude-code-config.git
cd claude-code-config/postiz
```

### 4. Create your .env
```bash
cp .env.example .env
nano .env        # fill in DOMAIN, JWT_SECRET, POSTGRES_PASSWORD
```
Generate the secrets quickly:
```bash
echo "JWT_SECRET=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
```

### 5. Launch
```bash
docker compose up -d
```
First boot pulls images + runs DB migrations — give it 2–3 minutes.
Watch progress with: `docker compose logs -f postiz`

### 6. Create your account
Open `https://social.yourdomain.com` → register the first user (that's you).
Then **lock signups**: set `DISABLE_REGISTRATION=true` in `.env` and run
`docker compose up -d` again.

---

## Connecting Instagram + Facebook (the Meta part)

Posting to IG/FB requires a Meta Developer App with publishing permissions.
High-level path (Postiz docs have exact screens):

1. Convert your Instagram to a **Business or Creator** account (free, in the app).
2. Link it to a **Facebook Page**.
3. At [developers.facebook.com](https://developers.facebook.com) create an app,
   add the **Instagram** + **Facebook Login** products.
4. Set the OAuth redirect URL to your Postiz callback
   (`https://social.yourdomain.com/...` — Postiz shows the exact URL when you
   click "Add channel → Instagram").
5. Submit for **App Review** to unlock live posting beyond your own test users.
   This is the one step that takes a few days of Meta back-and-forth.

> X, LinkedIn, Bluesky, Mastodon, Telegram, etc. are much simpler — most just
> need an app key/secret or a direct OAuth login, no review.

Each platform's API keys go into Postiz via the UI (Settings → channels) or as
extra environment variables — see https://docs.postiz.com.

---

## Day-2 operations

| Task | Command (run inside `postiz/`) |
|---|---|
| View logs | `docker compose logs -f postiz` |
| Restart | `docker compose restart` |
| Update to latest Postiz | `docker compose pull && docker compose up -d` |
| Stop | `docker compose down` |
| Stop + wipe ALL data | `docker compose down -v` ⚠️ deletes posts/accounts |
| Back up the database | `docker exec postiz-postgres pg_dump -U postiz-user postiz-db-local > backup.sql` |

---

## Notes / gotchas
- **Instagram API limits:** single images, carousels, and feed videos post fine.
  Stories and some Reels features are restricted by Meta's API for all tools.
- **Local media storage:** uploads live in the `postiz-uploads` Docker volume.
  For scale you can switch `STORAGE_PROVIDER` to Cloudflare R2 / S3 later.
- **AI features** (caption generation) need an OpenAI key — add
  `OPENAI_API_KEY` to the `postiz` service environment in `docker-compose.yml`.
- Full configuration reference: https://docs.postiz.com

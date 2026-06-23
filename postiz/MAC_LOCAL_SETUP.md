# Run Postiz on your Mac — 100% free, no card

Postiz running right on your own Mac. No cloud, no credit card, ever. Your Mac
just needs to be **on and awake** when a scheduled post is set to go out.

---

## Stage 1 — Get it running (about 15 min, mostly waiting on downloads)

### Step 1 — Install Docker Desktop (free)
Docker is the engine that runs Postiz. It's free for personal use and small
businesses.
1. Go to **docker.com/products/docker-desktop**
2. Download **Docker Desktop for Mac** — pick **Apple Silicon** (M1/M2/M3 Macs,
   most Macs since 2020) or **Intel** if you have an older Mac.
   *(Not sure? Apple menu  → About This Mac → if it says "Apple M…" it's Apple Silicon.)*
3. Open the downloaded file, drag Docker to Applications, launch it, accept the
   defaults. When the whale icon 🐳 sits steady in your top menu bar, it's ready.

### Step 2 — Download the Postiz files
1. Open the **Terminal** app (Spotlight → type "Terminal" → Enter)
2. Paste this and press Enter:
   ```bash
   git clone https://github.com/paxsonloveschool-dotcom/claude-code-config.git ~/postiz-setup
   cd ~/postiz-setup/postiz
   ```
   *(If it says `git: command not found`, a popup offers to install developer
   tools — click Install, wait, then run the two lines again.)*

### Step 3 — Start Postiz
Paste this and press Enter:
```bash
docker compose -f docker-compose.local.yml up -d
```
First time, it downloads Postiz (~2–4 min). Watch it get ready with:
```bash
docker compose -f docker-compose.local.yml logs -f postiz
```
When you see it's listening / ready, press **Ctrl+C** to stop watching (that
only stops the log view, not Postiz).

### Step 4 — Open it
Go to **http://localhost:5000** in your browser. Register the first account —
that's your admin login. 🎉 Postiz is now running on your Mac.

---

## Stage 2 — Connect your social accounts

Some platforms need a public web address to connect (a local `localhost`
address won't work for them). The free fix is a **Cloudflare Tunnel** — it
gives your local Postiz a temporary public `https://…` address. No card.

1. Install the tunnel tool (free):
   ```bash
   brew install cloudflared
   ```
   *(No Homebrew? Install it first from **brew.sh**, then run the line above.)*
2. Point it at Postiz:
   ```bash
   cloudflared tunnel --url http://localhost:5000
   ```
   It prints a `https://something.trycloudflare.com` address. Use **that**
   address (instead of localhost) to open Postiz while connecting accounts.
3. In Postiz → **Add Channel** → pick a platform → log in & approve.
   - **Easy/instant:** X (Twitter), LinkedIn, Bluesky, Mastodon, Telegram
   - **Instagram/Facebook:** also need a free Instagram **Business/Creator**
     account linked to a Facebook Page, plus Meta's one-time app review.

> Tip: the free tunnel address changes each time you restart it. That's fine for
> trying things. If you want a permanent address later, that's the point where a
> always-on setup (home server or cloud) makes sense.

---

## Everyday commands (run from `~/postiz-setup/postiz`)
| Do this | Command |
|---|---|
| Start | `docker compose -f docker-compose.local.yml up -d` |
| Stop | `docker compose -f docker-compose.local.yml down` |
| See logs | `docker compose -f docker-compose.local.yml logs -f postiz` |
| Update | `docker compose -f docker-compose.local.yml pull && docker compose -f docker-compose.local.yml up -d` |

## Loading your ready-made posts
The 40 captions I wrote are in `automation/content/`. Once your accounts are
connected, see `automation/README.md` to bulk-schedule them.

## Reality check
- **Free, no card:** yes, completely.
- **Catch:** your Mac must be **awake** at a post's scheduled time. For "set it
  and forget it" 24/7 posting, an always-on machine (old laptop left on, or a
  cloud server) is better — but for getting started, your Mac is perfect.

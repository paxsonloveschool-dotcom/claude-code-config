# Postiz — Go-Live Runbook

Every step, in order, from zero to posts going out automatically. Check each
box as you go. Plan on ~30–45 min of active work, plus a few days waiting on
Meta's review (only if you want Instagram/Facebook).

---

## Stage 0 — What you need
- [ ] A credit/debit card (Oracle ID check only — Always Free is never charged)
- [ ] A Google or GitHub login (for DuckDNS)
- [ ] The social accounts you want to post to

---

## Stage 1 — Free server (≈10 min)
Full clicks: [`ORACLE_FREE_SETUP.md`](./ORACLE_FREE_SETUP.md).
- [ ] Sign up at oracle.com/cloud/free, pick a home region
- [ ] **DuckDNS** (duckdns.org): create a subdomain + copy your token
- [ ] Create instance → Ubuntu 24.04 → shape **VM.Standard.A1.Flex (4 OCPU / 24 GB)**
      *(if "out of capacity", use E2.1.Micro as fallback)*
- [ ] Expand **Show advanced options → Management → User data**, paste
      [`cloud-init.yaml`](./cloud-init.yaml) with your `DUCK_SUB` + `DUCK_TOKEN` filled in
- [ ] Create the instance, copy its **public IP**
- [ ] In the VCN **Security List**, add ingress rules for **TCP 80 and 443** (`0.0.0.0/0`)

> No cloud-init? SSH in and run `./setup.sh` instead (Option B in the Oracle guide).

---

## Stage 2 — First login (≈5 min, after server finishes building ~3–5 min)
- [ ] Open `https://YOUR_SUBDOMAIN.duckdns.org` (wait ~60s for the HTTPS cert)
- [ ] Register the first account — **this is your admin**
- [ ] Lock signups: SSH in → `cd claude-code-config/postiz` →
      `sed -i 's/DISABLE_REGISTRATION=false/DISABLE_REGISTRATION=true/' .env && docker compose up -d`

---

## Stage 3 — Connect social accounts
Easy ones first (no review needed): **X, LinkedIn, Bluesky, Mastodon, Telegram, Threads**.
- [ ] In Postiz → **Add Channel** → pick a platform → log in / approve

**Instagram + Facebook (the slow path):**
- [ ] Convert Instagram to a **Business/Creator** account, link it to a **Facebook Page**
- [ ] At developers.facebook.com create an app, add **Instagram** + **Facebook Login**
- [ ] Set the OAuth redirect URL Postiz shows you, then submit for **App Review**
- [ ] Once approved, connect IG/FB in Postiz like the others

---

## Stage 4 — Wire up content automation (≈10 min)
From `postiz/automation/` (see [`automation/README.md`](./automation/README.md)).
- [ ] In Postiz → **Settings → Public API** → generate an **API key**
- [ ] Find your channel ids:
      `curl -H "Authorization: $POSTIZ_API_KEY" "$POSTIZ_API_URL/public/v1/integrations"`
- [ ] Export env vars:
      `export POSTIZ_API_URL="https://YOUR_SUBDOMAIN.duckdns.org"` and `export POSTIZ_API_KEY="..."`
- [ ] **Dry-run** first: `make dry-run CONTENT=automation/content/hp-landscaping.json`

---

## Stage 5 — Schedule your first month
- [ ] Build a drip calendar (Mon/Wed/Fri 9am — adjust `--utc-offset` to your zone):
      ```
      python3 automation/plan_calendar.py automation/content/hp-landscaping.json \
        --days mon,wed,fri --time 09:00 --utc-offset -4 \
        --channels YOUR_CHANNEL_ID --out planned.json
      ```
- [ ] Send it: `python3 automation/schedule_posts.py planned.json`
- [ ] Confirm the posts appear on Postiz's calendar view

You now have content queued. Repeat with `restore.json` and the `-winter.json`
batches as the seasons change.

---

## Stage 6 — Hands-off going forward
- [ ] (Optional) Add repo secrets `POSTIZ_API_URL` + `POSTIZ_API_KEY` in GitHub,
      then trigger [`postiz-schedule.yml`](../.github/workflows/postiz-schedule.yml)
      from the **GitHub mobile app** anytime — schedule a batch with no laptop
- [ ] Set a monthly reminder to refill content + re-run the planner
- [ ] Back up occasionally: `make backup`

---

## If something breaks
| Symptom | Where to look |
|---|---|
| Site won't load | Both firewall layers (Oracle ingress + `setup.sh` ran) — Oracle guide |
| HTTPS error on first load | Wait 60s; check `ping YOUR_SUBDOMAIN.duckdns.org` resolves to your IP |
| Container restarts (1 GB shape) | Add swap — Oracle guide troubleshooting table |
| API post fails | `make dry-run` to inspect payload; check channel ids + API key |
| Logs | `make logs` |

---

## Content library on hand
| File | Use |
|---|---|
| `automation/content/hp-landscaping.json` | HP Landscaping — main season (10) |
| `automation/content/hp-landscaping-winter.json` | HP Landscaping — winter (10) |
| `automation/content/restore.json` | Restore — general (10) |
| `automation/content/restore-winter.json` | Restore — winter (10) |

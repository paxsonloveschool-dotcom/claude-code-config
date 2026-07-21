# HP Auto-Posting — Go-Live Runbook

**Goal:** HP posts to **Facebook + Instagram + TikTok** on a **Mon/Wed/Fri, 11:00 AM CT** schedule, with your chosen songs on IG + TikTok — without leaving a computer running 24/7.

This runbook is the single source of truth for turning it on. It supersedes the
cadence notes in the older per-platform docs (`IG_AUTOPOST_SETUP.md`,
`TIKTOK_BROWSER_AUTOPOST.md`) — those said noon; **we use 11:00 AM** now.

---

## How it actually runs (read this first)

| Platform | Where it runs | Machine on? | Songs |
|---|---|---|---|
| **Facebook** | ☁️ GitHub Actions (cloud) | **Never** — already live | Video's own audio |
| **TikTok** | 💻 This machine, **~weekly 10-min batch** | Only during that weekly run | ✅ Your chosen songs (TikTok's library) |
| **Instagram** | 💻 This machine, **Mon/Wed/Fri 11:00** | Wakes itself ~2 min, 3×/week | ✅ Your chosen songs (IG's library) |

**Why the machine at all?** TikTok and Instagram block cloud servers and require a
real logged-in session to attach their trending songs. That's the price of "the
songs I choose." But it does **not** mean "always on":

- **TikTok** uploads a whole week's batch to **TikTok's own scheduler** (up to 10
  days out), then TikTok publishes them. The machine is only needed for the weekly
  upload run.
- **Instagram** has *no* scheduler (it posts instantly), so the machine wakes for
  ~2 minutes each Mon/Wed/Fri at 11:00, posts one Reel, and sleeps again.

The installer sets up **scheduled wake**, so the machine can sleep the rest of the
time. Requirement: it's **plugged in and asleep (not fully shut down)** at those
times, with Dropbox synced.

---

## Facebook — already done ✅

Nothing to do. The cloud job (`.github/workflows/fb-autopost.yml`) posts HP's next
numbered Dropbox clip every Mon/Wed/Fri at 11:00 CT. Verify anytime: GitHub →
Actions → "Facebook auto-post". *(Token note: the stored `BRAND_HP_META_ACCESS_TOKEN`
is a non-expiring Page token, so it won't silently die.)*

---

## One-time setup (tomorrow, ~20 min)

### 0. Prereqs
- This repo cloned locally, Python 3.10+ installed.
- **TikTok** also needs **Node.js** installed.
- Dropbox desktop app installed and syncing HP's clip folder.

### 1. Fill in the machine config
```bash
# macOS / Linux
cd social-suite/deploy/local-timers
cp config.example.env config.env
# edit config.env — set SOCIAL_SUITE_DIR, PYTHON, IG_FOLDER, IG_CREDS
```
```bat
REM Windows
cd social-suite\deploy\local-timers\windows
copy config.env.bat.example config.env.bat
notepad config.env.bat
move config.env.bat ..\config.env.bat
```

### 2. Instagram — log in once, then test
```bash
pip install instagrapi
# create the login file (path = IG_CREDS from your config):
#   {"username":"HP_IG_USERNAME","password":"HP_IG_PASSWORD"}
```
Test one Reel by hand (posts immediately — do it when you're OK with a live post):
```bash
cd social-suite
IG_FOLDER="...","IG_CREDS="..." python automation/ig_autopost.py   # (mac/linux)
```
If the song attaches → you're set. If IG blocks the track, that's the
Business-account music limit — switch that song for a cleared one (edit the
`SONGS` list in `automation/ig_autopost.py`).

### 3. TikTok — install, log in once, then test
```bash
cd social-suite
pip install tiktokautouploader
phantomwright_driver install chromium
```
Approve a clip to test: in `content/queue.json` set one item's `status` to
`"pending"`, ensure `platforms` includes `"tiktok"`, give it a `"sound"`. Then:
```bash
python automation/tiktok_browser_post.py --brand hp --dry-run   # preview
python automation/tiktok_browser_post.py --brand hp             # real (opens browser to log in the 1st time)
```
The first real run opens a browser — log into HP's TikTok, clear any captcha; it
saves `Tk_cookies_hp.json` and reuses it after that.

### 4. Turn on the timers
```bash
# macOS
cd social-suite/deploy/local-timers/mac
bash install.sh          # loads launchd timers + schedules wake (asks for your password)
```
```powershell
# Windows (PowerShell)
cd social-suite\deploy\local-timers\windows
powershell -ExecutionPolicy Bypass -File .\Install-HPTimers.ps1
```

### 5. Verify
- **macOS:** `pmset -g sched` shows the wake schedule; logs in `../logs/`.
- **Windows:** `Get-ScheduledTask -TaskName 'HP-*'`; test with
  `Start-ScheduledTask -TaskName 'HP-Instagram-AutoPost'`.

---

## Everyday use
- **TikTok (weekly):** approve the clips you want out — flip each one's `status`
  from `"review"` → `"pending"` in `content/queue.json` (keep `"tiktok"` in
  `platforms`). The Monday run picks them up automatically. There are currently
  **9 HP clips sitting at `status:"review"`** — none will post to TikTok until you
  approve them.
- **Instagram** just grabs the next new clip from your Dropbox `IG_FOLDER` — no
  approval step.
- **Facebook** is fully automatic off the numbered Dropbox clips.

## Change songs / cadence
- **TikTok songs:** `content/tiktok_songs_hp.txt` (one `Artist - Title` per line).
- **Instagram songs:** the `SONGS` list in `automation/ig_autopost.py`.
- **Cadence:** Facebook + TikTok are set in `POST_WEEKDAYS` / `POST_HOUR` at the top
  of their scripts (Mon/Wed/Fri 11:00). Instagram's cadence is the timer itself —
  edit the schedule in `mac/install.sh` or re-run the Windows installer.

## Uninstall
- **macOS:** `bash mac/uninstall.sh`   • **Windows:** `Uninstall-HPTimers.ps1`

## ⚠️ Honest risk note
IG (`instagrapi`) and TikTok (browser robot) automate against those platforms'
Terms. Real accounts *can* be flagged/limited. Keep volume human (3×/week is fine),
test one post per platform first, and don't be shocked if a mainstream song is
occasionally refused (that's the platform's copyright wall, not a bug).

## TikTok's *official* API (separate, still pending)
There's also an official TikTok API path in this repo that was submitted for
TikTok's app audit on 2026-06-29 (`TIKTOK_SETUP_PROGRESS.md`). It's **not needed**
for the browser robot above. If/when TikTok approves it, that unlocks a cloud
(no-machine) TikTok path — revisit then.

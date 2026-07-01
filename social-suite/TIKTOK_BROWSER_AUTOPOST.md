# Fully-automatic TikTok posting with a real song (no phone, free)

This is the "browser robot" path. It auto-uploads your approved videos, writes
the caption + hashtags, **attaches a TikTok sound you name** (e.g. a country
song), and **schedules** each post with TikTok's own scheduler — no device, no
emulator, no official API. It runs on your **laptop**.

It's a thin wrapper (`automation/tiktok_browser_post.py`) around the open-source
[`tiktokautouploader`](https://github.com/haziq-exe/TikTokAutoUploader) package,
fed by the same `content/queue.json` the rest of the suite uses.

## ⚠️ Read first
1. **This automates TikTok, which is against its Terms.** The tool has
   bot-detection evasion, but the risk of the **@hplandscapingllc** account being
   flagged/limited is real and is on you. Don't run huge volumes; keep it human.
2. **Business accounts get a copyright check.** A mainstream song's audio may be
   refused (`copyrightcheck=True` surfaces this). **Test ONE post before trusting
   it.** If Wallen-type songs get blocked, use TikTok's cleared/commercial sounds
   (still free) or accept the manual one-tap flow for big songs.
3. Why the laptop and not GitHub Actions: TikTok blocks datacenter IPs and an
   un-cookied browser. It must run where you normally browse, logged in.

## One-time setup (≈15 min, on the laptop)
1. Install **Python 3.10+** and **Node.js** (the tool needs both).
2. In a terminal, in this `social-suite/` folder:
   ```
   pip install tiktokautouploader
   phantomwright_driver install chromium
   ```
3. **Log in once per account.** The first real run opens a browser — log into the
   **HP** TikTok, finish any captcha, and it saves the cookies
   (`Tk_cookies_hp.json`) for next time. (Keep that file private — it's a login.)

## Test it (do this BEFORE automating)
1. Pick one approved post in `content/queue.json` (set its `status` to `pending`,
   make sure `platforms` includes `"tiktok"`), and give it a `"sound"`:
   ```json
   { "id": "hp-test", "brand": "hp", "status": "pending",
     "platforms": ["tiktok"], "sound": "Morgan Wallen - Whiskey Glasses",
     "schedule": null, "text": "....caption...." }
   ```
2. Dry run (uploads nothing, shows the plan):
   ```
   python automation/tiktok_browser_post.py --brand hp --dry-run
   ```
3. For real, just that one:
   ```
   python automation/tiktok_browser_post.py --brand hp --once hp-test
   ```
4. Watch the browser. If the song attaches and it posts/schedules → ✅ we're in
   business. If the song is refused → it's the business-account copyright wall,
   not the tool.

## Everyday use — basically one command a week
1. Approve the videos you want out (flip each one's `status` from `review` →
   `pending` in `content/queue.json`; make sure `platforms` includes `"tiktok"`).
2. Run:
   ```
   python automation/tiktok_browser_post.py --brand hp
   ```
   For each approved post it automatically:
   - grabs the **next song** from `content/tiktok_songs_hp.txt` (cycled in order),
   - picks the **next Mon/Wed/Fri 10:00** slot (your cadence), and
   - uploads + schedules it on TikTok (up to 10 days out).
   Because TikTok fires the scheduled posts itself, the **laptop can be off**
   until you queue the next batch (~weekly).
3. Preview first anytime with `--dry-run` (shows song + time per post, uploads
   nothing).

### Change the songs or cadence
- **Songs:** edit `content/tiktok_songs_hp.txt` — one `Artist - Title` per line.
- **Days/time:** edit `POST_WEEKDAYS` / `POST_HOUR` at the top of
  `automation/tiktok_browser_post.py` (default Mon/Wed/Fri 10:00 **local** time —
  TikTok schedules in the account's local timezone).
- **One-off override:** `--sound "Song Name"` forces one song for the whole run;
  a post can also carry its own `"sound"` / `"schedule"` to override the defaults.
- **Sound volume:** `TIKTOK_SOUND_VOLUME=background|mix|main` (default `mix`).

Re-running is safe: posted items flip to `status="scheduled"` and are skipped, and
anything that doesn't fit the 10-day window is left for the next run.

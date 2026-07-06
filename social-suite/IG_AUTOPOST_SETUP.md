# Instagram Reels auto-poster (with a real song) — setup

Same idea as the TikTok system, for Instagram. Uses `instagrapi` (Instagram's
private mobile API) to post a clip as a **Reel with a trending song attached**,
pulling clips from the shared HP Dropbox folder and rotating the same song list.

Instagram's private API posts **immediately** (no native scheduling), so a
launchd timer fires the poster **Mon/Wed/Fri at 12:00** — one Reel per run.

> ⚠️ Private-API automation is against Instagram's ToS (same risk class as the
> TikTok tool). A **Business** IG account may be limited to cleared songs; a
> **Creator/personal** account gets the full trending library. We confirm which
> by testing one Reel. Everything below is built and ready — **don't run it until
> we're ready to test together.**

## One-time setup (on the laptop)
1. Install the library:
   ```
   pip3 install instagrapi
   ```
2. Create the login file `~/Downloads/ig_creds.json` with HP's Instagram login:
   ```json
   { "username": "HP_INSTAGRAM_USERNAME", "password": "HP_INSTAGRAM_PASSWORD" }
   ```
   (First login may ask for a 2FA/verification code — that's a one-time thing;
   the session is then saved to `~/Downloads/ig_session.json` and reused.)

## Test (one Reel — do this before turning on auto)
```
python3 ~/Downloads/ig_autopost.py
```
It posts the next clip as a Reel with the next song. If the song attaches → we're
in business. If the account blocks the track → that's the Business-account music
limit (same as TikTok), and we use cleared songs or add trending ones in-app.

## Turn on full auto (after the test passes)
Installs a launchd timer that runs the poster **Mon/Wed/Fri at noon**:
```
mkdir -p ~/Library/LaunchAgents
cat > ~/Library/LaunchAgents/com.hp.ig.autopost.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.hp.ig.autopost</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/Users/calebpittman/Downloads/ig_autopost.py</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/calebpittman</string>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>12</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/Users/calebpittman/Downloads/ig_autopost.log</string>
  <key>StandardErrorPath</key><string>/Users/calebpittman/Downloads/ig_autopost.err</string>
</dict>
</plist>
EOF
launchctl unload ~/Library/LaunchAgents/com.hp.ig.autopost.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.hp.ig.autopost.plist
echo "IG AUTO-RUN INSTALLED ✅"
```
Only rule: the Mac must be on around noon Mon/Wed/Fri for it to fire.

## Facebook (comes mostly free)
Link HP's Instagram to the HP Facebook Page and turn on **"Share Reels to
Facebook"** in Instagram settings — then each Reel auto-crossposts to Facebook.
(If you'd rather post to FB independently, that's a follow-on; the official Meta
API poster in this repo already handles FB.)

## Notes
- `~/Downloads/ig_autopost_state.json` tracks what's been posted (separate from
  TikTok's, so the same clip posts to both).
- Song list + hooks are embedded in `ig_autopost.py` — edit there to change them.
- One Reel per run; a batch of clips drips out one per Mon/Wed/Fri slot.

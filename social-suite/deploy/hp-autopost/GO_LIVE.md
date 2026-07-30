# HP Auto-Post — Go-Live Checklist

Everything is built. This is the exact order of steps to turn it on. Do them
top to bottom. Nothing posts until Step 5.

Structure that's already set up for you:
- Dropbox `HP Auto Post/` has **HP Landscaping**, **HP Pools**, **HP Design**
  (each with a `Talking Videos/` subfolder).
- Each company folder posts to that company's accounts only.
- Schedule: Mon / Wed / Fri at 11:00am.

---

## Step 0 — Put clips in the company folders
Drop each company's clips into its Dropbox folder (`HP Landscaping`, `HP Pools`,
`HP Design`). Talking clips go in that company's `Talking Videos`. A few each is
enough to start.

---

## Step 1 — Connect the remaining accounts

**TikTok (3)** — browser opens, log in as that account, wait for the For You feed:
```zsh
~/tiktok-venv39/bin/python ~/claude-code-config/social-suite/automation/tiktok_login_one.py --account higherpurposedesign
~/tiktok-venv39/bin/python ~/claude-code-config/social-suite/automation/tiktok_login_one.py --account hpdesignn
~/tiktok-venv39/bin/python ~/claude-code-config/social-suite/automation/tiktok_login_one.py --account HigherPurposePools
```

**X — Pools (1)** — grab `auth_token` (+`ct0`) from x.com cookies as @HigherPurposePools:
```zsh
read -s "AUTH?Paste X auth_token then Enter: "; echo; read -s "CT0?Paste X ct0 then Enter: "; echo; AUTH="$AUTH" CT0="$CT0" ~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/x_cookie_save.py --account HigherPurposePools
```

**YouTube (2)** — one-time Google setup, then connect each channel:
```zsh
# a) install the connector (once)
~/hp-venv/bin/pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
# b) create an OAuth client in Google Cloud (YouTube Data API v3, "Desktop app")
#    and save the downloaded file to ~/hp-auto/client_secret.json
# c) authorize each channel (browser opens -> pick the channel's Google account -> Allow)
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/youtube_connect_one.py --channel Landscaping
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/youtube_connect_one.py --channel Pools
```

---

## Step 2 — Turn the config into your live config
```zsh
cp ~/claude-code-config/social-suite/content/accounts.example.json ~/claude-code-config/social-suite/content/accounts.json
```
In `accounts.json`, flip `"enabled": true` for the accounts you've connected and
**tested** (X and YouTube start off until you've done a test post — see Step 4).

---

## Step 3 — Pre-flight (checks every enabled account is ready; posts nothing)
```zsh
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/preflight.py
```
Every enabled account should show ✅. Fix any ❌ before continuing.

---

## Step 4 — Dry run (shows exactly what each company will post; posts nothing)
```zsh
cd ~/claude-code-config/social-suite && DRY_RUN=1 ~/hp-venv/bin/python automation/post_multi.py
```
You'll see one line per company (the clip it picked) and one line per account.

> Test X + YouTube once each with a throwaway/deletable post before enabling them
> on the schedule — those two are automation-based and worth a one-time check.

---

## Step 5 — Install the schedule (Mon/Wed/Fri 11am)
```zsh
cp ~/claude-code-config/social-suite/deploy/hp-autopost/run-multi.sh ~/hp-auto/run-multi.sh
chmod +x ~/hp-auto/run-multi.sh
cp ~/claude-code-config/social-suite/deploy/hp-autopost/com.hp.autopost.plist ~/Library/LaunchAgents/com.hp.autopost.plist
launchctl unload ~/Library/LaunchAgents/com.hp.autopost.plist 2>/dev/null
launchctl load  ~/Library/LaunchAgents/com.hp.autopost.plist
echo "scheduled."
```

---

## Step 6 — Turn OFF the old single-brand schedule (avoid double-posting)
Find and unload the old job (the one that posted only Landscaping FB+IG):
```zsh
launchctl list | grep -i hp
# then, for whatever old label it shows (e.g. com.hp.postall):
launchctl unload ~/Library/LaunchAgents/<old-label>.plist
```

---

## To test the whole thing immediately (real post, off-schedule)
```zsh
cd ~/claude-code-config/social-suite && ~/hp-venv/bin/python automation/post_multi.py
```
Watch the log:
```zsh
tail -f ~/hp-auto/autopost.log
```

# HP Auto-Post — Go-Live Checklist (15 accounts: 3 companies × 5 platforms)

Everything is built. Do these steps top to bottom tomorrow. Nothing posts until
the dry run / Step 5.

**The grid — one account per company on each platform:**

| | Facebook | Instagram | TikTok | X | YouTube |
|---|---|---|---|---|---|
| **Landscaping** | ✅ hp-fb | ✅ hp-ig | ✅ HigherPurposeLandscaping | ⏳ HigherPurposeLandscaping | ⏳ Landscaping |
| **Pools** | ✅ pools-fb | ✅ pools-ig | ✅ HpPools | ⏳ HigherPurposePools | ⏳ Pools |
| **Design** | ✅ design-fb | ✅ design-ig | ⏳ higherpurposedesign | ⏳ (confirm handle) | ⏳ Design |

✅ = already connected · ⏳ = connect tomorrow. Each company posts from its own
Dropbox folder (`HP Landscaping` / `HP Pools` / `HP Design`).

---

## Step 0 — Put clips in the company folders
Drop each company's clips into its Dropbox folder; talking clips into that
company's `Talking Videos`. A few each is enough to start.

---

## Step 1 — Connect the accounts still marked ⏳

### TikTok — Design (browser opens; log in; wait for For You feed)
```zsh
~/tiktok-venv39/bin/python ~/claude-code-config/social-suite/automation/tiktok_login_one.py --account higherpurposedesign
```

### X — Pools & Design (grab auth_token + ct0 from x.com cookies for each)
```zsh
read -s "AUTH?Paste X auth_token: "; echo; read -s "CT0?Paste X ct0: "; echo; AUTH="$AUTH" CT0="$CT0" ~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/x_cookie_save.py --account HigherPurposePools
read -s "AUTH?Paste X auth_token: "; echo; read -s "CT0?Paste X ct0: "; echo; AUTH="$AUTH" CT0="$CT0" ~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/x_cookie_save.py --account <DESIGN_X_HANDLE>
```

### YouTube — Landscaping, Pools, Design
```zsh
# once: install + create a Google OAuth client (YouTube Data API v3, "Desktop app"),
# save the downloaded file to ~/hp-auto/client_secret.json
~/hp-venv/bin/pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
# then authorize each channel (browser -> pick that channel's Google account -> Allow)
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/youtube_connect_one.py --channel Landscaping
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/youtube_connect_one.py --channel Pools
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/youtube_connect_one.py --channel Design
```

> Already connected (no action): all 3 Facebook, all 3 Instagram, TikTok
> Landscaping + Pools, X Landscaping.

---

## Step 2 — Turn the config into your live config
```zsh
cp ~/claude-code-config/social-suite/content/accounts.example.json ~/claude-code-config/social-suite/content/accounts.json
```
In `accounts.json`: set the real `x_account` for Design (replace the CONFIRM
placeholder), and flip `"enabled": true` for every account you've connected
**and tested**.

---

## Step 3 — Pre-flight (checks every enabled account is ready; posts nothing)
```zsh
~/hp-venv/bin/python ~/claude-code-config/social-suite/automation/preflight.py
```
Every enabled account should show ✅.

---

## Step 4 — Dry run (shows exactly what each company will post; posts nothing)
```zsh
cd ~/claude-code-config/social-suite && DRY_RUN=1 ~/hp-venv/bin/python automation/post_multi.py
```

> Give X + YouTube one test post each (throwaway/deletable) before enabling them
> on the schedule — they're automation-based. FB/IG/TikTok are solid.

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

## Step 6 — Turn OFF the old single-brand schedule (avoid double-posting)
```zsh
launchctl list | grep -i hp
# for the old label it shows:
launchctl unload ~/Library/LaunchAgents/<old-label>.plist
```

---

## Test the whole thing now (real post, off-schedule)
```zsh
cd ~/claude-code-config/social-suite && ~/hp-venv/bin/python automation/post_multi.py
tail -f ~/hp-auto/autopost.log
```

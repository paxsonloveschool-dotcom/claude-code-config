# TikTok setup — link an account to the auto-poster

This is the definitive guide to posting to **your own** TikTok account via the
**Content Posting API**, the TikTok parallel to [`META_SETUP.md`](META_SETUP.md).

> **The one thing to understand up front:** a TikTok **access** token lives only
> **~24 hours**; the **refresh** token lives **~365 days**. So we never store a
> bare access token — we store the **refresh token** (plus the app's
> `client_key` / `client_secret`) and the poster mints a fresh access token
> just-in-time before every post. This is the same refresh-token pattern the
> Dropbox ingest already uses.

The result of this guide, per brand, is the values you paste into your brand
credentials (`BRANDS_JSON` / `content/brands.json`):

```json
"tiktok": {
  "refresh_token": "...",        // the long-lived (~365d) token — the key one
  "client_key": "...",           // your TikTok app's Client Key
  "client_secret": "...",        // your TikTok app's Client Secret
  "privacy_level": "PUBLIC_TO_EVERYONE"
}
```

---

## (a) Create the TikTok app (developers.tiktok.com)

1. Go to **https://developers.tiktok.com** → register / log in with the account
   that owns the brand → **Manage apps → Connect an app**.
2. Add the **Content Posting API** product (this is what `video.publish` needs).
3. Fill app details, add your **privacy policy URL** and **terms URL** (a simple
   page on the business site is fine — see [`legal/`](legal/)).
4. Under **Login Kit / redirect URIs**, add a redirect URI you control, e.g.
   `https://<your-site>/tiktok/callback` (it does **not** need to be a live
   server — you only read the `code` out of the redirected URL by hand). Copy it
   **exactly**; it must match byte-for-byte in step (b).
5. Copy the **Client Key** and **Client Secret** from the app's credentials.

> ⚠️ **Audit / privacy levels.** Until your app passes TikTok's Content Posting
> API **audit**, posts can only go out as **`SELF_ONLY`** (private). Submit for
> audit to unlock `PUBLIC_TO_EVERYONE`. You can wire everything up and test in
> `SELF_ONLY` while the audit is pending — see (e).

---

## (b) Authorize the account once (get the one-time `code`)

Build the consent URL (requests the `video.publish` scope) and open it in the
browser **logged in as the brand's TikTok account**:

```bash
python social-suite/services/publish/direct/tiktok_oauth.py authorize \
  --client-key "YOUR_CLIENT_KEY" \
  --redirect-uri "https://<your-site>/tiktok/callback"
```

Approve the screen. TikTok redirects to
`https://<your-site>/tiktok/callback?code=THE_CODE&scope=...`. Copy `THE_CODE`
out of the address bar (it is single-use and expires within minutes).

---

## (c) Exchange the `code` for the refresh token

```bash
python social-suite/services/publish/direct/tiktok_oauth.py exchange \
  --client-key "YOUR_CLIENT_KEY" \
  --client-secret "YOUR_CLIENT_SECRET" \
  --code "THE_CODE" \
  --redirect-uri "https://<your-site>/tiktok/callback"
```

Response (trimmed):

```json
{
  "access_token": "act....",        // ~24h — we don't store this
  "refresh_token": "rft....",       // ~365d — THIS is what we store
  "refresh_expires_in": 31536000,
  "open_id": "...",
  "scope": "user.info.basic,video.publish"
}
```

Take the **`refresh_token`** → that, with the `client_key` + `client_secret`, is
what the brand stores.

---

## (d) Put the values into your brand credentials

### Recommended: flat per-brand GitHub Secrets (how HP + Restore's Meta is set)

Exactly the pattern already used for IG/FB — **one secret = one pasted value**,
no JSON to mangle. Go to **repo → Settings → Secrets and variables → Actions →
New repository secret** and add these (per brand; `<NAME>` = `HP`, `RESTORE`, …):

| Secret name | Value |
|---|---|
| `BRAND_<NAME>_TIKTOK_REFRESH_TOKEN` | the `rft....` refresh token from step (c) |
| `BRAND_<NAME>_TIKTOK_CLIENT_KEY` | your app's Client Key |
| `BRAND_<NAME>_TIKTOK_CLIENT_SECRET` | your app's Client Secret |
| `BRAND_<NAME>_TIKTOK_PRIVACY_LEVEL` | `PUBLIC_TO_EVERYONE` (or `SELF_ONLY` pre-audit) |

`services/publish/brands.py` reads these into the brand's `tiktok` creds and the
poster mints a fresh access token each run. The cron
(`.github/workflows/social-post.yml`) already passes these secrets. Flat secrets
override `BRANDS_JSON`, and stray spaces/newlines are trimmed automatically.

### Alternative: one `BRANDS_JSON` secret / local `content/brands.json`

Same values as one JSON object (see
[`content/brands.example.json`](content/brands.example.json)):

```json
"tiktok": {
  "refresh_token": "rft....",
  "client_key": "YOUR_CLIENT_KEY",
  "client_secret": "YOUR_CLIENT_SECRET",
  "privacy_level": "PUBLIC_TO_EVERYONE"
}
```

At post time, `run_due.py` sees the `refresh_token` and calls
`tiktok_oauth.refresh_access_token(...)` to mint a fresh ~24h access token, then
posts — no manual token babysitting.

> TikTok **rotates** the refresh token on each refresh, but the previous one
> keeps working until it nears expiry, so an unattended cron stays valid for the
> full ~365-day window without re-storing. Re-run (b)–(c) once a year (or if a
> token is ever revoked) to re-link.

---

## (e) Verify it works

**Check a fresh access token can post** (cheapest authenticated call —
`creator_info/query`):

```bash
# Mint one from the refresh token, then check it:
python social-suite/services/publish/direct/tiktok_oauth.py refresh \
  --client-key "YOUR_CLIENT_KEY" --client-secret "YOUR_CLIENT_SECRET" \
  --refresh-token "rft...."        # copy access_token from the output

TIKTOK_ACCESS_TOKEN="act...." \
  python social-suite/services/publish/direct/tiktok_oauth.py check
# -> "TikTok access token OK — creator info reachable, posting scope present."
```

**Verify every brand's link at once** (refreshes + checks each brand that has
TikTok creds in `BRANDS_JSON` / `content/brands.json`):

```bash
python social-suite/services/publish/direct/tiktok_oauth.py check --all-brands
# -> "[hp] OK"  "[restore] OK"  "All 2 brand TikTok link(s) OK."
```

**Dry-run the queue** (routes nothing, just shows what would post):

```bash
python social-suite/services/publish/run_due.py social-suite/content/queue.json --dry-run
```

While the audit is pending, set `"privacy_level": "SELF_ONLY"` so a real run
posts a private video you can confirm in the app, then flip it to
`PUBLIC_TO_EVERYONE` once audited.

---

## (f) Media: a LOCAL file (no public host needed)

The publisher uploads the bytes directly via **FILE_UPLOAD**, so a post's
`media_url` can be a **local video file path** (e.g. the rendered clip on disk) —
**no public host, no verified domain, $0**. An `http(s)` URL also works (it's
downloaded first), but you don't need one. This is the opposite of Meta, which
must fetch your media server-side.

---

## (g) Test ONE private SELF_ONLY clip, then delete it

Nothing here goes public: `SELF_ONLY` posts a **private** video only you can see.
Post one from a local clip with the brand's token, confirm it in the TikTok app,
then delete it.

```bash
# Use a fresh access token (mint from the refresh token if needed — see (e)).
python - <<'PY'
from services.publish.direct import tiktok
pub_id = tiktok.post_tiktok(
    access_token="act....",          # the brand's TikTok access token
    caption="suite test — private",
    video="media/clips/test.mp4",     # a LOCAL clip path
    privacy_level="SELF_ONLY",        # private; nothing public
)
print("publish_id:", pub_id)
# Optional: poll until done
import time
for _ in range(20):
    s = tiktok.fetch_status("act....", pub_id)
    st = (s.get("data") or {}).get("status")
    print(st)
    if st in ("PUBLISH_COMPLETE", "FAILED"):
        break
    time.sleep(3)
PY
```

Then open the **TikTok app → your profile → the private video** and **delete it**.
(Because it's `SELF_ONLY`, no follower ever saw it.)

> The suite's own queue stays **paused**: the cron in
> `.github/workflows/social-post.yml` is off, and `run_due.py` only fires posts
> with `status == "pending"`. So nothing posts on its own until you flip a post
> to `pending` yourself.

---

## Recap — what each piece is

| Value | What it is | Lifetime |
|---|---|---|
| `client_key` / `client_secret` | The TikTok **app** identity (developers.tiktok.com) | until rotated |
| `code` | One-time grant from the consent screen | minutes |
| `access_token` | Used to post; minted just-in-time, never stored | ~24h |
| `refresh_token` | **Stored** — mints access tokens for the cron | ~365d |

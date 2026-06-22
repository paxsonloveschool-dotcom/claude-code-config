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

Add the brand's `tiktok` block to `BRANDS_JSON` (one secret holding every
brand's creds) or `content/brands.json` — see
[`content/brands.example.json`](content/brands.example.json):

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

**Dry-run the queue** (routes nothing, just shows what would post):

```bash
python social-suite/services/publish/run_due.py social-suite/content/queue.json --dry-run
```

While the audit is pending, set `"privacy_level": "SELF_ONLY"` so a real run
posts a private video you can confirm in the app, then flip it to
`PUBLIC_TO_EVERYONE` once audited.

---

## (f) Media must be a PUBLIC video URL

TikTok fetches the bytes **server-side** via `PULL_FROM_URL`, so a post's
`media_url` must be a **public video URL on a verified domain** (verify the
domain under your app's **URL properties**). A `localhost`/private path fails —
TikTok can't reach it. Same constraint as Meta's image/video fetch.

---

## Recap — what each piece is

| Value | What it is | Lifetime |
|---|---|---|
| `client_key` / `client_secret` | The TikTok **app** identity (developers.tiktok.com) | until rotated |
| `code` | One-time grant from the consent screen | minutes |
| `access_token` | Used to post; minted just-in-time, never stored | ~24h |
| `refresh_token` | **Stored** — mints access tokens for the cron | ~365d |

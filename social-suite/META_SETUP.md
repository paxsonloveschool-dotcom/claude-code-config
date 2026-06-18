# Meta (Instagram + Facebook) setup — the NO-VERIFICATION path

This is the definitive guide to posting to **your own** Instagram Professional
account and **your own** Facebook Page via the Meta Graph API — with **no App
Review and no Business Verification**.

> **The one thing to understand up front:** posting to accounts *you* own and
> admin only needs **Development Mode + Standard Access**. App Review and
> Business Verification are required only for **Advanced Access** — i.e. serving
> *other people's* accounts. **We never request Advanced Access**, so we never
> trigger either review. Keep the app in Development Mode and you are done.

The result of this guide is three values you paste into GitHub repo Secrets:
`META_ACCESS_TOKEN`, `IG_USER_ID`, `FB_PAGE_ID`. After that the cron workflow
posts on its own.

> **Running MORE than one brand?** (e.g. HP Landscaping **and** Restore, each
> with its own IG + FB.) Get the three values above **for each brand**, then see
> **[`MULTI_BRAND.md`](MULTI_BRAND.md)** — you put all brands into one
> `BRANDS_JSON` secret instead of the three single secrets.

---

## (a) Confirm Instagram is Professional + linked to its Facebook Page

1. In the **Instagram app** → your profile → **☰ → Settings → Account type and
   tools → Switch to Professional account** (pick **Business** or **Creator**).
2. Link it to a **Facebook Page** you admin: Instagram **Settings → Sharing to
   other apps / Linked accounts → Facebook**, or from the **Facebook Page →
   Settings → Linked accounts → Instagram**. The Page and IG must be linked or
   the Graph API cannot see the IG account.

You do **not** need an Instagram "app password" or anything else here — just the
Professional account linked to a Page you administer.

---

## (b) Create a **Business**-type Meta app — and KEEP IT IN DEVELOPMENT MODE

1. Go to **https://developers.facebook.com** → **My Apps → Create App**.
2. App type: **Business**.
3. Name it (e.g. "HP Restore Publisher"), attach it to your Business portfolio
   if asked.
4. The app starts in **Development Mode** (top bar shows a toggle:
   *In development* / *Live*). **Leave it in Development Mode.**

> ⛔️ **Do NOT do any of these** — they are only for serving other people's
> accounts and they are what triggers review:
> - Do **not** flip the app to **Live** (not needed for own-account posting).
> - Do **not** click **"Request Advanced Access"** on any permission.
> - Do **not** submit **App Review**.
> - Do **not** start **Business Verification**.
>
> With **Standard Access** (the default) every permission works on accounts where
> **you are an admin / assigned asset** while the app is in Development Mode. That
> is exactly our case.

5. Add the **Instagram Graph API** product (and **Facebook Login** is fine to add
   too). You do **not** need to configure OAuth redirect URLs for this token
   path — we mint the token by hand in the Graph API Explorer (step d).

Reference: **App Modes (Development vs Live) & Access Levels (Standard vs
Advanced)** — https://developers.facebook.com/docs/development/build-and-test/app-modes/

---

## (c) Add yourself as Admin and add your Page + IG as assets

1. App dashboard → **App roles → Roles** (or **App settings → Advanced →
   roles**): confirm **your** Facebook account is an **Administrator** of the app.
2. Make sure your Facebook user is an **Admin of the Facebook Page**
   (Page → **Settings → Page roles**) and the Page is linked to the IG account
   (step a). Because Standard Access keys off "are you an admin of this asset,"
   admin-of-the-Page + linked-IG is what unlocks publishing in Development Mode.

---

## (d) Get the **non-expiring Page token** (Graph API Explorer → long-lived exchange → /me/accounts)

The token we store is a **Page access token derived from a long-lived user
token**. Page tokens obtained this way are **effectively non-expiring** (they do
not carry a 60-day expiry the way user tokens do), which is what we want for an
unattended cron.

**Step 1 — short-lived USER token (Graph API Explorer).**
1. Open **https://developers.facebook.com/tools/explorer/**.
2. Top-right: select **your app** in the **Meta App** dropdown.
3. **User or Page** dropdown → **Get User Access Token**.
4. Add these **permissions (scopes)** and click **Generate Access Token**, then
   approve the popup:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_posts`
   - `business_management`
5. Copy the token it shows. This is a **short-lived USER token** (expires in
   ~1–2 hours — that's fine, we exchange it next).

You also need your **App ID** and **App Secret** for the exchange:
**App settings → Basic** (click *Show* next to App Secret).

**Step 2 — exchange for a LONG-LIVED user token** (`fb_exchange_token`).
Run this (fill in the three values). It is a `GET`:

```bash
curl -s -G "https://graph.facebook.com/v21.0/oauth/access_token" \
  --data-urlencode "grant_type=fb_exchange_token" \
  --data-urlencode "client_id=YOUR_APP_ID" \
  --data-urlencode "client_secret=YOUR_APP_SECRET" \
  --data-urlencode "fb_exchange_token=SHORT_LIVED_USER_TOKEN"
```

Plain URL form (same thing):

```
https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=YOUR_APP_ID&client_secret=YOUR_APP_SECRET&fb_exchange_token=SHORT_LIVED_USER_TOKEN
```

Response: `{"access_token":"LONG_LIVED_USER_TOKEN","token_type":"bearer","expires_in":5184000}`
(~60 days). Copy `LONG_LIVED_USER_TOKEN`.

**Step 3 — get the PAGE token from `/me/accounts`.**
Use the long-lived **user** token to list your Pages; each Page comes with its
own `access_token` — that Page token is the **non-expiring** one we store.

```bash
curl -s -G "https://graph.facebook.com/v21.0/me/accounts" \
  --data-urlencode "access_token=LONG_LIVED_USER_TOKEN"
```

Response (trimmed):

```json
{
  "data": [
    {
      "name": "Higher Purpose Landscaping",
      "id": "1234567890",                       // <- this is your FB_PAGE_ID
      "access_token": "PAGE_TOKEN_HERE"         // <- this is your META_ACCESS_TOKEN
    }
  ]
}
```

Take the `access_token` of the Page you want to post to → that is
**`META_ACCESS_TOKEN`**. Take its `id` → that is **`FB_PAGE_ID`** (also usable in
step e).

References:
- **Get a long-lived token** — https://developers.facebook.com/docs/facebook-login/guides/access-tokens/get-long-lived/
- **Instagram Content Publishing** — https://developers.facebook.com/docs/instagram-platform/content-publishing/

---

## (e) Find your IG user id and FB Page id

- **FB Page id** — from `/me/accounts` above (the `id` field), or
  **Page → About → Page transparency / Page ID**.
- **IG user id** — ask the Page for its linked IG Business account:

```bash
curl -s -G "https://graph.facebook.com/v21.0/FB_PAGE_ID" \
  --data-urlencode "fields=instagram_business_account" \
  --data-urlencode "access_token=META_ACCESS_TOKEN"
```

Response:

```json
{ "instagram_business_account": { "id": "17841400000000000" }, "id": "1234567890" }
```

`instagram_business_account.id` → that is **`IG_USER_ID`**.

---

## (f) Put the three values into GitHub repo Secrets

Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `META_ACCESS_TOKEN` | the **Page** `access_token` from `/me/accounts` (non-expiring) |
| `IG_USER_ID` | `instagram_business_account.id` from step (e) |
| `FB_PAGE_ID` | the Page `id` from `/me/accounts` |

The cron workflow (`.github/workflows/social-post.yml`) reads these. Its first
step runs `services/publish/check_token.py`, which fails the run loudly if
`META_ACCESS_TOKEN` is ever revoked/invalid.

**Verify locally first:**

```bash
META_ACCESS_TOKEN="PAGE_TOKEN_HERE" python social-suite/services/publish/check_token.py
# -> "META_ACCESS_TOKEN OK — resolves to <name> (id ...)."  (exit 0)
```

---

## (g) Media must be a PUBLIC URL

Meta fetches your image/video **server-side**, so `media_url` must be reachable
on the open internet. Easiest: commit the rendered clip into the repo and use its
`https://raw.githubusercontent.com/...` URL, or any public host (Dropbox direct
link, S3, etc.). A `localhost`/private path **fails** — Meta can't reach it.

---

## (h) The ~25 posts/day Instagram limit

Instagram caps publishing at roughly **25 posts per rolling 24 hours** per IG
account. Check the live remaining quota any time:

```bash
curl -s -G "https://graph.facebook.com/v21.0/IG_USER_ID/content_publishing_limit" \
  --data-urlencode "fields=quota_usage,config" \
  --data-urlencode "access_token=META_ACCESS_TOKEN"
```

Reference: **content_publishing_limit** —
https://developers.facebook.com/docs/instagram-platform/content-publishing/#rate-limiting

(Facebook Page posting is not subject to this IG cap.)

---

## (i) App Review & Business Verification are explicitly NOT needed here

To restate, because it is the whole point of this path:

- **Development Mode + Standard Access** is sufficient to publish to **your own**
  IG Professional account and **your own** FB Page where **you are an admin**.
- **App Review** and **Business Verification** gate **Advanced Access** —
  publishing on behalf of **other** accounts/businesses. We never request
  Advanced Access, so **neither review applies** and there is **nothing to wait
  on**. The only human step is generating the token above.

If a Meta screen ever pushes you toward "Request Advanced Access" / "Start
verification," you can safely **ignore it** for this own-account use case.

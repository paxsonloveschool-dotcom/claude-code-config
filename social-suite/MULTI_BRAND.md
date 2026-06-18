# Multi-brand posting (HP Landscaping + Restore + future brands)

The poster started as **single-account**: one set of Meta creds
(`META_ACCESS_TOKEN`, `IG_USER_ID`, `FB_PAGE_ID`) posting to one IG + one FB.

**Multi-brand** lets each business post to its **own** Instagram + Facebook on
the same schedule. Each brand keeps its **own** three Meta values — you just
bundle them all into **one GitHub Secret** called `BRANDS_JSON`.

> First get the three Meta values for **each** brand by following
> [`META_SETUP.md`](META_SETUP.md) once per brand (one Meta app can admin
> several Pages/IG accounts, so you usually only generate fresh Page tokens).

---

## 1. The `BRANDS_JSON` secret format

One JSON object: `{ "<brand-key>": { creds }, ... }`. The brand key (e.g. `hp`,
`restore`) is what you put on each queued post's `"brand"` field.

```json
{
  "hp": {
    "meta_access_token": "EAAG...HP_PAGE_TOKEN",
    "ig_user_id": "1784xxxxxxxxxxx",
    "fb_page_id": "1015xxxxxxxxxxx"
  },
  "restore": {
    "meta_access_token": "EAAG...RESTORE_PAGE_TOKEN",
    "ig_user_id": "1784yyyyyyyyyyy",
    "fb_page_id": "1015yyyyyyyyyyy"
  }
}
```

Paste that whole object as the value of **one** repo Secret named `BRANDS_JSON`
(GitHub → repo → Settings → Secrets and variables → Actions → New secret).

`content/brands.example.json` ships as a copy-paste template.

**This replaces the three single secrets** (`META_ACCESS_TOKEN` / `IG_USER_ID` /
`FB_PAGE_ID`) for multi-brand use. The single secrets still work as a fallback
`"default"` brand for any post with no `"brand"` field — keep or drop them.

---

## 2. Tag each post with its brand

In `content/queue.json`, add `"brand"` to each entry:

```json
{ "id": "...", "text": "...", "media_url": "...",
  "platforms": ["instagram", "facebook"], "schedule": null,
  "brand": "hp", "status": "pending", "error": null }
```

A post with **no** `"brand"` (or `"brand": "default"`) uses the legacy single
secrets — fully backward compatible.

See `content/queue.example.json` for HP + Restore entries side by side.

---

## 3. Add a NEW brand later

1. Follow `META_SETUP.md` for that brand to get its 3 values.
2. Open the `BRANDS_JSON` secret and paste a new key/object:
   ```json
   "newbrand": { "meta_access_token": "...", "ig_user_id": "...", "fb_page_id": "..." }
   ```
3. Use `"brand": "newbrand"` on that brand's queued posts.

Nothing else changes — no code edits, no new secrets.

---

## 4. How routing works (per brand)

- `services/publish/brands.py` loads the brand→creds map. Source priority:
  `BRANDS_JSON` env → `BRANDS_FILE` file (default `content/brands.json`) →
  single `"default"` brand from `META_ACCESS_TOKEN`/`IG_USER_ID`/`FB_PAGE_ID`.
- `run_due.py` resolves each due post's `brand` to its `BrandCreds`, then routes
  `instagram` → that brand's IG account and `facebook` → that brand's FB Page,
  using **that brand's** token.
- An **unknown brand** or **missing creds** marks just that post `failed` (with a
  clear error) and the run continues for the others. A per-brand summary prints
  at the end.
- The token-check step validates **every** brand's token when `BRANDS_JSON` is
  set; otherwise it checks the single legacy token.

---

## 5. Local secrets file (optional, never committed)

For local runs you can drop a real `content/brands.json` (same shape) instead of
setting `BRANDS_JSON`. It is **gitignored** — only `content/brands.example.json`
is committed. This code never writes tokens to disk.

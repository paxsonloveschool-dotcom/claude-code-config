# Postiz Content Automation Kit

Programmatically create and schedule social posts through the Postiz **public API**.

## What's here

| File | Purpose |
|------|---------|
| `schedule_posts.py` | Stdlib-only Python 3 script that posts a JSON file of captions to Postiz. |
| `plan_calendar.py` | Stamps a content file with drip-out `schedule` dates and (optionally) channel ids. |
| `content/hp-landscaping.json` | 10 ready-to-post captions for HP Landscaping. |
| `content/restore.json` | 10 ready-to-post captions for Restore. |

No third-party packages required — uses `urllib` from the standard library.

## API details (confirmed from Postiz source)

- **Endpoint:** `POST {POSTIZ_API_URL}/public/v1/posts`
- **Auth header:** `Authorization: <YOUR_API_KEY>` (raw key, **no** `Bearer ` prefix)
- **Rate limit:** ~30 requests/hour on the create-post endpoint.

Source: `gitroomhq/postiz-app` — `apps/sdk/src/index.ts`,
`apps/backend/src/public-api/routes/v1/public.integrations.controller.ts`,
`libraries/nestjs-libraries/src/dtos/posts/create.post.dto.ts`.

## 1. Get an API key

1. Open your Postiz web UI (self-hosted domain, or https://app.postiz.com).
2. Go to **Settings → Public API**.
3. Generate / copy the API key.

## 2. Set environment variables

```bash
# Hosted Postiz:
export POSTIZ_API_URL="https://api.postiz.com"
# Self-hosted (your NEXT_PUBLIC_BACKEND_URL, WITHOUT the /public/v1 suffix):
export POSTIZ_API_URL="https://social.yourdomain.com"

export POSTIZ_API_KEY="paste-your-key-here"
```

The script appends `/public/v1/posts` itself — don't include it in the URL.

## 3. Map your accounts to friendly labels (`channels.json`)

So you never mix up which business a post goes to, content files reference
accounts by **readable labels** (`hp-instagram`, `restore-facebook`, …) instead
of cryptic ids. You map those labels to real ids **once**, in `channels.json`.

First, list your connected accounts and their integration ids:

```bash
curl -H "Authorization: $POSTIZ_API_KEY" \
     "$POSTIZ_API_URL/public/v1/integrations"
```

Then copy the template and fill in the ids:

```bash
cp channels.example.json channels.json
# edit channels.json — paste each account's id next to its label
```

```json
{
  "hp-instagram": "the-id-of-HP-Landscaping-instagram",
  "hp-facebook": "the-id-of-HP-Landscaping-facebook",
  "restore-instagram": "the-id-of-Restore-instagram",
  "restore-facebook": "the-id-of-Restore-facebook"
}
```

`channels.json` is **gitignored** (it's specific to your instance). Only the
`.example` template is committed. Don't have Facebook (or an account)? Just
delete that label from both `channels.json` and the content files.

**Safety:** a label that isn't in `channels.json` is *skipped*, never guessed —
so a missing/typo'd mapping can't accidentally post to the wrong account.

## 4. Edit the content files

In `content/*.json`, each post object is:

```json
{
  "text": "caption with #hashtags and emojis",
  "channels": ["hp-instagram", "hp-facebook"],
  "schedule": "2026-07-01T14:00:00Z",
  "image": "https://yourcdn.com/photo.jpg"
}
```

- `channels` — one or more **labels** (from `channels.json`) or raw integration
  ids. This is how you target a post at ONE business and not the other: the
  HP files use `hp-*` labels, the Restore files use `restore-*` labels, so they
  stay separate. Want a post on just one account? List only that one label.
- `schedule` — ISO 8601 UTC time to post; use `null` to post immediately.
- `image` — public media URL, or `null` for text-only. (See note below.)

## 5. Dry-run (no API calls)

Always preview first. This prints the exact JSON payload that would be sent:

```bash
python3 schedule_posts.py content/hp-landscaping.json --dry-run
```

## 6. Send for real

```bash
python3 schedule_posts.py content/hp-landscaping.json
python3 schedule_posts.py content/restore.json
```

Posts still containing `REPLACE_WITH_CHANNEL_ID` are skipped automatically so you
can't accidentally fire placeholder data at the live API.

## 7. Drip posts out over a calendar (instead of all at once)

`plan_calendar.py` stamps each post with a `schedule` time across the weekdays
you pick, and can inject your channel id so you don't hand-edit the JSON:

```bash
# Mon/Wed/Fri at 9am EDT (UTC-4), starting next Monday, to one channel:
python3 plan_calendar.py content/hp-landscaping.json \
    --days mon,wed,fri --time 09:00 --utc-offset -4 \
    --channels YOUR_CHANNEL_ID --out planned.json

python3 schedule_posts.py planned.json    # sends them as scheduled posts
```

## Shortcuts

- **Makefile** (run from `postiz/`): `make dry-run`, `make plan CHANNELS=<id>`,
  `make schedule`, plus server ops `make up|down|logs|update|backup`.
- **GitHub Action** (`.github/workflows/postiz-schedule.yml`): trigger a batch
  from the Actions tab (or the GitHub mobile app) — set repo secrets
  `POSTIZ_API_URL` and `POSTIZ_API_KEY` first. Defaults to dry-run for safety.

## Notes / caveats

- **Images:** Postiz's `MediaDto` wants an uploaded media `id` + `path`. For a
  plain external URL the script sends the URL as both `id` and `path`. This is
  marked **ASSUMED** in the code — if image posts are rejected on your instance,
  upload the media through Postiz first and use the returned media id. Text-only
  posts (`"image": null`) are unaffected.
- **Settings:** each post is sent with an empty `settings: {}` so Postiz applies
  each provider's defaults. Add provider-specific settings there if you need them.

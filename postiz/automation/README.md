# Postiz Content Automation Kit

Programmatically create and schedule social posts through the Postiz **public API**.

## What's here

| File | Purpose |
|------|---------|
| `schedule_posts.py` | Stdlib-only Python 3 script that posts a JSON file of captions to Postiz. |
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

## 3. Find your channel (integration) IDs

Each post targets one or more connected accounts by **integration id**. Get them with:

```bash
curl -H "Authorization: $POSTIZ_API_KEY" \
     "$POSTIZ_API_URL/public/v1/integrations"
```

Copy the `id` of each channel you want to post to and paste it into the JSON,
replacing every `"REPLACE_WITH_CHANNEL_ID"`.

## 4. Edit the content files

In `content/*.json`, each post object is:

```json
{
  "text": "caption with #hashtags and emojis",
  "channels": ["INTEGRATION_ID_1", "INTEGRATION_ID_2"],
  "schedule": "2026-07-01T14:00:00Z",
  "image": "https://yourcdn.com/photo.jpg"
}
```

- `channels` — one or more integration ids (required).
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

## Notes / caveats

- **Images:** Postiz's `MediaDto` wants an uploaded media `id` + `path`. For a
  plain external URL the script sends the URL as both `id` and `path`. This is
  marked **ASSUMED** in the code — if image posts are rejected on your instance,
  upload the media through Postiz first and use the returned media id. Text-only
  posts (`"image": null`) are unaffected.
- **Settings:** each post is sent with an empty `settings: {}` so Postiz applies
  each provider's defaults. Add provider-specific settings there if you need them.

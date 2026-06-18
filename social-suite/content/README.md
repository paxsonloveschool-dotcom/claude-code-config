# Content — organized per brand

Each brand has its own content file, and **every post is tagged with its brand**,
so a brand's content can only ever go to that brand's own accounts. No mixing.

| File | Brand | Posts | Goes to |
|------|-------|-------|---------|
| `hp-content.json` | `hp` | 20 | HP Landscaping's accounts only |
| `restore-content.json` | `restore` | 20 | Restore's accounts only |

## Post shape
```json
{
  "id": "hp-001",
  "brand": "hp",                 // routing key → HP's credentials (BRANDS_JSON)
  "text": "caption with #hashtags 🌱",
  "media_url": null,             // a PUBLIC url; required to post to Instagram
  "platforms": ["facebook"],     // add "instagram" once media_url is set
  "schedule": null,              // null = eligible now; or ISO-8601 UTC time
  "status": "pending"            // becomes sent/failed after a run
}
```

## To also post to Instagram
Instagram (unlike Facebook) **requires an image/video at a public URL**. So for any
post you want on IG: set `media_url` to a public link (e.g. a rendered clip the
pipeline produced and committed to the repo → its `raw.githubusercontent.com`
URL) and add `"instagram"` to `platforms`. Facebook posts fine text-only.

## Scheduling
Use `automation/plan_calendar.py` to stamp `schedule` dates across the week, then
the GitHub-Actions runner (`services/publish/run_due.py`) posts each due item to
the right brand's accounts. Per-brand routing is handled by `BRANDS_JSON` (see
`../MULTI_BRAND.md`).

## Adding a new brand's content
Create `content/<brand>-content.json`, tag every post with `"brand": "<brand>"`,
and add that brand's credentials to `BRANDS_JSON`. Done.

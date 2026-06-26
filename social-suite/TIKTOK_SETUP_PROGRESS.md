# TikTok setup — WHERE WE LEFT OFF

Plain-English progress tracker for linking HP's TikTok to the auto-poster.
Full technical guide: [`TIKTOK_SETUP.md`](TIKTOK_SETUP.md).

## Account / app info
- HP TikTok login email: **higherpurposelandscaping@gmail.com**
- HP website: **https://hplandscapingllc.com**
- Sandbox app: **HP Auto Poster** → sandbox **HP Test** (Individual)
- Redirect URI (must match EXACTLY everywhere):
  **`https://hplandscapingllc.com/tiktok/callback`**
- Repo secrets stored (owner account `paxsonloveschool-dotcom`):
  `BRAND_HP_TIKTOK_CLIENT_KEY`, `BRAND_HP_TIKTOK_CLIENT_SECRET`

## ✅ DONE — posting is PROVEN end-to-end
1. Recovered HP TikTok login; logged into developers.tiktok.com.
2. Created app **HP Auto Poster** + sandbox **HP Test**; added Login Kit +
   Content Posting API (Direct Post); scope `video.publish`; redirect URI.
3. Added HP as a sandbox Target User; copied Client Key/Secret.
4. Stored `BRAND_HP_TIKTOK_CLIENT_KEY` / `_CLIENT_SECRET` repo secrets.
5. Built `.github/workflows/tiktok-link.yml` — runs the OAuth exchange + a
   SELF_ONLY test post on GitHub's runners (the dev sandbox egress blocks
   `open.tiktokapis.com`). Triggered it via the GitHub MCP as the owner.
6. **2026-06-26: private SELF_ONLY test post → `PUBLISH_COMPLETE`.** Owner saw
   the green test clip on the HP profile. The full chain works: generate video
   → upload → TikTok publishes. $0, hands-off.

### Key learning (why the first posts failed)
- `ubuntu-latest` no longer ships ffmpeg → install it in the workflow.
- TikTok error `unaudited_client_can_only_post_to_private_accounts`: an
  **unaudited** app can only post to a TikTok account whose profile is set to
  **Private**. HP was Public; flipping it Private let the SELF_ONLY post go
  through. **Public posting requires passing TikTok's audit.**

## ⏳ REMAINING — to post PUBLIC on a schedule (the business goal)
1. **Pass TikTok's Content Posting API audit** (developers.tiktok.com → the app
   → App review / "Submit for review"). Most fields already filled (icon,
   description, ToS + Privacy URLs = https://hplandscapingllc.com/index.html,
   category Business, platform Web). Remaining for the submission:
   - The **scope/product explanation** text box (draft ready in chat).
   - A **demo video** (screen recording) showing the authorize → post flow.
   - Remove any unused scopes before submitting.
2. After approval: set HP's TikTok back to **Public**; set
   `BRAND_HP_TIKTOK_PRIVACY_LEVEL` = `PUBLIC_TO_EVERYONE`.
3. **Persist the refresh token for the unattended cron.** The link workflow can
   auto-store `BRAND_HP_TIKTOK_REFRESH_TOKEN` when a `GH_PAT` secret
   (fine-grained PAT, Secrets:write) exists — add that, then re-run the link
   workflow once with a fresh code so the cron can post on its own.
4. Un-pause the cron (`.github/workflows/social-post.yml`) / flip queue items to
   `pending` when ready to go live.

## Notes
- Account is currently set to **Private** (flipped for the test) — flip back to
  Public after audit, or whenever (posting only works private until audited).
- Everything is $0 (FILE_UPLOAD = no host/CDN). Cron stays paused until you
  turn it on; only `pending` posts fire.
- The one-time `code` from the consent screen expires in minutes — grab a fresh
  one right before each link run.
</content>

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

## ▶️ MONDAY — START HERE (2026-06-29)
Goal: finish TikTok's audit so HP can post **public** on a schedule.
We're on the **Production** app's **App review** form (developers.tiktok.com →
HP Auto Poster → Production). It's down to **2 blockers**:

1. **Domain verification of `hplandscapingllc.com`** (3 of the 4 form errors).
   TikTok's ToS / Privacy / Web URLs all show "This URL is not verified."
   Fix path: App → **URL properties** tab → add property → **Domain (DNS record)**
   → TikTok gives a `TXT` record → add it in the domain's DNS → Verify. Verifying
   the Domain clears all 3 URL errors at once.
   - 🔑 **BLOCKER / first question Monday:** *who manages hplandscapingllc.com?*
     (self on Wix/GoDaddy/Squarespace/etc., or a person/agency who built it.)
     Whoever can edit the site/DNS adds the TXT record in ~2 min. Owner didn't
     know offhand — find this out first.
   - Alt method: "URL prefix → signature file" (upload TikTok's file to the
     site) if DNS access is easier than expected. Either clears the URL errors.

2. **Demo video** (the 4th error). A ~30s screen recording: open the authorize
   link → tap Allow → show redirect → open TikTok app → show a posted video.
   Upload to the App review "demo video" spot. (TikTok is strict here; the
   headless-automation shape may need a revision pass.)

### Already filled on the Production form ✅
icon (green HP), name, category=Business, description, ToS + Privacy URLs
(https://hplandscapingllc.com/index.html), platform=Web + Web/Desktop URL,
scope explanation text (the paragraph), products Login Kit + Content Posting API.
**Still to set on Production:** add scope **`video.publish`** + remove
**`video.upload`**; add Login Kit **redirect URI**
`https://hplandscapingllc.com/tiktok/callback`; turn **Direct Post** ON. (These
were done in the sandbox but NOT yet on Production.)

### After the audit is APPROVED
3. Set HP's TikTok back to **Public**; set
   `BRAND_HP_TIKTOK_PRIVACY_LEVEL` = `PUBLIC_TO_EVERYONE`.
4. **Persist the refresh token for the unattended cron:** add a `GH_PAT`
   (fine-grained PAT, Secrets:write) repo secret, then re-run the
   **TikTok link** workflow once with a fresh code — it auto-stores
   `BRAND_HP_TIKTOK_REFRESH_TOKEN` (never printed).
5. Un-pause the cron (`.github/workflows/social-post.yml`) / flip queue items to
   `pending` when ready to go live.

### Interim option (optional, works today, no audit)
Run it posting **private** (SELF_ONLY) on a schedule to watch it work over time;
flip to public after the audit. (HP account is currently set to Private from the
test — leave it private for this, or flip back to Public anytime.)

## Notes
- Account is currently set to **Private** (flipped for the test) — flip back to
  Public after audit, or whenever (posting only works private until audited).
- Everything is $0 (FILE_UPLOAD = no host/CDN). Cron stays paused until you
  turn it on; only `pending` posts fire.
- The one-time `code` from the consent screen expires in minutes — grab a fresh
  one right before each link run.
</content>

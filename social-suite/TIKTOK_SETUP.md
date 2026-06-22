# TikTok connection — setup guide (for the parallel Claude Code session)

Goal: let the social suite post HP Landscaping + Restore clips to **TikTok**, on the
same rules as the rest of the suite: **$0, no credit card, nothing posts until the
owner approves.** TikTok dev accounts are free and need no card.

> Honest caveat (read first): TikTok's Content Posting API, while your app is
> **unaudited**, can only post to **your own** connected TikTok account(s) and forces
> videos to **SELF_ONLY (private)** until TikTok approves the app for public posting.
> That's fine here — the suite already holds everything for manual approval. Public,
> multi-account auto-posting needs the app to pass TikTok's audit later (free, but a
> review). This mirrors the Meta "dev mode" situation we already accepted.

---

## PART A — Browser steps (owner does these; Claude walks them through)
1. Go to **developers.tiktok.com** → log in with the HP TikTok account → **Manage apps**
   → **Connect an app** (create one, e.g. "HP Social Suite"). Free, no card.
2. In the app, **add products**: **Login Kit** and **Content Posting API**.
   - Under Content Posting API choose **Direct Post**.
3. **Scopes**: enable `user.info.basic`, `video.upload`, `video.publish`.
4. **Redirect URI**: add `https://localhost/callback` (we'll use a manual code paste,
   no server needed) — or any URI you control.
5. Copy the **Client Key** and **Client Secret** (keep them private).
6. **Add target users / testers**: add the HP TikTok account (and Restore's) as
   testers so the unaudited app can post to them.
7. (Only if using PULL_FROM_URL later) verify a **URL Prefix** you own. We'll use
   **FILE_UPLOAD** (direct bytes) instead, so you can skip this.

## PART B — Get an access token per account (OAuth, manual paste)
For EACH brand account (HP, then Restore):
1. Build the authorize URL (Claude will fill in CLIENT_KEY):
   `https://www.tiktok.com/v2/auth/authorize/?client_key=CLIENT_KEY&scope=user.info.basic,video.upload,video.publish&response_type=code&redirect_uri=https://localhost/callback&state=hp`
2. Open it, log into the brand's TikTok, approve. The browser redirects to
   `https://localhost/callback?code=XXXX&...` — copy the **code** value from the URL.
3. Exchange it for tokens (Claude runs this, or owner pastes in a terminal):
   ```
   curl -X POST https://open.tiktokapis.com/v2/oauth/token/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "client_key=CLIENT_KEY&client_secret=CLIENT_SECRET&code=XXXX&grant_type=authorization_code&redirect_uri=https://localhost/callback"
   ```
   Save from the JSON: `access_token`, `refresh_token`, `open_id`, `expires_in`.
   (Tokens are short-lived; the `refresh_token` flow renews them — same pattern as
   Dropbox in this repo.)

## PART C — Wire into the repo (Claude implements)
1. **GitHub Secrets** (repo Settings → Secrets → Actions), flat per-brand:
   `BRAND_HP_TIKTOK_CLIENT_KEY`, `BRAND_HP_TIKTOK_CLIENT_SECRET`,
   `BRAND_HP_TIKTOK_ACCESS_TOKEN`, `BRAND_HP_TIKTOK_REFRESH_TOKEN`,
   `BRAND_HP_TIKTOK_OPEN_ID` (and the same `BRAND_RESTORE_TIKTOK_*` set).
2. **`services/publish/brands.py`** — extend `_from_flat_env()` / `_FLAT_FIELDS` to
   parse the `TIKTOK_*` suffixes into the existing `BrandCreds.tiktok` sub-dict
   (`{"client_key","client_secret","access_token","refresh_token","open_id"}`).
3. **New publisher** `services/publish/tiktok.py`:
   - Refresh the access token if expired (POST `/v2/oauth/token/`,
     `grant_type=refresh_token`).
   - Direct Post via **FILE_UPLOAD**: POST `/v2/post/publish/video/init/` with
     `{"post_info":{"title": <caption>, "privacy_level":"SELF_ONLY"}, "source_info":
     {"source":"FILE_UPLOAD","video_size":N,"chunk_size":N,"total_chunk_count":1}}`,
     then PUT the bytes to the returned `upload_url`. Poll
     `/v2/post/publish/status/fetch/` until done.
   - Keep `privacy_level` SELF_ONLY until the app is audited.
4. **Hook into `run_due`** so a queued item with `"tiktok"` in `platforms` routes to
   this publisher — but ONLY when `status=="pending"`. Leave the cron paused; the
   suite still never posts on its own.
5. **Test** with one HP clip set to a private SELF_ONLY post, confirm it lands in the
   HP TikTok as private, then delete it. Do NOT flip anything to public.

## Constraints to preserve (do not violate)
- **Nothing posts automatically.** Poster only fires `status=="pending"`; keep the
  cron in `.github/workflows/social-post.yml` commented out.
- **$0 / no credit card.** TikTok dev + API are free; never add billing.
- Per-brand only — an HP clip can only ever go to HP's TikTok.
- Commit trailers used in this repo:
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` and the `Claude-Session:`
  line. Never put any model identifier in commits/PRs/code.
- Read `CLAUDE.md` and `STYLE_PROFILE.md` first for full project context.

---

### Ready-to-paste prompt for the other Claude Code session
> I'm working in the `claude-code-config` repo (social-suite). Read
> `social-suite/TIKTOK_SETUP.md`, `social-suite/services/publish/brands.py`, and
> `CLAUDE.md` first. Goal: connect my HP Landscaping and Restore **TikTok** accounts
> so the suite can post to them — but keep the hard rules: $0, no credit card, and
> **nothing posts until I approve** (poster only fires `status=="pending"`, cron stays
> off). Walk me through the TikTok developer-portal steps (Part A/B), then implement
> Part C (brands.py TikTok creds, a `tiktok.py` Direct-Post publisher using
> FILE_UPLOAD + SELF_ONLY privacy, and routing in `run_due`). Add the
> `BRAND_HP_TIKTOK_*` / `BRAND_RESTORE_TIKTOK_*` GitHub secrets. Commit to `main`.
> Don't post anything public; test one private SELF_ONLY clip then delete it.

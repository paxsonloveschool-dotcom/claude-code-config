# TikTok setup — WHERE WE LEFT OFF (resume here tomorrow)

Plain-English progress tracker for linking HP's TikTok to the auto-poster.
Full technical guide: [`TIKTOK_SETUP.md`](TIKTOK_SETUP.md).

## Account info (so we don't get stuck again)
- HP TikTok login email: **higherpurposelandscaping@gmail.com**
- HP website: **https://hplandscapingllc.com**
- Developer app name: **HP Auto Poster** (type: Individual)
- Redirect URI we're using (must match EXACTLY everywhere):
  **`https://hplandscapingllc.com/tiktok/callback`**

## ✅ Done so far
1. Recovered HP TikTok login (reset password via the Gmail). Logged in.
2. Logged into the developer site (developers.tiktok.com).
3. Created the app **"HP Auto Poster"** (Individual).
4. Added products: **Login Kit** + **Content Posting API**.

## ⏳ Pick up here — remaining portal clicks (all on developers.tiktok.com, app page)
Ignore the big **"App review"** section (demo video, Terms URL, etc.) — that's
only needed LATER to go public. We're doing a PRIVATE test first.

1. **Finish the redirect URI (Login Kit).**
   - Scroll to the sentence: *"Add up to 10 Redirect URIs..."*
   - Click **Web** directly under THAT sentence (not the one near the top).
   - Turn ON **Configure for Web**.
   - Paste `https://hplandscapingllc.com/tiktok/callback` → **Add** → **Save**.
2. **Turn on Direct Post (Content Posting API section).**
   - Toggle **Direct Post** ON.
   - SKIP "Verify domains" — we use push_by_file (FILE_UPLOAD), which needs no
     domain verification.
3. **Add the `video.publish` scope.**
   - In the **Scopes** section, use **Search**, type `video.publish`, **Add**.
   - (Currently only `user.info.basic` + `video.upload` are present.)
4. **Save the app.**
5. **Sandbox + add HP as a tester.**
   - Open/create a **Sandbox** for the app.
   - Add HP's TikTok account as a **Target User / tester** (required — an
     unaudited app can ONLY post to testers, even a private SELF_ONLY post).
6. **Copy the Client Key + Client Secret** (eye/copy icon next to each under
   **Credentials**). Keep them private — paste them to Claude in chat.

## 🤝 Then Claude takes over (the technical part)
7. Claude generates the **authorize link** (uses the Client Key + redirect URI).
8. Owner opens it, clicks **Allow**; TikTok redirects to
   `https://hplandscapingllc.com/tiktok/callback?code=THE_CODE&...`.
   Copy the WHOLE address bar and paste it to Claude.
9. Claude runs `tiktok_oauth.py exchange` → gets the **refresh_token**.
10. Claude stores GitHub Secrets per brand:
    - `BRAND_HP_TIKTOK_REFRESH_TOKEN`
    - `BRAND_HP_TIKTOK_CLIENT_KEY`
    - `BRAND_HP_TIKTOK_CLIENT_SECRET`
    - `BRAND_HP_TIKTOK_PRIVACY_LEVEL` = `SELF_ONLY` (private; flip to
      `PUBLIC_TO_EVERYONE` after TikTok audits the app)
11. Claude runs ONE private `SELF_ONLY` test post from a local clip; owner
    confirms it in the TikTok app, then deletes it.

## Reminder
- Nothing posts on its own — the cron stays paused; only `pending` posts fire.
- This whole thing is $0 (FILE_UPLOAD = no public host/CDN needed).
- Posts stay PRIVATE (SELF_ONLY) until TikTok's free audit; then they can go public.
</content>
</invoke>

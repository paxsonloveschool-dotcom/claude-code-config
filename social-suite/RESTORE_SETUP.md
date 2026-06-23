# Add Restore — the simple checklist (do this next session)

HP is already live. This adds **Restore Marketing** the exact same way, so it
posts to **its own** Facebook Page (kept totally separate from HP). ~10 minutes.
Full detail lives in `META_SETUP.md`; this is the short, do-this-now version.

> You'll collect **2 values** for Restore: its **Page token** and its **Page ID**
> — same two you already did for HP. Then you add them to the `BRANDS_JSON`
> secret next to HP. That's it.

---

## Step 1 — make sure Restore's Instagram is a Professional account linked to its Page
(Only needed if you'll do Restore on Instagram later. For Facebook-only you can
skip to Step 2.) In the Instagram app → Restore's profile → Settings → **Account
type → Switch to Professional** → link it to Restore's Facebook Page.

## Step 2 — create a second Meta app for Restore
1. Go to **developers.facebook.com → My Apps → Create App**.
2. Type: **Business**. Name it e.g. **"Restore Publisher"**.
3. **Leave it in Development Mode.** (Do NOT go Live, do NOT request Advanced
   Access, do NOT start verification — none are needed to post to your own page.)
4. Add the **Instagram Graph API** product.

## Step 3 — mint Restore's Page token (Graph API Explorer)
1. Open **developers.facebook.com/tools/explorer**.
2. Top-right **Meta App** dropdown → pick **Restore Publisher**.
3. **Get User Access Token** with these permissions checked:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
   `instagram_basic`, `instagram_content_publish`, `business_management`.
4. Generate → approve the popup → copy the token (short-lived, that's fine).
5. Exchange it for a long-lived one, then pull the Page token — both curl
   commands are in `META_SETUP.md` section (d). The **Page** `access_token` it
   returns is Restore's **`meta_access_token`**; the Page `id` is Restore's
   **`fb_page_id`**. (Ignore the `1784…` number — that's Instagram, for later.)

## Step 4 — add Restore to the secret (next to HP)
**EASIEST METHOD — flat secrets (no JSON, nothing to mangle).** Each secret is
**one pasted value** — no braces, quotes, or commas. Go to **repo → Settings →
Secrets and variables → Actions → New repository secret** and create these four
(name on the left, value = the matching token/ID you saved, nothing else):

| Secret name | Value |
|---|---|
| `BRAND_HP_META_ACCESS_TOKEN` | HP's `EAA…` Page token |
| `BRAND_HP_FB_PAGE_ID` | HP's Page ID (numbers) |
| `BRAND_RESTORE_META_ACCESS_TOKEN` | Restore's `EAA…` Page token |
| `BRAND_RESTORE_FB_PAGE_ID` | Restore's Page ID (numbers) |

(Optional, only when doing Instagram: `BRAND_HP_IG_USER_ID`,
`BRAND_RESTORE_IG_USER_ID`.)

These **override** `BRANDS_JSON` automatically, so you can ignore/delete the old
`BRANDS_JSON` secret — a broken one can't block this path. The poster also
trims stray spaces/newlines from each value, so a copy-paste wobble won't break it.

## Step 5 — verify (nothing posts yet — everything's still paused)
Tell me "added Restore" and I'll:
1. Flip `restore-001` back to `pending` and re-stamp fresh schedules.
2. Run a one-off check that Restore's token is valid (read-only, no posting).
3. When you say go, un-pause and the robot starts posting **both** brands to
   **their own** pages on schedule.

---

### Reminder: content stays separate
Every post is tagged with its `brand` (`hp` or `restore`). HP content can only
ever go to HP's accounts and Restore's only to Restore's — enforced in the
queue, never mixed.

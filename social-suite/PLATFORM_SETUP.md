# Platform Developer-App Setup & Approval Guide

To post programmatically, each platform makes you register a **developer app**
and (for most) pass a **review/audit**. This is the slowest part of the whole
project — so **start these now, in parallel**, while the code is built. They
approve while you wait.

The credentials you collect here get pasted into **Postiz** (Settings → each
channel), which handles the actual OAuth/posting. Keep every key in a password
manager as you go.

> **Order matters** — do them in this order (fastest approval first):
> **1) X → 2) YouTube → 3) LinkedIn → 4) Meta (IG/FB) → 5) TikTok.**

You'll also need two things ready that every reviewer asks for:
- A **public privacy policy URL** and **terms URL** (a simple page on your
  business site is fine — I can generate the text).
- Your business name, website, and a short description of "what the app does"
  (use: *"Schedules and publishes our own marketing content to our own
  accounts."*).

---

## 1. X / Twitter  — *fastest, ~minutes to a day*
1. Go to **developer.x.com** → sign in with your business X account → **Sign up for Free**.
2. Create a **Project** + **App**. For the use-case, pick "Making a bot / Publishing content."
3. In the app's **Keys and tokens**, generate and copy:
   - **API Key** + **API Key Secret**
   - **Access Token** + **Access Token Secret**
   - **Client ID** + **Client Secret** (for OAuth 2.0)
4. In **User authentication settings**: enable **OAuth 2.0**, set app permissions to **Read and Write**, and add Postiz's callback URL (Postiz shows it when you add the X channel).
5. ⚠️ Free tier has low monthly post caps; fine to start. Paid "Basic" tier if you scale.
→ Paste the keys into Postiz → Add Channel → X.

---

## 2. YouTube  — *fast app, but OAuth verification can take ~1-2 weeks*
1. Go to **console.cloud.google.com** → create a **Project** (e.g. "Social Suite").
2. **APIs & Services → Library →** enable **YouTube Data API v3**.
3. **OAuth consent screen:** choose **External**, fill app name, your email, the
   privacy/terms URLs, and add the scope `.../auth/youtube.upload`. Add yourself
   as a **Test user** so you can use it immediately while verification is pending.
4. **Credentials → Create OAuth client ID → Web application.** Add Postiz's
   redirect URL. Copy the **Client ID** + **Client Secret**.
5. ⚠️ To post for non-test users (or remove the "unverified app" screen), submit
   for **OAuth verification** (Google reviews; ~days–2 weeks). You can post to
   your *own* channel as a test user immediately.
→ Paste into Postiz → Add Channel → YouTube.

---

## 3. LinkedIn  — *app instant, posting scope review ~days*
1. Go to **developer.linkedin.com** → **Create app**. Link it to your LinkedIn
   **Company Page** (you must be an admin of the Page).
2. Under **Products**, request **"Share on LinkedIn"** and **"Sign In with LinkedIn
   using OpenID Connect."** (Posting needs the `w_member_social` scope.)
3. In **Auth**, copy the **Client ID** + **Client Secret**, and add Postiz's
   redirect URL.
4. ⚠️ The "Share" product is review-gated — approval is usually quick (days) once
   your Page + app details are filled in.
→ Paste into Postiz → Add Channel → LinkedIn.

---

## 4. Meta — Instagram + Facebook  — *the big one, App Review ~1-3 weeks*
Both IG and FB run through **one** Meta app.
**Prerequisites (free, do first):**
- Convert each Instagram to a **Business or Creator** account.
- Link each Instagram to its **Facebook Page**.
- Have a **Meta Business Suite / Business Portfolio** for your business.

**Steps:**
1. Go to **developers.facebook.com** → **My Apps → Create App** → type **Business**.
2. Add products: **Facebook Login** and **Instagram** (Instagram Graph API / Content Publishing).
3. In **App settings → Basic**, add privacy policy URL, business info, and complete
   **Business Verification** (Meta verifies your business is real — upload docs;
   this is the step that takes the longest).
4. Add Postiz's OAuth redirect URL under Facebook Login settings.
5. Request these permissions, then submit for **App Review** with a short
   screencast of the use-case:
   - `pages_manage_posts`, `pages_read_engagement`, `pages_show_list`
   - `instagram_basic`, `instagram_content_publish`, `business_management`
6. While in "Development mode," you can post to accounts where you're an admin —
   so you may be able to test before full approval.
7. Copy **App ID** + **App Secret**.
→ Paste into Postiz → Add Channel → Facebook, then Instagram.

> ⚠️ Reality: Meta review is the slowest and pickiest. Apply **first among the
> slow ones**, keep the use-case description simple ("publishing our own content
> to our own accounts"), and expect 1–3 weeks plus possible back-and-forth.

---

## 5. TikTok  — *audit required, ~1-2 weeks*
1. Go to **developers.tiktok.com** → register → **Manage apps → Connect an app**.
2. Add the **Content Posting API** product.
3. Fill app details + privacy/terms URLs. Copy **Client Key** + **Client Secret**.
4. Add Postiz's redirect URL.
5. ⚠️ Until your app passes **audit**, the Content Posting API only posts as
   **private/SELF_ONLY** drafts. Submit for audit to enable public posting
   (TikTok reviews; ~1–2 weeks).
→ Paste into Postiz → Add Channel → TikTok.

---

## Tracking sheet (fill as you go)
| Platform | App created | Keys saved | Submitted for review | Approved | In Postiz |
|---|---|---|---|---|---|
| X | ☐ | ☐ | n/a | n/a | ☐ |
| YouTube | ☐ | ☐ | ☐ | ☐ | ☐ |
| LinkedIn | ☐ | ☐ | ☐ | ☐ | ☐ |
| Meta (IG+FB) | ☐ | ☐ | ☐ | ☐ | ☐ |
| TikTok | ☐ | ☐ | ☐ | ☐ | ☐ |

## What I can do for you on this
- Generate the **privacy policy + terms** text you'll need for every submission.
- Draft the **app description / use-case blurb** and the review screencast script.
- Tell you exactly which **Postiz redirect URL** to paste once your Postiz host is up.

Just say which and I'll produce it.

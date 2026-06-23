# App Review Submission Pack

Copy-paste answers for the developer-app forms and review submissions. Replace
[BUSINESS NAME] / [YOURSITE] / [CONTACT EMAIL]. Keep the framing consistent
everywhere: **an internal tool that publishes our own content to our own
accounts** — reviewers approve this use-case readily.

---

## Short app description (use everywhere a 1-2 liner is asked)
> [BUSINESS NAME]'s internal tool for scheduling and publishing our own marketing
> content (videos, images, captions) to our own business social media accounts.

## Detailed description (longer "what does your app do" fields)
> This application is used solely by [BUSINESS NAME] to manage our own social
> media presence. We upload our own video and image content, the app helps format
> and caption it, and then schedules and publishes it to our own connected
> business accounts. It is not offered to third parties and does not access or
> collect data from other users or audiences. Authentication uses the platform's
> official OAuth, and we only request the permissions necessary to publish our own
> posts.

## How users connect / data handling (common field)
> We connect only our own accounts via official OAuth. Access tokens are stored
> securely and used exclusively to publish our content. We do not sell or share
> data. Users can revoke access at any time through the platform's settings. See
> our Privacy Policy: https://[YOURSITE]/privacy and Terms: https://[YOURSITE]/terms.

---

## Meta (Instagram + Facebook) — per-permission justifications
Paste each next to the matching permission in App Review. Reference your
screencast (below).

- **pages_show_list** — "To list the Facebook Pages we own so we can select which
  of our own Pages to publish to."
- **pages_read_engagement** — "To confirm our Page connection and read basic Page
  info needed to publish to our own Page."
- **pages_manage_posts** — "To publish and schedule posts to our own Facebook
  Page, which is the core function of our internal tool."
- **instagram_basic** — "To identify and connect our own Instagram Professional
  account that is linked to our Facebook Page."
- **instagram_content_publish** — "To publish our own photos/videos to our own
  Instagram Professional account, the core function of our tool."
- **business_management** — "To access the business assets (Pages/IG accounts) we
  own within our Business Portfolio so the tool can publish to them."

**Meta screencast must show:** logging in → granting permissions → selecting our
own Page/IG → composing a post → it appearing on our own Page/IG. (See script.)

---

## TikTok (Content Posting API) — audit notes
> Our app posts our own short-form videos to our own TikTok account. We request
> the Content Posting API to upload and publish videos we create. We comply with
> TikTok's content sharing guidelines and only post to accounts we own and have
> authenticated via OAuth.

## YouTube (OAuth verification) — justification
> We use the YouTube Data API v3 (youtube.upload scope) to upload our own videos
> to our own YouTube channel. The app is an internal publishing tool; we do not
> access other users' data.

## LinkedIn (Share product) — justification
> We use w_member_social / Share on LinkedIn to publish our own company updates to
> our own LinkedIn Company Page. Internal marketing use only.

## X / Twitter
> Read and Write access to publish our own marketing posts to our own X account.

---

## Review screencast script (≈60-90 seconds, for Meta/TikTok)
Record your screen narrating these steps. Keep it simple and literal — reviewers
just need to see the real flow on your own accounts.

1. "This is [BUSINESS NAME]'s internal content scheduling tool."
2. "I'm clicking Connect, and logging into our own [Facebook/Instagram/TikTok]
   account via the official login."
3. "I grant the requested permissions." (show the consent screen)
4. "I select our own [Page / Instagram / channel]." (show it's your account)
5. "I compose a post — here's our video and caption — and schedule/publish it."
6. "Here is the post now live on our own [Page/Instagram/TikTok]." (show it)
7. "That's the complete use of the requested permissions — publishing our own
   content to our own accounts."

Tip: do this against a real connected account in Development/Sandbox mode so you
have something genuine to show.

---

## Reviewer-ready facts sheet (have these on hand)
| Field | Value |
|---|---|
| App name | [BUSINESS NAME] Social Publisher |
| Company | [BUSINESS NAME] |
| Website | https://[YOURSITE] |
| Privacy policy | https://[YOURSITE]/privacy |
| Terms | https://[YOURSITE]/terms |
| Contact email | [CONTACT EMAIL] |
| Use case | Internal — publish our own content to our own accounts |
| Who uses it | [BUSINESS NAME] staff only |
| Data sold/shared? | No |

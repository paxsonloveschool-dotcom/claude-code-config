# Meta App Review — Copy-Paste Submission Pack

Use this once **Business Verification is approved**. For each permission, Meta asks
"Tell us how your app uses this permission" + wants a screencast. Paste the matching
blurb below and follow the screencast script at the bottom.

**Context line (reusable):** HP Landscaping is a landscaping design-and-build company in
College Station, TX. This app is our **own first-party assistant** for our **own**
Facebook Page and linked Instagram business account. It auto-answers common customer
questions and routes pricing/quote requests to a human. It does not serve other
businesses and does not access data beyond our own Page/IG account.

---

## Permission justifications

**pages_messaging**
> We use pages_messaging to read inbound Messenger messages sent to our own HP
> Landscaping Page and reply automatically. The assistant answers common questions
> (services offered, hours, service area, financing, warranty) and, for pricing/quote
> requests, sends a brief "a team member will follow up" reply while notifying our
> staff. Used only on our own Page, only in response to customers who messaged us first.

**pages_manage_metadata**
> We use pages_manage_metadata to subscribe our own Page to webhooks so the app is
> notified in real time when a customer sends a message or comments on a post. This is
> required for the assistant to receive and respond to those events.

**pages_read_engagement**
> We use pages_read_engagement to read the text of comments customers leave on our own
> Page's posts, so the assistant can understand the question and respond appropriately.

**pages_manage_engagement**
> We use pages_manage_engagement to reply to comments on our own Page's posts — publicly
> for general questions, and via a private reply (direct message) when a customer asks
> for pricing or personal details.

**instagram_manage_messages**
> We use instagram_manage_messages to read and respond to Instagram Direct messages sent
> to our own connected Instagram business account, the same way as Messenger above.

**instagram_manage_comments**
> We use instagram_manage_comments to read and respond to comments on our own Instagram
> business account's posts.

**pages_show_list** (if requested)
> We use pages_show_list only during setup to let us select our own HP Landscaping Page
> to connect the assistant to.

---

## Screencast script (record after the Page connection works)

Meta wants a short screen recording showing each permission in real use. Record one
2–4 min video showing, in order:

1. **Login/setup:** show logging into the app and selecting the HP Landscaping Page
   (covers pages_show_list).
2. **Messenger auto-reply:** from a test profile, send the Page a DM like "what areas do
   you cover?" → show the assistant's automatic reply (pages_messaging).
3. **Comment reply:** comment a basic question on a Page post → show the public reply;
   comment a pricing question → show the private DM reply (pages_read_engagement,
   pages_manage_engagement).
4. **Pricing handoff:** DM "how much for a patio?" → show the "a team member will follow
   up" reply + the staff alert (pages_messaging).
5. **Instagram:** repeat the DM + comment demo on the connected IG business account
   (instagram_manage_messages, instagram_manage_comments).

Narrate briefly what each step shows. Upload the video in the App Review submission.

## Other submission fields (already prepared)

- **Privacy Policy URL:** https://social-ai-responder.higherpurposelandscaping.workers.dev/privacy
- **Data Deletion URL:** https://social-ai-responder.higherpurposelandscaping.workers.dev/data-deletion
- **Category:** Business and Pages
- **App icon, contact email:** set in App Settings → Basic

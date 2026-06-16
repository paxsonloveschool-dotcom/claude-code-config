# HP Landscaping — Gmail Auto-Drafter (always-on)

Runs on Google's servers 24/7 (active 8 AM–7 PM Central), independent of any chat session.
For each new client email it drafts a reply in HP's voice, labels it `📝 Email In Draft` + the
client's name, and **never sends**. ~Fractions of a cent per email.

## One-time setup (~10 minutes)

### 1. Get an Anthropic API key
- Go to https://console.anthropic.com → **API Keys** → **Create Key**. Copy it.
- Add a payment method under **Billing** (usage is tiny — Haiku is ~$0.001–0.005 per email).

### 2. Create the Apps Script project
- Go to https://script.google.com → **New project**.
- Sign in as **higherpurposelandscaping@gmail.com** (must be this account).
- Delete the placeholder code, paste the full contents of **Code.gs**, click 💾 Save.
- Rename the project (top-left) to `HP Gmail Auto-Drafter`.

### 3. Add your API key (kept out of the code)
- Click the ⚙️ **Project Settings** (left sidebar) → scroll to **Script Properties** →
  **Add script property**:
  - Property: `ANTHROPIC_API_KEY`
  - Value: *(paste your key from step 1)*
- Save.

### 4. Authorize + install the schedule
- Back in the **Editor** (`< >` icon), pick the function **`setup`** in the toolbar dropdown →
  click **Run**.
- A Google permission popup appears → **Review permissions** → choose the account →
  "Google hasn't verified this app" → **Advanced** → **Go to HP Gmail Auto-Drafter (unsafe)** →
  **Allow**. (This is your own script; it only touches your Gmail + calls the Claude API.)
- Done. The execution log should say *"Setup complete."*

That's it. It now runs every 30 minutes, 8 AM–7 PM Central, drafting new client mail.

## Verify it works
- Send a test email to the inbox from another address (e.g. *"Hi, I'd like a quote to redo my
  backyard"*).
- In the Editor, run **`runAutoDrafter`** once manually (or wait for the next 30-min tick).
- Check Gmail: the thread should have a **draft reply** + the `📝 Email In Draft` and name labels.

## Controls
- **Pause:** Editor → run the **`stop`** function (removes the trigger). Or ⏰ **Triggers** → delete.
- **Resume:** run **`setup`** again.
- **Higher-quality drafts:** edit `CLAUDE_MODEL` to `'claude-sonnet-4-6'` (slightly higher cost).
- **Change hours:** edit `BUSINESS_START_HOUR` / `BUSINESS_END_HOUR`.
- **See activity / errors:** Editor → **Executions** (left sidebar).

## Notes
- It **never sends** — `createDraftReply` only creates drafts you review and send yourself.
- It only drafts mail received **after** you ran `setup()` — the existing backlog is left alone.
- It skips automated/marketing/billing/personal senders, and Claude double-checks each one is a
  real client/business inquiry before drafting.

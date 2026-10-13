# LSA Lead Sync — Google LSA leads → "LSA" Google Sheet

Auto-logs every Google Local Services Ads lead into the HP Landscaping **LSA** spreadsheet. Runs every 10 minutes, dedupes by Gmail message ID, never touches existing rows.

## Why this design

Google offers no native LSA → Sheets export. The reliable free path is: LSA sends a notification email per lead → an Apps Script bound to the sheet reads that inbox and appends a row. The script must live on **the account that receives the lead emails** (higherpurposelandscaping@gmail.com), which is why it can't be installed remotely.

## Install (2 minutes, one time)

Do this in Chrome while signed into the **HP Landscaping main account**:

1. Open the **LSA** spreadsheet
2. **Extensions → Apps Script**
3. Delete any placeholder code, paste the full contents of `Code.gs`
4. Save (Ctrl+S)
5. In the function dropdown at top, select **`setup`** → click **Run**
6. Approve the permission prompts (Gmail read + Sheets — it will warn "unverified app"; click *Advanced → Go to project*)

Done. `setup()` builds the **Leads** tab, installs the 10-minute trigger, and immediately backfills leads from the last 30 days.

## What lands in the sheet

| Received | Lead Name | Phone | Job Type | Lead Type | Status | Notes | Email Subject | Gmail Message ID |
|---|---|---|---|---|---|---|---|---|

- **Status** starts as `New` — edit it by hand as leads are worked (Contacted / Booked / Lost)
- **Notes** is yours; the script never overwrites either column
- If Google changes their email template and a field can't be parsed, the row still logs with `(see email)` so no lead is ever silently dropped

## Verify it's working

- Apps Script editor → **Executions** (left sidebar) shows each run and how many leads were appended
- Or wait for the next LSA lead email and check the sheet within 10 minutes

## Troubleshooting

| Symptom | Fix |
|---|---|
| No rows appear, but lead emails exist | Check the emails' From address; if it's not one already in `GMAIL_QUERY` in `Code.gs`, add it |
| Duplicate rows | Only possible if the Gmail Message ID column was manually cleared — don't delete that column |
| Trigger stopped | Re-run `setup()` — it replaces the trigger cleanly |
| Backfill older than 30 days wanted | Change `newer_than:30d` in `GMAIL_QUERY`, run `syncLeads()` once, change it back |

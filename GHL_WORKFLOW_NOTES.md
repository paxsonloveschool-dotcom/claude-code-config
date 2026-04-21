# GHL Workflow Notes — HP Landscaping

## Access Info
- **Platform:** GoHighLevel (app.gohighlevel.com)
- **Agency:** Restore Marketing (restoremarketingco@gmail.com)
- **Auth:** Sign in with Google
- **HP Landscaping Location ID:** Gqozcy4LpsUukpaWg9b3
- **Workflows URL:** https://app.gohighlevel.com/v2/location/Gqozcy4LpsUukpaWg9b3/automation/list

## MCP Wiring
Config lives in `.mcp.json` (checked in, no secrets). Claude Code expands
`${GHL_API_KEY}` and `${GHL_LOCATION_ID}` from the shell env at launch.

**One-time setup on a new machine:**
1. `cp .env.example .env`
2. Paste PIT token into `.env` (GHL → Settings → Private Integrations → Create)
3. `set -a && . ./.env && set +a` (or use direnv / your shell's autoload)
4. `./scripts/ghl-check.sh` — verifies token + probes `@highlevel/mcp-server`
5. Restart Claude Code so it re-reads `.mcp.json`

**Switching sub-accounts:** override `GHL_LOCATION_ID` in `.env` or the shell.
Default is HP Landscaping (`Gqozcy4LpsUukpaWg9b3`).


## Sub-Accounts
| Name | Address | Phone |
|------|---------|-------|
| Bison Metal Building | 14801 S Dowling Rd | 979-571-1241 |
| Blacktop Towing | 2009 Avenue A | 979-595-8524 |
| HP Landscaping | 14801 S Dowling St | 979-777-8851 |
| Language Learning Center | 943 William D. Fitch Pkwy | 979-260-5400 |
| Restore Marketing | 14801 S Dowling Rd | 979-777-8851 |

## Current Status
- Workflow is "already working and built"
- Needs "minor changes" (TBD — user to specify)
- Could not load workflow list yet — GHL SPA was slow to render

## Audit Attempts Log

### 2026-04-05 (Scheduled Task — 08:23)
- Chrome MCP (`switch_browser` → `tabs_context_mcp`) connected successfully
- `navigate` to `app.gohighlevel.com` timed out after 300s — GHL SPA too heavy for current Chrome extension state
- All subsequent Chrome MCP calls (`get_page_text`, etc.) also timed out
- **Root cause:** Chrome extension likely needs user interaction to recover; browser may be on login page awaiting Google SSO

### Required Action for Next Session
1. Open Chrome manually and navigate to https://app.gohighlevel.com
2. Sign in with Google (restoremarketingco@gmail.com) if not already authenticated
3. Then run the scheduled task or ask Claude to document workflows

## TODO
- [ ] Load workflow list from HP Landscaping sub-account (requires Chrome in authenticated state)
- [ ] Document all existing workflows
- [ ] Identify what needs minor changes
- [ ] Implement changes once identified
- [ ] Test and verify

---
*Last updated: 2026-04-05*

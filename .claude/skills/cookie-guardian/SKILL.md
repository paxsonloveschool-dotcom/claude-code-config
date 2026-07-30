---
name: cookie-guardian
description: >
  Fetch web pages with tracker cookies blocked at the network layer and
  cookie/consent banners auto-dismissed. Use when scraping a URL that (a) is
  gated behind a GDPR/CCPA consent wall, (b) has heavy tracker JS that
  interferes with reading, or (c) the user asks to "block cookies", "reject
  cookies", "dismiss the cookie banner", or scrape a page cleanly.
  Sits alongside agent-reach — prefer this over `agent-reach read` / Jina
  Reader when the target site has a consent overlay.
  Triggers: "block cookies", "reject cookies", "dismiss cookie banner",
  "cookie wall", "consent banner", "scrape without tracking",
  "fetch page without cookies", "gdpr popup".
---

# cookie-guardian — Usage Guide

Playwright-based helper. Blocks ~150 known tracker hosts via network route
interception, then clicks "Reject all" on the consent banner (falls back to
"Accept all" if reject isn't offered — mode is configurable).

## Prerequisites

```bash
cookie-guardian doctor          # verify install + chromium binary
```

If `doctor` reports missing playwright or chromium, run bootstrap.sh (it
installs both). Chromium lives at `/opt/pw-browsers/chromium` on Linux
sandboxes; on the user's Mac, `playwright install chromium`.

## Fetch a page cleanly

```bash
cookie-guardian fetch https://example.com --out /tmp/page.html
```

Writes rendered HTML (post-consent-click) to `/tmp/page.html`. Prints a
one-line status to stderr:

```
status=200 blocked=27 consent=reject via #onetrust-reject-all-handler
```

## Get a JSON summary instead of HTML

```bash
cookie-guardian fetch https://cnn.com --json --out /tmp/cnn.html
```

Output:

```json
{
  "url": "https://cnn.com",
  "status": 200,
  "blocked_count": 42,
  "consent_action": "reject",
  "consent_selector": "#onetrust-reject-all-handler",
  "html_bytes": 815234,
  "output_path": "/tmp/cnn.html"
}
```

## Screenshot after consent dismissal

```bash
cookie-guardian fetch https://example.com --screenshot /tmp/shot.png
```

## Debug a blocking rule

```bash
cookie-guardian block-check https://nytimes.com
```

Runs a fetch with consent dismissal OFF and prints the JSON summary — use
this to see what got blocked before adding/removing entries in
`tools/cookie-guardian/blocklist.txt`.

## Flags

| flag              | default    | notes                                        |
|-------------------|------------|----------------------------------------------|
| `--out FILE`      | stdout     | write HTML to file                           |
| `--consent MODE`  | `reject`   | `reject` \| `accept` \| `off`                |
| `--wait-ms N`     | `1500`     | ms to wait after DOMContentLoaded            |
| `--screenshot F`  | (none)     | full-page PNG                                |
| `--user-agent UA` | Chrome 131 | override UA                                  |
| `--headed`        | off        | show the browser (debug on local machines)   |
| `--json`          | off        | machine-readable summary                     |

## When NOT to use

- URL is a raw API endpoint (JSON, XML, RSS) — use `curl` / `agent-reach read`.
- URL is a YouTube/Twitter/Reddit page — use `agent-reach` channels; they
  hit better data sources than the rendered HTML.
- You need to log in — cookie-guardian runs stateless. Use agent-reach's
  cookie-configured channels or extend with a persistent user data dir.

## Extending

- **Add tracker hosts**: append to `tools/cookie-guardian/blocklist.txt`,
  one host per line, `#` for comments. Suffix match — `doubleclick.net`
  covers `stats.doubleclick.net` too.
- **Add banner selectors**: edit `tools/cookie-guardian/consent_selectors.json`.
  CSS selectors matched first, then role=button text matches. Reject-mode
  tries reject list first, then accept. Add both a CSS and a text fallback
  for new banners so it survives DOM churn.

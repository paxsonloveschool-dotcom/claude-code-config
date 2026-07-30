"""cookie-guardian — Playwright wrapper that blocks tracker cookies and
auto-dismisses consent banners so pages actually render for scraping/reading.

Usage:
    cookie-guardian fetch <url> [--out FILE] [--consent reject|accept|off]
                                [--wait-ms N] [--screenshot FILE]
                                [--headed] [--user-agent UA]
    cookie-guardian doctor            # verify install
    cookie-guardian block-check <url> # print what was blocked

Exit codes:
    0 = success, page fetched
    2 = navigation error (timeout, DNS, network)
    3 = install/config error (missing browser, bad JSON)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

try:
    from playwright.async_api import (
        Browser,
        BrowserContext,
        Page,
        Route,
        async_playwright,
    )
except ImportError:
    sys.stderr.write(
        "cookie-guardian: playwright not installed. "
        "Run: pip install playwright\n"
    )
    sys.exit(3)


ROOT = Path(__file__).resolve().parent
BLOCKLIST_PATH = ROOT / "blocklist.txt"
SELECTORS_PATH = ROOT / "consent_selectors.json"
CHROMIUM_PATH = os.environ.get("PLAYWRIGHT_CHROMIUM", "/opt/pw-browsers/chromium")


def load_blocklist(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    out: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line.lower())
    return out


def load_selectors(path: Path) -> dict:
    if not path.is_file():
        return {"css_selectors": {}, "text_fallback": {}}
    return json.loads(path.read_text())


def host_matches(request_url: str, blocklist: Iterable[str]) -> str | None:
    try:
        host = (urlparse(request_url).hostname or "").lower()
    except Exception:
        return None
    if not host:
        return None
    for entry in blocklist:
        e = entry.lower()
        if "/" in e:
            if e in request_url.lower():
                return entry
        elif host == e or host.endswith("." + e):
            return entry
    return None


@dataclass
class FetchResult:
    url: str
    status: int
    html: str
    blocked_urls: list[str] = field(default_factory=list)
    consent_action: str | None = None
    consent_selector: str | None = None


class Guardian:
    def __init__(
        self,
        consent_mode: str = "reject",
        blocklist_path: Path = BLOCKLIST_PATH,
        selectors_path: Path = SELECTORS_PATH,
        chromium_path: str = CHROMIUM_PATH,
        user_agent: str | None = None,
        headed: bool = False,
    ):
        if consent_mode not in {"reject", "accept", "off"}:
            raise ValueError(f"bad consent_mode: {consent_mode}")
        self.consent_mode = consent_mode
        self.blocklist = load_blocklist(blocklist_path)
        self.selectors = load_selectors(selectors_path)
        self.chromium_path = chromium_path
        self.user_agent = user_agent or (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        self.headed = headed

    async def _launch(self, pw) -> Browser:
        launch_kwargs = {"headless": not self.headed}
        if self.chromium_path and Path(self.chromium_path).exists():
            launch_kwargs["executable_path"] = _resolve_chromium_binary(
                self.chromium_path
            )
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        if proxy_url:
            bypass = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
            proxy_conf: dict = {"server": proxy_url}
            if bypass:
                proxy_conf["bypass"] = bypass
            launch_kwargs["proxy"] = proxy_conf
        return await pw.chromium.launch(**launch_kwargs)

    async def _new_context(self, browser: Browser) -> BrowserContext:
        return await browser.new_context(
            user_agent=self.user_agent,
            viewport={"width": 1440, "height": 900},
            java_script_enabled=True,
        )

    async def _install_route_blocker(self, context: BrowserContext, sink: list[str]):
        async def handler(route: Route):
            url = route.request.url
            hit = host_matches(url, self.blocklist)
            if hit:
                sink.append(url)
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", handler)

    async def _dismiss_consent(self, page: Page) -> tuple[str | None, str | None]:
        if self.consent_mode == "off":
            return None, None
        modes = (
            ["reject", "accept"]
            if self.consent_mode == "reject"
            else ["accept", "reject"]
        )
        css = self.selectors.get("css_selectors", {})
        txt = self.selectors.get("text_fallback", {})
        for mode in modes:
            for sel in css.get(mode, []):
                try:
                    el = await page.query_selector(sel)
                    if el and await el.is_visible():
                        await el.click(timeout=2000)
                        return mode, sel
                except Exception:
                    continue
            for phrase in txt.get(mode, []):
                try:
                    el = page.get_by_role("button", name=phrase, exact=False)
                    if await el.count() > 0 and await el.first.is_visible():
                        await el.first.click(timeout=2000)
                        return mode, f"text:{phrase}"
                except Exception:
                    continue
        return None, None

    async def fetch(
        self,
        url: str,
        wait_ms: int = 1500,
        screenshot: Path | None = None,
    ) -> FetchResult:
        async with async_playwright() as pw:
            browser = await self._launch(pw)
            try:
                context = await self._new_context(browser)
                blocked: list[str] = []
                await self._install_route_blocker(context, blocked)
                page = await context.new_page()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                status = response.status if response else 0
                await page.wait_for_timeout(wait_ms)
                action, selector = await self._dismiss_consent(page)
                if action:
                    await page.wait_for_timeout(500)
                if screenshot:
                    await page.screenshot(path=str(screenshot), full_page=True)
                html = await page.content()
                return FetchResult(
                    url=url,
                    status=status,
                    html=html,
                    blocked_urls=blocked,
                    consent_action=action,
                    consent_selector=selector,
                )
            finally:
                await browser.close()


def _resolve_chromium_binary(root: str) -> str:
    """The Playwright cache stores chromium under subdirs like chromium-1194/
    chrome-linux/chrome. Walk to find the actual executable."""
    p = Path(root)
    if p.is_file():
        return str(p)
    for name in ("chrome", "headless_shell", "chromium"):
        hit = next(p.rglob(name), None)
        if hit and hit.is_file() and os.access(hit, os.X_OK):
            return str(hit)
    return str(p)


# ---- CLI ----

def _cmd_fetch(args: argparse.Namespace) -> int:
    g = Guardian(
        consent_mode=args.consent,
        headed=args.headed,
        user_agent=args.user_agent,
    )
    try:
        result = asyncio.run(
            g.fetch(
                args.url,
                wait_ms=args.wait_ms,
                screenshot=Path(args.screenshot) if args.screenshot else None,
            )
        )
    except Exception as e:
        sys.stderr.write(f"cookie-guardian: fetch failed: {e}\n")
        return 2
    if args.out:
        Path(args.out).write_text(result.html, encoding="utf-8")
    if args.json:
        summary = {
            "url": result.url,
            "status": result.status,
            "blocked_count": len(result.blocked_urls),
            "consent_action": result.consent_action,
            "consent_selector": result.consent_selector,
            "html_bytes": len(result.html),
            "output_path": args.out,
        }
        print(json.dumps(summary, indent=2))
    else:
        sys.stderr.write(
            f"status={result.status} blocked={len(result.blocked_urls)} "
            f"consent={result.consent_action or 'none'}"
            f"{(' via ' + result.consent_selector) if result.consent_selector else ''}\n"
        )
        if not args.out:
            sys.stdout.write(result.html)
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    ok = True
    print("cookie-guardian doctor")
    print("  playwright module:", "ok" if async_playwright else "MISSING")
    print("  blocklist entries:", len(load_blocklist(BLOCKLIST_PATH)))
    sel = load_selectors(SELECTORS_PATH)
    css_count = sum(len(v) for v in sel.get("css_selectors", {}).values())
    txt_count = sum(len(v) for v in sel.get("text_fallback", {}).values())
    print(f"  consent selectors: css={css_count} text={txt_count}")
    bin_path = _resolve_chromium_binary(CHROMIUM_PATH)
    if Path(bin_path).exists():
        print(f"  chromium binary: {bin_path}")
    else:
        print(f"  chromium binary: NOT FOUND at {CHROMIUM_PATH}")
        ok = False
    return 0 if ok else 3


def _cmd_block_check(args: argparse.Namespace) -> int:
    args.out = None
    args.json = True
    args.screenshot = None
    args.headed = False
    args.consent = "off"
    args.wait_ms = 500
    args.user_agent = None
    return _cmd_fetch(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cookie-guardian")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="fetch a URL with blocking + consent dismissal")
    f.add_argument("url")
    f.add_argument("--out", help="write HTML to this file (default: stdout)")
    f.add_argument("--consent", choices=["reject", "accept", "off"], default="reject")
    f.add_argument("--wait-ms", type=int, default=1500)
    f.add_argument("--screenshot", help="full-page screenshot output path")
    f.add_argument("--headed", action="store_true", help="show the browser (debug)")
    f.add_argument("--user-agent", help="override User-Agent")
    f.add_argument("--json", action="store_true", help="print JSON summary instead of HTML")
    f.set_defaults(func=_cmd_fetch)

    d = sub.add_parser("doctor", help="verify install")
    d.set_defaults(func=_cmd_doctor)

    b = sub.add_parser("block-check", help="fetch and report what was blocked (JSON)")
    b.add_argument("url")
    b.set_defaults(func=_cmd_block_check)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

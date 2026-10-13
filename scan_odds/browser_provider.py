"""Opt-in public-page fallback using explicit CSS selectors. No login or anti-bot bypass."""
from __future__ import annotations
import asyncio, json
from pathlib import Path
from typing import Any

class BrowserPageProvider:
    """Read public odds pages with site-approved selectors and optional Playwright.

    The caller must confirm the URL is publicly accessible and permitted by site terms.
    This adapter intentionally does not log in, solve CAPTCHAs, or evade access controls.
    """
    def __init__(self, config_path: str = "config/web3_sites.json"):
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))

    async def _read_one(self, name: str, settings: dict[str, Any]) -> dict[str, Any]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Browser fallback requires optional package playwright and a compatible browser install.") from exc
        url = settings.get("public_odds_url")
        selectors = settings.get("selectors") or {}
        if not url or not selectors.get("event") or not selectors.get("market") or not selectors.get("selection") or not selectors.get("odds"):
            return {"provider": name, "status": "needs_site_selectors", "odds": [],
                    "message": "Configure a public odds URL and CSS selectors after verifying the page."}
        rows = []
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(min(int(settings.get("settle_ms", 1000)), 5000))
                event_nodes = await page.locator(selectors["event"]).all()
                market_nodes = await page.locator(selectors["market"]).all()
                selection_nodes = await page.locator(selectors["selection"]).all()
                odds_nodes = await page.locator(selectors["odds"]).all()
                count = min(len(selection_nodes), len(odds_nodes))
                event = (await event_nodes[0].inner_text()).strip() if event_nodes else ""
                market = (await market_nodes[0].inner_text()).strip() if market_nodes else ""
                for i in range(count):
                    selection = (await selection_nodes[i].inner_text()).strip()
                    raw_odds = (await odds_nodes[i].inner_text()).strip().replace(",", ".")
                    try:
                        odds = float(raw_odds)
                    except ValueError:
                        continue
                    if event and market and selection and odds > 1:
                        rows.append({"event": event, "market": market, "selection": selection,
                                     "odds": odds, "source": name, "side": "back"})
            finally:
                await browser.close()
        return {"provider": name, "status": "ok" if rows else "no_quotes",
                "fetched_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                "count": len(rows), "odds": rows,
                "message": "Public page only; selector accuracy and site permissions must be verified."}

    async def fetch(self, names: list[str] | None = None) -> list[dict[str, Any]]:
        providers = self.config.get("providers", {})
        chosen = names or list(providers)
        results = []
        for name in chosen:
            settings = providers.get(name)
            if not settings:
                results.append({"provider": name, "status": "not_configured", "odds": []})
                continue
            try:
                results.append(await self._read_one(name, settings))
            except Exception as exc:
                results.append({"provider": name, "status": "error", "odds": [], "message": str(exc)})
        return results

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Read configured public odds pages; no login or bets.")
    parser.add_argument("--config", default="config/web3_sites.json")
    parser.add_argument("--sites", default="", help="comma-separated configured site keys")
    args = parser.parse_args()
    provider = BrowserPageProvider(args.config)
    results = asyncio.run(provider.fetch([s.strip() for s in args.sites.split(",") if s.strip()] or None))
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()

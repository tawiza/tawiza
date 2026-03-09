"""LeBonCoin crawler for business distress signals.

Searches for ads indicating business closures, liquidations, equipment sales.
Uses Playwright for anti-bot bypass (split-routed via SFR residential IP).
"""

import asyncio
import re
from datetime import date, datetime
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

# Keywords indicating business distress
DISTRESS_KEYWORDS = [
    "cessation activité",
    "liquidation",
    "fermeture définitive",
    "cause départ retraite",
    "cause fermeture",
    "fond de commerce",
    "matériel professionnel",
    "vente cause cessation",
    "arrêt activité",
    "déstockage fermeture",
]

# Search URLs (no category filter = all categories for maximum coverage)
# DataDome bypass requires headless=False + Xvfb (see collect method)

DEPT_TO_REGION = {
    "75": "ile_de_france", "92": "ile_de_france", "93": "ile_de_france", "94": "ile_de_france",
    "13": "provence_alpes_cote_d_azur", "06": "provence_alpes_cote_d_azur",
    "69": "auvergne_rhone_alpes", "31": "occitanie", "34": "occitanie",
    "33": "nouvelle_aquitaine", "44": "pays_de_la_loire", "35": "bretagne",
    "59": "hauts_de_france", "67": "grand_est", "54": "grand_est", "57": "grand_est",
    "76": "normandie", "45": "centre_val_de_loire",
}


class LeBonCoinCollector(BaseCollector):
    """Collect business distress signals from LeBonCoin ads."""

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="leboncoin",
                source_type="crawler",
                rate_limit=0.5,  # Max 1 request per 2 seconds
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None, max_pages: int = 2
    ) -> list[CollectedSignal]:
        """Scrape LeBonCoin for business distress signals using Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("[leboncoin] Playwright not installed")
            return []

        region = DEPT_TO_REGION.get(code_dept or "75", "ile_de_france")
        all_signals: list[CollectedSignal] = []

        async with async_playwright() as p:
            # MUST use headless=False + Xvfb to bypass DataDome TLS fingerprinting
            # headless=True gets blocked. Run with: xvfb-run -a python ...
            browser = await p.chromium.launch(
                headless=False,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="fr-FR",
            )
            # Remove webdriver detection
            await context.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined})')

            # Warm up: visit homepage first to get DataDome cookies
            warmup_page = await context.new_page()
            try:
                await warmup_page.goto("https://www.leboncoin.fr/", timeout=15000)
                await asyncio.sleep(3)
            except Exception:
                pass
            finally:
                await warmup_page.close()

            for keyword in DISTRESS_KEYWORDS[:5]:  # Top 5 keywords per run
                try:
                    signals = await self._search_keyword(
                        context, keyword, region, code_dept or "75", max_pages
                    )
                    all_signals.extend(signals)
                    # Rate limit between searches
                    await asyncio.sleep(3)
                except Exception as e:
                    logger.warning(f"[leboncoin] Error searching '{keyword}': {e}")

            await browser.close()

        logger.info(f"[leboncoin] {code_dept}: {len(all_signals)} signals collected")
        return all_signals

    async def _search_keyword(
        self, context: Any, keyword: str, region: str, code_dept: str, max_pages: int
    ) -> list[CollectedSignal]:
        """Search a keyword on LeBonCoin and extract signals."""
        page = await context.new_page()
        signals: list[CollectedSignal] = []

        try:
            # Don't use locations param - triggers DataDome blocking
            url = f"https://www.leboncoin.fr/recherche?text={keyword.replace(' ', '+').replace('é', 'e').replace('ê', 'e').replace('è', 'e')}"
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(5)  # Let DataDome JS challenge pass

            # Check if we got blocked
            content = await page.content()
            if "temporairement restreint" in content or "captcha" in content.lower():
                logger.warning(f"[leboncoin] Blocked on '{keyword}' — DataDome TLS fingerprint")
                await page.close()
                return []

            # Extract ads using confirmed working selector
            ads = await page.query_selector_all('[data-qa-id="aditem_container"]')

            for ad in ads[:20]:  # Max 20 per keyword
                try:
                    signal = await self._parse_ad(ad, keyword, code_dept)
                    if signal:
                        signals.append(signal)
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"[leboncoin] Page error for '{keyword}': {e}")
        finally:
            await page.close()

        return signals

    async def _parse_ad(
        self, ad_element: Any, keyword: str, code_dept: str
    ) -> CollectedSignal | None:
        """Parse a single ad element into a signal."""
        try:
            # Title from dedicated element or first <p>
            title_el = await ad_element.query_selector('p[data-qa-id="aditem_title"]')
            if not title_el:
                title_el = await ad_element.query_selector("p")
            title = await title_el.inner_text() if title_el else ""

            # Link
            link_el = await ad_element.query_selector("a[href*='/ad/']")
            href = await link_el.get_attribute("href") if link_el else ""
            if href and not href.startswith("http"):
                href = f"https://www.leboncoin.fr{href}"

            # Price
            price_el = await ad_element.query_selector('p[data-qa-id="aditem_price"]')
            price_text = await price_el.inner_text() if price_el else ""
            price = self._extract_price(price_text)

            # Location
            loc_el = await ad_element.query_selector('p[data-qa-id="aditem_location"]')
            location = await loc_el.inner_text() if loc_el else ""

            if not title:
                return None

            # Calculate distress confidence based on keyword matches
            title_lower = title.lower()
            distress_score = sum(
                1 for kw in DISTRESS_KEYWORDS if kw in title_lower
            )
            confidence = min(0.5 + distress_score * 0.15, 0.95)

            return CollectedSignal(
                source="leboncoin",
                source_url=href or f"https://www.leboncoin.fr/recherche?text={keyword}",
                event_date=date.today(),
                code_dept=code_dept,
                code_commune=None,
                metric_name="annonce_cessation",
                metric_value=price if price else 0.0,
                signal_type="negatif",
                confidence=confidence,
                raw_data={
                    "title": title[:200],
                    "keyword": keyword,
                    "price": price_text,
                    "location": location,
                },
            )
        except Exception:
            return None

    @staticmethod
    def _extract_price(text: str) -> float:
        """Extract numeric price from text like '1 500 €'."""
        if not text:
            return 0.0
        # Remove currency symbols and spaces, extract number
        cleaned = re.sub(r"[^\d,.]", "", text.replace(" ", ""))
        cleaned = cleaned.replace(",", ".")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

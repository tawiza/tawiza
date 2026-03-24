"""
Leboncoin Research Crawler - Mode recherche/expérimentation.

⚠️ USAGE RECHERCHE UNIQUEMENT
- Ne pas utiliser en production
- Respecter les délais entre requêtes
- Données pour analyse de faisabilité

Recherche les annonces signalant des cessations d'activité.
"""

from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import httpx
from loguru import logger


@dataclass
class LeboncoinAd:
    """Une annonce Leboncoin."""

    title: str
    price: float | None
    location: str
    category: str
    date_posted: str | None
    url: str
    description_preview: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "price": self.price,
            "location": self.location,
            "category": self.category,
            "date_posted": self.date_posted,
            "url": self.url,
            "description_preview": self.description_preview,
        }


# Mots-clés signalant une cessation d'activité
CESSATION_KEYWORDS = [
    "cessation activité",
    "cause cessation",
    "liquidation",
    "cause fermeture",
    "fin d'activité",
    "fermeture commerce",
    "cession fonds commerce",
    "déstockage fermeture",
    "tout doit disparaître",
    "matériel professionnel urgent",
]

# User agents pour rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


class LeboncoinResearchCrawler:
    """
    Crawler de recherche pour Leboncoin.

    Mode expérimental pour évaluer la faisabilité.
    """

    BASE_URL = "https://www.leboncoin.fr"
    API_URL = "https://api.leboncoin.fr/finder/search"

    def __init__(self):
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
                    "Origin": "https://www.leboncoin.fr",
                    "Referer": "https://www.leboncoin.fr/",
                },
            )
        return self._client

    async def search_cessations(
        self,
        department: str | None = None,
        max_results: int = 20,
    ) -> list[LeboncoinAd]:
        """
        Recherche les annonces de cessation d'activité.

        Args:
            department: Code département (ex: "69") ou None pour France entière
            max_results: Nombre max de résultats
        """
        all_ads = []

        for keyword in CESSATION_KEYWORDS[:3]:  # Limiter pour le test
            try:
                ads = await self._search_keyword(keyword, department, limit=10)
                all_ads.extend(ads)

                # Délai aléatoire entre requêtes (respecter le serveur)
                await asyncio.sleep(random.uniform(2.0, 5.0))

            except Exception as e:
                logger.warning(f"Search failed for '{keyword}': {e}")
                continue

        # Dédupliquer par URL
        seen_urls = set()
        unique_ads = []
        for ad in all_ads:
            if ad.url not in seen_urls:
                seen_urls.add(ad.url)
                unique_ads.append(ad)

        return unique_ads[:max_results]

    async def _search_keyword(
        self,
        keyword: str,
        department: str | None,
        limit: int = 10,
    ) -> list[LeboncoinAd]:
        """Recherche un mot-clé spécifique."""
        client = await self._get_client()

        # Construire l'URL de recherche web (fallback si API bloquée)
        search_url = f"{self.BASE_URL}/recherche?text={quote_plus(keyword)}"
        if department:
            search_url += f"&locations=d_{department}"

        logger.info(f"Searching: {keyword}" + (f" in dept {department}" if department else ""))

        try:
            # Essayer l'API d'abord
            ads = await self._search_via_api(keyword, department, limit)
            if ads:
                return ads
        except Exception as e:
            logger.debug(f"API search failed: {e}")

        # Fallback: scraping HTML (basique)
        try:
            return await self._search_via_html(search_url, limit)
        except Exception as e:
            logger.warning(f"HTML search failed: {e}")
            return []

    async def _search_via_api(
        self,
        keyword: str,
        department: str | None,
        limit: int,
    ) -> list[LeboncoinAd]:
        """Recherche via l'API Leboncoin (peut être bloquée)."""
        client = await self._get_client()

        payload = {
            "limit": limit,
            "limit_alu": 0,
            "filters": {
                "category": {"id": ""},  # Toutes catégories
                "keywords": {"text": keyword},
                "location": {},
            },
            "offset": 0,
            "owner_type": "all",
            "sort_by": "time",
            "sort_order": "desc",
        }

        if department:
            payload["filters"]["location"] = {
                "departments": [department],
            }

        response = await client.post(
            self.API_URL,
            json=payload,
        )

        if response.status_code == 403:
            raise Exception("API access blocked (403)")

        response.raise_for_status()
        data = response.json()

        ads = []
        for item in data.get("ads", [])[:limit]:
            ads.append(
                LeboncoinAd(
                    title=item.get("subject", ""),
                    price=item.get("price", [None])[0] if item.get("price") else None,
                    location=item.get("location", {}).get("city", ""),
                    category=item.get("category_name", ""),
                    date_posted=item.get("first_publication_date"),
                    url=item.get("url", ""),
                    description_preview=item.get("body", "")[:200] if item.get("body") else None,
                )
            )

        return ads

    async def _search_via_html(
        self,
        url: str,
        limit: int,
    ) -> list[LeboncoinAd]:
        """Fallback: extraction depuis HTML (basique, fragile)."""
        client = await self._get_client()

        response = await client.get(url)

        if response.status_code == 403:
            raise Exception("Access blocked (403)")

        response.raise_for_status()
        html = response.text

        # Extraction basique via regex (fragile mais simple)
        # Leboncoin injecte les données en JSON dans la page
        ads = []

        # Chercher le JSON des annonces dans le HTML
        json_match = re.search(r'"ads":\s*(\[.*?\])\s*,\s*"ads_alu"', html, re.DOTALL)
        if json_match:
            import json

            try:
                ads_data = json.loads(json_match.group(1))
                for item in ads_data[:limit]:
                    ads.append(
                        LeboncoinAd(
                            title=item.get("subject", ""),
                            price=item.get("price", [None])[0] if item.get("price") else None,
                            location=item.get("location", {}).get("city", ""),
                            category=item.get("category_name", ""),
                            date_posted=item.get("first_publication_date"),
                            url=f"https://www.leboncoin.fr{item.get('url', '')}",
                        )
                    )
            except json.JSONDecodeError:
                pass

        return ads

    async def close(self):
        """Ferme le client HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None


async def test_crawler():
    """Test du crawler."""
    crawler = LeboncoinResearchCrawler()

    try:
        print("🔍 Test crawler Leboncoin - cessations d'activité\n")

        # Test France entière
        print("Recherche France entière...")
        ads = await crawler.search_cessations(max_results=10)

        print(f"\n📋 {len(ads)} annonces trouvées:\n")
        for ad in ads:
            print(f"  📦 {ad.title[:60]}")
            print(f"     💰 {ad.price}€ | 📍 {ad.location} | 🏷️ {ad.category}")
            print(f"     🔗 {ad.url[:70]}...")
            print()

        return ads

    finally:
        await crawler.close()


if __name__ == "__main__":
    asyncio.run(test_crawler())

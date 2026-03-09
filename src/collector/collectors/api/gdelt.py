"""GDELT collector - News signals from GDELT v2 Doc API."""

import asyncio
import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from ...processing.geocoder import resolve_commune
from ..base import BaseCollector, CollectedSignal, CollectorConfig


class GDELTCollector(BaseCollector):
    """Collect news signals from GDELT v2 Doc API.
    
    Monitors French-language news articles for economic indicators:
    - Business closures and layoffs (negative signals)
    - Investments and new businesses (positive signals)
    """

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    
    # Query definitions with signal types - simplified syntax without OR/spaces
    QUERIES = {
        "liquidation": "negatif",
        "licenciement": "negatif", 
        "fermeture": "negatif",
        "investissement": "positif",
        "création": "positif",
        "implantation": "positif"
    }

    def __init__(self) -> None:
        super().__init__(
            CollectorConfig(
                name="gdelt",
                source_type="api",
                rate_limit=0.2,  # 1 request per 5 seconds
                timeout=30,
            )
        )

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Collect news signals from GDELT."""
        if since is None:
            since = date.today() - timedelta(days=7)

        signals = []
        
        for query, signal_type in self.QUERIES.items():
            logger.info(f"[gdelt] Querying '{query}'")
            
            params = {
                "query": f'sourcelang:french {query}',
                "mode": "artlist",
                "maxrecords": "25",
                "format": "json",
                "timespan": "7d"
            }
            
            response = await self._request_with_retry("GET", self.BASE_URL, params=params, timeout=30.0)
            if not response:
                logger.warning(f"[gdelt] No response for query '{query}'")
                continue
                
            try:
                data = response.json()
                articles = data.get("articles", [])
                
                logger.info(f"[gdelt] Found {len(articles)} articles for '{query}'")
                
                for article in articles:
                    signal = await self._process_article(article, query, signal_type)
                    if signal:
                        signals.append(signal)
                        
            except Exception as e:
                logger.error(f"[gdelt] Error processing query '{query}': {e}")
                
            # Rate limit: wait 5 seconds between requests
            await asyncio.sleep(5)
            
        logger.info(f"[gdelt] Collected {len(signals)} total signals")
        return signals

    async def _process_article(self, article: dict, query: str, signal_type: str) -> CollectedSignal | None:
        """Process a single article into a signal."""
        try:
            title = article.get("title", "")
            url = article.get("url", "")
            domain = article.get("domain", "")
            
            if not title or not url:
                return None
                
            # Extract department from title/domain
            dept_info = self._extract_department(title, domain)
            
            # Build signal
            signal = CollectedSignal(
                source="gdelt",
                source_url=url,
                event_date=date.today(),
                code_dept=dept_info.get("code_dept"),
                code_commune=dept_info.get("code_commune"),
                metric_name=f"gdelt_{query.replace(' ', '_')}",
                metric_value=1.0,
                signal_type=signal_type,
                confidence=0.6,
                extracted_text=title[:500],
                raw_data={
                    "query": query,
                    "domain": domain,
                    "title": title,
                    "detected_location": dept_info.get("detected_location")
                }
            )
            
            return signal
            
        except Exception as e:
            logger.warning(f"[gdelt] Error processing article: {e}")
            return None

    def _extract_department(self, title: str, domain: str) -> dict[str, str | None]:
        """Extract department from article title or domain using city names."""
        # Common French city patterns
        city_patterns = [
            r'\b(Paris|Marseille|Lyon|Toulouse|Nice|Nantes|Strasbourg|Montpellier|Bordeaux|Lille)\b',
            r'\b([A-Z][a-z]+-[A-Z][a-z]+)\b',  # Hyphenated city names
            r'\b([A-Z][a-z]+(?:-sur-[A-Z][a-z]+)?)\b',  # Cities with -sur-
            r'\b([A-Z][a-z]{3,})\b'  # General capitalized words (potential cities)
        ]
        
        text_to_search = f"{title} {domain}"
        detected_location = None
        
        for pattern in city_patterns:
            matches = re.finditer(pattern, text_to_search, re.IGNORECASE)
            for match in matches:
                potential_city = match.group(1)
                if len(potential_city) >= 4:  # Skip very short words
                    detected_location = potential_city
                    break
            if detected_location:
                break
        
        if not detected_location:
            return {"code_dept": None, "code_commune": None, "detected_location": None}
        
        # Try to resolve the detected city
        try:
            geo_info = resolve_commune(detected_location)
            return {
                "code_dept": geo_info.get("code_dept"),
                "code_commune": geo_info.get("code_commune"),
                "detected_location": detected_location
            }
        except Exception as e:
            logger.debug(f"[gdelt] Could not resolve location '{detected_location}': {e}")
            return {
                "code_dept": None,
                "code_commune": None,
                "detected_location": detected_location
            }
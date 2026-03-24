"""Local press crawler - Extract signals from regional press RSS feeds.

Uses Trafilatura for high-quality French text extraction.
"""

from datetime import date
from typing import Any

from loguru import logger

from ..base import BaseCollector, CollectedSignal, CollectorConfig

# Regional press RSS feeds (extensible)
# Disabled (403/404): lesechos, la_tribune, ouest_france, la_voix_du_nord
DEFAULT_FEEDS = {
    "la_depeche": "https://www.ladepeche.fr/rss.xml",
    "le_progres": "https://www.leprogres.fr/rss",
    "dna": "https://www.dna.fr/rss",
    "sud_ouest": "https://www.sudouest.fr/rss.xml",
    "le_parisien_eco": "https://www.leparisien.fr/economie/rss.xml",
}

# Keywords for signal detection
SIGNAL_KEYWORDS = {
    "positif": [
        "ouverture",
        "inauguration",
        "création",
        "embauche",
        "recrutement",
        "investissement",
        "implantation",
        "développement",
        "croissance",
        "nouveau magasin",
        "nouvelle usine",
        "emplois créés",
    ],
    "negatif": [
        "fermeture",
        "liquidation",
        "licenciement",
        "plan social",
        "cessation",
        "redressement judiciaire",
        "chômage partiel",
        "faillite",
        "restructuration",
        "suppression de postes",
        "délocalisation",
        "fin d'activité",
    ],
}


class PresseLocaleCollector(BaseCollector):
    """Crawl regional press for territorial signals.

    Uses Trafilatura for:
    - RSS feed discovery and parsing
    - High-quality text extraction (F1=0.958 on French text)
    - Metadata extraction (date, author, title)
    """

    def __init__(self, feeds: dict[str, str] | None = None) -> None:
        super().__init__(
            CollectorConfig(
                name="presse_locale",
                source_type="crawler",
                rate_limit=2,  # Be polite to press sites
                timeout=30,
            )
        )
        self._feeds = feeds or DEFAULT_FEEDS

    async def collect(
        self, code_dept: str | None = None, since: date | None = None
    ) -> list[CollectedSignal]:
        """Crawl press feeds and extract signals."""
        try:
            import trafilatura
            from trafilatura.feeds import find_feed_urls
        except ImportError:
            logger.error("[presse_locale] trafilatura not installed: pip install trafilatura")
            return []

        signals = []

        for feed_name, feed_url in self._feeds.items():
            logger.info(f"[presse_locale] Processing feed: {feed_name}")

            try:
                # Fetch and parse RSS feed
                feed_signals = await self._process_feed(feed_name, feed_url, since, trafilatura)
                signals.extend(feed_signals)
            except Exception as e:
                logger.warning(f"[presse_locale] Error processing {feed_name}: {e}")

        logger.info(f"[presse_locale] Total signals extracted: {len(signals)}")
        return signals

    async def _process_feed(
        self, feed_name: str, feed_url: str, since: date | None, trafilatura: Any
    ) -> list[CollectedSignal]:
        """Process a single RSS feed."""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        signals = []

        # Trafilatura is sync, run in executor
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Get feed URLs
            urls = await loop.run_in_executor(
                executor,
                lambda: trafilatura.feeds.find_feed_urls(feed_url) or [],
            )

            if not urls:
                # Try the URL directly as an RSS feed
                response = await self._request_with_retry("GET", feed_url)
                if response:
                    urls = trafilatura.feeds.extract_links(response.text) or []

            logger.info(f"[presse_locale] {feed_name}: {len(urls)} URLs found")

            # Process each article (limit to avoid hammering)
            for url in list(urls)[:20]:
                await self._rate_limit()

                try:
                    result = await loop.run_in_executor(
                        executor,
                        lambda u=url: trafilatura.fetch_url(u),
                    )
                    if not result:
                        continue

                    extracted = await loop.run_in_executor(
                        executor,
                        lambda html=result: trafilatura.extract(
                            html,
                            output_format="dict",
                            with_metadata=True,
                            target_language="fr",
                            include_comments=False,
                        ),
                    )

                    if not extracted or not extracted.get("text"):
                        continue

                    # Detect signals from text
                    signal = self._detect_signal(
                        text=extracted["text"],
                        title=extracted.get("title", ""),
                        url=url,
                        pub_date=extracted.get("date"),
                        feed_name=feed_name,
                    )
                    if signal:
                        signals.append(signal)

                except Exception as e:
                    logger.debug(f"[presse_locale] Error on {url}: {e}")

        return signals

    def _detect_signal(
        self,
        text: str,
        title: str,
        url: str,
        pub_date: str | None,
        feed_name: str,
    ) -> CollectedSignal | None:
        """Detect if article contains a territorial signal."""
        full_text = f"{title} {text}".lower()

        # Check for signal keywords
        signal_type = None
        matched_keywords = []

        for stype, keywords in SIGNAL_KEYWORDS.items():
            for kw in keywords:
                if kw in full_text:
                    signal_type = stype
                    matched_keywords.append(kw)

        if not signal_type:
            return None

        # Parse date
        event_date = None
        if pub_date:
            try:
                event_date = date.fromisoformat(pub_date[:10])
            except (ValueError, TypeError):
                event_date = date.today()

        return CollectedSignal(
            source="presse_locale",
            source_url=url,
            event_date=event_date or date.today(),
            metric_name=f"presse_{signal_type}",
            metric_value=float(len(matched_keywords)),
            signal_type=signal_type,
            confidence=min(0.5 + 0.1 * len(matched_keywords), 0.95),
            raw_data={
                "feed": feed_name,
                "title": title,
                "keywords": matched_keywords,
            },
            extracted_text=text[:2000],  # Limit stored text
        )

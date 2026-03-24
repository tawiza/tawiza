"""
Crawling Pipeline - The core algorithm for territorial micro-signal detection.

Architecture:
    1. URL Discovery   → Trafilatura RSS/sitemaps, custom feeds
    2. Content Fetch   → Trafilatura (90%), Playwright fallback (10%)
    3. Text Extraction → Trafilatura extract with metadata
    4. NLP Analysis    → Keyword detection + spaCy NER (LOC, ORG, PER)
    5. Signal Scoring  → Confidence based on keyword density + entity match
    6. Geo Resolution  → Map extracted locations to INSEE codes
    7. Storage         → PostgreSQL signals table
    8. Anomaly Cross   → Cross-source detection post-collection
"""

import asyncio
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from loguru import logger

from ..collectors.base import CollectedSignal

# ---------------------------------------------------------------------------
# Signal detection rules
# ---------------------------------------------------------------------------


@dataclass
class SignalRule:
    """A rule that maps keywords/patterns to a signal type."""

    name: str
    metric_name: str
    signal_type: str  # positif, negatif, neutre
    keywords: list[str]
    weight: float = 1.0  # multiplier for confidence
    require_geo: bool = False  # require geographic entity


# Comprehensive French territorial signal rules
SIGNAL_RULES: list[SignalRule] = [
    # === POSITIVE SIGNALS ===
    SignalRule(
        name="creation_entreprise",
        metric_name="presse_creation",
        signal_type="positif",
        keywords=[
            "création d'entreprise",
            "nouvelle entreprise",
            "start-up",
            "startup",
            "incubateur",
            "pépinière",
            "lancement",
            "ouvre ses portes",
            "nouveau commerce",
            "inauguration",
            "implantation",
            "s'installe",
            "s'implante",
        ],
        weight=1.2,
    ),
    SignalRule(
        name="recrutement",
        metric_name="presse_emploi_positif",
        signal_type="positif",
        keywords=[
            "embauche",
            "recrutement",
            "recrute",
            "emplois créés",
            "postes à pourvoir",
            "offres d'emploi",
            "CDI",
            "CDD",
            "création de postes",
            "plan d'embauche",
            "nouveau site",
        ],
        weight=1.3,
    ),
    SignalRule(
        name="investissement",
        metric_name="presse_investissement",
        signal_type="positif",
        keywords=[
            "investissement",
            "millions d'euros",
            "levée de fonds",
            "financement",
            "subvention",
            "aide publique",
            "plan de relance",
            "développement économique",
            "zone d'activité",
            "aménagement",
            "réhabilitation",
        ],
        weight=1.1,
    ),
    SignalRule(
        name="construction",
        metric_name="presse_construction",
        signal_type="positif",
        keywords=[
            "permis de construire",
            "chantier",
            "construction",
            "logements neufs",
            "programme immobilier",
            "ZAC",
            "écoquartier",
            "rénovation urbaine",
            "nouveau quartier",
        ],
        weight=1.0,
    ),
    SignalRule(
        name="tourisme_positif",
        metric_name="presse_tourisme",
        signal_type="positif",
        keywords=[
            "fréquentation touristique",
            "saison record",
            "touristes",
            "hôtel",
            "camping",
            "gîte",
            "office de tourisme",
            "patrimoine",
            "festival",
        ],
        weight=0.8,
    ),
    # === NEGATIVE SIGNALS ===
    SignalRule(
        name="fermeture",
        metric_name="presse_fermeture",
        signal_type="negatif",
        keywords=[
            "fermeture",
            "liquidation",
            "liquidation judiciaire",
            "cessation d'activité",
            "fin d'activité",
            "faillite",
            "dépôt de bilan",
            "rideau baissé",
            "ferme ses portes",
            "dernier jour",
        ],
        weight=1.3,
    ),
    SignalRule(
        name="licenciement",
        metric_name="presse_emploi_negatif",
        signal_type="negatif",
        keywords=[
            "licenciement",
            "plan social",
            "PSE",
            "suppression de postes",
            "suppression d'emplois",
            "chômage partiel",
            "activité partielle",
            "restructuration",
            "plan de sauvegarde",
            "délocalisation",
            "dégraissage",
        ],
        weight=1.4,
    ),
    SignalRule(
        name="crise_economique",
        metric_name="presse_crise",
        signal_type="negatif",
        keywords=[
            "crise",
            "récession",
            "déficit",
            "dette",
            "baisse du chiffre d'affaires",
            "perte d'exploitation",
            "redressement judiciaire",
            "tribunal de commerce",
            "difficultés financières",
            "trésorerie tendue",
        ],
        weight=1.2,
    ),
    SignalRule(
        name="desertification",
        metric_name="presse_desert",
        signal_type="negatif",
        keywords=[
            "désert médical",
            "fermeture d'école",
            "fermeture de classe",
            "fermeture de maternité",
            "désertification",
            "exode rural",
            "centre-ville désert",
            "friches",
            "vacance commerciale",
            "commerces fermés",
        ],
        weight=1.1,
    ),
    # === NEUTRAL / STRUCTURAL SIGNALS ===
    SignalRule(
        name="immobilier",
        metric_name="presse_immobilier",
        signal_type="neutre",
        keywords=[
            "prix de l'immobilier",
            "marché immobilier",
            "prix au mètre carré",
            "transaction immobilière",
            "vente immobilière",
            "loyer",
            "baux commerciaux",
        ],
        weight=0.9,
    ),
    SignalRule(
        name="transport",
        metric_name="presse_transport",
        signal_type="neutre",
        keywords=[
            "ligne de train",
            "gare",
            "autoroute",
            "rocade",
            "transport en commun",
            "tramway",
            "bus",
            "mobilité",
            "piste cyclable",
            "covoiturage",
        ],
        weight=0.7,
    ),
    SignalRule(
        name="demographie",
        metric_name="presse_demographie",
        signal_type="neutre",
        keywords=[
            "population",
            "recensement",
            "habitants",
            "croissance démographique",
            "naissances",
            "décès",
            "migration",
            "solde migratoire",
        ],
        weight=0.8,
    ),
]


# ---------------------------------------------------------------------------
# Geographic resolution
# ---------------------------------------------------------------------------

# French department names → codes (for extraction from text)
DEPT_NAMES_TO_CODES: dict[str, str] = {
    "ain": "01",
    "aisne": "02",
    "allier": "03",
    "alpes-de-haute-provence": "04",
    "hautes-alpes": "05",
    "alpes-maritimes": "06",
    "ardèche": "07",
    "ardennes": "08",
    "ariège": "09",
    "aube": "10",
    "aude": "11",
    "aveyron": "12",
    "bouches-du-rhône": "13",
    "calvados": "14",
    "cantal": "15",
    "charente": "16",
    "charente-maritime": "17",
    "cher": "18",
    "corrèze": "19",
    "corse-du-sud": "2A",
    "haute-corse": "2B",
    "côte-d'or": "21",
    "côtes-d'armor": "22",
    "creuse": "23",
    "dordogne": "24",
    "doubs": "25",
    "drôme": "26",
    "eure": "27",
    "eure-et-loir": "28",
    "finistère": "29",
    "gard": "30",
    "haute-garonne": "31",
    "gers": "32",
    "gironde": "33",
    "hérault": "34",
    "ille-et-vilaine": "35",
    "indre": "36",
    "indre-et-loire": "37",
    "isère": "38",
    "jura": "39",
    "landes": "40",
    "loir-et-cher": "41",
    "loire": "42",
    "haute-loire": "43",
    "loire-atlantique": "44",
    "loiret": "45",
    "lot": "46",
    "lot-et-garonne": "47",
    "lozère": "48",
    "maine-et-loire": "49",
    "manche": "50",
    "marne": "51",
    "haute-marne": "52",
    "mayenne": "53",
    "meurthe-et-moselle": "54",
    "meuse": "55",
    "morbihan": "56",
    "moselle": "57",
    "nièvre": "58",
    "nord": "59",
    "oise": "60",
    "orne": "61",
    "pas-de-calais": "62",
    "puy-de-dôme": "63",
    "pyrénées-atlantiques": "64",
    "hautes-pyrénées": "65",
    "pyrénées-orientales": "66",
    "bas-rhin": "67",
    "haut-rhin": "68",
    "rhône": "69",
    "haute-saône": "70",
    "saône-et-loire": "71",
    "sarthe": "72",
    "savoie": "73",
    "haute-savoie": "74",
    "paris": "75",
    "seine-maritime": "76",
    "seine-et-marne": "77",
    "yvelines": "78",
    "deux-sèvres": "79",
    "somme": "80",
    "tarn": "81",
    "tarn-et-garonne": "82",
    "var": "83",
    "vaucluse": "84",
    "vendée": "85",
    "vienne": "86",
    "haute-vienne": "87",
    "vosges": "88",
    "yonne": "89",
    "territoire de belfort": "90",
    "essonne": "91",
    "hauts-de-seine": "92",
    "seine-saint-denis": "93",
    "val-de-marne": "94",
    "val-d'oise": "95",
    # Major cities → dept
    "marseille": "13",
    "lyon": "69",
    "toulouse": "31",
    "nice": "06",
    "nantes": "44",
    "strasbourg": "67",
    "montpellier": "34",
    "bordeaux": "33",
    "lille": "59",
    "rennes": "35",
    "reims": "51",
    "saint-étienne": "42",
    "toulon": "83",
    "le havre": "76",
    "grenoble": "38",
    "dijon": "21",
    "angers": "49",
    "nîmes": "30",
    "clermont-ferrand": "63",
    "tours": "37",
    "limoges": "87",
    "amiens": "80",
    "metz": "57",
    "besançon": "25",
    "orléans": "45",
    "rouen": "76",
    "mulhouse": "68",
    "caen": "14",
    "nancy": "54",
    "perpignan": "66",
    "pau": "64",
    "bayonne": "64",
    "avignon": "84",
    "poitiers": "86",
    "la rochelle": "17",
    "brest": "29",
    "lorient": "56",
    "saint-nazaire": "44",
    "valence": "26",
    "ajaccio": "2A",
    "bastia": "2B",
    "troyes": "10",
    "chambéry": "73",
    "annecy": "74",
    "dunkerque": "59",
    "calais": "62",
    "boulogne-sur-mer": "62",
    "lens": "62",
    "douai": "59",
    "arras": "62",
}

# Major cities to commune codes (top 30)
CITY_TO_COMMUNE: dict[str, str] = {
    "paris": "75056",
    "marseille": "13055",
    "lyon": "69123",
    "toulouse": "31555",
    "nice": "06088",
    "nantes": "44109",
    "strasbourg": "67482",
    "montpellier": "34172",
    "bordeaux": "33063",
    "lille": "59350",
    "rennes": "35238",
    "reims": "51454",
    "saint-étienne": "42218",
    "toulon": "83137",
    "le havre": "76351",
    "grenoble": "38185",
    "dijon": "21231",
    "angers": "49007",
    "nîmes": "30189",
    "clermont-ferrand": "63113",
}


def extract_department_from_text(text: str) -> str | None:
    """Extract department code from article text using location mentions."""
    text_lower = text.lower()

    # Try city names first (more specific)
    for city, code in DEPT_NAMES_TO_CODES.items():
        # Look for city/dept name with word boundaries
        pattern = r"\b" + re.escape(city) + r"\b"
        if re.search(pattern, text_lower):
            return code

    return None


def extract_commune_from_text(text: str) -> str | None:
    """Extract commune INSEE code from text using city names."""
    text_lower = text.lower()
    for city, code in CITY_TO_COMMUNE.items():
        pattern = r"\b" + re.escape(city) + r"\b"
        if re.search(pattern, text_lower):
            return code
    return None


# ---------------------------------------------------------------------------
# NLP Analyzer
# ---------------------------------------------------------------------------


@dataclass
class ArticleAnalysis:
    """Result of analyzing a single article."""

    url: str
    title: str
    text: str
    pub_date: date | None
    source_feed: str

    # NLP results
    matched_rules: list[tuple[SignalRule, list[str]]] = field(default_factory=list)
    entities_loc: list[str] = field(default_factory=list)
    entities_org: list[str] = field(default_factory=list)
    entities_per: list[str] = field(default_factory=list)

    # Geo resolution
    code_dept: str | None = None
    code_commune: str | None = None

    def to_signals(self) -> list[CollectedSignal]:
        """Convert analysis to CollectedSignal objects."""
        signals = []
        for rule, matched_kw in self.matched_rules:
            # Confidence: base 0.4 + 0.1 per keyword + 0.15 if geo found + rule weight
            base_confidence = 0.4
            kw_bonus = min(len(matched_kw) * 0.1, 0.3)
            geo_bonus = 0.15 if self.code_dept else 0.0
            entity_bonus = 0.05 if self.entities_org else 0.0
            confidence = min(
                (base_confidence + kw_bonus + geo_bonus + entity_bonus) * rule.weight, 0.98
            )

            signals.append(
                CollectedSignal(
                    source="presse_locale",
                    source_url=self.url,
                    event_date=self.pub_date or date.today(),
                    code_dept=self.code_dept,
                    code_commune=self.code_commune,
                    metric_name=rule.metric_name,
                    metric_value=float(len(matched_kw)),
                    signal_type=rule.signal_type,
                    confidence=round(confidence, 3),
                    raw_data={
                        "title": self.title,
                        "feed": self.source_feed,
                        "keywords_matched": matched_kw,
                        "rule": rule.name,
                        "entities": {
                            "LOC": self.entities_loc[:5],
                            "ORG": self.entities_org[:5],
                            "PER": self.entities_per[:3],
                        },
                    },
                    extracted_text=self.text[:3000],
                )
            )
        return signals


class NLPAnalyzer:
    """NLP analysis engine using keyword matching + optional spaCy NER."""

    def __init__(self, use_spacy: bool = True) -> None:
        self._nlp = None
        self._use_spacy = use_spacy

    def _load_spacy(self) -> None:
        """Lazy-load spaCy model."""
        if self._nlp is not None:
            return
        if not self._use_spacy:
            return

        try:
            import spacy

            # Try large model first, fall back to small
            for model in ["fr_core_news_lg", "fr_core_news_sm", "fr_core_news_md"]:
                try:
                    self._nlp = spacy.load(model)
                    logger.info(f"[nlp] Loaded spaCy model: {model}")
                    return
                except OSError:
                    continue
            logger.warning("[nlp] No French spaCy model found, using keywords only")
            self._use_spacy = False
        except ImportError:
            logger.warning("[nlp] spaCy not installed, using keywords only")
            self._use_spacy = False

    def analyze(self, article: ArticleAnalysis) -> ArticleAnalysis:
        """Run NLP analysis on an article."""
        full_text = f"{article.title} {article.text}".lower()

        # 1. Keyword matching against rules
        for rule in SIGNAL_RULES:
            matched = []
            for kw in rule.keywords:
                if kw.lower() in full_text:
                    matched.append(kw)
            if matched:
                article.matched_rules.append((rule, matched))

        # 2. spaCy NER (if available)
        self._load_spacy()
        if self._nlp is not None:
            # Analyze first 5000 chars to keep fast
            doc = self._nlp(article.text[:5000])
            for ent in doc.ents:
                if ent.label_ == "LOC":
                    article.entities_loc.append(ent.text)
                elif ent.label_ == "ORG":
                    article.entities_org.append(ent.text)
                elif ent.label_ == "PER":
                    article.entities_per.append(ent.text)

        # 3. Geo resolution from text
        # Try NER entities first, then raw text
        geo_text = " ".join(article.entities_loc) if article.entities_loc else full_text
        article.code_dept = extract_department_from_text(geo_text)
        article.code_commune = extract_commune_from_text(geo_text)

        return article


# ---------------------------------------------------------------------------
# Crawling Pipeline
# ---------------------------------------------------------------------------


# Source configurations
@dataclass
class FeedSource:
    """A press/web source to crawl."""

    name: str
    url: str
    category: str = "presse"  # presse, mairie, institutionnel
    max_articles: int = 30
    priority: int = 1  # 1=high, 3=low


# Default French territorial press feeds
# NOTE: Sources returning persistent 403/404 have been disabled (2026-02-21 audit)
DEFAULT_SOURCES: list[FeedSource] = [
    # National economic press
    FeedSource("Le Figaro Eco", "https://www.lefigaro.fr/rss/figaro_economie.xml", "presse", 15, 2),
    # Regional press (verified working)
    FeedSource("La Dépêche", "https://www.ladepeche.fr/rss.xml", "presse", 25, 1),
    FeedSource("Le Progrès", "https://www.leprogres.fr/rss", "presse", 25, 1),
    FeedSource("DNA", "https://www.dna.fr/rss", "presse", 20, 2),
    FeedSource("Sud Ouest", "https://www.sudouest.fr/rss.xml", "presse", 25, 1),
    FeedSource("Le Parisien Eco", "https://www.leparisien.fr/economie/rss.xml", "presse", 20, 1),
    FeedSource("Le Dauphiné", "https://www.ledauphine.com/rss", "presse", 20, 2),
    FeedSource("L'Est Républicain", "https://www.estrepublicain.fr/rss", "presse", 20, 2),
    FeedSource("Nice Matin", "https://www.nicematin.com/rss", "presse", 15, 2),
    # Disabled (403 - anti-bot): Les Echos, Ouest-France, La Voix du Nord,
    # Le Telegramme, La Provence, La Montagne, La Nouvelle Republique,
    # Centre Presse, Paris Normandie, 20 Minutes, Midi Libre
    # Disabled (404 - feed removed): La Tribune, INSEE RSS
    # Disabled (403): Banque de France RSS, BPI France RSS
    # Last audit: 2026-02-21
]


class CrawlingPipeline:
    """
    Main crawling pipeline for territorial micro-signal detection.

    Usage:
        pipeline = CrawlingPipeline()
        signals = await pipeline.run()
        # signals ready for PostgreSQL storage
    """

    def __init__(
        self,
        sources: list[FeedSource] | None = None,
        use_spacy: bool = True,
        max_workers: int = 3,
        dedup_window_hours: int = 48,
    ) -> None:
        self._sources = sources or DEFAULT_SOURCES
        self._analyzer = NLPAnalyzer(use_spacy=use_spacy)
        self._max_workers = max_workers
        self._dedup_window = dedup_window_hours
        self._seen_urls: set[str] = set()
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def run(self, sources: list[FeedSource] | None = None) -> list[CollectedSignal]:
        """
        Run the full crawling pipeline.

        Returns list of CollectedSignal ready for storage.
        """
        target_sources = sources or self._sources
        all_signals: list[CollectedSignal] = []

        logger.info(f"[pipeline] Starting crawl of {len(target_sources)} sources")

        # Sort by priority
        target_sources.sort(key=lambda s: s.priority)

        for source in target_sources:
            try:
                signals = await self._process_source(source)
                all_signals.extend(signals)
                logger.info(f"[pipeline] {source.name}: {len(signals)} signals detected")
            except Exception as e:
                logger.error(f"[pipeline] {source.name} failed: {e}")

        logger.info(
            f"[pipeline] Crawl complete: {len(all_signals)} total signals "
            f"from {len(target_sources)} sources"
        )
        return all_signals

    async def _process_source(self, source: FeedSource) -> list[CollectedSignal]:
        """Process a single feed source through the full pipeline."""
        import trafilatura
        from trafilatura import feeds as tf_feeds

        loop = asyncio.get_event_loop()
        signals: list[CollectedSignal] = []

        # Step 1: Discover URLs from RSS/sitemap
        logger.debug(f"[pipeline] Discovering URLs from {source.name}")
        urls = await loop.run_in_executor(
            self._executor,
            lambda: list(tf_feeds.find_feed_urls(source.url) or []),
        )

        if not urls:
            # Try fetching the URL directly and extracting links
            try:
                html = await loop.run_in_executor(
                    self._executor,
                    lambda: trafilatura.fetch_url(source.url),
                )
                if html:
                    urls = list(tf_feeds.extract_links(html) or [])
            except Exception:
                pass

        if not urls:
            logger.debug(f"[pipeline] {source.name}: no URLs discovered")
            return []

        # Deduplicate
        urls = [u for u in urls if self._url_hash(u) not in self._seen_urls]
        urls = urls[: source.max_articles]

        logger.debug(f"[pipeline] {source.name}: processing {len(urls)} articles")

        # Step 2-6: Process each article
        for url in urls:
            self._seen_urls.add(self._url_hash(url))

            try:
                article_signals = await self._process_article(url, source, trafilatura, loop)
                signals.extend(article_signals)
            except Exception as e:
                logger.debug(f"[pipeline] Error on {url}: {e}")

            # Rate limit: be polite
            await asyncio.sleep(0.5)

        return signals

    async def _fetch_with_playwright(self, url: str) -> str | None:
        """Fallback: fetch page content using Playwright for JS-heavy/anti-bot sites."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.debug("[pipeline] Playwright not available for fallback")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    locale="fr-FR",
                )
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)  # Let JS render
                html = await page.content()
                await browser.close()
                return html
        except Exception as e:
            logger.debug(f"[pipeline] Playwright fallback failed for {url}: {e}")
            return None

    async def _fetch_with_ocr(self, url: str) -> str | None:
        """Last resort: screenshot page and OCR it with GLM-OCR."""
        try:
            from playwright.async_api import async_playwright

            from ..processing.ocr import extract_text_from_image
        except ImportError:
            return None

        import tempfile

        tmp_dir = tempfile.gettempdir()
        screenshot_path = f"{tmp_dir}/pipeline_ocr_{hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:8]}.png"
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.screenshot(path=screenshot_path, full_page=True)
                await browser.close()

            result = await extract_text_from_image(screenshot_path)
            return result.get("text", "")
        except Exception as e:
            logger.debug(f"[pipeline] OCR fallback failed for {url}: {e}")
            return None

    async def _process_article(
        self,
        url: str,
        source: FeedSource,
        trafilatura: Any,
        loop: asyncio.AbstractEventLoop,
    ) -> list[CollectedSignal]:
        """Process a single article through the NLP pipeline."""

        # Step 2: Fetch content (Trafilatura → Playwright → OCR)
        html = await loop.run_in_executor(
            self._executor,
            lambda: trafilatura.fetch_url(url),
        )
        if not html:
            # Fallback to Playwright for anti-bot sites
            logger.debug(f"[pipeline] Trafilatura failed, trying Playwright: {url}")
            html = await self._fetch_with_playwright(url)
        if not html:
            return []

        # Step 3: Extract text with metadata
        # Trafilatura 2.0: bare_extraction() returns a dict
        from trafilatura import bare_extraction

        extracted = await loop.run_in_executor(
            self._executor,
            lambda: bare_extraction(
                html,
                with_metadata=True,
                target_language="fr",
                include_comments=False,
                favor_precision=True,
            ),
        )

        if not extracted:
            return []

        # Handle Document, dict and string returns
        if isinstance(extracted, str):
            text = extracted
            title = ""
            extracted = {"text": text}
        elif isinstance(extracted, dict):
            text = extracted.get("text", "")
            title = extracted.get("title", "")
        elif hasattr(extracted, "as_dict"):
            # Trafilatura 2.0 Document object
            text = extracted.text or ""
            title = extracted.title or ""
            extracted = extracted.as_dict()
        else:
            return []

        if not text:
            return []

        # Skip very short articles
        if len(text) < 100:
            return []

        # Parse publication date
        pub_date = None
        if extracted.get("date"):
            try:
                pub_date = date.fromisoformat(extracted["date"][:10])
            except (ValueError, TypeError):
                pub_date = date.today()

        # Step 4-5: NLP Analysis (keyword + NER + scoring)
        article = ArticleAnalysis(
            url=url,
            title=title,
            text=text,
            pub_date=pub_date,
            source_feed=source.name,
        )
        self._analyzer.analyze(article)

        # Skip if no signals detected
        if not article.matched_rules:
            return []

        # Step 6-7: Convert to signals (geo resolution done in analyze)
        return article.to_signals()

    @staticmethod
    def _url_hash(url: str) -> str:
        """Hash URL for dedup."""
        return hashlib.md5(url.encode(), usedforsecurity=False).hexdigest()[:12]

    async def close(self) -> None:
        """Cleanup resources."""
        self._executor.shutdown(wait=False)

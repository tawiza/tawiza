#!/usr/bin/env python3
"""
WebCrawlerAgent - Agent spécialisé dans le crawling web intelligent pour Tawiza-V2
Crawling respectueux, extraction de données, suivi de liens et indexation
"""

import asyncio
import contextlib
import hashlib
import os
import re
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from loguru import logger

try:
    from playwright.async_api import Browser, Page, async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. JavaScript rendering disabled.")


@dataclass
class CrawlConfig:
    """Configuration du crawler"""
    max_pages: int = 100
    max_depth: int = 3
    delay_seconds: float = 1.0
    timeout_seconds: float = 30.0
    respect_robots_txt: bool = True
    follow_external_links: bool = False
    user_agent: str = "Tawiza-Crawler/1.0 (+https://tawiza.ai/bot)"
    allowed_domains: list[str] = field(default_factory=list)
    excluded_patterns: list[str] = field(default_factory=list)
    include_patterns: list[str] = field(default_factory=list)
    extract_images: bool = True
    extract_links: bool = True
    extract_metadata: bool = True
    use_javascript: bool = False
    max_concurrent: int = 5
    retry_count: int = 3


@dataclass
class CrawledPage:
    """Page crawlée"""
    url: str
    title: str
    content: str  # Texte brut extrait
    html: str
    depth: int
    status_code: int
    content_type: str
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    crawled_at: str = ""
    load_time_ms: float = 0.0
    hash: str = ""


@dataclass
class CrawlResult:
    """Résultat du crawling"""
    start_url: str
    pages_crawled: int
    pages_failed: int
    total_links_found: int
    total_images_found: int
    unique_domains: set[str]
    pages: list[CrawledPage]
    errors: list[dict[str, str]]
    start_time: str
    end_time: str
    duration_seconds: float
    sitemap: dict[str, list[str]]


@dataclass
class RobotsRules:
    """Règles du fichier robots.txt"""
    allowed: list[str] = field(default_factory=list)
    disallowed: list[str] = field(default_factory=list)
    crawl_delay: float = 0.0
    sitemaps: list[str] = field(default_factory=list)


class WebCrawlerAgent:
    """Agent de crawling web intelligent"""

    def __init__(self, config: CrawlConfig = None):
        """Initialiser le crawler

        Args:
            config: Configuration du crawler
        """
        self.name = "WebCrawlerAgent"
        self.agent_type = "crawler"
        self.capabilities = [
            "web_crawling",
            "content_extraction",
            "link_discovery",
            "sitemap_generation",
            "robots_txt_parsing",
            "javascript_rendering"
        ]

        self.config = config or CrawlConfig()

        # État du crawler
        self.visited_urls: set[str] = set()
        self.queue: deque = deque()
        self.robots_cache: dict[str, RobotsRules] = {}
        self.is_running = False
        self.stats = {
            "requests": 0,
            "success": 0,
            "failed": 0,
            "bytes_downloaded": 0
        }

        # Client HTTP
        self.client: httpx.AsyncClient | None = None

        # Playwright pour JS rendering
        self.playwright = None
        self.browser = None

    async def initialize(self):
        """Initialiser les ressources du crawler"""
        self.client = httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": self.config.user_agent},
            follow_redirects=True
        )

        if self.config.use_javascript and PLAYWRIGHT_AVAILABLE:
            # Enable VNC support if not in headless mode
            use_headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
            if not use_headless:
                os.environ["DISPLAY"] = os.getenv("DISPLAY", ":99")
                logger.info(f"🌐 Using DISPLAY={os.environ['DISPLAY']} for Crawler VNC streaming")

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=use_headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            logger.info(f"🌐 Playwright initialized (headless={use_headless})")

        logger.info("🕷️ WebCrawlerAgent initialized")

    async def close(self):
        """Fermer les ressources"""
        if self.client:
            await self.client.aclose()

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("🕷️ WebCrawlerAgent closed")

    # ==================== ROBOTS.TXT ====================

    async def parse_robots_txt(self, domain: str) -> RobotsRules:
        """Parser le fichier robots.txt d'un domaine"""
        if domain in self.robots_cache:
            return self.robots_cache[domain]

        rules = RobotsRules()

        try:
            robots_url = f"https://{domain}/robots.txt"
            response = await self.client.get(robots_url)

            if response.status_code == 200:
                content = response.text
                current_agent = None

                for line in content.split("\n"):
                    line = line.strip().lower()

                    if line.startswith("user-agent:"):
                        agent = line.split(":", 1)[1].strip()
                        current_agent = agent == "*" or "tawiza" in agent

                    elif current_agent:
                        if line.startswith("allow:"):
                            rules.allowed.append(line.split(":", 1)[1].strip())
                        elif line.startswith("disallow:"):
                            rules.disallowed.append(line.split(":", 1)[1].strip())
                        elif line.startswith("crawl-delay:"):
                            with contextlib.suppress(ValueError):
                                rules.crawl_delay = float(line.split(":", 1)[1].strip())
                        elif line.startswith("sitemap:"):
                            rules.sitemaps.append(line.split(":", 1)[1].strip())

            self.robots_cache[domain] = rules
            logger.debug(f"Parsed robots.txt for {domain}")

        except Exception as e:
            logger.warning(f"Could not fetch robots.txt for {domain}: {e}")
            self.robots_cache[domain] = rules

        return rules

    def is_allowed_by_robots(self, url: str, rules: RobotsRules) -> bool:
        """Vérifier si une URL est autorisée par robots.txt"""
        parsed = urlparse(url)
        path = parsed.path or "/"

        # Vérifier les exclusions
        for pattern in rules.disallowed:
            if pattern and path.startswith(pattern):
                return False

        # Vérifier les inclusions explicites
        for pattern in rules.allowed:
            if pattern and path.startswith(pattern):
                return True

        return True

    # ==================== URL MANAGEMENT ====================

    def normalize_url(self, url: str) -> str:
        """Normaliser une URL"""
        parsed = urlparse(url)

        # Supprimer le fragment
        parsed = parsed._replace(fragment="")

        # Normaliser le chemin
        path = parsed.path or "/"
        if not path.startswith("/"):
            path = "/" + path

        # Reconstruire l'URL
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            ""
        ))

    def is_valid_url(self, url: str) -> bool:
        """Vérifier si une URL est valide pour le crawling"""
        try:
            parsed = urlparse(url)

            # Vérifier le schéma
            if parsed.scheme not in ["http", "https"]:
                return False

            # Vérifier le domaine
            if not parsed.netloc:
                return False

            # Vérifier les patterns exclus
            for pattern in self.config.excluded_patterns:
                if re.search(pattern, url):
                    return False

            # Vérifier les patterns inclus (si définis)
            if self.config.include_patterns:
                if not any(re.search(p, url) for p in self.config.include_patterns):
                    return False

            # Exclure les fichiers non-HTML courants
            excluded_extensions = [
                ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
                ".mp3", ".mp4", ".avi", ".mov",
                ".zip", ".tar", ".gz", ".rar",
                ".css", ".js", ".woff", ".woff2", ".ttf", ".eot"
            ]
            path_lower = parsed.path.lower()
            return all(not path_lower.endswith(ext) for ext in excluded_extensions)

        except Exception:
            return False

    def extract_domain(self, url: str) -> str:
        """Extraire le domaine d'une URL"""
        return urlparse(url).netloc

    # ==================== CONTENT EXTRACTION ====================

    async def fetch_page(self, url: str) -> CrawledPage | None:
        """Récupérer et parser une page"""
        self.stats["requests"] += 1
        start_time = time.time()

        try:
            if self.config.use_javascript and self.browser:
                return await self._fetch_with_javascript(url, start_time)
            else:
                return await self._fetch_with_httpx(url, start_time)

        except Exception as e:
            self.stats["failed"] += 1
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def _fetch_with_httpx(self, url: str, start_time: float) -> CrawledPage | None:
        """Récupérer une page avec httpx"""
        response = await self.client.get(url)
        load_time = (time.time() - start_time) * 1000

        content_type = response.headers.get("content-type", "")

        # Vérifier que c'est du HTML
        if "text/html" not in content_type.lower():
            return None

        html = response.text
        self.stats["bytes_downloaded"] += len(html.encode())
        self.stats["success"] += 1

        return self._parse_html(url, html, response.status_code, content_type,
                               dict(response.headers), load_time)

    async def _fetch_with_javascript(self, url: str, start_time: float) -> CrawledPage | None:
        """Récupérer une page avec Playwright (JavaScript)"""
        page = await self.browser.new_page()
        try:
            response = await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(0.5)  # Attendre les scripts

            html = await page.content()
            load_time = (time.time() - start_time) * 1000

            self.stats["bytes_downloaded"] += len(html.encode())
            self.stats["success"] += 1

            return self._parse_html(
                url, html,
                response.status if response else 200,
                "text/html",
                {},
                load_time
            )
        finally:
            await page.close()

    def _parse_html(
        self,
        url: str,
        html: str,
        status_code: int,
        content_type: str,
        headers: dict[str, str],
        load_time: float
    ) -> CrawledPage:
        """Parser le HTML et extraire les informations"""
        soup = BeautifulSoup(html, "html.parser")

        # Extraire le titre
        title = ""
        if soup.title:
            title = soup.title.string or ""
        elif soup.find("h1"):
            title = soup.find("h1").get_text(strip=True)

        # Extraire le contenu textuel
        # Supprimer les scripts et styles
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        content = soup.get_text(separator=" ", strip=True)
        # Nettoyer les espaces multiples
        content = re.sub(r"\s+", " ", content)

        # Extraire les liens
        links = []
        if self.config.extract_links:
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(url, href)
                if self.is_valid_url(full_url):
                    links.append(self.normalize_url(full_url))

        # Extraire les images
        images = []
        if self.config.extract_images:
            for img in soup.find_all("img", src=True):
                src = img["src"]
                full_url = urljoin(url, src)
                images.append(full_url)

        # Extraire les métadonnées
        metadata = {}
        if self.config.extract_metadata:
            for meta in soup.find_all("meta"):
                name = meta.get("name") or meta.get("property", "")
                content_meta = meta.get("content", "")
                if name and content_meta:
                    metadata[name] = content_meta

        # Calculer le hash du contenu
        content_hash = hashlib.md5(content.encode()).hexdigest()

        return CrawledPage(
            url=url,
            title=title,
            content=content[:50000],  # Limiter le contenu
            html=html[:100000] if len(html) < 100000 else html[:100000],
            depth=0,  # Sera mis à jour par le crawler
            status_code=status_code,
            content_type=content_type,
            links=list(set(links)),  # Dédupliquer
            images=list(set(images)),
            metadata=metadata,
            headers=headers,
            crawled_at=datetime.utcnow().isoformat(),
            load_time_ms=load_time,
            hash=content_hash
        )

    # ==================== CRAWLING ====================

    async def crawl(
        self,
        start_url: str,
        callback: Callable[[CrawledPage], None] = None
    ) -> CrawlResult:
        """Crawler un site à partir d'une URL de départ

        Args:
            start_url: URL de départ
            callback: Fonction appelée pour chaque page crawlée

        Returns:
            Résultat du crawling
        """
        logger.info(f"🕷️ Starting crawl from {start_url}")
        await self.initialize()

        start_time = datetime.utcnow()
        self.is_running = True
        self.visited_urls.clear()
        self.queue.clear()
        self.stats = {"requests": 0, "success": 0, "failed": 0, "bytes_downloaded": 0}

        # Normaliser et ajouter l'URL de départ
        start_url = self.normalize_url(start_url)
        start_domain = self.extract_domain(start_url)

        # Configurer les domaines autorisés si pas définis
        if not self.config.allowed_domains:
            self.config.allowed_domains = [start_domain]

        # Parser robots.txt si nécessaire
        if self.config.respect_robots_txt:
            await self.parse_robots_txt(start_domain)

        # Ajouter à la queue
        self.queue.append((start_url, 0))

        pages: list[CrawledPage] = []
        errors: list[dict[str, str]] = []
        all_links: set[str] = set()
        all_images: set[str] = set()
        domains: set[str] = set()
        sitemap: dict[str, list[str]] = {}

        # Boucle principale
        while self.queue and len(pages) < self.config.max_pages and self.is_running:
            # Prendre les prochaines URLs
            batch = []
            while self.queue and len(batch) < self.config.max_concurrent:
                url, depth = self.queue.popleft()
                if url not in self.visited_urls and depth <= self.config.max_depth:
                    batch.append((url, depth))
                    self.visited_urls.add(url)

            if not batch:
                break

            # Crawler en parallèle
            tasks = [self._crawl_url(url, depth) for url, depth in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (url, depth), result in zip(batch, results, strict=False):
                if isinstance(result, Exception):
                    errors.append({"url": url, "error": str(result)})
                    continue

                if result is None:
                    continue

                page = result
                page.depth = depth
                pages.append(page)

                # Callback
                if callback:
                    callback(page)

                # Statistiques
                domain = self.extract_domain(url)
                domains.add(domain)
                all_links.update(page.links)
                all_images.update(page.images)

                # Sitemap
                if domain not in sitemap:
                    sitemap[domain] = []
                sitemap[domain].append(url)

                # Ajouter les liens à la queue
                for link in page.links:
                    link_domain = self.extract_domain(link)

                    # Vérifier si on peut crawler ce lien
                    if link in self.visited_urls:
                        continue

                    if not self.config.follow_external_links:
                        if link_domain not in self.config.allowed_domains:
                            continue

                    # Vérifier robots.txt
                    if self.config.respect_robots_txt:
                        rules = await self.parse_robots_txt(link_domain)
                        if not self.is_allowed_by_robots(link, rules):
                            continue

                    self.queue.append((link, depth + 1))

            # Respecter le délai
            await asyncio.sleep(self.config.delay_seconds)

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        self.is_running = False
        await self.close()

        result = CrawlResult(
            start_url=start_url,
            pages_crawled=len(pages),
            pages_failed=len(errors),
            total_links_found=len(all_links),
            total_images_found=len(all_images),
            unique_domains=domains,
            pages=pages,
            errors=errors,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_seconds=duration,
            sitemap=sitemap
        )

        logger.info(
            f"🕷️ Crawl complete: {result.pages_crawled} pages, "
            f"{result.total_links_found} links, {duration:.1f}s"
        )

        return result

    async def _crawl_url(self, url: str, depth: int) -> CrawledPage | None:
        """Crawler une URL unique"""
        try:
            page = await self.fetch_page(url)
            if page:
                page.depth = depth
            return page
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return None

    # ==================== SITEMAP ====================

    async def crawl_sitemap(self, sitemap_url: str) -> list[str]:
        """Crawler un sitemap XML pour obtenir les URLs"""
        urls = []

        try:
            response = await self.client.get(sitemap_url)
            soup = BeautifulSoup(response.text, "xml")

            # Sitemaps imbriqués
            for sitemap in soup.find_all("sitemap"):
                loc = sitemap.find("loc")
                if loc:
                    nested_urls = await self.crawl_sitemap(loc.text)
                    urls.extend(nested_urls)

            # URLs directes
            for url in soup.find_all("url"):
                loc = url.find("loc")
                if loc:
                    urls.append(loc.text)

            logger.info(f"📍 Found {len(urls)} URLs in sitemap")

        except Exception as e:
            logger.error(f"Error parsing sitemap {sitemap_url}: {e}")

        return urls

    # ==================== STREAMING ====================

    async def crawl_stream(
        self,
        start_url: str
    ) -> AsyncGenerator[CrawledPage]:
        """Crawler en mode streaming (yield les pages une par une)"""
        logger.info(f"🕷️ Starting streaming crawl from {start_url}")
        await self.initialize()

        self.is_running = True
        self.visited_urls.clear()
        self.queue.clear()

        start_url = self.normalize_url(start_url)
        start_domain = self.extract_domain(start_url)

        if not self.config.allowed_domains:
            self.config.allowed_domains = [start_domain]

        if self.config.respect_robots_txt:
            await self.parse_robots_txt(start_domain)

        self.queue.append((start_url, 0))
        pages_count = 0

        while self.queue and pages_count < self.config.max_pages and self.is_running:
            url, depth = self.queue.popleft()

            if url in self.visited_urls or depth > self.config.max_depth:
                continue

            self.visited_urls.add(url)

            page = await self._crawl_url(url, depth)
            if page:
                pages_count += 1
                yield page

                for link in page.links:
                    link_domain = self.extract_domain(link)
                    if link not in self.visited_urls:
                        if self.config.follow_external_links or link_domain in self.config.allowed_domains:
                            self.queue.append((link, depth + 1))

            await asyncio.sleep(self.config.delay_seconds)

        self.is_running = False
        await self.close()

    def stop(self):
        """Arrêter le crawling"""
        self.is_running = False
        logger.info("🕷️ Crawl stopped")

    async def health_check(self) -> dict[str, Any]:
        """Vérifier l'état du crawler"""
        return {
            "status": "healthy" if not self.is_running else "crawling",
            "visited_urls": len(self.visited_urls),
            "queue_size": len(self.queue),
            "stats": self.stats,
            "config": {
                "max_pages": self.config.max_pages,
                "max_depth": self.config.max_depth,
                "delay": self.config.delay_seconds
            }
        }


# Factory function
def create_crawler(
    max_pages: int = 100,
    max_depth: int = 3,
    delay: float = 1.0,
    use_javascript: bool = False
) -> WebCrawlerAgent:
    """Créer une instance du crawler avec configuration personnalisée"""
    config = CrawlConfig(
        max_pages=max_pages,
        max_depth=max_depth,
        delay_seconds=delay,
        use_javascript=use_javascript
    )
    return WebCrawlerAgent(config)

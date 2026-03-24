"""Tests complets pour web_crawler_agent.py

Tests couvrant:
- CrawlConfig, CrawledPage, CrawlResult, RobotsRules dataclasses
- WebCrawlerAgent
- Tests conditionnels (httpx, playwright optionnels)
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.agents.advanced.web_crawler_agent import (
    CrawlConfig,
    CrawledPage,
    CrawlResult,
    RobotsRules,
    WebCrawlerAgent,
)


# ============================================================================
# Tests CrawlConfig Dataclass
# ============================================================================
class TestCrawlConfig:
    """Tests pour la dataclass CrawlConfig."""

    def test_create_config_default(self):
        """Configuration par défaut."""
        config = CrawlConfig()

        assert config.max_pages == 100
        assert config.max_depth == 3
        assert config.delay_seconds == 1.0
        assert config.timeout_seconds == 30.0
        assert config.respect_robots_txt is True
        assert config.follow_external_links is False
        assert config.max_concurrent == 5
        assert config.retry_count == 3

    def test_create_config_custom(self):
        """Configuration personnalisée."""
        config = CrawlConfig(
            max_pages=500,
            max_depth=5,
            delay_seconds=0.5,
            timeout_seconds=60.0,
            respect_robots_txt=False,
            follow_external_links=True,
            user_agent="CustomBot/1.0",
            allowed_domains=["example.com", "test.com"],
            excluded_patterns=["/admin/*", "/private/*"],
            include_patterns=["/blog/*", "/articles/*"],
            use_javascript=True,
            max_concurrent=10,
        )

        assert config.max_pages == 500
        assert config.max_depth == 5
        assert config.user_agent == "CustomBot/1.0"
        assert len(config.allowed_domains) == 2
        assert len(config.excluded_patterns) == 2
        assert config.use_javascript is True


# ============================================================================
# Tests CrawledPage Dataclass
# ============================================================================
class TestCrawledPage:
    """Tests pour la dataclass CrawledPage."""

    def test_create_page(self):
        """Création d'une page crawlée."""
        page = CrawledPage(
            url="https://example.com/page",
            title="Example Page",
            content="Page content text",
            html="<html>...</html>",
            depth=1,
            status_code=200,
            content_type="text/html",
            links=["https://example.com/link1", "https://example.com/link2"],
            images=["https://example.com/img1.png"],
            metadata={"author": "Test"},
            headers={"content-length": "1234"},
            crawled_at="2024-01-01T12:00:00",
            load_time_ms=150.5,
            hash="abc123",
        )

        assert page.url == "https://example.com/page"
        assert page.title == "Example Page"
        assert page.depth == 1
        assert page.status_code == 200
        assert len(page.links) == 2
        assert len(page.images) == 1

    def test_page_default_values(self):
        """Valeurs par défaut."""
        page = CrawledPage(
            url="https://test.com",
            title="Test",
            content="",
            html="",
            depth=0,
            status_code=200,
            content_type="text/html",
        )

        assert page.links == []
        assert page.images == []
        assert page.metadata == {}
        assert page.headers == {}
        assert page.crawled_at == ""
        assert page.load_time_ms == 0.0
        assert page.hash == ""


# ============================================================================
# Tests CrawlResult Dataclass
# ============================================================================
class TestCrawlResult:
    """Tests pour la dataclass CrawlResult."""

    def test_create_result(self):
        """Création d'un résultat de crawl."""
        pages = [
            CrawledPage(
                url=f"https://example.com/page{i}",
                title=f"Page {i}",
                content="Content",
                html="<html></html>",
                depth=1,
                status_code=200,
                content_type="text/html",
            )
            for i in range(3)
        ]

        result = CrawlResult(
            start_url="https://example.com",
            pages_crawled=3,
            pages_failed=1,
            total_links_found=50,
            total_images_found=20,
            unique_domains={"example.com", "cdn.example.com"},
            pages=pages,
            errors=[{"url": "https://example.com/error", "error": "404"}],
            start_time="2024-01-01T12:00:00",
            end_time="2024-01-01T12:05:00",
            duration_seconds=300.0,
            sitemap={"https://example.com": ["https://example.com/page1"]},
        )

        assert result.pages_crawled == 3
        assert result.pages_failed == 1
        assert result.total_links_found == 50
        assert len(result.unique_domains) == 2
        assert len(result.pages) == 3
        assert result.duration_seconds == 300.0


# ============================================================================
# Tests RobotsRules Dataclass
# ============================================================================
class TestRobotsRules:
    """Tests pour la dataclass RobotsRules."""

    def test_create_rules_default(self):
        """Règles par défaut."""
        rules = RobotsRules()

        assert rules.allowed == []
        assert rules.disallowed == []
        assert rules.crawl_delay == 0.0
        assert rules.sitemaps == []

    def test_create_rules_full(self):
        """Règles complètes."""
        rules = RobotsRules(
            allowed=["/public/*", "/blog/*"],
            disallowed=["/admin/*", "/private/*", "/api/*"],
            crawl_delay=2.0,
            sitemaps=["https://example.com/sitemap.xml"],
        )

        assert len(rules.allowed) == 2
        assert len(rules.disallowed) == 3
        assert rules.crawl_delay == 2.0
        assert len(rules.sitemaps) == 1


# ============================================================================
# Tests WebCrawlerAgent - Création
# ============================================================================
class TestWebCrawlerAgentBasic:
    """Tests basiques pour WebCrawlerAgent."""

    def test_create_agent_default(self):
        """Création avec configuration par défaut."""
        agent = WebCrawlerAgent()

        assert agent.name == "WebCrawlerAgent"
        assert agent.agent_type == "crawler"
        assert isinstance(agent.config, CrawlConfig)
        assert agent.is_running is False
        assert len(agent.visited_urls) == 0

    def test_create_agent_custom_config(self):
        """Création avec configuration personnalisée."""
        config = CrawlConfig(max_pages=200, max_depth=5)
        agent = WebCrawlerAgent(config=config)

        assert agent.config.max_pages == 200
        assert agent.config.max_depth == 5

    def test_capabilities(self):
        """Vérification des capacités."""
        agent = WebCrawlerAgent()

        expected_capabilities = [
            "web_crawling",
            "content_extraction",
            "link_discovery",
            "sitemap_generation",
            "robots_txt_parsing",
            "javascript_rendering",
        ]

        for cap in expected_capabilities:
            assert cap in agent.capabilities

    def test_initial_stats(self):
        """Statistiques initiales."""
        agent = WebCrawlerAgent()

        assert agent.stats["requests"] == 0
        assert agent.stats["success"] == 0
        assert agent.stats["failed"] == 0
        assert agent.stats["bytes_downloaded"] == 0


# ============================================================================
# Tests WebCrawlerAgent - Initialisation
# ============================================================================
class TestWebCrawlerAgentInitialization:
    """Tests d'initialisation."""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Initialisation de base."""
        agent = WebCrawlerAgent()
        await agent.initialize()

        assert agent.client is not None

    @pytest.mark.asyncio
    async def test_close(self):
        """Fermeture des ressources (si méthode existe)."""
        agent = WebCrawlerAgent()
        await agent.initialize()

        # Check for close or cleanup method
        if hasattr(agent, "close"):
            agent.client = MagicMock()
            agent.client.aclose = AsyncMock()
            await agent.close()
            agent.client.aclose.assert_called_once()
        elif hasattr(agent, "cleanup"):
            agent.client = MagicMock()
            agent.client.aclose = AsyncMock()
            await agent.cleanup()
            agent.client.aclose.assert_called_once()
        else:
            # No cleanup method - just verify client was created
            assert agent.client is not None


# ============================================================================
# Tests WebCrawlerAgent - URL Management
# ============================================================================
class TestWebCrawlerAgentUrls:
    """Tests de gestion des URLs."""

    def test_visited_urls_tracking(self):
        """Suivi des URLs visitées."""
        agent = WebCrawlerAgent()

        agent.visited_urls.add("https://example.com/page1")
        agent.visited_urls.add("https://example.com/page2")

        assert "https://example.com/page1" in agent.visited_urls
        assert "https://example.com/page3" not in agent.visited_urls
        assert len(agent.visited_urls) == 2

    def test_queue_management(self):
        """Gestion de la queue."""
        agent = WebCrawlerAgent()

        agent.queue.append(("https://example.com/page1", 0))
        agent.queue.append(("https://example.com/page2", 1))

        assert len(agent.queue) == 2

        url, depth = agent.queue.popleft()
        assert url == "https://example.com/page1"
        assert depth == 0


# ============================================================================
# Tests WebCrawlerAgent - Robots Cache
# ============================================================================
class TestWebCrawlerAgentRobots:
    """Tests du cache robots.txt."""

    def test_robots_cache_empty(self):
        """Cache robots vide au départ."""
        agent = WebCrawlerAgent()
        assert agent.robots_cache == {}

    def test_robots_cache_storage(self):
        """Stockage des règles robots."""
        agent = WebCrawlerAgent()

        rules = RobotsRules(disallowed=["/admin/*"], crawl_delay=1.0)
        agent.robots_cache["example.com"] = rules

        assert "example.com" in agent.robots_cache
        assert agent.robots_cache["example.com"].crawl_delay == 1.0


# ============================================================================
# Tests Edge Cases
# ============================================================================
class TestWebCrawlerAgentEdgeCases:
    """Tests des cas limites."""

    def test_config_with_patterns(self):
        """Configuration avec patterns."""
        config = CrawlConfig(
            excluded_patterns=[r".*\.pdf$", r".*\.zip$"],
            include_patterns=[r"^/blog/.*", r"^/articles/.*"],
        )
        agent = WebCrawlerAgent(config=config)

        assert len(agent.config.excluded_patterns) == 2
        assert len(agent.config.include_patterns) == 2

    def test_multiple_agent_instances(self):
        """Plusieurs instances indépendantes."""
        config1 = CrawlConfig(max_pages=100)
        config2 = CrawlConfig(max_pages=500)

        agent1 = WebCrawlerAgent(config=config1)
        agent2 = WebCrawlerAgent(config=config2)

        agent1.visited_urls.add("https://site1.com")
        agent2.visited_urls.add("https://site2.com")

        assert agent1.config.max_pages != agent2.config.max_pages
        assert "https://site1.com" not in agent2.visited_urls
        assert "https://site2.com" not in agent1.visited_urls

    def test_stats_update(self):
        """Mise à jour des statistiques."""
        agent = WebCrawlerAgent()

        # Simuler des requêtes
        agent.stats["requests"] = 100
        agent.stats["success"] = 95
        agent.stats["failed"] = 5
        agent.stats["bytes_downloaded"] = 1024 * 1024  # 1MB

        success_rate = agent.stats["success"] / agent.stats["requests"]
        assert success_rate == 0.95

    def test_crawled_page_with_error(self):
        """Page crawlée avec erreur."""
        page = CrawledPage(
            url="https://example.com/error",
            title="",
            content="",
            html="",
            depth=1,
            status_code=404,
            content_type="",
        )

        assert page.status_code == 404
        assert page.title == ""
        assert page.content == ""

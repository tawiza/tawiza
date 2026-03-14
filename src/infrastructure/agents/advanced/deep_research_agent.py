#!/usr/bin/env python3
"""
DeepResearchAgent - Agent de recherche approfondie pour Tawiza-V2

Combine:
- Web Crawling intelligent
- Extraction et analyse de contenu
- Stockage S3 pour cache
- Indexation vectorielle Qdrant
- Analyse LLM avec Ollama
- Synthèse et rapport
"""

import asyncio
import hashlib
import json
import os
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantClient = None

from ..tracing import LANGFUSE_AVAILABLE, get_tracer
from .s3_storage_agent import S3StorageAgent, get_s3_agent
from .web_crawler_agent import CrawlConfig, WebCrawlerAgent


@dataclass
class ResearchQuery:
    """Requête de recherche"""

    query: str
    depth: int = 2
    max_sources: int = 10
    languages: list[str] = field(default_factory=lambda: ["fr", "en"])
    domains: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    focus_keywords: list[str] = field(default_factory=list)


@dataclass
class ResearchSource:
    """Source de recherche"""

    url: str
    title: str
    content: str
    summary: str
    relevance_score: float
    keywords: list[str]
    crawled_at: str
    cached: bool = False


@dataclass
class ResearchResult:
    """Résultat complet de recherche"""

    query: str
    sources: list[ResearchSource]
    synthesis: str
    key_findings: list[str]
    recommendations: list[str]
    related_queries: list[str]
    total_sources_analyzed: int
    execution_time_seconds: float
    generated_at: str


class DeepResearchAgent:
    """Agent de recherche approfondie combinant crawling, LLM et indexation"""

    def __init__(
        self,
        ollama_url: str = None,
        ollama_model: str = "llama3.1:8b",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        s3_agent: S3StorageAgent = None,
        cache_bucket: str = "tawiza-research-cache",
    ):
        """Initialiser l'agent de recherche

        Args:
            ollama_url: URL du serveur Ollama
            ollama_model: Modèle à utiliser
            qdrant_host: Host Qdrant
            qdrant_port: Port Qdrant
            s3_agent: Agent S3 pour le cache
            cache_bucket: Bucket S3 pour le cache
        """
        self.name = "DeepResearchAgent"
        self.agent_type = "research"
        self.capabilities = [
            "web_crawling",
            "content_extraction",
            "semantic_search",
            "llm_analysis",
            "synthesis",
            "caching",
        ]

        # Configuration - use environment variable for Ollama URL
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = ollama_model
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.cache_bucket = cache_bucket

        # Composants
        self.crawler = None
        self.s3 = s3_agent
        self.qdrant: QdrantClient | None = None
        self.http_client: httpx.AsyncClient | None = None

        # Collection Qdrant
        self.collection_name = "research_documents"
        self.vector_size = 768  # Pour nomic-embed-text

        # Langfuse tracer
        self.tracer = None

        self.is_initialized = False

    async def initialize(self) -> bool:
        """Initialiser tous les composants"""
        try:
            # HTTP Client
            self.http_client = httpx.AsyncClient(timeout=60.0)

            # S3 Agent (optional - graceful degradation if not available)
            self.s3_available = False
            try:
                if self.s3 is None:
                    self.s3 = get_s3_agent()
                # S3 connect() is async - use wait_for with timeout
                connected = await asyncio.wait_for(self.s3.connect(), timeout=10.0)
                if connected and self.s3.is_connected:
                    await asyncio.wait_for(self.s3.create_bucket(self.cache_bucket), timeout=5.0)
                    self.s3_available = True
                    logger.info("📦 S3 cache enabled")
                else:
                    logger.warning("⚠️ S3 connection failed (caching disabled)")
                    self.s3 = None
            except TimeoutError:
                logger.warning("⚠️ S3 connection timed out (caching disabled)")
                self.s3 = None
            except Exception as e:
                logger.warning(f"⚠️ S3 not available (caching disabled): {e}")
                self.s3 = None

            # Qdrant (optional - graceful degradation)
            self.qdrant_available = False
            if QDRANT_AVAILABLE:
                try:
                    self.qdrant = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
                    await self._ensure_collection()
                    self.qdrant_available = True
                    logger.info("🔍 Qdrant indexing enabled")
                except Exception as e:
                    logger.warning(f"⚠️ Qdrant not available (indexing disabled): {e}")
                    self.qdrant = None

            # Crawler
            self.crawler = WebCrawlerAgent(
                CrawlConfig(max_pages=50, max_depth=3, delay_seconds=0.5, respect_robots_txt=True)
            )

            # Langfuse tracer
            if LANGFUSE_AVAILABLE:
                self.tracer = get_tracer()
                logger.info("📊 Langfuse tracing enabled")

            self.is_initialized = True
            logger.info(
                f"🔬 DeepResearchAgent initialized (S3: {self.s3_available}, Qdrant: {self.qdrant_available})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize DeepResearchAgent: {e}")
            return False

    async def _ensure_collection(self):
        """S'assurer que la collection Qdrant existe"""
        if not self.qdrant:
            return

        collections = self.qdrant.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self.qdrant.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")

    # ==================== OLLAMA INTEGRATION ====================

    async def _get_embedding(self, text: str) -> list[float]:
        """Obtenir l'embedding d'un texte via Ollama"""
        try:
            response = await self.http_client.post(
                f"{self.ollama_url}/api/embed",
                json={
                    "model": "nomic-embed-text",
                    "input": text[:8000],  # Limite de contexte
                },
            )
            if response.status_code == 200:
                data = response.json()
                embs = data.get("embeddings", [[]])
                return embs[0] if embs else []
        except Exception as e:
            logger.warning(f"Embedding error: {e}")

        # Fallback: embedding aléatoire
        import random

        return [random.random() for _ in range(self.vector_size)]

    async def _generate_text(
        self, prompt: str, system: str = None, temperature: float = 0.7
    ) -> str:
        """Générer du texte via Ollama"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await self.http_client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.ollama_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
                timeout=120.0,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "")

        except Exception as e:
            logger.error(f"Generation error: {e}")

        return ""

    # ==================== CACHE MANAGEMENT ====================

    def _cache_key(self, url: str) -> str:
        """Générer une clé de cache pour une URL"""
        hash_val = hashlib.md5(url.encode()).hexdigest()
        return f"pages/{hash_val}.json"

    async def _get_cached(self, url: str) -> dict | None:
        """Récupérer une page du cache"""
        if not self.s3_available or not self.s3:
            return None
        try:
            key = self._cache_key(url)
            data = await self.s3.download_bytes(self.cache_bucket, key)
            if data:
                return json.loads(data.decode())
        except Exception:
            pass
        return None

    async def _cache_page(self, url: str, page_data: dict):
        """Mettre une page en cache"""
        if not self.s3_available or not self.s3:
            return
        try:
            key = self._cache_key(url)
            data = json.dumps(page_data, ensure_ascii=False).encode()
            await self.s3.upload_bytes(
                self.cache_bucket, key, data, content_type="application/json"
            )
        except Exception as e:
            logger.warning(f"Cache error for {url}: {e}")

    # ==================== SEARCH SOURCES ====================

    async def _search_web(self, query: str, num_results: int = 10) -> list[str]:
        """Rechercher des URLs via DuckDuckGo"""
        try:
            # Utiliser DuckDuckGo HTML
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            response = await self.http_client.get(search_url, headers={"User-Agent": "Mozilla/5.0"})

            if response.status_code == 200:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(response.text, "html.parser")
                urls = []

                for a in soup.find_all("a", class_="result__a"):
                    href = a.get("href", "")
                    if href.startswith("http"):
                        urls.append(href)
                    elif "uddg=" in href:
                        # Extraire l'URL encodée
                        import urllib.parse

                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        if "uddg" in parsed:
                            urls.append(parsed["uddg"][0])

                logger.info(f"Found {len(urls)} search results for: {query}")
                return urls[:num_results]

        except Exception as e:
            logger.error(f"Search error: {e}")

        return []

    # ==================== CONTENT ANALYSIS ====================

    async def _analyze_content(self, content: str, query: str) -> tuple[str, float, list[str]]:
        """Analyser le contenu avec LLM

        Returns:
            Tuple de (résumé, score de pertinence, mots-clés)
        """
        system = """Tu es un analyste de recherche expert. Analyse le contenu fourni par rapport à la requête.
Réponds en JSON avec:
{
    "summary": "résumé concis en 2-3 phrases",
    "relevance": 0.0-1.0,
    "keywords": ["mot1", "mot2", ...]
}"""

        prompt = f"""Requête de recherche: {query}

Contenu à analyser:
{content[:4000]}

Analyse ce contenu et sa pertinence pour la requête."""

        response = await self._generate_text(prompt, system, temperature=0.3)

        try:
            # Parser le JSON
            json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return (
                    data.get("summary", ""),
                    float(data.get("relevance", 0.5)),
                    data.get("keywords", []),
                )
        except Exception:
            pass

        return ("", 0.5, [])

    async def _synthesize_research(
        self, query: str, sources: list[ResearchSource]
    ) -> tuple[str, list[str], list[str], list[str]]:
        """Synthétiser les résultats de recherche

        Returns:
            Tuple de (synthèse, findings, recommendations, related_queries)
        """
        system = """Tu es un expert en synthèse de recherche.
Crée une synthèse complète à partir des sources fournies.
Réponds en JSON avec:
{
    "synthesis": "synthèse détaillée en paragraphes",
    "key_findings": ["finding 1", "finding 2", ...],
    "recommendations": ["rec 1", "rec 2", ...],
    "related_queries": ["query 1", "query 2", ...]
}"""

        sources_text = "\n\n".join([f"Source: {s.title}\n{s.summary}" for s in sources[:10]])

        prompt = f"""Requête de recherche: {query}

Sources analysées:
{sources_text}

Crée une synthèse complète de ces informations."""

        response = await self._generate_text(prompt, system, temperature=0.5)

        try:
            json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return (
                    data.get("synthesis", ""),
                    data.get("key_findings", []),
                    data.get("recommendations", []),
                    data.get("related_queries", []),
                )
        except Exception:
            pass

        return (response, [], [], [])

    # ==================== MAIN RESEARCH FLOW ====================

    async def research(self, query: ResearchQuery) -> ResearchResult:
        """Effectuer une recherche approfondie

        Args:
            query: Requête de recherche

        Returns:
            Résultat complet de la recherche
        """
        if not self.is_initialized:
            await self.initialize()

        start_time = datetime.utcnow()
        logger.info(f"🔬 Starting deep research: {query.query}")

        # Start Langfuse trace
        trace_id = None
        if self.tracer:
            trace_id = self.tracer.start_trace(
                name="deep_research",
                agent_name=self.name,
                agent_type=self.agent_type,
                input_data={
                    "query": query.query,
                    "depth": query.depth,
                    "max_sources": query.max_sources,
                },
                tags=["research", "deep_research"],
            )

        sources: list[ResearchSource] = []
        total_analyzed = 0

        # 1. Rechercher des URLs
        search_query = query.query
        if query.focus_keywords:
            search_query += " " + " ".join(query.focus_keywords)

        urls = await self._search_web(search_query, query.max_sources * 2)

        # Filtrer par domaines
        if query.domains:
            urls = [u for u in urls if any(d in u for d in query.domains)]
        if query.exclude_domains:
            urls = [u for u in urls if not any(d in u for d in query.exclude_domains)]

        # 2. Crawler et analyser chaque URL
        for url in urls[: query.max_sources]:
            try:
                # Vérifier le cache
                cached = await self._get_cached(url)
                if cached:
                    page_data = cached
                    from_cache = True
                else:
                    # Crawler la page
                    await self.crawler.initialize()
                    result = await self.crawler.crawl(url)
                    await self.crawler.close()

                    if result.pages:
                        page = result.pages[0]
                        page_data = {"url": page.url, "title": page.title, "content": page.content}
                        await self._cache_page(url, page_data)
                        from_cache = False
                    else:
                        continue

                total_analyzed += 1

                # Analyser le contenu
                summary, relevance, keywords = await self._analyze_content(
                    page_data["content"], query.query
                )

                # Créer la source
                source = ResearchSource(
                    url=page_data["url"],
                    title=page_data["title"],
                    content=page_data["content"][:2000],
                    summary=summary,
                    relevance_score=relevance,
                    keywords=keywords,
                    crawled_at=datetime.utcnow().isoformat(),
                    cached=from_cache,
                )

                # Indexer dans Qdrant (optional)
                if self.qdrant_available and self.qdrant and source.summary:
                    try:
                        embedding = await self._get_embedding(source.summary)
                        if len(embedding) == self.vector_size:
                            self.qdrant.upsert(
                                collection_name=self.collection_name,
                                points=[
                                    PointStruct(
                                        id=hash(url) % (2**63),
                                        vector=embedding,
                                        payload={
                                            "url": url,
                                            "title": source.title,
                                            "summary": source.summary,
                                        },
                                    )
                                ],
                            )
                        else:
                            logger.debug(
                                f"Skipping indexing - embedding dim mismatch: {len(embedding)} vs {self.vector_size}"
                            )
                    except Exception as e:
                        logger.warning(f"Qdrant indexing error: {e}")

                sources.append(source)
                logger.debug(f"Analyzed: {source.title} (relevance: {relevance:.2f})")

            except Exception as e:
                logger.warning(f"Error processing {url}: {e}")
                continue

        # 3. Trier par pertinence
        sources.sort(key=lambda x: x.relevance_score, reverse=True)

        # 4. Synthétiser
        synthesis, findings, recommendations, related = await self._synthesize_research(
            query.query, sources
        )

        # Calculer le temps d'exécution
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        result = ResearchResult(
            query=query.query,
            sources=sources,
            synthesis=synthesis,
            key_findings=findings,
            recommendations=recommendations,
            related_queries=related,
            total_sources_analyzed=total_analyzed,
            execution_time_seconds=execution_time,
            generated_at=datetime.utcnow().isoformat(),
        )

        logger.info(f"🔬 Research complete: {len(sources)} sources, {execution_time:.1f}s")

        # End Langfuse trace
        if self.tracer and trace_id:
            self.tracer.end_trace(
                trace_id,
                output_data={
                    "sources_count": len(sources),
                    "execution_time": execution_time,
                    "synthesis_length": len(synthesis),
                },
            )
            self.tracer.flush()

        return result

    async def search_similar(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Rechercher des documents similaires dans l'index

        Args:
            query: Requête de recherche
            limit: Nombre de résultats

        Returns:
            Liste de documents similaires
        """
        if not self.qdrant:
            return []

        try:
            embedding = await self._get_embedding(query)
            results = self.qdrant.search(
                collection_name=self.collection_name, query_vector=embedding, limit=limit
            )

            return [
                {
                    "url": r.payload.get("url"),
                    "title": r.payload.get("title"),
                    "summary": r.payload.get("summary"),
                    "score": r.score,
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def stream_research(self, query: ResearchQuery) -> AsyncGenerator[dict[str, Any]]:
        """Recherche en mode streaming (yield les résultats progressivement)"""
        if not self.is_initialized:
            await self.initialize()

        yield {"type": "start", "query": query.query}

        urls = await self._search_web(query.query, query.max_sources)
        yield {"type": "urls_found", "count": len(urls)}

        for i, url in enumerate(urls):
            yield {"type": "processing", "url": url, "index": i}

            try:
                cached = await self._get_cached(url)
                if cached:
                    yield {"type": "cache_hit", "url": url}
                else:
                    await self.crawler.initialize()
                    result = await self.crawler.crawl(url)
                    await self.crawler.close()

                    if result.pages:
                        page = result.pages[0]
                        await self._cache_page(
                            url, {"url": page.url, "title": page.title, "content": page.content}
                        )

                        summary, relevance, _ = await self._analyze_content(
                            page.content, query.query
                        )

                        yield {
                            "type": "source",
                            "url": url,
                            "title": page.title,
                            "summary": summary,
                            "relevance": relevance,
                        }

            except Exception as e:
                yield {"type": "error", "url": url, "error": str(e)}

        yield {"type": "complete"}

    async def health_check(self) -> dict[str, Any]:
        """Vérifier l'état de l'agent"""
        status = {"agent": self.name, "initialized": self.is_initialized, "components": {}}

        # S3
        if self.s3:
            s3_health = await self.s3.health_check()
            status["components"]["s3"] = s3_health.get("status")

        # Qdrant
        if self.qdrant:
            try:
                collections = self.qdrant.get_collections()
                status["components"]["qdrant"] = "healthy"
                status["components"]["qdrant_collections"] = len(collections.collections)
            except Exception:
                status["components"]["qdrant"] = "unhealthy"

        # Ollama
        try:
            response = await self.http_client.get(f"{self.ollama_url}/api/tags")
            status["components"]["ollama"] = (
                "healthy" if response.status_code == 200 else "unhealthy"
            )
        except Exception:
            status["components"]["ollama"] = "unhealthy"

        return status

    async def execute_from_prompt(self, prompt: str) -> dict[str, Any]:
        """Execute research from natural language prompt.

        This method allows the agent to be called from the TUI with plain text.
        It parses the prompt to extract research parameters and executes the research.

        Args:
            prompt: Natural language research request

        Returns:
            Dict with research results
        """
        if not self.is_initialized:
            await self.initialize()

        logger.info(f"🔬 Executing research from prompt: {prompt[:100]}...")

        # Extract parameters from prompt
        depth = 2
        max_sources = 5

        # Check for depth indicators
        if any(
            word in prompt.lower() for word in ["deep", "thorough", "comprehensive", "approfondi"]
        ):
            depth = 3
            max_sources = 10
        elif any(word in prompt.lower() for word in ["quick", "brief", "rapide", "bref"]):
            depth = 1
            max_sources = 3

        # Extract focus keywords (words in quotes)
        import re

        quoted_keywords = re.findall(r'"([^"]+)"', prompt)

        # Create ResearchQuery
        query = ResearchQuery(
            query=prompt, depth=depth, max_sources=max_sources, focus_keywords=quoted_keywords
        )

        try:
            # Execute research
            result = await self.research(query)

            return {
                "success": True,
                "query": result.query,
                "synthesis": result.synthesis,
                "key_findings": result.key_findings,
                "recommendations": result.recommendations,
                "sources_count": len(result.sources),
                "sources": [
                    {
                        "title": s.title,
                        "url": s.url,
                        "summary": s.summary,
                        "relevance": s.relevance_score,
                    }
                    for s in result.sources[:5]  # Top 5 sources
                ],
                "execution_time": result.execution_time_seconds,
                "related_queries": result.related_queries,
            }

        except Exception as e:
            logger.error(f"Research execution failed: {e}")
            return {"success": False, "error": str(e), "query": prompt}

    async def close(self):
        """Fermer les ressources"""
        if self.http_client:
            await self.http_client.aclose()
        if self.s3:
            await self.s3.close()
        logger.info("🔬 DeepResearchAgent closed")


# Factory function
def create_research_agent(ollama_model: str = "llama3.1:8b") -> DeepResearchAgent:
    """Créer une instance de l'agent de recherche"""
    return DeepResearchAgent(ollama_model=ollama_model)

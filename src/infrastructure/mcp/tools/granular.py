"""Granular MCP tools for Tawiza.

These tools provide direct access to individual data sources and utilities:
- sirene/search: Search SIRENE database
- bodacc/search: Search BODACC legal announcements
- boamp/search: Search public contracts
- geo/locate: Geocode an address
- geo/map: Generate map from locations
- debate/run: Run multi-agent debate
"""

import json

from mcp.server.fastmcp import FastMCP


def register_granular_tools(mcp: FastMCP) -> None:
    """Register granular tools on the MCP server."""

    @mcp.tool()
    async def sirene_search(
        query: str,
        region: str | None = None,
        activite: str | None = None,
        limit: int = 20,
    ) -> str:
        """Recherche dans la base SIRENE (INSEE).

        Base de données officielle des entreprises françaises.

        Args:
            query: Termes de recherche (nom, activité, etc.)
            region: Code région (ex: "32" pour Hauts-de-France)
            activite: Code NAF/APE (ex: "62.01Z" pour programmation)
            limit: Nombre maximum de résultats

        Returns:
            Liste d'entreprises avec SIRET, nom, adresse, effectifs
        """
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)

        params = {'query': query, 'limite': limit}
        if region:
            params['region'] = region
        if activite:
            params['activite'] = activite

        result = await registry.execute('sirene.search', params)

        return json.dumps({
            "success": True,
            "source": "sirene",
            "query": query,
            "count": len(result.get("enterprises", [])),
            "enterprises": result.get("enterprises", []),
        }, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def bodacc_search(
        query: str,
        limit: int = 20,
    ) -> str:
        """Recherche dans le BODACC (Bulletin Officiel des Annonces Civiles et Commerciales).

        Annonces légales: créations, modifications, procédures collectives.

        Args:
            query: Termes de recherche (nom d'entreprise, SIRET)
            limit: Nombre maximum de résultats

        Returns:
            Liste d'annonces légales
        """
        from src.infrastructure.datasources.bodacc import BodaccDataSource

        datasource = BodaccDataSource()
        results = await datasource.search(query=query, limit=limit)

        return json.dumps({
            "success": True,
            "source": "bodacc",
            "query": query,
            "count": len(results),
            "announcements": results,
        }, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def boamp_search(
        query: str,
        limit: int = 20,
    ) -> str:
        """Recherche dans le BOAMP (Bulletin Officiel des Annonces des Marchés Publics).

        Appels d'offres et marchés publics français.

        Args:
            query: Termes de recherche (secteur, mots-clés)
            limit: Nombre maximum de résultats

        Returns:
            Liste de marchés publics
        """
        from src.infrastructure.datasources.boamp import BoampDataSource

        datasource = BoampDataSource()
        results = await datasource.search(query=query, limit=limit)

        return json.dumps({
            "success": True,
            "source": "boamp",
            "query": query,
            "count": len(results),
            "contracts": results,
        }, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def geo_locate(
        address: str,
    ) -> str:
        """Géocode une adresse française en coordonnées lat/lon.

        Utilise l'API Adresse (BAN) - Base Adresse Nationale.

        Args:
            address: Adresse à géocoder (ex: "10 rue de la Paix, Paris")

        Returns:
            Coordonnées et détails de l'adresse
        """
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        registry = ToolRegistry()
        register_all_tools(registry)

        result = await registry.execute('geo.locate', {'address': address})

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def geo_batch_locate(
        addresses: str,
    ) -> str:
        """Géocode plusieurs adresses françaises (max 50).

        Args:
            addresses: Liste d'adresses au format JSON

        Returns:
            Coordonnées pour chaque adresse
        """
        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        try:
            addr_list = json.loads(addresses)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON"})

        registry = ToolRegistry()
        register_all_tools(registry)

        result = await registry.execute('geo.batch_locate', {'addresses': addr_list})

        return json.dumps(result, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def geo_generate_map(
        locations: str,
        title: str = "Carte",
    ) -> str:
        """Génère une carte interactive HTML avec Folium.

        Args:
            locations: Liste de localisations au format JSON
                      [{nom, lat, lon, type?, effectif?, commune?}, ...]
            title: Titre de la carte

        Returns:
            Carte HTML
        """
        import tempfile

        from src.cli.v2.agents.tools import register_all_tools
        from src.cli.v2.agents.unified.tools import ToolRegistry

        try:
            locs = json.loads(locations)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON"})

        registry = ToolRegistry()
        register_all_tools(registry)

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            map_path = f.name

        result = await registry.execute('geo.map', {
            'locations': locs,
            'title': title,
            'output_path': map_path,
        })

        if result.get("success"):
            with open(map_path) as f:
                html = f.read()
            return json.dumps({
                "success": True,
                "map_html": html,
                "markers": result.get("markers"),
            }, ensure_ascii=False)

        return json.dumps(result, ensure_ascii=False)

    @mcp.tool()
    async def debate_run(
        query: str,
        data: str,
        mode: str = "extended",
    ) -> str:
        """Lance un débat multi-agents pour valider des données.

        Args:
            query: Contexte du débat
            data: Données à valider (JSON)
            mode: "standard" (3 agents) ou "extended" (6 agents)

        Returns:
            Résultat du débat avec score de confiance
        """
        from src.domain.debate import DebateMode
        from src.domain.debate.debate_system import DebateSystem
        from src.infrastructure.llm import create_debate_system_with_llm

        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError:
            return json.dumps({"success": False, "error": "Invalid JSON data"})

        debate_mode = DebateMode.EXTENDED if mode == "extended" else DebateMode.STANDARD

        try:
            debate = create_debate_system_with_llm(text_model="qwen3.5:27b", mode=debate_mode)
        except Exception:
            debate = DebateSystem(mode=debate_mode)

        result = await debate.validate(query=query, data=parsed_data)

        return json.dumps({
            "success": True,
            "confidence": result.final_confidence,
            "verdict": result.verdict,
            "issues": result.issues,
            "messages": [
                {"agent": m.agent, "role": m.role, "confidence": m.confidence, "content": m.content}
                for m in result.messages
            ],
        }, ensure_ascii=False, indent=2)

    @mcp.tool()
    async def gdelt_search(
        query: str,
        limit: int = 20,
    ) -> str:
        """Recherche d'actualités dans GDELT.

        Base de données mondiale d'actualités en temps réel.

        Args:
            query: Termes de recherche
            limit: Nombre maximum de résultats

        Returns:
            Liste d'articles
        """
        from src.infrastructure.datasources.gdelt import GdeltDataSource

        datasource = GdeltDataSource()
        results = await datasource.search(query=query, limit=limit)

        return json.dumps({
            "success": True,
            "source": "gdelt",
            "query": query,
            "count": len(results),
            "articles": results,
        }, ensure_ascii=False, indent=2, default=str)

    @mcp.tool()
    async def subventions_search(
        query: str,
        limit: int = 20,
    ) -> str:
        """Recherche de subventions publiques (data.gouv.fr).

        Args:
            query: Termes de recherche (nom d'entreprise, secteur)
            limit: Nombre maximum de résultats

        Returns:
            Liste de subventions
        """
        from src.infrastructure.datasources.subventions import SubventionsDataSource

        datasource = SubventionsDataSource()
        results = await datasource.search(query=query, limit=limit)

        return json.dumps({
            "success": True,
            "source": "subventions",
            "query": query,
            "count": len(results),
            "subventions": results,
        }, ensure_ascii=False, indent=2, default=str)

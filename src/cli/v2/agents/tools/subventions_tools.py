"""Subventions and public funding tools.

Uses:
- API Data.Subvention (beta.gouv.fr) for French subsidies
- Aides-territoires API for territorial aids
"""

from typing import Any

import httpx
from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry

# API URLs
DATA_SUBVENTION_URL = "https://api.datasubvention.beta.gouv.fr"
AIDES_TERRITOIRES_URL = "https://aides-territoires.beta.gouv.fr/api"


def register_subventions_tools(registry: ToolRegistry) -> None:
    """Register subsidies and public funding tools."""

    async def subventions_search(
        siret: str | None = None,
        rna: str | None = None,
        nom: str | None = None,
    ) -> dict[str, Any]:
        """Search subsidies received by an organization.

        Args:
            siret: SIRET number (14 digits)
            rna: RNA number for associations
            nom: Organization name (partial match)

        Returns:
            Dict with subsidies list
        """
        try:
            if not siret and not rna and not nom:
                return {"success": False, "error": "Provide siret, rna, or nom parameter"}

            # Data.Subvention API requires SIRET or RNA
            if siret:
                identifier = siret.replace(" ", "")
                endpoint = f"{DATA_SUBVENTION_URL}/etablissement/{identifier}/subventions"
            elif rna:
                endpoint = f"{DATA_SUBVENTION_URL}/association/{rna}/subventions"
            else:
                # Search by name not directly supported, return info
                return {
                    "success": False,
                    "error": "Search by name not supported. Please provide SIRET or RNA number.",
                    "tip": "Use sirene.search to find SIRET first",
                }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(endpoint)

                if response.status_code == 404:
                    return {
                        "success": True,
                        "message": "No subsidies found for this organization",
                        "subventions": [],
                        "count": 0,
                    }

                if response.status_code != 200:
                    return {"success": False, "error": f"API error: {response.status_code}"}

                data = response.json()

                subventions = []
                for sub in data.get("subventions", []):
                    subventions.append({
                        "dispositif": sub.get("dispositif"),
                        "montant": sub.get("montant"),
                        "annee": sub.get("annee"),
                        "service_instructeur": sub.get("service_instructeur"),
                        "status": sub.get("statut"),
                    })

                return {
                    "success": True,
                    "identifier": siret or rna,
                    "subventions": subventions,
                    "count": len(subventions),
                    "total_amount": sum(s.get("montant", 0) or 0 for s in subventions),
                }

        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"API error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Subventions search failed: {e}")
            return {"success": False, "error": str(e)}

    async def aides_search(
        text: str | None = None,
        region: str | None = None,
        targeted_audiences: list[str] | None = None,
        categories: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search available territorial aids and funding programs.

        Args:
            text: Search text (keywords)
            region: Region name or code
            targeted_audiences: List of audiences ("commune", "epci", "entreprise", "association")
            categories: List of categories ("urbanisme", "mobilite", "environnement", etc.)
            limit: Maximum results

        Returns:
            Dict with available aids
        """
        try:
            params = {
                "itemsPerPage": min(limit, 50),
            }

            if text:
                params["text"] = text

            if targeted_audiences:
                params["targetedAudiences"] = targeted_audiences

            if categories:
                params["categories"] = categories

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{AIDES_TERRITOIRES_URL}/aids/",
                    params=params,
                )

                if response.status_code != 200:
                    # Fallback: try simpler request
                    response = await client.get(f"{AIDES_TERRITOIRES_URL}/aids/")

                if response.status_code != 200:
                    return {
                        "success": False,
                        "error": f"Aides-territoires API error: {response.status_code}",
                        "tip": "Try using subventions_by_theme with specific keywords",
                    }

                data = response.json()

                aids = []
                for aid in data.get("results", data.get("items", []))[:limit]:
                    aids.append({
                        "name": aid.get("name"),
                        "description": (aid.get("description") or "")[:200],
                        "financers": aid.get("financers", []),
                        "aid_types": aid.get("aid_types", []),
                        "targeted_audiences": aid.get("targeted_audiences", []),
                        "recurrence": aid.get("recurrence"),
                        "application_url": aid.get("application_url"),
                        "is_call_for_project": aid.get("is_call_for_project", False),
                    })

                return {
                    "success": True,
                    "query": text,
                    "aids": aids,
                    "count": len(aids),
                    "total_available": data.get("count", len(aids)),
                }

        except Exception as e:
            logger.error(f"Aides search failed: {e}")
            return {"success": False, "error": str(e)}

    async def subventions_by_theme(
        theme: str,
        region: str | None = None,
    ) -> dict[str, Any]:
        """Search subsidies and aids by theme/sector.

        Searches both Data.Subvention and Aides-territoires.

        Args:
            theme: Theme or sector (e.g., "hydrogène", "innovation", "transition écologique")
            region: Optional region filter

        Returns:
            Dict with relevant funding opportunities
        """
        try:
            # Map themes to search terms
            theme_mappings = {
                "hydrogène": ["hydrogène", "H2", "mobilité propre"],
                "innovation": ["innovation", "R&D", "recherche développement"],
                "transition écologique": ["transition écologique", "environnement", "climat"],
                "numérique": ["numérique", "digital", "transformation digitale"],
                "industrie": ["industrie", "réindustrialisation", "industrie 4.0"],
                "économie circulaire": ["économie circulaire", "recyclage", "réemploi"],
            }

            search_terms = theme_mappings.get(theme.lower(), [theme])

            all_aids = []

            # Search Aides-territoires
            for term in search_terms[:2]:  # Limit to avoid too many requests
                result = await aides_search(text=term, limit=10)
                if result.get("success"):
                    all_aids.extend(result.get("aids", []))

            # Deduplicate by name
            seen = set()
            unique_aids = []
            for aid in all_aids:
                name = aid.get("name", "")
                if name not in seen:
                    seen.add(name)
                    unique_aids.append(aid)

            # Categorize
            calls_for_projects = [a for a in unique_aids if a.get("is_call_for_project")]
            permanent_aids = [a for a in unique_aids if not a.get("is_call_for_project")]

            return {
                "success": True,
                "theme": theme,
                "search_terms": search_terms,
                "calls_for_projects": calls_for_projects[:10],
                "permanent_aids": permanent_aids[:10],
                "total_found": len(unique_aids),
            }

        except Exception as e:
            logger.error(f"Subventions by theme failed: {e}")
            return {"success": False, "error": str(e)}

    async def subventions_stats(
        sirets: list[str],
    ) -> dict[str, Any]:
        """Get aggregated statistics for subsidies across multiple organizations.

        Args:
            sirets: List of SIRET numbers (max 20)

        Returns:
            Dict with aggregated subsidy statistics
        """
        try:
            if len(sirets) > 20:
                return {"success": False, "error": "Maximum 20 SIRETs per request"}

            total_amount = 0
            total_count = 0
            by_year = {}
            by_dispositif = {}
            organizations_with_subsidies = 0

            for siret in sirets:
                result = await subventions_search(siret=siret)
                if result.get("success") and result.get("subventions"):
                    organizations_with_subsidies += 1

                    for sub in result.get("subventions", []):
                        amount = sub.get("montant") or 0
                        total_amount += amount
                        total_count += 1

                        # By year
                        year = sub.get("annee")
                        if year:
                            by_year[year] = by_year.get(year, 0) + amount

                        # By dispositif
                        dispositif = sub.get("dispositif") or "Inconnu"
                        by_dispositif[dispositif] = by_dispositif.get(dispositif, 0) + amount

            return {
                "success": True,
                "organizations_checked": len(sirets),
                "organizations_with_subsidies": organizations_with_subsidies,
                "total_subsidies": total_count,
                "total_amount": total_amount,
                "average_per_organization": round(total_amount / organizations_with_subsidies, 2) if organizations_with_subsidies else 0,
                "by_year": dict(sorted(by_year.items(), reverse=True)[:5]),
                "top_dispositifs": dict(sorted(by_dispositif.items(), key=lambda x: x[1], reverse=True)[:10]),
            }

        except Exception as e:
            logger.error(f"Subventions stats failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["subventions.search"] = Tool(
        name="subventions.search",
        func=subventions_search,
        category=ToolCategory.DATA,
        description="Search subsidies received by organization (SIRET or RNA required).",
    )

    registry._tools["aides.search"] = Tool(
        name="aides.search",
        func=aides_search,
        category=ToolCategory.DATA,
        description="Search available territorial aids and funding programs.",
    )

    registry._tools["subventions.by_theme"] = Tool(
        name="subventions.by_theme",
        func=subventions_by_theme,
        category=ToolCategory.DATA,
        description="Find funding opportunities by theme (hydrogène, innovation, etc.).",
    )

    registry._tools["subventions.stats"] = Tool(
        name="subventions.stats",
        func=subventions_stats,
        category=ToolCategory.DATA,
        description="Get aggregated subsidy statistics for multiple organizations.",
    )

    logger.debug("Registered 4 subventions tools")

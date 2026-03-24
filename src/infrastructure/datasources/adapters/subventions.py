"""Data.gouv Subventions adapter - French public subsidies data."""

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from src.infrastructure.datasources.base import AdapterConfig, BaseAdapter, SyncStatus


class SubventionsAdapter(BaseAdapter):
    """Adapter for French public subsidies data via Data.gouv.fr.

    Uses the Data.gouv.fr API to search for:
    - Subventions datasets
    - Public aids and grants
    - Government financial assistance programs

    API Documentation: https://doc.data.gouv.fr/api/reference/
    """

    BASE_URL = "https://www.data.gouv.fr/api/1"

    def __init__(self, config: AdapterConfig | None = None):
        if config is None:
            config = AdapterConfig(
                name="subventions",
                base_url="https://www.data.gouv.fr/api/1",
                rate_limit=30,
                cache_ttl=86400,  # 24 hours - subventions don't change often
            )
        super().__init__(config)
        self._client = httpx.AsyncClient(timeout=self.config.timeout)

    async def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Search for subventions datasets.

        Args:
            query: Search parameters
                - keywords: Search terms
                - organization: Organization ID or slug
                - tag: Filter by tag
                - limit: Max results (default 20)

        Returns:
            List of subventions/datasets
        """
        # Build search query - always include "subvention" context
        keywords = query.get("keywords", "")
        search_query = f"subvention {keywords}".strip()

        params = {
            "q": search_query,
            "page_size": min(query.get("limit", 20), 50),
        }

        # Add filters
        if org := query.get("organization"):
            params["organization"] = org
        if tag := query.get("tag"):
            params["tag"] = tag

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/datasets/",
                params=params,
            )
            response.raise_for_status()
            data = response.json()

            datasets = data.get("data", [])
            return [self._transform_dataset(ds) for ds in datasets]

        except httpx.HTTPError as e:
            logger.error(f"Subventions search failed: {e}")
            return []

    async def get_by_id(self, id: str) -> dict[str, Any] | None:
        """Get dataset by ID.

        Args:
            id: Dataset ID or slug

        Returns:
            Dataset data or None
        """
        try:
            response = await self._client.get(f"{self.BASE_URL}/datasets/{id}/")
            if response.status_code == 200:
                return self._transform_dataset(response.json())
            return None
        except httpx.HTTPError:
            return None

    async def health_check(self) -> bool:
        """Check if Data.gouv API is available."""
        try:
            response = await self._client.get(
                f"{self.BASE_URL}/datasets/",
                params={"q": "test", "page_size": 1},
            )
            return response.status_code == 200
        except Exception:
            return False

    async def sync(self, since: datetime | None = None) -> SyncStatus:
        """Sync recent subventions datasets."""
        try:
            results = await self.search({"limit": 50})
            return SyncStatus(
                adapter_name=self.name,
                last_sync=datetime.utcnow(),
                records_synced=len(results),
                status="success",
            )
        except Exception as e:
            return SyncStatus(
                adapter_name=self.name,
                last_sync=None,
                records_synced=0,
                status="failed",
                error=str(e),
            )

    def _transform_dataset(self, dataset: dict) -> dict[str, Any]:
        """Transform dataset to standard format."""
        org = dataset.get("organization") or {}
        return {
            "source": "subventions",
            "id": dataset.get("id"),
            "slug": dataset.get("slug"),
            "title": dataset.get("title"),
            "description": dataset.get("description", ""),
            "url": dataset.get("page"),
            "organization": org.get("name"),
            "organization_id": org.get("id"),
            "tags": dataset.get("tags", []),
            "frequency": dataset.get("frequency"),
            "created_at": dataset.get("created_at"),
            "last_modified": dataset.get("last_modified"),
            "resources_count": len(dataset.get("resources", [])),
            "resources": [
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "format": r.get("format"),
                    "url": r.get("url"),
                }
                for r in dataset.get("resources", [])[:5]  # Limit to 5 resources
            ],
            "raw": dataset,
        }

    async def search_by_organization(
        self,
        org_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search subventions by organization (convenience method).

        Args:
            org_name: Organization name to search
            limit: Max results

        Returns:
            List of subventions datasets from that organization
        """
        return await self.search(
            {
                "keywords": org_name,
                "limit": limit,
            }
        )

    async def search_by_territory(
        self,
        territory: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search subventions by territory (convenience method).

        Args:
            territory: Territory name (region, department, commune)
            limit: Max results

        Returns:
            List of subventions datasets for that territory
        """
        return await self.search(
            {
                "keywords": territory,
                "limit": limit,
            }
        )

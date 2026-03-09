"""Tests for Google News RSS adapter."""

import pytest

from src.infrastructure.datasources.adapters.google_news import GoogleNewsAdapter


@pytest.mark.asyncio
async def test_google_news_search():
    """Test searching Google News."""
    adapter = GoogleNewsAdapter()
    results = await adapter.search(
        {
            "keywords": "startup intelligence artificielle",
            "limit": 5,
        }
    )
    assert len(results) > 0
    assert "title" in results[0]
    assert "url" in results[0]

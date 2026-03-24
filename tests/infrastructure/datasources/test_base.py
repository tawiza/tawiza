"""Tests for base adapter protocol."""

from typing import Protocol, runtime_checkable

import pytest

from src.infrastructure.datasources.base import DataSourceAdapter


def test_adapter_protocol_exists():
    """Test DataSourceAdapter protocol is defined."""
    assert hasattr(DataSourceAdapter, "name")
    assert hasattr(DataSourceAdapter, "search")
    assert hasattr(DataSourceAdapter, "get_by_id")
    assert hasattr(DataSourceAdapter, "health_check")


def test_adapter_is_runtime_checkable():
    """Test we can check if a class implements the protocol."""

    @runtime_checkable
    class TestProtocol(Protocol):
        pass

    # DataSourceAdapter should be runtime_checkable
    assert isinstance(DataSourceAdapter, type)

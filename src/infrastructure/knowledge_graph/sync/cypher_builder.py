"""Cypher query builder for Neo4j sync."""
from typing import Any

from .queue import SyncItem


class CypherBuilder:
    """Builds Cypher queries from SyncItems."""

    # Node type to label mapping
    LABELS = {
        "Company": "Company",
        "Establishment": "Establishment",
        "Territory": "Territory",
        "Sector": "Sector",
    }

    # Node type to unique key mapping
    UNIQUE_KEYS = {
        "Company": "siren",
        "Establishment": "siret",
        "Territory": "code",
        "Sector": "naf_code",
    }

    @classmethod
    def build_single(cls, item: SyncItem) -> tuple[str, dict[str, Any]]:
        """
        Build query for single item.

        Returns:
            (query, parameters)
        """
        label = cls.LABELS.get(item.node_type, item.node_type)
        key = cls.UNIQUE_KEYS.get(item.node_type, "id")
        key_value = item.data.get(key)

        if item.operation == "merge":
            query = f"""
            MERGE (n:{label} {{{key}: ${key}}})
            SET n += $props
            RETURN n
            """
        elif item.operation == "create":
            query = f"""
            CREATE (n:{label})
            SET n = $props
            RETURN n
            """
        elif item.operation == "delete":
            query = f"""
            MATCH (n:{label} {{{key}: ${key}}})
            DELETE n
            """
        else:
            raise ValueError(f"Unknown operation: {item.operation}")

        params = {key: key_value, "props": item.data}
        return query, params

    @classmethod
    def build_batch(cls, items: list[SyncItem]) -> tuple[str, dict[str, Any]]:
        """
        Build batch UNWIND query for items of same type.

        Returns:
            (query, parameters)
        """
        if not items:
            return "", {}

        # Assume all items are same type for batch
        first = items[0]
        label = cls.LABELS.get(first.node_type, first.node_type)
        key = cls.UNIQUE_KEYS.get(first.node_type, "id")

        query = f"""
        UNWIND $items AS item
        MERGE (n:{label} {{{key}: item.{key}}})
        SET n += item
        RETURN count(n) as count
        """

        params = {"items": [item.data for item in items]}
        return query, params

    @classmethod
    def build_with_relationship(
        cls,
        item: SyncItem
    ) -> tuple[str, dict[str, Any]]:
        """
        Build query with relationship.

        Returns:
            (query, parameters)
        """
        if not item.relationship:
            return cls.build_single(item)

        rel = item.relationship
        label = cls.LABELS.get(item.node_type, item.node_type)
        key = cls.UNIQUE_KEYS.get(item.node_type, "id")
        key_value = item.data.get(key)

        target_label = cls.LABELS.get(rel["target_type"], rel["target_type"])
        target_key = rel["target_key"]
        rel_type = rel["type"]

        query = f"""
        MERGE (n:{label} {{{key}: ${key}}})
        SET n += $props
        WITH n
        MATCH (t:{target_label} {{{target_key}: $target_value}})
        MERGE (n)-[r:{rel_type}]->(t)
        RETURN n, r, t
        """

        params = {
            key: key_value,
            "props": item.data,
            "target_value": rel["target_value"]
        }
        return query, params

"""
Vector store infrastructure with pgvector
"""
from .pgvector_client import PGVectorClient, SearchResult

__all__ = ["PGVectorClient", "SearchResult"]

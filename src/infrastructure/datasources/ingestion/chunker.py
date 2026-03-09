"""Text chunking for document ingestion."""
from dataclasses import dataclass


@dataclass
class TextChunker:
    """Split text into overlapping chunks."""

    chunk_size: int = 512
    overlap: int = 50

    def chunk(self, text: str) -> list[str]:
        """Split text into chunks with overlap."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.overlap

        return chunks

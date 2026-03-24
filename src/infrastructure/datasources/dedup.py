"""Headline deduplication using word-level Jaccard similarity.

Inspired by World Monitor's dedup.mjs implementation.
Prevents duplicate news from different sources cluttering the feed.
"""

import re
from typing import Any

# French + English stop words (common words to exclude from similarity)
STOP_WORDS = frozenset(
    {
        # French
        "les",
        "des",
        "une",
        "pour",
        "dans",
        "sur",
        "par",
        "avec",
        "plus",
        "que",
        "qui",
        "est",
        "sont",
        "ont",
        "pas",
        "ses",
        "son",
        "aux",
        "cette",
        "ces",
        "leur",
        "tous",
        "tout",
        "mais",
        "aussi",
        "très",
        "fait",
        "être",
        "avoir",
        "entre",
        "après",
        "depuis",
        "sans",
        "encore",
        "autre",
        "même",
        "nous",
        "vous",
        "ils",
        "elle",
        # English
        "the",
        "and",
        "for",
        "that",
        "with",
        "this",
        "from",
        "has",
        "have",
        "was",
        "were",
        "are",
        "been",
        "will",
        "would",
        "could",
        "should",
        "about",
        "their",
        "which",
        "when",
        "what",
        "where",
        "than",
        "they",
        "into",
        "more",
        "some",
        "over",
        "also",
        "after",
        "before",
    }
)

# Minimum word length for meaningful comparison
MIN_WORD_LENGTH = 4

# Similarity threshold (0.0-1.0) — >0.6 = duplicate
SIMILARITY_THRESHOLD = 0.6


def _tokenize(text: str) -> set[str]:
    """Tokenize text into meaningful words.

    Args:
        text: Raw headline text

    Returns:
        Set of normalized words (lowercase, no punctuation, min length)
    """
    normalized = text.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return {w for w in normalized.split() if len(w) >= MIN_WORD_LENGTH and w not in STOP_WORDS}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Calculate Jaccard similarity between two texts.

    Uses word overlap with minimum word length filtering.
    This is the same approach World Monitor uses (intersection / min_size).

    Args:
        text_a: First text
        text_b: Second text

    Returns:
        Similarity score (0.0-1.0)
    """
    words_a = _tokenize(text_a)
    words_b = _tokenize(text_b)

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    # Using min(size) instead of union for better near-duplicate detection
    min_size = min(len(words_a), len(words_b))

    if min_size == 0:
        return 0.0

    return len(intersection) / min_size


def deduplicate_headlines(
    items: list[dict[str, Any]],
    title_key: str = "title",
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[dict[str, Any]]:
    """Deduplicate a list of items by headline similarity.

    Preserves order — first occurrence is kept.

    Args:
        items: List of dicts containing headlines
        title_key: Key to use for title comparison
        threshold: Similarity threshold (default 0.6)

    Returns:
        Deduplicated list (preserving order)
    """
    seen_tokens: list[set[str]] = []
    unique: list[dict[str, Any]] = []

    for item in items:
        title = item.get(title_key, "")
        if not title:
            continue

        tokens = _tokenize(title)
        if not tokens:
            unique.append(item)
            continue

        is_duplicate = False
        for seen in seen_tokens:
            if not seen:
                continue
            intersection = tokens & seen
            min_size = min(len(tokens), len(seen))
            if min_size > 0 and len(intersection) / min_size > threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            seen_tokens.append(tokens)
            unique.append(item)

    return unique


def deduplicate_by_url(
    items: list[dict[str, Any]],
    url_key: str = "url",
) -> list[dict[str, Any]]:
    """Simple URL-based deduplication.

    Args:
        items: List of dicts containing URLs
        url_key: Key to use for URL comparison

    Returns:
        Deduplicated list (first occurrence kept)
    """
    seen_urls: set[str] = set()
    unique: list[dict[str, Any]] = []

    for item in items:
        url = item.get(url_key, "")
        if not url:
            unique.append(item)
            continue

        # Normalize URL (strip trailing slash, query params for comparison)
        normalized = url.rstrip("/").split("?")[0].lower()
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            unique.append(item)

    return unique

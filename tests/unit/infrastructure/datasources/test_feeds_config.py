"""Unit tests for the RSS feeds configuration module (issue #161, batch 4 coverage).

Covers:
- FeedCategory / FeedPriority enums (values, members, str/int behaviour).
- FeedConfig dataclass: construction with required + default fields, mutable
  default isolation (tags), and positional/keyword construction.
- The FEEDS registry: presence, structure, identifier uniqueness, valid
  category/priority/language values, well-formed URLs.
- Helper functions: get_feeds_by_category, get_feeds_by_region,
  get_feeds_by_priority, get_all_feed_urls, get_feed_count.

The production code is the source of truth; these tests assert its real
behaviour. No production API is invented.
"""

from enum import Enum, StrEnum

import pytest

from src.infrastructure.datasources.feeds_config import (
    FEEDS,
    FeedCategory,
    FeedConfig,
    FeedPriority,
    get_all_feed_urls,
    get_feed_count,
    get_feeds_by_category,
    get_feeds_by_priority,
    get_feeds_by_region,
)


# ---------------------------------------------------------------------------
# FeedCategory enum
# ---------------------------------------------------------------------------
class TestFeedCategoryEnum:
    """Tests for the FeedCategory StrEnum."""

    def test_is_str_enum(self):
        assert issubclass(FeedCategory, StrEnum)

    def test_values(self):
        assert FeedCategory.ECO_NATIONAL.value == "eco_national"
        assert FeedCategory.ECO_REGIONAL.value == "eco_regional"
        assert FeedCategory.STARTUPS.value == "startups"
        assert FeedCategory.INDUSTRY.value == "industry"
        assert FeedCategory.INSTITUTIONS.value == "institutions"
        assert FeedCategory.THINK_TANKS.value == "think_tanks"
        assert FeedCategory.INTERNATIONAL.value == "international"
        assert FeedCategory.TECH.value == "tech"
        assert FeedCategory.SECURITY.value == "security"
        assert FeedCategory.ENVIRONMENT.value == "environment"

    def test_str_behaviour(self):
        # StrEnum members compare equal to their string value.
        assert FeedCategory.TECH == "tech"
        assert str(FeedCategory.SECURITY) == "security"

    def test_member_count(self):
        assert len(list(FeedCategory)) == 10

    def test_all_values_unique(self):
        values = [c.value for c in FeedCategory]
        assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# FeedPriority enum
# ---------------------------------------------------------------------------
class TestFeedPriorityEnum:
    """Tests for the FeedPriority int Enum."""

    def test_is_int_enum(self):
        assert issubclass(FeedPriority, int)
        assert issubclass(FeedPriority, Enum)

    def test_values(self):
        assert FeedPriority.CRITICAL.value == 1
        assert FeedPriority.HIGH.value == 2
        assert FeedPriority.MEDIUM.value == 3
        assert FeedPriority.LOW.value == 4

    def test_int_behaviour(self):
        assert FeedPriority.CRITICAL == 1
        assert int(FeedPriority.LOW) == 4

    def test_ordering_by_value(self):
        # Lower value = higher priority.
        assert FeedPriority.CRITICAL.value < FeedPriority.HIGH.value
        assert FeedPriority.HIGH.value < FeedPriority.MEDIUM.value
        assert FeedPriority.MEDIUM.value < FeedPriority.LOW.value

    def test_member_count(self):
        assert len(list(FeedPriority)) == 4


# ---------------------------------------------------------------------------
# FeedConfig dataclass
# ---------------------------------------------------------------------------
class TestFeedConfig:
    """Tests for the FeedConfig dataclass."""

    def test_minimal_construction_defaults(self):
        feed = FeedConfig(
            name="Test",
            url="https://example.com/rss",
            category=FeedCategory.TECH,
        )
        assert feed.name == "Test"
        assert feed.url == "https://example.com/rss"
        assert feed.category == FeedCategory.TECH
        # Defaults.
        assert feed.priority == FeedPriority.MEDIUM
        assert feed.language == "fr"
        assert feed.region is None
        assert feed.refresh_interval == 300
        assert feed.max_items == 20
        assert feed.enabled is True
        assert feed.tags == []

    def test_full_construction_keyword(self):
        feed = FeedConfig(
            name="Full",
            url="https://example.com/full.xml",
            category=FeedCategory.SECURITY,
            priority=FeedPriority.CRITICAL,
            language="en",
            region="13",
            refresh_interval=600,
            max_items=50,
            enabled=False,
            tags=["a", "b"],
        )
        assert feed.priority == FeedPriority.CRITICAL
        assert feed.language == "en"
        assert feed.region == "13"
        assert feed.refresh_interval == 600
        assert feed.max_items == 50
        assert feed.enabled is False
        assert feed.tags == ["a", "b"]

    def test_positional_construction_matches_registry_usage(self):
        # The registry builds feeds positionally: name, url, category, priority.
        feed = FeedConfig(
            "Pos",
            "https://example.com/pos.xml",
            FeedCategory.ECO_NATIONAL,
            FeedPriority.HIGH,
        )
        assert feed.name == "Pos"
        assert feed.url == "https://example.com/pos.xml"
        assert feed.category == FeedCategory.ECO_NATIONAL
        assert feed.priority == FeedPriority.HIGH

    def test_tags_default_is_isolated_per_instance(self):
        # field(default_factory=list) must not share state between instances.
        a = FeedConfig("A", "https://a.test", FeedCategory.TECH)
        b = FeedConfig("B", "https://b.test", FeedCategory.TECH)
        a.tags.append("x")
        assert a.tags == ["x"]
        assert b.tags == []


# ---------------------------------------------------------------------------
# FEEDS registry structure and integrity
# ---------------------------------------------------------------------------
class TestFeedsRegistry:
    """Tests for the FEEDS list as a whole."""

    def test_is_non_empty_list_of_feedconfig(self):
        assert isinstance(FEEDS, list)
        assert len(FEEDS) > 0
        assert all(isinstance(f, FeedConfig) for f in FEEDS)

    def test_all_names_non_empty(self):
        assert all(f.name and f.name.strip() for f in FEEDS)

    def test_names_are_unique(self):
        names = [f.name for f in FEEDS]
        duplicates = {n for n in names if names.count(n) > 1}
        assert len(names) == len(set(names)), f"Duplicate feed names: {duplicates}"

    def test_all_urls_well_formed(self):
        for f in FEEDS:
            assert f.url.startswith(("http://", "https://")), (
                f"Feed {f.name!r} has malformed URL: {f.url}"
            )

    def test_all_categories_are_valid_members(self):
        valid = set(FeedCategory)
        assert all(f.category in valid for f in FEEDS)

    def test_all_priorities_are_valid_members(self):
        valid = set(FeedPriority)
        assert all(f.priority in valid for f in FEEDS)

    def test_all_languages_known(self):
        # Module only declares fr/en feeds.
        assert all(f.language in {"fr", "en"} for f in FEEDS)

    def test_refresh_interval_positive(self):
        assert all(f.refresh_interval > 0 for f in FEEDS)

    def test_max_items_positive(self):
        assert all(f.max_items > 0 for f in FEEDS)

    def test_every_category_has_at_least_one_feed(self):
        present = {f.category for f in FEEDS}
        assert present == set(FeedCategory)

    def test_at_least_one_feed_enabled(self):
        assert any(f.enabled for f in FEEDS)

    def test_some_feeds_disabled(self):
        # Registry intentionally ships some feeds disabled by default.
        assert any(not f.enabled for f in FEEDS)


# ---------------------------------------------------------------------------
# get_feeds_by_category
# ---------------------------------------------------------------------------
class TestGetFeedsByCategory:
    def test_returns_only_enabled_matching_category(self):
        result = get_feeds_by_category(FeedCategory.SECURITY)
        assert all(f.category == FeedCategory.SECURITY for f in result)
        assert all(f.enabled for f in result)

    def test_matches_manual_filter(self):
        for category in FeedCategory:
            expected = [
                f for f in FEEDS if f.category == category and f.enabled
            ]
            assert get_feeds_by_category(category) == expected

    def test_returns_list(self):
        assert isinstance(get_feeds_by_category(FeedCategory.TECH), list)


# ---------------------------------------------------------------------------
# get_feeds_by_region
# ---------------------------------------------------------------------------
class TestGetFeedsByRegion:
    def test_returns_only_enabled_matching_region(self):
        result = get_feeds_by_region("13")
        assert all(f.region == "13" for f in result)
        assert all(f.enabled for f in result)

    def test_known_region_has_feeds(self):
        # "13" (Bouches-du-Rhone / PACA) is a focus region in the registry.
        assert len(get_feeds_by_region("13")) >= 1

    def test_unknown_region_returns_empty(self):
        assert get_feeds_by_region("zzz-not-a-region") == []

    def test_matches_manual_filter(self):
        expected = [f for f in FEEDS if f.region == "06" and f.enabled]
        assert get_feeds_by_region("06") == expected


# ---------------------------------------------------------------------------
# get_feeds_by_priority
# ---------------------------------------------------------------------------
class TestGetFeedsByPriority:
    def test_critical_only_returns_critical_enabled(self):
        result = get_feeds_by_priority(FeedPriority.CRITICAL)
        assert all(f.priority == FeedPriority.CRITICAL for f in result)
        assert all(f.enabled for f in result)

    def test_higher_threshold_is_superset(self):
        # max_priority=LOW (value 4) includes everything <= 4.
        critical = get_feeds_by_priority(FeedPriority.CRITICAL)
        low = get_feeds_by_priority(FeedPriority.LOW)
        assert len(low) >= len(critical)
        critical_names = {f.name for f in critical}
        low_names = {f.name for f in low}
        assert critical_names <= low_names

    def test_low_threshold_returns_all_enabled(self):
        result = get_feeds_by_priority(FeedPriority.LOW)
        expected = [f for f in FEEDS if f.enabled]
        assert {f.name for f in result} == {f.name for f in expected}

    def test_matches_manual_filter(self):
        expected = [
            f
            for f in FEEDS
            if f.priority.value <= FeedPriority.MEDIUM.value and f.enabled
        ]
        assert get_feeds_by_priority(FeedPriority.MEDIUM) == expected


# ---------------------------------------------------------------------------
# get_all_feed_urls
# ---------------------------------------------------------------------------
class TestGetAllFeedUrls:
    def test_returns_dict_of_name_to_url(self):
        urls = get_all_feed_urls()
        assert isinstance(urls, dict)
        for name, url in urls.items():
            assert isinstance(name, str)
            assert url.startswith(("http://", "https://"))

    def test_only_enabled_feeds_included(self):
        urls = get_all_feed_urls()
        enabled_names = {f.name for f in FEEDS if f.enabled}
        assert set(urls.keys()) == enabled_names

    def test_disabled_feeds_excluded(self):
        urls = get_all_feed_urls()
        for f in FEEDS:
            if not f.enabled:
                assert f.name not in urls

    def test_url_values_match_registry(self):
        urls = get_all_feed_urls()
        for f in FEEDS:
            if f.enabled:
                assert urls[f.name] == f.url


# ---------------------------------------------------------------------------
# get_feed_count
# ---------------------------------------------------------------------------
class TestGetFeedCount:
    def test_returns_dict_keyed_by_category_value(self):
        counts = get_feed_count()
        assert isinstance(counts, dict)
        valid_values = {c.value for c in FeedCategory}
        assert set(counts.keys()) <= valid_values

    def test_total_equals_full_registry_length(self):
        # Counts include disabled feeds (no enabled filter in get_feed_count).
        counts = get_feed_count()
        assert sum(counts.values()) == len(FEEDS)

    def test_per_category_matches_manual_count(self):
        counts = get_feed_count()
        for category in FeedCategory:
            manual = sum(1 for f in FEEDS if f.category == category)
            if manual:
                assert counts[category.value] == manual

    def test_all_counts_positive(self):
        counts = get_feed_count()
        assert all(v > 0 for v in counts.values())


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])

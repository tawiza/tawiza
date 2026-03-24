"""Tests for AlertService - territorial alert management."""

from datetime import datetime

import pytest

from src.application.services.alert_service import (
    Alert,
    AlertRule,
    AlertService,
    AlertSeverity,
    AlertStatus,
    AlertType,
    get_alert_service,
)


class TestAlertEnums:
    """Test alert enums have expected values."""

    def test_alert_types(self):
        assert AlertType.ENTERPRISE_CREATION.value == "enterprise_creation"
        assert AlertType.ENTERPRISE_CLOSURE.value == "enterprise_closure"
        assert AlertType.MARKET_OPPORTUNITY.value == "market_opportunity"
        assert AlertType.JOB_MARKET_CHANGE.value == "job_market_change"
        assert AlertType.REAL_ESTATE_CHANGE.value == "real_estate_change"
        assert AlertType.SUBSIDY_AVAILABLE.value == "subsidy_available"
        assert len(AlertType) == 8

    def test_alert_severity(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_status(self):
        assert AlertStatus.NEW.value == "new"
        assert AlertStatus.READ.value == "read"
        assert AlertStatus.ARCHIVED.value == "archived"


class TestAlertDataclass:
    """Test Alert dataclass."""

    def test_create_alert(self):
        alert = Alert(
            id="test-1",
            type=AlertType.ENTERPRISE_CREATION,
            severity=AlertSeverity.INFO,
            title="Test Alert",
            description="Test description",
            territory="75",
            sector="62.01Z",
            data={"name": "TestCorp"},
            created_at=datetime(2026, 1, 1),
        )
        assert alert.id == "test-1"
        assert alert.type == AlertType.ENTERPRISE_CREATION
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.NEW  # default
        assert alert.source_id is None  # default

    def test_alert_default_status(self):
        alert = Alert(
            id="test-2",
            type=AlertType.MARKET_OPPORTUNITY,
            severity=AlertSeverity.WARNING,
            title="Market",
            description="Desc",
            territory=None,
            sector=None,
            data={},
            created_at=datetime.now(),
        )
        assert alert.status == AlertStatus.NEW


class TestAlertRule:
    """Test AlertRule dataclass."""

    def test_create_rule(self):
        rule = AlertRule(
            id="rule-1",
            name="Test Rule",
            alert_type=AlertType.ENTERPRISE_CREATION,
            condition=lambda d: True,
            severity=AlertSeverity.INFO,
        )
        assert rule.id == "rule-1"
        assert rule.enabled is True  # default
        assert rule.territories is None
        assert rule.sectors is None

    def test_rule_condition(self):
        rule = AlertRule(
            id="rule-2",
            name="High Amount",
            alert_type=AlertType.MARKET_OPPORTUNITY,
            condition=lambda d: d.get("amount", 0) > 100,
            severity=AlertSeverity.WARNING,
        )
        assert rule.condition({"amount": 200}) is True
        assert rule.condition({"amount": 50}) is False
        assert rule.condition({}) is False


class TestAlertService:
    """Test AlertService business logic."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton between tests."""
        AlertService._instance = None
        yield
        AlertService._instance = None

    @pytest.fixture
    def service(self):
        return AlertService()

    def test_init_has_default_rules(self, service):
        assert len(service._rules) == 5  # 5 default rules

    def test_add_rule(self, service):
        initial = len(service._rules)
        service.add_rule(
            AlertRule(
                id="custom",
                name="Custom",
                alert_type=AlertType.ECONOMIC_INDICATOR,
                condition=lambda d: True,
                severity=AlertSeverity.CRITICAL,
            )
        )
        assert len(service._rules) == initial + 1

    def test_process_data_triggers_alert(self, service):
        # Tech company creation matches the "tech_creation" default rule
        data = {"name": "TechStartup", "naf_code": "62.01Z"}
        alerts = service.process_data(
            data=data,
            source_id="test-source",
            data_type=AlertType.ENTERPRISE_CREATION,
            territory="75",
        )
        assert len(alerts) >= 1
        alert = alerts[0]
        assert alert.type == AlertType.ENTERPRISE_CREATION
        assert alert.severity == AlertSeverity.INFO
        assert "TechStartup" in alert.title
        assert alert.territory == "75"

    def test_process_data_no_match(self, service):
        # Non-tech company, shouldn't match tech_creation rule's sector filter
        data = {"name": "Bakery", "naf_code": "10.71A"}
        alerts = service.process_data(
            data=data,
            source_id="test-source",
            data_type=AlertType.ENTERPRISE_CREATION,
        )
        assert len(alerts) == 0

    def test_process_data_major_closure(self, service):
        data = {"name": "BigCorp", "employees": 100}
        alerts = service.process_data(
            data=data,
            source_id="bodacc",
            data_type=AlertType.ENTERPRISE_CLOSURE,
        )
        assert len(alerts) >= 1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_process_data_market_opportunity(self, service):
        data = {"title": "Marché informatique", "amount": 200000}
        alerts = service.process_data(
            data=data,
            source_id="boamp",
            data_type=AlertType.MARKET_OPPORTUNITY,
        )
        assert len(alerts) >= 1

    def test_process_data_job_variation(self, service):
        data = {"territory": "75", "variation_pct": 15.0}
        alerts = service.process_data(
            data=data,
            source_id="france-travail",
            data_type=AlertType.JOB_MARKET_CHANGE,
        )
        assert len(alerts) >= 1
        assert alerts[0].severity == AlertSeverity.WARNING

    def test_process_data_disabled_rule(self, service):
        # Disable all rules
        for rule in service._rules:
            rule.enabled = False
        data = {"name": "TechCo", "naf_code": "62.01Z"}
        alerts = service.process_data(
            data=data,
            source_id="test",
            data_type=AlertType.ENTERPRISE_CREATION,
        )
        assert len(alerts) == 0

    def test_get_alerts_empty(self, service):
        alerts = service.get_alerts()
        assert alerts == []

    def test_get_alerts_filtered_by_status(self, service):
        # Trigger some alerts
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )
        assert len(service.get_alerts(status=AlertStatus.NEW)) >= 1
        assert len(service.get_alerts(status=AlertStatus.READ)) == 0

    def test_get_alerts_filtered_by_type(self, service):
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )
        assert len(service.get_alerts(alert_type=AlertType.ENTERPRISE_CREATION)) >= 1
        assert len(service.get_alerts(alert_type=AlertType.REAL_ESTATE_CHANGE)) == 0

    def test_get_alerts_filtered_by_territory(self, service):
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
            territory="75",
        )
        assert len(service.get_alerts(territory="75")) >= 1
        assert len(service.get_alerts(territory="13")) == 0

    def test_get_alerts_limit(self, service):
        # Generate multiple alerts
        for i in range(5):
            service.process_data(
                {"name": f"Co{i}", "naf_code": "62.01Z"},
                "src",
                AlertType.ENTERPRISE_CREATION,
            )
        assert len(service.get_alerts(limit=2)) == 2

    def test_mark_read(self, service):
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )
        alert_id = service._alerts[0].id
        assert service.mark_read(alert_id) is True
        assert service._alerts[0].status == AlertStatus.READ

    def test_mark_read_not_found(self, service):
        assert service.mark_read("nonexistent") is False

    def test_archive(self, service):
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )
        alert_id = service._alerts[0].id
        assert service.archive(alert_id) is True
        assert service._alerts[0].status == AlertStatus.ARCHIVED

    def test_archive_not_found(self, service):
        assert service.archive("nonexistent") is False

    def test_get_stats_empty(self, service):
        stats = service.get_stats()
        assert stats["total"] == 0
        assert stats["new"] == 0
        assert stats["rules_count"] == 5

    def test_get_stats_with_alerts(self, service):
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )
        stats = service.get_stats()
        assert stats["total"] >= 1
        assert stats["new"] >= 1
        assert "enterprise_creation" in stats["by_type"]
        assert "info" in stats["by_severity"]

    def test_on_alert_handler(self, service):
        received = []
        service.on_alert(lambda a: received.append(a))
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )
        assert len(received) >= 1
        assert isinstance(received[0], Alert)

    def test_on_alert_handler_error_doesnt_crash(self, service):
        def bad_handler(a):
            raise ValueError("boom")

        service.on_alert(bad_handler)
        # Should not raise
        service.process_data(
            {"name": "Co", "naf_code": "62.01Z"},
            "src",
            AlertType.ENTERPRISE_CREATION,
        )

    def test_singleton(self):
        s1 = AlertService.get_instance()
        s2 = AlertService.get_instance()
        assert s1 is s2

    def test_get_alert_service_func(self):
        s = get_alert_service()
        assert isinstance(s, AlertService)

    def test_generate_title_templates(self, service):
        rule_creation = AlertRule(
            id="t",
            name="Test",
            alert_type=AlertType.ENTERPRISE_CREATION,
            condition=lambda d: True,
            severity=AlertSeverity.INFO,
        )
        title = service._generate_title({"name": "Acme"}, rule_creation)
        assert "Acme" in title

        rule_closure = AlertRule(
            id="t",
            name="Test",
            alert_type=AlertType.ENTERPRISE_CLOSURE,
            condition=lambda d: True,
            severity=AlertSeverity.INFO,
        )
        title = service._generate_title({"name": "OldCorp"}, rule_closure)
        assert "OldCorp" in title

    def test_generate_description(self, service):
        rule = AlertRule(
            id="t",
            name="My Rule",
            alert_type=AlertType.MARKET_OPPORTUNITY,
            condition=lambda d: True,
            severity=AlertSeverity.INFO,
        )
        desc = service._generate_description(
            {"department": "75", "city": "Paris", "naf_code": "62.01Z", "amount": 50000},
            rule,
        )
        assert "My Rule" in desc
        assert "75" in desc
        assert "Paris" in desc
        assert "62.01Z" in desc
        assert "50" in desc  # amount formatted

    def test_territory_filter(self, service):
        """Rules with territory filter should only match specific territories."""
        service._rules.clear()
        service.add_rule(
            AlertRule(
                id="paris-only",
                name="Paris only",
                alert_type=AlertType.ENTERPRISE_CREATION,
                condition=lambda d: True,
                severity=AlertSeverity.INFO,
                territories=["75"],
            )
        )
        # Match
        alerts = service.process_data(
            {"name": "Co"},
            "src",
            AlertType.ENTERPRISE_CREATION,
            territory="75",
        )
        assert len(alerts) == 1
        # No match
        alerts = service.process_data(
            {"name": "Co"},
            "src",
            AlertType.ENTERPRISE_CREATION,
            territory="13",
        )
        assert len(alerts) == 0

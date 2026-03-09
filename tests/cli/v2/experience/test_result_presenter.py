"""Tests for result presenter."""

import pytest

from src.cli.v2.experience.result_presenter import ResultAction, ResultPresenter


class TestResultPresenter:
    @pytest.fixture
    def presenter(self):
        return ResultPresenter()

    def test_small_result_inline(self, presenter):
        """Small results display inline."""
        display = presenter.format_for_display("Hello, world!")
        assert display.is_inline
        assert "Hello, world!" in display.content

    def test_large_result_preview(self, presenter):
        """Large results show preview with truncation."""
        large_content = "Line " * 1000
        display = presenter.format_for_display(large_content)
        assert not display.is_inline
        assert display.preview is not None
        assert len(display.preview) < len(large_content)

    def test_available_actions(self, presenter):
        """Results have available actions."""
        display = presenter.format_for_display("Some content here")
        assert ResultAction.VIEW in display.actions
        assert ResultAction.SAVE in display.actions
        assert ResultAction.COPY in display.actions

    def test_table_detection(self, presenter):
        """Tabular data is detected and formatted."""
        csv_data = "name,age\nAlice,30\nBob,25"
        display = presenter.format_for_display(csv_data)
        assert display.detected_format == "table"

    def test_code_detection(self, presenter):
        """Code is detected and syntax highlighted."""
        code = "def hello():\n    print('Hello')"
        display = presenter.format_for_display(code)
        assert display.detected_format == "code"

    def test_chain_result_stores(self, presenter):
        """Results can be stored for chaining."""
        presenter.store_result("test_result", {"data": [1, 2, 3]})
        retrieved = presenter.get_result("test_result")
        assert retrieved == {"data": [1, 2, 3]}

    def test_last_result_shortcut(self, presenter):
        """$LAST retrieves most recent result."""
        presenter.store_result("first", "First result")
        presenter.store_result("second", "Second result")
        assert presenter.get_last_result() == "Second result"

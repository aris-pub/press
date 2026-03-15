"""Tests for Sentry alert configuration and abuse pattern detection."""

from unittest.mock import patch

import pytest

from app.sentry_config import before_send, report_rate_limit_hit, report_rapid_uploads


class TestBeforeSend:
    """Tests for the Sentry before_send filter."""

    def test_filters_testing_events(self):
        event = {"level": "error", "exception": {"values": [{"type": "ValueError"}]}}
        result = before_send(event, {}, environment="testing")
        assert result is None

    def test_passes_production_events(self):
        event = {"level": "error", "exception": {"values": [{"type": "ValueError"}]}}
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_filters_404_errors(self):
        event = {
            "level": "error",
            "exception": {"values": [{"type": "HTTPException", "value": "404 Not Found"}]},
        }
        result = before_send(event, {}, environment="production")
        assert result is None

    def test_passes_500_errors(self):
        event = {
            "level": "error",
            "exception": {
                "values": [{"type": "HTTPException", "value": "500 Internal Server Error"}]
            },
        }
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_passes_non_exception_events(self):
        event = {"level": "info", "message": "Test message"}
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_passes_development_events(self):
        event = {"level": "error", "exception": {"values": [{"type": "RuntimeError"}]}}
        result = before_send(event, {}, environment="development")
        assert result == event

    def test_handles_missing_exception_values(self):
        event = {"level": "error", "exception": {}}
        result = before_send(event, {}, environment="production")
        assert result == event

    def test_handles_empty_exception_values(self):
        event = {"level": "error", "exception": {"values": []}}
        result = before_send(event, {}, environment="production")
        assert result == event


class TestReportRateLimitHit:
    """Tests for rate limit abuse reporting to Sentry."""

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_rate_limit_hit(self, mock_sentry):
        report_rate_limit_hit(client_ip="1.2.3.4", path="/upload-form", method="POST")

        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert "Rate limit hit" in call_args[0][0]
        assert call_args[1]["level"] == "warning"

    @patch("app.sentry_config.sentry_sdk")
    def test_sets_fingerprint_for_grouping(self, mock_sentry):
        mock_sentry.push_scope.return_value.__enter__ = lambda s: s
        mock_sentry.push_scope.return_value.__exit__ = lambda s, *a: None

        report_rate_limit_hit(client_ip="1.2.3.4", path="/upload", method="POST")

        mock_sentry.capture_message.assert_called_once()


class TestReportRapidUploads:
    """Tests for rapid upload abuse reporting to Sentry."""

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_rapid_uploads(self, mock_sentry):
        report_rapid_uploads(user_id="user-123", upload_count=5, window_seconds=3600)

        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert "Rapid upload" in call_args[0][0]
        assert call_args[1]["level"] == "warning"

    @patch("app.sentry_config.sentry_sdk")
    def test_includes_user_context(self, mock_sentry):
        report_rapid_uploads(user_id="user-456", upload_count=10, window_seconds=3600)

        mock_sentry.set_user.assert_called_once_with({"id": "user-456"})


class TestStorageThresholdReport:
    """Tests for storage consumption threshold reporting."""

    @patch("app.sentry_config.sentry_sdk")
    def test_reports_storage_threshold(self, mock_sentry):
        from app.sentry_config import report_storage_threshold

        report_storage_threshold(
            user_id="user-789", total_bytes=524288000, scroll_count=50
        )

        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert "Storage threshold" in call_args[0][0]
        assert call_args[1]["level"] == "warning"

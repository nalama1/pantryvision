"""Unit tests for get_alert_config().

Validates: Requirements 2.8, 4.2
"""

import pytest

from handler import ConfigurationError, get_alert_config


def test_all_present_returns_alert_config(monkeypatch):
    monkeypatch.setenv("ALERT_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@example.com")
    monkeypatch.setenv("TABLE_NAME", "pantryvision-products")

    config = get_alert_config()

    assert config == {
        "sender_address": "sender@example.com",
        "recipient_address": "recipient@example.com",
        "table_name": "pantryvision-products",
    }


def test_missing_sender_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("ALERT_SENDER_EMAIL", raising=False)
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@example.com")
    monkeypatch.setenv("TABLE_NAME", "pantryvision-products")

    with pytest.raises(ConfigurationError) as exc_info:
        get_alert_config()

    assert "ALERT_SENDER_EMAIL" in str(exc_info.value)


def test_missing_recipient_raises_configuration_error(monkeypatch):
    monkeypatch.setenv("ALERT_SENDER_EMAIL", "sender@example.com")
    monkeypatch.delenv("ALERT_RECIPIENT_EMAIL", raising=False)
    monkeypatch.setenv("TABLE_NAME", "pantryvision-products")

    with pytest.raises(ConfigurationError) as exc_info:
        get_alert_config()

    assert "ALERT_RECIPIENT_EMAIL" in str(exc_info.value)


def test_missing_table_name_raises_configuration_error(monkeypatch):
    monkeypatch.setenv("ALERT_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@example.com")
    monkeypatch.delenv("TABLE_NAME", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        get_alert_config()

    assert "TABLE_NAME" in str(exc_info.value)


def test_all_missing_raises_configuration_error(monkeypatch):
    monkeypatch.delenv("ALERT_SENDER_EMAIL", raising=False)
    monkeypatch.delenv("ALERT_RECIPIENT_EMAIL", raising=False)
    monkeypatch.delenv("TABLE_NAME", raising=False)

    with pytest.raises(ConfigurationError):
        get_alert_config()


def test_blank_string_values_treated_as_missing(monkeypatch):
    monkeypatch.setenv("ALERT_SENDER_EMAIL", "   ")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@example.com")
    monkeypatch.setenv("TABLE_NAME", "pantryvision-products")

    with pytest.raises(ConfigurationError) as exc_info:
        get_alert_config()

    assert "ALERT_SENDER_EMAIL" in str(exc_info.value)


def test_blank_recipient_treated_as_missing(monkeypatch):
    monkeypatch.setenv("ALERT_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "")
    monkeypatch.setenv("TABLE_NAME", "pantryvision-products")

    with pytest.raises(ConfigurationError) as exc_info:
        get_alert_config()

    assert "ALERT_RECIPIENT_EMAIL" in str(exc_info.value)


def test_error_message_does_not_leak_values(monkeypatch):
    """Error message must name the missing variable, never leak any value."""
    monkeypatch.setenv("ALERT_SENDER_EMAIL", "secret-sender@example.com")
    monkeypatch.delenv("ALERT_RECIPIENT_EMAIL", raising=False)
    monkeypatch.setenv("TABLE_NAME", "pantryvision-products")

    with pytest.raises(ConfigurationError) as exc_info:
        get_alert_config()

    assert "secret-sender@example.com" not in str(exc_info.value)

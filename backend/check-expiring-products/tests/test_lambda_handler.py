"""Unit tests for lambda_handler orchestration.

Validates: Requirements 2.6-2.8, 5.1-5.3
"""

from datetime import date
from unittest.mock import MagicMock, patch

import handler
from handler import ConfigurationError, ScanFailedError, lambda_handler


BASE_CONFIG = {
    "sender_address": "sender@example.com",
    "recipient_address": "recipient@example.com",
    "table_name": "pantryvision-products",
}


def _make_table_mock():
    """Returns a fake Table object returned by dynamodb.Table(...)."""
    return MagicMock(name="table")


@patch("handler.log_run_summary")
@patch("handler.scan_products")
@patch("handler.get_alert_config")
def test_configuration_error_skips_scan(mock_get_config, mock_scan, mock_log_summary):
    mock_get_config.side_effect = ConfigurationError("ALERT_SENDER_EMAIL is missing or blank")

    result = lambda_handler({}, None)

    mock_scan.assert_not_called()
    mock_log_summary.assert_not_called()
    assert result["statusCode"] == 200
    assert "configuration error" in result["body"]


@patch("handler.send_alert_email")
@patch("handler.log_run_summary")
@patch("handler.scan_products")
@patch("handler.get_alert_config")
@patch.object(handler, "_dynamodb_resource")
def test_scan_failure_skips_send(
    mock_dynamodb_resource, mock_get_config, mock_scan, mock_log_summary, mock_send
):
    mock_get_config.return_value = dict(BASE_CONFIG)
    mock_dynamodb_resource.Table.return_value = _make_table_mock()
    mock_scan.side_effect = ScanFailedError("Products_Table scan failed after 3 attempts")

    result = lambda_handler({}, None)

    mock_send.assert_not_called()
    mock_log_summary.assert_not_called()
    assert result["statusCode"] == 200
    assert "scan failed" in result["body"]


@patch("handler.send_alert_email")
@patch("handler.classify_products")
@patch("handler.log_run_summary")
@patch("handler.scan_products")
@patch("handler.get_alert_config")
@patch.object(handler, "_dynamodb_resource")
def test_empty_batch_logs_not_needed_and_skips_send(
    mock_dynamodb_resource,
    mock_get_config,
    mock_scan,
    mock_log_summary,
    mock_classify,
    mock_send,
):
    mock_get_config.return_value = dict(BASE_CONFIG)
    mock_dynamodb_resource.Table.return_value = _make_table_mock()
    mock_scan.return_value = []
    mock_classify.return_value = []

    result = lambda_handler({}, None)

    mock_send.assert_not_called()
    mock_log_summary.assert_called_once_with(
        expiring_count=0, expired_count=0, status="not-needed"
    )
    assert result["status"] == "not-needed"
    assert result["expiring_count"] == 0
    assert result["expired_count"] == 0


@patch("handler.send_alert_email")
@patch("handler.build_email_body")
@patch("handler.classify_products")
@patch("handler.log_run_summary")
@patch("handler.scan_products")
@patch("handler.get_alert_config")
@patch.object(handler, "_dynamodb_resource")
@patch.object(handler, "_ses_client")
def test_non_empty_batch_success_sends_email_and_logs_sent(
    mock_ses_client,
    mock_dynamodb_resource,
    mock_get_config,
    mock_scan,
    mock_log_summary,
    mock_classify,
    mock_build_body,
    mock_send,
):
    mock_get_config.return_value = dict(BASE_CONFIG)
    mock_dynamodb_resource.Table.return_value = _make_table_mock()
    mock_scan.return_value = [{"productName": "Milk", "expirationDate": "2025-01-01"}]
    alert_batch = [
        {
            "product_name": "Milk",
            "expiration_date": "2025-01-01",
            "classification": "Expiring_Product",
        }
    ]
    mock_classify.return_value = alert_batch
    mock_build_body.return_value = ("subject", "body")
    mock_send.return_value = {"status": "sent", "failure_reason": None}

    result = lambda_handler({}, None)

    mock_build_body.assert_called_once()
    called_args = mock_build_body.call_args[0]
    assert called_args[0] == alert_batch
    assert isinstance(called_args[1], date)
    mock_send.assert_called_once_with(
        mock_ses_client,
        BASE_CONFIG["sender_address"],
        BASE_CONFIG["recipient_address"],
        "subject",
        "body",
    )
    mock_log_summary.assert_called_once_with(
        1, 0, status="sent", failure_reason=None
    )
    assert result["status"] == "sent"
    assert result["expiring_count"] == 1
    assert result["expired_count"] == 0


@patch("handler.send_alert_email")
@patch("handler.build_email_body")
@patch("handler.classify_products")
@patch("handler.log_run_summary")
@patch("handler.scan_products")
@patch("handler.get_alert_config")
@patch.object(handler, "_dynamodb_resource")
def test_non_empty_batch_ses_failure_logs_failed_with_reason(
    mock_dynamodb_resource,
    mock_get_config,
    mock_scan,
    mock_log_summary,
    mock_classify,
    mock_build_body,
    mock_send,
):
    mock_get_config.return_value = dict(BASE_CONFIG)
    mock_dynamodb_resource.Table.return_value = _make_table_mock()
    mock_scan.return_value = [{"productName": "Eggs", "expirationDate": "2024-01-01"}]
    alert_batch = [
        {
            "product_name": "Eggs",
            "expiration_date": "2024-01-01",
            "classification": "Expired_Product",
        }
    ]
    mock_classify.return_value = alert_batch
    mock_build_body.return_value = ("subject", "body")
    mock_send.return_value = {"status": "failed", "failure_reason": "Throttling"}

    result = lambda_handler({}, None)

    mock_send.assert_called_once()
    mock_log_summary.assert_called_once_with(
        0, 1, status="failed", failure_reason="Throttling"
    )
    assert result["status"] == "failed"
    assert result["expiring_count"] == 0
    assert result["expired_count"] == 1


@patch("handler.get_alert_config")
def test_unhandled_exception_is_caught_and_logged(mock_get_config, caplog):
    mock_get_config.side_effect = RuntimeError("boom")

    result = lambda_handler({}, None)

    assert result["statusCode"] == 500
    assert "unhandled error" in result["body"]

"""Unit tests for send_alert_email (task 4.6)."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from handler import send_alert_email


def _client_error(code: str, message: str = "boom") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": message}},
        operation_name="SendEmail",
    )


def test_send_alert_email_immediate_success():
    ses_client = MagicMock()
    ses_client.send_email.return_value = {"MessageId": "abc123"}

    result = send_alert_email(
        ses_client, "sender@example.com", "recipient@example.com", "Subject", "Body"
    )

    assert result["status"] == "sent"
    assert result["failure_reason"] is None
    ses_client.send_email.assert_called_once_with(
        Source="sender@example.com",
        Destination={"ToAddresses": ["recipient@example.com"]},
        Message={
            "Subject": {"Data": "Subject"},
            "Body": {"Html": {"Data": "Body"}},
        },
    )


@patch("handler.time.sleep")
def test_send_alert_email_transient_failure_then_success(mock_sleep):
    ses_client = MagicMock()
    ses_client.send_email.side_effect = [
        _client_error("Throttling"),
        {"MessageId": "abc123"},
    ]

    result = send_alert_email(
        ses_client, "sender@example.com", "recipient@example.com", "Subject", "Body"
    )

    assert result["status"] == "sent"
    assert result["failure_reason"] is None
    assert ses_client.send_email.call_count == 2
    mock_sleep.assert_called_once()


@patch("handler.time.sleep")
def test_send_alert_email_transient_failure_exhausts_all_attempts(mock_sleep):
    ses_client = MagicMock()
    ses_client.send_email.side_effect = [
        _client_error("Throttling"),
        _client_error("ServiceUnavailable"),
        _client_error("InternalFailure"),
    ]

    result = send_alert_email(
        ses_client, "sender@example.com", "recipient@example.com", "Subject", "Body"
    )

    assert result["status"] == "failed"
    assert "InternalFailure" in result["failure_reason"]
    assert ses_client.send_email.call_count == 3
    assert mock_sleep.call_count == 2


@patch("handler.time.sleep")
def test_send_alert_email_non_transient_failure_no_retry(mock_sleep):
    ses_client = MagicMock()
    ses_client.send_email.side_effect = _client_error("MessageRejected", "Email address is not verified")

    result = send_alert_email(
        ses_client, "sender@example.com", "recipient@example.com", "Subject", "Body"
    )

    assert result["status"] == "failed"
    assert "MessageRejected" in result["failure_reason"]
    ses_client.send_email.assert_called_once()
    mock_sleep.assert_not_called()

"""Unit tests for log_run_summary (Requirements 5.1, 5.2, 5.4)."""

import logging
import sys
from pathlib import Path

# Allow importing handler.py from the parent directory without a package install step.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handler import log_run_summary  # noqa: E402

# A representative email-like string that must never leak into log output.
FAKE_RECIPIENT_EMAIL = "owner@example.com"
FAKE_SENDER_EMAIL = "alerts@pantryvision.example.com"


def test_status_sent_logs_counts_and_status(caplog):
    with caplog.at_level(logging.INFO):
        log_run_summary(expiring_count=3, expired_count=2, status="sent")

    assert len(caplog.records) == 1
    message = caplog.text
    assert "3" in message
    assert "2" in message
    assert "sent" in message
    # No failure reason should be present when the run succeeded.
    assert "failure_reason" not in message


def test_status_not_needed_logs_zero_counts(caplog):
    with caplog.at_level(logging.INFO):
        log_run_summary(expiring_count=0, expired_count=0, status="not-needed")

    assert len(caplog.records) == 1
    message = caplog.text
    assert "not-needed" in message
    assert "failure_reason" not in message


def test_status_failed_includes_failure_reason(caplog):
    with caplog.at_level(logging.INFO):
        log_run_summary(
            expiring_count=1,
            expired_count=0,
            status="failed",
            failure_reason="Throttling",
        )

    assert len(caplog.records) == 1
    message = caplog.text
    assert "failed" in message
    assert "Throttling" in message


def test_status_failed_without_reason_does_not_crash(caplog):
    with caplog.at_level(logging.INFO):
        log_run_summary(expiring_count=0, expired_count=1, status="failed")

    assert len(caplog.records) == 1
    assert "failed" in caplog.text


def test_log_never_contains_email_addresses(caplog):
    """Proxy check per design Property 12: no '@' substring (email-like
    content) should ever appear in the run summary log, since only counts,
    status, and the SES failure reason (an error code/message) are logged."""
    with caplog.at_level(logging.INFO):
        log_run_summary(
            expiring_count=5,
            expired_count=1,
            status="failed",
            failure_reason="MessageRejected: Email address is not verified",
        )

    assert "@" not in caplog.text
    assert FAKE_RECIPIENT_EMAIL not in caplog.text
    assert FAKE_SENDER_EMAIL not in caplog.text

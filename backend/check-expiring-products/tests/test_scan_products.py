"""Unit tests for scan_products().

Validates: Requirements 1.1, 1.6
"""

from unittest.mock import MagicMock, call

import pytest
from botocore.exceptions import ClientError

from handler import ScanFailedError, scan_products


def _client_error(code: str = "ProvisionedThroughputExceededException") -> ClientError:
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "transient failure"}},
        operation_name="Scan",
    )


def test_scan_products_concatenates_all_pages(monkeypatch):
    monkeypatch.setattr("handler.time.sleep", MagicMock())

    table = MagicMock()
    table.scan.side_effect = [
        {"Items": [{"productId": "1"}, {"productId": "2"}], "LastEvaluatedKey": {"productId": "2"}},
        {"Items": [{"productId": "3"}], "LastEvaluatedKey": {"productId": "3"}},
        {"Items": [{"productId": "4"}]},
    ]

    result = scan_products(table)

    assert result == [
        {"productId": "1"},
        {"productId": "2"},
        {"productId": "3"},
        {"productId": "4"},
    ]
    assert table.scan.call_count == 3
    table.scan.assert_has_calls(
        [
            call(),
            call(ExclusiveStartKey={"productId": "2"}),
            call(ExclusiveStartKey={"productId": "3"}),
        ]
    )


def test_scan_products_raises_after_three_failed_attempts(monkeypatch):
    sleep_mock = MagicMock()
    monkeypatch.setattr("handler.time.sleep", sleep_mock)

    table = MagicMock()
    table.scan.side_effect = [_client_error(), _client_error(), _client_error()]

    with pytest.raises(ScanFailedError):
        scan_products(table)

    assert table.scan.call_count == 3
    # Only 2 delays between 3 attempts, never a delay after the final failure.
    assert sleep_mock.call_count == 2


def test_scan_products_succeeds_after_one_transient_failure(monkeypatch):
    sleep_mock = MagicMock()
    monkeypatch.setattr("handler.time.sleep", sleep_mock)

    table = MagicMock()
    table.scan.side_effect = [
        _client_error(),
        {"Items": [{"productId": "1"}]},
    ]

    result = scan_products(table)

    assert result == [{"productId": "1"}]
    assert table.scan.call_count == 2
    assert sleep_mock.call_count == 1

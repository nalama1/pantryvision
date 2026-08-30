"""Concrete edge-case unit tests for the delete-product Lambda.

Covers the example / edge-case scenarios called out in the design's Testing
Strategy (as opposed to the Hypothesis property tests):

- INVALID_JSON on a malformed / None body (Req 2.7)
- 404 NOT_FOUND when the conditional update fails (Req 2.6)
- MISSING_PARAMS boundary validation on productId (Req 2.5)
- Retry behavior on transient DynamoDB errors (Req 2.8, 2.9)

Two mocking styles are used deliberately:

- moto (a real in-memory DynamoDB) for the validation + not-found + boundary
  cases, so the ConditionExpression and the whole DynamoDB round-trip are
  exercised as they would be in production.
- A MagicMock table + monkeypatched time.sleep for the retry cases, mirroring
  backend/check-expiring-products/tests/test_scan_products.py, so transient
  ClientErrors can be injected precisely and no real backoff delay is incurred.
"""

import importlib
import json
import os
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

TABLE_NAME = "pantryvision-products"


def _client_error(code: str, operation: str = "UpdateItem") -> ClientError:
    """Build a botocore ClientError with the given DynamoDB error code."""
    return ClientError(
        error_response={"Error": {"Code": code, "Message": "x"}},
        operation_name=operation,
    )


def _make_event(body) -> dict:
    """Wrap a raw body value in an API Gateway proxy-style event."""
    return {"body": body}


# ---------------------------------------------------------------------------
# moto-backed fixtures: a real in-memory table + a freshly imported handler
# bound to that table.
# ---------------------------------------------------------------------------
@pytest.fixture
def dynamodb_handler(monkeypatch):
    """Yield a handler module whose module-level `table` points at a moto table.

    The handler creates `dynamodb`/`table` at import time, so we must set the
    TABLE_NAME env var and (re)import the module inside the moto context to bind
    it to the mocked backend.
    """
    with mock_aws():
        monkeypatch.setenv("TABLE_NAME", TABLE_NAME)
        client = boto3.resource("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "productId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "productId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        import handler as handler_module

        handler = importlib.reload(handler_module)
        yield handler


def _seed_product(handler, product_id: str) -> None:
    """Insert a minimal product record so a delete can succeed against it."""
    handler.table.put_item(
        Item={
            "productId": product_id,
            "productName": "Milk",
            "brand": "Acme",
            "presentation": "1 L",
            "expirationDate": "2026-01-15",
            "imageKey": "images/x.jpg",
            "createdAt": "2025-01-01T00:00:00Z",
            "quantity": 1,
            "unit": "unit",
        }
    )


# ---------------------------------------------------------------------------
# 1. INVALID_JSON (Req 2.7)
# ---------------------------------------------------------------------------
def test_malformed_json_body_returns_invalid_json(dynamodb_handler):
    """A syntactically invalid JSON body is rejected with 400 INVALID_JSON."""
    response = dynamodb_handler.lambda_handler(_make_event("{bad json"), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_JSON"


def test_none_body_returns_invalid_json(dynamodb_handler):
    """A None body reaches json.loads(None) -> TypeError -> 400 INVALID_JSON.

    Documents actual handler behavior: `event.get("body", "{}")` returns the
    explicit None (the key exists), so it is NOT replaced by the "{}" default.
    """
    response = dynamodb_handler.lambda_handler(_make_event(None), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_JSON"


def test_missing_body_key_defaults_to_empty_object_then_missing_params(dynamodb_handler):
    """A truly missing `body` key defaults to "{}" and fails validation.

    Documents actual handler behavior: with no `body` key, `event.get("body",
    "{}")` yields "{}", which parses successfully, so the request falls through
    to payload validation and fails with MISSING_PARAMS (no productId), NOT
    INVALID_JSON.
    """
    response = dynamodb_handler.lambda_handler({}, None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "MISSING_PARAMS"


# ---------------------------------------------------------------------------
# 2. 404 NOT_FOUND (Req 2.6)
# ---------------------------------------------------------------------------
def test_delete_nonexistent_product_returns_404(dynamodb_handler):
    """Deleting a productId absent from an empty table returns 404 NOT_FOUND.

    moto enforces ConditionExpression=attribute_exists(productId), so the
    conditional update raises ConditionalCheckFailedException, which the handler
    maps to ProductNotFoundError -> 404.
    """
    body = json.dumps({"productId": "does-not-exist"})
    response = dynamodb_handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 404
    assert json.loads(response["body"])["error"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# 3. MISSING_PARAMS boundary validation (Req 2.5)
# ---------------------------------------------------------------------------
def test_product_id_length_256_is_accepted_and_deletes(dynamodb_handler):
    """A 256-char productId is at the upper bound -> valid -> 200 on delete."""
    product_id = "a" * 256
    _seed_product(dynamodb_handler, product_id)

    body = json.dumps({"productId": product_id})
    response = dynamodb_handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["productId"] == product_id


def test_product_id_length_257_is_rejected_before_dynamodb(dynamodb_handler):
    """A 257-char productId exceeds the bound -> 400 MISSING_PARAMS.

    Rejected by validation before any DynamoDB call, so no record needs to
    exist for this assertion.
    """
    body = json.dumps({"productId": "a" * 257})
    response = dynamodb_handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "MISSING_PARAMS"


def test_missing_product_id_is_rejected(dynamodb_handler):
    """A payload without productId is rejected with 400 MISSING_PARAMS."""
    body = json.dumps({"foo": "bar"})
    response = dynamodb_handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "MISSING_PARAMS"


def test_non_string_product_id_is_rejected(dynamodb_handler):
    """A non-string productId (int) is rejected with 400 MISSING_PARAMS."""
    body = json.dumps({"productId": 12345})
    response = dynamodb_handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "MISSING_PARAMS"


def test_empty_string_product_id_is_rejected(dynamodb_handler):
    """An empty-string productId (length 0) is rejected with 400 MISSING_PARAMS."""
    body = json.dumps({"productId": ""})
    response = dynamodb_handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "MISSING_PARAMS"


# ---------------------------------------------------------------------------
# 4. Retry paths (Req 2.8, 2.9) -- MagicMock + monkeypatch, no moto.
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_handler(monkeypatch):
    """Import the handler and swap its module-level table + time.sleep for mocks.

    Using a MagicMock table lets us inject precise transient ClientError
    side_effects; monkeypatching handler.time.sleep prevents any real backoff
    delay, mirroring the retry-testing pattern in test_scan_products.py.
    """
    import handler as handler_module

    handler = importlib.reload(handler_module)

    mock_table = MagicMock()
    sleep_mock = MagicMock()
    monkeypatch.setattr(handler, "table", mock_table)
    monkeypatch.setattr(handler.time, "sleep", sleep_mock)

    return handler, mock_table, sleep_mock


def test_transient_error_twice_then_success_returns_200(mock_handler):
    """Two transient errors then success: delete succeeds after 3 update_item calls.

    Validates the retry policy (Req 2.8): transient DynamoDB errors are retried
    up to MAX_ATTEMPTS total, and a success on the final attempt yields 200.
    """
    handler, mock_table, sleep_mock = mock_handler
    mock_table.update_item.side_effect = [
        _client_error("ProvisionedThroughputExceededException"),
        _client_error("ThrottlingException"),
        None,  # third attempt succeeds
    ]

    body = json.dumps({"productId": "abc"})
    response = handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["productId"] == "abc"
    # Exactly 3 attempts; 2 backoff sleeps between them.
    assert mock_table.update_item.call_count == 3
    assert sleep_mock.call_count == 2


def test_transient_error_on_all_attempts_returns_500(mock_handler):
    """Transient error on all 3 attempts -> 500 INTERNAL_ERROR (Req 2.9).

    update_item is called exactly MAX_ATTEMPTS (3) times, and time.sleep is
    called exactly 2 times: between attempts only, never after the final failure.
    """
    handler, mock_table, sleep_mock = mock_handler
    mock_table.update_item.side_effect = [
        _client_error("ThrottlingException"),
        _client_error("ThrottlingException"),
        _client_error("ThrottlingException"),
    ]

    body = json.dumps({"productId": "abc"})
    response = handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 500
    assert json.loads(response["body"])["error"] == "INTERNAL_ERROR"
    assert mock_table.update_item.call_count == 3
    # Only 2 delays between 3 attempts, never a delay after the final failure.
    assert sleep_mock.call_count == 2


def test_conditional_check_failure_is_not_retried(mock_handler):
    """A ConditionalCheckFailedException is not retried: 404 after one call.

    Validates that the not-found path (Req 2.6) short-circuits the retry loop:
    update_item is called exactly once and time.sleep is never called.
    """
    handler, mock_table, sleep_mock = mock_handler
    mock_table.update_item.side_effect = _client_error("ConditionalCheckFailedException")

    body = json.dumps({"productId": "abc"})
    response = handler.lambda_handler(_make_event(body), None)

    assert response["statusCode"] == 404
    assert json.loads(response["body"])["error"] == "NOT_FOUND"
    assert mock_table.update_item.call_count == 1
    sleep_mock.assert_not_called()

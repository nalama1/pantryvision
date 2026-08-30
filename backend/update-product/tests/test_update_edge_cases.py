"""Concrete example (unit) tests for the update-product Lambda edge cases.

Covers the design's "Example / edge-case unit tests" for manage-products:
- INVALID_JSON on a malformed / None body (Req 1.9)
- 404 NOT_FOUND when the conditional update fails because the record is absent
  (Req 1.8) -- exercised against a real moto-backed DynamoDB table, which
  enforces the ConditionExpression the handler relies on.
- Boundary values for the length-limited and date fields (Req 1.11, plus 1.7 for
  the impossible-date case), verified against a seeded record so the accepted
  cases actually perform a 200 update.

These are example tests (fixed inputs), not property tests, so nothing here is
tagged with a design Property number.
"""

import importlib
import json
import os

import boto3
import pytest
from moto import mock_aws

TABLE_NAME = "pantryvision-products"

# A fixed productId for the seeded record so the "accepted" boundary cases update
# a known item and return 200. Using a constant keeps the tests deterministic.
SEEDED_PRODUCT_ID = "seed-product-0001"


@pytest.fixture(scope="function")
def handler_module():
    """Start moto, create the products table, then (re)import the handler.

    The handler binds `dynamodb`/`table` at import time, so the mock must be
    active and the table must exist BEFORE the module is imported/reloaded;
    otherwise the module-level `table` would point at a resource with no table.
    Mirrors the fixture pattern used by test_update_property_preservation.py.
    """
    with mock_aws():
        os.environ["TABLE_NAME"] = TABLE_NAME

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "productId", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "productId", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        dynamodb.meta.client.get_waiter("table_exists").wait(TableName=TABLE_NAME)

        import handler as handler_mod

        importlib.reload(handler_mod)

        yield handler_mod, dynamodb.Table(TABLE_NAME)


def _seed_record(table) -> dict:
    """Insert one fully-formed Product_Record and return it.

    Boundary "accepted" cases update this record, so it must carry the immutable
    and untouched fields (imageKey/createdAt/quantity/unit) as well.
    """
    record = {
        "productId": SEEDED_PRODUCT_ID,
        "productName": "Original Name",
        "brand": "Original Brand",
        "presentation": "1 L carton",
        "expirationDate": "2026-01-01",
        "imageKey": "images/seed.jpg",
        "createdAt": "2025-01-01T00:00:00Z",
        "quantity": 3,
        "unit": "unit",
    }
    table.put_item(Item=record)
    return record


def _valid_payload(**overrides) -> dict:
    """A baseline valid update payload for the seeded record, with overrides."""
    payload = {
        "productId": SEEDED_PRODUCT_ID,
        "productName": "Updated Name",
        "brand": "Updated Brand",
        "presentation": "500 ml bottle",
        "expirationDate": "2026-06-30",
    }
    payload.update(overrides)
    return payload


# --- INVALID_JSON (Req 1.9) -------------------------------------------------


def test_malformed_json_body_returns_400_invalid_json(handler_module):
    """A non-JSON string body -> 400 INVALID_JSON (json.loads raises ValueError)."""
    handler_mod, _table = handler_module

    response = handler_mod.lambda_handler({"body": "{not valid json"}, None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_JSON"


def test_none_body_returns_400_invalid_json(handler_module):
    """A present-but-None body -> 400 INVALID_JSON.

    `event.get("body", "{}")` returns None when the key exists with a None value
    (the default is only used for a MISSING key), so `json.loads(None)` raises
    TypeError, which the handler catches and maps to INVALID_JSON. This asserts
    the handler's actual behavior (it does not 500).
    """
    handler_mod, _table = handler_module

    response = handler_mod.lambda_handler({"body": None}, None)

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_JSON"


# --- 404 NOT_FOUND (Req 1.8) ------------------------------------------------


def test_update_nonexistent_product_returns_404_not_found(handler_module):
    """Valid payload but the table is empty -> 404 NOT_FOUND.

    moto enforces the `attribute_exists(productId)` ConditionExpression, so the
    update raises ConditionalCheckFailedException, which the handler maps through
    ProductNotFoundError to a 404. No record is seeded here.
    """
    handler_mod, _table = handler_module

    payload = {"productId": "does-not-exist", "productName": "Whatever"}
    response = handler_mod.lambda_handler({"body": json.dumps(payload)}, None)

    assert response["statusCode"] == 404
    assert json.loads(response["body"])["error"] == "NOT_FOUND"


# --- Boundary values (Req 1.11, 1.7) ----------------------------------------


def test_product_name_exactly_200_chars_is_accepted(handler_module):
    """productName of exactly 200 chars (after trim) -> 200 OK and is stored."""
    handler_mod, table = handler_module
    _seed_record(table)

    name_200 = "a" * 200
    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(productName=name_200))}, None
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["productName"] == name_200


def test_product_name_201_chars_returns_400_invalid_params(handler_module):
    """productName of 201 chars -> 400 INVALID_PARAMS (over the 200 limit)."""
    handler_mod, table = handler_module
    _seed_record(table)

    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(productName="a" * 201))}, None
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_PARAMS"


def test_brand_exactly_100_chars_is_accepted(handler_module):
    """brand of exactly 100 chars -> 200 OK and is stored."""
    handler_mod, table = handler_module
    _seed_record(table)

    brand_100 = "b" * 100
    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(brand=brand_100))}, None
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["brand"] == brand_100


def test_brand_101_chars_returns_400_invalid_params(handler_module):
    """brand of 101 chars -> 400 INVALID_PARAMS (over the 100 limit)."""
    handler_mod, table = handler_module
    _seed_record(table)

    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(brand="b" * 101))}, None
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_PARAMS"


def test_presentation_exactly_100_chars_is_accepted(handler_module):
    """presentation of exactly 100 chars -> 200 OK and is stored."""
    handler_mod, table = handler_module
    _seed_record(table)

    presentation_100 = "p" * 100
    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(presentation=presentation_100))}, None
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["presentation"] == presentation_100


def test_presentation_101_chars_returns_400_invalid_params(handler_module):
    """presentation of 101 chars -> 400 INVALID_PARAMS (over the 100 limit)."""
    handler_mod, table = handler_module
    _seed_record(table)

    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(presentation="p" * 101))}, None
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_PARAMS"


def test_empty_expiration_date_is_accepted(handler_module):
    """An empty expirationDate is allowed (product has no known date) -> 200 OK."""
    handler_mod, table = handler_module
    _seed_record(table)

    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(expirationDate=""))}, None
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["expirationDate"] == ""


def test_valid_expiration_date_is_accepted(handler_module):
    """A real YYYY-MM-DD expirationDate is accepted -> 200 OK and is stored."""
    handler_mod, table = handler_module
    _seed_record(table)

    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(expirationDate="2026-01-15"))}, None
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["expirationDate"] == "2026-01-15"


def test_impossible_expiration_date_returns_400_invalid_date(handler_module):
    """A well-formed but impossible date (2026-02-30) -> 400 INVALID_DATE.

    The handler requires the value to both match the YYYY-MM-DD shape AND parse
    as a real calendar date, so Feb 30 is rejected even though it is 10 chars.
    """
    handler_mod, table = handler_module
    _seed_record(table)

    response = handler_mod.lambda_handler(
        {"body": json.dumps(_valid_payload(expirationDate="2026-02-30"))}, None
    )

    assert response["statusCode"] == 400
    assert json.loads(response["body"])["error"] == "INVALID_DATE"

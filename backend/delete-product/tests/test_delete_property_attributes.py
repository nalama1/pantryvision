"""Property-based tests for the delete-product Lambda.

Covers design Correctness Property 3 ("Soft delete sets the deletion attributes
and preserves everything else") for the manage-products feature. DynamoDB is
backed by an in-memory moto table so 100+ Hypothesis examples stay cheap and
exercise our own logic, not AWS behavior.
"""

import importlib
import json
import os
from datetime import datetime
from decimal import Decimal

import boto3
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from moto import mock_aws

TABLE_NAME = "pantryvision-products"

# The exact timestamp format the handler produces for deletedAt.
_DELETED_AT_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture(scope="function")
def handler_module():
    """Start moto, create the products table, then (re)import the handler.

    The handler binds `dynamodb`/`table` at import time, so the mock must be
    active and the table must exist *before* the module is imported/reloaded.
    Otherwise the module-level `table` would point at a resource with no table.
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

        # Import fresh so the handler's module-level table binds to the mock.
        import handler as handler_mod

        importlib.reload(handler_mod)

        yield handler_mod, dynamodb.Table(TABLE_NAME)


# --- Strategies -------------------------------------------------------------

# A non-empty, unique productId per example (uuid) avoids cross-example residue.
_product_id = st.uuids().map(str)

_product_name = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")
_bounded_100 = st.text(max_size=100)

# expirationDate is either empty or a real YYYY-MM-DD calendar date.
_valid_dates = st.dates().map(lambda d: d.isoformat())
_expiration = st.one_of(st.just(""), _valid_dates)

_created_at = st.datetimes().map(lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ"))
_quantity = st.integers(min_value=1, max_value=100_000)
_unit = st.sampled_from(["unit", "pack", "loose", "box", "bottle", "can"])
_image_key = st.text(min_size=1, max_size=80).map(lambda s: f"images/{s}.jpg")


@st.composite
def _seed_record(draw):
    """A fully-formed existing Product_Record to place in the table."""
    return {
        "productId": draw(_product_id),
        "productName": draw(_product_name),
        "brand": draw(_bounded_100),
        "presentation": draw(_bounded_100),
        "expirationDate": draw(_expiration),
        "imageKey": draw(_image_key),
        "createdAt": draw(_created_at),
        "quantity": draw(_quantity),
        "unit": draw(_unit),
    }


# --- Property 3 -------------------------------------------------------------

# Feature: manage-products, Property 3: Soft delete sets the deletion attributes and preserves everything else
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(record=_seed_record())
def test_soft_delete_sets_attributes_and_preserves_everything_else(handler_module, record):
    """For any existing record, delete-product sets deleted=true and a valid UTC
    ISO8601 deletedAt, while every other attribute is unchanged.

    Validates: Requirements 2.1, 2.2
    """
    handler_mod, table = handler_module

    seed = dict(record)
    table.put_item(Item=seed)

    try:
        pid = seed["productId"]
        event = {"body": json.dumps({"productId": pid})}
        response = handler_mod.lambda_handler(event, None)

        assert response["statusCode"] == 200, response
        assert json.loads(response["body"]) == {"productId": pid}

        stored = table.get_item(Key={"productId": pid})["Item"]

        # Deletion attributes are set.
        assert stored["deleted"] is True

        # deletedAt parses as the exact UTC ISO8601 form the handler produces.
        deleted_at = stored["deletedAt"]
        assert isinstance(deleted_at, str)
        assert deleted_at.endswith("Z")
        # Raises ValueError if the format does not match exactly.
        datetime.strptime(deleted_at, _DELETED_AT_FORMAT)

        # Every other original attribute is unchanged vs. the seeded values.
        assert stored["productId"] == seed["productId"]
        assert stored["productName"] == seed["productName"]
        assert stored["brand"] == seed["brand"]
        assert stored["presentation"] == seed["presentation"]
        assert stored["expirationDate"] == seed["expirationDate"]
        assert stored["imageKey"] == seed["imageKey"]
        assert stored["createdAt"] == seed["createdAt"]
        # quantity round-trips through DynamoDB as a Decimal; compare numerically.
        assert Decimal(str(stored["quantity"])) == Decimal(seed["quantity"])
        assert stored["unit"] == seed["unit"]
    finally:
        table.delete_item(Key={"productId": seed["productId"]})

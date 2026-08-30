"""Property-based tests for the delete-product Lambda (idempotence).

Covers design Correctness Property 4 ("Soft delete is idempotent-safe") for the
manage-products feature. DynamoDB is backed by an in-memory moto table so 100+
Hypothesis examples stay cheap and exercise our own logic.

The design decision under test: re-deleting a still-present but already
soft-deleted record returns HTTP 200 (not 404), because
attribute_exists(productId) still holds after the first delete.
"""

import importlib
import json
import os
from datetime import datetime

import boto3
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from moto import mock_aws

TABLE_NAME = "pantryvision-products"
ISO8601 = "%Y-%m-%dT%H:%M:%SZ"


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

# A non-empty, unique productId per example so residue between examples never
# collides (each example manages its own item lifecycle).
_product_id = st.uuids().map(str)

_product_name = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")
_bounded_100 = st.text(max_size=100)
_valid_dates = st.dates().map(lambda d: d.isoformat())
_expiration = st.one_of(st.just(""), _valid_dates)
_created_at = st.datetimes().map(lambda d: d.strftime(ISO8601))
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


# --- Property 4 -------------------------------------------------------------

# Feature: manage-products, Property 4: Soft delete is idempotent-safe
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(record=_seed_record())
def test_soft_delete_is_idempotent_safe(handler_module, record):
    """For any existing record, deleting it twice in succession leaves it with
    deleted == true, and BOTH deletes return HTTP 200 (the second delete of an
    already-soft-deleted-but-present record is 200, not 404).

    Validates: Requirements 2.1, 2.6
    """
    handler_mod, table = handler_module

    seed = dict(record)
    pid = seed["productId"]
    table.put_item(Item=seed)

    try:
        event = {"body": json.dumps({"productId": pid})}

        # First delete.
        first = handler_mod.lambda_handler(event, None)
        assert first["statusCode"] == 200, first
        assert json.loads(first["body"]) == {"productId": pid}

        # Second delete of the still-present, already-soft-deleted record.
        second = handler_mod.lambda_handler(event, None)
        assert second["statusCode"] == 200, second
        assert json.loads(second["body"]) == {"productId": pid}

        # The record is still present and still marked deleted with a valid
        # UTC ISO8601 deletedAt after the second delete.
        item = table.get_item(Key={"productId": pid}).get("Item")
        assert item is not None
        assert item["deleted"] is True
        assert "deletedAt" in item
        # Parses as the exact UTC ISO8601 format produced by the handler.
        datetime.strptime(item["deletedAt"], ISO8601)
    finally:
        table.delete_item(Key={"productId": pid})

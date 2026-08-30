"""Property-based tests for the update-product Lambda.

Covers design Correctness Property 1 ("Update preserves immutable and untouched
fields") for the manage-products feature. DynamoDB is backed by an in-memory
moto table so 100+ Hypothesis examples stay cheap and exercise our own logic.
"""

import importlib
import json
import os
from decimal import Decimal

import boto3
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from moto import mock_aws

TABLE_NAME = "pantryvision-products"


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

# A non-empty, unique-friendly productId (uuid-ish). Uniqueness per example is
# guaranteed by combining a random suffix with Hypothesis-provided text.
_product_id = st.uuids().map(str)

# Editable text fields: bounded and non-empty-after-strip for productName.
_product_name = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")
_bounded_100 = st.text(max_size=100)

# expirationDate is either empty or a real YYYY-MM-DD calendar date.
_valid_dates = st.dates().map(lambda d: d.isoformat())
_expiration = st.one_of(st.just(""), _valid_dates)

# Immutable / untouched fields seeded on the existing record.
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


@st.composite
def _edit_payload(draw):
    """A VALID edit payload for the four editable fields."""
    return {
        "productName": draw(_product_name),
        "brand": draw(_bounded_100),
        "presentation": draw(_bounded_100),
        "expirationDate": draw(_expiration),
    }


# --- Property 1 -------------------------------------------------------------

# Feature: manage-products, Property 1: Update preserves immutable and untouched fields
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(record=_seed_record(), edit=_edit_payload())
def test_update_preserves_immutable_and_untouched_fields(handler_module, record, edit):
    """For any existing record + valid edit, productId/imageKey/createdAt/
    quantity/unit are unchanged and the four editable fields equal the trimmed
    submitted values.

    Validates: Requirements 1.1, 1.3, 1.4
    """
    handler_mod, table = handler_module

    # Seed the existing record. Item lifecycle is managed per example with a
    # unique productId so residue between examples never collides.
    seed = dict(record)
    table.put_item(Item=seed)

    try:
        event = {"body": json.dumps({"productId": seed["productId"], **edit})}
        response = handler_mod.lambda_handler(event, None)

        assert response["statusCode"] == 200, response
        updated = json.loads(response["body"])

        # Immutable / untouched fields survive byte-for-byte.
        assert updated["productId"] == seed["productId"]
        assert updated["imageKey"] == seed["imageKey"]
        assert updated["createdAt"] == seed["createdAt"]
        assert updated["unit"] == seed["unit"]
        # quantity round-trips through DynamoDB as a Decimal; compare numerically.
        assert Decimal(str(updated["quantity"])) == Decimal(seed["quantity"])

        # Editable fields equal the TRIMMED submitted values.
        assert updated["productName"] == edit["productName"].strip()
        assert updated["brand"] == edit["brand"].strip()
        assert updated["presentation"] == edit["presentation"].strip()
        assert updated["expirationDate"] == edit["expirationDate"].strip()
    finally:
        table.delete_item(Key={"productId": seed["productId"]})

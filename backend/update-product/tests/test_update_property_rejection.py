"""Property test for update-product Property 2 (rejection + no mutation).

Design: manage-products / Correctness Property 2.
"""

import importlib
import json
import os

import boto3
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from moto import mock_aws

TABLE_NAME = "pantryvision-products"

# Fixed identity for the single seeded record used to prove "never mutates".
SEEDED_PRODUCT_ID = "seed-0000-1111-2222-333344445555"

# Known baseline field values for the seeded record. The snapshot taken after
# seeding is compared against the post-invocation read to prove no write happened
# for payloads that carry this (valid) productId.
SEEDED_RECORD = {
    "productId": SEEDED_PRODUCT_ID,
    "productName": "Whole Milk",
    "brand": "Acme",
    "presentation": "1 L carton",
    "expirationDate": "2026-01-15",
    "imageKey": "images/seed.jpg",
    "createdAt": "2025-01-01T00:00:00Z",
    "quantity": 3,
    "unit": "pack",
}


@pytest.fixture()
def dynamo_setup():
    """Start moto, create the table, seed one known record, load the handler.

    The handler binds `table = dynamodb.Table(TABLE_NAME)` at import time, so we
    (re)load the module only after the mock is active and the table exists. That
    guarantees the module-level resource talks to the mocked table.
    """
    os.environ["TABLE_NAME"] = TABLE_NAME
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        client.create_table(
            TableName=TABLE_NAME,
            AttributeDefinitions=[{"AttributeName": "productId", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "productId", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )

        table = boto3.resource("dynamodb", region_name="us-east-1").Table(TABLE_NAME)
        table.put_item(Item=dict(SEEDED_RECORD))

        # Import (or reload) the handler now that the mock + table are live.
        import handler as handler_module

        handler_module = importlib.reload(handler_module)

        snapshot = table.get_item(Key={"productId": SEEDED_PRODUCT_ID})["Item"]

        yield handler_module, table, snapshot


# ---------------------------------------------------------------------------
# Invalid-payload generation.
#
# Each strategy returns (payload, expected_code, targets_seeded_record).
# We start from a base-valid payload pointing at the seeded record, then apply
# exactly ONE mutation that isolates a single violation class, so the expected
# error code is deterministic. Validation order in the handler is:
#   productId -> productName -> length bounds -> expirationDate
# so mutations keep every earlier-checked field valid.
# ---------------------------------------------------------------------------


def _base_valid_payload() -> dict:
    return {
        "productId": SEEDED_PRODUCT_ID,
        "productName": "Valid Name",
        "brand": "Acme",
        "presentation": "1 L carton",
        "expirationDate": "2026-01-15",
    }


# Sentinel used to model an absent key (as opposed to a present-but-invalid value).
_MISSING = object()

# --- MISSING_PARAMS: invalid productId (record cannot be located) ---
_bad_product_id_choices = st.sampled_from([_MISSING, None, "", "   ", 123, 4.5, [], {}])


@st.composite
def invalid_product_id_strategy(draw):
    payload = _base_valid_payload()
    bad = draw(_bad_product_id_choices)
    if bad is _MISSING:
        del payload["productId"]
    else:
        payload["productId"] = bad
    return payload, "MISSING_PARAMS", False


# --- MISSING_PARAMS: invalid productName (productId stays valid -> targets seed) ---
_bad_product_name_choices = st.sampled_from([_MISSING, None, "", "   ", "\t\n  ", 42, []])


@st.composite
def invalid_product_name_strategy(draw):
    payload = _base_valid_payload()
    bad = draw(_bad_product_name_choices)
    if bad is _MISSING:
        del payload["productName"]
    else:
        payload["productName"] = bad
    return payload, "MISSING_PARAMS", True


# --- INVALID_PARAMS: productName too long (> 200 after trim) ---
@st.composite
def product_name_too_long_strategy(draw):
    payload = _base_valid_payload()
    length = draw(st.integers(min_value=201, max_value=400))
    # Interior text so .strip() cannot shorten it below the limit; optional
    # surrounding whitespace confirms the check is against the trimmed length.
    core = draw(st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=length, max_size=length))
    pad = draw(st.sampled_from(["", " ", "  "]))
    payload["productName"] = f"{pad}{core}{pad}"
    return payload, "INVALID_PARAMS", True


# --- INVALID_PARAMS: brand too long (> 100) ---
@st.composite
def brand_too_long_strategy(draw):
    payload = _base_valid_payload()
    length = draw(st.integers(min_value=101, max_value=250))
    payload["brand"] = draw(
        st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=length, max_size=length)
    )
    return payload, "INVALID_PARAMS", True


# --- INVALID_PARAMS: presentation too long (> 100) ---
@st.composite
def presentation_too_long_strategy(draw):
    payload = _base_valid_payload()
    length = draw(st.integers(min_value=101, max_value=250))
    payload["presentation"] = draw(
        st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=length, max_size=length)
    )
    return payload, "INVALID_PARAMS", True


# --- INVALID_DATE: non-empty expirationDate that is not a real YYYY-MM-DD ---
_bad_dates = st.sampled_from(
    [
        "2026-13-01",   # month out of range
        "2026-00-10",   # month zero
        "2026-02-30",   # impossible calendar date
        "2026-04-31",   # April has 30 days
        "2026-2-3",     # not zero-padded / wrong shape
        "26-01-01",     # wrong year width
        "2026/01/15",   # wrong separators
        "15-01-2026",   # wrong order
        "not-a-date",   # garbage
        "20260115",     # no separators
        "2026-01-32",   # day out of range
    ]
)


@st.composite
def invalid_date_strategy(draw):
    payload = _base_valid_payload()
    # Keep productName valid so the date check is actually reached.
    payload["expirationDate"] = draw(_bad_dates)
    return payload, "INVALID_DATE", True


invalid_payloads = st.one_of(
    invalid_product_id_strategy(),
    invalid_product_name_strategy(),
    product_name_too_long_strategy(),
    brand_too_long_strategy(),
    presentation_too_long_strategy(),
    invalid_date_strategy(),
)


# Feature: manage-products, Property 2: Invalid update payloads are rejected with the correct code and never mutate the record
# The fixture only seeds + reads the record; rejected payloads never write, so
# reusing the same seeded table across generated inputs is safe here.
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(case=invalid_payloads)
def test_invalid_update_payloads_rejected_and_no_mutation(dynamo_setup, case):
    handler_module, table, snapshot = dynamo_setup
    payload, expected_code, targets_seed = case

    response = handler_module.lambda_handler({"body": json.dumps(payload)}, None)

    assert response["statusCode"] == 400, (
        f"expected 400 for payload={payload!r}, got {response['statusCode']} / {response['body']}"
    )
    body = json.loads(response["body"])
    assert body["error"] == expected_code, (
        f"expected error {expected_code} for payload={payload!r}, got {body['error']}"
    )

    # For payloads carrying the valid seeded productId, prove the record was
    # never mutated by re-reading and comparing to the pre-invocation snapshot.
    if targets_seed:
        current = table.get_item(Key={"productId": SEEDED_PRODUCT_ID})["Item"]
        assert current == snapshot, (
            f"record was mutated by a rejected payload={payload!r}: {current!r} != {snapshot!r}"
        )

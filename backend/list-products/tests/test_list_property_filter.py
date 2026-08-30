"""Property-based tests for the list-products soft-delete filter.

Covers design Correctness Property 5 ("list-products excludes deleted and
includes legacy/undeleted records") for the manage-products feature. DynamoDB
(and S3, for presign) are backed by in-memory moto resources so 100+ Hypothesis
examples stay cheap and exercise our own filter logic, not AWS behavior.
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
BUCKET_NAME = "pantryvision-product-images"

# deleted_state markers the strategy draws for each generated record.
_ABSENT = "absent"   # legacy record: no `deleted` attribute at all
_FALSE = "false"     # deleted == False
_TRUE = "true"       # deleted == True (must be excluded from the listing)


@pytest.fixture(scope="function")
def handler_module():
    """Start moto, create the products table (and image bucket), then (re)import
    the handler.

    The handler binds `dynamodb`/`s3_client`/`table` at import time, so the mock
    must be active and the resources must exist *before* the module is
    imported/reloaded. Otherwise the module-level `table` would point at a
    resource with no table.
    """
    with mock_aws():
        os.environ["TABLE_NAME"] = TABLE_NAME
        os.environ["BUCKET_NAME"] = BUCKET_NAME

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

        # Create the image bucket so any presign path stays fully offline-safe.
        # (generate_presigned_url is a local signing operation, but creating the
        # bucket removes any doubt; the test keeps imageKey="" anyway.)
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET_NAME)

        # Import fresh so the handler's module-level clients bind to the mock.
        import handler as handler_mod

        importlib.reload(handler_mod)

        yield handler_mod, dynamodb.Table(TABLE_NAME)


# --- Strategies -------------------------------------------------------------

_deleted_state = st.sampled_from([_ABSENT, _FALSE, _TRUE])
_product_name = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")
_expiration = st.one_of(st.just(""), st.dates().map(lambda d: d.isoformat()))
_quantity = st.integers(min_value=1, max_value=100_000)
_unit = st.sampled_from(["unit", "pack", "loose", "box", "bottle", "can"])


@st.composite
def _record(draw):
    """A minimal valid Product_Record plus its intended deleted_state.

    imageKey is kept empty so the handler sets imageUrl=None without touching
    S3 presign, keeping the test focused on the soft-delete filter.
    """
    return {
        "productId": draw(st.uuids().map(str)),
        "productName": draw(_product_name),
        "imageKey": "",
        "expirationDate": draw(_expiration),
        "quantity": draw(_quantity),
        "unit": draw(_unit),
        "_deleted_state": draw(_deleted_state),
    }


# unique_by productId so no two records in the same example collide.
_records = st.lists(_record(), min_size=0, max_size=15,
                    unique_by=lambda r: r["productId"])


# --- Property 5 -------------------------------------------------------------

# Feature: manage-products, Property 5: list-products excludes deleted and includes legacy/undeleted records
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(records=_records)
def test_list_excludes_deleted_includes_legacy_and_undeleted(handler_module, records):
    """For any mix of legacy (no `deleted`), deleted==False, and deleted==True
    records, list-products returns exactly the non-deleted set.

    Validates: Requirements 3.1, 3.2, 3.3
    """
    handler_mod, table = handler_module

    expected_ids = set()
    written_ids = []
    try:
        for rec in records:
            state = rec["_deleted_state"]
            item = {
                "productId": rec["productId"],
                "productName": rec["productName"],
                "imageKey": rec["imageKey"],
                "expirationDate": rec["expirationDate"],
                "quantity": rec["quantity"],
                "unit": rec["unit"],
            }
            # absent -> omit `deleted` entirely (legacy record).
            if state == _FALSE:
                item["deleted"] = False
            elif state == _TRUE:
                item["deleted"] = True

            table.put_item(Item=item)
            written_ids.append(rec["productId"])

            # A legacy (absent) or deleted==False record must be returned.
            if state in (_ABSENT, _FALSE):
                expected_ids.add(rec["productId"])

        response = handler_mod.lambda_handler({}, None)

        assert response["statusCode"] == 200, response
        returned = json.loads(response["body"])
        returned_ids = {item["productId"] for item in returned}

        # Exactly the non-deleted (legacy + deleted==False) set is returned.
        assert returned_ids == expected_ids
    finally:
        for pid in written_ids:
            table.delete_item(Key={"productId": pid})

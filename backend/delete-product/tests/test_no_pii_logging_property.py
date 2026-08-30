"""Property-based test for the no-PII logging guarantee.

Covers design Correctness Property 6 ("Logs never contain PII or credentials")
for the manage-products feature. This single test exercises BOTH the
update-product and delete-product handlers, because both must never log the
request body, user-entered field values, or any credential/secret material —
only non-identifying diagnostics such as productId and error codes.

Why load both handlers by path: update-product/handler.py and
delete-product/handler.py both live at the top-level module name `handler`, so a
plain `import handler` can only bind one of them. To exercise both without a name
collision we load each file under a distinct module name via importlib, AFTER the
moto mock + table exist, so each module's module-level `table` binds to the mock.
"""

import importlib.util
import json
import os
import uuid

import boto3
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from moto import mock_aws

TABLE_NAME = "pantryvision-products"

# Resolve the two handler files by absolute path (independent of sys.path order).
_here = os.path.dirname(os.path.abspath(__file__))          # backend/delete-product/tests
_delete_pkg = os.path.dirname(_here)                         # backend/delete-product
_backend = os.path.dirname(_delete_pkg)                      # backend
_update_handler_path = os.path.join(_backend, "update-product", "handler.py")
_delete_handler_path = os.path.join(_backend, "delete-product", "handler.py")

# Substrings that must never appear in logs. A tiny, high-signal blocklist of
# credential/secret markers; the sentinel below covers user-entered PII.
_SECRET_BLOCKLIST = (
    "aws_secret",
    "AKIA",
    "SessionToken",
    "password",
    "Authorization: ",
)


def _load(mod_name: str, path: str):
    """Load a module from an explicit file path under a caller-chosen name.

    Using module_from_spec + exec_module lets both handlers coexist under distinct
    names even though both files are named `handler.py`.
    """
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="function")
def handlers():
    """Start moto, create the products table, then load BOTH handlers by path.

    Each handler binds `dynamodb`/`table` at import time, so the mock must be
    active and the table must exist *before* the modules are loaded. `backend/`
    is already on sys.path (via conftest) so each handler's
    `from common.responses import ...` resolves.
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

        update_handler = _load("update_handler", _update_handler_path)
        delete_handler = _load("delete_handler", _delete_handler_path)

        yield update_handler, delete_handler, dynamodb.Table(TABLE_NAME)


# --- Strategies -------------------------------------------------------------

# Distinctive, collision-proof sentinel wrapped around a uuid: if this token
# appears anywhere in the logs, a user-entered field value leaked.
def _sentinel() -> str:
    return f"PIISENTINEL_{uuid.uuid4().hex}"


# A "kind" of request to generate, spanning both handlers and valid/invalid cases.
_request_kind = st.sampled_from(
    [
        "update_valid",
        "update_bad_date",
        "update_too_long",
        "update_missing_name",
        "delete_valid",
        "delete_missing",
        "delete_too_long",
    ]
)

# Free-text fragment woven into the user-entered fields alongside the sentinel.
# It widens the input space (so all 100 examples run rather than Hypothesis
# short-circuiting on the small discrete `kind` set) and it varies the exact
# user content that must never leak into logs. Bounded so valid update names
# stay within the 200-char limit.
_extra_text = st.text(max_size=40)


# --- Property 6 -------------------------------------------------------------

# Feature: manage-products, Property 6: Logs never contain PII or credentials
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(kind=_request_kind, marker=st.builds(_sentinel), extra=_extra_text)
def test_logs_never_contain_pii_or_credentials(handlers, caplog, kind, marker, extra):
    """For any request (valid or invalid) to update-product or delete-product,
    the emitted logs contain no user-entered field values, no verbatim request
    body, and no credential/secret material.

    Validates: Requirements 1.10, 2.9, 8.5
    """
    update_handler, delete_handler, table = handlers

    # Seed a record whose editable fields all carry the sentinel, so a "valid"
    # update reflects distinctive user content that must not be logged.
    product_id = str(uuid.uuid4())
    table.put_item(
        Item={
            "productId": product_id,
            "productName": f"Milk {marker} {extra}",
            "brand": f"Brand {marker}",
            "presentation": f"1 L {marker}",
            "expirationDate": "2026-01-15",
            "imageKey": f"images/{marker}.jpg",
            "createdAt": "2025-01-01T00:00:00Z",
            "quantity": 3,
            "unit": "unit",
        }
    )

    # Build the request body for this example. The sentinel lives in user-entered
    # fields wherever the payload has them.
    if kind == "update_valid":
        handler = update_handler
        body = {
            "productId": product_id,
            "productName": f"Whole Milk {marker} {extra}"[:200],
            "brand": f"Acme {marker}",
            "presentation": f"2 L {marker}",
            "expirationDate": "2026-02-01",
        }
    elif kind == "update_bad_date":
        handler = update_handler
        body = {
            "productId": product_id,
            "productName": f"Whole Milk {marker}",
            "brand": f"Acme {marker}",
            "presentation": f"2 L {marker}",
            "expirationDate": "2026-13-45",  # invalid -> INVALID_DATE
        }
    elif kind == "update_too_long":
        handler = update_handler
        body = {
            "productId": product_id,
            # > 200 chars, carrying the sentinel -> INVALID_PARAMS
            "productName": f"{marker} " + ("x" * 250),
            "brand": f"Acme {marker}",
            "presentation": f"2 L {marker}",
            "expirationDate": "",
        }
    elif kind == "update_missing_name":
        handler = update_handler
        body = {
            "productId": product_id,
            "productName": "   ",  # empty after trim -> MISSING_PARAMS
            "brand": f"Acme {marker}",
            "presentation": f"2 L {marker}",
            "expirationDate": "",
        }
    elif kind == "delete_valid":
        handler = delete_handler
        body = {"productId": product_id}
    elif kind == "delete_missing":
        handler = delete_handler
        # No free-text user fields on delete; a stray sentinel-bearing extra key
        # confirms unknown/body content is not echoed to logs. productId missing
        # -> MISSING_PARAMS.
        body = {"note": f"do not log {marker}"}
    else:  # delete_too_long
        handler = delete_handler
        body = {"productId": "x" * 300}  # > 256 -> MISSING_PARAMS

    body_str = json.dumps(body)
    event = {"body": body_str}

    # Capture at INFO on the root logger and the shared responses logger. INFO is
    # the level the handlers configure (logger.setLevel(logging.INFO)) and the level
    # Lambda emits in production, so this is exactly what would reach CloudWatch.
    # We deliberately do NOT capture DEBUG: the boto3/botocore SDK emits verbose
    # wire-level DEBUG logs (the raw DynamoDB request, which necessarily carries the
    # field values) that our handlers neither produce nor control and that never
    # surface at the production INFO level. Property 6 targets what OUR code writes.
    caplog.set_level("INFO")
    caplog.set_level("INFO", logger="common.responses")

    caplog.clear()
    handler.lambda_handler(event, None)

    # Assert only against logs emitted by our own code: the two handlers (logger name
    # "root", since they use logging.getLogger()) and the shared "common.responses"
    # module. Exclude third-party SDK loggers (boto3/botocore/moto/urllib3), whose
    # internal diagnostics are out of scope for the handlers' no-PII guarantee.
    _own_prefixes = ("root", "common.responses")
    all_logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name in _own_prefixes
    )

    # 1) No user-entered field value / PII leaked.
    assert marker not in all_logs, (
        f"PII sentinel leaked into logs for kind={kind}: {all_logs!r}"
    )

    # 2) No credential/secret material.
    for secret in _SECRET_BLOCKLIST:
        assert secret not in all_logs, (
            f"secret pattern {secret!r} appeared in logs for kind={kind}: {all_logs!r}"
        )

    # 3) The full JSON request body is not logged verbatim.
    assert body_str not in all_logs, (
        f"verbatim request body leaked into logs for kind={kind}: {all_logs!r}"
    )

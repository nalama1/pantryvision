import json
import os
import re
import logging
from datetime import datetime

import boto3
from botocore.exceptions import ClientError

# Shared CORS headers + error response builder live in backend/common so every
# Lambda emits an identical response shape and error logging stays in one place.
from common.responses import CORS_HEADERS, build_error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB resource initialized at module level for connection reuse across invocations.
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "pantryvision-products")
table = dynamodb.Table(TABLE_NAME)

# Precompiled so we validate the date shape on every request without recompiling.
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Field length limits mirror the DynamoDB data model / requirements (Req 1.11).
MAX_PRODUCT_NAME = 200
MAX_BRAND = 100
MAX_PRESENTATION = 100


class ProductNotFoundError(Exception):
    """
    Raised when the conditional update finds no matching productId.

    Using a dedicated exception (rather than inspecting the ClientError code in the
    handler) keeps the not-found intent explicit and lets lambda_handler map it to a
    404 without re-parsing DynamoDB error internals.
    """


def parse_and_validate_payload(body: dict) -> tuple[str | None, dict | None, dict | None]:
    """
    Validate an update payload.

    Returns (product_id, clean_fields, None) on success or (None, None, error_response)
    on failure. product_id is returned separately from the editable fields because it is
    the immutable key used to locate the record, not something we SET.
    """
    # productId: required, must be a non-empty string.
    product_id = body.get("productId")
    if not isinstance(product_id, str) or not product_id.strip():
        return None, None, build_error_response(
            400, "MISSING_PARAMS", "productId is required and must be a non-empty string"
        )

    # productName: required and non-empty after trimming; then bounded in length.
    product_name = body.get("productName")
    if not isinstance(product_name, str) or not product_name.strip():
        return None, None, build_error_response(
            400, "MISSING_PARAMS", "productName is required and must be a non-empty string"
        )
    product_name = product_name.strip()
    if len(product_name) > MAX_PRODUCT_NAME:
        return None, None, build_error_response(
            400, "INVALID_PARAMS", f"productName must be at most {MAX_PRODUCT_NAME} characters"
        )

    # brand: optional. Treat missing/None as empty string so the record always
    # stores a consistent type, then enforce the length bound.
    brand = _coerce_optional_str(body.get("brand"))
    if len(brand) > MAX_BRAND:
        return None, None, build_error_response(
            400, "INVALID_PARAMS", f"brand must be at most {MAX_BRAND} characters"
        )

    # presentation: optional, same coercion + bound as brand.
    presentation = _coerce_optional_str(body.get("presentation"))
    if len(presentation) > MAX_PRESENTATION:
        return None, None, build_error_response(
            400, "INVALID_PARAMS", f"presentation must be at most {MAX_PRESENTATION} characters"
        )

    # expirationDate: optional. Empty string is allowed (product has no known date);
    # a non-empty value must be both well-formed AND a real calendar date so that
    # impossible dates like 2026-02-30 are rejected.
    expiration_date = _coerce_optional_str(body.get("expirationDate"))
    if expiration_date:
        if not DATE_PATTERN.match(expiration_date) or not _is_real_date(expiration_date):
            return None, None, build_error_response(
                400, "INVALID_DATE", "expirationDate must be a valid date in YYYY-MM-DD format"
            )

    clean_fields = {
        "productName": product_name,
        "brand": brand,
        "presentation": presentation,
        "expirationDate": expiration_date,
    }
    return product_id.strip(), clean_fields, None


def _coerce_optional_str(value) -> str:
    """Treat missing/None as an empty string and trim; keeps stored types consistent."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def _is_real_date(value: str) -> bool:
    """True when value parses as an actual calendar date (rejects e.g. 2026-02-30)."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def update_product(product_id: str, fields: dict) -> dict:
    """
    Update ONLY the four editable fields of an existing record.

    SETting just these fields guarantees imageKey, createdAt, quantity, unit (and any
    deleted/deletedAt) are left untouched. The ConditionExpression makes the update fail
    when no record has the productId, which we surface as ProductNotFoundError (404)
    without needing GetItem/DeleteItem permissions.
    """
    try:
        response = table.update_item(
            Key={"productId": product_id},
            UpdateExpression="SET #pn = :pn, #br = :br, #pr = :pr, #ed = :ed",
            # All names are aliased to sidestep any DynamoDB reserved-word collisions.
            ExpressionAttributeNames={
                "#pn": "productName",
                "#br": "brand",
                "#pr": "presentation",
                "#ed": "expirationDate",
            },
            ExpressionAttributeValues={
                ":pn": fields["productName"],
                ":br": fields["brand"],
                ":pr": fields["presentation"],
                ":ed": fields["expirationDate"],
            },
            ConditionExpression="attribute_exists(productId)",
            ReturnValues="ALL_NEW",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise ProductNotFoundError(product_id) from e
        # Any other DynamoDB error propagates to the handler as an INTERNAL_ERROR.
        raise

    return response["Attributes"]


def build_success_response(record: dict) -> dict:
    """
    HTTP 200 with the full updated record.

    default=str handles DynamoDB Decimals (e.g. quantity), matching how list-products
    serializes its response so the frontend sees a consistent shape.
    """
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(record, default=str),
    }


def lambda_handler(event, context) -> dict:
    """
    POST /update-product
    Body: { productId, productName, brand?, presentation?, expirationDate? }

    Validates the payload, updates the editable fields of the matching record, and
    returns the complete updated Product_Record.
    """
    try:
        try:
            body = json.loads(event.get("body", "{}"))
        except (json.JSONDecodeError, TypeError):
            return build_error_response(400, "INVALID_JSON", "Request body must be valid JSON")

        product_id, fields, error_response = parse_and_validate_payload(body)
        if error_response:
            return error_response

        try:
            record = update_product(product_id, fields)
        except ProductNotFoundError:
            return build_error_response(404, "NOT_FOUND", "Product not found")

        # Log only non-identifying diagnostics: the productId and outcome, never the
        # user-entered field values (no-PII logging property).
        logger.info("Product updated: productId=%s", product_id)

        return build_success_response(record)

    except ClientError as e:
        logger.error("DynamoDB error: %s", str(e))
        return build_error_response(500, "INTERNAL_ERROR", "Failed to update product")
    except Exception:
        logger.exception("Unexpected error in update-product handler")
        return build_error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")

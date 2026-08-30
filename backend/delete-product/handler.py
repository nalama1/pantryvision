import json
import os
import time
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# Shared CORS headers + error response builder live in backend/common so every
# Lambda emits an identical response shape and error logging stays in one place.
from common.responses import CORS_HEADERS, build_error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB resource initialized at module level for connection reuse across invocations.
# No S3 client is created on purpose: soft delete preserves the image, so this Lambda
# must never touch S3 (and its execution role has no s3:* permission).
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "pantryvision-products")
table = dynamodb.Table(TABLE_NAME)

# productId length bounds mirror the delete API contract (Req 2.5).
MAX_PRODUCT_ID = 256

# Retry policy for the soft-delete UpdateItem: up to 3 total attempts on transient
# DynamoDB errors only (Req 2.8). ConditionalCheckFailedException (404) and validation
# errors are never retried.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.1
TRANSIENT_ERROR_CODES = (
    "ProvisionedThroughputExceededException",
    "ThrottlingException",
    "ThrottledException",
    "InternalServerError",
    "RequestLimitExceeded",
)


class ProductNotFoundError(Exception):
    """
    Raised when the conditional update finds no matching productId.

    Using a dedicated exception (rather than inspecting the ClientError code in the
    handler) keeps the not-found intent explicit and lets lambda_handler map it to a
    404 without re-parsing DynamoDB error internals.
    """


def parse_and_validate_payload(body: dict) -> tuple[str | None, dict | None]:
    """
    Validate a delete payload.

    Returns (product_id, None) on success or (None, error_response) on failure.
    productId must be a string of length 1..256 so we reject empty and oversized keys
    before ever calling DynamoDB (Req 2.5).
    """
    product_id = body.get("productId")
    if not isinstance(product_id, str) or not (1 <= len(product_id) <= MAX_PRODUCT_ID):
        return None, build_error_response(
            400, "MISSING_PARAMS", "a valid productId is required"
        )

    return product_id, None


def soft_delete_product(product_id: str) -> None:
    """
    Soft-delete a record by SETting deleted=true and deletedAt, preserving everything else.

    Only these two attributes are written, so productId, imageKey, productName, brand,
    presentation, expirationDate, createdAt, quantity, and unit are left untouched
    (Req 2.2). This is an UpdateItem (never DeleteItem) and never touches S3, so the
    image is provably preserved for a future restore feature (Req 2.3).

    The ConditionExpression makes the update fail when no record has the productId,
    which we surface as ProductNotFoundError (404) without GetItem/DeleteItem
    permissions (Req 8.3). A still-present but already-soft-deleted record still passes
    attribute_exists(productId), so re-deleting it returns 200, not 404.

    Transient DynamoDB errors are retried up to MAX_ATTEMPTS total; the conditional
    failure and non-transient errors are never retried (Req 2.8).
    """
    # deletedAt uses the same UTC ISO8601 format save-product uses for createdAt,
    # keeping timestamp formats consistent across the table.
    deleted_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            table.update_item(
                Key={"productId": product_id},
                UpdateExpression="SET #d = :true, #da = :now",
                # Aliased names sidestep any DynamoDB reserved-word collisions.
                ExpressionAttributeNames={"#d": "deleted", "#da": "deletedAt"},
                ExpressionAttributeValues={":true": True, ":now": deleted_at},
                ConditionExpression="attribute_exists(productId)",
            )
            return
        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            # Not-found: the record does not exist. Never retry; map to 404.
            if error_code == "ConditionalCheckFailedException":
                raise ProductNotFoundError(product_id) from e

            # Transient error with attempts remaining: back off and retry.
            if error_code in TRANSIENT_ERROR_CODES and attempt < MAX_ATTEMPTS:
                time.sleep(BACKOFF_BASE_SECONDS * attempt)
                continue

            # Non-transient error, or transient with no attempts left: propagate so
            # lambda_handler maps it to a 500 INTERNAL_ERROR.
            raise


def build_success_response(product_id: str) -> dict:
    """HTTP 200 confirming the soft delete, echoing back the productId (Req 2.4)."""
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps({"productId": product_id}),
    }


def lambda_handler(event, context) -> dict:
    """
    POST /delete-product
    Body: { productId }

    Validates the payload, soft-deletes the matching record (UpdateItem, no S3), and
    returns the productId on success.
    """
    try:
        try:
            body = json.loads(event.get("body", "{}"))
        except (json.JSONDecodeError, TypeError):
            return build_error_response(400, "INVALID_JSON", "Request body must be valid JSON")

        product_id, error_response = parse_and_validate_payload(body)
        if error_response:
            return error_response

        try:
            soft_delete_product(product_id)
        except ProductNotFoundError:
            return build_error_response(404, "NOT_FOUND", "Product not found")

        # Log only the non-identifying productId and outcome, never the request body
        # or any user-entered field values (no-PII logging property).
        logger.info("Product soft-deleted: productId=%s", product_id)

        return build_success_response(product_id)

    except ClientError as e:
        logger.error("DynamoDB error: %s", str(e))
        return build_error_response(500, "INTERNAL_ERROR", "Failed to delete product")
    except Exception:
        logger.exception("Unexpected error in delete-product handler")
        return build_error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")

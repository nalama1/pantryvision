import json
import os
import re
import uuid
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# DynamoDB client initialized at module level for connection reuse
dynamodb = boto3.resource("dynamodb")
TABLE_NAME = os.environ.get("TABLE_NAME", "pantryvision-products")
table = dynamodb.Table(TABLE_NAME)

# Regex to validate S3 object key format: UUID + image extension
OBJECT_KEY_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png|webp)$"
)

# CORS headers included in every response
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def lambda_handler(event, context) -> dict:
    """
    POST /save-product
    Body: { productName, brand?, presentation?, expirationDate?, imageKey, quantity?, unit? }

    Validates the request, generates IDs, applies defaults, and writes to DynamoDB.
    Returns the complete Product_Record on success.
    """
    try:
        try:
            body = json.loads(event.get("body", "{}"))
        except (json.JSONDecodeError, TypeError):
            return build_error_response(400, "INVALID_JSON", "Request body must be valid JSON")

        # Validate the request payload
        validation_error = validate_request(body)
        if validation_error:
            return validation_error

        # Build the complete product record with generated fields and defaults
        record = build_product_record(body)

        # Write to DynamoDB
        table.put_item(Item=record)

        logger.info("Product saved: productId=%s productName=%s", record["productId"], record["productName"])

        return build_success_response(record)

    except ClientError as e:
        logger.error("DynamoDB error: %s", str(e))
        return build_error_response(500, "INTERNAL_ERROR", "Failed to save product")
    except Exception:
        logger.exception("Unexpected error in save-product handler")
        return build_error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


def validate_request(body: dict) -> dict | None:
    """
    Validates the save-product request body.
    Returns an error response dict if validation fails, or None if valid.
    """
    missing_fields = []

    # Required: productName (non-empty after trim)
    product_name = body.get("productName", "")
    if not isinstance(product_name, str) or not product_name.strip():
        missing_fields.append("productName")

    # Required: imageKey (must match UUID-extension pattern)
    image_key = body.get("imageKey", "")
    if not image_key:
        missing_fields.append("imageKey")

    if missing_fields:
        return build_error_response(
            400, "MISSING_PARAMS",
            f"Missing required fields: {', '.join(missing_fields)}"
        )

    # Validate imageKey format
    if not OBJECT_KEY_PATTERN.match(image_key):
        return build_error_response(
            400, "INVALID_IMAGE_KEY",
            "imageKey must be a valid UUID with an image extension (jpg, jpeg, png, webp)"
        )

    # Validate quantity if provided
    quantity = body.get("quantity")
    if quantity is not None:
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            return build_error_response(
                400, "INVALID_QUANTITY",
                "quantity must be a positive integer"
            )

    return None


def build_product_record(body: dict) -> dict:
    """
    Generates productId, createdAt, applies defaults, and returns the complete record.
    """
    return {
        "productId": str(uuid.uuid4()),
        "productName": body.get("productName", "").strip(),
        "brand": body.get("brand", "").strip() if body.get("brand") else "",
        "presentation": body.get("presentation", "").strip() if body.get("presentation") else "",
        "expirationDate": body.get("expirationDate", "").strip() if body.get("expirationDate") else "",
        "imageKey": body["imageKey"],
        "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quantity": body.get("quantity", 1),
        "unit": body.get("unit", "unit").strip() if body.get("unit") else "unit",
    }


def build_success_response(record: dict) -> dict:
    """Constructs an HTTP 200 response with the saved Product_Record and CORS headers."""
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(record),
    }


def build_error_response(status_code: int, error_code: str, message: str) -> dict:
    """Constructs an error HTTP response with CORS headers."""
    log_level = logging.WARNING if status_code < 500 else logging.ERROR
    logger.log(log_level, "%s: %s", error_code, message)

    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps({
            "error": error_code,
            "message": message,
        }),
    }

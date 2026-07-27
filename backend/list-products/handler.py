import json
import os
import logging
from datetime import date

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients initialized at module level for connection reuse
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

TABLE_NAME = os.environ.get("TABLE_NAME", "pantryvision-products")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "pantryvision-product-images")
table = dynamodb.Table(TABLE_NAME)

PRESIGNED_URL_EXPIRATION_SECONDS = 300

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
}


def lambda_handler(event, context) -> dict:
    """
    GET /list-products

    Scans the products table, enriches each item with a presigned image URL,
    sorts by expiration date (soonest first, blanks last), and returns the list.
    """
    try:
        items = scan_all_products()
        enriched = [enrich_with_image_url(item) for item in items]
        sorted_items = sort_by_expiration(enriched)
        return build_success_response(sorted_items)
    except ClientError as e:
        logger.error("DynamoDB scan error: %s", str(e))
        return build_error_response(500, "INTERNAL_ERROR", "Failed to retrieve products")
    except Exception:
        logger.exception("Unexpected error in list-products handler")
        return build_error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


def scan_all_products() -> list[dict]:
    """Scans the products table, handling pagination via LastEvaluatedKey."""
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))

    return items


def enrich_with_image_url(item: dict) -> dict:
    """
    Returns a copy of item with 'imageUrl' set to a presigned GET URL
    (300s expiration) if imageKey is non-empty, otherwise None.
    Per-item presign failures are logged and result in imageUrl=None
    rather than failing the whole request.
    """
    enriched = dict(item)
    image_key = item.get("imageKey")

    if not image_key:
        enriched["imageUrl"] = None
        return enriched

    try:
        enriched["imageUrl"] = s3_client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": BUCKET_NAME, "Key": image_key},
            ExpiresIn=PRESIGNED_URL_EXPIRATION_SECONDS,
        )
    except ClientError as e:
        logger.warning("Failed to presign URL for imageKey=%s: %s", image_key, str(e))
        enriched["imageUrl"] = None

    return enriched


def sort_by_expiration(items: list[dict]) -> list[dict]:
    """
    Sorts items ascending by expirationDate; items with an empty
    expirationDate are placed after all items with a non-empty one.
    """
    def sort_key(item: dict) -> tuple:
        expiration = item.get("expirationDate") or ""
        # Empty dates sort last: (1, "") sorts after (0, "2025-01-01")
        return (1, "") if not expiration else (0, expiration)

    return sorted(items, key=sort_key)


def build_success_response(items: list[dict]) -> dict:
    """Constructs an HTTP 200 response with the product list and CORS headers."""
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(items, default=str),
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

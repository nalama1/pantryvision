import json
import os
import logging
from datetime import date

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from common.responses import CORS_HEADERS, build_error_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients initialized at module level for connection reuse
dynamodb = boto3.resource("dynamodb")
s3_client = boto3.client("s3")

TABLE_NAME = os.environ.get("TABLE_NAME", "pantryvision-products")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "pantryvision-product-images")
table = dynamodb.Table(TABLE_NAME)

PRESIGNED_URL_EXPIRATION_SECONDS = 300


def lambda_handler(event, context) -> dict:
    """
    GET /list-products[?includeDeleted=true]

    Scans the products table, enriches each item with a presigned image URL,
    sorts by expiration date (soonest first, blanks last), and returns the list.

    By default soft-deleted (inactive) records are excluded, preserving the
    behavior every existing caller relies on. When the request opts in via
    `?includeDeleted=true`, inactive records are returned too, carrying their
    stored `deleted`/`deletedAt` attributes so the client can distinguish them.
    """
    try:
        include_deleted = _wants_deleted(event)
        items = scan_all_products(include_deleted)
        enriched = [enrich_with_image_url(item) for item in items]
        sorted_items = sort_by_expiration(enriched)
        return build_success_response(sorted_items)
    except ClientError as e:
        logger.error("DynamoDB scan error: %s", str(e))
        return build_error_response(500, "INTERNAL_ERROR", "Failed to retrieve products")
    except Exception:
        logger.exception("Unexpected error in list-products handler")
        return build_error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


def _wants_deleted(event: dict) -> bool:
    """
    Returns True only when the request explicitly opts in to inactive records
    via a case-insensitive `includeDeleted=true` query parameter.

    This parse is total on purpose: API Gateway proxy integration sends
    `queryStringParameters` as None when no query string is present, and any
    value other than "true" (missing, empty, "false", "yes", ...) falls back to
    the default active-only behavior. That keeps the change backward compatible
    and impossible to error on a malformed parameter.
    """
    params = event.get("queryStringParameters") or {}
    value = str(params.get("includeDeleted") or "").strip().lower()
    return value == "true"


def scan_all_products(include_deleted: bool = False) -> list[dict]:
    """
    Scans the products table, handling pagination via LastEvaluatedKey.

    When `include_deleted` is False (the default), soft-deleted records are
    excluded. Records without the `deleted` attribute (legacy records written
    before soft-delete existed) are treated as not-deleted and still returned,
    so this stays backward compatible with no data migration required. When
    `include_deleted` is True, no filter is applied and inactive records are
    returned alongside active ones.
    """
    # Only build a FilterExpression for the default (active-only) mode. In
    # include-deleted mode we scan without a filter so inactive rows come back.
    scan_kwargs: dict = {}
    if not include_deleted:
        scan_kwargs["FilterExpression"] = (
            Attr("deleted").not_exists() | Attr("deleted").eq(False)
        )

    items = []
    response = table.scan(**scan_kwargs)
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"],
            **scan_kwargs,
        )
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

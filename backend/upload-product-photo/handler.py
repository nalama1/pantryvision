import json
import os
import uuid
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3", region_name=os.environ.get("AWS_REGION"))
BUCKET_NAME = os.environ["BUCKET_NAME"]
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
URL_EXPIRATION_SECONDS = 300


def lambda_handler(event, context):
    """Generate a presigned PUT URL for uploading a product photo to S3."""
    try:
        body = json.loads(event.get("body", "{}"))
    except (json.JSONDecodeError, TypeError):
        body = {}

    content_type = body.get("contentType")
    file_extension = body.get("fileExtension")

    # Validate required parameters
    if not content_type or not file_extension:
        return _error_response(400, "MISSING_PARAMS", "contentType and fileExtension are required")

    # Validate content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        return _error_response(400, "INVALID_CONTENT_TYPE", "Allowed types: image/jpeg, image/png, image/webp")

    # Generate unique object key
    object_key = f"{uuid.uuid4()}.{file_extension}"

    try:
        # Generate presigned URL with conditions
        upload_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",
            Params={
                "Bucket": BUCKET_NAME,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=URL_EXPIRATION_SECONDS,
        )
    except ClientError as e:
        logger.error("Failed to generate presigned URL: %s", str(e))
        return _error_response(500, "INTERNAL_ERROR", "Failed to generate upload URL")

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "uploadUrl": upload_url,
            "objectKey": object_key,
        }),
    }


def _error_response(status_code: int, error_code: str, message: str) -> dict:
    """Build a standardized error response."""
    log_level = logging.WARNING if status_code < 500 else logging.ERROR
    logger.log(log_level, "%s: %s", error_code, message)

    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({
            "error": error_code,
            "message": message,
        }),
    }

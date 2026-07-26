import json
import os
import re
import time
import logging
from datetime import datetime
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError
from PIL import Image, ImageOps

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# S3 client initialized at module level for connection reuse across invocations
s3_client = boto3.client("s3")
BUCKET_NAME = os.environ.get("BUCKET_NAME", "pantryvision-product-images")

# Bedrock client initialized at module level for connection reuse across invocations
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-pro-v1:0")
BEDROCK_TIMEOUT = int(os.environ.get("BEDROCK_TIMEOUT", "30"))

bedrock_config = Config(read_timeout=BEDROCK_TIMEOUT, connect_timeout=5)
bedrock_runtime = boto3.client("bedrock-runtime", config=bedrock_config)

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

# System prompt sets the AI's role and strict extraction rules
SYSTEM_PROMPT = """You are an expert OCR and product metadata extraction assistant.

Analyze the provided image carefully. The image might be upside down or rotated; make sure to inspect text in all orientations.

Rules:
- Product Name: Extract the exact main commercial product name visible on the container.
- Brand: Identify the primary brand name (e.g., Margarina, Flora, etc.).
- Presentation: Look for weight or volume (e.g., 200g, 500ml).
- Expiration Date: Extract expiration date in YYYY-MM-DD format (look for 'Vence', 'EXP', or date stamps). If year is 2 digits like '26', convert to '2026'.
- If any field is unclear or missing, do NOT hallucinate or guess from external knowledge. Return null for that field.
- Output JSON strictly conforming to the requested schema."""

# User prompt specifies the exact output format expected
USER_PROMPT = """Extract product data from this image. Return ONLY a valid JSON object with this exact structure:

{
  "productName": "string or null",
  "brand": "string or null",
  "presentation": "string or null",
  "expirationDate": "YYYY-MM-DD or null",
  "confidence": {
    "productName": "high|medium|low",
    "brand": "high|medium|low",
    "presentation": "high|medium|low",
    "expirationDate": "high|medium|low"
  }
}

Confidence levels:
- high: Text is clearly legible and unambiguous
- medium: Text is partially legible or inferred from context
- low: Not found or unreadable — return null for the value

Return ONLY the JSON object, no additional text or markdown formatting."""


# All-null fallback returned when extraction fails or produces unparseable output
ALL_NULL_EXTRACTION: dict = {
    "productName": None,
    "brand": None,
    "presentation": None,
    "expirationDate": None,
    "confidence": {
        "productName": "low",
        "brand": "low",
        "presentation": "low",
        "expirationDate": "low",
    },
}

# Fields expected in the extraction result
_EXTRACTION_FIELDS = ("productName", "brand", "presentation", "expirationDate")
_VALID_CONFIDENCE = {"high", "medium", "low"}


def normalize_date(date_str: str | None) -> str | None:
    """
    Normalizes various date formats found on product packaging to ISO 8601 (YYYY-MM-DD).

    Supported formats:
      - DD/MM/YYYY, DD-MM-YYYY
      - YYYY-MM-DD (pass-through)
      - DD MMM YYYY (e.g., "15 Mar 2025")
      - MMM YYYY (e.g., "Mar 2025") → first day of month
      - MM/YYYY (e.g., "03/2025") → first day of month
      - None → None
      - Invalid/unparseable → None (with warning logged)

    For ambiguous dates like "03/04/2025", prefers DD/MM/YYYY (day-first) interpretation.
    """
    if date_str is None:
        return None

    date_str = date_str.strip()
    if not date_str:
        return None

    # YYYY-MM-DD — pass through unchanged
    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # DD/MM/YYYY (day-first preference for ambiguous dates)
    try:
        parsed = datetime.strptime(date_str, "%d/%m/%Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # DD-MM-YYYY
    try:
        parsed = datetime.strptime(date_str, "%d-%m-%Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # DD MMM YYYY (e.g., "15 Mar 2025")
    try:
        parsed = datetime.strptime(date_str, "%d %b %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # MMM YYYY (e.g., "Mar 2025") → first day of month
    try:
        parsed = datetime.strptime(date_str, "%b %Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # MM/YYYY (e.g., "03/2025") → first day of month
    try:
        parsed = datetime.strptime(date_str, "%m/%Y")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        pass

    logger.warning("Unable to parse date: %s", date_str)
    return None


def parse_extraction(raw_response: str) -> dict:
    """
    Parses JSON from the raw Bedrock model text response into a standardized Extraction_Result.

    Handles both response formats:
      - Nested: {"productName": {"value": "...", "confidence": "high"}, ...}
      - Flat: {"productName": "...", "confidence": {"productName": "high", ...}}

    Strips markdown code fences if present. On malformed JSON, returns ALL_NULL_EXTRACTION.
    On partial results, preserves extracted fields and sets missing ones to null with "low" confidence.
    """
    if not raw_response or not raw_response.strip():
        logger.warning("Empty response from model")
        return dict(ALL_NULL_EXTRACTION)

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    text = raw_response.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Malformed JSON in model response: %s", raw_response[:200])
        return dict(ALL_NULL_EXTRACTION)

    if not isinstance(data, dict):
        logger.warning("Model response is not a JSON object: %s", type(data).__name__)
        return dict(ALL_NULL_EXTRACTION)

    # Detect response format: nested vs flat
    # Nested format: each field is {"value": ..., "confidence": ...}
    # Flat format: fields at top level, confidence in a separate "confidence" object
    is_nested = any(
        isinstance(data.get(field), dict) and "value" in data.get(field, {})
        for field in _EXTRACTION_FIELDS
        if field in data
    )

    result: dict = {
        "productName": None,
        "brand": None,
        "presentation": None,
        "expirationDate": None,
        "confidence": {
            "productName": "low",
            "brand": "low",
            "presentation": "low",
            "expirationDate": "low",
        },
    }

    if is_nested:
        # Nested format: {"productName": {"value": "Coca-Cola", "confidence": "high"}, ...}
        for field in _EXTRACTION_FIELDS:
            field_data = data.get(field)
            if isinstance(field_data, dict):
                value = field_data.get("value")
                confidence = field_data.get("confidence", "low")
                result[field] = value if value is not None else None
                if confidence in _VALID_CONFIDENCE:
                    result["confidence"][field] = confidence
                else:
                    result["confidence"][field] = "low"
            # If field is missing or not a dict in nested mode, it stays null/low
    else:
        # Flat format: {"productName": "Coca-Cola", "confidence": {"productName": "high"}}
        confidence_map = data.get("confidence", {})
        if not isinstance(confidence_map, dict):
            confidence_map = {}

        for field in _EXTRACTION_FIELDS:
            value = data.get(field)
            # Don't treat the "confidence" key as a field value
            if value is not None:
                result[field] = value
                # Use confidence from the confidence object, default to "low" if missing
                conf = confidence_map.get(field, "low")
                result["confidence"][field] = conf if conf in _VALID_CONFIDENCE else "low"
            else:
                result[field] = None
                result["confidence"][field] = "low"

    # Normalize expiration date to ISO 8601
    result["expirationDate"] = normalize_date(result["expirationDate"])

    return result


def lambda_handler(event, context) -> dict:
    """
    POST /extract-product-data
    Body: { "objectKey": "<uuid>.<ext>" }

    Validates the request and orchestrates the extraction pipeline.
    Returns an Extraction_Result or an error response.
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

        object_key = body["objectKey"]

        # Step 1: Retrieve image from S3
        image_result = retrieve_image(object_key)
        if image_result is None:
            return build_error_response(404, "IMAGE_NOT_FOUND", f"Image not found: {object_key}")

        image_bytes, image_format = image_result

        # Resize image to reduce Bedrock input tokens (max 1024px on longest side)
        image_bytes = resize_image(image_bytes, image_format)

        # Step 2: Invoke Bedrock for extraction
        raw_response = invoke_bedrock(image_bytes, image_format)
        if raw_response is None:
            # AI failure — return all-null result for manual entry
            fallback = dict(ALL_NULL_EXTRACTION)
            fallback["error"] = "AI extraction failed. Please enter product details manually."
            return build_success_response(fallback)

        # Step 3: Parse extraction response
        extraction_result = parse_extraction(raw_response)
        return build_success_response(extraction_result)

    except Exception:
        logger.exception("Unexpected error in extract-product-data handler")
        return build_error_response(500, "INTERNAL_ERROR", "An unexpected error occurred")


def validate_request(body: dict) -> dict | None:
    """
    Validates the extraction request body.
    Returns an error response dict if validation fails, or None if valid.
    """
    object_key = body.get("objectKey")

    if not object_key:
        return build_error_response(400, "MISSING_PARAMS", "objectKey is required")

    if not OBJECT_KEY_PATTERN.match(object_key):
        return build_error_response(400, "INVALID_OBJECT_KEY", "objectKey must be a valid UUID with an image extension (jpg, jpeg, png, webp)")

    return None


def retrieve_image(object_key: str) -> tuple[bytes, str] | None:
    """
    Retrieves a product image from S3.

    Returns a tuple of (image_bytes, image_format) where image_format is
    compatible with Bedrock Converse API ("jpeg", "png", or "webp").
    Returns None if the image does not exist (NoSuchKey).
    """
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=object_key)
        image_bytes = response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.warning("Image not found in S3: %s", object_key)
            return None
        raise

    # Derive format from file extension; map "jpg" to "jpeg" for Bedrock compatibility
    extension = object_key.rsplit(".", 1)[-1].lower()
    format_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
    image_format = format_map.get(extension, "jpeg")

    return (image_bytes, image_format)


def resize_image(image_bytes: bytes, image_format: str, max_side: int = 1024) -> bytes:
    """
    Scales down an image so its longest side does not exceed max_side pixels.

    Reduces Bedrock input token cost for large images while preserving
    text legibility via LANCZOS resampling. If the image is already within
    bounds, returns the original bytes unchanged (no re-encoding).
    """
    # Pillow format identifiers differ from Bedrock's lowercase strings
    pillow_format_map = {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}
    pil_format = pillow_format_map.get(image_format, "JPEG")

    try:
        img = Image.open(BytesIO(image_bytes))
        # Fix orientation from EXIF metadata (phone cameras embed rotation info)
        img = ImageOps.exif_transpose(img)
        original_w, original_h = img.size

        if original_w <= max_side and original_h <= max_side:
            return image_bytes

        # Scale proportionally so the longest side equals max_side
        scale = max_side / max(original_w, original_h)
        new_w = int(original_w * scale)
        new_h = int(original_h * scale)

        img = img.resize((new_w, new_h), Image.LANCZOS)
        logger.info("Image resized from %dx%d to %dx%d", original_w, original_h, new_w, new_h)

        buffer = BytesIO()
        img.save(buffer, format=pil_format)
        return buffer.getvalue()

    except Exception:
        # Don't block the pipeline if Pillow can't process the image
        logger.warning("Failed to resize image, using original bytes", exc_info=True)
        return image_bytes


def invoke_bedrock(image_bytes: bytes, image_format: str) -> str | None:
    """
    Invokes the configured Bedrock model via the Converse API with the product image.
    Uses a system prompt for role/rules and a user message with image + output format.

    Returns the model's text response containing extracted product JSON,
    or None if the invocation fails (timeout, client error).
    """
    start_time = time.time()

    try:
        response = bedrock_runtime.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{
                "role": "user",
                "content": [
                    {"image": {"format": image_format, "source": {"bytes": image_bytes}}},
                    {"text": USER_PROMPT}
                ]
            }],
            inferenceConfig={
                "maxTokens": 400,
                "temperature": 0
            }
        )
    except ReadTimeoutError:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Bedrock timeout: model=%s duration=%dms",
            BEDROCK_MODEL_ID, duration_ms
        )
        return None
    except ClientError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Bedrock client error: model=%s duration=%dms error=%s",
            BEDROCK_MODEL_ID, duration_ms, str(e)
        )
        return None

    duration_ms = int((time.time() - start_time) * 1000)
    input_tokens = response["usage"]["inputTokens"]
    output_tokens = response["usage"]["outputTokens"]

    logger.info(
        "Bedrock invocation: model=%s duration=%dms input_tokens=%d output_tokens=%d",
        BEDROCK_MODEL_ID, duration_ms, input_tokens, output_tokens
    )

    return response["output"]["message"]["content"][0]["text"]


def build_success_response(extraction: dict) -> dict:
    """Constructs an HTTP 200 response with the Extraction_Result and CORS headers."""
    return {
        "statusCode": 200,
        "headers": CORS_HEADERS,
        "body": json.dumps(extraction),
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

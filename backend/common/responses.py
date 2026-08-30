import json
import logging

# Single source of truth for CORS + structured error responses across all Lambdas.
# Centralizing error logging here keeps it in one audited place, which supports the
# no-PII logging property (only error codes and messages are logged, never payloads).
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
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

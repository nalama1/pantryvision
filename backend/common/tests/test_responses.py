"""Unit tests for backend/common/responses.py.

Covers the shared CORS headers and the structured error response builder,
including its logging behavior (WARNING for client errors, ERROR for
server errors) which supports the centralized, no-PII logging design.
"""

import json
import logging

from common.responses import CORS_HEADERS, build_error_response


class TestCorsHeaders:
    """Verifies the shared CORS header contract used by all Lambdas."""

    def test_content_type_is_json(self):
        assert CORS_HEADERS["Content-Type"] == "application/json"

    def test_allow_origin_is_wildcard(self):
        assert CORS_HEADERS["Access-Control-Allow-Origin"] == "*"

    def test_allow_headers(self):
        assert CORS_HEADERS["Access-Control-Allow-Headers"] == "Content-Type,Authorization"


class TestBuildErrorResponse:
    """Verifies the shape of the structured error response."""

    def test_client_error_400(self):
        response = build_error_response(400, "MISSING_PARAMS", "msg")

        assert response["statusCode"] == 400
        # headers must be the shared CORS headers object
        assert response["headers"] == CORS_HEADERS
        assert json.loads(response["body"]) == {
            "error": "MISSING_PARAMS",
            "message": "msg",
        }

    def test_server_error_500_same_shape(self):
        response = build_error_response(500, "INTERNAL_ERROR", "boom")

        assert response["statusCode"] == 500
        assert response["headers"] == CORS_HEADERS
        assert json.loads(response["body"]) == {
            "error": "INTERNAL_ERROR",
            "message": "boom",
        }


class TestErrorLogging:
    """Verifies log level selection: client errors -> WARNING, server errors -> ERROR."""

    def test_client_error_logs_warning(self, caplog):
        # Capture at the module logger so we see both WARNING and ERROR records.
        with caplog.at_level(logging.WARNING, logger="common.responses"):
            build_error_response(404, "NOT_FOUND", "product missing")

        matching = [
            record
            for record in caplog.records
            if record.levelno == logging.WARNING
            and "NOT_FOUND: product missing" in record.getMessage()
        ]
        assert matching, "expected a WARNING record with the error code and message"

    def test_server_error_logs_error(self, caplog):
        with caplog.at_level(logging.WARNING, logger="common.responses"):
            build_error_response(500, "INTERNAL_ERROR", "unexpected failure")

        matching = [
            record
            for record in caplog.records
            if record.levelno == logging.ERROR
            and "INTERNAL_ERROR: unexpected failure" in record.getMessage()
        ]
        assert matching, "expected an ERROR record with the error code and message"

    def test_client_error_does_not_log_at_error(self, caplog):
        with caplog.at_level(logging.WARNING, logger="common.responses"):
            build_error_response(400, "BAD_REQUEST", "invalid input")

        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert not error_records, "client errors must not be logged at ERROR level"

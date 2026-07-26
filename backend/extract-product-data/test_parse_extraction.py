"""Unit tests for parse_extraction and normalize_date functions."""

import os

# Set a dummy region so module-level boto3 clients can initialize during import
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import json
import pytest
from handler import normalize_date, parse_extraction, ALL_NULL_EXTRACTION


class TestNormalizeDate:
    """Tests for the normalize_date function."""

    def test_none_input(self):
        """None input should return None."""
        assert normalize_date(None) is None

    def test_empty_string(self):
        """Empty string should return None."""
        assert normalize_date("") is None

    def test_whitespace_only(self):
        """Whitespace-only string should return None."""
        assert normalize_date("   ") is None

    def test_iso_passthrough(self):
        """YYYY-MM-DD should pass through unchanged."""
        assert normalize_date("2025-03-15") == "2025-03-15"

    def test_dd_mm_yyyy_slash(self):
        """DD/MM/YYYY format should be normalized."""
        assert normalize_date("15/03/2025") == "2025-03-15"

    def test_dd_mm_yyyy_dash(self):
        """DD-MM-YYYY format should be normalized."""
        assert normalize_date("15-03-2025") == "2025-03-15"

    def test_dd_mmm_yyyy(self):
        """DD MMM YYYY format (e.g., '15 Mar 2025') should be normalized."""
        assert normalize_date("15 Mar 2025") == "2025-03-15"

    def test_mmm_yyyy(self):
        """MMM YYYY format (e.g., 'Mar 2025') should normalize to first day of month."""
        assert normalize_date("Mar 2025") == "2025-03-01"

    def test_mm_yyyy(self):
        """MM/YYYY format (e.g., '03/2025') should normalize to first day of month."""
        assert normalize_date("03/2025") == "2025-03-01"

    def test_ambiguous_date_prefers_day_first(self):
        """Ambiguous dates like '03/04/2025' should prefer DD/MM/YYYY (day=3, month=4)."""
        assert normalize_date("03/04/2025") == "2025-04-03"

    def test_invalid_date_returns_none(self):
        """Invalid/unparseable date strings should return None."""
        assert normalize_date("not-a-date") is None

    def test_leading_trailing_whitespace(self):
        """Leading/trailing whitespace should be stripped before parsing."""
        assert normalize_date("  2025-03-15  ") == "2025-03-15"


class TestParseExtraction:
    """Tests for the parse_extraction function."""

    def test_flat_format_complete(self):
        """Should parse a complete flat-format response correctly."""
        raw = json.dumps({
            "productName": "Coca-Cola",
            "brand": "Coca-Cola Company",
            "presentation": "600ml",
            "expirationDate": "2025-08-15",
            "confidence": {
                "productName": "high",
                "brand": "high",
                "presentation": "medium",
                "expirationDate": "low",
            },
        })
        result = parse_extraction(raw)
        assert result["productName"] == "Coca-Cola"
        assert result["brand"] == "Coca-Cola Company"
        assert result["presentation"] == "600ml"
        assert result["expirationDate"] == "2025-08-15"
        assert result["confidence"]["productName"] == "high"
        assert result["confidence"]["brand"] == "high"
        assert result["confidence"]["presentation"] == "medium"
        assert result["confidence"]["expirationDate"] == "low"

    def test_nested_format(self):
        """Should parse a nested-format response correctly."""
        raw = json.dumps({
            "productName": {"value": "Pepsi", "confidence": "high"},
            "brand": {"value": "PepsiCo", "confidence": "medium"},
            "presentation": {"value": "1L", "confidence": "high"},
            "expirationDate": {"value": "15/06/2025", "confidence": "medium"},
        })
        result = parse_extraction(raw)
        assert result["productName"] == "Pepsi"
        assert result["brand"] == "PepsiCo"
        assert result["presentation"] == "1L"
        assert result["expirationDate"] == "2025-06-15"
        assert result["confidence"]["productName"] == "high"
        assert result["confidence"]["brand"] == "medium"

    def test_markdown_code_fences_stripped(self):
        """Should strip markdown code fences before parsing."""
        inner = json.dumps({
            "productName": "Test",
            "brand": None,
            "presentation": None,
            "expirationDate": None,
            "confidence": {
                "productName": "high",
                "brand": "low",
                "presentation": "low",
                "expirationDate": "low",
            },
        })
        raw = f"```json\n{inner}\n```"
        result = parse_extraction(raw)
        assert result["productName"] == "Test"
        assert result["brand"] is None
        assert result["confidence"]["productName"] == "high"
        assert result["confidence"]["brand"] == "low"

    def test_malformed_json_returns_all_null(self):
        """Malformed JSON should return all-null extraction."""
        result = parse_extraction("this is not json at all")
        assert result["productName"] is None
        assert result["brand"] is None
        assert result["presentation"] is None
        assert result["expirationDate"] is None
        assert result["confidence"]["productName"] == "low"
        assert result["confidence"]["brand"] == "low"
        assert result["confidence"]["presentation"] == "low"
        assert result["confidence"]["expirationDate"] == "low"

    def test_empty_string_returns_all_null(self):
        """Empty input should return all-null extraction."""
        result = parse_extraction("")
        assert result["productName"] is None
        assert result["confidence"]["productName"] == "low"

    def test_partial_fields_preserved(self):
        """Partial results should preserve extracted fields, set missing to null."""
        raw = json.dumps({
            "productName": "Milk",
            "confidence": {"productName": "high"},
        })
        result = parse_extraction(raw)
        assert result["productName"] == "Milk"
        assert result["brand"] is None
        assert result["presentation"] is None
        assert result["expirationDate"] is None
        assert result["confidence"]["productName"] == "high"
        assert result["confidence"]["brand"] == "low"

    def test_date_normalization_in_extraction(self):
        """Expiration dates should be normalized to YYYY-MM-DD."""
        raw = json.dumps({
            "productName": "X",
            "brand": "Y",
            "presentation": "Z",
            "expirationDate": "15/03/2025",
            "confidence": {
                "productName": "high",
                "brand": "high",
                "presentation": "high",
                "expirationDate": "high",
            },
        })
        result = parse_extraction(raw)
        assert result["expirationDate"] == "2025-03-15"

    def test_non_dict_response_returns_all_null(self):
        """A JSON array or primitive should return all-null extraction."""
        result = parse_extraction("[1, 2, 3]")
        assert result["productName"] is None
        assert result["confidence"]["productName"] == "low"

    def test_invalid_confidence_value_defaults_to_low(self):
        """Invalid confidence values should default to 'low'."""
        raw = json.dumps({
            "productName": "Test",
            "brand": "Brand",
            "presentation": "500g",
            "expirationDate": "2025-12-31",
            "confidence": {
                "productName": "very_high",
                "brand": "unknown",
                "presentation": "high",
                "expirationDate": "medium",
            },
        })
        result = parse_extraction(raw)
        assert result["confidence"]["productName"] == "low"
        assert result["confidence"]["brand"] == "low"
        assert result["confidence"]["presentation"] == "high"
        assert result["confidence"]["expirationDate"] == "medium"

    def test_all_null_extraction_is_not_mutated(self):
        """parse_extraction should return a copy, not mutate ALL_NULL_EXTRACTION."""
        original = dict(ALL_NULL_EXTRACTION)
        original_conf = dict(ALL_NULL_EXTRACTION["confidence"])
        parse_extraction("invalid json!")
        assert ALL_NULL_EXTRACTION == original
        assert ALL_NULL_EXTRACTION["confidence"] == original_conf

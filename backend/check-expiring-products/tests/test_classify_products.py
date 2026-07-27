"""Unit tests for classify_products (Requirements 1.3, 1.4, 1.5)."""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handler import classify_products  # noqa: E402


def make_product(name: str, expiration_date: str | None) -> dict:
    product = {"productName": name}
    if expiration_date is not None:
        product["expirationDate"] = expiration_date
    return product


def test_empty_list_returns_empty_batch():
    assert classify_products([], date(2025, 1, 1)) == []


def test_product_exactly_at_day_plus_7_boundary_is_expiring():
    current_date = date(2025, 1, 1)
    expiration = current_date + timedelta(days=7)
    products = [make_product("Milk", expiration.isoformat())]

    result = classify_products(products, current_date)

    assert result == [
        {
            "product_name": "Milk",
            "expiration_date": expiration.isoformat(),
            "classification": "Expiring_Product",
        }
    ]


def test_product_exactly_at_day_minus_1_is_expired():
    current_date = date(2025, 1, 1)
    expiration = current_date - timedelta(days=1)
    products = [make_product("Yogurt", expiration.isoformat())]

    result = classify_products(products, current_date)

    assert result == [
        {
            "product_name": "Yogurt",
            "expiration_date": expiration.isoformat(),
            "classification": "Expired_Product",
        }
    ]


def test_product_with_missing_expiration_date_is_excluded():
    current_date = date(2025, 1, 1)
    products = [make_product("Rice", None)]

    result = classify_products(products, current_date)

    assert result == []


def test_product_with_expiration_date_equal_to_today_is_expiring_n_zero():
    current_date = date(2025, 1, 1)
    products = [make_product("Bread", current_date.isoformat())]

    result = classify_products(products, current_date)

    assert result == [
        {
            "product_name": "Bread",
            "expiration_date": current_date.isoformat(),
            "classification": "Expiring_Product",
        }
    ]


def test_product_beyond_expiring_window_is_excluded():
    current_date = date(2025, 1, 1)
    expiration = current_date + timedelta(days=8)
    products = [make_product("Canned Beans", expiration.isoformat())]

    result = classify_products(products, current_date)

    assert result == []


def test_mixed_batch_classifies_each_product_independently():
    current_date = date(2025, 1, 1)
    products = [
        make_product("Expired Cheese", (current_date - timedelta(days=3)).isoformat()),
        make_product("No Date Product", None),
        make_product("Expiring Soon", (current_date + timedelta(days=3)).isoformat()),
        make_product("Far Future", (current_date + timedelta(days=30)).isoformat()),
    ]

    result = classify_products(products, current_date)

    classifications = {entry["product_name"]: entry["classification"] for entry in result}
    assert classifications == {
        "Expired Cheese": "Expired_Product",
        "Expiring Soon": "Expiring_Product",
    }

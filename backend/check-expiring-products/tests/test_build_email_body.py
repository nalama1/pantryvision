"""Unit tests for build_email_body (Requirement 2.3)."""

import html
import sys
from datetime import date
from pathlib import Path

# Allow importing handler.py from the parent directory without a package install step.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from handler import build_email_body  # noqa: E402

EXPECTED_SUBJECT = "\U0001f6d2 PantryVision: You have products expiring in your pantry!"


def test_single_expiring_product():
    batch = [
        {
            "product_name": "Milk",
            "expiration_date": "2026-08-01",
            "classification": "Expiring_Product",
        }
    ]
    current_date = date(2026, 7, 31)

    subject, body = build_email_body(batch, current_date)

    assert subject == EXPECTED_SUBJECT
    assert "<table" in body
    assert "Milk" in body
    assert "Aug 1" in body
    assert "#F3E8FF" in body
    assert "#6B21A8" in body
    assert "\u23f3 Today" not in body  # sanity: not literally today
    assert "\u23f3 In 1 day" in body
    assert "\u23f0 Expiring this week (use them soon!)" in body
    # Expired block must not render when there are no expired products.
    assert "\u274c Expired products (toss or remove)" not in body


def test_single_expired_product():
    batch = [
        {
            "product_name": "Yogurt",
            "expiration_date": "2026-07-25",
            "classification": "Expired_Product",
        }
    ]
    current_date = date(2026, 7, 26)

    subject, body = build_email_body(batch, current_date)

    assert subject == EXPECTED_SUBJECT
    assert "<table" in body
    assert "Yogurt" in body
    assert "Jul 25 (Yesterday)" in body
    assert "#FEE2E2" in body
    assert "#991B1B" in body
    assert "\U0001f5d1\ufe0f Expired" in body
    assert "\u274c Expired products (toss or remove)" in body
    # Expiring block must not render when there are no expiring products.
    assert "\u23f0 Expiring this week (use them soon!)" not in body


def test_mixed_batch_lists_every_product_and_orders_expired_first():
    batch = [
        {
            "product_name": "Milk",
            "expiration_date": "2026-08-01",
            "classification": "Expiring_Product",
        },
        {
            "product_name": "Yogurt",
            "expiration_date": "2026-07-25",
            "classification": "Expired_Product",
        },
        {
            "product_name": "Cheese",
            "expiration_date": "2026-08-03",
            "classification": "Expiring_Product",
        },
    ]
    current_date = date(2026, 7, 31)

    subject, body = build_email_body(batch, current_date)

    assert subject == EXPECTED_SUBJECT

    # Every product must appear.
    for product in batch:
        assert product["product_name"] in body

    # Expired block should be listed before the expiring block.
    expired_heading_index = body.index("\u274c Expired products (toss or remove)")
    expiring_heading_index = body.index("\u23f0 Expiring this week (use them soon!)")
    assert expired_heading_index < expiring_heading_index

    yogurt_index = body.index("Yogurt")
    milk_index = body.index("Milk")
    cheese_index = body.index("Cheese")
    assert yogurt_index < milk_index
    assert yogurt_index < cheese_index

    # Countdown labels for the expiring-soon items.
    assert "\u23f3 In 1 day" in body  # Aug 1 relative to Jul 31
    assert "\u23f3 In 3 days" in body  # Aug 3 relative to Jul 31


def test_batch_with_special_characters_in_product_name():
    batch = [
        {
            "product_name": "Jamón Ibérico",
            "expiration_date": "2026-09-15",
            "classification": "Expiring_Product",
        },
        {
            "product_name": "Café Bustelo",
            "expiration_date": "2026-01-10",
            "classification": "Expired_Product",
        },
    ]
    current_date = date(2026, 1, 12)

    subject, body = build_email_body(batch, current_date)

    assert subject == EXPECTED_SUBJECT
    assert "Jamón Ibérico" in body
    assert "Café Bustelo" in body


def test_product_name_with_html_special_characters_is_escaped():
    batch = [
        {
            "product_name": "<script>alert('x')</script> & Co.",
            "expiration_date": "2026-09-15",
            "classification": "Expiring_Product",
        }
    ]
    current_date = date(2026, 9, 10)

    subject, body = build_email_body(batch, current_date)

    # The raw, unescaped markup must never appear in the output.
    assert "<script>alert('x')</script>" not in body
    # The escaped form must be present instead.
    assert html.escape("<script>alert('x')</script> & Co.") in body


def test_empty_batch_does_not_crash():
    subject, body = build_email_body([], date(2026, 1, 1))

    assert subject == EXPECTED_SUBJECT
    assert isinstance(body, str)
    assert "<html>" in body
    assert "Good news!" in body

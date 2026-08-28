from decimal import Decimal

from app.services.reconciliation import (
    classify,
    STATUS_MATCH,
    STATUS_AMOUNT_DIFFERENCE,
    STATUS_MISSING_IN_BANK,
    STATUS_MISSING_INTERNAL,
)


def test_match_when_amounts_are_equal():
    assert classify(Decimal("100.00"), Decimal("100.00")) == STATUS_MATCH


def test_amount_difference_when_amounts_differ():
    assert classify(Decimal("100.00"), Decimal("90.00")) == STATUS_AMOUNT_DIFFERENCE


def test_missing_in_bank_when_only_internal_exists():
    assert classify(Decimal("100.00"), None) == STATUS_MISSING_IN_BANK


def test_missing_internal_when_only_bank_exists():
    assert classify(None, Decimal("100.00")) == STATUS_MISSING_INTERNAL
